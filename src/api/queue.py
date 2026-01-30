"""Job queue with SQLite persistence and concurrent execution."""

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from .models import (
    EncodingRequest,
    JobInfo,
    JobStatus,
    QueueInfo,
    OutputMode,
)
from ..jobs import Job, JobRunner, JobState
from ..profiles.manager import ProfileManager

logger = logging.getLogger(__name__)


class JobQueue:
    """
    Async job queue with SQLite persistence.

    Handles:
    - Job submission and tracking
    - Concurrent execution with configurable limits
    - SQLite persistence for crash recovery
    - Job prioritization
    """

    def __init__(
        self,
        max_concurrent: int = 1,
        db_path: Optional[Path] = None,
    ):
        """
        Initialize job queue.

        Args:
            max_concurrent: Maximum concurrent encoding jobs
            db_path: Path to SQLite database (None for in-memory)
        """
        self.max_concurrent = max_concurrent
        self.db_path = db_path or Path(":memory:")

        self._running = False
        self._paused = False
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._active_jobs: dict[str, asyncio.Task] = {}

        self._conn: Optional[sqlite3.Connection] = None
        self._profile_manager = ProfileManager()
        self._job_runner = JobRunner()

    async def start(self):
        """Start the job queue."""
        self._running = True
        self._init_db()
        logger.info(f"Job queue started (max concurrent: {self.max_concurrent})")

        # Start the job processor
        asyncio.create_task(self._process_jobs())

    async def stop(self):
        """Stop the job queue gracefully."""
        self._running = False

        # Cancel active jobs
        for job_id, task in self._active_jobs.items():
            task.cancel()
            logger.info(f"Cancelled active job: {job_id}")

        # Wait for tasks to complete
        if self._active_jobs:
            await asyncio.gather(*self._active_jobs.values(), return_exceptions=True)

        self._executor.shutdown(wait=True)

        if self._conn:
            self._conn.close()

        logger.info("Job queue stopped")

    def _init_db(self):
        """Initialize SQLite database."""
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # Create jobs table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                profile TEXT NOT NULL,
                source_path TEXT NOT NULL,
                output_path TEXT,
                profile_index INTEGER DEFAULT 0,
                total_profiles INTEGER DEFAULT 1,
                parent_job_id TEXT,
                progress REAL DEFAULT 0.0,
                fps REAL DEFAULT 0.0,
                frames_processed INTEGER DEFAULT 0,
                frames_total INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                source_size_bytes INTEGER DEFAULT 0,
                output_size_bytes INTEGER DEFAULT 0,
                error_message TEXT,
                priority INTEGER DEFAULT 5,
                hardware_accel TEXT,
                backup BOOLEAN DEFAULT 1,
                backup_dir TEXT DEFAULT '.originals'
            )
        """)

        # Create index for efficient queries
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority DESC, created_at ASC)
        """)

        self._conn.commit()
        logger.info(f"Database initialized: {self.db_path}")

    async def submit(self, request: EncodingRequest) -> list[str]:
        """
        Submit encoding request and create jobs.

        Args:
            request: Encoding request

        Returns:
            List of created job IDs
        """
        job_ids = []
        source_path = Path(request.source)

        # Collect files to process
        files_to_process = []

        if source_path.is_file():
            files_to_process.append(source_path)
        elif source_path.is_dir():
            # Find matching files in directory
            for pattern in request.file_patterns:
                if request.recursive:
                    files_to_process.extend(source_path.rglob(pattern))
                else:
                    files_to_process.extend(source_path.glob(pattern))

        if not files_to_process:
            logger.warning(f"No files found matching patterns in: {source_path}")
            return []

        # Create jobs for each file and profile combination
        for file_path in files_to_process:
            parent_job_id = str(uuid.uuid4()) if len(request.profiles) > 1 else None

            for profile_index, profile_name in enumerate(request.profiles):
                job_id = str(uuid.uuid4())

                # Determine output path
                output_path = self._get_output_path(
                    file_path,
                    request,
                    profile_name,
                    profile_index,
                )

                # Insert job into database
                async with self._lock:
                    self._conn.execute("""
                        INSERT INTO jobs (
                            id, status, profile, source_path, output_path,
                            profile_index, total_profiles, parent_job_id,
                            created_at, priority, hardware_accel, backup, backup_dir,
                            source_size_bytes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job_id,
                        JobStatus.PENDING.value,
                        profile_name,
                        str(file_path),
                        str(output_path) if output_path else None,
                        profile_index,
                        len(request.profiles),
                        parent_job_id,
                        datetime.now().isoformat(),
                        request.priority,
                        request.hardware_accel,
                        request.backup if request.output_mode == OutputMode.REPLACE else False,
                        request.backup_dir,
                        file_path.stat().st_size if file_path.exists() else 0,
                    ))
                    self._conn.commit()

                job_ids.append(job_id)
                logger.info(f"Created job {job_id}: {file_path.name} -> {profile_name}")

        return job_ids

    def _get_output_path(
        self,
        source_file: Path,
        request: EncodingRequest,
        profile_name: str,
        profile_index: int,
    ) -> Optional[Path]:
        """Determine output path for a job."""
        output_filename = request.get_output_filename(source_file, profile_name, profile_index)

        if request.output_mode == OutputMode.REPLACE:
            # Replace in-place (output goes to temp, then replaces original)
            return source_file.parent / output_filename
        else:
            # Output to destination
            if not request.destination:
                return None

            dest_base = Path(request.destination)

            if request.preserve_structure:
                # Preserve folder structure
                try:
                    relative = source_file.parent.relative_to(Path(request.source))
                    return dest_base / relative / output_filename
                except ValueError:
                    return dest_base / output_filename
            else:
                return dest_base / output_filename

    async def _process_jobs(self):
        """Background task to process pending jobs."""
        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                # Check if we can start more jobs
                if len(self._active_jobs) >= self.max_concurrent:
                    await asyncio.sleep(0.5)
                    continue

                # Get next pending job
                job = await self._get_next_pending_job()
                if not job:
                    await asyncio.sleep(1)
                    continue

                # Start the job
                task = asyncio.create_task(self._execute_job(job["id"]))
                self._active_jobs[job["id"]] = task

                # Clean up completed tasks
                for job_id in list(self._active_jobs.keys()):
                    if self._active_jobs[job_id].done():
                        del self._active_jobs[job_id]

            except Exception as e:
                logger.error(f"Error in job processor: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _get_next_pending_job(self) -> Optional[dict]:
        """Get the next pending job by priority."""
        async with self._lock:
            cursor = self._conn.execute("""
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """, (JobStatus.PENDING.value,))
            row = cursor.fetchone()
            return dict(row) if row else None

    async def _execute_job(self, job_id: str):
        """Execute a single job."""
        try:
            # Update status to running
            await self._update_job_status(job_id, JobStatus.RUNNING)

            # Get job details from database (includes multi-profile context)
            async with self._lock:
                cursor = self._conn.execute(
                    """SELECT id, profile, source_path, output_path, hardware_accel,
                              profile_index, total_profiles, parent_job_id
                       FROM jobs WHERE id = ?""",
                    (job_id,)
                )
                row = cursor.fetchone()

            if not row:
                logger.error(f"Job not found: {job_id}")
                return

            hardware_accel = row["hardware_accel"]
            profile_index = row["profile_index"] or 0
            total_profiles = row["total_profiles"] or 1
            parent_job_id = row["parent_job_id"]
            output_path = Path(row["output_path"]) if row["output_path"] else None

            # Create Job object for runner
            job = Job(
                source_path=Path(row["source_path"]),
                profile_name=row["profile"],
                hardware_accel=hardware_accel,
            )
            job.id = job_id
            job.output_path = output_path

            # Execute in thread pool (blocking FFmpeg operation)
            loop = asyncio.get_event_loop()

            def run_job():
                return self._job_runner.execute(
                    job,
                    progress_callback=lambda j: self._sync_update_progress(job_id, j),
                    profile_index=profile_index,
                    total_profiles=total_profiles,
                    parent_job_id=parent_job_id,
                )

            completed_job = await loop.run_in_executor(self._executor, run_job)

            # Update job with results
            await self._update_job_completed(job_id, completed_job)

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            await self._update_job_failed(job_id, str(e))

        finally:
            # Remove from active jobs
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]

    def _sync_update_progress(self, job_id: str, job: Job):
        """Synchronously update job progress (called from thread)."""
        try:
            self._conn.execute("""
                UPDATE jobs SET
                    progress = ?,
                    fps = ?,
                    frames_processed = ?,
                    frames_total = ?
                WHERE id = ?
            """, (
                job.progress_percent,
                job.current_fps,
                job.frames_processed,
                job.frames_total,
                job_id,
            ))
            self._conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update progress for {job_id}: {e}")

    async def _update_job_status(self, job_id: str, status: JobStatus):
        """Update job status."""
        async with self._lock:
            now = datetime.now().isoformat()
            if status == JobStatus.RUNNING:
                self._conn.execute("""
                    UPDATE jobs SET status = ?, started_at = ? WHERE id = ?
                """, (status.value, now, job_id))
            else:
                self._conn.execute("""
                    UPDATE jobs SET status = ? WHERE id = ?
                """, (status.value, job_id))
            self._conn.commit()

    async def _update_job_completed(self, job_id: str, job: Job):
        """Update job as completed."""
        async with self._lock:
            self._conn.execute("""
                UPDATE jobs SET
                    status = ?,
                    completed_at = ?,
                    progress = 100.0,
                    output_size_bytes = ?,
                    output_path = ?
                WHERE id = ?
            """, (
                JobStatus.COMPLETED.value,
                datetime.now().isoformat(),
                job.output_size_bytes,
                str(job.output_path) if job.output_path else None,
                job_id,
            ))
            self._conn.commit()
            logger.info(f"Job completed: {job_id}")

    async def _update_job_failed(self, job_id: str, error: str):
        """Update job as failed."""
        async with self._lock:
            self._conn.execute("""
                UPDATE jobs SET
                    status = ?,
                    completed_at = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                JobStatus.FAILED.value,
                datetime.now().isoformat(),
                error,
                job_id,
            ))
            self._conn.commit()
            logger.error(f"Job failed: {job_id} - {error}")

    async def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job by ID."""
        async with self._lock:
            cursor = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_job_info(row)

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobInfo]:
        """List jobs with optional filtering."""
        async with self._lock:
            if status:
                cursor = self._conn.execute("""
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (status.value, limit, offset))
            else:
                cursor = self._conn.execute("""
                    SELECT * FROM jobs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

            return [self._row_to_job_info(row) for row in cursor.fetchall()]

    async def count_jobs(self, status: Optional[JobStatus] = None) -> int:
        """Count jobs with optional filtering."""
        async with self._lock:
            if status:
                cursor = self._conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status = ?",
                    (status.value,)
                )
            else:
                cursor = self._conn.execute("SELECT COUNT(*) FROM jobs")
            return cursor.fetchone()[0]

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = await self.get_job(job_id)
        if not job:
            return False

        if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return False

        # Cancel running task if exists
        if job_id in self._active_jobs:
            self._active_jobs[job_id].cancel()

        await self._update_job_status(job_id, JobStatus.CANCELLED)
        return True

    async def retry_job(self, job_id: str) -> Optional[JobInfo]:
        """Retry a failed job."""
        job = await self.get_job(job_id)
        if not job or job.status != JobStatus.FAILED:
            return None

        async with self._lock:
            self._conn.execute("""
                UPDATE jobs SET
                    status = ?,
                    error_message = NULL,
                    progress = 0.0,
                    started_at = NULL,
                    completed_at = NULL
                WHERE id = ?
            """, (JobStatus.PENDING.value, job_id))
            self._conn.commit()

        return await self.get_job(job_id)

    async def get_queue_info(self) -> QueueInfo:
        """Get queue statistics."""
        async with self._lock:
            cursor = self._conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM jobs
            """)
            row = cursor.fetchone()

            return QueueInfo(
                total_jobs=row["total"] or 0,
                pending_jobs=row["pending"] or 0,
                running_jobs=row["running"] or 0,
                completed_jobs=row["completed"] or 0,
                failed_jobs=row["failed"] or 0,
                max_concurrent=self.max_concurrent,
                current_concurrent=len(self._active_jobs),
            )

    async def pause(self):
        """Pause the queue."""
        self._paused = True
        logger.info("Queue paused")

    async def resume(self):
        """Resume the queue."""
        self._paused = False
        logger.info("Queue resumed")

    async def clear_completed(self) -> int:
        """Clear completed jobs."""
        async with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM jobs WHERE status = ?",
                (JobStatus.COMPLETED.value,)
            )
            self._conn.commit()
            return cursor.rowcount

    async def clear_failed(self) -> int:
        """Clear failed jobs."""
        async with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM jobs WHERE status = ?",
                (JobStatus.FAILED.value,)
            )
            self._conn.commit()
            return cursor.rowcount

    def _row_to_job_info(self, row: sqlite3.Row) -> JobInfo:
        """Convert database row to JobInfo."""
        return JobInfo(
            id=row["id"],
            status=JobStatus(row["status"]),
            profile=row["profile"],
            source_path=row["source_path"],
            output_path=row["output_path"],
            profile_index=row["profile_index"],
            total_profiles=row["total_profiles"],
            parent_job_id=row["parent_job_id"],
            progress=row["progress"],
            fps=row["fps"],
            frames_processed=row["frames_processed"],
            frames_total=row["frames_total"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            source_size_bytes=row["source_size_bytes"],
            output_size_bytes=row["output_size_bytes"],
            error_message=row["error_message"],
        )

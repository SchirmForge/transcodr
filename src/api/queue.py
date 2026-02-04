"""Job queue with SQLite persistence and concurrent execution."""

import asyncio
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from ..watcher.folder_processor import FolderProcessor
from .models import (
    EncodingRequest,
    JobInfo,
    JobStatus,
    QueueInfo,
    OutputMode,
    WatchfolderContext,
)
from ..jobs import Job, JobRunner, JobState, OutputMode
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
        temp_dir: Optional[Path] = None,
        duration_tolerance_seconds: float = 5.0,
    ):
        """
        Initialize job queue.

        Args:
            max_concurrent: Maximum concurrent encoding jobs
            db_path: Path to SQLite database (None for in-memory)
            temp_dir: Temporary directory for encoding (None for system temp)
        """
        self.max_concurrent = max_concurrent
        self.db_path = db_path or Path(":memory:")

        self._running = False
        self._paused = False
        self._lock = asyncio.Lock()
        self._db_lock = threading.Lock()  # For thread-safe DB writes from worker threads
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._active_jobs: dict[str, asyncio.Task] = {}

        self._conn: Optional[sqlite3.Connection] = None
        self._profile_manager = ProfileManager()
        self._job_runner = JobRunner(
            temp_dir=temp_dir,
            duration_tolerance_seconds=duration_tolerance_seconds,
        )

        # Folder processors for folder sources (continuous monitoring)
        self._folder_processors: dict[str, FolderProcessor] = {}
        self._folder_requests: dict[str, EncodingRequest] = {}  # folder_key -> original request
        self._folder_monitor_tasks: dict[str, asyncio.Task] = {}
        self._job_to_folder: dict[str, str] = {}  # job_id -> folder_key (for completion tracking)

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

    def set_max_concurrent(self, max_concurrent: int) -> None:
        """
        Update the maximum concurrent jobs limit.

        Changes take effect immediately:
        - If increased: pending jobs will start on next processor iteration
        - If decreased: running jobs continue, new jobs wait until under limit
        """
        old_value = self.max_concurrent
        self.max_concurrent = max_concurrent
        if old_value != max_concurrent:
            logger.info(f"Max concurrent jobs updated: {old_value} -> {max_concurrent}")

    def clear_profile_cache(self) -> None:
        """Clear the profile cache to force reload from disk on next use."""
        self._profile_manager.clear_cache()

    def _init_db(self):
        """Initialize SQLite database."""
        # Use isolation_level=None for autocommit mode to avoid
        # "cannot start a transaction within a transaction" errors
        # when multiple concurrent jobs complete simultaneously
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,
        )
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
                backup_dir TEXT DEFAULT '.originals',
                output_mode TEXT DEFAULT 'replace',
                delete_source BOOLEAN DEFAULT 0
            )
        """)

        # Migration: add output_mode column if it doesn't exist (for existing databases)
        try:
            self._conn.execute("SELECT output_mode FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding output_mode column")
            self._conn.execute("ALTER TABLE jobs ADD COLUMN output_mode TEXT DEFAULT 'replace'")

        # Migration: add delete_source column if it doesn't exist
        try:
            self._conn.execute("SELECT delete_source FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding delete_source column")
            self._conn.execute("ALTER TABLE jobs ADD COLUMN delete_source BOOLEAN DEFAULT 0")

        # Migration: add watchfolder_context column if it doesn't exist
        try:
            self._conn.execute("SELECT watchfolder_context FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding watchfolder_context column")
            self._conn.execute("ALTER TABLE jobs ADD COLUMN watchfolder_context TEXT")

        # Create index for efficient queries
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority DESC, created_at ASC)
        """)

        logger.info(f"Database initialized: {self.db_path}")

    async def submit(self, request: EncodingRequest) -> list[str]:
        """
        Submit encoding request and create jobs.

        For single files: submits immediately.
        For folders: uses FolderProcessor for stability detection and continuous monitoring.

        Args:
            request: Encoding request

        Returns:
            List of created job IDs (initial batch for folders)
        """
        source_path = Path(request.source)

        if source_path.is_file():
            # Single file - submit immediately
            return await self._submit_files([source_path], request)
        elif source_path.is_dir():
            # Folder - use FolderProcessor for continuous monitoring
            return await self._submit_folder(source_path, request)
        else:
            logger.warning(f"Source path does not exist: {source_path}")
            return []

    async def _submit_folder(self, folder_path: Path, request: EncodingRequest) -> list[str]:
        """
        Submit folder with continuous monitoring using FolderProcessor.

        Files are detected with stability checking, and new files added during
        encoding are also processed.

        Args:
            folder_path: Path to folder
            request: Encoding request

        Returns:
            List of job IDs for initially ready files
        """
        # Create folder processor
        processor = FolderProcessor(
            file_patterns=request.file_patterns,
            stability_scans=2,  # Default stability scans
            scan_interval=5.0,  # Default scan interval
            recursive=request.recursive,
        )
        folder_key = processor.register_folder(folder_path)

        # Store processor and request for monitoring
        self._folder_processors[folder_key] = processor
        self._folder_requests[folder_key] = request

        # Initial scan
        processor.scan_folder(folder_key)

        # Submit initially ready files
        job_ids = []
        for file_path in processor.get_ready_files(folder_key):
            ids = await self._submit_files([file_path], request, folder_key=folder_key)
            job_ids.extend(ids)
            processor.mark_file_submitted(folder_key, file_path)

        # Start background monitoring task
        monitor_task = asyncio.create_task(self._monitor_folder(folder_key))
        self._folder_monitor_tasks[folder_key] = monitor_task

        logger.info(
            f"Folder submitted for processing: {folder_path.name} "
            f"({len(job_ids)} initial jobs)"
        )
        return job_ids

    async def _monitor_folder(self, folder_key: str):
        """
        Background task to monitor folder for new files.

        Continues until folder is complete (no pending jobs and no new files).
        """
        processor = self._folder_processors.get(folder_key)
        request = self._folder_requests.get(folder_key)

        if not processor or not request:
            return

        try:
            while not processor.is_folder_complete(folder_key):
                await asyncio.sleep(processor.scan_interval)

                # Re-scan for new files
                processor.scan_folder(folder_key)

                # Submit newly ready files
                for file_path in processor.get_ready_files(folder_key):
                    await self._submit_files([file_path], request, folder_key=folder_key)
                    processor.mark_file_submitted(folder_key, file_path)

            # Folder complete - get stats before cleanup
            stats = processor.get_folder_stats(folder_key)
            folder_path = processor.complete_folder(folder_key)

            logger.info(
                f"Folder processing complete: {folder_path.name if folder_path else folder_key} "
                f"({stats.get('completed_jobs', 0)} succeeded, {stats.get('failed_jobs', 0)} failed)"
            )

        except asyncio.CancelledError:
            logger.info(f"Folder monitoring cancelled: {folder_key}")
        except Exception as e:
            logger.error(f"Error monitoring folder {folder_key}: {e}", exc_info=True)
        finally:
            # Cleanup
            self._folder_processors.pop(folder_key, None)
            self._folder_requests.pop(folder_key, None)
            self._folder_monitor_tasks.pop(folder_key, None)

    async def _submit_files(
        self,
        files: list[Path],
        request: EncodingRequest,
        folder_key: Optional[str] = None
    ) -> list[str]:
        """
        Submit a list of files for encoding.

        Args:
            files: List of file paths to encode
            request: Encoding request with profiles and settings
            folder_key: Optional folder key for tracking

        Returns:
            List of created job IDs
        """
        job_ids = []

        for file_path in files:
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

                # Serialize watchfolder_context if present
                watchfolder_context_json = None
                if request.watchfolder_context:
                    import json
                    watchfolder_context_json = json.dumps(request.watchfolder_context.model_dump())

                # Insert job into database
                async with self._lock:
                    self._conn.execute("""
                        INSERT INTO jobs (
                            id, status, profile, source_path, output_path,
                            profile_index, total_profiles, parent_job_id,
                            created_at, priority, hardware_accel, backup, backup_dir,
                            source_size_bytes, output_mode, delete_source, watchfolder_context
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        request.output_mode.value,
                        request.delete_source,
                        watchfolder_context_json,
                    ))
        
                job_ids.append(job_id)

                # Track job-to-folder association for completion handling
                if folder_key:
                    self._job_to_folder[job_id] = folder_key

                folder_info = f" (folder: {Path(folder_key).name})" if folder_key else ""
                logger.info(f"Created job {job_id}: {file_path.name} -> {profile_name}{folder_info}")

        return job_ids

    def _get_output_path(
        self,
        source_file: Path,
        request: EncodingRequest,
        profile_name: str,
        profile_index: int,
    ) -> Optional[Path]:
        """Determine output path for a job."""
        container = None
        try:
            profile = self._profile_manager.load_profile(profile_name)
            container = profile.container
        except Exception as e:
            logger.warning(f"Failed to load profile '{profile_name}' for container: {e}")

        output_filename = request.get_output_filename(
            source_file,
            profile_name,
            profile_index,
            container=container,
        )

        if request.output_mode == OutputMode.REPLACE:
            # Replace in-place (output goes to temp, then replaces original)
            return source_file.parent / output_filename
        else:
            # Output to destination
            if not request.destination:
                return None

            dest_base = Path(request.destination)

            # Preserve folder structure if requested
            if request.preserve_structure:
                try:
                    relative = source_file.parent.relative_to(Path(request.source))
                    dest_base = dest_base / relative
                except ValueError:
                    pass

            # Create profile subfolder if requested
            if request.create_profile_folders:
                dest_base = dest_base / profile_name

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

                # Small delay to prevent tight looping if jobs fail quickly
                await asyncio.sleep(0.1)

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
                              profile_index, total_profiles, parent_job_id, output_mode,
                              delete_source, watchfolder_context
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
            output_mode_str = row["output_mode"] or "replace"
            output_mode = OutputMode(output_mode_str)
            delete_source = bool(row["delete_source"]) if row["delete_source"] is not None else False

            # Deserialize watchfolder_context if present
            watchfolder_context = None
            if row["watchfolder_context"]:
                import json
                ctx_data = json.loads(row["watchfolder_context"])
                watchfolder_context = WatchfolderContext(**ctx_data)

            # Create Job object for runner
            job = Job(
                source_path=Path(row["source_path"]),
                profile_name=row["profile"],
                hardware_accel=hardware_accel,
                output_mode=output_mode,
                delete_source=delete_source,
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
                    watchfolder_context=watchfolder_context,
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
            with self._db_lock:
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
            logger.info(f"Job completed: {job_id}")

        # Notify folder processor if job belongs to a folder
        self._notify_folder_job_complete(job_id, success=True)

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
            logger.error(f"Job failed: {job_id} - {error}")

        # Notify folder processor if job belongs to a folder
        self._notify_folder_job_complete(job_id, success=False)

    def _notify_folder_job_complete(self, job_id: str, success: bool):
        """Notify folder processor that a job has completed."""
        folder_key = self._job_to_folder.pop(job_id, None)
        if folder_key:
            processor = self._folder_processors.get(folder_key)
            if processor:
                processor.mark_job_completed(folder_key, success=success)

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
            return cursor.rowcount

    async def clear_failed(self) -> int:
        """Clear failed jobs."""
        async with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM jobs WHERE status = ?",
                (JobStatus.FAILED.value,)
            )
            return cursor.rowcount

    async def purge_all(self, force: bool = False) -> int:
        """
        Purge all jobs from the database.

        Args:
            force: If True, also cancel and remove running/pending jobs

        Returns:
            Number of jobs purged
        """
        async with self._lock:
            if force:
                # Cancel all active jobs first
                for job_id, task in list(self._active_jobs.items()):
                    task.cancel()
                    logger.info(f"Cancelled active job during purge: {job_id}")
                self._active_jobs.clear()

                # Delete all jobs
                cursor = self._conn.execute("DELETE FROM jobs")
            else:
                # Only delete non-active jobs (completed, failed, cancelled)
                cursor = self._conn.execute(
                    "DELETE FROM jobs WHERE status NOT IN (?, ?)",
                    (JobStatus.PENDING.value, JobStatus.RUNNING.value)
                )

            count = cursor.rowcount
            logger.info(f"Purged {count} jobs from database (force={force})")
            return count

    def _row_to_job_info(self, row: sqlite3.Row) -> JobInfo:
        """Convert database row to JobInfo."""
        return JobInfo(
            id=row["id"],
            status=JobStatus(row["status"]),
            profile=row["profile"],
            source_path=row["source_path"],
            output_path=row["output_path"],
            profile_index=row["profile_index"] or 0,
            total_profiles=row["total_profiles"] or 1,
            parent_job_id=row["parent_job_id"],
            progress=row["progress"] or 0.0,
            fps=row["fps"] or 0.0,
            frames_processed=row["frames_processed"] or 0,
            frames_total=row["frames_total"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            source_size_bytes=row["source_size_bytes"] or 0,
            output_size_bytes=row["output_size_bytes"] or 0,
            error_message=row["error_message"],
        )

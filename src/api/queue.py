"""Job queue with SQLite persistence and concurrent execution."""

import asyncio
import json
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
from ..core.errors import ValidationError
from ..profiles.store import get_profile_manager, clear_profile_cache
from ..version import APP_VERSION, DB_COMPATIBLE_VERSIONS
from ..notifications.service import NotificationService

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
        profile_name_separator: str = "_",
        root_media: Optional[Path] = None,
        min_free_space_gb: int = 10,
        on_extension_mismatch: str = "rename",
        enable_temp_copy: bool = False,
        notify_service: Optional[NotificationService] = None,
    ):
        """
        Initialize job queue.

        Args:
            max_concurrent: Maximum concurrent encoding jobs
            db_path: Path to SQLite database (None for in-memory)
            temp_dir: Temporary directory for encoding (None for system temp)
            duration_tolerance_seconds: Tolerance for duration validation
            profile_name_separator: Separator between filename and profile name
            root_media: Base path for $root_media placeholder expansion
            min_free_space_gb: Minimum free space safety margin in GB
            on_extension_mismatch: Policy for extension mismatch in replace mode (rename/reject/keep)
            enable_temp_copy: Global default for source temp-copy (overridable per-request)
            notify_service: Notification service instance (None = notifications disabled)
        """
        self.max_concurrent = max_concurrent
        self.db_path = db_path or Path(":memory:")
        self._profile_name_separator = profile_name_separator
        self._root_media = root_media
        self._enable_temp_copy = enable_temp_copy
        self._notify_service: Optional[NotificationService] = notify_service

        self._running = False
        self._paused = False
        self._lock = asyncio.Lock()
        self._db_lock = threading.Lock()  # For thread-safe DB writes from worker threads
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._active_jobs: dict[str, asyncio.Task] = {}
        # True when queue has no pending/running jobs (to detect idle transitions)
        self._queue_was_empty: bool = True

        self._conn: Optional[sqlite3.Connection] = None
        self._profile_manager = get_profile_manager()
        self._job_runner = JobRunner(
            temp_dir=temp_dir,
            duration_tolerance_seconds=duration_tolerance_seconds,
            min_free_space_gb=min_free_space_gb,
            on_extension_mismatch=on_extension_mismatch,
        )

        # Folder processors for folder sources (continuous monitoring)
        self._folder_processors: dict[str, FolderProcessor] = {}
        self._folder_requests: dict[str, EncodingRequest] = {}  # folder_key -> original request
        self._folder_batch_ids: dict[str, str] = {}  # folder_key -> batch_id
        self._folder_monitor_tasks: dict[str, asyncio.Task] = {}
        self._job_to_folder: dict[str, str] = {}  # job_id -> folder_key (for completion tracking)

        # Per-source concurrency tracking
        self._source_running_counts: dict[str, int] = {}  # source_id -> running count
        self._source_limits: dict[str, int] = {}  # source_id -> max_concurrent

        # Track cancelled jobs so runner can detect cancellation vs failure
        self._cancelled_job_ids: set[str] = set()

        # In-memory runtime ETA snapshots for active jobs (not persisted to DB)
        self._runtime_eta: dict[str, dict[str, object]] = {}
        self._runtime_eta_lock = threading.Lock()

    async def start(self):
        """Start the job queue."""
        self._running = True
        with self._runtime_eta_lock:
            self._runtime_eta.clear()
        self._init_db()

        # Reset stale active-state jobs from previous daemon lifecycle to pending.
        # This covers both graceful shutdown (interrupted) and unexpected exits
        # where rows may remain marked as running.
        cursor = self._conn.execute("""
            UPDATE jobs
            SET status = ?,
                started_at = NULL,
                progress = 0.0,
                fps = 0.0,
                frames_processed = 0,
                frames_total = 0
            WHERE status IN (?, ?)
        """, (
            JobStatus.PENDING.value,
            JobStatus.INTERRUPTED.value,
            JobStatus.RUNNING.value,
        ))
        if cursor.rowcount > 0:
            logger.info(
                f"Reset {cursor.rowcount} stale active jobs to pending for retry"
            )
        self._conn.commit()

        logger.info(f"Job queue started (max concurrent: {self.max_concurrent})")

        # Start the job processor
        asyncio.create_task(self._process_jobs())

    async def stop(self):
        """Stop the job queue gracefully."""
        self._running = False

        # Signal job runner to shut down gracefully (terminates FFmpeg)
        self._job_runner.request_shutdown()

        # Cancel active asyncio tasks
        for job_id, task in self._active_jobs.items():
            task.cancel()
            logger.info(f"Interrupted active job: {job_id}")

        # Wait for tasks to complete
        if self._active_jobs:
            await asyncio.gather(*self._active_jobs.values(), return_exceptions=True)

        # Mark any jobs still in RUNNING state as INTERRUPTED
        # (they may not have been updated by the job runner if it was mid-execution)
        async with self._lock:
            cursor = self._conn.execute("""
                UPDATE jobs SET status = ?
                WHERE status = ?
            """, (JobStatus.INTERRUPTED.value, JobStatus.RUNNING.value))
            if cursor.rowcount > 0:
                logger.info(f"Marked {cursor.rowcount} running jobs as interrupted")
            self._conn.commit()

        self._executor.shutdown(wait=True)

        if self._conn:
            self._conn.close()

        with self._runtime_eta_lock:
            self._runtime_eta.clear()

        logger.info("Job queue stopped")

    def set_max_concurrent(self, max_concurrent: int) -> None:
        """
        Update the maximum concurrent jobs limit.

        Changes take effect immediately:
        - If increased: pending jobs will start on next processor iteration
        - If decreased: running jobs continue, new jobs wait until under limit
        """
        old_value = self.max_concurrent
        if old_value == max_concurrent:
            return

        # Keep thread pool capacity aligned with queue concurrency. Without this,
        # jobs can be marked running while still waiting in the old executor queue.
        old_executor = self._executor
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.max_concurrent = max_concurrent
        logger.info(f"Max concurrent jobs updated: {old_value} -> {max_concurrent}")

        # Let existing work on the old executor drain naturally.
        try:
            old_executor.shutdown(wait=False, cancel_futures=False)
        except TypeError:
            old_executor.shutdown(wait=False)

    def set_root_media(self, root_media: Path) -> None:
        """Update the root_media path (for config reload)."""
        self._root_media = root_media
        logger.info(f"Root media path updated: {root_media}")

    def set_enable_temp_copy(self, enable_temp_copy: bool) -> None:
        """Update the global enable_temp_copy default (for config reload)."""
        self._enable_temp_copy = enable_temp_copy
        logger.info(f"enable_temp_copy updated: {enable_temp_copy}")

    def set_notify_service(self, notify_service: Optional[NotificationService]) -> None:
        """Update the notification service (for config reload)."""
        self._notify_service = notify_service
        logger.info("Notification service updated")

    def clear_profile_cache(self) -> None:
        """Clear the profile cache to force reload from disk on next use."""
        clear_profile_cache()

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

        # DB metadata table — stores app_version for compatibility checking
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS db_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # DB version / compatibility check
        cursor = self._conn.execute("SELECT value FROM db_meta WHERE key = 'app_version'")
        stored_row = cursor.fetchone()
        if stored_row is None:
            # New or pre-0.4.3 DB — proceed to create/migrate, then stamp version
            pass
        elif stored_row["value"] not in DB_COMPATIBLE_VERSIONS:
            stored_v = stored_row["value"]
            raise RuntimeError(
                f"DB was created with app version {stored_v!r}, which is incompatible with "
                f"the current version {APP_VERSION!r}. "
                "Reset the database (delete jobs.db) or wait for a migration in a future version."
            )
        # else: version matches — nothing to do

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
                batch_id TEXT,
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
                warning_message TEXT,
                priority INTEGER DEFAULT 5,
                hardware_accel TEXT,
                backup BOOLEAN DEFAULT 1,
                backup_dir TEXT DEFAULT '.originals',
                output_mode TEXT DEFAULT 'replace',
                delete_source BOOLEAN DEFAULT 0,
                watchfolder_context TEXT,
                source_id TEXT,
                use_temp_folder BOOLEAN DEFAULT 1,
                enable_temp_copy BOOLEAN DEFAULT 0,
                auto_embed_subtitles BOOLEAN DEFAULT 1,
                subtitles_languages TEXT DEFAULT '"all"',
                subtitle_fallback_mode TEXT DEFAULT 'carry'
            )
        """)

        # Migration: add warning_message column if it doesn't exist (v0.3.4)
        try:
            self._conn.execute("SELECT warning_message FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding warning_message column")
            self._conn.execute("ALTER TABLE jobs ADD COLUMN warning_message TEXT")

        # Migration: add subtitle options columns (v0.4.1)
        try:
            self._conn.execute("SELECT auto_embed_subtitles FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding auto_embed_subtitles column")
            self._conn.execute(
                "ALTER TABLE jobs ADD COLUMN auto_embed_subtitles BOOLEAN DEFAULT 1"
            )

        try:
            self._conn.execute("SELECT subtitles_languages FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding subtitles_languages column")
            self._conn.execute(
                "ALTER TABLE jobs ADD COLUMN subtitles_languages TEXT DEFAULT '\"all\"'"
            )

        try:
            self._conn.execute("SELECT subtitle_fallback_mode FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding subtitle_fallback_mode column")
            self._conn.execute(
                "ALTER TABLE jobs ADD COLUMN subtitle_fallback_mode TEXT DEFAULT 'carry'"
            )

        # Migration: rename copy_source_to_temp -> enable_temp_copy (v0.4.2)
        try:
            self._conn.execute("SELECT enable_temp_copy FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            try:
                logger.info("Migrating database: renaming copy_source_to_temp to enable_temp_copy")
                self._conn.execute(
                    "ALTER TABLE jobs RENAME COLUMN copy_source_to_temp TO enable_temp_copy"
                )
            except sqlite3.OperationalError:
                logger.info("Migrating database: adding enable_temp_copy column")
                self._conn.execute(
                    "ALTER TABLE jobs ADD COLUMN enable_temp_copy BOOLEAN DEFAULT 0"
                )

        # Migration: add batch_id column (v0.4.3)
        try:
            self._conn.execute("SELECT batch_id FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding batch_id column")
            self._conn.execute("ALTER TABLE jobs ADD COLUMN batch_id TEXT")

        # Create index for efficient queries
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority DESC, created_at ASC)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id)
        """)

        # Stamp (or update) the app version in db_meta
        self._conn.execute(
            "INSERT OR REPLACE INTO db_meta (key, value) VALUES ('app_version', ?)",
            (APP_VERSION,),
        )

        logger.info(f"Database initialized: {self.db_path} (app version: {APP_VERSION})")

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
        # Resolve effective enable_temp_copy: per-request override → global default
        effective_enable_temp_copy = (
            request.enable_temp_copy
            if request.enable_temp_copy is not None
            else self._enable_temp_copy
        )
        # Guard: replace mode + multi-profile requires temp copy to avoid source corruption.
        # Without a temp copy, the first profile to finish would replace the original source
        # before the other profiles have finished reading it.
        if (
            not effective_enable_temp_copy
            and request.output_mode == OutputMode.REPLACE
            and len(request.profiles) > 1
        ):
            raise ValidationError(
                "enable_temp_copy must be enabled when using replace mode with multiple profiles "
                "(without a temp copy the first profile to complete would overwrite the source "
                "before other profiles finish reading it)"
            )
        # Stamp resolved value back onto request so _submit_files uses it
        request = request.model_copy(update={"enable_temp_copy": effective_enable_temp_copy})

        source_path = Path(request.source)
        # One batch_id per submit() call — groups all resulting jobs for batch-complete detection
        batch_id = str(uuid.uuid4())

        if source_path.is_file():
            # Single file - submit immediately
            return await self._submit_files([source_path], request, batch_id=batch_id)
        elif source_path.is_dir():
            # Folder - use FolderProcessor for continuous monitoring
            return await self._submit_folder(source_path, request, batch_id=batch_id)
        else:
            logger.warning(f"Source path does not exist: {source_path}")
            return []

    async def _submit_folder(
        self, folder_path: Path, request: EncodingRequest, batch_id: str
    ) -> list[str]:
        """
        Submit folder with continuous monitoring using FolderProcessor.

        Files are detected with stability checking, and new files added during
        encoding are also processed.

        Args:
            folder_path: Path to folder
            request: Encoding request
            batch_id: Submission batch ID shared by all jobs from this submit() call

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

        # Store processor, request, and batch_id for monitoring
        self._folder_processors[folder_key] = processor
        self._folder_requests[folder_key] = request
        self._folder_batch_ids[folder_key] = batch_id

        # Initial scan
        processor.scan_folder(folder_key)

        # Submit initially ready files
        job_ids = []
        for file_path in processor.get_ready_files(folder_key):
            ids = await self._submit_files([file_path], request, folder_key=folder_key, batch_id=batch_id)
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
        batch_id = self._folder_batch_ids.get(folder_key)

        if not processor or not request:
            return

        try:
            while not processor.is_folder_complete(folder_key):
                await asyncio.sleep(processor.scan_interval)

                # Re-scan for new files
                processor.scan_folder(folder_key)

                # Submit newly ready files
                for file_path in processor.get_ready_files(folder_key):
                    await self._submit_files(
                        [file_path], request, folder_key=folder_key, batch_id=batch_id
                    )
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
            self._folder_batch_ids.pop(folder_key, None)
            self._folder_monitor_tasks.pop(folder_key, None)

    async def _submit_files(
        self,
        files: list[Path],
        request: EncodingRequest,
        folder_key: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> list[str]:
        """
        Submit a list of files for encoding.

        Args:
            files: List of file paths to encode
            request: Encoding request with profiles and settings
            folder_key: Optional folder key for tracking
            batch_id: Optional submission batch ID for batch-completion detection

        Returns:
            List of created job IDs
        """
        job_ids = []
        # Mark queue as non-empty when new jobs are submitted
        self._queue_was_empty = False

        # Generate source_id for per-source concurrency tracking.
        # For media watchfolders we prefer a stable watchfolder bucket so limits
        # apply across all files from that watchfolder, not per individual file.
        if request.watchfolder_context and request.watchfolder_context.concurrency_bucket:
            source_id = request.watchfolder_context.concurrency_bucket
        elif request.watchfolder_context and request.watchfolder_context.file_hash:
            source_id = request.watchfolder_context.file_hash
        else:
            source_id = str(uuid.uuid4())

        # Register per-source concurrency limit if specified
        if request.max_concurrent_jobs:
            # Ensure limit doesn't exceed global limit
            effective_limit = min(request.max_concurrent_jobs, self.max_concurrent)
            self._source_limits[source_id] = effective_limit
            logger.debug(f"Registered source limit: {source_id} -> {effective_limit}")

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
                    watchfolder_context_json = json.dumps(request.watchfolder_context.model_dump())

                # Insert job into database
                async with self._lock:
                    self._conn.execute("""
                        INSERT INTO jobs (
                            id, status, profile, source_path, output_path,
                            profile_index, total_profiles, parent_job_id, batch_id,
                            created_at, priority, hardware_accel, backup, backup_dir,
                            source_size_bytes, output_mode, delete_source, watchfolder_context,
                            source_id, use_temp_folder, enable_temp_copy,
                            auto_embed_subtitles, subtitles_languages, subtitle_fallback_mode
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job_id,
                        JobStatus.PENDING.value,
                        profile_name,
                        str(file_path),
                        str(output_path) if output_path else None,
                        profile_index,
                        len(request.profiles),
                        parent_job_id,
                        batch_id,
                        datetime.now().isoformat(),
                        request.priority,
                        request.hardware_accel,
                        request.backup if request.output_mode == OutputMode.REPLACE else False,
                        request.backup_dir,
                        file_path.stat().st_size if file_path.exists() else 0,
                        request.output_mode.value,
                        request.delete_source,
                        watchfolder_context_json,
                        source_id,
                        request.use_temp_folder,
                        request.enable_temp_copy,
                        request.auto_embed_subtitles,
                        json.dumps(request.subtitles_languages),
                        request.subtitle_fallback_mode,
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
        import os

        container = None
        profile = None
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
            separator=self._profile_name_separator,
        )

        if request.output_mode == OutputMode.REPLACE:
            # Replace in-place (output goes to temp, then replaces original)
            return source_file.parent / output_filename
        else:
            # Output to destination
            if request.use_profile_destination:
                # Use profile's destination field (absolute path)
                if not profile or not profile.destination:
                    raise ValueError(f"Profile '{profile_name}' has no destination field")
                # Expand path placeholders ($root_media, ~, etc.)
                dest_str = profile.destination
                if self._root_media and "$root_media" in dest_str:
                    root_str = str(self._root_media).rstrip("/")
                    dest_str = dest_str.replace("$root_media", root_str)
                dest_base = Path(os.path.expandvars(os.path.expanduser(dest_str)))
                # Validate destination directory exists
                if not dest_base.exists():
                    raise ValueError(f"Profile '{profile_name}' destination does not exist: {dest_base}")
                if not dest_base.is_dir():
                    raise ValueError(f"Profile '{profile_name}' destination is not a directory: {dest_base}")
            elif request.destination:
                dest_base = Path(request.destination)
            else:
                return None

            # Preserve folder structure if requested
            if request.preserve_structure:
                try:
                    relative = source_file.parent.relative_to(Path(request.source))
                    dest_base = dest_base / relative
                except ValueError:
                    pass

            # Create profile subfolder if requested (mutually exclusive with use_profile_destination)
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
        """Get the next pending job by priority, respecting per-source limits."""
        async with self._lock:
            # Get all pending jobs ordered by priority
            cursor = self._conn.execute("""
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY priority DESC, created_at ASC
            """, (JobStatus.PENDING.value,))

            for row in cursor.fetchall():
                job = dict(row)
                source_id = job.get("source_id")

                # Check per-source limit
                if source_id and source_id in self._source_limits:
                    current_running = self._source_running_counts.get(source_id, 0)
                    if current_running >= self._source_limits[source_id]:
                        # Source at its limit, skip to next job
                        continue

                # This job can run
                return job

            return None

    async def _execute_job(self, job_id: str):
        """Execute a single job."""
        source_id = None  # Track for cleanup in finally
        try:
            # Update status to running
            await self._update_job_status(job_id, JobStatus.RUNNING)

            # Get job details from database (includes multi-profile context)
            async with self._lock:
                cursor = self._conn.execute(
                    """SELECT id, profile, source_path, output_path, hardware_accel,
                              profile_index, total_profiles, parent_job_id, output_mode,
                              delete_source, watchfolder_context, source_id, use_temp_folder,
                              enable_temp_copy, auto_embed_subtitles, subtitles_languages,
                              subtitle_fallback_mode
                       FROM jobs WHERE id = ?""",
                    (job_id,)
                )
                row = cursor.fetchone()

            if not row:
                logger.error(f"Job not found: {job_id}")
                return

            # Track per-source running count
            source_id = row["source_id"]
            if source_id:
                self._source_running_counts[source_id] = self._source_running_counts.get(source_id, 0) + 1

            hardware_accel = row["hardware_accel"]
            profile_index = row["profile_index"] or 0
            total_profiles = row["total_profiles"] or 1
            parent_job_id = row["parent_job_id"]
            output_path = Path(row["output_path"]) if row["output_path"] else None
            output_mode_str = row["output_mode"] or "replace"
            output_mode = OutputMode(output_mode_str)
            delete_source = bool(row["delete_source"]) if row["delete_source"] is not None else False
            use_temp_folder = bool(row["use_temp_folder"]) if row["use_temp_folder"] is not None else True
            enable_temp_copy = bool(row["enable_temp_copy"]) if row["enable_temp_copy"] is not None else False
            auto_embed_subtitles = bool(row["auto_embed_subtitles"]) if row["auto_embed_subtitles"] is not None else True
            subtitle_fallback_mode = str(row["subtitle_fallback_mode"] or "carry").lower()
            if subtitle_fallback_mode not in {"carry", "skip", "fail"}:
                subtitle_fallback_mode = "carry"

            subtitles_languages = None
            if row["subtitles_languages"]:
                try:
                    parsed_languages = json.loads(row["subtitles_languages"])
                    if isinstance(parsed_languages, list):
                        subtitles_languages = [str(lang) for lang in parsed_languages]
                except Exception:
                    subtitles_languages = None

            # Deserialize watchfolder_context if present
            watchfolder_context = None
            if row["watchfolder_context"]:
                ctx_data = json.loads(row["watchfolder_context"])
                watchfolder_context = WatchfolderContext(**ctx_data)

            # Create Job object for runner
            job = Job(
                source_path=Path(row["source_path"]),
                profile_name=row["profile"],
                hardware_accel=hardware_accel,
                output_mode=output_mode,
                delete_source=delete_source,
                use_temp_folder=use_temp_folder,
                enable_temp_copy=enable_temp_copy,
                auto_embed_subtitles=auto_embed_subtitles,
                subtitles_languages=subtitles_languages,
                subtitle_fallback_mode=subtitle_fallback_mode,
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

        except asyncio.CancelledError:
            # Job was cancelled - check if it was already marked as cancelled
            # (by cancel_job()) or if this is a daemon shutdown
            async with self._lock:
                cursor = self._conn.execute(
                    "SELECT status FROM jobs WHERE id = ?", (job_id,)
                )
                row = cursor.fetchone()
                current_status = row["status"] if row else None

            if current_status == JobStatus.CANCELLED.value:
                logger.info(f"Job {job_id} was cancelled by user")
            else:
                # Daemon shutdown - mark as interrupted for auto-retry
                logger.info(f"Job {job_id} interrupted by shutdown")
                await self._update_job_status(job_id, JobStatus.INTERRUPTED)
            raise  # Re-raise to propagate cancellation

        except ValidationError as e:
            # Validation failures are expected conditions — log cleanly without traceback
            logger.warning(f"Job {job_id} validation failed: {e}")
            await self._update_job_failed(job_id, str(e))

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            await self._update_job_failed(job_id, str(e))

        finally:
            # Remove from active jobs
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]

            # Clean up cancelled job tracking
            self._cancelled_job_ids.discard(job_id)

            # Decrement per-source running count
            if source_id and source_id in self._source_running_counts:
                self._source_running_counts[source_id] -= 1
                if self._source_running_counts[source_id] <= 0:
                    # Clean up tracking for this source
                    del self._source_running_counts[source_id]
                    self._source_limits.pop(source_id, None)

    def _sync_update_progress(self, job_id: str, job: Job):
        """Synchronously update job progress (called from thread)."""
        try:
            with self._db_lock:
                self._conn.execute("""
                    UPDATE jobs SET
                        progress = ?,
                        fps = ?,
                        frames_processed = ?,
                        frames_total = ?,
                        hardware_accel = ?
                    WHERE id = ?
                """, (
                    job.progress_percent,
                    job.current_fps,
                    job.frames_processed,
                    job.frames_total,
                    job.hardware_accel,
                    job_id,
                ))
            self._set_runtime_eta(job_id, job.eta_seconds, job.eta_quality)
        except Exception as e:
            logger.warning(f"Failed to update progress for {job_id}: {e}")

    def _set_runtime_eta(
        self,
        job_id: str,
        eta_seconds: Optional[int],
        eta_quality: Optional[str],
    ) -> None:
        """Store latest in-memory ETA snapshot for a running job."""
        with self._runtime_eta_lock:
            if eta_seconds is None and eta_quality is None:
                self._runtime_eta.pop(job_id, None)
                return
            self._runtime_eta[job_id] = {
                "eta_seconds": eta_seconds,
                "eta_quality": eta_quality,
            }

    def _get_runtime_eta(self, job_id: str) -> tuple[Optional[int], Optional[str]]:
        """Get in-memory ETA snapshot for a job."""
        with self._runtime_eta_lock:
            eta = self._runtime_eta.get(job_id)
            if not eta:
                return None, None
            eta_seconds = eta.get("eta_seconds")
            eta_quality = eta.get("eta_quality")
            return (
                eta_seconds if isinstance(eta_seconds, int) else None,
                eta_quality if isinstance(eta_quality, str) else None,
            )

    def _clear_runtime_eta(self, job_id: str) -> None:
        """Clear in-memory ETA snapshot for a job."""
        with self._runtime_eta_lock:
            self._runtime_eta.pop(job_id, None)

    async def _update_job_status(self, job_id: str, status: JobStatus):
        """Update job status."""
        async with self._lock:
            now = datetime.now().isoformat()
            if status == JobStatus.RUNNING:
                self._clear_runtime_eta(job_id)
                self._conn.execute("""
                    UPDATE jobs SET status = ?, started_at = ? WHERE id = ?
                """, (status.value, now, job_id))
            else:
                self._clear_runtime_eta(job_id)
                self._conn.execute("""
                    UPDATE jobs SET status = ? WHERE id = ?
                """, (status.value, job_id))

    async def _update_job_completed(self, job_id: str, job: Job):
        """Update job as completed (or warning if warnings present)."""
        status = JobStatus.WARNING if job.warning_message else JobStatus.COMPLETED
        self._clear_runtime_eta(job_id)
        batch_id: Optional[str] = None
        async with self._lock:
            # Fetch batch_id before updating (same lock)
            cur = self._conn.execute("SELECT batch_id FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                batch_id = row["batch_id"]
            self._conn.execute("""
                UPDATE jobs SET
                    status = ?,
                    completed_at = ?,
                    progress = 100.0,
                    output_size_bytes = ?,
                    output_path = ?,
                    hardware_accel = ?,
                    warning_message = ?
                WHERE id = ?
            """, (
                status.value,
                datetime.now().isoformat(),
                job.output_size_bytes,
                str(job.output_path) if job.output_path else None,
                job.hardware_accel,
                job.warning_message,
                job_id,
            ))
            if job.warning_message:
                logger.warning(f"Job completed with warnings: {job_id}")
            else:
                logger.info(f"Job completed: {job_id}")

        # Notify folder processor if job belongs to a folder
        self._notify_folder_job_complete(job_id, success=True)

        # Fire notifications asynchronously
        if self._notify_service:
            asyncio.create_task(self._post_job_done(
                job_id, status, batch_id,
                source=str(job.source_path),
                profile=job.profile_name,
                source_size_bytes=job.source_size_bytes,
                output_size_bytes=job.output_size_bytes,
                error_message=None,
            ))

    async def _update_job_failed(self, job_id: str, error: str):
        """Update job as failed."""
        self._clear_runtime_eta(job_id)
        batch_id: Optional[str] = None
        async with self._lock:
            # Fetch batch_id and job details before updating
            cur = self._conn.execute(
                "SELECT batch_id, profile, source_path, source_size_bytes FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = cur.fetchone()
            if row:
                batch_id = row["batch_id"]
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

        # Fire notifications asynchronously
        if self._notify_service and row:
            asyncio.create_task(self._post_job_done(
                job_id, JobStatus.FAILED, batch_id,
                source=row["source_path"],
                profile=row["profile"],
                source_size_bytes=row["source_size_bytes"],
                output_size_bytes=None,
                error_message=error,
            ))

    def _notify_folder_job_complete(self, job_id: str, success: bool):
        """Notify folder processor that a job has completed."""
        folder_key = self._job_to_folder.pop(job_id, None)
        if folder_key:
            processor = self._folder_processors.get(folder_key)
            if processor:
                processor.mark_job_completed(folder_key, success=success)

    async def _post_job_done(
        self,
        job_id: str,
        status: JobStatus,
        batch_id: Optional[str],
        source: str,
        profile: str,
        source_size_bytes: Optional[int],
        output_size_bytes: Optional[int],
        error_message: Optional[str],
    ) -> None:
        """Dispatch notifications after a job reaches a terminal state."""
        if not self._notify_service:
            return

        # Per-job notification
        await self._notify_service.notify_job_complete(
            job_id=job_id,
            profile=profile,
            source=source,
            status=status.value,
            source_size_bytes=source_size_bytes,
            output_size_bytes=output_size_bytes,
            error_message=error_message,
        )

        # Batch completion check
        if batch_id:
            async with self._lock:
                cur = self._conn.execute(
                    "SELECT COUNT(*) as remaining FROM jobs "
                    "WHERE batch_id = ? AND status IN (?, ?, ?)",
                    (batch_id, JobStatus.PENDING.value, JobStatus.QUEUED.value, JobStatus.RUNNING.value),
                )
                remaining = cur.fetchone()["remaining"]
                if remaining == 0:
                    cur2 = self._conn.execute(
                        "SELECT COUNT(*) as total, "
                        "SUM(CASE WHEN status IN (?, ?) THEN 1 ELSE 0 END) as completed, "
                        "SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failed "
                        "FROM jobs WHERE batch_id = ?",
                        (
                            JobStatus.COMPLETED.value, JobStatus.WARNING.value,
                            JobStatus.FAILED.value,
                            batch_id,
                        ),
                    )
                    stats = cur2.fetchone()
            if remaining == 0:
                await self._notify_service.notify_batch_complete(
                    batch_id=batch_id,
                    total=stats["total"] or 0,
                    completed=stats["completed"] or 0,
                    failed=stats["failed"] or 0,
                )

        # Queue empty check (transition False → True)
        async with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) as count FROM jobs WHERE status IN (?, ?, ?)",
                (JobStatus.PENDING.value, JobStatus.QUEUED.value, JobStatus.RUNNING.value),
            )
            active_count = cur.fetchone()["count"]
        is_empty = active_count == 0
        if is_empty and not self._queue_was_empty:
            self._queue_was_empty = True
            await self._notify_service.notify_queue_empty()
        elif not is_empty:
            self._queue_was_empty = False

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

        # Track that this job was explicitly cancelled (not daemon shutdown)
        self._cancelled_job_ids.add(job_id)

        # Tell the job runner this job was cancelled (for proper cleanup handling)
        self._job_runner.mark_job_cancelled(job_id)

        # For running jobs, we need to terminate FFmpeg and signal cancellation
        if job.status == JobStatus.RUNNING and job_id in self._active_jobs:
            # Mark as cancelled in DB first (before terminating FFmpeg)
            await self._update_job_status(job_id, JobStatus.CANCELLED)

            # Terminate FFmpeg process gracefully
            self._job_runner.ffmpeg.terminate()

            # Cancel the asyncio task
            self._active_jobs[job_id].cancel()
        else:
            # Pending job - just update status
            await self._update_job_status(job_id, JobStatus.CANCELLED)

        return True

    async def retry_job(self, job_id: str) -> Optional[JobInfo]:
        """Retry a failed job."""
        job = await self.get_job(job_id)
        if not job or job.status != JobStatus.FAILED:
            return None

        async with self._lock:
            # Watchfolder failures rename the source file to ".failed".
            # On retry, restore original filename so JobRunner can find input.
            cursor = self._conn.execute(
                "SELECT source_path, watchfolder_context FROM jobs WHERE id = ?",
                (job_id,),
            )
            row = cursor.fetchone()
            if row:
                source_path = Path(row["source_path"])
                watchfolder_context = row["watchfolder_context"]

                if watchfolder_context and not source_path.exists():
                    failed_path = source_path.with_suffix(source_path.suffix + ".failed")
                    if failed_path.exists():
                        failed_path.rename(source_path)
                        logger.info(
                            f"Restored failed source for retry: {failed_path.name} -> {source_path.name}"
                        )

            self._conn.execute("""
                UPDATE jobs SET
                    status = ?,
                    error_message = NULL,
                    progress = 0.0,
                    started_at = NULL,
                    completed_at = NULL
                WHERE id = ?
            """, (JobStatus.PENDING.value, job_id))
            self._clear_runtime_eta(job_id)

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

    async def clear_warning(self) -> int:
        """Clear warning jobs (completed with warnings)."""
        async with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM jobs WHERE status = ?",
                (JobStatus.WARNING.value,)
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
        # Get encoding settings from profile
        profile_name = row["profile"]
        video_codec = None
        audio_codec = None
        subtitle_mode = None
        container = None

        try:
            profile = self._profile_manager.load_profile(profile_name)
            if profile:
                container = profile.container
                if profile.video:
                    video_codec = profile.video.codec
                if profile.audio:
                    audio_codec = profile.audio.codec if profile.audio.codec else "copy"
                else:
                    audio_codec = "copy"
                if profile.subtitles:
                    subtitle_mode = "include_all" if profile.subtitles.include_all else "none"
                else:
                    subtitle_mode = "include_all"  # default
        except Exception:
            pass  # Profile lookup failed, leave fields as None

        # Check if temp folder is enabled (from DB column, fallback to watchfolder_context)
        use_temp_folder = bool(row["use_temp_folder"]) if row["use_temp_folder"] is not None else True
        if use_temp_folder and row["watchfolder_context"]:
            try:
                ctx_data = json.loads(row["watchfolder_context"])
                use_temp_folder = ctx_data.get("enable_temp_copy", False)
            except Exception:
                pass

        eta_seconds, eta_quality = self._get_runtime_eta(row["id"])

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
            eta_seconds=eta_seconds,
            eta_quality=eta_quality,
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            source_size_bytes=row["source_size_bytes"] or 0,
            output_size_bytes=row["output_size_bytes"] or 0,
            error_message=row["error_message"],
            warning_message=row["warning_message"],
            # Encoding settings
            hardware_accel=row["hardware_accel"],
            video_codec=video_codec,
            audio_codec=audio_codec,
            subtitle_mode=subtitle_mode,
            container=container,
            use_temp_folder=use_temp_folder,
        )

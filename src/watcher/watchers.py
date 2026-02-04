"""Watch folder classes for monitoring directories and auto-processing files."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .folder_processor import FolderProcessor, PendingFile, is_file_ready
from .inotify_watcher import InotifyWatcher, is_local_filesystem, INOTIFY_AVAILABLE
from ..api.models import EncodingRequest, OutputMode, WatchfolderContext, process_encoding_request
from ..core.hash import compute_file_fingerprint

if TYPE_CHECKING:
    from ..api.queue import JobQueue

logger = logging.getLogger(__name__)


class CommandFileWatcher:
    """
    Watches a directory for YAML command files.

    When a .yaml file is dropped in the watched directory, it's parsed
    as an EncodingRequest and submitted to the queue.
    """

    def __init__(
        self,
        watch_path: Path,
        job_queue: "JobQueue",
        scan_interval: float = 5.0,
        root_media: Optional[Path] = None,
    ):
        """
        Initialize command file watcher.

        Args:
            watch_path: Directory to watch for command files
            job_queue: Job queue to submit jobs to
            scan_interval: How often to scan (seconds)
            root_media: Base path for $root_media placeholder expansion
        """
        self.watch_path = watch_path
        self.job_queue = job_queue
        self.scan_interval = scan_interval
        self.root_media = root_media or Path.home() / "Videos"

        self._running = False
        self._paused = False
        self._scan_task: Optional[asyncio.Task] = None
        self._processed_files: set[str] = set()

    async def start(self):
        """Start watching for command files."""
        # Validate watch directory exists - don't create it
        if not self.watch_path.exists():
            logger.error(f"Command file watcher: directory does not exist: {self.watch_path}")
            return

        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info(f"Command file watcher started: {self.watch_path}")

    async def stop(self):
        """Stop watching."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        logger.info("Command file watcher stopped")

    async def _scan_loop(self):
        """Scan for new command files."""
        import yaml

        while self._running:
            try:
                # Skip if paused
                if self._paused:
                    await asyncio.sleep(self.scan_interval)
                    continue

                for yaml_file in self.watch_path.glob("*.yaml"):
                    if str(yaml_file) in self._processed_files:
                        continue

                    # Check if file is complete (not being written)
                    try:
                        mtime = yaml_file.stat().st_mtime
                        if time.time() - mtime < 2:  # Wait 2 seconds
                            continue
                    except OSError:
                        continue

                    # Parse command file
                    try:
                        with open(yaml_file) as f:
                            data = yaml.safe_load(f)

                        request = EncodingRequest(**data)

                        # Process request (expand $root_media, validate)
                        request, issues = process_encoding_request(request, self.root_media)
                        if issues:
                            logger.error(
                                f"Invalid command file {yaml_file.name}: {'; '.join(issues)}"
                            )
                            self._move_to_failed(yaml_file, issues)
                            continue

                        # Submit encoding job(s)
                        job_ids = await self.job_queue.submit(request)
                        logger.info(
                            f"Submitted {len(job_ids)} job(s) from: {yaml_file.name}"
                        )

                        # Move to processed
                        self._move_to_processed(yaml_file)

                    except Exception as e:
                        logger.error(f"Error processing command file {yaml_file.name}: {e}")
                        self._move_to_failed(yaml_file, [str(e)])

                    self._processed_files.add(str(yaml_file))

            except Exception as e:
                logger.error(f"Error scanning command files: {e}", exc_info=True)

            await asyncio.sleep(self.scan_interval)

    def _move_to_processed(self, yaml_file: Path):
        """Move processed command file to 'processed' subdirectory."""
        processed_dir = self.watch_path / "processed"
        processed_dir.mkdir(exist_ok=True)

        dest = processed_dir / f"{yaml_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        yaml_file.rename(dest)

    def _move_to_failed(self, yaml_file: Path, errors: list[str]):
        """Move failed command file to 'failed' subdirectory."""
        failed_dir = self.watch_path / "failed"
        failed_dir.mkdir(exist_ok=True)

        dest = failed_dir / f"{yaml_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        yaml_file.rename(dest)

        # Write error file
        error_file = failed_dir / f"{yaml_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.errors"
        error_file.write_text("\n".join(errors))


@dataclass
class SubmittedJob:
    """Tracks a submitted job for a source file."""
    original_path: Path          # Original file path (before renaming)
    processing_path: Path        # Path while processing (.processing suffix)
    temp_source: Optional[Path]  # Temp copy of source (if temp copy enabled)
    job_ids: list[str]
    submitted_at: float
    folder_key: Optional[str] = None  # Track which folder this file belongs to


class MediaFileWatcher:
    """
    Watches a directory for media files (video/audio).

    Uses file size stability detection: a file is ready when its size
    hasn't changed for a configurable number of consecutive scans.
    Encoding settings come from the watchfolder configuration.

    Source files are only renamed/deleted AFTER all jobs complete successfully.
    """

    def __init__(self, config, job_queue: "JobQueue"):
        """
        Initialize media file watcher.

        Args:
            config: WatchfolderConfig with encoding settings
            job_queue: Job queue to submit jobs to
        """
        self.config = config
        self.job_queue = job_queue
        self.watch_path = config.watchfolder_location

        self._running = False
        self._paused = False
        self._scan_task: Optional[asyncio.Task] = None
        self._pending_files: dict[str, PendingFile] = {}
        self._submitted_jobs: dict[str, SubmittedJob] = {}  # path -> submitted job info
        self._failed_files: set[str] = set()  # Files that failed validation (won't retry)

        # Folder processor for dropped folders
        self._folder_processor = FolderProcessor(
            file_patterns=config.file_patterns,
            stability_scans=config.stability_scans,
            scan_interval=config.scan_interval,
            recursive=True,  # Always recursive for dropped folders
        )
        self._active_folder_keys: set[str] = set()  # Currently processing folders

        # Inotify watcher for local filesystems (instant CLOSE_WRITE detection)
        self._inotify_watcher: Optional[InotifyWatcher] = None
        self._inotify_ready_files: set[str] = set()  # Files marked ready by inotify
        self._use_inotify = False  # Whether inotify is active for this watcher

    async def start(self):
        """Start watching for media files."""
        # Validate watch directory exists - don't create it
        if not self.watch_path.exists():
            logger.error(f"Media file watcher: directory does not exist: {self.watch_path}")
            return

        # Try to use inotify for instant file-ready detection on local filesystems
        if INOTIFY_AVAILABLE and is_local_filesystem(self.watch_path):
            try:
                self._inotify_watcher = InotifyWatcher(
                    watch_path=self.watch_path,
                    callback=self._on_inotify_close,
                    file_patterns=self.config.file_patterns,
                )
                if self._inotify_watcher.start():
                    self._use_inotify = True
                    logger.info(f"Media watcher using inotify for {self.watch_path} (local filesystem)")
                else:
                    logger.warning(f"Failed to start inotify, using polling for {self.watch_path}")
            except Exception as e:
                logger.warning(f"Inotify init failed, using polling: {e}")
        else:
            reason = "NFS/remote" if INOTIFY_AVAILABLE else "inotify unavailable"
            logger.info(f"Media watcher using polling for {self.watch_path} ({reason})")

        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info(
            f"Media file watcher started: {self.watch_path} "
            f"(profiles: {self.config.profiles}, stability: {self.config.stability_scans} scans)"
        )

    async def stop(self):
        """Stop watching."""
        self._running = False

        # Stop inotify watcher
        if self._inotify_watcher:
            self._inotify_watcher.stop()
            self._inotify_watcher = None
            self._use_inotify = False

        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Media file watcher stopped: {self.watch_path}")

    def _matches_pattern(self, filename: str) -> bool:
        """Check if filename matches any of the file patterns."""
        return any(
            fnmatch(filename.lower(), pattern.lower())
            for pattern in self.config.file_patterns
        )

    def _on_inotify_close(self, file_path: Path):
        """
        Callback when inotify detects CLOSE_WRITE (file copy complete).

        Called from inotify thread, adds file to ready set for next scan.
        """
        path_str = str(file_path)
        self._inotify_ready_files.add(path_str)
        logger.debug(f"Media watcher: inotify marked ready: {file_path.name}")

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        Check if file is ready for processing.

        Detection method depends on filesystem:
        - Local filesystem: Uses inotify IN_CLOSE_WRITE (instant detection)
        - NFS/remote: Uses size+mtime stability polling (fallback)
        """
        path_str = str(file_path)

        # Skip files that already have submitted jobs
        if path_str in self._submitted_jobs:
            return False

        # Skip files that failed validation (won't retry until daemon restart)
        if path_str in self._failed_files:
            return False

        # Skip files that have already been processed (.processed companion exists)
        processed_path = file_path.with_suffix(file_path.suffix + ".processed")
        if processed_path.exists():
            return False

        # Skip files currently being processed (.processing companion exists)
        processing_path = file_path.with_suffix(file_path.suffix + ".processing")
        if processing_path.exists():
            return False

        # Check if inotify marked this file as ready (CLOSE_WRITE received)
        if path_str in self._inotify_ready_files:
            self._inotify_ready_files.discard(path_str)
            self._pending_files.pop(path_str, None)  # Cleanup tracking
            logger.info(f"Media watcher: file ready (inotify): {file_path.name}")
            return True

        # First time seeing this file?
        if path_str not in self._pending_files:
            try:
                stat_info = file_path.stat()
            except (OSError, FileNotFoundError):
                return False
            self._pending_files[path_str] = PendingFile(
                first_seen=time.time(),
                last_size=stat_info.st_size,
                last_mtime=stat_info.st_mtime,
                stable_count=0
            )
            if self._use_inotify:
                logger.debug(f"Media watcher: tracking {file_path.name}, waiting for inotify CLOSE_WRITE")
            else:
                logger.debug(f"Media watcher: new file detected: {file_path.name} ({stat_info.st_size} bytes)")
            return False

        # If using inotify, don't poll for readiness - wait for CLOSE_WRITE event
        if self._use_inotify:
            return False

        # Fallback: polling-based stability check (for NFS/remote filesystems)
        pending = self._pending_files[path_str]
        result = is_file_ready(file_path, pending, self.config.stability_scans)

        # Cleanup if file disappeared
        if not file_path.exists():
            self._pending_files.pop(path_str, None)

        return result

    async def _scan_loop(self):
        """Scan for new media files and check completed jobs."""
        while self._running:
            try:
                # Skip processing if paused, but still check completed jobs
                if not self._paused:
                    await self._process_ready_files()
                await self._check_completed_jobs()
            except Exception as e:
                logger.error(f"Error in media watcher scan loop: {e}", exc_info=True)

            await asyncio.sleep(self.config.scan_interval)

    async def _process_ready_files(self):
        """Find and submit ready files for encoding."""
        if not self.watch_path.exists():
            return

        # First pass: check items for folders (if enabled) and files
        # Use recursive glob if recursive mode is enabled
        if self.config.recursive:
            scan_iter = self.watch_path.rglob("*")
        else:
            scan_iter = self.watch_path.iterdir()

        for item_path in scan_iter:
            # Skip items with processing markers
            if any(item_path.name.endswith(suffix) for suffix in [".processing", ".processed", ".failed"]):
                continue

            # Folder handling (only if allow_folder_drop is enabled and at top level)
            if item_path.is_dir() and self.config.allow_folder_drop:
                # Only process folders at top level of watchfolder
                if item_path.parent == self.watch_path:
                    if not self._folder_processor.is_registered(item_path):
                        folder_key = self._folder_processor.register_folder(item_path)
                        self._active_folder_keys.add(folder_key)
            elif item_path.is_file():
                # File in watch folder - use existing logic
                if self._matches_pattern(item_path.name):
                    if self._is_file_ready(item_path):
                        await self._submit_job(item_path)

        # Second pass: process registered folders (only if allow_folder_drop is enabled)
        if self.config.allow_folder_drop:
            for folder_key in list(self._active_folder_keys):
                await self._process_folder(folder_key)

    async def _process_folder(self, folder_key: str):
        """Process a folder registered with FolderProcessor."""
        # Scan for new files
        self._folder_processor.scan_folder(folder_key)

        # Submit ready files
        for file_path in self._folder_processor.get_ready_files(folder_key):
            await self._submit_folder_file(folder_key, file_path)

        # Check if folder is complete
        if self._folder_processor.is_folder_complete(folder_key):
            await self._complete_folder(folder_key)

    async def _submit_folder_file(self, folder_key: str, file_path: Path):
        """Submit a file from a folder for encoding."""
        # Mark as submitted in folder processor before actual submission
        self._folder_processor.mark_file_submitted(folder_key, file_path)

        # Use existing submit logic with folder_key tracking
        await self._submit_job(file_path, folder_key=folder_key)

    async def _complete_folder(self, folder_key: str):
        """Handle completed folder - rename to .processed or delete based on config."""
        folder_path = self._folder_processor.complete_folder(folder_key)
        self._active_folder_keys.discard(folder_key)

        if folder_path and folder_path.exists():
            try:
                if self.config.keep_processed_files:
                    # Rename folder to .processed
                    processed_path = folder_path.with_name(folder_path.name + ".processed")
                    folder_path.rename(processed_path)
                    logger.info(f"Media watcher: folder complete: {folder_path.name} -> {processed_path.name}")
                else:
                    # Delete entire folder tree
                    import shutil
                    shutil.rmtree(folder_path)
                    logger.info(f"Media watcher: folder deleted: {folder_path.name}")
            except Exception as e:
                logger.warning(f"Media watcher: failed to handle folder {folder_path.name}: {e}")

    def _get_temp_folder(self) -> Path:
        """Get temp folder for source copy and encoding workspace."""
        import tempfile
        if self.config.temp_folder:
            temp_folder = self.config.temp_folder
        else:
            temp_folder = Path(tempfile.gettempdir()) / "videotranscode"
        temp_folder.mkdir(parents=True, exist_ok=True)
        return temp_folder

    async def _submit_job(self, file_path: Path, folder_key: Optional[str] = None):
        """
        Submit encoding job for a ready file.

        Watcher only detects and submits - all file operations (temp copy,
        .processing rename) are handled by JobRunner via WatchfolderContext.

        Args:
            file_path: Path to the file to encode
            folder_key: Optional folder key if this file belongs to a dropped folder
        """
        path_str = str(file_path)

        # Determine destination - either use profile destinations or a fixed folder
        use_profile_dest = self.config.use_profile_destination
        destination_str = None  # Will be set if not using profile destinations
        if not use_profile_dest:
            # Use the configured destination folder
            destination = self.config.destination

            # Calculate destination path for folder drops with preserve_folder_structure
            if folder_key and self.config.preserve_folder_structure:
                # folder_key is the dropped folder path (e.g., /wf-media/test1)
                # file_path is the file inside (e.g., /wf-media/test1/01/video.mkv)
                # We want to preserve: test1/01/ relative to destination
                folder_path = Path(folder_key)
                try:
                    # Get path relative to the dropped folder (e.g., 01/video.mkv)
                    relative_from_folder = file_path.relative_to(folder_path)
                    # Get the subdirectory part (e.g., 01)
                    relative_subdir = relative_from_folder.parent
                    # Final destination includes folder name and subdir
                    destination = destination / folder_path.name / relative_subdir
                except ValueError:
                    # file_path is not inside folder_key - shouldn't happen, but fallback
                    logger.warning(f"Media watcher: {file_path} not inside folder {folder_path}")

            destination_str = str(destination)

        # Compute file fingerprint for tracking
        try:
            file_hash = compute_file_fingerprint(file_path)
        except Exception as e:
            logger.error(f"Media watcher: failed to compute hash for {file_path.name}: {e}")
            self._pending_files.pop(path_str, None)
            self._failed_files.add(path_str)
            return

        # Build request with watchfolder context
        # JobRunner handles: temp copy (optional), final rename to .processed/.failed or delete
        request = EncodingRequest(
            profiles=self.config.profiles,
            source=str(file_path),
            output_mode="destination",
            destination=destination_str,
            use_profile_destination=use_profile_dest,
            preserve_structure=self.config.preserve_folder_structure,
            backup=False,
            hardware_accel=self.config.hardware_accel,
            priority=self.config.priority,
            append_profile_name=self.config.append_profile_name,
            max_concurrent_jobs=self.config.max_concurrent_jobs,
            watchfolder_context=WatchfolderContext(
                file_hash=file_hash,
                keep_processed_files=self.config.keep_processed_files,
                disable_temp_copy=self.config.disable_temp_copy,
                temp_folder=str(self.config.temp_folder) if self.config.temp_folder else None,
            ),
        )

        # Validate request
        issues = request.validate_request()
        if issues:
            logger.error(f"Media watcher: invalid request for {file_path.name}: {'; '.join(issues)}")
            self._pending_files.pop(path_str, None)
            self._failed_files.add(path_str)
            return

        # Submit job(s)
        job_ids = await self.job_queue.submit(request)

        if job_ids:
            # Track submitted file (prevents re-detection until job completes)
            # File operations are now handled by JobRunner
            self._submitted_jobs[path_str] = SubmittedJob(
                original_path=file_path,
                processing_path=file_path.with_suffix(file_path.suffix + ".processing"),
                temp_source=None,  # JobRunner handles temp copy now
                job_ids=job_ids,
                submitted_at=time.time(),
                folder_key=folder_key,
            )
            self._pending_files.pop(path_str, None)
            folder_info = f" (folder: {Path(folder_key).name})" if folder_key else ""
            logger.info(f"Media watcher: submitted {len(job_ids)} job(s) for {file_path.name}{folder_info}")
        else:
            # Job submission failed
            logger.error(f"Media watcher: failed to submit jobs for {file_path.name}")
            self._pending_files.pop(path_str, None)
            self._failed_files.add(path_str)

    async def _check_completed_jobs(self):
        """Check submitted jobs and handle source files when all jobs complete."""
        from ..api.models import JobStatus

        completed_paths = []

        for path_str, submitted in list(self._submitted_jobs.items()):
            all_done = True
            any_failed = False

            for job_id in submitted.job_ids:
                job = await self.job_queue.get_job(job_id)
                if not job:
                    # Job not found - treat as failed
                    any_failed = True
                    continue

                if job.status == JobStatus.COMPLETED:
                    continue
                elif job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                    any_failed = True
                else:
                    # Job still pending/running/queued
                    all_done = False
                    break

            if all_done:
                completed_paths.append(path_str)
                # Handle source file based on outcome
                self._handle_completed_job(submitted, failed=any_failed)

                # Update folder processor if this file belonged to a folder
                if submitted.folder_key:
                    self._folder_processor.mark_job_completed(
                        submitted.folder_key,
                        success=not any_failed
                    )

        # Remove completed entries
        for path_str in completed_paths:
            del self._submitted_jobs[path_str]

    def _handle_completed_job(self, submitted: SubmittedJob, failed: bool = False):
        """
        Handle completed job - just cleanup internal tracking and log.

        File operations (.processing rename, temp cleanup) are handled by JobRunner
        via WatchfolderContext.

        Args:
            submitted: SubmittedJob with file paths
            failed: True if any job failed/cancelled
        """
        original_name = submitted.original_path.name
        if failed:
            logger.warning(f"Media watcher: job(s) failed for {original_name}")
        else:
            logger.info(f"Media watcher: job(s) completed for {original_name}")

"""Watch folder manager for monitoring directories and auto-processing files."""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

from .models import EncodingRequest, OutputMode, WatchFolderInfo
from .queue import JobQueue

logger = logging.getLogger(__name__)


@dataclass
class PendingFile:
    """Tracks a pending file for size stability detection."""
    first_seen: float
    last_size: int
    stable_count: int = 0


class WatchFolder:
    """Represents a single watch folder."""

    def __init__(self, request: EncodingRequest):
        self.id = str(uuid.uuid4())
        self.path = Path(request.source)
        self.profiles = request.profiles
        self.output_mode = request.output_mode
        self.destination = request.destination
        self.preserve_structure = request.preserve_structure
        self.recursive = request.recursive
        self.file_patterns = request.file_patterns
        self.min_age_seconds = request.min_age_seconds
        self.hardware_accel = request.hardware_accel
        self.priority = request.priority
        self.backup = request.backup
        self.backup_dir = request.backup_dir

        # State
        self.active = True
        self.files_processed = 0
        self.last_activity: Optional[datetime] = None

        # Track processed files (to avoid re-processing)
        self._processed_files: set[str] = set()
        self._pending_files: dict[str, float] = {}  # path -> first_seen_time

    def to_info(self) -> WatchFolderInfo:
        """Convert to WatchFolderInfo model."""
        return WatchFolderInfo(
            id=self.id,
            path=str(self.path),
            profiles=self.profiles,
            output_mode=self.output_mode,
            destination=self.destination,
            preserve_structure=self.preserve_structure,
            recursive=self.recursive,
            file_patterns=self.file_patterns,
            min_age_seconds=self.min_age_seconds,
            hardware_accel=self.hardware_accel,
            priority=self.priority,
            active=self.active,
            files_processed=self.files_processed,
            last_activity=self.last_activity,
        )

    def matches_pattern(self, filename: str) -> bool:
        """Check if filename matches any of the file patterns."""
        return any(fnmatch(filename.lower(), pattern.lower()) for pattern in self.file_patterns)

    def is_file_ready(self, file_path: Path) -> bool:
        """
        Check if file is ready to be processed.

        A file is ready when:
        - It has been seen for at least min_age_seconds
        - It's not currently being written (size is stable)
        """
        path_str = str(file_path)

        # Check if already processed
        if path_str in self._processed_files:
            return False

        # Get file modification time
        try:
            mtime = file_path.stat().st_mtime
            age = time.time() - mtime
        except (OSError, FileNotFoundError):
            return False

        # Track pending files
        if path_str not in self._pending_files:
            self._pending_files[path_str] = time.time()
            return False

        # Check if file is old enough
        time_tracked = time.time() - self._pending_files[path_str]
        if age < self.min_age_seconds or time_tracked < self.min_age_seconds:
            return False

        return True

    def mark_processed(self, file_path: Path):
        """Mark a file as processed."""
        path_str = str(file_path)
        self._processed_files.add(path_str)
        self._pending_files.pop(path_str, None)
        self.files_processed += 1
        self.last_activity = datetime.now()

    def get_files_to_process(self) -> list[Path]:
        """Get list of files ready to be processed."""
        files = []

        if not self.path.exists():
            logger.warning(f"Watch folder does not exist: {self.path}")
            return files

        # Scan directory
        if self.recursive:
            scan_iter = self.path.rglob("*")
        else:
            scan_iter = self.path.glob("*")

        for file_path in scan_iter:
            if not file_path.is_file():
                continue

            if not self.matches_pattern(file_path.name):
                continue

            if self.is_file_ready(file_path):
                files.append(file_path)

        return files


class WatchFolderManager:
    """
    Manages multiple watch folders.

    Periodically scans watch folders for new files and submits
    encoding jobs to the queue.
    """

    def __init__(self, job_queue: JobQueue, scan_interval: float = 10.0):
        """
        Initialize watch folder manager.

        Args:
            job_queue: Job queue to submit jobs to
            scan_interval: How often to scan folders (seconds)
        """
        self.job_queue = job_queue
        self.scan_interval = scan_interval

        self._folders: dict[str, WatchFolder] = {}
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the watch folder manager."""
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info(f"Watch folder manager started (scan interval: {self.scan_interval}s)")

    async def stop(self):
        """Stop the watch folder manager."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        logger.info("Watch folder manager stopped")

    async def register(self, request: EncodingRequest) -> str:
        """
        Register a new watch folder.

        Args:
            request: Encoding request with mode=watch

        Returns:
            Watch folder ID
        """
        folder = WatchFolder(request)
        self._folders[folder.id] = folder
        logger.info(f"Registered watch folder {folder.id}: {folder.path}")
        return folder.id

    async def unregister(self, folder_id: str) -> bool:
        """Remove a watch folder."""
        if folder_id in self._folders:
            del self._folders[folder_id]
            logger.info(f"Unregistered watch folder: {folder_id}")
            return True
        return False

    async def get_folder(self, folder_id: str) -> Optional[WatchFolderInfo]:
        """Get watch folder info."""
        folder = self._folders.get(folder_id)
        return folder.to_info() if folder else None

    async def list_folders(self) -> list[WatchFolderInfo]:
        """List all watch folders."""
        return [folder.to_info() for folder in self._folders.values()]

    async def pause(self, folder_id: str) -> bool:
        """Pause a watch folder."""
        folder = self._folders.get(folder_id)
        if folder:
            folder.active = False
            logger.info(f"Paused watch folder: {folder_id}")
            return True
        return False

    async def resume(self, folder_id: str) -> bool:
        """Resume a watch folder."""
        folder = self._folders.get(folder_id)
        if folder:
            folder.active = True
            logger.info(f"Resumed watch folder: {folder_id}")
            return True
        return False

    async def _scan_loop(self):
        """Background task to periodically scan watch folders."""
        while self._running:
            try:
                await self._scan_all_folders()
            except Exception as e:
                logger.error(f"Error scanning watch folders: {e}", exc_info=True)

            await asyncio.sleep(self.scan_interval)

    async def _scan_all_folders(self):
        """Scan all active watch folders for new files."""
        for folder_id, folder in list(self._folders.items()):
            if not folder.active:
                continue

            try:
                files = folder.get_files_to_process()

                for file_path in files:
                    # Create encoding request for this file
                    request = EncodingRequest(
                        mode="encode",
                        profiles=folder.profiles,
                        source=str(file_path),
                        output_mode=folder.output_mode,
                        destination=folder.destination,
                        preserve_structure=folder.preserve_structure,
                        backup=folder.backup,
                        backup_dir=folder.backup_dir,
                        hardware_accel=folder.hardware_accel,
                        priority=folder.priority,
                    )

                    # Submit job
                    job_ids = await self.job_queue.submit(request)

                    if job_ids:
                        folder.mark_processed(file_path)
                        logger.info(
                            f"Watch folder {folder_id}: submitted {len(job_ids)} job(s) "
                            f"for {file_path.name}"
                        )

            except Exception as e:
                logger.error(
                    f"Error processing watch folder {folder_id}: {e}",
                    exc_info=True
                )


class CommandFileWatcher:
    """
    Watches a directory for YAML command files.

    When a .yaml file is dropped in the watched directory, it's parsed
    as an EncodingRequest and submitted to the queue.
    """

    def __init__(
        self,
        watch_path: Path,
        job_queue: JobQueue,
        watch_manager: WatchFolderManager,
        scan_interval: float = 5.0,
        root_media: Optional[Path] = None,
    ):
        """
        Initialize command file watcher.

        Args:
            watch_path: Directory to watch for command files
            job_queue: Job queue to submit jobs to
            watch_manager: Watch folder manager for watch requests
            scan_interval: How often to scan (seconds)
            root_media: Base path for $root_media placeholder expansion
        """
        self.watch_path = watch_path
        self.job_queue = job_queue
        self.watch_manager = watch_manager
        self.scan_interval = scan_interval
        self.root_media = root_media or Path.home() / "Videos"

        self._running = False
        self._paused = False
        self._scan_task: Optional[asyncio.Task] = None
        self._processed_files: set[str] = set()

    async def start(self):
        """Start watching for command files."""
        # Create watch directory if it doesn't exist
        self.watch_path.mkdir(parents=True, exist_ok=True)

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

                        # Expand $root_media placeholders in paths
                        request = request.expand_paths(self.root_media)

                        # Validate
                        issues = request.validate_request()
                        if issues:
                            logger.error(
                                f"Invalid command file {yaml_file.name}: {'; '.join(issues)}"
                            )
                            self._move_to_failed(yaml_file, issues)
                            continue

                        # Process based on mode
                        if request.mode.value == "watch":
                            await self.watch_manager.register(request)
                            logger.info(f"Registered watch folder from: {yaml_file.name}")
                        else:
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


class MediaFileWatcher:
    """
    Watches a directory for media files (video/audio).

    Uses file size stability detection: a file is ready when its size
    hasn't changed for a configurable number of consecutive scans.
    Encoding settings come from the watchfolder configuration.

    Source files are only renamed/deleted AFTER all jobs complete successfully.
    """

    def __init__(self, config, job_queue: JobQueue):
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

    async def start(self):
        """Start watching for media files."""
        self.watch_path.mkdir(parents=True, exist_ok=True)

        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info(
            f"Media file watcher started: {self.watch_path} "
            f"(profiles: {self.config.profiles}, stability: {self.config.stability_scans} scans)"
        )

    async def stop(self):
        """Stop watching."""
        self._running = False
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

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        Check if file is ready using size stability.

        A file is ready when its size hasn't changed for
        `stability_scans` consecutive scans.
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

        # Get current file size
        try:
            current_size = file_path.stat().st_size
        except (OSError, FileNotFoundError):
            # File disappeared or inaccessible
            self._pending_files.pop(path_str, None)
            return False

        if path_str not in self._pending_files:
            # First time seeing this file
            self._pending_files[path_str] = PendingFile(
                first_seen=time.time(),
                last_size=current_size,
                stable_count=0
            )
            logger.debug(f"Media watcher: new file detected: {file_path.name} ({current_size} bytes)")
            return False

        pending = self._pending_files[path_str]

        if current_size == pending.last_size:
            # Size unchanged - increment stable count
            pending.stable_count += 1
            logger.debug(
                f"Media watcher: {file_path.name} stable count: {pending.stable_count}/{self.config.stability_scans}"
            )
        else:
            # Size changed - reset counter
            logger.debug(
                f"Media watcher: {file_path.name} size changed: {pending.last_size} -> {current_size}"
            )
            pending.last_size = current_size
            pending.stable_count = 0

        return pending.stable_count >= self.config.stability_scans

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

        if self.config.recursive:
            scan_iter = self.watch_path.rglob("*")
        else:
            scan_iter = self.watch_path.glob("*")

        for file_path in scan_iter:
            if not file_path.is_file():
                continue

            if not self._matches_pattern(file_path.name):
                continue

            if self._is_file_ready(file_path):
                await self._submit_job(file_path)

    def _get_temp_folder(self) -> Path:
        """Get temp folder for source copy and encoding workspace."""
        import tempfile
        if self.config.temp_folder:
            temp_folder = self.config.temp_folder
        else:
            temp_folder = Path(tempfile.gettempdir()) / "videotranscode"
        temp_folder.mkdir(parents=True, exist_ok=True)
        return temp_folder

    async def _submit_job(self, file_path: Path):
        """
        Submit encoding job for a ready file.

        Workflow:
        1. Copy source to temp folder (unless disable_temp_copy=True)
        2. Rename source to .processing
        3. Submit job(s) - encodes from temp, outputs to destination
        4. (After completion) Rename .processing to .processed/.failed
        """
        import shutil
        path_str = str(file_path)
        original_path = file_path
        processing_path = file_path.with_suffix(file_path.suffix + ".processing")

        # Destination is required (validated at startup)
        destination = self.config.destination
        temp_folder = self._get_temp_folder()
        temp_source: Optional[Path] = None

        try:
            # Step 1: Copy source to temp folder (if enabled)
            if not self.config.disable_temp_copy:
                temp_source = temp_folder / file_path.name
                logger.info(f"Media watcher: copying {file_path.name} to temp folder")
                shutil.copy2(file_path, temp_source)
                source_for_encoding = temp_source
            else:
                # Encode directly from original (will be renamed to .processing)
                source_for_encoding = processing_path

            # Step 2: Rename source to .processing
            logger.info(f"Media watcher: renaming {file_path.name} to {processing_path.name}")
            file_path.rename(processing_path)

        except Exception as e:
            logger.error(f"Media watcher: failed to prepare {file_path.name}: {e}")
            self._pending_files.pop(path_str, None)
            self._failed_files.add(path_str)
            # Cleanup temp if we created it
            if temp_source and temp_source.exists():
                temp_source.unlink()
            return

        # Step 3: Build and submit encoding request
        request = EncodingRequest(
            mode="encode",
            profiles=self.config.profiles,
            source=str(source_for_encoding),
            output_mode="destination",
            destination=str(destination),
            backup=False,  # We handle source file ourselves
            hardware_accel=self.config.hardware_accel,
            priority=self.config.priority,
        )

        # Validate request
        issues = request.validate_request()
        if issues:
            logger.error(f"Media watcher: invalid request for {file_path.name}: {'; '.join(issues)}")
            self._pending_files.pop(path_str, None)
            self._failed_files.add(path_str)
            # Rollback: rename .processing back to original
            try:
                processing_path.rename(original_path)
            except Exception:
                pass
            # Cleanup temp
            if temp_source and temp_source.exists():
                temp_source.unlink()
            return

        # Submit job(s)
        job_ids = await self.job_queue.submit(request)

        if job_ids:
            # Track submitted jobs - source file handling happens after job completion
            self._submitted_jobs[path_str] = SubmittedJob(
                original_path=original_path,
                processing_path=processing_path,
                temp_source=temp_source,
                job_ids=job_ids,
                submitted_at=time.time(),
            )
            self._pending_files.pop(path_str, None)
            logger.info(
                f"Media watcher: submitted {len(job_ids)} job(s) for {file_path.name} "
                f"(temp_copy={'disabled' if self.config.disable_temp_copy else 'enabled'})"
            )
        else:
            # Job submission failed - rollback
            logger.error(f"Media watcher: failed to submit jobs for {file_path.name}")
            self._pending_files.pop(path_str, None)
            self._failed_files.add(path_str)
            try:
                processing_path.rename(original_path)
            except Exception:
                pass
            if temp_source and temp_source.exists():
                temp_source.unlink()

    async def _check_completed_jobs(self):
        """Check submitted jobs and handle source files when all jobs complete."""
        from .models import JobStatus

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

        # Remove completed entries
        for path_str in completed_paths:
            del self._submitted_jobs[path_str]

    def _handle_completed_job(self, submitted: SubmittedJob, failed: bool = False):
        """
        Handle completed job - rename .processing file and cleanup temp.

        Args:
            submitted: SubmittedJob with file paths
            failed: True if any job failed/cancelled

        Behavior:
        - If any job failed: .processing -> .failed
        - If all succeeded and keep_processed_files=True: .processing -> .processed
        - If all succeeded and keep_processed_files=False: delete .processing file
        - Always cleanup temp source copy
        """
        processing_path = submitted.processing_path
        original_name = submitted.original_path.name

        # Handle the .processing file
        if not processing_path.exists():
            logger.warning(f"Media watcher: .processing file no longer exists: {processing_path.name}")
        else:
            try:
                if failed:
                    # Some jobs failed - rename to .failed for easy identification
                    # .processing -> .failed (remove .processing, add .failed)
                    failed_path = submitted.original_path.with_suffix(
                        submitted.original_path.suffix + ".failed"
                    )
                    processing_path.rename(failed_path)
                    logger.warning(f"Media watcher: {original_name} -> {failed_path.name} (encoding failed)")
                elif self.config.keep_processed_files:
                    # All succeeded - rename to .processed
                    processed_path = submitted.original_path.with_suffix(
                        submitted.original_path.suffix + ".processed"
                    )
                    processing_path.rename(processed_path)
                    logger.info(f"Media watcher: {original_name} -> {processed_path.name}")
                else:
                    # All succeeded - delete source file
                    processing_path.unlink()
                    logger.info(f"Media watcher: deleted original {original_name}")
            except Exception as e:
                logger.warning(f"Media watcher: failed to handle {processing_path.name}: {e}")

        # Cleanup temp source copy
        if submitted.temp_source and submitted.temp_source.exists():
            try:
                submitted.temp_source.unlink()
                logger.debug(f"Media watcher: cleaned up temp source {submitted.temp_source.name}")
            except Exception as e:
                logger.warning(f"Media watcher: failed to cleanup temp source: {e}")


class WatchfolderService:
    """
    Manages watchfolders based on configuration files.

    Loads watchfolder configurations from ~/.config/videotranscode/watchfolders/
    and starts appropriate watchers:
    - CommandFileWatcher for 'command' type (watches for YAML command files)
    - MediaFileWatcher for 'media' type (watches for video/audio files)
    """

    def __init__(self, job_queue: JobQueue, watch_manager: WatchFolderManager):
        """
        Initialize watchfolder service.

        Args:
            job_queue: Job queue to submit jobs to
            watch_manager: Watch folder manager for watch requests
        """
        self.job_queue = job_queue
        self.watch_manager = watch_manager
        self._command_watchers: dict[str, CommandFileWatcher] = {}
        self._media_watchers: dict[str, MediaFileWatcher] = {}
        self._root_media: Optional[Path] = None  # Set in start()

    async def start(self):
        """Load watchfolder configs and start watchers."""
        from ..config.manager import ConfigManager
        from ..config.schema import WatchfolderType

        # Load main config to get root_media setting
        main_config = ConfigManager.load_config()
        self._root_media = main_config.storage.root_media

        configs = ConfigManager.load_watchfolder_configs()
        logger.info(f"Loaded {len(configs)} watchfolder configuration(s)")

        for config in configs:
            if config.watchfolder_type == WatchfolderType.COMMAND:
                await self._start_command_watcher(config)
            elif config.watchfolder_type == WatchfolderType.MEDIA:
                await self._start_media_watcher(config)

    async def _start_command_watcher(self, config):
        """Start a command file watcher for the given config."""
        location = config.watchfolder_location
        location_str = str(location)

        if location_str in self._command_watchers:
            logger.warning(f"Command watcher already exists for: {location}")
            return

        watcher = CommandFileWatcher(
            watch_path=location,
            job_queue=self.job_queue,
            watch_manager=self.watch_manager,
            scan_interval=config.scan_interval,
            root_media=self._root_media,
        )
        await watcher.start()
        self._command_watchers[location_str] = watcher
        logger.info(f"Started command watcher for: {location}")

    async def _start_media_watcher(self, config):
        """Start a media file watcher for the given config."""
        location = config.watchfolder_location
        location_str = str(location)

        # Validate media config has profiles
        if not config.profiles:
            logger.error(
                f"Media watchfolder missing 'profiles' setting: {location}. "
                "Skipping this watchfolder."
            )
            return

        # Validate destination is set (required to avoid infinite re-encoding)
        if not config.destination:
            logger.error(
                f"Media watchfolder missing 'destination' setting: {location}. "
                "Media watchfolders require a destination folder for encoded files. "
                "Skipping this watchfolder."
            )
            return

        # Validate destination differs from source (prevent infinite loop)
        if config.destination.resolve() == location.resolve():
            logger.error(
                f"Media watchfolder destination cannot be the same as watchfolder_location: {location}. "
                "This would cause infinite re-encoding. Skipping this watchfolder."
            )
            return

        if location_str in self._media_watchers:
            logger.warning(f"Media watcher already exists for: {location}")
            return

        watcher = MediaFileWatcher(config=config, job_queue=self.job_queue)
        await watcher.start()
        self._media_watchers[location_str] = watcher
        logger.info(f"Started media watcher for: {location} -> {config.destination}")

    async def stop(self):
        """Stop all watchers."""
        for location, watcher in self._command_watchers.items():
            await watcher.stop()
        self._command_watchers.clear()

        for location, watcher in self._media_watchers.items():
            await watcher.stop()
        self._media_watchers.clear()

    def get_active_watchers(self) -> dict[str, list[dict]]:
        """Get dict of active watchfolder info by type."""
        command_list = []
        for path, watcher in self._command_watchers.items():
            command_list.append({
                "id": path,
                "path": path,
                "scan_interval": watcher.scan_interval,
                "active": watcher._running,
                "paused": getattr(watcher, '_paused', False),
            })

        media_list = []
        for path, watcher in self._media_watchers.items():
            media_list.append({
                "id": path,
                "path": path,
                "profiles": watcher.config.profiles,
                "destination": str(watcher.config.destination),
                "scan_interval": watcher.config.scan_interval,
                "file_patterns": watcher.config.file_patterns,
                "active": watcher._running,
                "paused": getattr(watcher, '_paused', False),
                "pending_files": len(watcher._pending_files),
                "submitted_jobs": len(watcher._submitted_jobs),
            })

        return {
            "command": command_list,
            "media": media_list,
        }

    def get_watcher(self, folder_id: str) -> Optional[dict]:
        """Get a specific watcher by ID (path)."""
        # Check command watchers
        if folder_id in self._command_watchers:
            watcher = self._command_watchers[folder_id]
            return {
                "id": folder_id,
                "path": folder_id,
                "type": "command",
                "scan_interval": watcher.scan_interval,
                "active": watcher._running,
                "paused": getattr(watcher, '_paused', False),
            }

        # Check media watchers
        if folder_id in self._media_watchers:
            watcher = self._media_watchers[folder_id]
            return {
                "id": folder_id,
                "path": folder_id,
                "type": "media",
                "profiles": watcher.config.profiles,
                "destination": str(watcher.config.destination),
                "scan_interval": watcher.config.scan_interval,
                "file_patterns": watcher.config.file_patterns,
                "active": watcher._running,
                "paused": getattr(watcher, '_paused', False),
                "pending_files": len(watcher._pending_files),
                "submitted_jobs": len(watcher._submitted_jobs),
            }

        return None

    def pause_watcher(self, folder_id: str) -> bool:
        """Pause a watcher by ID."""
        if folder_id in self._command_watchers:
            self._command_watchers[folder_id]._paused = True
            logger.info(f"Paused command watcher: {folder_id}")
            return True

        if folder_id in self._media_watchers:
            self._media_watchers[folder_id]._paused = True
            logger.info(f"Paused media watcher: {folder_id}")
            return True

        return False

    def resume_watcher(self, folder_id: str) -> bool:
        """Resume a paused watcher by ID."""
        if folder_id in self._command_watchers:
            self._command_watchers[folder_id]._paused = False
            logger.info(f"Resumed command watcher: {folder_id}")
            return True

        if folder_id in self._media_watchers:
            self._media_watchers[folder_id]._paused = False
            logger.info(f"Resumed media watcher: {folder_id}")
            return True

        return False

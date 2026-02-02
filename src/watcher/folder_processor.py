"""Shared folder processing with stability detection and re-scanning."""

import logging
import time
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PendingFile:
    """Tracks a file for size stability detection."""
    first_seen: float
    last_size: int
    stable_count: int = 0


@dataclass
class TrackedFolder:
    """Tracks a folder being processed."""
    path: Path
    first_seen: float
    known_files: set[str] = field(default_factory=set)
    pending_files: dict[str, PendingFile] = field(default_factory=dict)
    submitted_files: set[str] = field(default_factory=set)
    pending_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    stable_scans: int = 0  # Scans with no new files


class FolderProcessor:
    """
    Processes folders with stability detection and re-scanning.

    Used by both MediaFileWatcher and JobQueue for consistent folder handling.
    Provides:
    - Recursive folder scanning for video files
    - File size stability detection (wait for files to finish copying)
    - Re-scanning during encoding to catch new files
    - Folder completion detection

    Usage:
        processor = FolderProcessor(file_patterns=["*.mkv", "*.mp4"])
        folder_key = processor.register_folder(Path("/path/to/folder"))

        # In a loop:
        processor.scan_folder(folder_key)
        for file_path in processor.get_ready_files(folder_key):
            # Submit job
            processor.mark_file_submitted(folder_key, file_path)

        # When job completes:
        processor.mark_job_completed(folder_key, success=True)

        # Check completion:
        if processor.is_folder_complete(folder_key):
            folder_path = processor.complete_folder(folder_key)
            # Rename folder to .processed
    """

    def __init__(
        self,
        file_patterns: list[str],
        stability_scans: int = 2,
        scan_interval: float = 5.0,
        recursive: bool = True,
    ):
        """
        Initialize folder processor.

        Args:
            file_patterns: Glob patterns to match files (e.g., ["*.mkv", "*.mp4"])
            stability_scans: Number of consecutive scans with stable file size
            scan_interval: Interval between scans in seconds
            recursive: Whether to scan subdirectories
        """
        self.file_patterns = file_patterns
        self.stability_scans = stability_scans
        self.scan_interval = scan_interval
        self.recursive = recursive

        self._folders: dict[str, TrackedFolder] = {}

    def register_folder(self, folder_path: Path) -> str:
        """
        Register a folder for processing.

        Args:
            folder_path: Path to folder to process

        Returns:
            Folder key (string path) for subsequent operations
        """
        folder_key = str(folder_path)
        if folder_key not in self._folders:
            self._folders[folder_key] = TrackedFolder(
                path=folder_path,
                first_seen=time.time(),
            )
            logger.info(f"Folder registered for processing: {folder_path.name}")
        return folder_key

    def is_registered(self, folder_path: Path) -> bool:
        """Check if a folder is registered."""
        return str(folder_path) in self._folders

    def matches_pattern(self, filename: str) -> bool:
        """Check if filename matches any of the file patterns."""
        return any(
            fnmatch(filename.lower(), pattern.lower())
            for pattern in self.file_patterns
        )

    def scan_folder(self, folder_key: str) -> list[Path]:
        """
        Scan folder for new files.

        Detects new files that match patterns and adds them to tracking.
        Updates folder stability counter.

        Args:
            folder_key: Folder key from register_folder()

        Returns:
            List of newly detected file paths
        """
        folder = self._folders.get(folder_key)
        if not folder or not folder.path.exists():
            return []

        new_files = []

        if self.recursive:
            scan_iter = folder.path.rglob("*")
        else:
            scan_iter = folder.path.glob("*")

        for file_path in scan_iter:
            if not file_path.is_file():
                continue
            if not self.matches_pattern(file_path.name):
                continue

            file_key = str(file_path)
            if file_key in folder.known_files:
                continue  # Already tracking this file

            # Skip files with processing/processed/failed markers
            if any(file_path.name.endswith(suffix) for suffix in [".processing", ".processed", ".failed"]):
                continue

            # New file found
            try:
                file_size = file_path.stat().st_size
            except (OSError, FileNotFoundError):
                continue

            folder.known_files.add(file_key)
            folder.pending_files[file_key] = PendingFile(
                first_seen=time.time(),
                last_size=file_size,
            )
            new_files.append(file_path)
            logger.debug(f"New file detected in folder: {file_path.name}")

        # Update folder stability
        if new_files:
            folder.stable_scans = 0
            logger.info(f"Folder {folder.path.name}: {len(new_files)} new file(s) detected")
        else:
            folder.stable_scans += 1

        return new_files

    def check_file_ready(self, folder_key: str, file_path: Path) -> bool:
        """
        Check if a file is stable and ready for processing.

        A file is ready when its size hasn't changed for stability_scans
        consecutive checks.

        Args:
            folder_key: Folder key
            file_path: File to check

        Returns:
            True if file is ready for processing
        """
        folder = self._folders.get(folder_key)
        if not folder:
            return False

        file_key = str(file_path)
        pending = folder.pending_files.get(file_key)
        if not pending:
            return False

        # Skip if already submitted
        if file_key in folder.submitted_files:
            return False

        try:
            current_size = file_path.stat().st_size
        except (OSError, FileNotFoundError):
            # File disappeared
            folder.pending_files.pop(file_key, None)
            return False

        if current_size == pending.last_size:
            pending.stable_count += 1
            logger.debug(
                f"File {file_path.name} stable count: "
                f"{pending.stable_count}/{self.stability_scans}"
            )
        else:
            pending.last_size = current_size
            pending.stable_count = 0
            logger.debug(f"File {file_path.name} size changed, resetting stability")

        return pending.stable_count >= self.stability_scans

    def get_ready_files(self, folder_key: str) -> list[Path]:
        """
        Get all files that are ready for processing.

        Args:
            folder_key: Folder key

        Returns:
            List of file paths ready for encoding
        """
        folder = self._folders.get(folder_key)
        if not folder:
            return []

        ready = []
        for file_key in list(folder.pending_files.keys()):
            file_path = Path(file_key)
            if self.check_file_ready(folder_key, file_path):
                ready.append(file_path)
        return ready

    def mark_file_submitted(self, folder_key: str, file_path: Path):
        """
        Mark a file as submitted for encoding.

        Moves file from pending to submitted tracking.

        Args:
            folder_key: Folder key
            file_path: File that was submitted
        """
        folder = self._folders.get(folder_key)
        if folder:
            file_key = str(file_path)
            folder.submitted_files.add(file_key)
            folder.pending_jobs += 1
            # Remove from pending (no longer need stability tracking)
            folder.pending_files.pop(file_key, None)
            logger.debug(f"File submitted: {file_path.name}")

    def mark_job_completed(self, folder_key: str, success: bool = True):
        """
        Mark a job as completed.

        Call this when an encoding job finishes.

        Args:
            folder_key: Folder key
            success: True if job succeeded, False if failed
        """
        folder = self._folders.get(folder_key)
        if folder:
            folder.pending_jobs = max(0, folder.pending_jobs - 1)
            if success:
                folder.completed_jobs += 1
            else:
                folder.failed_jobs += 1

    def is_folder_complete(self, folder_key: str) -> bool:
        """
        Check if folder processing is complete.

        A folder is complete when:
        1. No pending jobs (all encoding done)
        2. No files waiting for stability
        3. Multiple stable scans with no new files detected

        Args:
            folder_key: Folder key

        Returns:
            True if folder is fully processed
        """
        folder = self._folders.get(folder_key)
        if not folder:
            return True

        return (
            folder.pending_jobs == 0 and
            len(folder.pending_files) == 0 and
            folder.stable_scans >= self.stability_scans
        )

    def get_folder_stats(self, folder_key: str) -> dict:
        """
        Get folder processing statistics.

        Args:
            folder_key: Folder key

        Returns:
            Dict with folder stats
        """
        folder = self._folders.get(folder_key)
        if not folder:
            return {}
        return {
            "path": str(folder.path),
            "known_files": len(folder.known_files),
            "pending_stability": len(folder.pending_files),
            "submitted": len(folder.submitted_files),
            "pending_jobs": folder.pending_jobs,
            "completed_jobs": folder.completed_jobs,
            "failed_jobs": folder.failed_jobs,
            "stable_scans": folder.stable_scans,
        }

    def get_all_folder_keys(self) -> list[str]:
        """Get all registered folder keys."""
        return list(self._folders.keys())

    def complete_folder(self, folder_key: str) -> Optional[Path]:
        """
        Mark folder as complete and remove from tracking.

        Call this after is_folder_complete() returns True.

        Args:
            folder_key: Folder key

        Returns:
            Path to the folder (for renaming), or None if not found
        """
        folder = self._folders.pop(folder_key, None)
        if folder:
            stats = {
                "completed": folder.completed_jobs,
                "failed": folder.failed_jobs,
            }
            logger.info(
                f"Folder complete: {folder.path.name} "
                f"({stats['completed']} succeeded, {stats['failed']} failed)"
            )
            return folder.path
        return None

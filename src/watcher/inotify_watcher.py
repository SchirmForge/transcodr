"""Inotify-based file completion detection for local filesystems."""

import logging
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from threading import Thread, Event
from typing import Callable, Optional, Set

try:
    from inotify_simple import INotify, flags
    INOTIFY_AVAILABLE = True
except ImportError:
    INOTIFY_AVAILABLE = False
    INotify = None
    flags = None

logger = logging.getLogger(__name__)

# Local filesystem types that support inotify
LOCAL_FILESYSTEM_TYPES = {
    'ext4', 'ext3', 'ext2', 'xfs', 'btrfs', 'zfs',
    'tmpfs', 'overlay', 'overlayfs', 'aufs',
    'f2fs', 'reiserfs', 'jfs', 'nilfs2'
}

# Remote filesystem types that don't support inotify
REMOTE_FILESYSTEM_TYPES = {
    'nfs', 'nfs4', 'cifs', 'smb', 'smbfs',
    'fuse.sshfs', 'fuse.rclone', 'fuse.s3fs',
    'afs', 'ceph', 'glusterfs', 'lustre'
}


def is_local_filesystem(path: Path) -> bool:
    """
    Check if path is on a local filesystem that supports inotify.

    Args:
        path: Path to check

    Returns:
        True if path is on a local filesystem, False for NFS/CIFS/etc.
    """
    try:
        # Use stat -f to get filesystem type
        result = subprocess.run(
            ['stat', '-f', '-c', '%T', str(path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            logger.debug(f"stat failed for {path}: {result.stderr}")
            return False

        fs_type = result.stdout.strip().lower()
        logger.debug(f"Filesystem type for {path}: {fs_type}")

        # Check against known types
        if fs_type in LOCAL_FILESYSTEM_TYPES:
            return True
        if fs_type in REMOTE_FILESYSTEM_TYPES:
            return False

        # Unknown type - assume local if not obviously remote
        logger.debug(f"Unknown filesystem type '{fs_type}' for {path}, assuming local")
        return True

    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout checking filesystem type for {path}")
        return False
    except Exception as e:
        logger.warning(f"Error checking filesystem type for {path}: {e}")
        return False


class InotifyWatcher:
    """
    Watch a directory for IN_CLOSE_WRITE events (file copy completion).

    Only works on local filesystems. For NFS, the caller should use
    polling as a fallback.

    Usage:
        watcher = InotifyWatcher(
            watch_path=Path('/watchfolder'),
            callback=on_file_ready,
            file_patterns=['*.mkv', '*.mp4']
        )
        if watcher.is_supported():
            watcher.start()
        # Later:
        watcher.stop()
    """

    def __init__(
        self,
        watch_path: Path,
        callback: Callable[[Path], None],
        file_patterns: list[str],
    ):
        """
        Initialize inotify watcher.

        Args:
            watch_path: Directory to watch
            callback: Function to call when a file is ready (closed after write)
            file_patterns: Glob patterns to match files (e.g., ['*.mkv', '*.mp4'])
        """
        self.watch_path = watch_path
        self.callback = callback
        self.file_patterns = file_patterns

        self._inotify: Optional[INotify] = None
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._running = False

    def is_supported(self) -> bool:
        """
        Check if inotify can be used for this path.

        Returns:
            True if inotify is available and path is on local filesystem
        """
        if not INOTIFY_AVAILABLE:
            logger.debug("inotify_simple not installed")
            return False
        return is_local_filesystem(self.watch_path)

    def start(self) -> bool:
        """
        Start watching for CLOSE_WRITE events.

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            return True

        if not INOTIFY_AVAILABLE:
            logger.warning("Cannot start inotify: inotify_simple not installed")
            return False

        try:
            self._inotify = INotify()
            # Watch for:
            # - CLOSE_WRITE: File closed after being written (copy complete)
            # - MOVED_TO: File moved into the directory (mv command)
            watch_flags = flags.CLOSE_WRITE | flags.MOVED_TO
            self._inotify.add_watch(str(self.watch_path), watch_flags)

            self._stop_event.clear()
            self._thread = Thread(target=self._watch_loop, daemon=True, name="inotify-watcher")
            self._thread.start()
            self._running = True

            logger.info(f"Inotify watcher started for {self.watch_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to start inotify watcher: {e}")
            self._cleanup()
            return False

    def stop(self):
        """Stop watching and cleanup resources."""
        if not self._running:
            return

        logger.debug(f"Stopping inotify watcher for {self.watch_path}")
        self._stop_event.set()
        self._cleanup()
        self._running = False

    def _cleanup(self):
        """Clean up inotify resources."""
        if self._inotify:
            try:
                self._inotify.close()
            except Exception:
                pass
            self._inotify = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def _watch_loop(self):
        """Main loop reading inotify events."""
        logger.debug(f"Inotify watch loop started for {self.watch_path}")

        while not self._stop_event.is_set():
            try:
                # Read with timeout so we can check stop_event periodically
                events = self._inotify.read(timeout=1000)  # 1 second timeout

                for event in events:
                    if not event.name:
                        continue

                    if self._matches_pattern(event.name):
                        file_path = self.watch_path / event.name
                        event_type = "CLOSE_WRITE" if event.mask & flags.CLOSE_WRITE else "MOVED_TO"
                        logger.info(f"File ready ({event_type}): {event.name}")

                        try:
                            self.callback(file_path)
                        except Exception as e:
                            logger.error(f"Error in inotify callback for {event.name}: {e}")

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Inotify read error: {e}")
                    # Brief sleep to avoid tight error loop
                    self._stop_event.wait(1)

        logger.debug(f"Inotify watch loop ended for {self.watch_path}")

    def _matches_pattern(self, filename: str) -> bool:
        """Check if filename matches any of the watch patterns."""
        return any(
            fnmatch(filename.lower(), pattern.lower())
            for pattern in self.file_patterns
        )

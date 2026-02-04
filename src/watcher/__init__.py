"""Watcher module for video transcoding watchfolders."""

from .schema import WatchfolderType, WatchfolderConfig
from .manager import WatchfolderConfigManager
from .folder_processor import FolderProcessor, TrackedFolder, PendingFile, is_file_ready
from .inotify_watcher import InotifyWatcher, is_local_filesystem, INOTIFY_AVAILABLE
from .watchers import (
    WatchFolder,
    WatchFolderManager,
    CommandFileWatcher,
    SubmittedJob,
    MediaFileWatcher,
)
from .service import WatchfolderService

__all__ = [
    # Schema
    "WatchfolderType",
    "WatchfolderConfig",
    # Manager
    "WatchfolderConfigManager",
    # Folder processor
    "FolderProcessor",
    "TrackedFolder",
    "PendingFile",
    "is_file_ready",
    # Inotify
    "InotifyWatcher",
    "is_local_filesystem",
    "INOTIFY_AVAILABLE",
    # Watchers
    "WatchFolder",
    "WatchFolderManager",
    "CommandFileWatcher",
    "SubmittedJob",
    "MediaFileWatcher",
    # Service
    "WatchfolderService",
]

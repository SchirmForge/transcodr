"""Watcher module for video transcoding watchfolders."""

from .schema import WatchfolderType, WatchfolderConfig
from .manager import WatchfolderConfigManager
from .folder_processor import FolderProcessor, TrackedFolder, PendingFile as FolderPendingFile
from .watchers import (
    PendingFile,
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
    "FolderPendingFile",
    # Watchers
    "PendingFile",
    "WatchFolder",
    "WatchFolderManager",
    "CommandFileWatcher",
    "SubmittedJob",
    "MediaFileWatcher",
    # Service
    "WatchfolderService",
]

"""Watchfolder service for managing config-based watchers."""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .schema import WatchfolderType
from .manager import WatchfolderConfigManager
from .watchers import WatchFolderManager, CommandFileWatcher, MediaFileWatcher

if TYPE_CHECKING:
    from ..api.queue import JobQueue

logger = logging.getLogger(__name__)


class WatchfolderService:
    """
    Manages watchfolders based on configuration files.

    Loads watchfolder configurations from ~/.config/videotranscode/watchfolders/
    and starts appropriate watchers:
    - CommandFileWatcher for 'command' type (watches for YAML command files)
    - MediaFileWatcher for 'media' type (watches for video/audio files)
    """

    def __init__(self, job_queue: "JobQueue", watch_manager: WatchFolderManager):
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

        # Load main config to get root_media setting
        main_config = ConfigManager.load_config()
        self._root_media = main_config.storage.root_media

        configs = WatchfolderConfigManager.load_configs()
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

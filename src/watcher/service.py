"""Watchfolder service for managing config-based watchers."""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .schema import WatchfolderType
from .manager import WatchfolderConfigManager
from .watchers import CommandFileWatcher, MediaFileWatcher

if TYPE_CHECKING:
    from ..api.queue import JobQueue

logger = logging.getLogger(__name__)


class WatchfolderService:
    """
    Manages watchfolders based on configuration files.

    Loads watchfolder configurations from ~/.config/transcodr/watchfolders/
    and starts appropriate watchers:
    - CommandFileWatcher for 'command' type (watches for YAML command files)
    - MediaFileWatcher for 'media' type (watches for video/audio files)
    """

    def __init__(self, job_queue: "JobQueue"):
        """
        Initialize watchfolder service.

        Args:
            job_queue: Job queue to submit jobs to
        """
        self.job_queue = job_queue
        self._command_watchers: dict[str, CommandFileWatcher] = {}
        self._media_watchers: dict[str, MediaFileWatcher] = {}
        self._root_media: Optional[Path] = None  # Set in start()
        self._validated_profile_destinations: set[str] = set()  # Track validated paths

    async def start(self):
        """Load watchfolder configs and start watchers."""
        from ..config.manager import ConfigManager
        from ..profiles.store import get_profile_manager

        # Load main config to get root_media setting
        main_config = ConfigManager.load_config()
        self._root_media = main_config.storage.root_media

        configs = WatchfolderConfigManager.load_configs()
        logger.info(f"Loaded {len(configs)} watchfolder configuration(s)")

        # Create profile manager for validation
        profile_manager = get_profile_manager()
        self._validated_profile_destinations.clear()  # Reset on start/reload

        for config in configs:
            # Validate watchfolder before starting
            errors, warnings = self._validate_watchfolder(config, profile_manager)
            for warning in warnings:
                logger.warning(f"Watchfolder {config.watchfolder_location}: {warning}")
            if errors:
                for error in errors:
                    logger.error(f"Watchfolder {config.watchfolder_location}: {error}")
                logger.error(f"Skipping invalid watchfolder: {config.watchfolder_location}")
                continue

            if config.watchfolder_type == WatchfolderType.COMMAND:
                await self._start_command_watcher(config)
            elif config.watchfolder_type == WatchfolderType.MEDIA:
                await self._start_media_watcher(config)

    def _expand_profile_destination(self, dest_str: str) -> Path:
        """Expand $root_media, ~, $HOME in profile destination."""
        import os
        if self._root_media and "$root_media" in dest_str:
            root_str = str(self._root_media).rstrip("/")
            dest_str = dest_str.replace("$root_media", root_str)
        return Path(os.path.expandvars(os.path.expanduser(dest_str)))

    def _validate_watchfolder(
        self,
        config,
        profile_manager,
    ) -> tuple[list[str], list[str]]:
        """
        Validate watchfolder configuration before starting.

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Check watchfolder location exists
        if not config.watchfolder_location.exists():
            errors.append("Location does not exist")
        elif not config.watchfolder_location.is_dir():
            errors.append("Location is not a directory")

        # For media type, validate profiles and destination
        if config.watchfolder_type == WatchfolderType.MEDIA:
            # Validate profiles list is not empty
            if not config.profiles:
                errors.append("Missing 'profiles' setting")

            # Validate profiles exist
            for profile_name in config.profiles:
                if not profile_manager.profile_exists(profile_name):
                    errors.append(f"Profile not found: '{profile_name}'")

            # Validate destination settings
            if config.use_profile_destination:
                # use_profile_destination mode - validate each profile's destination
                for profile_name in config.profiles:
                    if not profile_manager.profile_exists(profile_name):
                        continue  # Already reported as error above
                    try:
                        profile = profile_manager.load_profile(profile_name)
                        if not profile.destination:
                            errors.append(f"Profile '{profile_name}' has no destination field")
                        else:
                            # Skip if already validated (avoids duplicate checks)
                            if profile.destination in self._validated_profile_destinations:
                                continue
                            # Expand and validate
                            dest_path = self._expand_profile_destination(profile.destination)
                            if not dest_path.exists():
                                errors.append(
                                    f"Profile '{profile_name}' destination does not exist: {dest_path}"
                                )
                            elif not dest_path.is_dir():
                                errors.append(
                                    f"Profile '{profile_name}' destination is not a directory: {dest_path}"
                                )
                            else:
                                self._validated_profile_destinations.add(profile.destination)
                    except Exception as e:
                        errors.append(f"Failed to load profile '{profile_name}': {e}")
            elif not config.destination:
                errors.append(
                    "Missing 'destination' setting. "
                    "Media watchfolders require a destination folder (or use_profile_destination: true)."
                )
            else:
                # Direct destination path - validate it exists and differs from source
                if config.destination.resolve() == config.watchfolder_location.resolve():
                    errors.append(
                        "Destination cannot be the same as watchfolder_location. "
                        "This would cause infinite re-encoding."
                    )
                elif not config.destination.exists():
                    errors.append(f"Destination does not exist: {config.destination}")
                elif not config.destination.is_dir():
                    errors.append(f"Destination is not a directory: {config.destination}")

        return errors, warnings

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
            scan_interval=config.scan_interval,
            root_media=self._root_media,
        )
        await watcher.start()
        self._command_watchers[location_str] = watcher
        logger.info(f"Started command watcher for: {location}")

    async def _start_media_watcher(self, config):
        """Start a media file watcher for the given config."""
        # Note: Validation is done in _validate_watchfolder() before this is called
        location = config.watchfolder_location
        location_str = str(location)

        if location_str in self._media_watchers:
            logger.warning(f"Media watcher already exists for: {location}")
            return

        watcher = MediaFileWatcher(config=config, job_queue=self.job_queue)
        await watcher.start()
        self._media_watchers[location_str] = watcher
        dest_info = "profile destinations" if config.use_profile_destination else config.destination
        logger.info(f"Started media watcher for: {location} -> {dest_info}")

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
            dest_value = (
                "profile" if watcher.config.use_profile_destination
                else str(watcher.config.destination)
            )
            media_list.append({
                "id": path,
                "path": path,
                "profiles": watcher.config.profiles,
                "destination": dest_value,
                "use_profile_destination": watcher.config.use_profile_destination,
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
            dest_value = (
                "profile" if watcher.config.use_profile_destination
                else str(watcher.config.destination)
            )
            return {
                "id": folder_id,
                "path": folder_id,
                "type": "media",
                "profiles": watcher.config.profiles,
                "destination": dest_value,
                "use_profile_destination": watcher.config.use_profile_destination,
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

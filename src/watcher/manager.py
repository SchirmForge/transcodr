"""Watchfolder configuration manager."""

import logging
import os
from pathlib import Path
import yaml

from ..config.manager import ConfigManager, expand_path
from .schema import WatchfolderConfig

logger = logging.getLogger(__name__)


class WatchfolderConfigManager:
    """
    Manages watchfolder configuration files.

    Loads watchfolder configurations from YAML files in
    ~/.config/transcodr/watchfolders/
    """

    @staticmethod
    def ensure_config_dir() -> None:
        """Ensure watchfolders configuration directory exists."""
        config_dir = ConfigManager.get_watchfolders_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Watchfolders config directory: {config_dir}")

    @staticmethod
    def load_configs() -> list[WatchfolderConfig]:
        """
        Load all watchfolder configurations from watchfolders directory.

        Expands environment variables ($HOME, ${HOME}, ~) and $root_media
        placeholder in all path values.

        Returns:
            List of WatchfolderConfig objects
        """
        watchfolders_dir = ConfigManager.get_watchfolders_config_dir()
        configs = []

        if not watchfolders_dir.exists():
            return configs

        # Get root_media for $root_media expansion
        main_config = ConfigManager.load_config()
        root_media = expand_path(main_config.storage.root_media)

        for yaml_file in watchfolders_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)

                if data:
                    # Expand environment variables and $root_media in all string values
                    def expand_value(value):
                        if isinstance(value, str):
                            # Expand $root_media placeholder
                            if "$root_media" in value:
                                value = value.replace("$root_media", str(root_media))
                            # Expand $HOME, ${HOME}, ~, $USER, etc.
                            value = os.path.expandvars(os.path.expanduser(value))
                            return value
                        elif isinstance(value, dict):
                            return {k: expand_value(v) for k, v in value.items()}
                        elif isinstance(value, list):
                            return [expand_value(item) for item in value]
                        return value

                    data = expand_value(data)
                    config = WatchfolderConfig(**data)
                    configs.append(config)
                    logger.info(f"Loaded watchfolder config: {yaml_file.name} -> {config.watchfolder_location}")
            except Exception as e:
                logger.error(f"Failed to load watchfolder config {yaml_file}: {e}")

        return configs

"""Configuration manager for loading and saving configuration."""

import logging
from pathlib import Path
from typing import Optional
import yaml

from .schema import Config

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages application configuration.

    Handles loading configuration from YAML files, saving configuration,
    and providing default configuration.
    """

    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "videotranscode" / "config.yaml"

    @staticmethod
    def get_default_config() -> Config:
        """
        Get default configuration.

        Returns:
            Config object with default values
        """
        return Config()

    @staticmethod
    def load_config(config_path: Optional[Path] = None) -> Config:
        """
        Load configuration from file.

        Args:
            config_path: Path to config file (default: ~/.config/videotranscode/config.yaml)

        Returns:
            Config object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if config_path is None:
            config_path = ConfigManager.DEFAULT_CONFIG_PATH

        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}")
            logger.info("Using default configuration")
            return ConfigManager.get_default_config()

        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}

            logger.info(f"Loaded configuration from: {config_path}")
            return Config(**config_data)

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")

    @staticmethod
    def save_config(config: Config, config_path: Optional[Path] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Config object to save
            config_path: Path to save to (default: ~/.config/videotranscode/config.yaml)
        """
        if config_path is None:
            config_path = ConfigManager.DEFAULT_CONFIG_PATH

        # Create config directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and save as YAML
        config_dict = config.model_dump(mode="python")

        # Convert Path objects to strings for YAML serialization
        def path_to_str(obj):
            if isinstance(obj, dict):
                return {k: path_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [path_to_str(item) for item in obj]
            elif isinstance(obj, Path):
                return str(obj)
            return obj

        config_dict = path_to_str(config_dict)

        with open(config_path, "w") as f:
            yaml.dump(
                config_dict,
                f,
                default_flow_style=False,
                sort_keys=False,
                indent=2,
            )

        logger.info(f"Saved configuration to: {config_path}")

    @staticmethod
    def create_default_config_file(config_path: Optional[Path] = None) -> Path:
        """
        Create a default configuration file with comments.

        Args:
            config_path: Path to create config file (default: ~/.config/videotranscode/config.yaml)

        Returns:
            Path to created config file
        """
        if config_path is None:
            config_path = ConfigManager.DEFAULT_CONFIG_PATH

        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with helpful comments
        config_content = """# Video Transcode Configuration

# FFmpeg settings
ffmpeg:
  binary_path: ffmpeg              # Path to FFmpeg binary
  hardware_accel: auto             # Hardware acceleration: auto|vaapi|nvenc|qsv|none

# Daemon settings
daemon:
  host: 127.0.0.1                  # API bind address (127.0.0.1 for local only)
  port: 8765                       # API port
  max_concurrent_jobs: 1           # Maximum concurrent encoding jobs
  pid_file: null                   # PID file path (null for none)

# Storage settings
storage:
  temp_dir: /tmp/videotranscode    # Temporary directory for encoding
  backup_originals: true           # Create backup of original files
  backup_dir: ./.originals         # Backup directory (relative or absolute)
  min_free_space_gb: 10            # Minimum free space required (GB)

# Logging settings
logging:
  level: INFO                      # Log level: DEBUG|INFO|WARNING|ERROR|CRITICAL
  dir: null                        # Log directory (null for no file logging)
  rotation: daily                  # Log rotation policy
  per_job_logs: true               # Create separate log file per job

# Hot folder monitoring (optional)
hot_folders: []
# Example hot folder:
# - path: /media/downloads
#   profile: x265-main
#   min_age_seconds: 300           # Wait 5 minutes before processing
#   recursive: true                # Monitor subdirectories
"""

        with open(config_path, "w") as f:
            f.write(config_content)

        logger.info(f"Created default configuration file: {config_path}")
        return config_path

    @staticmethod
    def validate_config(config: Config) -> list[str]:
        """
        Validate configuration and return list of issues.

        Args:
            config: Config object to validate

        Returns:
            List of validation issues (empty if valid)
        """
        issues = []

        # Check temp directory is writable
        if not config.storage.temp_dir.exists():
            try:
                config.storage.temp_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create temp directory: {e}")

        # Check port is reasonable
        if config.daemon.port < 1024 and config.daemon.port != 0:
            issues.append(
                f"Port {config.daemon.port} requires root privileges. "
                "Consider using port >= 1024"
            )

        # Check log directory if specified
        if config.logging.dir:
            if not config.logging.dir.exists():
                try:
                    config.logging.dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create log directory: {e}")

        # Check hot folder paths exist
        for hot_folder in config.hot_folders:
            if not hot_folder.path.exists():
                issues.append(f"Hot folder path does not exist: {hot_folder.path}")

        return issues

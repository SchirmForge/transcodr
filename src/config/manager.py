"""Configuration manager for loading and saving configuration."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional
import yaml

from .schema import Config

logger = logging.getLogger(__name__)


def expand_path(path: Path) -> Path:
    """
    Expand ~ and environment variables like $USER, $HOME in a path.

    Args:
        path: Path that may contain ~ or environment variables

    Returns:
        Expanded Path object
    """
    return Path(os.path.expandvars(os.path.expanduser(str(path))))


def expand_root_media_in_string(value: str, root_media_path: str) -> str:
    """
    Replace $root_media placeholder in a string with the actual path.

    Args:
        value: String that may contain $root_media placeholder
        root_media_path: Expanded root_media path to substitute

    Returns:
        String with placeholder expanded
    """
    if "$root_media" in value:
        # Remove trailing slash to avoid double slashes
        root_str = root_media_path.rstrip("/")
        return value.replace("$root_media", root_str)
    return value


def expand_root_media_in_config(config_data: dict) -> dict:
    """
    Expand $root_media placeholder in config values.

    Args:
        config_data: Raw config dictionary from YAML

    Returns:
        Config dictionary with $root_media placeholders expanded
    """
    # Get root_media value (with env var expansion)
    storage = config_data.get("storage", {})
    root_media_raw = storage.get("root_media", str(Path.home() / "Videos"))
    root_media_expanded = os.path.expandvars(os.path.expanduser(str(root_media_raw)))

    # Recursively expand $root_media in string values
    def expand_value(value):
        if isinstance(value, str):
            return expand_root_media_in_string(value, root_media_expanded)
        elif isinstance(value, dict):
            return {k: expand_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [expand_value(item) for item in value]
        return value

    return expand_value(config_data)


class ConfigManager:
    """
    Manages application configuration.

    Handles loading configuration from YAML files, saving configuration,
    and providing default configuration.
    """

    @staticmethod
    def get_default_config_path() -> Path:
        """Get default config file path. Supports TRANSCODR_CONFIG_DIR env var."""
        return ConfigManager.get_config_dir() / "config.yaml"

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
            config_path: Path to config file (default: ~/.config/transcodr/config.yaml)

        Returns:
            Config object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if config_path is None:
            config_path = ConfigManager.get_default_config_path()

        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}")
            logger.info("Using default configuration")
            return ConfigManager.get_default_config()

        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}

            # Expand $root_media placeholders in config values
            config_data = expand_root_media_in_config(config_data)

            logger.info(f"Loaded configuration from: {config_path}")
            return Config(**config_data)

        except yaml.YAMLError as e:
            # Extract line/column info if available
            if hasattr(e, 'problem_mark') and e.problem_mark:
                mark = e.problem_mark
                raise ValueError(
                    f"Invalid YAML syntax at line {mark.line + 1}, column {mark.column + 1}: {e.problem}"
                )
            raise ValueError(f"Invalid YAML in config file: {e}")
        except ImportError:
            raise
        except Exception as e:
            # Handle Pydantic validation errors with field-specific messages
            error_name = type(e).__name__
            if error_name == "ValidationError":
                # Parse Pydantic validation errors for better messages
                errors = []
                for error in e.errors():
                    loc = ".".join(str(x) for x in error["loc"])
                    msg = error["msg"]
                    errors.append(f"  - {loc}: {msg}")
                raise ValueError(f"Configuration validation failed:\n" + "\n".join(errors))
            raise ValueError(f"Failed to load config: {e}")

    @staticmethod
    def save_config(config: Config, config_path: Optional[Path] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Config object to save
            config_path: Path to save to (default: ~/.config/transcodr/config.yaml)
        """
        if config_path is None:
            config_path = ConfigManager.get_default_config_path()

        # Create config directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict using JSON mode so Path and Enum values become plain strings,
        # preventing yaml.dump from emitting Python-specific object tags.
        config_dict = config.model_dump(mode="json")

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
            config_path: Path to create config file (default: ~/.config/transcodr/config.yaml)

        Returns:
            Path to created config file
        """
        if config_path is None:
            config_path = ConfigManager.get_default_config_path()

        config_path.parent.mkdir(parents=True, exist_ok=True)

        template_path = Path(__file__).with_name("default-config.yml")
        try:
            config_content = template_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Default config template not found: {template_path}"
            ) from exc

        if not config_content.endswith("\n"):
            config_content += "\n"

        with open(config_path, "w") as f:
            f.write(config_content)

        logger.info(f"Created default configuration file: {config_path}")
        return config_path

    @staticmethod
    def validate_config(config: Config) -> tuple[list[str], list[str]]:
        """
        Validate configuration and return errors and warnings.

        Args:
            config: Config object to validate

        Returns:
            Tuple of (errors, warnings) where:
            - errors: Fatal issues that should prevent daemon startup
            - warnings: Non-fatal issues the user should be aware of
        """
        errors = []
        warnings = []

        # Check root_media folder exists (with env var expansion) - FATAL
        if config.storage.root_media:
            root_media = expand_path(config.storage.root_media)
            if not root_media.exists():
                errors.append(f"root_media folder does not exist: {root_media}")

        # Check temp directory is writable - FATAL if can't create
        if not config.storage.temp_dir.exists():
            try:
                config.storage.temp_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create temp directory: {e}")

        # Check log directory if specified - FATAL if can't create
        if config.logging.dir:
            if not config.logging.dir.exists():
                try:
                    config.logging.dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create log directory: {e}")

        # Check hot folder paths exist - FATAL
        for hot_folder in config.hot_folders:
            if not hot_folder.path.exists():
                errors.append(f"Hot folder path does not exist: {hot_folder.path}")

        # Check port is reasonable - WARNING only
        if config.daemon.port < 1024 and config.daemon.port != 0:
            warnings.append(
                f"Port {config.daemon.port} requires root privileges. "
                "Consider using port >= 1024"
            )

        return errors, warnings

    @staticmethod
    def get_config_dir() -> Path:
        """Get configuration directory path. Supports TRANSCODR_CONFIG_DIR env var."""
        env_dir = os.environ.get("TRANSCODR_CONFIG_DIR")
        if env_dir:
            return Path(env_dir)
        return Path.home() / ".config" / "transcodr"

    @staticmethod
    def get_profiles_dir() -> Path:
        """Get user profiles directory path."""
        return ConfigManager.get_config_dir() / "profiles"

    @staticmethod
    def get_builtin_profiles_dir() -> Path:
        """Get built-in profiles directory path."""
        # Assume built-in profiles are in src/profiles/builtin relative to this file
        return Path(__file__).parent.parent / "profiles" / "builtin"

    @staticmethod
    def get_watchfolders_config_dir() -> Path:
        """Get watchfolders configuration directory path."""
        return ConfigManager.get_config_dir() / "watchfolders"

    @staticmethod
    def ensure_config_structure() -> None:
        """
        Ensure configuration directory structure exists.

        Creates:
        - ~/.config/transcodr/
        - ~/.config/transcodr/profiles/
        - ~/.config/transcodr/watchfolders/
        """
        config_dir = ConfigManager.get_config_dir()
        profiles_dir = ConfigManager.get_profiles_dir()
        watchfolders_dir = ConfigManager.get_watchfolders_config_dir()

        # Create directories
        config_dir.mkdir(parents=True, exist_ok=True)
        profiles_dir.mkdir(parents=True, exist_ok=True)
        watchfolders_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Configuration directory: {config_dir}")
        logger.info(f"Profiles directory: {profiles_dir}")
        logger.info(f"Watchfolders config directory: {watchfolders_dir}")

    @staticmethod
    def copy_builtin_profiles(overwrite: bool = False) -> list[Path]:
        """
        Copy built-in profiles to user profiles directory.

        Args:
            overwrite: Overwrite existing user profiles

        Returns:
            List of copied profile paths
        """
        builtin_dir = ConfigManager.get_builtin_profiles_dir()
        user_dir = ConfigManager.get_profiles_dir()

        if not builtin_dir.exists():
            logger.warning(f"Built-in profiles directory not found: {builtin_dir}")
            return []

        # Ensure user profiles directory exists
        user_dir.mkdir(parents=True, exist_ok=True)

        copied_profiles = []

        # Copy each built-in profile
        for profile_file in builtin_dir.glob("*.yaml"):
            dest_file = user_dir / profile_file.name

            # Skip if exists and not overwriting
            if dest_file.exists() and not overwrite:
                logger.debug(f"Profile already exists, skipping: {profile_file.name}")
                continue

            # Copy profile
            shutil.copy2(profile_file, dest_file)
            copied_profiles.append(dest_file)
            logger.info(f"Copied built-in profile: {profile_file.name}")

        return copied_profiles

    @staticmethod
    def initialize(force_copy_profiles: bool = False) -> dict:
        """
        Initialize configuration directory and files.

        Creates directory structure, default config, and copies built-in profiles.

        Args:
            force_copy_profiles: Force overwrite of existing user profiles

        Returns:
            Dict with initialization info:
            {
                'config_dir': Path,
                'config_file': Path,
                'profiles_dir': Path,
                'config_created': bool,
                'profiles_copied': list[Path]
            }
        """
        config_dir = ConfigManager.get_config_dir()
        config_file = ConfigManager.get_default_config_path()
        profiles_dir = ConfigManager.get_profiles_dir()

        # Create directory structure
        ConfigManager.ensure_config_structure()

        # Create default config if it doesn't exist
        config_created = False
        if not config_file.exists():
            ConfigManager.create_default_config_file()
            config_created = True
            logger.info("Created default configuration file")
        else:
            logger.info(f"Configuration file already exists: {config_file}")

        # Copy built-in profiles
        profiles_copied = ConfigManager.copy_builtin_profiles(overwrite=force_copy_profiles)

        if profiles_copied:
            logger.info(f"Copied {len(profiles_copied)} built-in profiles")
        else:
            logger.info("No profiles copied (already exist or built-in profiles not found)")

        return {
            'config_dir': config_dir,
            'config_file': config_file,
            'profiles_dir': profiles_dir,
            'config_created': config_created,
            'profiles_copied': profiles_copied,
        }

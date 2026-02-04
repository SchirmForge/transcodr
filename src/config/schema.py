"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class FFmpegConfig(BaseModel):
    """FFmpeg configuration."""

    binary_path: str = Field(default="ffmpeg", description="Path to FFmpeg binary")
    hardware_accel: str = Field(
        default="auto",
        description="Hardware acceleration mode (auto|vaapi|nvenc|qsv|none)",
    )

    @field_validator("hardware_accel")
    @classmethod
    def validate_hardware_accel(cls, v: str) -> str:
        """Validate hardware acceleration mode."""
        valid_modes = ["auto", "vaapi", "nvenc", "qsv", "none"]
        if v not in valid_modes:
            raise ValueError(
                f"Invalid hardware_accel: {v}. Must be one of: {valid_modes}"
            )
        return v


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    host: str = Field(default="127.0.0.1", description="API bind address")
    port: int = Field(default=8765, description="API port", ge=1024, le=65535)
    max_concurrent_jobs: int = Field(
        default=1, description="Maximum concurrent encoding jobs", ge=1
    )
    pid_file: Optional[Path] = Field(
        default=None, description="PID file path (None for no PID file)"
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host address."""
        # Basic validation - could be more sophisticated
        if v not in ["127.0.0.1", "localhost", "0.0.0.0"]:
            # Allow any IP for flexibility, but warn in docs about security
            pass
        return v


class StorageConfig(BaseModel):
    """Storage configuration."""

    temp_dir: Path = Field(
        default=Path("/tmp/videotranscode"),
        description="Temporary directory for encoding",
    )
    backup_originals: bool = Field(
        default=True, description="Create backup of original files"
    )
    backup_dir: str = Field(
        default="./.originals",
        description="Backup directory (relative to source file or absolute)",
    )
    min_free_space_gb: int = Field(
        default=10,
        description="Minimum free space required (GB)",
        ge=1,
    )
    root_media: Path = Field(
        default_factory=lambda: Path.home() / "Videos",
        description="Base path for $root_media placeholder in command files. Supports ~ and $USER.",
    )
    profile_name_separator: str = Field(
        default="_",
        description="Separator between filename and profile name (for append_profile_name)",
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    dir: Optional[Path] = Field(
        default=None, description="Log directory (None for no file logging)"
    )
    rotation: str = Field(default="daily", description="Log rotation policy")
    per_job_logs: bool = Field(
        default=True, description="Create separate log file per job"
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of: {valid_levels}")
        return v_upper


class ValidationConfig(BaseModel):
    """Validation configuration."""

    duration_tolerance: float = Field(
        default=5.0,
        ge=0,
        description="Minimum absolute duration tolerance for extracted clips (seconds)",
    )


class HotFolderConfig(BaseModel):
    """Hot folder monitoring configuration."""

    path: Path = Field(description="Path to monitor")
    profile: str = Field(description="Profile to use for encoding")
    min_age_seconds: int = Field(
        default=300,
        description="Minimum file age before processing (seconds)",
        ge=0,
    )
    recursive: bool = Field(default=True, description="Monitor subdirectories")


class Config(BaseModel):
    """Main application configuration."""

    ffmpeg: FFmpegConfig = Field(default_factory=FFmpegConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    hot_folders: list[HotFolderConfig] = Field(
        default_factory=list, description="Hot folder configurations"
    )

    def get_config_dir(self) -> Path:
        """Get configuration directory."""
        return Path.home() / ".config" / "videotranscode"

    def get_profiles_dir(self) -> Path:
        """Get profiles directory."""
        return self.get_config_dir() / "profiles"

    def get_jobs_db_path(self) -> Path:
        """Get jobs database path."""
        return self.get_config_dir() / "jobs.db"

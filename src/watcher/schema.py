"""Watchfolder schema using Pydantic."""

from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class WatchfolderType(str, Enum):
    """Watchfolder type."""
    COMMAND = "command"    # Watch for EncodingRequest YAML command files
    MEDIA = "media"        # Watch for media files directly


class WatchfolderConfig(BaseModel):
    """
    Watchfolder configuration.

    Defines a watchfolder that monitors a location for command files or media files.
    Configuration files are stored in ~/.config/videotranscode/watchfolders/

    For type 'command': watches for YAML command files that specify encoding settings.
    For type 'media': watches for video/audio files and uses embedded encoding settings.
    """

    # Location and type
    watchfolder_location: Path = Field(description="Path to watch for files")
    watchfolder_type: WatchfolderType = Field(
        default=WatchfolderType.COMMAND,
        description="Type: 'command' (YAML commands) or 'media' (video files)"
    )

    # File detection settings
    scan_interval: float = Field(
        default=5.0,
        description="Scan interval in seconds",
        ge=1.0
    )
    stability_scans: int = Field(
        default=2,
        ge=1,
        description="Consecutive scans with stable file size before processing"
    )
    file_patterns: list[str] = Field(
        default_factory=lambda: ["*.mkv", "*.mp4", "*.avi", "*.mov", "*.webm", "*.flv", "*.wmv"],
        description="File patterns to match (for media type)"
    )
    recursive: bool = Field(
        default=False,
        description="Detect files in watchfolder subdirectories (multi-user mode)"
    )
    allow_folder_drop: bool = Field(
        default=False,
        description="Enable processing of dropped folders as complete units"
    )

    # Encoding settings (for media type only)
    profiles: list[str] = Field(
        default_factory=list,
        description="Encoding profiles (required for media type)"
    )
    destination: Optional[Path] = Field(
        default=None,
        description="Destination folder for encoded files (required for media type, must differ from watchfolder_location)"
    )
    temp_folder: Optional[Path] = Field(
        default=None,
        description="Temporary folder for source copy during encoding (default: system temp)"
    )
    disable_temp_copy: bool = Field(
        default=False,
        description="If true, encode directly from source without copying to temp first"
    )
    keep_processed_files: bool = Field(
        default=True,
        description="For media type: keep source files (rename to .processed) or delete after encoding"
    )
    hardware_accel: Optional[str] = Field(
        default=None,
        description="Override hardware acceleration"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Job priority (1=lowest, 10=highest)"
    )
    preserve_folder_structure: bool = Field(
        default=True,
        description="Preserve folder structure from source to destination"
    )
    append_profile_name: bool = Field(
        default=False,
        description="Always add profile name to output filename (useful for multi-profile extracts)"
    )

    @model_validator(mode='after')
    def validate_folder_options(self) -> 'WatchfolderConfig':
        """Ensure allow_folder_drop and recursive are mutually exclusive."""
        if self.allow_folder_drop and self.recursive:
            raise ValueError(
                "allow_folder_drop and recursive are mutually exclusive. "
                "Use allow_folder_drop for folder processing, or recursive for multi-user subdirectories."
            )
        return self

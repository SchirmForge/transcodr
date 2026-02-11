"""API data models for encoding requests and job status."""

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(str, Enum):
    """Job status states."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # Graceful shutdown while running


class OutputMode(str, Enum):
    """Output handling mode."""
    REPLACE = "replace"           # Replace original file in-place
    DESTINATION = "destination"   # Output to destination folder


# =============================================================================
# Watchfolder Context (for job file handling)
# =============================================================================

class WatchfolderContext(BaseModel):
    """
    Context for watchfolder job file handling.

    When present, JobRunner handles:
    - Optional temp copy (if not disable_temp_copy)
    - Final rename to .processed/.failed (last profile) or delete

    Note: No .processing rename during execution - all profiles read
    from the original file (or temp copy).
    """
    file_hash: str = Field(
        description="File fingerprint for tracking and duplicate detection"
    )
    keep_processed_files: bool = Field(
        default=True,
        description="Keep .processed files after encoding, or delete source"
    )
    disable_temp_copy: bool = Field(
        default=False,
        description="Encode directly from source without creating temp copy"
    )
    temp_folder: Optional[str] = Field(
        default=None,
        description="Override temp folder location for source copy"
    )


# =============================================================================
# Encoding Request Models (for API and watch folder command files)
# =============================================================================

class EncodingRequest(BaseModel):
    """
    Encoding request - can be submitted via API or dropped as YAML in watch folder.

    Examples:

    Minimal (single profile, replace original):
    ```yaml
    profile: x265-balanced
    source: /media/videos/movie.mkv
    ```

    Multiple profiles (TV + Mobile versions):
    ```yaml
    profiles:
      - x265-balanced    # First profile replaces original (or primary output)
      - x265-mobile      # Creates movie_x265-mobile.mkv
      - x265-tv          # Creates movie_x265-tv.mkv
    source: /media/videos/movie.mkv
    output_mode: replace
    ```

    With destination folder:
    ```yaml
    profiles:
      - x265-balanced
      - x265-mobile
    source: /media/downloads/
    output_mode: destination
    destination: /media/encoded/
    preserve_structure: true
    recursive: true
    ```

    Full options:
    ```yaml
    profiles:
      - x265-balanced
      - x265-mobile
    source: /media/videos/
    output_mode: replace
    backup: true
    backup_dir: .originals
    recursive: true
    file_patterns:
      - "*.mkv"
      - "*.mp4"
    hardware_accel: vaapi
    priority: 5
    ```
    """

    # Profile(s) - can be single string or list
    # If single profile specified via 'profile' field, it's converted to list
    profiles: list[str] = Field(
        default_factory=list,
        description="Encoding profile(s) - first replaces original, others add profile name suffix"
    )

    # Source path (required)
    source: str = Field(
        description="Source file or folder path"
    )

    # Output handling
    output_mode: OutputMode = Field(
        default=OutputMode.REPLACE,
        description="Output mode: 'replace' (in-place) or 'destination' (separate folder)"
    )
    destination: Optional[str] = Field(
        default=None,
        description="Destination folder (required if output_mode is 'destination' and use_profile_destination is false)"
    )
    use_profile_destination: bool = Field(
        default=False,
        description="Use each profile's destination field instead of a single destination folder"
    )
    preserve_structure: bool = Field(
        default=True,
        description="Preserve folder structure from source to destination"
    )

    # Backup options (only for replace mode)
    backup: bool = Field(
        default=True,
        description="Create backup of original files before replacing"
    )
    backup_dir: str = Field(
        default=".originals",
        description="Backup directory (relative to source or absolute)"
    )

    # Processing options
    recursive: bool = Field(
        default=True,
        description="Process subdirectories recursively"
    )
    file_patterns: list[str] = Field(
        default_factory=lambda: ["*.mkv", "*.mp4", "*.avi", "*.mov", "*.wmv", "*.flv", "*.webm", "*.m2ts", "*.ts"],
        description="File patterns to match (glob patterns)"
    )

    # Performance options
    hardware_accel: Optional[str] = Field(
        default=None,
        description="Override hardware acceleration (auto|vaapi|nvenc|qsv|none)"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Job priority (1=lowest, 10=highest)"
    )

    # Output organization options
    create_profile_folders: bool = Field(
        default=False,
        description="Create subfolder per profile in destination (e.g., dest/x265-balanced/)"
    )
    append_profile_name: bool = Field(
        default=False,
        description="Always add profile name to output filename"
    )
    delete_source: bool = Field(
        default=False,
        description="Delete source file after successful encoding"
    )
    use_temp_folder: bool = Field(
        default=True,
        description="Encode to temp folder first, then move to output (safer but needs temp space)"
    )
    copy_source_to_temp: bool = Field(
        default=True,
        description="Copy source file to temp before encoding (for multi-profile jobs on network storage)"
    )

    # Concurrency control
    max_concurrent_jobs: Optional[int] = Field(
        default=None,
        ge=1,
        description="Max concurrent jobs for this request (None=use global limit)"
    )

    # Watchfolder context (for MediaFileWatcher submissions)
    watchfolder_context: Optional[WatchfolderContext] = Field(
        default=None,
        description="Context for watchfolder jobs - when present, JobRunner handles all file operations"
    )

    @model_validator(mode='before')
    @classmethod
    def normalize_profile_field(cls, data):
        """Convert single 'profile' field to 'profiles' list."""
        if isinstance(data, dict):
            # Handle single profile -> profiles list
            if 'profile' in data and 'profiles' not in data:
                profile = data.pop('profile')
                if isinstance(profile, str):
                    data['profiles'] = [profile]
                elif isinstance(profile, list):
                    data['profiles'] = profile
            # Handle profiles as single string
            elif 'profiles' in data and isinstance(data['profiles'], str):
                data['profiles'] = [data['profiles']]
        return data

    @field_validator('output_mode', mode='before')
    @classmethod
    def normalize_output_mode(cls, v):
        """Allow 'yes'/'no' for replace as shorthand."""
        if isinstance(v, str):
            v = v.lower()
            if v in ('yes', 'true', 'replace'):
                return OutputMode.REPLACE
            elif v in ('no', 'false', 'destination'):
                return OutputMode.DESTINATION
        return v

    @field_validator('backup', mode='before')
    @classmethod
    def normalize_backup(cls, v):
        """Allow 'yes'/'no' strings."""
        if isinstance(v, str):
            return v.lower() in ('yes', 'true', '1')
        return v

    @field_validator('recursive', mode='before')
    @classmethod
    def normalize_recursive(cls, v):
        """Allow 'yes'/'no' strings."""
        if isinstance(v, str):
            return v.lower() in ('yes', 'true', '1')
        return v

    @field_validator('preserve_structure', mode='before')
    @classmethod
    def normalize_preserve_structure(cls, v):
        """Allow 'yes'/'no' strings."""
        if isinstance(v, str):
            return v.lower() in ('yes', 'true', '1')
        return v

    @model_validator(mode='after')
    def validate_destination_profile(self):
        """Validate use_profile_destination options."""
        if self.use_profile_destination and self.create_profile_folders:
            raise ValueError(
                "Cannot use use_profile_destination with create_profile_folders=true. "
                "Use one or the other."
            )
        if self.use_profile_destination and self.destination:
            raise ValueError(
                "use_profile_destination and destination are mutually exclusive. "
                "Use use_profile_destination to output to each profile's destination, "
                "or specify a single destination folder."
            )
        return self

    def validate_request(self) -> list[str]:
        """Validate the request and return list of issues."""
        issues = []

        # Check at least one profile specified
        if not self.profiles:
            issues.append("At least one profile is required")

        # Check source exists
        source_path = Path(self.source)
        if not source_path.exists():
            issues.append(f"Source path does not exist: {self.source}")

        # Check destination is provided when needed (unless using profile destinations)
        if self.output_mode == OutputMode.DESTINATION and not self.destination and not self.use_profile_destination:
            issues.append("Destination is required when output_mode is 'destination'")

        # Check destination is writable
        if self.destination:
            dest_path = Path(self.destination)
            if dest_path.exists() and not dest_path.is_dir():
                issues.append(f"Destination must be a directory: {self.destination}")

        return issues

    def get_output_filename(
        self,
        source_file: Path,
        profile_name: str,
        profile_index: int,
        container: Optional[str] = None,
        separator: str = "_",
    ) -> str:
        """
        Generate output filename based on profile position and settings.

        Args:
            source_file: Source file path
            profile_name: Profile name being used
            profile_index: Index of profile in profiles list (0-based)
            container: Override output container format
            separator: Separator between filename and profile name (default: "_")

        Returns:
            Output filename
        """
        stem = source_file.stem
        suffix = source_file.suffix

        # Strip processing markers to get real extension
        # e.g., "video.mkv.processing" -> stem="video.mkv", suffix=".processing"
        # We want: stem="video", suffix=".mkv"
        processing_markers = [".processing", ".processed", ".failed"]
        if suffix in processing_markers:
            real_stem = Path(stem)
            suffix = real_stem.suffix or ".mkv"  # Fallback to .mkv
            stem = real_stem.stem

        # Override extension if container is specified
        if container:
            suffix = f".{container.lstrip('.')}"

        # If append_profile_name is enabled, always add profile name
        if self.append_profile_name:
            return f"{stem}{separator}{profile_name}{suffix}"

        # Default behavior: first profile keeps original name, others get suffix
        if profile_index == 0:
            return f"{stem}{suffix}"
        else:
            return f"{stem}{separator}{profile_name}{suffix}"

    @staticmethod
    def expand_root_media(path: str, root_media: Path) -> str:
        """
        Replace $root_media placeholder with actual path.

        Args:
            path: Path string that may contain $root_media placeholder
            root_media: Base path to substitute (supports ~ and $USER)

        Returns:
            Path with placeholder expanded
        """
        if "$root_media" in path:
            # Expand environment variables and ~ in root_media
            expanded = os.path.expandvars(os.path.expanduser(str(root_media)))
            # Normalize: remove trailing slash to avoid double slashes
            root_str = expanded.rstrip("/")
            return path.replace("$root_media", root_str)
        return path

    def expand_paths(self, root_media: Path) -> "EncodingRequest":
        """
        Return a copy of this request with $root_media placeholders expanded.

        Args:
            root_media: Base path to substitute for $root_media placeholder

        Returns:
            New EncodingRequest with expanded paths
        """
        data = self.model_dump()
        if self.source:
            data["source"] = self.expand_root_media(self.source, root_media)
        if self.destination:
            data["destination"] = self.expand_root_media(self.destination, root_media)
        return EncodingRequest(**data)


def process_encoding_request(
    request: EncodingRequest,
    root_media: Path
) -> tuple[EncodingRequest, list[str]]:
    """
    Process an encoding request: expand placeholders and validate.

    This helper ensures consistent processing for both API submissions
    and command file watcher.

    Args:
        request: The encoding request to process
        root_media: Base path for $root_media expansion

    Returns:
        Tuple of (processed_request, validation_issues)
    """
    # Expand $root_media placeholders
    request = request.expand_paths(root_media)

    # Validate
    issues = request.validate_request()

    return request, issues


# =============================================================================
# Watch Folder Models
# =============================================================================

class WatchFolderInfo(BaseModel):
    """Information about a registered watch folder."""

    id: str = Field(description="Unique watch folder identifier")
    path: str = Field(description="Watch folder path")
    profiles: list[str] = Field(description="Profiles to use for encoding")
    output_mode: OutputMode = Field(description="Output handling mode")
    destination: Optional[str] = Field(default=None, description="Destination folder")
    preserve_structure: bool = Field(default=True)
    recursive: bool = Field(default=True)
    file_patterns: list[str] = Field(description="File patterns to match")
    hardware_accel: Optional[str] = Field(default=None)
    priority: int = Field(default=5)

    # Status
    active: bool = Field(default=True, description="Watch folder is active")
    files_processed: int = Field(default=0, description="Total files processed")
    last_activity: Optional[datetime] = Field(default=None, description="Last file processed time")


# =============================================================================
# Job Models (for tracking and status)
# =============================================================================

class JobInfo(BaseModel):
    """Job information returned by API."""

    id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current job status")
    profile: str = Field(description="Encoding profile used")
    source_path: str = Field(description="Source file path")
    output_path: Optional[str] = Field(default=None, description="Output file path")

    # Multi-profile info
    profile_index: int = Field(default=0, description="Profile index (0=primary)")
    total_profiles: int = Field(default=1, description="Total profiles for this source")
    parent_job_id: Optional[str] = Field(default=None, description="Parent job ID if multi-profile")

    # Progress
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage")
    fps: float = Field(default=0.0, description="Current encoding speed (fps)")
    frames_processed: int = Field(default=0, description="Frames processed")
    frames_total: int = Field(default=0, description="Total frames")

    # Timing
    created_at: datetime = Field(description="Job creation time")
    started_at: Optional[datetime] = Field(default=None, description="Job start time")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion time")

    # Size info
    source_size_bytes: int = Field(default=0, description="Source file size")
    output_size_bytes: int = Field(default=0, description="Output file size")

    # Error info
    error_message: Optional[str] = Field(default=None, description="Error message if failed")

    # Encoding settings (populated from profile when returning job info)
    hardware_accel: Optional[str] = Field(default=None, description="Hardware acceleration used")
    video_codec: Optional[str] = Field(default=None, description="Video codec")
    audio_codec: Optional[str] = Field(default=None, description="Audio codec or 'copy'")
    subtitle_mode: Optional[str] = Field(default=None, description="Subtitle handling")
    container: Optional[str] = Field(default=None, description="Output container format")
    use_temp_folder: bool = Field(default=True, description="Using temp folder for encoding")

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.source_size_bytes > 0 and self.output_size_bytes > 0:
            return self.output_size_bytes / self.source_size_bytes
        return 0.0

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class QueueInfo(BaseModel):
    """Queue status information."""

    total_jobs: int = Field(description="Total jobs in queue")
    pending_jobs: int = Field(description="Jobs waiting to start")
    running_jobs: int = Field(description="Jobs currently running")
    completed_jobs: int = Field(description="Completed jobs")
    failed_jobs: int = Field(description="Failed jobs")

    max_concurrent: int = Field(description="Maximum concurrent jobs")
    current_concurrent: int = Field(description="Current concurrent jobs")


class DaemonStatus(BaseModel):
    """Daemon status information."""

    running: bool = Field(description="Daemon is running")
    version: str = Field(description="Daemon version")
    uptime_seconds: float = Field(description="Daemon uptime in seconds")

    queue: QueueInfo = Field(description="Queue status")
    watch_folders: list[WatchFolderInfo] = Field(description="Active watch folders")

    hardware: dict = Field(description="Hardware capabilities")
    config_path: str = Field(description="Configuration file path")


# =============================================================================
# API Request/Response Models
# =============================================================================

class SubmitJobRequest(BaseModel):
    """Request to submit a new encoding job or register watch folder."""
    request: EncodingRequest


class SubmitJobResponse(BaseModel):
    """Response after submitting a job."""
    success: bool
    job_ids: list[str] = Field(
        default_factory=list,
        description="Created job IDs (may be multiple for folders/profiles)"
    )
    message: str


class JobListResponse(BaseModel):
    """Response with list of jobs."""
    jobs: list[JobInfo]
    total: int


class CancelJobResponse(BaseModel):
    """Response after cancelling a job."""
    success: bool
    message: str


# =============================================================================
# File Browser Models
# =============================================================================

class BrowseEntry(BaseModel):
    """A file or directory entry in a browse response."""
    name: str
    type: Literal["directory", "file"]
    path: str
    size: Optional[int] = None


class BrowseResponse(BaseModel):
    """Response from the file browser endpoint."""
    current_path: str
    parent_path: Optional[str]
    root_media: str
    entries: list[BrowseEntry]

"""Job model for encoding tasks."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class JobState(str, Enum):
    """Job state enumeration."""

    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    VALIDATING_OUTPUT = "validating_output"
    REPLACING = "replacing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # Graceful shutdown while running


class OutputMode(str, Enum):
    """Output handling mode."""

    REPLACE = "replace"  # Replace original file in-place
    DESTINATION = "destination"  # Output to destination folder


class Job(BaseModel):
    """Encoding job."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: JobState = Field(default=JobState.PENDING)

    # Input/output
    source_path: Path
    output_path: Optional[Path] = None  # Calculated during execution
    temp_path: Optional[Path] = None  # Temporary output path
    output_mode: OutputMode = Field(default=OutputMode.REPLACE)
    delete_source: bool = Field(default=False)
    use_temp_folder: bool = Field(default=True)
    enable_temp_copy: bool = Field(default=False)
    auto_embed_subtitles: bool = Field(default=True)
    subtitles_languages: Optional[list[str]] = None  # None means "all"
    subtitle_fallback_mode: str = Field(default="carry")

    # Profile
    profile_name: str
    hardware_accel: Optional[str] = None  # None for auto-detect

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Progress tracking
    progress_percent: float = 0.0
    frames_processed: int = 0
    frames_total: Optional[int] = None
    current_fps: float = 0.0
    eta_seconds: Optional[int] = None
    eta_quality: Optional[str] = None

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0

    # Warning tracking
    warning_message: Optional[str] = None

    # Metadata
    source_size_bytes: int = 0
    output_size_bytes: int = 0
    source_codec: Optional[str] = None
    output_codec: Optional[str] = None

    def update_progress(self, frame: int, fps: float, total_frames: Optional[int] = None):
        """
        Update job progress.

        Args:
            frame: Current frame number
            fps: Current FPS
            total_frames: Total frames (if known)
        """
        self.frames_processed = frame
        self.current_fps = fps

        if total_frames:
            self.frames_total = total_frames
            self.progress_percent = (frame / total_frames) * 100

            # Estimate ETA
            if fps > 0:
                remaining_frames = total_frames - frame
                self.eta_seconds = int(remaining_frames / fps)

    def mark_failed(self, error: str):
        """Mark job as failed with error message."""
        self.state = JobState.FAILED
        self.error_message = error
        self.completed_at = datetime.now()

    def mark_completed(self):
        """Mark job as completed."""
        self.state = JobState.COMPLETED
        self.progress_percent = 100.0
        self.completed_at = datetime.now()

    def add_warning(self, message: str):
        """Append a warning message to the job."""
        if self.warning_message:
            self.warning_message += "\n" + message
        else:
            self.warning_message = message

    def __repr__(self):
        return (
            f"Job(id={self.id[:8]}, state={self.state.value}, "
            f"source={self.source_path.name}, profile={self.profile_name})"
        )

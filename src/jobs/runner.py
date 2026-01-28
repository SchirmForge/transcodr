"""Job runner for executing encoding tasks."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Callable

from src.core.ffmpeg import FFmpegWrapper, FFmpegProgress
from src.core.probe import ProbeHelper
from src.core.replace import SafeReplacer
from src.core.hardware import HardwareCapabilities
from src.core.errors import ValidationError, EncodingError, ReplacementError
from src.profiles.manager import ProfileManager
from .model import Job, JobState

logger = logging.getLogger(__name__)


class JobRunner:
    """
    Executes encoding jobs.

    Handles job validation, encoding, output validation, and file replacement.
    """

    def __init__(
        self,
        ffmpeg: Optional[FFmpegWrapper] = None,
        profile_manager: Optional[ProfileManager] = None,
        temp_dir: Optional[Path] = None,
        backup_originals: bool = True,
    ):
        """
        Initialize job runner.

        Args:
            ffmpeg: FFmpeg wrapper (default: auto-create)
            profile_manager: Profile manager (default: auto-create)
            temp_dir: Temporary directory for encoding (default: system temp)
            backup_originals: Create backups of original files
        """
        self.ffmpeg = ffmpeg or FFmpegWrapper()
        self.profile_manager = profile_manager or ProfileManager()
        self.probe = ProbeHelper()
        self.replacer = SafeReplacer(backup_originals=backup_originals)

        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "videotranscode"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.hardware_caps = HardwareCapabilities()

    def execute(
        self,
        job: Job,
        progress_callback: Optional[Callable[[Job], None]] = None,
    ) -> Job:
        """
        Execute encoding job.

        Args:
            job: Job to execute
            progress_callback: Optional callback for progress updates

        Returns:
            Updated job object

        Raises:
            ValidationError: If validation fails
            EncodingError: If encoding fails
            ReplacementError: If file replacement fails
        """
        logger.info(f"Starting job execution: {job}")

        try:
            # Pre-flight validation
            job.state = JobState.VALIDATING
            if progress_callback:
                progress_callback(job)
            self._validate_job(job)

            # Setup paths
            self._setup_paths(job)

            # Determine hardware acceleration
            if job.hardware_accel is None:
                job.hardware_accel = self.hardware_caps.get_recommended_accel()
                logger.info(f"Auto-selected hardware acceleration: {job.hardware_accel or 'none'}")

            # Load profile
            profile = self.profile_manager.load_profile(job.profile_name)

            # Build FFmpeg arguments
            ffmpeg_args = profile.to_ffmpeg_args(
                str(job.source_path),
                str(job.temp_path),
                hardware_accel=job.hardware_accel,
            )

            # Log FFmpeg command for debugging
            logger.info(f"FFmpeg command: ffmpeg {' '.join(ffmpeg_args)}")

            # Estimate total frames for progress tracking
            job.frames_total = self.probe.estimate_frame_count(job.source_path)

            # Start encoding
            job.state = JobState.RUNNING
            if progress_callback:
                progress_callback(job)

            logger.info(f"Starting encoding: {job.source_path.name} → {profile.name}")

            def on_progress(progress: FFmpegProgress):
                """Handle FFmpeg progress updates."""
                job.update_progress(
                    frame=progress.frame,
                    fps=progress.fps,
                    total_frames=job.frames_total,
                )
                if progress_callback:
                    progress_callback(job)

            # Run FFmpeg
            self.ffmpeg.run(ffmpeg_args, progress_callback=on_progress)

            # Validate output
            job.state = JobState.VALIDATING_OUTPUT
            if progress_callback:
                progress_callback(job)
            self._validate_output(job)

            # Replace original file
            job.state = JobState.REPLACING
            if progress_callback:
                progress_callback(job)
            self._replace_file(job)

            # Mark completed
            job.mark_completed()
            if progress_callback:
                progress_callback(job)

            logger.info(f"Job completed successfully: {job.id}")
            return job

        except Exception as e:
            logger.error(f"Job failed: {e}", exc_info=True)
            job.mark_failed(str(e))
            if progress_callback:
                progress_callback(job)

            # Cleanup temp file
            if job.temp_path and job.temp_path.exists():
                try:
                    job.temp_path.unlink()
                    logger.debug(f"Cleaned up temp file: {job.temp_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

            raise

    def _validate_job(self, job: Job):
        """
        Pre-flight validation.

        Checks:
        - Source file exists and is readable
        - Source file is valid video
        - Sufficient disk space
        - Profile exists and is valid
        """
        logger.debug("Running pre-flight validation")

        # Check source file
        if not job.source_path.exists():
            raise ValidationError(f"Source file not found: {job.source_path}")

        if not job.source_path.is_file():
            raise ValidationError(f"Source path is not a file: {job.source_path}")

        # Validate source is a video
        if not self.probe.validate_file(job.source_path):
            raise ValidationError(f"Source file is not a valid video: {job.source_path}")

        # Get source metadata
        try:
            info = self.probe.get_info(job.source_path)
            job.source_size_bytes = job.source_path.stat().st_size
            video_stream = info.get_primary_video_stream()
            if video_stream:
                job.source_codec = video_stream.codec_name
        except Exception as e:
            logger.warning(f"Failed to get source metadata: {e}")

        # Check disk space (need ~2x source size + 10GB safety margin)
        source_size = job.source_path.stat().st_size
        required_space = source_size * 2 + (10 * 1024**3)  # 2x + 10GB

        disk_usage = shutil.disk_usage(self.temp_dir)
        if disk_usage.free < required_space:
            raise ValidationError(
                f"Insufficient disk space: need {required_space / 1024**3:.1f}GB, "
                f"have {disk_usage.free / 1024**3:.1f}GB"
            )

        # Check profile exists
        if not self.profile_manager.profile_exists(job.profile_name):
            raise ValidationError(f"Profile not found: {job.profile_name}")

        logger.debug("Pre-flight validation passed")

    def _setup_paths(self, job: Job):
        """Setup output and temp paths for job."""
        # Determine output path (same as source if not specified)
        if job.output_path is None:
            job.output_path = job.source_path

        # Create temp path
        temp_filename = f"{job.id}_{job.source_path.stem}_encoded{job.source_path.suffix}"
        job.temp_path = self.temp_dir / temp_filename

        logger.debug(f"Temp path: {job.temp_path}")

    def _validate_output(self, job: Job):
        """Validate encoded output file."""
        logger.debug("Validating encoded output")

        if not job.temp_path.exists():
            raise ValidationError("Encoded file not found")

        if not self.probe.validate_file(job.temp_path):
            raise ValidationError("Encoded file is not a valid video")

        # Get output metadata
        try:
            job.output_size_bytes = job.temp_path.stat().st_size
            info = self.probe.get_info(job.temp_path)
            video_stream = info.get_primary_video_stream()
            if video_stream:
                job.output_codec = video_stream.codec_name

            logger.info(
                f"Output: {job.output_codec}, "
                f"{job.output_size_bytes / 1024**2:.1f}MB "
                f"({job.output_size_bytes / job.source_size_bytes * 100:.1f}% of original)"
            )
        except Exception as e:
            logger.warning(f"Failed to get output metadata: {e}")

        logger.debug("Output validation passed")

    def _replace_file(self, job: Job):
        """Replace original file with encoded version."""
        logger.debug("Replacing original file")

        self.replacer.replace(job.source_path, job.temp_path)

        logger.debug("File replacement completed")

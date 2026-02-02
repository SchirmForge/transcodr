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
from .model import Job, JobState, OutputMode

logger = logging.getLogger(__name__)


class JobRunner:
    """
    Executes encoding jobs.

    Handles job validation, encoding, output validation, and file replacement.
    Supports multi-profile encoding by using temp copies of the source file.
    """

    # Class-level tracking of temp source copies for multi-profile jobs
    _temp_source_copies: dict[str, tuple[Path, int]] = {}  # parent_id -> (temp_path, ref_count)
    _temp_source_lock = None  # Initialized lazily

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

        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "videotranscode"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.replacer = SafeReplacer(
            backup_originals=backup_originals,
            temp_dir=self.temp_dir,
        )

        self.hardware_caps = HardwareCapabilities()

        # Initialize thread lock for temp source tracking
        import threading
        if JobRunner._temp_source_lock is None:
            JobRunner._temp_source_lock = threading.Lock()

    def execute(
        self,
        job: Job,
        progress_callback: Optional[Callable[[Job], None]] = None,
        profile_index: int = 0,
        total_profiles: int = 1,
        parent_job_id: Optional[str] = None,
    ) -> Job:
        """
        Execute encoding job.

        Args:
            job: Job to execute
            progress_callback: Optional callback for progress updates
            profile_index: Index of this profile in multi-profile encoding (0-based)
            total_profiles: Total number of profiles for this source
            parent_job_id: Parent job ID for multi-profile grouping

        Returns:
            Updated job object

        Raises:
            ValidationError: If validation fails
            EncodingError: If encoding fails
            ReplacementError: If file replacement fails
        """
        is_multi_profile = total_profiles > 1
        temp_source_path: Optional[Path] = None
        logger.info(f"Starting job execution: {job} (profile {profile_index + 1}/{total_profiles})")

        try:
            # Pre-flight validation
            job.state = JobState.VALIDATING
            if progress_callback:
                progress_callback(job)
            self._validate_job(job)

            # Setup paths
            self._setup_paths(job)

            # For multi-profile encoding, get or create temp source copy
            source_for_encoding = job.source_path
            if is_multi_profile and parent_job_id:
                temp_source_path = self._get_or_create_temp_source(
                    parent_job_id,
                    job.source_path,
                    total_profiles,
                )
                source_for_encoding = temp_source_path
                logger.info(f"Using temp source copy: {temp_source_path}")

            # Determine hardware acceleration
            if job.hardware_accel is None:
                job.hardware_accel = self.hardware_caps.get_recommended_accel()
                logger.info(f"Auto-selected hardware acceleration: {job.hardware_accel or 'none'}")

            # Load profile
            profile = self.profile_manager.load_profile(job.profile_name)

            # Build FFmpeg arguments (use temp source for multi-profile)
            ffmpeg_args = profile.to_ffmpeg_args(
                str(source_for_encoding),
                str(job.temp_path),
                hardware_accel=job.hardware_accel,
            )

            # Log FFmpeg command for debugging
            logger.info(f"FFmpeg command: ffmpeg {' '.join(ffmpeg_args)}")

            # Estimate total frames for progress tracking
            job.frames_total = self.probe.estimate_frame_count(source_for_encoding)

            # Start encoding
            job.state = JobState.RUNNING
            if progress_callback:
                progress_callback(job)

            logger.info(f"Starting encoding: {source_for_encoding.name} → {profile.name}")

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
            self._validate_output(job, source_for_encoding)

            # Handle output placement
            job.state = JobState.REPLACING
            if progress_callback:
                progress_callback(job)

            if job.output_mode == OutputMode.DESTINATION:
                # Destination mode: always copy to output path, never replace
                self._copy_to_output(job)
            elif profile_index == 0:
                # Replace mode, first profile: replace original file
                self._replace_file(job)
            else:
                # Replace mode, subsequent profiles: copy to output path (with profile suffix)
                self._copy_to_output(job)

            # Delete source if requested (only for destination mode, as replace mode already replaces)
            if job.delete_source and job.output_mode == OutputMode.DESTINATION:
                try:
                    job.source_path.unlink()
                    logger.info(f"Deleted source file: {job.source_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete source file: {e}")

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

        finally:
            # Release temp source copy reference (cleanup when last profile finishes)
            if is_multi_profile and parent_job_id:
                self._release_temp_source(parent_job_id)

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

        # Create temp path - handle .processing/.processed/.failed markers
        source_name = job.source_path.name
        source_suffix = job.source_path.suffix

        # Strip processing markers to get real extension
        processing_markers = [".processing", ".processed", ".failed"]
        if source_suffix in processing_markers:
            # Real extension is in the stem (e.g., "video.mkv.processing" -> stem="video.mkv")
            real_stem = Path(job.source_path.stem)
            source_suffix = real_stem.suffix or ".mkv"  # Fallback to .mkv
            source_name = real_stem.stem

        temp_filename = f"{job.id}_{source_name}_encoded{source_suffix}"
        job.temp_path = self.temp_dir / temp_filename

        logger.debug(f"Temp path: {job.temp_path}")

    def _validate_output(self, job: Job, source_for_comparison: Optional[Path] = None):
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

        # Compare durations (use the actual source that was encoded)
        compare_source = source_for_comparison or job.source_path
        if not self.probe.compare_durations(compare_source, job.temp_path, tolerance_percent=1.0):
            orig_duration = self.probe.get_duration(compare_source)
            enc_duration = self.probe.get_duration(job.temp_path)
            diff_percent = abs(orig_duration - enc_duration) / orig_duration * 100 if orig_duration > 0 else 100
            raise ValidationError(
                f"Duration mismatch: source={orig_duration:.1f}s, "
                f"encoded={enc_duration:.1f}s (diff={diff_percent:.2f}%)"
            )

        logger.debug("Output validation passed")

    def _replace_file(self, job: Job):
        """Replace original file with encoded version."""
        logger.debug("Replacing original file")

        self.replacer.replace(job.source_path, job.temp_path)

        logger.debug("File replacement completed")

    def _copy_to_output(self, job: Job):
        """Copy encoded file to output path (for additional profiles)."""
        logger.debug(f"Copying encoded file to output: {job.output_path}")

        if job.output_path is None:
            raise ValidationError("Output path not set for additional profile")

        # Ensure output directory exists
        job.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy the encoded file to the output location
        shutil.copy2(job.temp_path, job.output_path)
        logger.info(f"Copied encoded file to: {job.output_path}")

        # Cleanup temp file
        try:
            job.temp_path.unlink()
            logger.debug(f"Cleaned up temp file: {job.temp_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")

    def _get_or_create_temp_source(
        self,
        parent_job_id: str,
        source_path: Path,
        total_profiles: int,
    ) -> Path:
        """
        Get or create a temp copy of the source file for multi-profile encoding.

        This ensures all profiles encode from the same original source,
        even after the first profile replaces the original file.

        Args:
            parent_job_id: Parent job ID for grouping
            source_path: Original source file path
            total_profiles: Total number of profiles (used for ref counting)

        Returns:
            Path to temp source copy
        """
        with JobRunner._temp_source_lock:
            if parent_job_id in JobRunner._temp_source_copies:
                # Already exists, increment ref count
                temp_path, ref_count = JobRunner._temp_source_copies[parent_job_id]
                JobRunner._temp_source_copies[parent_job_id] = (temp_path, ref_count + 1)
                logger.debug(f"Reusing temp source copy: {temp_path} (refs: {ref_count + 1})")
                return temp_path
            else:
                # Create new temp copy
                temp_path = self.replacer.copy_source_to_temp(source_path)
                JobRunner._temp_source_copies[parent_job_id] = (temp_path, 1)
                logger.info(f"Created temp source copy: {temp_path}")
                return temp_path

    def _release_temp_source(self, parent_job_id: str):
        """
        Release reference to temp source copy.

        When the ref count reaches zero, the temp copy is deleted.

        Args:
            parent_job_id: Parent job ID
        """
        with JobRunner._temp_source_lock:
            if parent_job_id not in JobRunner._temp_source_copies:
                return

            temp_path, ref_count = JobRunner._temp_source_copies[parent_job_id]
            ref_count -= 1

            if ref_count <= 0:
                # Last reference, cleanup temp source
                del JobRunner._temp_source_copies[parent_job_id]
                self.replacer.cleanup_temp_source(temp_path)
                logger.info(f"Cleaned up temp source copy: {temp_path}")
            else:
                JobRunner._temp_source_copies[parent_job_id] = (temp_path, ref_count)
                logger.debug(f"Released temp source ref: {temp_path} (refs: {ref_count})")

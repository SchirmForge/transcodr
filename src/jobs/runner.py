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
from src.profiles.store import get_profile_manager
from src.api.models import WatchfolderContext
from src.watcher.inotify_watcher import wait_for_file_ready
from .model import Job, JobState, OutputMode

logger = logging.getLogger(__name__)


class JobRunner:
    """
    Executes encoding jobs.

    Handles job validation, encoding, output validation, and file replacement.
    Supports multi-profile encoding by using temp copies of the source file.
    """

    # Class-level tracking of temp source copies for multi-profile jobs (direct API submissions)
    _temp_source_copies: dict[str, tuple[Path, int]] = {}  # parent_id -> (temp_path, ref_count)
    _temp_source_lock = None  # Initialized lazily

    # Class-level tracking for watchfolder file state
    _watchfolder_state: dict[str, dict] = {}  # state_key -> { processing_path, temp_source, ref_count }
    _watchfolder_lock = None  # Initialized lazily

    def __init__(
        self,
        ffmpeg: Optional[FFmpegWrapper] = None,
        profile_manager: Optional[ProfileManager] = None,
        temp_dir: Optional[Path] = None,
        backup_originals: bool = True,
        duration_tolerance_seconds: float = 10.0,
        min_free_space_gb: int = 10,
        on_extension_mismatch: str = "rename",
    ):
        """
        Initialize job runner.

        Args:
            ffmpeg: FFmpeg wrapper (default: auto-create)
            profile_manager: Profile manager (default: auto-create)
            temp_dir: Temporary directory for encoding (default: system temp)
            backup_originals: Create backups of original files
            min_free_space_gb: Minimum free space safety margin in GB
            on_extension_mismatch: Policy for extension mismatch in replace mode (rename/reject/keep)
        """
        self.on_extension_mismatch = on_extension_mismatch
        self.ffmpeg = ffmpeg or FFmpegWrapper()
        self.profile_manager = profile_manager or get_profile_manager()
        self.probe = ProbeHelper()

        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "transcodr"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.replacer = SafeReplacer(
            backup_originals=backup_originals,
            temp_dir=self.temp_dir,
        )

        self.duration_tolerance_seconds = duration_tolerance_seconds
        self.min_free_space_gb = min_free_space_gb

        self.hardware_caps = HardwareCapabilities()

        # Graceful shutdown flag
        self._shutting_down = False

        # Track cancelled job IDs (set by queue when user cancels a job)
        self._cancelled_job_ids: set[str] = set()

        # Initialize thread locks for temp source and watchfolder tracking
        import threading
        if JobRunner._temp_source_lock is None:
            JobRunner._temp_source_lock = threading.Lock()
        if JobRunner._watchfolder_lock is None:
            JobRunner._watchfolder_lock = threading.Lock()

    def request_shutdown(self):
        """
        Signal that daemon is shutting down.

        Gracefully terminates any running FFmpeg process.
        """
        self._shutting_down = True
        if self.ffmpeg:
            self.ffmpeg.terminate()

    def mark_job_cancelled(self, job_id: str):
        """
        Mark a job as cancelled by user (not daemon shutdown).

        This allows the runner to distinguish between user cancellation
        and daemon shutdown when handling cleanup.
        """
        self._cancelled_job_ids.add(job_id)

    def is_job_cancelled(self, job_id: str) -> bool:
        """Check if a job was cancelled by user."""
        return job_id in self._cancelled_job_ids

    def clear_cancelled_job(self, job_id: str):
        """Remove job from cancelled tracking after cleanup."""
        self._cancelled_job_ids.discard(job_id)

    def execute(
        self,
        job: Job,
        progress_callback: Optional[Callable[[Job], None]] = None,
        profile_index: int = 0,
        total_profiles: int = 1,
        parent_job_id: Optional[str] = None,
        watchfolder_context: Optional[WatchfolderContext] = None,
    ) -> Job:
        """
        Execute encoding job.

        Args:
            job: Job to execute
            progress_callback: Optional callback for progress updates
            profile_index: Index of this profile in multi-profile encoding (0-based)
            total_profiles: Total number of profiles for this source
            parent_job_id: Parent job ID for multi-profile grouping
            watchfolder_context: Context for watchfolder jobs - when present,
                JobRunner handles all file operations (.processing rename, temp copy)

        Returns:
            Updated job object

        Raises:
            ValidationError: If validation fails
            EncodingError: If encoding fails
            ReplacementError: If file replacement fails
        """
        is_multi_profile = total_profiles > 1
        is_first_profile = profile_index == 0
        temp_source_path: Optional[Path] = None
        logger.info(f"Starting job execution: {job} (profile {profile_index + 1}/{total_profiles})")

        try:
            # Pre-flight validation
            job.state = JobState.VALIDATING
            if progress_callback:
                progress_callback(job)
            self._validate_job(job)

            # Load profile early to get container format
            profile = self.profile_manager.load_profile(job.profile_name)

            # Setup paths with profile's container format
            self._setup_paths(job, container=profile.container)

            # Handle source file setup
            source_for_encoding = job.source_path

            if watchfolder_context:
                # Watchfolder job: optionally create temp copy, all profiles use same source
                source_for_encoding = self._setup_watchfolder_source(
                    job,
                    watchfolder_context,
                    parent_job_id or job.id,
                    is_first_profile,
                    total_profiles,
                )
            elif is_multi_profile and parent_job_id:
                # Direct API submission with multi-profile
                if job.copy_source_to_temp:
                    temp_source_path = self._get_or_create_temp_source(
                        parent_job_id,
                        job.source_path,
                        total_profiles,
                    )
                    source_for_encoding = temp_source_path
                    logger.info(f"Using temp source copy: {temp_source_path}")
                else:
                    logger.info(f"Encoding directly from source (temp copy disabled): {job.source_path}")

            # Determine hardware acceleration
            if job.hardware_accel is None:
                job.hardware_accel = self.hardware_caps.get_recommended_accel()
                logger.info(f"Auto-selected hardware acceleration: {job.hardware_accel or 'none'}")
            expected_duration = None
            if profile.duration:
                expected_duration = self._parse_duration_to_seconds(profile.duration)
                if expected_duration is None:
                    logger.warning(f"Invalid profile duration format: {profile.duration}")

            # Validate start_time + duration fits within source duration
            if profile.start_time or profile.duration:
                source_duration = self.probe.get_duration(source_for_encoding)
                start_seconds = self._parse_duration_to_seconds(profile.start_time) if profile.start_time else 0

                if start_seconds and start_seconds >= source_duration:
                    raise ValidationError(
                        f"start_time ({start_seconds:.1f}s) exceeds source duration ({source_duration:.1f}s)"
                    )

                if expected_duration and start_seconds is not None:
                    end_time = start_seconds + expected_duration
                    if end_time > source_duration:
                        raise ValidationError(
                            f"start_time + duration ({end_time:.1f}s) exceeds source duration ({source_duration:.1f}s)"
                        )

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
            self._validate_output(
                job,
                source_for_encoding,
                expected_duration=expected_duration,
            )

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

        except ValidationError as e:
            # Validation failures are expected conditions (bad source, no space, etc.)
            # Log as warning without traceback
            logger.warning(f"Job validation failed: {job.id} - {e}")
            job.mark_failed(str(e))
            if progress_callback:
                progress_callback(job)
            raise

        except Exception as e:
            # Check if this was due to:
            # 1. User cancellation (via cancel_job API)
            # 2. Daemon shutdown (SIGINT/SIGTERM)
            # 3. FFmpeg receiving SIGINT from process group (exit code 255)
            is_sigint = (
                isinstance(e, EncodingError) and
                getattr(e, 'exit_code', None) == 255
            )
            is_cancelled = self.is_job_cancelled(job.id)
            is_interrupted = self._shutting_down or is_sigint

            if is_cancelled:
                # User cancelled this job - mark as cancelled, leave source unchanged
                logger.info(f"Job cancelled by user: {job.id}")
                job.state = JobState.CANCELLED
                job.error_message = "Cancelled by user"
            elif is_interrupted:
                logger.info(f"Job interrupted by shutdown: {job.id}")
                job.state = JobState.INTERRUPTED
                job.error_message = "Interrupted by daemon shutdown"
            else:
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
            # Handle cleanup based on job type
            is_failed = job.state == JobState.FAILED
            is_cancelled = job.state == JobState.CANCELLED
            is_interrupted = job.state == JobState.INTERRUPTED

            # Clear cancelled tracking after handling
            self.clear_cancelled_job(job.id)

            if watchfolder_context:
                # Watchfolder job: decrement ref_count and finalize when all profiles complete
                # Cancelled jobs are treated like interrupted (leave source unchanged)
                self._release_watchfolder_ref(
                    watchfolder_context,
                    parent_job_id or job.id,
                    failed=is_failed,
                    interrupted=is_interrupted or is_cancelled,
                )
            elif is_multi_profile and parent_job_id and not watchfolder_context:
                # Direct API submission: release temp source copy reference
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

        # Check disk space in temp directory (if using temp folder)
        if job.use_temp_folder:
            source_size = job.source_path.stat().st_size
            safety_margin = self.min_free_space_gb * 1024**3
            required_space = source_size + safety_margin  # ~1x source (output estimate) + safety margin

            disk_usage = shutil.disk_usage(self.temp_dir)
            if disk_usage.free < required_space:
                source_gb = source_size / 1024**3
                raise ValidationError(
                    f"Insufficient space in temp directory ({self.temp_dir}): "
                    f"estimated {required_space / 1024**3:.1f}GB needed "
                    f"({source_gb:.1f}GB source + {self.min_free_space_gb}GB safety margin), "
                    f"only {disk_usage.free / 1024**3:.1f}GB available. "
                    f"Consider freeing space, changing temp_dir in config, "
                    f"or disabling temp folder encoding."
                )

        # Check profile exists
        if not self.profile_manager.profile_exists(job.profile_name):
            raise ValidationError(f"Profile not found: {job.profile_name}")

        logger.debug("Pre-flight validation passed")

    def _setup_paths(self, job: Job, container: str = "mkv"):
        """Setup output and temp paths for job.

        Args:
            job: Job to setup paths for
            container: Output container format from profile (mkv, mp4, etc.)
        """
        # Determine output path (same as source if not specified)
        if job.output_path is None:
            job.output_path = job.source_path

        # Get source name without processing markers
        source_name = job.source_path.name
        source_suffix = job.source_path.suffix

        # Strip processing markers to get real name
        processing_markers = [".processing", ".processed", ".failed"]
        if source_suffix in processing_markers:
            # Real extension is in the stem (e.g., "video.mkv.processing" -> stem="video.mkv")
            real_stem = Path(job.source_path.stem)
            source_name = real_stem.stem
        else:
            source_name = job.source_path.stem

        # Use profile's container format for output extension
        output_ext = f".{container}"
        temp_filename = f"{job.id}_{source_name}_encoded{output_ext}"

        if job.use_temp_folder:
            job.temp_path = self.temp_dir / temp_filename
        else:
            # Write temp file next to the output (or source for replace mode)
            output_dir = job.output_path.parent if job.output_path else job.source_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            job.temp_path = output_dir / temp_filename

        logger.debug(f"Temp path: {job.temp_path} (container: {container}, use_temp_folder: {job.use_temp_folder})")

    @staticmethod
    def _parse_duration_to_seconds(duration: str) -> Optional[float]:
        if duration is None:
            return None
        if isinstance(duration, (int, float)):
            return float(duration)
        if not isinstance(duration, str):
            return None
        text = duration.strip()
        if not text:
            return None
        try:
            if ":" in text:
                parts = [p.strip() for p in text.split(":")]
                if len(parts) > 3:
                    return None
                values = [float(p) for p in parts]
                if len(values) == 3:
                    hours, minutes, seconds = values
                elif len(values) == 2:
                    hours = 0.0
                    minutes, seconds = values
                else:
                    hours = 0.0
                    minutes = 0.0
                    seconds = values[0]
                return hours * 3600 + minutes * 60 + seconds
            return float(text)
        except ValueError:
            return None

    def _validate_output(
        self,
        job: Job,
        source_for_comparison: Optional[Path] = None,
        expected_duration: Optional[float] = None,
    ):
        """Validate encoded output file."""
        logger.debug("Validating encoded output")

        if not job.temp_path.exists():
            raise ValidationError("Encoded file not found")

        if not self.probe.validate_file(job.temp_path):
            raise ValidationError("Encoded file is not a valid video")

        # Get output metadata
        output_duration = None
        try:
            job.output_size_bytes = job.temp_path.stat().st_size
            info = self.probe.get_info(job.temp_path)
            output_duration = info.duration
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

        # Compare durations (use expected duration for extract profiles)
        if expected_duration is not None and expected_duration > 0:
            if output_duration is None:
                output_duration = self.probe.get_duration(job.temp_path)
            diff_seconds = abs(expected_duration - output_duration)
            tolerance_seconds = max(expected_duration * 0.01, self.duration_tolerance_seconds)
            if diff_seconds > tolerance_seconds:
                raise ValidationError(
                    f"Duration mismatch: expected={expected_duration:.1f}s, "
                    f"encoded={output_duration:.1f}s (diff={diff_seconds:.1f}s, "
                    f"tol={tolerance_seconds:.1f}s)"
                )
        else:
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
        """Replace original file with encoded version, handling extension mismatch."""
        source_ext = job.source_path.suffix.lower()
        encoded_ext = job.temp_path.suffix.lower()

        if source_ext == encoded_ext:
            # Extensions match — standard replacement
            logger.debug("Replacing original file (extensions match)")
            self.replacer.replace(job.source_path, job.temp_path)
            logger.debug("File replacement completed")
            return

        # Extension mismatch detected
        logger.info(
            f"Extension mismatch: source={source_ext}, encoded={encoded_ext} "
            f"(policy: {self.on_extension_mismatch})"
        )

        if self.on_extension_mismatch == "reject":
            raise ReplacementError(
                f"Extension mismatch: source is '{source_ext}' but profile produces '{encoded_ext}'. "
                f"Set on_extension_mismatch to 'rename' (use correct extension) or 'keep' "
                f"(keep source extension) in config.yaml to allow this."
            )
        elif self.on_extension_mismatch == "keep":
            # Replace keeping the source extension (file content won't match extension)
            self.replacer.replace(job.source_path, job.temp_path)
            job.add_warning(
                f"Extension mismatch: file kept as '{source_ext}' but contains "
                f"'{encoded_ext}' content (on_extension_mismatch=keep)"
            )
            logger.warning(f"Replaced with mismatched extension: {job.source_path}")
        else:
            # "rename" (default): use correct extension, delete original
            self._replace_with_new_extension(job, encoded_ext)
            job.add_warning(
                f"Extension mismatch: source was '{source_ext}', "
                f"renamed to '{encoded_ext}' (on_extension_mismatch=rename)"
            )

    def _replace_with_new_extension(self, job: Job, new_ext: str):
        """
        Replace original file with encoded version using the correct extension.

        Creates a new file with the proper extension, backs up the original if
        configured, then removes both the original and temp file.

        Args:
            job: Job being processed
            new_ext: New file extension (e.g. ".mkv")
        """
        source = job.source_path
        encoded = job.temp_path
        new_path = source.with_suffix(new_ext)

        # Validate encoded file
        if not self.probe.validate_file(encoded):
            raise ReplacementError(f"Encoded file is corrupt: {encoded}")

        # Backup original if configured
        if self.replacer.backup_originals:
            backup_path = self.replacer._get_backup_path(source)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, backup_path)
                logger.info(f"Backup created: {backup_path}")
            except Exception as e:
                raise ReplacementError(f"Failed to create backup: {e}")

        # Copy encoded file to new location (with correct extension)
        try:
            shutil.copy2(encoded, new_path)
            logger.info(f"Created output with correct extension: {new_path}")
        except Exception as e:
            raise ReplacementError(f"Failed to copy encoded file to {new_path}: {e}")

        # Delete original (different extension, so it's a separate file)
        try:
            source.unlink()
            logger.info(f"Deleted original: {source}")
        except Exception as e:
            logger.warning(f"Failed to delete original after rename: {e}")

        # Clean up temp file
        try:
            if encoded.exists():
                encoded.unlink()
                logger.debug(f"Cleaned up temp file: {encoded}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")

        # Update job output path to reflect the new extension
        job.output_path = new_path
        logger.info(f"File replacement completed (renamed {source.suffix} → {new_ext})")

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

    def _setup_watchfolder_source(
        self,
        job: Job,
        ctx: WatchfolderContext,
        state_key: str,
        is_first_profile: bool,
        total_profiles: int,
    ) -> Path:
        """
        Setup source for watchfolder job.

        All jobs read from the original file (no .processing rename during execution).
        Temp copy is created once by first profile if disable_temp_copy=False.
        Final rename (.processed/.failed) or delete happens in _do_watchfolder_cleanup().

        Uses inotify for instant detection of copy completion on local filesystems,
        with polling fallback for NFS/remote filesystems.

        Args:
            job: Job being executed
            ctx: Watchfolder context with file handling settings
            state_key: Key for tracking state (parent_job_id or job.id)
            is_first_profile: True if this is the first profile
            total_profiles: Total number of profiles

        Returns:
            Path to use for encoding (temp copy or original file)
        """
        import time

        source_path = job.source_path

        if is_first_profile:
            # First profile: create temp copy if needed
            temp_source = None
            if not ctx.disable_temp_copy:
                temp_folder = Path(ctx.temp_folder) if ctx.temp_folder else self.temp_dir
                temp_folder.mkdir(parents=True, exist_ok=True)
                temp_source = temp_folder / source_path.name

                # Store state BEFORE starting copy so subsequent profiles know what to wait for
                with JobRunner._watchfolder_lock:
                    JobRunner._watchfolder_state[state_key] = {
                        "source_path": source_path,
                        "temp_source": temp_source,
                        "copy_complete": False,
                        "ref_count": total_profiles,
                    }

                # Do the copy OUTSIDE the lock so other profiles can check state
                logger.info(f"Copying {source_path.name} to temp folder")
                shutil.copy2(source_path, temp_source)

                # Mark copy as complete
                with JobRunner._watchfolder_lock:
                    if state_key in JobRunner._watchfolder_state:
                        JobRunner._watchfolder_state[state_key]["copy_complete"] = True
            else:
                logger.info(f"Encoding directly from source (disable_temp_copy): {source_path}")
                # Store state for subsequent profiles
                with JobRunner._watchfolder_lock:
                    JobRunner._watchfolder_state[state_key] = {
                        "source_path": source_path,
                        "temp_source": None,
                        "copy_complete": True,
                        "ref_count": total_profiles,
                    }

            return temp_source if temp_source else source_path

        else:
            # Subsequent profile: wait for first profile to set up state and complete copy
            max_state_wait = 30  # Wait up to 30s for state to appear
            state_interval = 0.5
            elapsed = 0.0

            # First, wait for state to be created
            while elapsed < max_state_wait:
                with JobRunner._watchfolder_lock:
                    state = JobRunner._watchfolder_state.get(state_key)
                    if state:
                        break
                time.sleep(state_interval)
                elapsed += state_interval

            if not state:
                raise RuntimeError(
                    f"Timeout waiting for watchfolder state {state_key} - "
                    f"first profile may have failed to start"
                )

            temp_source = state.get("temp_source")
            source_to_use = temp_source if temp_source else state["source_path"]

            # If no temp copy, return immediately
            if not temp_source:
                return source_to_use

            # Check if copy is already complete
            with JobRunner._watchfolder_lock:
                if JobRunner._watchfolder_state.get(state_key, {}).get("copy_complete"):
                    return source_to_use

            # Wait for temp copy to be ready using inotify/polling
            logger.info(f"Waiting for temp copy to complete: {temp_source.name}")
            if wait_for_file_ready(temp_source, timeout_seconds=300):
                return source_to_use
            else:
                raise RuntimeError(
                    f"Timeout waiting for temp copy {temp_source} - "
                    f"first profile may have failed during copy"
                )

    def _release_watchfolder_ref(
        self,
        ctx: WatchfolderContext,
        state_key: str,
        failed: bool,
        interrupted: bool = False,
    ):
        """
        Release reference to watchfolder state.

        Decrements ref_count. When it reaches zero, calls _do_watchfolder_cleanup
        to handle cleanup and final rename.

        Args:
            ctx: Watchfolder context with file handling settings
            state_key: Key for tracking state
            failed: True if this profile's job failed
            interrupted: True if this profile's job was interrupted/cancelled
        """
        with JobRunner._watchfolder_lock:
            state = JobRunner._watchfolder_state.get(state_key)
            if not state:
                logger.warning(f"No watchfolder state for {state_key} during release")
                return

            # Decrement ref count
            state["ref_count"] -= 1

            # Track if any profile failed or was interrupted/cancelled
            # Note: cancelled jobs pass interrupted=True to leave source unchanged
            if failed:
                state["any_failed"] = True
            if interrupted:
                state["any_interrupted"] = True

            logger.debug(
                f"Released watchfolder ref: {state_key} "
                f"(refs: {state['ref_count']}, failed: {state.get('any_failed', False)}, "
                f"interrupted: {state.get('any_interrupted', False)})"
            )

            if state["ref_count"] <= 0:
                # Last profile completed - finalize outside the lock
                any_failed = state.get("any_failed", False)
                any_interrupted = state.get("any_interrupted", False)
                # Remove state and extract data for cleanup after releasing lock
                JobRunner._watchfolder_state.pop(state_key, None)
                source_path = state["source_path"]
                temp_source = state["temp_source"]
            else:
                return  # Not the last profile, nothing more to do

        # Outside the lock - do cleanup for last profile
        self._do_watchfolder_cleanup(ctx, source_path, temp_source, any_failed, any_interrupted)

    def _do_watchfolder_cleanup(
        self,
        ctx: WatchfolderContext,
        source_path: Path,
        temp_source: Optional[Path],
        failed: bool,
        interrupted: bool = False,
    ):
        """
        Perform watchfolder cleanup after all profiles complete.

        Args:
            ctx: Watchfolder context with file handling settings
            source_path: Original source file path
            temp_source: Temp copy path (if created)
            failed: True if any profile failed
            interrupted: True if any profile was interrupted by shutdown
        """
        # Cleanup temp source
        if temp_source and temp_source.exists():
            try:
                temp_source.unlink()
                logger.debug(f"Cleaned up temp source: {temp_source}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp source: {e}")

        # Handle source file (final rename or delete)
        if not source_path.exists():
            logger.warning(f"Source file no longer exists: {source_path}")
            return

        try:
            if interrupted:
                # Job was interrupted (shutdown) or cancelled - leave file unchanged for retry
                logger.info(f"Job interrupted/cancelled, source unchanged: {source_path.name}")
            elif failed:
                # Rename to .failed
                failed_path = source_path.with_suffix(source_path.suffix + ".failed")
                source_path.rename(failed_path)
                logger.info(f"Job failed: {source_path.name} → {failed_path.name}")
            elif ctx.keep_processed_files:
                # Rename to .processed
                processed_path = source_path.with_suffix(source_path.suffix + ".processed")
                source_path.rename(processed_path)
                logger.info(f"Job completed: {source_path.name} → {processed_path.name}")
            else:
                # Delete source
                source_path.unlink()
                logger.info(f"Job completed, source deleted: {source_path.name}")
        except Exception as e:
            logger.error(f"Failed to finalize watchfolder source: {e}")

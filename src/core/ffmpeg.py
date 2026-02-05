"""FFmpeg wrapper for video transcoding operations."""

import re
import signal
import subprocess
import logging
from pathlib import Path
from typing import Callable, Optional

from .errors import FFmpegNotFoundError, EncodingError

logger = logging.getLogger(__name__)


class FFmpegProgress:
    """Represents FFmpeg encoding progress."""

    def __init__(
        self,
        frame: int = 0,
        fps: float = 0.0,
        size_kb: int = 0,
        time: str = "00:00:00.00",
        bitrate: float = 0.0,
        speed: float = 0.0,
    ):
        self.frame = frame
        self.fps = fps
        self.size_kb = size_kb
        self.time = time
        self.bitrate = bitrate
        self.speed = speed

    def __repr__(self):
        return (
            f"FFmpegProgress(frame={self.frame}, fps={self.fps:.1f}, "
            f"time={self.time}, bitrate={self.bitrate:.1f}kbits/s)"
        )


class FFmpegWrapper:
    """
    Wrapper for FFmpeg operations.

    Handles FFmpeg invocation, version detection, progress tracking,
    and error handling. Supports overriding FFmpeg binary path for
    upgrades or custom installations.
    """

    def __init__(self, binary_path: str = "ffmpeg"):
        """
        Initialize FFmpeg wrapper.

        Args:
            binary_path: Path to FFmpeg binary (default: "ffmpeg" from PATH)
        """
        self.binary_path = binary_path
        self._current_process: Optional[subprocess.Popen] = None
        self.version = self._detect_version()
        logger.info(f"FFmpeg initialized: {self.version}")

    def _detect_version(self) -> str:
        """
        Detect FFmpeg version.

        Returns:
            Version string (e.g., "ffmpeg version 7.1.1")

        Raises:
            FFmpegNotFoundError: If FFmpeg binary not found or not executable
        """
        try:
            out = subprocess.check_output(
                [self.binary_path, "-version"],
                stderr=subprocess.STDOUT,
                text=True,
            )
            version_line = out.splitlines()[0]
            logger.debug(f"FFmpeg version detected: {version_line}")
            return version_line
        except FileNotFoundError:
            raise FFmpegNotFoundError(
                f"FFmpeg binary not found at: {self.binary_path}"
            )
        except subprocess.CalledProcessError as e:
            raise FFmpegNotFoundError(
                f"Failed to execute FFmpeg: {e}"
            )

    def get_version_number(self) -> str:
        """
        Extract version number from version string.

        Returns:
            Version number (e.g., "7.1.1")
        """
        # Parse "ffmpeg version 7.1.1" -> "7.1.1"
        match = re.search(r"version\s+([\d.]+)", self.version)
        if match:
            return match.group(1)
        return "unknown"

    def supports_codec(self, codec: str) -> bool:
        """
        Check if FFmpeg supports a specific codec.

        Args:
            codec: Codec name (e.g., "libx265", "hevc_nvenc")

        Returns:
            True if codec is supported
        """
        try:
            result = subprocess.run(
                [self.binary_path, "-codecs"],
                capture_output=True,
                text=True,
                check=True,
            )
            return codec in result.stdout
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to check codec support for: {codec}")
            return False

    def _parse_progress(self, line: str) -> Optional[FFmpegProgress]:
        """
        Parse FFmpeg progress line from stderr.

        FFmpeg outputs progress in format:
        frame= 1234 fps=45 q=28.0 size=  12345kB time=00:01:23.45 bitrate=1234.5kbits/s speed=1.5x

        Args:
            line: Single line from FFmpeg stderr

        Returns:
            FFmpegProgress object or None if line doesn't contain progress
        """
        # Look for frame= indicator
        if "frame=" not in line:
            return None

        progress = FFmpegProgress()

        # Extract frame number
        frame_match = re.search(r"frame=\s*(\d+)", line)
        if frame_match:
            progress.frame = int(frame_match.group(1))

        # Extract fps
        fps_match = re.search(r"fps=\s*([\d.]+)", line)
        if fps_match:
            progress.fps = float(fps_match.group(1))

        # Extract size (in KB)
        size_match = re.search(r"size=\s*(\d+)kB", line)
        if size_match:
            progress.size_kb = int(size_match.group(1))

        # Extract time
        time_match = re.search(r"time=\s*([\d:.-]+)", line)
        if time_match:
            progress.time = time_match.group(1)

        # Extract bitrate
        bitrate_match = re.search(r"bitrate=\s*([\d.]+)kbits/s", line)
        if bitrate_match:
            progress.bitrate = float(bitrate_match.group(1))

        # Extract speed
        speed_match = re.search(r"speed=\s*([\d.]+)x", line)
        if speed_match:
            progress.speed = float(speed_match.group(1))

        return progress

    def run(
        self,
        args: list[str],
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
    ) -> subprocess.CompletedProcess:
        """
        Run FFmpeg with given arguments.

        Args:
            args: List of FFmpeg arguments (without the binary name)
            progress_callback: Optional callback for progress updates

        Returns:
            CompletedProcess object

        Raises:
            EncodingError: If FFmpeg exits with non-zero code
        """
        cmd = [self.binary_path] + args

        logger.debug(f"Running FFmpeg: {' '.join(cmd)}")

        # Run FFmpeg and capture output
        # stdin=DEVNULL prevents FFmpeg from thinking it's interactive
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Store process reference for graceful termination
        self._current_process = process

        stderr_lines = []

        try:
            # Stream stderr for progress and error capture
            for line in process.stderr:
                stderr_lines.append(line)

                # Log stderr (but filter out progress lines to avoid spam)
                if "frame=" not in line:
                    logger.debug(f"FFmpeg: {line.rstrip()}")

                # Parse and report progress
                if progress_callback:
                    progress = self._parse_progress(line)
                    if progress:
                        try:
                            progress_callback(progress)
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")

            # Wait for process to complete
            process.wait()
        finally:
            # Clear process reference
            self._current_process = None

        stderr_text = "".join(stderr_lines)

        if process.returncode != 0:
            logger.error(f"FFmpeg failed with exit code {process.returncode}")
            logger.error(f"FFmpeg stderr:\n{stderr_text}")
            raise EncodingError(
                f"FFmpeg exited with code {process.returncode}. "
                f"Check logs for details.",
                exit_code=process.returncode,
            )

        logger.info("FFmpeg completed successfully")

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout="",
            stderr=stderr_text,
        )

    def terminate(self, timeout: float = 10.0) -> bool:
        """
        Gracefully terminate running FFmpeg process.

        Sends SIGINT first (allows FFmpeg to finish writing), then SIGTERM/SIGKILL
        if it doesn't exit within the timeout.

        Args:
            timeout: Seconds to wait for graceful exit before force killing

        Returns:
            True if process terminated gracefully, False if force killed
        """
        process = self._current_process
        if not process or process.poll() is not None:
            # No process running or already terminated
            return True

        logger.info("Gracefully terminating FFmpeg process...")

        # Send SIGINT for graceful exit (FFmpeg finishes writing current frame)
        try:
            process.send_signal(signal.SIGINT)
        except OSError:
            # Process may have already terminated
            return True

        try:
            process.wait(timeout=timeout)
            logger.info("FFmpeg terminated gracefully")
            return True
        except subprocess.TimeoutExpired:
            # Force kill if graceful shutdown fails
            logger.warning(f"FFmpeg did not exit within {timeout}s, force killing...")
            process.kill()
            process.wait()
            logger.info("FFmpeg force killed")
            return False

    def get_encoders(self) -> list[str]:
        """
        Get list of available encoders.

        Returns:
            List of encoder names
        """
        try:
            result = subprocess.run(
                [self.binary_path, "-encoders"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Parse encoder list (skip header lines)
            encoders = []
            for line in result.stdout.splitlines():
                # Encoder lines start with " V" (video), " A" (audio), etc.
                if line.startswith(" V") or line.startswith(" A"):
                    # Format: " V..... libx265 ..."
                    parts = line.split()
                    if len(parts) >= 2:
                        encoders.append(parts[1])
            return encoders
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get encoder list: {e}")
            return []

    def get_decoders(self) -> list[str]:
        """
        Get list of available decoders.

        Returns:
            List of decoder names
        """
        try:
            result = subprocess.run(
                [self.binary_path, "-decoders"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Parse decoder list
            decoders = []
            for line in result.stdout.splitlines():
                if line.startswith(" V") or line.startswith(" A"):
                    parts = line.split()
                    if len(parts) >= 2:
                        decoders.append(parts[1])
            return decoders
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get decoder list: {e}")
            return []

    def get_hardware_encoders(self) -> dict[str, list[str]]:
        """
        Get hardware-accelerated encoders grouped by type.

        Returns:
            Dict mapping acceleration type to list of encoders
            Example: {"nvenc": ["h264_nvenc", "hevc_nvenc"], "vaapi": ["h264_vaapi", ...]}
        """
        encoders = self.get_encoders()

        hardware_types = {
            "nvenc": [],    # NVIDIA NVENC
            "vaapi": [],    # Video Acceleration API (Intel/AMD)
            "qsv": [],      # Intel Quick Sync Video
            "amf": [],      # AMD Advanced Media Framework
            "videotoolbox": [],  # Apple VideoToolbox
            "v4l2m2m": [],  # Video4Linux2 Memory-to-Memory
        }

        for encoder in encoders:
            for hw_type in hardware_types.keys():
                if hw_type in encoder.lower():
                    hardware_types[hw_type].append(encoder)

        # Return only types that have encoders
        return {k: v for k, v in hardware_types.items() if v}

    def get_hardware_decoders(self) -> dict[str, list[str]]:
        """
        Get hardware-accelerated decoders grouped by type.

        Returns:
            Dict mapping acceleration type to list of decoders
        """
        decoders = self.get_decoders()

        hardware_types = {
            "cuvid": [],    # NVIDIA CUVID
            "vaapi": [],    # Video Acceleration API
            "qsv": [],      # Intel Quick Sync Video
            "videotoolbox": [],  # Apple VideoToolbox
            "v4l2m2m": [],  # Video4Linux2 Memory-to-Memory
        }

        for decoder in decoders:
            for hw_type in hardware_types.keys():
                if hw_type in decoder.lower():
                    hardware_types[hw_type].append(decoder)

        return {k: v for k, v in hardware_types.items() if v}

    def get_hwaccels(self) -> list[str]:
        """
        Get list of available hardware acceleration methods.

        Returns:
            List of hwaccel names (e.g., ["vaapi", "cuda", "qsv"])
        """
        try:
            result = subprocess.run(
                [self.binary_path, "-hwaccels"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Parse hwaccel list (skip header line)
            hwaccels = []
            lines = result.stdout.splitlines()
            for line in lines[1:]:  # Skip "Hardware acceleration methods:"
                line = line.strip()
                if line:
                    hwaccels.append(line)
            return hwaccels
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get hwaccel list: {e}")
            return []

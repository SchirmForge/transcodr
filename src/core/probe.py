"""FFprobe helpers for video file inspection and validation."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from .errors import ValidationError

logger = logging.getLogger(__name__)


class StreamInfo:
    """Information about a media stream."""

    def __init__(self, data: dict):
        self.index = data.get("index", 0)
        self.codec_name = data.get("codec_name", "unknown")
        self.codec_type = data.get("codec_type", "unknown")
        self.codec_long_name = data.get("codec_long_name", "")

        # Video specific
        self.width = data.get("width")
        self.height = data.get("height")
        self.pix_fmt = data.get("pix_fmt")
        self.frame_rate = data.get("r_frame_rate", "0/0")

        # Audio specific
        self.sample_rate = data.get("sample_rate")
        self.channels = data.get("channels")
        self.channel_layout = data.get("channel_layout")

        # Common
        self.bit_rate = data.get("bit_rate")
        self.duration = data.get("duration")
        self.tags = data.get("tags", {})

    def __repr__(self):
        if self.codec_type == "video":
            return (
                f"StreamInfo(type=video, codec={self.codec_name}, "
                f"resolution={self.width}x{self.height})"
            )
        elif self.codec_type == "audio":
            return (
                f"StreamInfo(type=audio, codec={self.codec_name}, "
                f"channels={self.channels})"
            )
        else:
            return f"StreamInfo(type={self.codec_type}, codec={self.codec_name})"


class MediaInfo:
    """Complete information about a media file."""

    def __init__(self, data: dict):
        self.format_data = data.get("format", {})
        self.streams = [StreamInfo(s) for s in data.get("streams", [])]

        # Format info
        self.filename = self.format_data.get("filename", "")
        self.format_name = self.format_data.get("format_name", "")
        self.format_long_name = self.format_data.get("format_long_name", "")
        self.duration = float(self.format_data.get("duration", 0))
        self.size = int(self.format_data.get("size", 0))
        self.bit_rate = int(self.format_data.get("bit_rate", 0))
        self.tags = self.format_data.get("tags", {})

    def get_video_streams(self) -> list[StreamInfo]:
        """Get all video streams."""
        return [s for s in self.streams if s.codec_type == "video"]

    def get_audio_streams(self) -> list[StreamInfo]:
        """Get all audio streams."""
        return [s for s in self.streams if s.codec_type == "audio"]

    def get_subtitle_streams(self) -> list[StreamInfo]:
        """Get all subtitle streams."""
        return [s for s in self.streams if s.codec_type == "subtitle"]

    def get_primary_video_stream(self) -> Optional[StreamInfo]:
        """Get the first video stream (primary)."""
        video_streams = self.get_video_streams()
        return video_streams[0] if video_streams else None

    def get_primary_audio_stream(self) -> Optional[StreamInfo]:
        """Get the first audio stream (primary)."""
        audio_streams = self.get_audio_streams()
        return audio_streams[0] if audio_streams else None

    def __repr__(self):
        video_count = len(self.get_video_streams())
        audio_count = len(self.get_audio_streams())
        return (
            f"MediaInfo(format={self.format_name}, duration={self.duration:.1f}s, "
            f"video_streams={video_count}, audio_streams={audio_count})"
        )


class ProbeHelper:
    """
    Helper for inspecting video files using ffprobe.

    Provides methods for extracting media information, validating files,
    and checking codec compatibility.
    """

    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Initialize probe helper.

        Args:
            ffprobe_path: Path to ffprobe binary (default: "ffprobe" from PATH)
        """
        self.ffprobe_path = ffprobe_path
        logger.debug(f"ProbeHelper initialized with: {ffprobe_path}")

    def get_info(self, file_path: Path) -> MediaInfo:
        """
        Get comprehensive file information.

        Args:
            file_path: Path to media file

        Returns:
            MediaInfo object

        Raises:
            ValidationError: If file cannot be probed
        """
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        try:
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)
            logger.debug(f"Probed file: {file_path.name}")

            return MediaInfo(data)

        except subprocess.CalledProcessError as e:
            raise ValidationError(
                f"Failed to probe file {file_path}: {e.stderr}"
            )
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Failed to parse ffprobe output for {file_path}: {e}"
            )

    def get_duration(self, file_path: Path) -> float:
        """
        Get media duration in seconds.

        Args:
            file_path: Path to media file

        Returns:
            Duration in seconds
        """
        info = self.get_info(file_path)
        return info.duration

    def get_video_codec(self, file_path: Path) -> Optional[str]:
        """
        Get primary video codec name.

        Args:
            file_path: Path to media file

        Returns:
            Codec name (e.g., "h264", "hevc") or None if no video stream
        """
        info = self.get_info(file_path)
        video_stream = info.get_primary_video_stream()
        return video_stream.codec_name if video_stream else None

    def get_audio_codec(self, file_path: Path) -> Optional[str]:
        """
        Get primary audio codec name.

        Args:
            file_path: Path to media file

        Returns:
            Codec name (e.g., "aac", "opus") or None if no audio stream
        """
        info = self.get_info(file_path)
        audio_stream = info.get_primary_audio_stream()
        return audio_stream.codec_name if audio_stream else None

    def get_resolution(self, file_path: Path) -> Optional[tuple[int, int]]:
        """
        Get video resolution (width, height).

        Args:
            file_path: Path to media file

        Returns:
            Tuple of (width, height) or None if no video stream
        """
        info = self.get_info(file_path)
        video_stream = info.get_primary_video_stream()
        if video_stream and video_stream.width and video_stream.height:
            return (video_stream.width, video_stream.height)
        return None

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate that file is a playable media file.

        Args:
            file_path: Path to media file

        Returns:
            True if file is valid, False otherwise
        """
        try:
            info = self.get_info(file_path)
            # Check that we have at least one stream
            return len(info.streams) > 0
        except ValidationError:
            return False

    def compare_durations(
        self,
        file1: Path,
        file2: Path,
        tolerance_percent: float = 1.0,
    ) -> bool:
        """
        Compare durations of two files within a tolerance.

        Useful for validating that encoded file matches original duration.

        Args:
            file1: First file path
            file2: Second file path
            tolerance_percent: Allowed difference percentage (default: 1.0%)

        Returns:
            True if durations match within tolerance
        """
        try:
            duration1 = self.get_duration(file1)
            duration2 = self.get_duration(file2)

            if duration1 == 0:
                logger.warning(f"File {file1} has zero duration")
                return False

            diff_percent = abs(duration1 - duration2) / duration1 * 100

            logger.debug(
                f"Duration comparison: {duration1:.2f}s vs {duration2:.2f}s "
                f"(diff: {diff_percent:.2f}%)"
            )

            return diff_percent <= tolerance_percent

        except ValidationError as e:
            logger.error(f"Failed to compare durations: {e}")
            return False

    def get_frame_count(self, file_path: Path) -> Optional[int]:
        """
        Get total frame count for video.

        This uses ffprobe's count_frames method which can be slow for large files.

        Args:
            file_path: Path to media file

        Returns:
            Total frame count or None if unavailable
        """
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-count_frames",
                "-show_entries", "stream=nb_read_frames",
                "-of", "default=nokey=1:noprint_wrappers=1",
                str(file_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            frame_count = int(result.stdout.strip())
            logger.debug(f"Frame count for {file_path.name}: {frame_count}")
            return frame_count

        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(f"Failed to get frame count: {e}")
            return None

    def estimate_frame_count(self, file_path: Path) -> Optional[int]:
        """
        Estimate frame count from duration and frame rate.

        Faster than get_frame_count but less accurate.

        Args:
            file_path: Path to media file

        Returns:
            Estimated frame count or None if unavailable
        """
        try:
            info = self.get_info(file_path)
            video_stream = info.get_primary_video_stream()

            if not video_stream or not video_stream.frame_rate:
                return None

            # Parse frame rate (format: "30/1" or "24000/1001")
            fps_parts = video_stream.frame_rate.split("/")
            if len(fps_parts) == 2:
                fps = float(fps_parts[0]) / float(fps_parts[1])
                estimated_frames = int(info.duration * fps)
                logger.debug(
                    f"Estimated frames for {file_path.name}: {estimated_frames} "
                    f"(duration={info.duration:.1f}s, fps={fps:.2f})"
                )
                return estimated_frames

            return None

        except (ValidationError, ValueError, ZeroDivisionError) as e:
            logger.warning(f"Failed to estimate frame count: {e}")
            return None

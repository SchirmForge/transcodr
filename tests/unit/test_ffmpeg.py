"""Unit tests for FFmpeg wrapper."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.ffmpeg import FFmpegWrapper, FFmpegProgress
from src.core.errors import FFmpegNotFoundError, EncodingError


class TestFFmpegWrapper:
    """Test FFmpeg wrapper functionality."""

    def test_version_detection(self):
        """Test FFmpeg version detection."""
        with patch("subprocess.check_output") as mock_check:
            mock_check.return_value = "ffmpeg version 7.1.1-1ubuntu4\nConfiguration: ...\n"

            wrapper = FFmpegWrapper()

            assert "ffmpeg version 7.1.1" in wrapper.version
            assert wrapper.get_version_number() == "7.1.1"

    def test_version_detection_failure(self):
        """Test FFmpeg not found."""
        with patch("subprocess.check_output") as mock_check:
            mock_check.side_effect = FileNotFoundError()

            with pytest.raises(FFmpegNotFoundError):
                FFmpegWrapper()

    def test_progress_parsing_frame(self):
        """Test parsing FFmpeg progress line."""
        wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
        wrapper.binary_path = "ffmpeg"

        line = "frame= 1234 fps=45.2 q=28.0 size=  12345kB time=00:01:23.45 bitrate=1234.5kbits/s speed=1.5x"
        progress = wrapper._parse_progress(line)

        assert progress is not None
        assert progress.frame == 1234
        assert progress.fps == 45.2
        assert progress.size_kb == 12345
        assert progress.time == "00:01:23.45"
        assert progress.bitrate == 1234.5
        assert progress.speed == 1.5

    def test_progress_parsing_no_progress(self):
        """Test parsing non-progress line returns None."""
        wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
        wrapper.binary_path = "ffmpeg"

        line = "Input #0, matroska,webm, from 'file.mkv':"
        progress = wrapper._parse_progress(line)

        assert progress is None

    def test_supports_codec(self):
        """Test codec support checking."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "V..... libx265 x265 codec\nV..... h264 H.264"
            mock_run.return_value = mock_result

            wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
            wrapper.binary_path = "ffmpeg"

            assert wrapper.supports_codec("libx265") is True
            assert wrapper.supports_codec("h264") is True
            assert wrapper.supports_codec("nonexistent") is False

    def test_get_encoders(self):
        """Test getting encoder list."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = """Encoders:
 V..... libx265              libx265 H.265 / HEVC
 V..... h264_nvenc           NVIDIA NVENC H.264 encoder
 A..... aac                  AAC (Advanced Audio Coding)
"""
            mock_run.return_value = mock_result

            wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
            wrapper.binary_path = "ffmpeg"

            encoders = wrapper.get_encoders()
            assert "libx265" in encoders
            assert "h264_nvenc" in encoders
            assert "aac" in encoders

    def test_run_success(self):
        """Test successful FFmpeg run."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.stderr = iter([
                "Input #0, matroska,webm, from 'input.mkv':\n",
                "frame= 100 fps=30 size=1024kB time=00:00:03.33\n",
                "frame= 200 fps=30 size=2048kB time=00:00:06.66\n",
            ])
            mock_popen.return_value = mock_process

            wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
            wrapper.binary_path = "ffmpeg"

            progress_updates = []

            def progress_callback(progress):
                progress_updates.append(progress)

            result = wrapper.run(["-i", "input.mkv", "output.mkv"], progress_callback)

            assert result.returncode == 0
            assert len(progress_updates) == 2
            assert progress_updates[0].frame == 100
            assert progress_updates[1].frame == 200

    def test_run_failure(self):
        """Test FFmpeg run failure."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.stderr = iter(["Error: Invalid input\n"])
            mock_popen.return_value = mock_process

            wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
            wrapper.binary_path = "ffmpeg"

            with pytest.raises(EncodingError):
                wrapper.run(["-i", "nonexistent.mkv", "output.mkv"])


class TestFFmpegProgress:
    """Test FFmpegProgress class."""

    def test_progress_creation(self):
        """Test creating progress object."""
        progress = FFmpegProgress(
            frame=1234,
            fps=45.2,
            size_kb=12345,
            time="00:01:23.45",
            bitrate=1234.5,
            speed=1.5,
        )

        assert progress.frame == 1234
        assert progress.fps == 45.2
        assert progress.size_kb == 12345
        assert progress.time == "00:01:23.45"
        assert progress.bitrate == 1234.5
        assert progress.speed == 1.5

    def test_progress_repr(self):
        """Test progress string representation."""
        progress = FFmpegProgress(frame=100, fps=30.0, bitrate=1000.0)
        repr_str = repr(progress)

        assert "frame=100" in repr_str
        assert "fps=30.0" in repr_str
        assert "bitrate=1000.0" in repr_str

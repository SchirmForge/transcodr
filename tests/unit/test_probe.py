"""Unit tests for probe helpers."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from src.core.probe import ProbeHelper, MediaInfo, StreamInfo
from src.core.errors import ValidationError


class TestProbeHelper:
    """Test probe helper functionality."""

    @pytest.fixture
    def sample_probe_output(self):
        """Sample ffprobe JSON output."""
        return {
            "streams": [
                {
                    "index": 0,
                    "codec_name": "h264",
                    "codec_type": "video",
                    "codec_long_name": "H.264 / AVC / MPEG-4 AVC",
                    "width": 1920,
                    "height": 1080,
                    "pix_fmt": "yuv420p",
                    "r_frame_rate": "30/1",
                    "bit_rate": "5000000",
                },
                {
                    "index": 1,
                    "codec_name": "aac",
                    "codec_type": "audio",
                    "codec_long_name": "AAC (Advanced Audio Coding)",
                    "sample_rate": "48000",
                    "channels": 2,
                    "channel_layout": "stereo",
                },
            ],
            "format": {
                "filename": "test.mp4",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "format_long_name": "QuickTime / MOV",
                "duration": "120.5",
                "size": "75000000",
                "bit_rate": "5000000",
            },
        }

    def test_get_info_success(self, sample_probe_output, tmp_path):
        """Test getting media info."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            info = probe.get_info(test_file)

            assert isinstance(info, MediaInfo)
            assert info.duration == 120.5
            assert info.format_name == "mov,mp4,m4a,3gp,3g2,mj2"
            assert len(info.streams) == 2

    def test_get_info_file_not_found(self):
        """Test probing non-existent file."""
        probe = ProbeHelper()

        with pytest.raises(ValidationError, match="File not found"):
            probe.get_info(Path("/nonexistent/file.mp4"))

    def test_get_video_codec(self, sample_probe_output, tmp_path):
        """Test getting video codec."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            codec = probe.get_video_codec(test_file)

            assert codec == "h264"

    def test_get_audio_codec(self, sample_probe_output, tmp_path):
        """Test getting audio codec."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            codec = probe.get_audio_codec(test_file)

            assert codec == "aac"

    def test_get_resolution(self, sample_probe_output, tmp_path):
        """Test getting video resolution."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            resolution = probe.get_resolution(test_file)

            assert resolution == (1920, 1080)

    def test_validate_file_valid(self, sample_probe_output, tmp_path):
        """Test validating a valid file."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            assert probe.validate_file(test_file) is True

    def test_validate_file_invalid(self, tmp_path):
        """Test validating an invalid file."""
        test_file = tmp_path / "invalid.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Invalid file")

            probe = ProbeHelper()
            assert probe.validate_file(test_file) is False

    def test_compare_durations_match(self, sample_probe_output, tmp_path):
        """Test comparing durations that match."""
        file1 = tmp_path / "file1.mp4"
        file2 = tmp_path / "file2.mp4"
        file1.touch()
        file2.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            assert probe.compare_durations(file1, file2, tolerance_percent=1.0) is True

    def test_compare_durations_mismatch(self, sample_probe_output, tmp_path):
        """Test comparing durations that don't match."""
        file1 = tmp_path / "file1.mp4"
        file2 = tmp_path / "file2.mp4"
        file1.touch()
        file2.touch()

        probe_output_2 = sample_probe_output.copy()
        probe_output_2["format"]["duration"] = "100.0"  # Significant difference

        with patch("subprocess.run") as mock_run:
            # Return different durations for each file
            mock_run.side_effect = [
                MagicMock(stdout=json.dumps(sample_probe_output)),
                MagicMock(stdout=json.dumps(probe_output_2)),
            ]

            probe = ProbeHelper()
            assert probe.compare_durations(file1, file2, tolerance_percent=1.0) is False

    def test_estimate_frame_count(self, sample_probe_output, tmp_path):
        """Test estimating frame count."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(sample_probe_output)
            mock_run.return_value = mock_result

            probe = ProbeHelper()
            frame_count = probe.estimate_frame_count(test_file)

            # duration=120.5s, fps=30 -> ~3615 frames
            assert frame_count is not None
            assert 3600 <= frame_count <= 3630


class TestMediaInfo:
    """Test MediaInfo class."""

    def test_media_info_creation(self):
        """Test creating MediaInfo from probe data."""
        data = {
            "streams": [
                {
                    "index": 0,
                    "codec_name": "h264",
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                },
            ],
            "format": {
                "filename": "test.mp4",
                "format_name": "mp4",
                "duration": "120.0",
                "size": "10000000",
            },
        }

        info = MediaInfo(data)

        assert info.duration == 120.0
        assert info.size == 10000000
        assert len(info.streams) == 1

    def test_get_video_streams(self):
        """Test getting video streams."""
        data = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {"codec_type": "audio", "codec_name": "aac"},
                {"codec_type": "video", "codec_name": "h264"},
            ],
            "format": {},
        }

        info = MediaInfo(data)
        video_streams = info.get_video_streams()

        assert len(video_streams) == 2
        assert all(s.codec_type == "video" for s in video_streams)

    def test_get_audio_streams(self):
        """Test getting audio streams."""
        data = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {"codec_type": "audio", "codec_name": "aac"},
                {"codec_type": "audio", "codec_name": "opus"},
            ],
            "format": {},
        }

        info = MediaInfo(data)
        audio_streams = info.get_audio_streams()

        assert len(audio_streams) == 2
        assert all(s.codec_type == "audio" for s in audio_streams)

    def test_get_primary_streams(self):
        """Test getting primary video and audio streams."""
        data = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {},
        }

        info = MediaInfo(data)

        assert info.get_primary_video_stream().codec_name == "h264"
        assert info.get_primary_audio_stream().codec_name == "aac"


class TestStreamInfo:
    """Test StreamInfo class."""

    def test_video_stream_info(self):
        """Test creating video stream info."""
        data = {
            "index": 0,
            "codec_name": "h264",
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
        }

        stream = StreamInfo(data)

        assert stream.codec_name == "h264"
        assert stream.codec_type == "video"
        assert stream.width == 1920
        assert stream.height == 1080
        assert stream.pix_fmt == "yuv420p"

    def test_audio_stream_info(self):
        """Test creating audio stream info."""
        data = {
            "index": 1,
            "codec_name": "aac",
            "codec_type": "audio",
            "sample_rate": "48000",
            "channels": 2,
            "channel_layout": "stereo",
        }

        stream = StreamInfo(data)

        assert stream.codec_name == "aac"
        assert stream.codec_type == "audio"
        assert stream.sample_rate == "48000"
        assert stream.channels == 2

"""Unit tests for FFmpeg subtitle argument generation."""

from src.profiles.schema import AudioSettings, Profile, SubtitleSettings, VideoSettings


def _make_profile() -> Profile:
    return Profile(
        name="test-profile",
        container="mkv",
        video=VideoSettings(codec="libx265"),
        audio=AudioSettings(copy=True, all=True),
        subtitles=SubtitleSettings(copy=True, all=True),
    )


def test_external_subtitle_inputs_and_metadata_with_internal_override():
    profile = _make_profile()

    args = profile.to_ffmpeg_args(
        input_path="input.mkv",
        output_path="output.mkv",
        external_subtitles=[
            ("/tmp/input.en.srt", "eng"),
            ("/tmp/input.fr.srt", "fre"),
        ],
        subtitle_map_overrides=["0:2?"],
        external_subtitle_codec_overrides=[(1, "mov_text")],
    )

    # Inputs
    assert args[:6] == ["-i", "input.mkv", "-i", "/tmp/input.en.srt", "-i", "/tmp/input.fr.srt"]

    # Mapping includes internal override + both external subtitle inputs
    assert "0:2?" in args
    assert "1:s:0?" in args
    assert "2:s:0?" in args

    # Language metadata starts after 1 internal subtitle map
    assert "-metadata:s:s:1" in args
    assert "language=eng" in args
    assert "-metadata:s:s:2" in args
    assert "language=fre" in args
    assert "-c:s:1" in args
    assert "mov_text" in args


def test_external_subtitle_metadata_when_no_internal_subtitles_selected():
    profile = _make_profile()

    args = profile.to_ffmpeg_args(
        input_path="input.mkv",
        output_path="output.mkv",
        external_subtitles=[("/tmp/input.en.srt", "eng")],
        subtitle_map_overrides=[],
    )

    assert "1:s:0?" in args
    assert "-metadata:s:s:0" in args
    assert "language=eng" in args

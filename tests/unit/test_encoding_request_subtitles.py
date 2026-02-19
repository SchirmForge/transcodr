"""Unit tests for EncodingRequest subtitle fields."""

from src.api.models import EncodingRequest


def test_encoding_request_subtitles_language_normalization():
    request = EncodingRequest(
        source="/tmp/input.mkv",
        profiles=["x265-balanced"],
        subtitles_languages=["en", "french", "spa"],
    )
    assert request.subtitles_languages == ["eng", "fre", "spa"]


def test_encoding_request_subtitles_languages_all_default():
    request = EncodingRequest(
        source="/tmp/input.mkv",
        profiles=["x265-balanced"],
    )
    assert request.subtitles_languages == "all"
    assert request.auto_embed_subtitles is True
    assert request.subtitle_fallback_mode == "carry"


def test_encoding_request_subtitle_fallback_mode_normalization():
    request = EncodingRequest(
        source="/tmp/input.mkv",
        profiles=["x265-balanced"],
        subtitle_fallback_mode="SKIP",
    )
    assert request.subtitle_fallback_mode == "skip"

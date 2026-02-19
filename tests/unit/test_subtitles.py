"""Unit tests for subtitle helpers."""

from pathlib import Path

from src.core.subtitles import (
    FfmpegSubtitleCapabilities,
    detect_external_subtitles,
    evaluate_professional_subtitle_embedding,
    infer_language_from_filename,
    is_professional_subtitle_file,
    normalize_language_code,
    parse_subtitle_fallback_mode,
    parse_requested_subtitle_languages,
    should_include_subtitle_language,
)


def test_parse_requested_subtitle_languages():
    assert parse_requested_subtitle_languages("all") is None
    assert parse_requested_subtitle_languages(["eng", "fr", "english"]) == ["eng", "fre"]
    assert parse_requested_subtitle_languages("en, fre spa") == ["eng", "fre", "spa"]


def test_infer_language_from_filename():
    assert infer_language_from_filename(Path("movie.en.srt")) == "eng"
    assert infer_language_from_filename(Path("movie.english.srt")) == "eng"
    assert infer_language_from_filename(Path("movie.fr.vtt")) == "fre"
    assert infer_language_from_filename(Path("movie.srt")) == "und"


def test_detect_external_subtitles_exact_and_idx_sub_pair(tmp_path: Path):
    source = tmp_path / "movie.mkv"
    source.write_text("video")

    (tmp_path / "movie.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    (tmp_path / "movie.en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    (tmp_path / "movie.fr.vtt").write_text("WEBVTT")
    (tmp_path / "movie.idx").write_text("IDX")
    (tmp_path / "movie.sub").write_text("SUB")
    (tmp_path / "unrelated.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nNope\n")

    detected = detect_external_subtitles(source)
    names = [s.path.name for s in detected]
    langs = {s.path.name: s.language for s in detected}

    assert "movie.srt" in names
    assert "movie.en.srt" in names
    assert "movie.fr.vtt" in names
    assert "movie.idx" in names
    assert "movie.sub" not in names  # paired with .idx, should not be duplicated
    assert "unrelated.srt" not in names

    assert langs["movie.en.srt"] == "eng"
    assert langs["movie.fr.vtt"] == "fre"
    assert langs["movie.srt"] == "und"


def test_detect_external_subtitles_conservative_fuzzy(tmp_path: Path):
    source = tmp_path / "Big.Buck.Bunny.mkv"
    source.write_text("video")
    (tmp_path / "Bunny.Big.en.srt").write_text("subtitle")

    detected = detect_external_subtitles(source)
    names = [s.path.name for s in detected]
    assert "Bunny.Big.en.srt" in names


def test_should_include_unknown_with_language_filter():
    selected = {"eng", "fre"}
    assert should_include_subtitle_language("eng", selected)
    assert should_include_subtitle_language("fre", selected)
    assert should_include_subtitle_language("und", selected)
    assert not should_include_subtitle_language("spa", selected)


def test_normalize_language_code():
    assert normalize_language_code("en") == "eng"
    assert normalize_language_code("fre") == "fre"
    assert normalize_language_code("french") == "fre"
    assert normalize_language_code("xyz") == "xyz"


def test_parse_subtitle_fallback_mode():
    assert parse_subtitle_fallback_mode(None) == "carry"
    assert parse_subtitle_fallback_mode("SKIP") == "skip"
    assert parse_subtitle_fallback_mode("fail") == "fail"


def test_is_professional_subtitle_file():
    assert is_professional_subtitle_file(Path("movie.stl"))
    assert is_professional_subtitle_file(Path("movie.ttml"))
    assert is_professional_subtitle_file(Path("movie.imsc"))
    assert not is_professional_subtitle_file(Path("movie.srt"))


def test_evaluate_professional_subtitle_embedding_success():
    caps = FfmpegSubtitleCapabilities(
        decode_formats=frozenset({"stl", "ttml"}),
        encode_formats=frozenset({"srt", "mov_text"}),
        encode_codecs=frozenset({"subrip", "mov_text"}),
    )

    decision = evaluate_professional_subtitle_embedding(
        Path("movie.stl"),
        container="mkv",
        ffmpeg_caps=caps,
        profile_subtitle_codec=None,
    )
    assert decision.embeddable is True
    assert decision.codec_override == "srt"


def test_evaluate_professional_subtitle_embedding_failure():
    caps = FfmpegSubtitleCapabilities(
        decode_formats=frozenset({"stl"}),
        encode_formats=frozenset({"mov_text"}),
        encode_codecs=frozenset({"mov_text"}),
    )

    decision = evaluate_professional_subtitle_embedding(
        Path("movie.ttml"),
        container="mkv",
        ffmpeg_caps=caps,
        profile_subtitle_codec=None,
    )
    assert decision.embeddable is False
    assert decision.reason is not None

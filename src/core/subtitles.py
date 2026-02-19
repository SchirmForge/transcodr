"""Subtitle language and sidecar detection helpers."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence

# Supported sidecar subtitle formats for v0.4.1 phase 1.
SUPPORTED_EXTERNAL_SUBTITLE_EXTENSIONS = {
    ".srt",
    ".ass",
    ".ssa",
    ".vtt",
    ".sub",
    ".idx",
    ".stl",
    ".ttml",
    ".imsc",
    ".xml",
}

PROFESSIONAL_SUBTITLE_EXTENSIONS = {
    ".stl",
    ".ttml",
    ".imsc",
    ".xml",
}

PROFESSIONAL_FORMAT_BY_EXTENSION = {
    ".stl": "stl",
    ".ttml": "ttml",
    ".imsc": "ttml",
    ".xml": "ttml",
}

DEFAULT_PROFESSIONAL_TARGET_CODEC_BY_CONTAINER = {
    "mkv": "srt",
    "mp4": "mov_text",
    "webm": "webvtt",
    "avi": "srt",
}

SUBTITLE_CODEC_ENCODER_ALIASES = {
    "srt": {"srt", "subrip"},
    "subrip": {"srt", "subrip"},
    "mov_text": {"mov_text"},
    "webvtt": {"webvtt"},
    "ass": {"ass", "ssa"},
    "ssa": {"ass", "ssa"},
    "ttml": {"ttml"},
}

LANGUAGE_ALIASES = {
    "en": "eng",
    "eng": "eng",
    "english": "eng",
    "fr": "fre",
    "fra": "fre",
    "fre": "fre",
    "french": "fre",
    "es": "spa",
    "spa": "spa",
    "spanish": "spa",
    "de": "ger",
    "deu": "ger",
    "ger": "ger",
    "german": "ger",
    "it": "ita",
    "ita": "ita",
    "italian": "ita",
    "pt": "por",
    "por": "por",
    "portuguese": "por",
    "ja": "jpn",
    "jpn": "jpn",
    "japanese": "jpn",
    "zh": "chi",
    "chi": "chi",
    "chinese": "chi",
    "ko": "kor",
    "kor": "kor",
    "korean": "kor",
    "ru": "rus",
    "rus": "rus",
    "russian": "rus",
    "ar": "ara",
    "ara": "ara",
    "arabic": "ara",
    "nl": "dut",
    "nld": "dut",
    "dut": "dut",
    "dutch": "dut",
    "pl": "pol",
    "pol": "pol",
    "polish": "pol",
    "sv": "swe",
    "swe": "swe",
    "swedish": "swe",
    "und": "und",
    "unknown": "und",
}

LANGUAGE_TOKENS = set(LANGUAGE_ALIASES.keys()) | set(LANGUAGE_ALIASES.values())


@dataclass(frozen=True)
class DetectedSubtitle:
    """Detected external subtitle file and inferred language."""

    path: Path
    language: str


@dataclass(frozen=True)
class ExternalSubtitleDecision:
    """Decision for one external subtitle candidate."""

    embeddable: bool
    reason: Optional[str] = None
    codec_override: Optional[str] = None


@dataclass(frozen=True)
class FfmpegSubtitleCapabilities:
    """FFmpeg subtitle demuxing/encoding capabilities."""

    decode_formats: frozenset[str]
    encode_formats: frozenset[str]
    encode_codecs: frozenset[str]

    def can_decode_format(self, format_name: str) -> bool:
        return format_name in self.decode_formats

    def can_encode_codec(self, codec_name: str) -> bool:
        aliases = SUBTITLE_CODEC_ENCODER_ALIASES.get(codec_name, {codec_name})
        return any(alias in self.encode_codecs for alias in aliases)


def normalize_language_code(value: Optional[str]) -> Optional[str]:
    """Normalize a language token to a 3-letter code."""
    if value is None:
        return None

    token = str(value).strip().lower()
    if not token:
        return None

    token = token.replace("_", "-")
    if token in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[token]

    no_dash = token.replace("-", "")
    if no_dash in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[no_dash]

    if len(token) == 3 and token.isalpha():
        return token

    return None


def parse_requested_subtitle_languages(
    value: Optional[str | Sequence[str]],
) -> Optional[list[str]]:
    """
    Parse requested subtitle languages.

    Returns:
        None for "all", otherwise list of normalized 3-letter language codes.
    """
    if value is None:
        return None

    tokens: list[str] = []
    if isinstance(value, str):
        raw = value.strip()
        if not raw or raw.lower() == "all":
            return None
        tokens = [part for part in re.split(r"[\s,;]+", raw) if part]
    else:
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                tokens.append(text)

    if not tokens:
        raise ValueError("subtitles_languages cannot be empty")

    normalized: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token.lower() == "all":
            return None
        code = normalize_language_code(token)
        if not code:
            raise ValueError(f"Invalid subtitle language: {token}")
        if code not in seen:
            seen.add(code)
            normalized.append(code)

    return normalized


def parse_subtitle_fallback_mode(value: Optional[str]) -> str:
    """Normalize subtitle fallback mode."""
    token = (value or "carry").strip().lower()
    if token not in {"carry", "skip", "fail"}:
        raise ValueError("subtitle_fallback_mode must be one of: carry, skip, fail")
    return token


def should_include_subtitle_language(
    language: str,
    selected_languages: Optional[set[str]],
) -> bool:
    """Check if subtitle language should be included for current filter."""
    if selected_languages is None:
        return True
    return language == "und" or language in selected_languages


def infer_language_from_filename(file_path: Path) -> str:
    """Infer subtitle language from filename tokens."""
    stem = file_path.stem.lower()
    tokens = [t for t in re.split(r"[.\-_ ]+", stem) if t]

    for token in reversed(tokens):
        code = normalize_language_code(token)
        if code:
            return code

    return "und"


def detect_external_subtitles(source_path: Path) -> list[DetectedSubtitle]:
    """Detect likely subtitle sidecars for a source media file."""
    source_dir = source_path.parent
    source_stem = source_path.stem.lower()
    source_tokens = _name_tokens(source_stem)

    exact_matches: list[Path] = []
    fuzzy_matches: list[Path] = []

    for candidate in sorted(source_dir.iterdir(), key=lambda p: p.name.lower()):
        if not candidate.is_file():
            continue

        ext = candidate.suffix.lower()
        if ext not in SUPPORTED_EXTERNAL_SUBTITLE_EXTENSIONS:
            continue

        # Keep idx/sub as a single stream input: prefer .idx when paired.
        if ext == ".sub" and candidate.with_suffix(".idx").exists():
            continue

        candidate_stem = candidate.stem.lower()
        if _is_exact_subtitle_match(source_stem, candidate_stem):
            exact_matches.append(candidate)
        elif _is_conservative_fuzzy_match(source_tokens, _name_tokens(candidate_stem)):
            fuzzy_matches.append(candidate)

    seen: set[Path] = set()
    results: list[DetectedSubtitle] = []
    for path in [*exact_matches, *fuzzy_matches]:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        results.append(DetectedSubtitle(path=path, language=infer_language_from_filename(path)))

    return results


def is_professional_subtitle_file(path: Path) -> bool:
    """Check if subtitle file is a professional format handled in phase 2."""
    return path.suffix.lower() in PROFESSIONAL_SUBTITLE_EXTENSIONS


def evaluate_professional_subtitle_embedding(
    subtitle_path: Path,
    *,
    container: str,
    ffmpeg_caps: FfmpegSubtitleCapabilities,
    profile_subtitle_codec: Optional[str],
) -> ExternalSubtitleDecision:
    """Evaluate whether a professional subtitle can be embedded."""
    ext = subtitle_path.suffix.lower()
    format_name = PROFESSIONAL_FORMAT_BY_EXTENSION.get(ext)
    if not format_name:
        return ExternalSubtitleDecision(embeddable=True)

    if not ffmpeg_caps.can_decode_format(format_name):
        return ExternalSubtitleDecision(
            embeddable=False,
            reason=f"ffmpeg cannot decode {format_name}",
        )

    codec = profile_subtitle_codec or DEFAULT_PROFESSIONAL_TARGET_CODEC_BY_CONTAINER.get(container)
    if not codec:
        return ExternalSubtitleDecision(
            embeddable=False,
            reason=f"no target subtitle codec for container {container}",
        )

    if not ffmpeg_caps.can_encode_codec(codec):
        return ExternalSubtitleDecision(
            embeddable=False,
            reason=f"ffmpeg cannot encode subtitle codec {codec}",
        )

    return ExternalSubtitleDecision(embeddable=True, codec_override=codec)


@lru_cache(maxsize=8)
def detect_ffmpeg_subtitle_capabilities(ffmpeg_binary: str = "ffmpeg") -> FfmpegSubtitleCapabilities:
    """Detect FFmpeg subtitle-related format and codec capabilities."""
    decode_formats: set[str] = set()
    encode_formats: set[str] = set()
    encode_codecs: set[str] = set()

    try:
        formats_output = subprocess.check_output(
            [ffmpeg_binary, "-hide_banner", "-formats"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        formats_output = ""

    format_pattern = re.compile(r"^\s([D ])([E ])\s+([a-zA-Z0-9_,]+)\s")
    for line in formats_output.splitlines():
        match = format_pattern.match(line)
        if not match:
            continue
        can_decode = match.group(1) == "D"
        can_encode = match.group(2) == "E"
        names = [name.strip() for name in match.group(3).split(",") if name.strip()]
        for name in names:
            if can_decode:
                decode_formats.add(name)
            if can_encode:
                encode_formats.add(name)

    try:
        codecs_output = subprocess.check_output(
            [ffmpeg_binary, "-hide_banner", "-codecs"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        codecs_output = ""

    for line in codecs_output.splitlines():
        text = line.strip()
        if len(text) < 7:
            continue
        flags = text[:6]
        if len(flags) < 3:
            continue
        is_subtitle = flags[2] == "S"
        can_encode = flags[1] == "E"
        if not (is_subtitle and can_encode):
            continue

        parts = text.split()
        if len(parts) >= 2:
            encode_codecs.add(parts[1])

    return FfmpegSubtitleCapabilities(
        decode_formats=frozenset(decode_formats),
        encode_formats=frozenset(encode_formats),
        encode_codecs=frozenset(encode_codecs),
    )


def _is_exact_subtitle_match(source_stem: str, candidate_stem: str) -> bool:
    if candidate_stem == source_stem:
        return True
    return any(
        candidate_stem.startswith(source_stem + sep)
        for sep in (".", "_", "-", " ")
    )


def _name_tokens(name: str) -> set[str]:
    raw = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]
    return {t for t in raw if t not in LANGUAGE_TOKENS}


def _is_conservative_fuzzy_match(source_tokens: set[str], candidate_tokens: set[str]) -> bool:
    if not source_tokens or not candidate_tokens:
        return False

    common = source_tokens & candidate_tokens
    if len(common) < 2:
        return False

    overlap = len(common) / float(len(source_tokens))
    return overlap >= 0.6

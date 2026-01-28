"""Core functionality for video transcoding."""

from .ffmpeg import FFmpegWrapper
from .hardware import HardwareCapabilities, detect_hardware_accel
from .errors import (
    TranscodeError,
    FFmpegNotFoundError,
    ValidationError,
    InsufficientSpaceError,
    EncodingError,
    CorruptedOutputError,
    ReplacementError,
)

__all__ = [
    "FFmpegWrapper",
    "HardwareCapabilities",
    "detect_hardware_accel",
    "TranscodeError",
    "FFmpegNotFoundError",
    "ValidationError",
    "InsufficientSpaceError",
    "EncodingError",
    "CorruptedOutputError",
    "ReplacementError",
]

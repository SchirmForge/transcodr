"""Exception types for video transcoding operations."""


class TranscodeError(Exception):
    """Base exception for all transcoding errors."""
    pass


class FFmpegNotFoundError(TranscodeError):
    """FFmpeg binary not found or not executable."""
    pass


class ValidationError(TranscodeError):
    """Pre-flight validation failed."""
    pass


class InsufficientSpaceError(TranscodeError):
    """Not enough disk space for transcoding operation."""
    pass


class EncodingError(TranscodeError):
    """FFmpeg encoding process failed."""
    pass


class CorruptedOutputError(TranscodeError):
    """Output file validation failed (corrupt or incomplete)."""
    pass


class ReplacementError(TranscodeError):
    """File replacement operation failed."""
    pass


class TemporaryIOError(TranscodeError):
    """Temporary I/O error (retryable)."""
    pass

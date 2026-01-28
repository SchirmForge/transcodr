"""Profile schema definitions using Pydantic."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class VideoSettings(BaseModel):
    """Video encoding settings."""

    codec: str = Field(description="Video codec (e.g., libx265, h264_vaapi)")
    crf: Optional[int] = Field(default=None, description="Constant Rate Factor (for CRF mode)")
    bitrate: Optional[str] = Field(default=None, description="Target bitrate (e.g., '5M', '2000k')")
    preset: Optional[str] = Field(default=None, description="Encoding preset (e.g., slow, medium, fast)")
    pix_fmt: Optional[str] = Field(default=None, description="Pixel format (e.g., yuv420p, yuv420p10le)")
    tune: Optional[str] = Field(default=None, description="Tuning option (e.g., film, animation)")
    profile: Optional[str] = Field(default=None, description="Codec profile (e.g., main, high)")
    level: Optional[str] = Field(default=None, description="Codec level (e.g., 4.0, 5.1)")
    max_bitrate: Optional[str] = Field(default=None, description="Maximum bitrate for VBR")
    bufsize: Optional[str] = Field(default=None, description="Buffer size for rate control")

    # Hardware acceleration
    hwaccel: Optional[str] = Field(default=None, description="Hardware acceleration method (vaapi, cuda, qsv)")
    hwaccel_device: Optional[str] = Field(default=None, description="Hardware device path (e.g., /dev/dri/renderD128)")

    # Additional options (passed as-is to FFmpeg)
    extra_options: dict[str, str] = Field(
        default_factory=dict,
        description="Additional FFmpeg options as key-value pairs"
    )


class AudioSettings(BaseModel):
    """Audio encoding settings."""

    copy_streams: bool = Field(default=True, description="Copy audio stream without re-encoding", alias="copy")
    codec: Optional[str] = Field(default=None, description="Audio codec (e.g., aac, opus, libmp3lame)")
    bitrate: Optional[str] = Field(default=None, description="Audio bitrate (e.g., '192k', '128k')")
    sample_rate: Optional[int] = Field(default=None, description="Audio sample rate (e.g., 48000, 44100)")
    channels: Optional[int] = Field(default=None, description="Number of audio channels (e.g., 2 for stereo)")

    # Additional options
    extra_options: dict[str, str] = Field(
        default_factory=dict,
        description="Additional FFmpeg audio options"
    )

    model_config = {"populate_by_name": True}  # Allow both 'copy' and 'copy_streams'


class SubtitleSettings(BaseModel):
    """Subtitle handling settings."""

    copy_streams: bool = Field(default=True, description="Copy subtitle streams", alias="copy")
    codec: Optional[str] = Field(default=None, description="Subtitle codec (e.g., srt, ass)")

    model_config = {"populate_by_name": True}  # Allow both 'copy' and 'copy_streams'


class HardwareVariant(BaseModel):
    """Hardware-specific variant of a profile."""

    video: VideoSettings
    description: Optional[str] = Field(default=None, description="Description of this variant")


class Profile(BaseModel):
    """Complete encoding profile."""

    name: str = Field(description="Profile name (unique identifier)")
    description: Optional[str] = Field(default=None, description="Human-readable description")

    # Inheritance
    extends: Optional[str] = Field(default=None, description="Parent profile to inherit from")

    # Container format
    container: Literal["mkv", "mp4", "webm", "avi"] = Field(
        default="mkv",
        description="Output container format"
    )

    # Encoding settings
    video: VideoSettings
    audio: AudioSettings = Field(default_factory=AudioSettings)
    subtitles: SubtitleSettings = Field(default_factory=SubtitleSettings)

    # Hardware variants (optional)
    hardware_variants: Optional[dict[str, HardwareVariant]] = Field(
        default=None,
        description="Hardware-specific variants (vaapi, nvenc, qsv, etc.)"
    )

    # Performance settings
    recommended_concurrency: Optional[int] = Field(
        default=None,
        description="Recommended number of concurrent jobs for this profile (None = use global setting)"
    )

    # Metadata
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization (e.g., 'high-quality', 'fast', 'hdr')"
    )

    def to_ffmpeg_args(
        self,
        input_path: str,
        output_path: str,
        hardware_accel: Optional[str] = None,
    ) -> list[str]:
        """
        Convert profile to FFmpeg command arguments.

        Args:
            input_path: Input file path
            output_path: Output file path
            hardware_accel: Hardware acceleration to use (if available)

        Returns:
            List of FFmpeg arguments
        """
        args = []

        # Select video settings (hardware variant or default)
        video_settings = self.video
        if hardware_accel and self.hardware_variants:
            variant = self.hardware_variants.get(hardware_accel)
            if variant:
                video_settings = variant.video

        # Hardware acceleration (MUST be before -i for decode acceleration)
        if video_settings.hwaccel:
            args.extend(["-hwaccel", video_settings.hwaccel])
            if video_settings.hwaccel_device:
                args.extend(["-hwaccel_device", video_settings.hwaccel_device])

        # Input file
        args.extend(["-i", input_path])

        # VAAPI requires video filter to upload frames to GPU
        if video_settings.hwaccel == "vaapi" and "vaapi" in video_settings.codec.lower():
            args.extend(["-vf", "format=nv12,hwupload"])

        # Video codec
        args.extend(["-c:v", video_settings.codec])

        # Video encoding parameters
        if video_settings.crf is not None:
            args.extend(["-crf", str(video_settings.crf)])
        if video_settings.bitrate:
            args.extend(["-b:v", video_settings.bitrate])
        if video_settings.preset:
            args.extend(["-preset", video_settings.preset])
        # Don't set pix_fmt for hardware encoders (they handle it internally)
        if video_settings.pix_fmt and video_settings.hwaccel is None:
            args.extend(["-pix_fmt", video_settings.pix_fmt])
        if video_settings.tune:
            args.extend(["-tune", video_settings.tune])
        if video_settings.profile:
            args.extend(["-profile:v", video_settings.profile])
        if video_settings.level:
            args.extend(["-level:v", video_settings.level])
        if video_settings.max_bitrate:
            args.extend(["-maxrate", video_settings.max_bitrate])
        if video_settings.bufsize:
            args.extend(["-bufsize", video_settings.bufsize])

        # Video extra options
        for key, value in video_settings.extra_options.items():
            args.extend([f"-{key}", value])

        # Audio settings
        if self.audio.copy_streams:
            args.extend(["-c:a", "copy"])
        else:
            if self.audio.codec:
                args.extend(["-c:a", self.audio.codec])
            if self.audio.bitrate:
                args.extend(["-b:a", self.audio.bitrate])
            if self.audio.sample_rate:
                args.extend(["-ar", str(self.audio.sample_rate)])
            if self.audio.channels:
                args.extend(["-ac", str(self.audio.channels)])

            # Audio extra options
            for key, value in self.audio.extra_options.items():
                args.extend([f"-{key}", value])

        # Subtitle settings
        if self.subtitles.copy_streams:
            args.extend(["-c:s", "copy"])
        elif self.subtitles.codec:
            args.extend(["-c:s", self.subtitles.codec])

        # Output file
        args.append(output_path)

        return args

    def __repr__(self):
        hw_variants = list(self.hardware_variants.keys()) if self.hardware_variants else []
        return (
            f"Profile(name={self.name}, codec={self.video.codec}, "
            f"container={self.container}, hw_variants={hw_variants})"
        )

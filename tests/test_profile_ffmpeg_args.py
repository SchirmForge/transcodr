#!/usr/bin/env python3
"""Test FFmpeg argument generation for profiles."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.profiles.manager import ProfileManager


def main():
    """Test FFmpeg argument generation."""
    manager = ProfileManager()

    profile_name = "x265-balanced"
    profile = manager.load_profile(profile_name)

    print(f"Profile: {profile_name}")
    print(f"Description: {profile.description}")
    print()

    # Generate CPU command
    print("=" * 60)
    print("CPU Encoding (no hardware acceleration):")
    print("=" * 60)
    cpu_args = profile.to_ffmpeg_args(
        input_path="input.mp4",
        output_path="output.mkv",
        hardware_accel=None,
    )
    print("ffmpeg " + " ".join(cpu_args))
    print()

    # Generate VAAPI command
    print("=" * 60)
    print("VAAPI Encoding (AMD/Intel GPU):")
    print("=" * 60)
    vaapi_args = profile.to_ffmpeg_args(
        input_path="input.mp4",
        output_path="output.mkv",
        hardware_accel="vaapi",
    )
    print("ffmpeg " + " ".join(vaapi_args))
    print()

    # Check hardware variants
    if profile.hardware_variants:
        print("=" * 60)
        print("Available hardware variants:")
        print("=" * 60)
        for hw_type, variant in profile.hardware_variants.items():
            print(f"  {hw_type}:")
            print(f"    codec: {variant.video.codec}")
            print(f"    hwaccel: {variant.video.hwaccel}")
            if variant.video.extra_options:
                print(f"    extra_options: {variant.video.extra_options}")


if __name__ == "__main__":
    main()

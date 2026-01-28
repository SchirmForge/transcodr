#!/usr/bin/env python
"""
Manual test script for FFmpeg wrapper.

Run this script from the conda environment to verify FFmpeg integration:
    conda activate videotranscode
    python tests/manual_test_ffmpeg.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.ffmpeg import FFmpegWrapper
from src.core.hardware import HardwareCapabilities, get_gpu_info, get_vaapi_profiles
from src.core.logging import setup_logging

def main():
    """Test FFmpeg wrapper with actual FFmpeg binary."""
    print("=" * 60)
    print("Manual FFmpeg Wrapper Test")
    print("=" * 60)

    # Setup logging
    setup_logging(level="DEBUG", console=True)

    # Test 1: Version detection
    print("\n[TEST 1] FFmpeg Version Detection")
    print("-" * 60)
    try:
        wrapper = FFmpegWrapper()
        print(f"✓ FFmpeg detected: {wrapper.version}")
        print(f"✓ Version number: {wrapper.get_version_number()}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return 1

    # Test 2: Codec support
    print("\n[TEST 2] Codec Support Check")
    print("-" * 60)
    codecs_to_check = ["libx265", "h264", "aac", "opus", "nonexistent_codec"]
    for codec in codecs_to_check:
        supported = wrapper.supports_codec(codec)
        status = "✓" if supported else "✗"
        print(f"{status} {codec}: {'supported' if supported else 'not supported'}")

    # Test 3: Get encoders
    print("\n[TEST 3] Available Encoders")
    print("-" * 60)
    encoders = wrapper.get_encoders()
    print(f"Found {len(encoders)} encoders")

    # Show x265 family encoders
    x265_encoders = [e for e in encoders if 'x265' in e or 'hevc' in e]
    if x265_encoders:
        print("x265/HEVC encoders:")
        for encoder in x265_encoders[:5]:  # Show first 5
            print(f"  - {encoder}")
    else:
        print("⚠ No x265/HEVC encoders found")

    # Test 4: Get decoders
    print("\n[TEST 4] Available Decoders")
    print("-" * 60)
    decoders = wrapper.get_decoders()
    print(f"Found {len(decoders)} decoders")

    # Show h264/hevc decoders
    h264_decoders = [d for d in decoders if 'h264' in d or 'hevc' in d]
    if h264_decoders:
        print("H.264/HEVC decoders:")
        for decoder in h264_decoders[:5]:
            print(f"  - {decoder}")

    # Test 5: Hardware acceleration methods
    print("\n[TEST 5] Hardware Acceleration Methods")
    print("-" * 60)
    hwaccels = wrapper.get_hwaccels()
    print(f"Found {len(hwaccels)} hardware acceleration methods:")
    for hwaccel in hwaccels:
        print(f"  - {hwaccel}")

    # Test 6: Hardware encoders
    print("\n[TEST 6] Hardware Encoders")
    print("-" * 60)
    hw_encoders = wrapper.get_hardware_encoders()
    if hw_encoders:
        for hw_type, encoders in hw_encoders.items():
            print(f"{hw_type.upper()}: {len(encoders)} encoder(s)")
            for encoder in encoders[:3]:  # Show first 3
                print(f"  - {encoder}")
    else:
        print("⚠ No hardware encoders found")

    # Test 7: Hardware decoders
    print("\n[TEST 7] Hardware Decoders")
    print("-" * 60)
    hw_decoders = wrapper.get_hardware_decoders()
    if hw_decoders:
        for hw_type, decoders in hw_decoders.items():
            print(f"{hw_type.upper()}: {len(decoders)} decoder(s)")
            for decoder in decoders[:3]:  # Show first 3
                print(f"  - {decoder}")
    else:
        print("⚠ No hardware decoders found")

    # Test 8: System hardware detection
    print("\n[TEST 8] System Hardware Detection")
    print("-" * 60)
    hw_caps = HardwareCapabilities()
    print(f"Hardware capabilities: {hw_caps}")

    summary = hw_caps.get_summary()
    print("\nDetailed status:")
    print(f"  VAAPI:        {'✓ Available' if summary['vaapi'] else '✗ Not available'}")
    print(f"  NVIDIA NVENC: {'✓ Available' if summary['nvidia_nvenc'] else '✗ Not available'}")
    print(f"  AMD GPU:      {'✓ Available' if summary['amd_gpu'] else '✗ Not available'}")
    print(f"  Intel QSV:    {'✓ Available' if summary['intel_qsv'] else '✗ Not available'}")

    if summary['recommended']:
        print(f"\n  Recommended: {summary['recommended'].upper()}")
    else:
        print("\n  ⚠ No hardware acceleration recommended (CPU encoding only)")

    # Test 9: GPU information
    print("\n[TEST 9] GPU Information")
    print("-" * 60)
    gpu_info = get_gpu_info()

    if gpu_info['nvidia']:
        print("NVIDIA GPU:")
        print(f"  Name:    {gpu_info['nvidia']['name']}")
        print(f"  Driver:  {gpu_info['nvidia']['driver_version']}")
        print(f"  Memory:  {gpu_info['nvidia']['memory_total']}")

    if gpu_info['amd']:
        print("AMD GPU:")
        print(f"  {gpu_info['amd']['name']}")

    if gpu_info['intel']:
        print("Intel GPU:")
        print(f"  {gpu_info['intel']['name']}")

    if not any(gpu_info.values()):
        print("No detailed GPU information available")

    # Test 10: VAAPI profiles
    if summary['vaapi']:
        print("\n[TEST 10] VAAPI Profiles")
        print("-" * 60)
        vaapi_profiles = get_vaapi_profiles()
        if vaapi_profiles:
            print(f"Found {len(vaapi_profiles)} VAAPI profiles:")
            for profile in vaapi_profiles[:10]:  # Show first 10
                print(f"  - {profile}")
        else:
            print("⚠ Could not retrieve VAAPI profiles")

    # Test 11: Progress parsing
    print("\n[TEST 11] Progress Parsing")
    print("-" * 60)
    test_lines = [
        "frame= 1234 fps=45.2 q=28.0 size=  12345kB time=00:01:23.45 bitrate=1234.5kbits/s speed=1.5x",
        "Input #0, matroska,webm, from 'file.mkv':",
        "frame=  100 fps=30 size=1024kB time=00:00:03.33 bitrate=2500.0kbits/s",
    ]

    for line in test_lines:
        progress = wrapper._parse_progress(line)
        if progress:
            print(f"✓ Parsed: {progress}")
        else:
            print(f"  Skipped (not a progress line): {line[:50]}...")

    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())

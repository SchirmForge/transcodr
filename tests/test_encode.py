#!/usr/bin/env python3
"""
Test encoding workflow end-to-end.

This script tests the complete encoding pipeline:
1. List available profiles
2. Create a job
3. Execute encoding
4. Validate output
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logging import setup_logging
from src.profiles.manager import ProfileManager
from src.jobs.model import Job
from src.jobs.runner import JobRunner
from src.core.hardware import HardwareCapabilities


def print_section(title: str):
    """Print section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    """Run encoding test."""
    # Setup logging
    setup_logging(level="INFO", console=True)

    print_section("Video Encoding Test")

    # Check if input file provided
    if len(sys.argv) < 2:
        print("\nUsage: python tests/test_encode.py <input_video_file> [profile_name]")
        print("\nExample:")
        print("  python tests/test_encode.py sample.mp4 x265-balanced")
        print("\nThis will create a backup of the original in .originals/ directory")
        print("and replace the original file with the encoded version.\n")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    profile_name = sys.argv[2] if len(sys.argv) > 2 else "x265-balanced"

    if not input_file.exists():
        print(f"\n✗ Error: Input file not found: {input_file}")
        sys.exit(1)

    # Hardware detection
    print_section("Hardware Detection")
    hw = HardwareCapabilities()
    summary = hw.get_summary()

    print("Hardware capabilities:")
    print(f"  VAAPI:        {'✓' if summary['vaapi'] else '✗'}")
    print(f"  NVIDIA NVENC: {'✓' if summary['nvidia_nvenc'] else '✗'}")
    print(f"  AMD GPU:      {'✓' if summary['amd_gpu'] else '✗'}")
    print(f"  Intel QSV:    {'✓' if summary['intel_qsv'] else '✗'}")

    if summary['recommended']:
        print(f"\nRecommended: {summary['recommended'].upper()}")
    else:
        print("\n⚠ No hardware acceleration (will use CPU)")

    # List profiles
    print_section("Available Profiles")
    profile_manager = ProfileManager()
    profiles = profile_manager.list_profiles()

    print(f"Found {len(profiles)} profiles:")
    for p in profiles:
        info = profile_manager.get_profile_info(p)
        hw_variants = info.get('hardware_variants', [])
        hw_str = f" (HW: {', '.join(hw_variants)})" if hw_variants else ""
        print(f"  - {p}: {info.get('description', 'No description')}{hw_str}")

    # Check if profile exists
    if profile_name not in profiles:
        print(f"\n✗ Error: Profile '{profile_name}' not found")
        print(f"Available profiles: {', '.join(profiles)}")
        sys.exit(1)

    # Load profile
    print_section(f"Using Profile: {profile_name}")
    profile = profile_manager.load_profile(profile_name)
    print(f"Description: {profile.description}")
    print(f"Codec:       {profile.video.codec}")
    print(f"Container:   {profile.container}")
    if profile.video.crf:
        print(f"CRF:         {profile.video.crf}")
    if profile.video.preset:
        print(f"Preset:      {profile.video.preset}")

    if profile.hardware_variants:
        print(f"HW Variants: {', '.join(profile.hardware_variants.keys())}")

    # Confirm encoding
    print_section("Confirmation")
    print(f"Input file:  {input_file}")
    print(f"File size:   {input_file.stat().st_size / 1024**2:.1f} MB")
    print(f"Profile:     {profile_name}")
    print(f"\nBackup will be created in: {input_file.parent / '.originals'}")
    print(f"Original file will be REPLACED with encoded version.")

    response = input("\nProceed with encoding? [y/N]: ")
    if response.lower() != 'y':
        print("Encoding cancelled.")
        sys.exit(0)

    # Create job
    print_section("Creating Job")
    job = Job(
        source_path=input_file,
        profile_name=profile_name,
    )
    print(f"Job ID: {job.id}")
    print(f"State:  {job.state.value}")

    # Execute job
    print_section("Executing Job")
    runner = JobRunner()

    def on_progress(job: Job):
        """Display progress."""
        if job.state == JobState.RUNNING:
            progress_bar = "█" * int(job.progress_percent / 2)
            progress_bar = progress_bar.ljust(50)
            print(
                f"\rProgress: [{progress_bar}] {job.progress_percent:.1f}% | "
                f"Frame: {job.frames_processed}/{job.frames_total or '?'} | "
                f"FPS: {job.current_fps:.1f} | "
                f"ETA: {job.eta_seconds or '?'}s",
                end="",
                flush=True,
            )
        else:
            print(f"\nState: {job.state.value}")

    try:
        from src.jobs.model import JobState
        job = runner.execute(job, progress_callback=on_progress)
        print()  # Newline after progress

        # Results
        print_section("Results")
        print(f"Status:         {job.state.value}")
        print(f"Source codec:   {job.source_codec}")
        print(f"Output codec:   {job.output_codec}")
        print(f"Source size:    {job.source_size_bytes / 1024**2:.1f} MB")
        print(f"Output size:    {job.output_size_bytes / 1024**2:.1f} MB")
        print(f"Compression:    {job.output_size_bytes / job.source_size_bytes * 100:.1f}%")
        print(f"Space saved:    {(job.source_size_bytes - job.output_size_bytes) / 1024**2:.1f} MB")

        if job.state == JobState.COMPLETED:
            print("\n✓ Encoding completed successfully!")
            print(f"\nOriginal file has been replaced.")
            print(f"Backup location: {input_file.parent / '.originals' / f'{input_file.stem}.backup{input_file.suffix}'}")
        else:
            print(f"\n✗ Encoding failed: {job.error_message}")

    except KeyboardInterrupt:
        print("\n\n✗ Encoding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Encoding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

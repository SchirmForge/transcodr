#!/usr/bin/env python3
"""
Benchmark optimal concurrency for encoding.

Tests encoding performance with 1, 2, 3, ... N parallel jobs to find
the optimal number of concurrent encodes for your hardware.
"""

import sys
import time
import tempfile
import shutil
import subprocess
import atexit
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logging import setup_logging
from src.jobs import Job, JobRunner
from src.core.hardware import HardwareCapabilities


# Terminal state management
_terminal_state = None


def save_terminal_state():
    """Save current terminal state."""
    global _terminal_state
    try:
        result = subprocess.run(
            ["stty", "-g"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            _terminal_state = result.stdout.strip()
    except Exception:
        pass  # Not a terminal or stty not available


def restore_terminal_state():
    """Restore terminal state to saved state."""
    global _terminal_state
    if _terminal_state:
        try:
            subprocess.run(
                ["stty", _terminal_state],
                timeout=1,
                check=False
            )
        except Exception:
            pass


def reset_terminal():
    """Reset terminal to sane state."""
    try:
        subprocess.run(
            ["stty", "sane"],
            timeout=1,
            check=False
        )
    except Exception:
        pass


# Register terminal restoration on exit
atexit.register(restore_terminal_state)


def encode_test_file(job_runner: JobRunner, test_file: Path, profile_name: str, job_id: int) -> dict:
    """
    Encode a single test file and return timing info.

    Args:
        job_runner: Job runner instance
        test_file: Test file to encode
        profile_name: Profile to use
        job_id: Job identifier for logging

    Returns:
        Dict with timing and performance metrics
    """
    start_time = time.time()

    # Create job
    job = Job(
        source_path=test_file,
        profile_name=profile_name,
    )

    try:
        # Execute job
        job = job_runner.execute(job)

        end_time = time.time()
        duration = end_time - start_time

        return {
            "job_id": job_id,
            "success": job.state.value == "completed",
            "duration": duration,
            "fps": job.frames_processed / duration if duration > 0 else 0,
            "frames": job.frames_processed,
            "source_size_mb": job.source_size_bytes / 1024**2,
            "output_size_mb": job.output_size_bytes / 1024**2,
            "compression_ratio": job.output_size_bytes / job.source_size_bytes if job.source_size_bytes > 0 else 0,
        }
    except Exception as e:
        end_time = time.time()
        return {
            "job_id": job_id,
            "success": False,
            "duration": end_time - start_time,
            "error": str(e),
        }


def run_concurrent_test(
    test_files: list[Path],
    profile_name: str,
    concurrency: int,
) -> dict:
    """
    Run encoding test with specified concurrency level.

    Args:
        test_files: List of test files to encode
        profile_name: Profile to use
        concurrency: Number of concurrent jobs

    Returns:
        Dict with aggregate performance metrics
    """
    print(f"\nTesting with {concurrency} concurrent job(s)...")

    job_runner = JobRunner()
    results = []

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for i, test_file in enumerate(test_files[:concurrency]):
            future = executor.submit(encode_test_file, job_runner, test_file, profile_name, i + 1)
            futures.append(future)

        # Collect results
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["success"]:
                print(f"  Job {result['job_id']}: {result['duration']:.1f}s ({result['fps']:.1f} fps)")
            else:
                print(f"  Job {result['job_id']}: FAILED - {result.get('error', 'Unknown error')}")

    end_time = time.time()
    total_duration = end_time - start_time

    # Calculate aggregate metrics
    successful_results = [r for r in results if r["success"]]

    if not successful_results:
        return {
            "concurrency": concurrency,
            "success": False,
            "total_duration": total_duration,
        }

    return {
        "concurrency": concurrency,
        "success": True,
        "total_duration": total_duration,
        "avg_job_duration": statistics.mean([r["duration"] for r in successful_results]),
        "total_frames": sum([r["frames"] for r in successful_results]),
        "avg_fps": statistics.mean([r["fps"] for r in successful_results]),
        "throughput_fps": sum([r["frames"] for r in successful_results]) / total_duration,
        "jobs_completed": len(successful_results),
        "jobs_failed": len(results) - len(successful_results),
    }


def extract_clip_from_video(source_video: Path, duration: int = 10) -> Optional[Path]:
    """
    Extract a clip from source video for benchmarking.

    Extracts from middle of video, or at 5-minute mark for long videos.

    Args:
        source_video: Source video path
        duration: Clip duration in seconds

    Returns:
        Path to extracted clip or None on failure
    """
    import subprocess
    from src.core.probe import ProbeHelper

    print(f"\nExtracting {duration}s clip from: {source_video.name}")

    # Get video duration
    probe = ProbeHelper()
    try:
        video_duration = probe.get_duration(source_video)
    except Exception as e:
        print(f"  ✗ Failed to probe source video: {e}")
        return None

    # Determine start time
    if video_duration < duration:
        print(f"  ⚠ Source video is shorter than {duration}s, using entire video")
        start_time = 0
    elif video_duration > 600:  # > 10 minutes
        # For long videos (movies), extract from 5-minute mark
        start_time = 300
        print(f"  Source duration: {video_duration:.0f}s (long video)")
        print(f"  Extracting from 5:00 mark")
    else:
        # For shorter videos, extract from middle
        start_time = (video_duration - duration) / 2
        print(f"  Source duration: {video_duration:.0f}s")
        print(f"  Extracting from middle ({start_time:.0f}s mark)")

    # Create temp directory
    temp_dir = Path(tempfile.gettempdir()) / "videotranscode_benchmark"
    temp_dir.mkdir(exist_ok=True)

    # Output path
    clip_path = temp_dir / f"source_clip.mkv"

    # Extract clip with FFmpeg (copy streams for fast extraction)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", str(source_video),
        "-t", str(duration),
        "-c", "copy",  # Copy streams without re-encoding
        str(clip_path)
    ]

    print(f"  Extracting clip...")
    result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ Failed to extract clip")
        return None

    print(f"  ✓ Clip extracted: {clip_path.name} ({clip_path.stat().st_size / 1024**2:.1f} MB)")
    return clip_path


def create_test_files(count: int, duration: int = 10, source_video: Optional[Path] = None) -> list[Path]:
    """
    Create test video files for benchmarking.

    Args:
        count: Number of test files to create
        duration: Duration of each test file in seconds
        source_video: Optional source video to extract clips from (more realistic)

    Returns:
        List of paths to created test files
    """
    temp_dir = Path(tempfile.gettempdir()) / "videotranscode_benchmark"
    temp_dir.mkdir(exist_ok=True)

    # If source video provided, extract clip and make copies
    if source_video:
        clip = extract_clip_from_video(source_video, duration)
        if not clip:
            print("  ⚠ Falling back to generated test pattern")
            source_video = None
        else:
            # Create copies of the clip
            print(f"\nCreating {count} copies of extracted clip...")
            test_files = []
            for i in range(count):
                test_file = temp_dir / f"test_{i+1}.mkv"
                shutil.copy2(clip, test_file)
                test_files.append(test_file)
                print(f"  Created test file {i+1}: {test_file.name}")

            return test_files

    # Generate synthetic test pattern (fallback)
    print(f"\nCreating {count} test video files ({duration}s each)...")
    test_files = []

    for i in range(count):
        test_file = temp_dir / f"test_{i+1}.mp4"

        # Skip if already exists
        if test_file.exists():
            print(f"  Test file {i+1} already exists, skipping creation")
            test_files.append(test_file)
            continue

        # Create test video with FFmpeg
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=1280x720:rate=30",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(test_file)
        ]

        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Failed to create test file {i+1}")
            continue

        test_files.append(test_file)
        print(f"  Created test file {i+1}: {test_file.name} ({test_file.stat().st_size / 1024**2:.1f} MB)")

    return test_files


def print_results_table(all_results: list[dict], profile_name: str = "", test_duration: int = 10, source_video: Optional[Path] = None, max_concurrency: int = 4, clip_duration: Optional[int] = None):
    """Print results in a formatted table."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    print(f"\n{'Concurrency':<12} {'Duration':<12} {'Throughput':<15} {'Avg FPS':<12} {'Efficiency':<12}")
    print("-" * 80)

    baseline_throughput = None

    for result in all_results:
        if not result["success"]:
            print(f"{result['concurrency']:<12} {'FAILED':<12}")
            continue

        if baseline_throughput is None:
            baseline_throughput = result["throughput_fps"]

        efficiency = (result["throughput_fps"] / baseline_throughput) * 100 if baseline_throughput else 0

        print(
            f"{result['concurrency']:<12} "
            f"{result['total_duration']:.1f}s{'':<7} "
            f"{result['throughput_fps']:.1f} fps{'':<7} "
            f"{result['avg_fps']:.1f} fps{'':<4} "
            f"{efficiency:.0f}%"
        )

    # Find optimal concurrency
    successful_results = [r for r in all_results if r["success"]]
    if successful_results:
        optimal = max(successful_results, key=lambda r: r["throughput_fps"])
        print("\n" + "=" * 80)
        print(f"OPTIMAL CONCURRENCY: {optimal['concurrency']} concurrent job(s)")
        print(f"  Throughput: {optimal['throughput_fps']:.1f} fps")
        print(f"  Efficiency: {(optimal['throughput_fps'] / baseline_throughput * 100):.0f}% vs single job")

        # Check if efficiency is still climbing
        if optimal['concurrency'] == max_concurrency:
            last_efficiency = (optimal['throughput_fps'] / baseline_throughput) * 100
            if len(successful_results) >= 2:
                second_last = successful_results[-2]
                second_last_efficiency = (second_last['throughput_fps'] / baseline_throughput) * 100
                efficiency_gain = last_efficiency - second_last_efficiency

                if efficiency_gain > 1.0:  # Still gaining more than 1%
                    print("\n⚠ NOTE: Efficiency still increasing at max tested concurrency!")
                    print(f"  Last gain: +{efficiency_gain:.1f}%")
                    print(f"  Suggestion: Test higher concurrency (e.g., {max_concurrency + 4})")

                    # Build command with same options
                    cmd_parts = [
                        "python tests/benchmark_concurrency.py",
                        profile_name,
                        str(max_concurrency + 4),
                        str(test_duration)
                    ]
                    if source_video:
                        cmd_parts.extend(["--source", str(source_video)])
                        # Include clip-duration if it was different from test_duration
                        if clip_duration and clip_duration != test_duration:
                            cmd_parts.extend(["--clip-duration", str(clip_duration)])
                    cmd_parts.append("--cleanup")

                    print(f"  Command: {' '.join(cmd_parts)}")

        print("=" * 80)


def main():

    # TODO: Add argument parsing with argparse for better usability
    # TODO: Add debug level logging option
    # TODO: Improve error handling and reporting when parsing arguments

    """Run concurrency benchmark."""
    # Save terminal state at start
    save_terminal_state()

    try:
        setup_logging(level="WARNING", console=True)  # Reduce log noise during benchmark

        print("=" * 80)
        print("VIDEO ENCODING CONCURRENCY BENCHMARK")
        print("=" * 80)

        # Parse arguments
        profile_name = sys.argv[1] if len(sys.argv) > 1 else "x265-fast"
        max_concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        test_duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10

        # Check for source video argument (--source or -s)
        source_video = None
        for i, arg in enumerate(sys.argv):
            if arg in ["--source", "-s"] and i + 1 < len(sys.argv):
                source_video = Path(sys.argv[i + 1])
                if not source_video.exists():
                    print(f"✗ Source video not found: {source_video}")
                    sys.exit(1)
                break

        # Check for clip duration argument (--clip-duration)
        clip_duration = None
        for i, arg in enumerate(sys.argv):
            if arg == "--clip-duration" and i + 1 < len(sys.argv):
                clip_duration = int(sys.argv[i + 1])
                break

        # Default clip duration to test_duration if not specified
        if clip_duration is None:
            clip_duration = test_duration

        auto_cleanup = "--cleanup" in sys.argv or "-c" in sys.argv

        print(f"\nProfile: {profile_name}")
        print(f"Max concurrency to test: {max_concurrency}")
        print(f"Test video duration: {test_duration}s")
        if source_video:
            print(f"Source video: {source_video.name}")
            if clip_duration != test_duration:
                print(f"Clip duration: {clip_duration}s (different from test duration)")
            else:
                print(f"Clip duration: {clip_duration}s")
        else:
            print(f"Source video: Generated test pattern (synthetic)")
        print(f"Auto cleanup: {auto_cleanup}")

        # Hardware detection
        hw = HardwareCapabilities()
        summary = hw.get_summary()

        print("\nHardware capabilities:")
        print(f"  VAAPI:        {'✓' if summary['vaapi'] else '✗'}")
        print(f"  NVIDIA NVENC: {'✓' if summary['nvidia_nvenc'] else '✗'}")
        print(f"  AMD GPU:      {'✓' if summary['amd_gpu'] else '✗'}")
        print(f"  Intel QSV:    {'✓' if summary['intel_qsv'] else '✗'}")
        print(f"  Recommended:  {summary['recommended'] or 'CPU only'}")

        # Create test files
        # Use clip_duration for extraction, but test_duration is for generated videos
        test_files = create_test_files(
            max_concurrency,
            duration=clip_duration if source_video else test_duration,
            source_video=source_video
        )

        if not test_files:
            print("\n✗ Failed to create test files")
            sys.exit(1)

        print(f"\n✓ Created {len(test_files)} test files")

        # Show source type
        if source_video:
            print(f"   Using realistic video content from: {source_video.name}")
        else:
            print(f"   Using synthetic test pattern (less realistic)")
            print(f"   Tip: Use --source for more realistic results!")

        # Confirm
        print("\n" + "=" * 80)
        print("This benchmark will:")
        print(f"  1. Test encoding with 1, 2, 3, ... {max_concurrency} concurrent jobs")
        print(f"  2. Each test encodes {min(len(test_files), max_concurrency)} file(s)")
        if source_video:
            print(f"  3. Using {clip_duration}s clip from real video (realistic complexity)")
        else:
            print(f"  3. Using synthetic test pattern ({test_duration}s)")
        print(f"  4. Measure throughput (frames per second) at each concurrency level")
        print(f"  5. Identify optimal concurrency for your hardware")
        print("=" * 80)

        response = input("\nProceed with benchmark? [y/N]: ")
        if response.lower() != 'y':
            print("Benchmark cancelled.")
            sys.exit(0)

        # Run benchmark tests
        all_results = []

        print("\n" + "=" * 80)
        print("RUNNING BENCHMARK")
        print("=" * 80)

        for concurrency in range(1, max_concurrency + 1):
            result = run_concurrent_test(test_files, profile_name, concurrency)
            all_results.append(result)

            # Print quick summary
            if result["success"]:
                print(f"  ✓ Concurrency {concurrency}: {result['throughput_fps']:.1f} fps throughput")
            else:
                print(f"  ✗ Concurrency {concurrency}: FAILED")

        # Print final results
        print_results_table(
            all_results,
            profile_name=profile_name,
            test_duration=test_duration,
            source_video=source_video,
            max_concurrency=max_concurrency,
            clip_duration=clip_duration if source_video else None
        )

        # Cleanup option
        temp_dir = Path(tempfile.gettempdir()) / "videotranscode_benchmark"
        print(f"\nTest files location: {temp_dir}")

        # Flush output to ensure everything is printed
        sys.stdout.flush()
        sys.stderr.flush()

        if auto_cleanup:
            shutil.rmtree(temp_dir)
            print("✓ Test files deleted (auto cleanup enabled)")
        else:
            try:
                cleanup = input("Delete test files? [y/N]: ")
                if cleanup.lower() == 'y':
                    shutil.rmtree(temp_dir)
                    print("✓ Test files deleted")
                else:
                    print(f"Test files kept at: {temp_dir}")
            except (EOFError, KeyboardInterrupt):
                print(f"\n\nTest files kept at: {temp_dir}")
                print("To delete manually: rm -rf /tmp/videotranscode_benchmark")

    finally:
        # Always restore terminal state, even on error/interrupt
        restore_terminal_state()


if __name__ == "__main__":
    print("\nUsage: python tests/benchmark_concurrency.py [profile_name] [max_concurrency] [test_duration] [options]")
    print("\nExamples:")
    print("  # Use synthetic test pattern (fast but less realistic)")
    print("  python tests/benchmark_concurrency.py x265-balanced 10 10 --cleanup")
    print()
    print("  # Use real video content (more realistic results)")
    print("  python tests/benchmark_concurrency.py x265-balanced 10 10 --source /path/to/video.mkv --cleanup")
    print()
    print("  # Use longer clip for more accurate results")
    print("  python tests/benchmark_concurrency.py x265-balanced 10 10 --source video.mkv --clip-duration 60 --cleanup")
    print()
    print("Arguments:")
    print("  profile_name      Profile to benchmark (default: x265-fast)")
    print("  max_concurrency   Maximum concurrent jobs to test (default: 4)")
    print("  test_duration     Test video duration in seconds (default: 10)")
    print()
    print("Options:")
    print("  --source <file>       Use real video instead of test pattern (recommended)")
    print("  -s <file>             Short form of --source")
    print("  --clip-duration <sec> Duration of clip to extract from source (default: same as test_duration)")
    print("  --cleanup             Auto-delete test files after benchmark")
    print("  -c                    Short form of --cleanup")
    print()
    print("Notes:")
    print("  - Using --source extracts a clip from your video (middle or 5min mark)")
    print("  - Real video content gives more accurate benchmark results")
    print("  - Synthetic test patterns encode faster (no motion complexity)")
    print("  - Longer clips (30-60s) give more accurate results but take longer to benchmark")
    print()

    main()

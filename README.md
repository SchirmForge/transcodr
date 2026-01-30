# Video Transcode

A robust, production-ready video transcoding system with daemon, CLI, and API interfaces.

## Project Status

### Phase 1: Foundation ✓ (Completed)

Core components implemented:
- ✓ Project structure
- ✓ FFmpeg wrapper with version detection (supports FFmpeg 7.x and future versions)
- ✓ Probe helpers for file inspection
- ✓ Error types and exception hierarchy
- ✓ Logging system (structured and human-readable)
- ✓ Configuration management (Pydantic schemas + YAML)
- ✓ Hardware acceleration detection (VAAPI, NVENC, QSV, AMF)

### Phase 2: Profile Management ✓ (Completed)

- ✓ Profile schema (Pydantic models)
- ✓ Profile manager (loading, validation, inheritance)
- ✓ Built-in profiles with VAAPI support (x265-balanced, x265-quality, x265-fast)
- ✓ Hardware-specific profile variants

### Phase 3: Simple Job System ✓ (Completed)

- ✓ Job model with state tracking
- ✓ Job runner (direct execution)
- ✓ Safe file replacement with validation and backup
- ✓ Progress tracking and callbacks

**🎉 You can now encode videos!**

### Next Phases

- **Phase 4**: API (FastAPI endpoints) & daemon (basic)
- **Phase 5**: Job queue with SQLite persistence
- **Phase 6**: CLI (API client using Typer)
- **Phase 7+**: Advanced features (WebSocket progress, distributed encoding)

## Quick Start - Encode a Video!

### 1. Create a test video

```bash
./tests/create_test_video.sh tests/fixtures/test_video.mp4 10
```

This creates a 10-second test video in H.264 format.

### 2. Run the encoding test

```bash
python tests/test_encode.py tests/fixtures/test_video.mp4 x265-balanced
```

This will:
- Detect your hardware capabilities (VAAPI for AMD GPU)
- Show available profiles
- Encode the video using x265 with VAAPI acceleration
- Create a backup in `.originals/` directory
- Replace the original with the encoded version
- Show compression statistics

### 3. Use your own video

```bash
python tests/test_encode.py /path/to/your/video.mp4 x265-quality
```

**Available profiles:**
- `x265-balanced` - Recommended (CRF 23, medium preset)
- `x265-quality` - High quality (CRF 20, slow preset)
- `x265-fast` - Fast encoding (CRF 25, fast preset)

All profiles include VAAPI hardware variants for AMD/Intel GPUs!

## Performance Tuning - Find Optimal Concurrency

### Benchmark Your Hardware

Find the optimal number of concurrent encoding jobs for your GPU:

```bash
python tests/benchmark_concurrency.py x265-balanced 6 10
```

**Arguments:**
- `x265-balanced` - Profile to benchmark
- `6` - Test up to 6 concurrent jobs
- `10` - 10-second test videos

**What it does:**
- Tests encoding with 1, 2, 3, 4, 5, 6 concurrent jobs
- Measures throughput (frames per second) at each level
- Identifies optimal concurrency for maximum throughput
- Shows efficiency comparison

**Example output:**
```
Concurrency  Duration     Throughput      Avg FPS      Efficiency
------------------------------------------------------------------------
1            45.2s        66.4 fps        66.4 fps     100%
2            25.1s        119.5 fps       59.8 fps     180%
3            20.3s        147.8 fps       49.3 fps     223%
4            18.9s        158.7 fps       39.7 fps     239%  ← Optimal!

OPTIMAL CONCURRENCY: 4 concurrent jobs
```

### Save Results to Profile

```bash
python tests/save_benchmark_to_profile.py x265-balanced 4
```

This saves the optimal concurrency setting to the profile.

**Why benchmark?**
- VAAPI can often handle 3-6 concurrent encodes efficiently
- CPU-only encoding typically saturates at 1-2 concurrent jobs
- Find the sweet spot for your hardware to maximize throughput
- Avoid over-committing and slowing down the system

See [docs/concurrency-tuning.md](docs/concurrency-tuning.md) for detailed guidance.

## Architecture

This project follows an **API-first architecture**:
- Daemon runs FastAPI server + job queue + worker threads
- CLI is a thin client making HTTP requests to daemon
- Web UI (future) uses the same API
- All interfaces have identical capabilities

See [docs/architecture.md](docs/architecture.md) for complete architectural documentation.

## Setup

### Prerequisites

- Ubuntu 25.10 (or compatible Linux distribution)
- FFmpeg 7.x (system-installed)
- Miniconda with Python 3.12

### FFmpeg Installation

```bash
# Verify FFmpeg is installed
ffmpeg -version
```

Expected output: `ffmpeg version 7.1.1-1ubuntu4` (or similar)

### Python Environment

Create and activate conda environment:

```bash
conda create -n videotranscode python=3.12
conda activate videotranscode
```

Install dependencies:

```bash
conda install -c conda-forge \
  fastapi \
  uvicorn \
  typer \
  pydantic \
  rich \
  pytest \
  httpx \
  watchdog \
  pyyaml
```

## Testing

### Manual FFmpeg Test

Test the FFmpeg wrapper with the actual FFmpeg binary:

```bash
conda activate videotranscode
python tests/manual_test_ffmpeg.py
```

This will:
- Detect FFmpeg version
- Check codec support
- List available encoders/decoders
- Test progress parsing

### Unit Tests

Run unit tests (requires pytest in conda environment):

```bash
conda activate videotranscode
pytest tests/unit/ -v
```

## Current Capabilities

### Complete Encoding Pipeline

```python
from pathlib import Path
from src.jobs import Job, JobRunner

# Create a job
job = Job(
    source_path=Path("input.mp4"),
    profile_name="x265-balanced",
    hardware_accel=None,  # Auto-detect (will use VAAPI on AMD GPU)
)

# Execute the job
runner = JobRunner()

def on_progress(job):
    print(f"Progress: {job.progress_percent:.1f}% | FPS: {job.current_fps:.1f}")

job = runner.execute(job, progress_callback=on_progress)

print(f"Status: {job.state}")
print(f"Compression: {job.output_size_bytes / job.source_size_bytes * 100:.1f}%")
```

### Profile Management

```python
from src.profiles import ProfileManager

manager = ProfileManager()

# List available profiles
profiles = manager.list_profiles()
print(f"Available profiles: {profiles}")

# Load a profile
profile = manager.load_profile("x265-balanced")
print(f"Codec: {profile.video.codec}")
print(f"Hardware variants: {list(profile.hardware_variants.keys())}")

# Get FFmpeg arguments
ffmpeg_args = profile.to_ffmpeg_args(
    input_path="input.mp4",
    output_path="output.mkv",
    hardware_accel="vaapi"  # Use VAAPI acceleration
)
print(f"FFmpeg command: ffmpeg {' '.join(ffmpeg_args)}")
```

### Hardware Detection

```python
from src.core.hardware import HardwareCapabilities

hw = HardwareCapabilities()
summary = hw.get_summary()

print(f"VAAPI available: {summary['vaapi']}")
print(f"AMD GPU: {summary['amd_gpu']}")
print(f"Recommended: {summary['recommended']}")  # Will be 'vaapi' on AMD
```

### FFmpeg Wrapper

```python
from src.core.ffmpeg import FFmpegWrapper

# Initialize with auto-detection
wrapper = FFmpegWrapper()
print(f"FFmpeg version: {wrapper.get_version_number()}")

# Check codec support
if wrapper.supports_codec("libx265"):
    print("x265 encoding available")

# Get available encoders
encoders = wrapper.get_encoders()
print(f"Found {len(encoders)} encoders")

# Run FFmpeg with progress tracking
def on_progress(progress):
    print(f"Frame {progress.frame}, FPS: {progress.fps}")

wrapper.run(["-i", "input.mp4", "-c:v", "libx265", "output.mkv"], on_progress)
```

### Probe Helpers

```python
from pathlib import Path
from src.core.probe import ProbeHelper

probe = ProbeHelper()

# Get comprehensive media info
info = probe.get_info(Path("video.mp4"))
print(f"Duration: {info.duration}s")
print(f"Format: {info.format_name}")
print(f"Video codec: {info.get_primary_video_stream().codec_name}")

# Quick codec check
video_codec = probe.get_video_codec(Path("video.mp4"))
print(f"Video codec: {video_codec}")

# Validate file
if probe.validate_file(Path("video.mp4")):
    print("File is valid")

# Compare durations (for validation after encoding)
if probe.compare_durations(Path("original.mp4"), Path("encoded.mkv")):
    print("Duration matches!")
```

### Configuration

```python
from src.config import ConfigManager, Config

# Load configuration (or create default)
config = ConfigManager.load_config()

# Access settings
print(f"Temp directory: {config.storage.temp_dir}")
print(f"Max concurrent jobs: {config.daemon.max_concurrent_jobs}")

# Create default config file with comments
ConfigManager.create_default_config_file()

# Validate configuration
issues = ConfigManager.validate_config(config)
if issues:
    print("Config issues:", issues)
```

### Logging

```python
from pathlib import Path
from src.core.logging import setup_logging, JobLogger

# Setup application logging
setup_logging(
    level="INFO",
    log_dir=Path.home() / ".local/share/videotranscode/logs",
    console=True
)

# Per-job logging
with JobLogger("job-123", Path("/tmp/logs")) as logger:
    logger.info("Starting encode")
    logger.debug("FFmpeg args: ...")
    logger.info("Encode complete")
```

## Key Design Decisions

### FFmpeg Version Agnostic

The FFmpeg wrapper is designed to work with any FFmpeg version:
- Uses `ffmpeg -version` for detection (your suggestion!)
- No hard dependencies on specific FFmpeg features
- Supports upgrading from FFmpeg 7.x to 8.x without code changes

### API-First Architecture

All user interfaces are clients of the daemon API:
- CLI makes HTTP requests to daemon
- Future Web UI uses same API
- Consistent behavior across all interfaces
- Enables remote control capabilities

### Data-Driven Configuration

Settings and profiles are YAML files, not hardcoded:
- Easy to edit by hand
- Version controllable
- No code changes needed for new profiles

### Safety First

Multiple safeguards to prevent data loss:
- Encode to temp location first
- Validate output before replacement
- Atomic file operations
- Optional backup of originals
- Pre-flight validation checks

## Directory Structure

```
videotranscode/
├── src/
│   ├── core/              # Core functionality
│   │   ├── ffmpeg.py      # FFmpeg wrapper ✓
│   │   ├── probe.py       # Media inspection ✓
│   │   ├── errors.py      # Exception types ✓
│   │   └── logging.py     # Logging setup ✓
│   ├── config/            # Configuration management ✓
│   │   ├── schema.py      # Pydantic models ✓
│   │   └── manager.py     # Config loader ✓
│   ├── profiles/          # Profile management (TODO)
│   ├── jobs/              # Job queue system (TODO)
│   ├── api.py             # FastAPI app (TODO)
│   ├── cli.py             # Typer CLI (TODO)
│   └── daemon.py          # Daemon main (TODO)
├── tests/
│   ├── unit/              # Unit tests ✓
│   └── manual_test_ffmpeg.py  # Manual test script ✓
├── docs/
│   └── architecture.md    # Architecture documentation ✓
└── local-docs/
    └── readme-dev.md      # Development setup notes
```

## Contributing

This is a personal project in active development. See the architecture document for design decisions and implementation roadmap.

## License

TBD

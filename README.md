# Video Transcode

A robust, production-ready video transcoding system with daemon, CLI, and API interfaces.

## Features

- **Daemon-based architecture** - Background service with REST API
- **Multi-profile encoding** - Encode one source to multiple formats simultaneously
- **Watch folders** - Automatic encoding via command files or direct media detection
- **Folder drop support** - Drop entire folder trees with automatic subdirectory processing
- **Hardware acceleration** - VAAPI (AMD/Intel), NVENC, QSV support
- **Safe file replacement** - Backup originals, validate output, atomic operations
- **Flexible output** - Replace original or output to destination folder
- **SQLite persistence** - Job queue survives daemon restarts
- **Portable configs** - Use `$root_media`, `$HOME`, `~` placeholders in paths

## Project Status: Version 0.2.3

### What's New in v0.2.3

**Profile-Level Destinations**
- Profiles can define their own `destination:` folder (absolute path)
- Use `destination: profile` in commands/watchfolders to output to each profile's folder
- Supports path placeholders (`$root_media`, `~`, `$HOME`)
- Validation ensures profile destination directories exist

**Configurable Output Naming**
- `profile_name_separator` config option for `append_profile_name` feature (default: `_`)
- Customize how profile names are appended to filenames

**Per-Source Concurrency Limits**
- `max_concurrent_jobs` option in watchfolders and commands
- Limit how many jobs run simultaneously from a single source
- Useful for resource management on slower storage

### What's New in v0.2.2

**Multi-Profile Concurrent Encoding**
- Fixed race conditions when encoding with multiple profiles concurrently
- Ref-count based finalization ensures proper cleanup when all profiles complete
- `disable_temp_copy` option now works correctly for all profiles

**Stream Handling**
- Include all audio streams from source (`audio.all: true`, default)
- Include all subtitle streams from source (`subtitles.all: true`, default)
- Proper stream mapping with VAAPI hardware encoding

**Reliability**
- Fixed SQLite transaction errors under concurrent load
- Fixed container format issues (temp files now use profile's container)
- Profile cache clears on daemon reload for immediate profile updates

### What's New in v0.2.1

**Watch Folder Improvements**
- `$root_media` placeholder for portable command files and watchfolder configs
- Environment variable expansion (`$HOME`, `${HOME}`, `~`, `$USER`)
- Folder drop processing with `allow_folder_drop` option
- Nested subdirectory scanning with stability detection
- `preserve_folder_structure` works correctly for dropped folders
- Automatic folder completion tracking with `.processed` rename or delete

**Code Architecture**
- Dedicated `src/watcher/` module for all watchfolder functionality
- Cleaner separation of concerns (schema, manager, watchers, service)

### Core Features (v0.1)

**Core Encoding**
- FFmpeg wrapper with progress streaming
- ffprobe helpers (codec detection, duration, validation)
- Profile management (YAML-based, inheritance, hardware variants)
- Safe file replacement (cross-device, backup, rollback)
- Multi-profile encoding (one source -> multiple outputs)

**Daemon & API**
- FastAPI REST API with full CRUD operations
- Job queue with SQLite persistence
- Watch folder monitoring (command and media types)
- Priority-based job ordering
- Concurrent job execution (configurable)
- Profile management endpoints
- Configuration reload without restart

**Hardware**
- VAAPI detection and auto-selection (AMD/Intel GPU)
- Hardware variants in profiles

**CLI**
- Full CLI client for daemon API
- Profile listing and management
- Job monitoring and control

## Quick Start

### 1. Setup

```bash
# Create conda environment
conda create -n videotranscode python=3.12
conda activate videotranscode

# Install dependencies
pip install -r requirements.txt

# Initialize configuration
python src/cli/init.py
```

### 2. Start the Daemon

```bash
python -m src.daemon
```

The daemon starts on `http://127.0.0.1:8765` by default.

### 3. Submit an Encoding Job

```bash
# Encode a single file (replace mode - creates backup)
python -m src.cli.client submit \
  --source /path/to/video.mkv \
  --profile x265-balanced

# Encode a folder to destination
python -m src.cli.client submit \
  --source /path/to/videos/ \
  --profile x265-balanced \
  --destination /path/to/output/ \
  --recursive

# Multi-profile encoding
python -m src.cli.client submit \
  --source /path/to/video.mkv \
  --profile x265-balanced \
  --profile x265-fast \
  --destination /path/to/output/
```

### 4. Monitor Jobs

```bash
# List all jobs
python -m src.cli.client jobs

# Get job details
python -m src.cli.client job <job-id>

# Check daemon status
python -m src.cli.client status
```

### 5. Manage Profiles

```bash
# List available profiles
python -m src.cli.client profiles
```

## Encoding Options

### Output Modes

| Mode | Description |
|------|-------------|
| `replace` | Replace original file in-place (with backup) |
| `destination` | Output to separate folder |

### Request Parameters

| Parameter | Description |
|-----------|-------------|
| `source` | Source file or folder path |
| `profiles` | List of encoding profiles |
| `output_mode` | `replace` or `destination` |
| `destination` | Output folder, or `profile` to use each profile's destination |
| `recursive` | Process subdirectories |
| `preserve_structure` | Recreate folder structure in destination |
| `create_profile_folders` | Create subfolder per profile (e.g., `dest/x265-balanced/`) |
| `append_profile_name` | Add profile name to filename (e.g., `video_x265-balanced.mkv`) |
| `delete_source` | Delete source after successful encoding |
| `backup` | Create backup before replacing (default: true) |
| `priority` | Job priority 1-10 (default: 5) |
| `max_concurrent_jobs` | Limit concurrent jobs from this request |

### Example: YAML Encoding Request

```yaml
# encoding-request.yaml
mode: encode
profiles:
  - x265-balanced
  - x265-fast
source: /media/videos/
output_mode: destination
destination: /media/encoded/
preserve_structure: true
create_profile_folders: true
append_profile_name: true
recursive: true
priority: 7
file_patterns:
  - "*.mkv"
  - "*.mp4"
  - "*.m2ts"
```

## Watch Folders

Two types of watch folders are supported:

### Command Watch Folder

Monitors a folder for YAML command files:

```yaml
# ~/.config/videotranscode/watchfolders/commands.yaml
watchfolder_location: /tmp/encode-commands
watchfolder_type: command
scan_interval: 5
```

Drop a command file to trigger encoding:
```yaml
# /tmp/encode-commands/encode-movie.yaml
profile: x265-balanced
source: /media/videos/movie.mkv
output_mode: replace
```

### Media Watch Folder

Monitors a folder for video files directly:

```yaml
# ~/.config/videotranscode/watchfolders/downloads.yaml
watchfolder_location: $HOME/downloads
watchfolder_type: media
scan_interval: 10
stability_scans: 3
file_patterns:
  - "*.mkv"
  - "*.mp4"
profiles:
  - x265-balanced
destination: $root_media/encoded/
preserve_folder_structure: true
```

### Media Watch Folder with Folder Drops

Process entire folders dropped into the watch location:

```yaml
# ~/.config/videotranscode/watchfolders/folder-drop.yaml
watchfolder_location: $HOME/encode-folders
watchfolder_type: media
scan_interval: 5
stability_scans: 2
allow_folder_drop: true           # Enable folder processing
preserve_folder_structure: true   # Keep subfolder structure
file_patterns:
  - "*.mkv"
  - "*.mp4"
profiles:
  - x265-fast
destination: $root_media/encoded/
keep_processed_files: false       # Delete source after encoding
```

See [docs/watchfolders.md](docs/watchfolders.md) for detailed guide.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Daemon status and queue info |
| `/jobs` | GET | List all jobs |
| `/jobs` | POST | Submit encoding job |
| `/jobs/{id}` | GET | Get job details |
| `/jobs/{id}` | DELETE | Cancel job |
| `/profiles` | GET | List all profiles |
| `/profiles/{name}` | GET | Get profile details |
| `/profiles/{name}` | DELETE | Delete user profile |
| `/watchfolders` | GET | List all watchfolders |
| `/watchfolders/{id}` | GET | Get watchfolder details |
| `/watchfolders/{id}` | DELETE | Remove watchfolder |
| `/watchfolders/{id}/pause` | POST | Pause watchfolder |
| `/watchfolders/{id}/resume` | POST | Resume watchfolder |
| `/queue/pause` | POST | Pause job queue |
| `/queue/resume` | POST | Resume job queue |
| `/reload` | POST | Reload configuration |
| `/purge` | POST | Purge job database |

See [docs/api-reference.md](docs/api-reference.md) for complete documentation.

## Configuration

Configuration is stored in `~/.config/videotranscode/`:

```
~/.config/videotranscode/
├── config.yaml          # Main configuration
├── profiles/            # User profiles
├── watchfolders/        # Watchfolder configs
└── jobs.db              # Job database
```

### Key Configuration Options

```yaml
# config.yaml
daemon:
  host: 127.0.0.1
  port: 8765
  max_concurrent_jobs: 2

storage:
  temp_dir: /tmp/videotranscode
  backup_originals: true
  backup_dir: .originals
  root_media: ~/Videos   # Base path for $root_media placeholder
  profile_name_separator: "_"  # Separator for append_profile_name

ffmpeg:
  hardware_accel: auto  # auto|vaapi|nvenc|qsv|none
```

### Path Placeholders

Use these placeholders in watchfolder and command configs:

| Placeholder | Expands To |
|-------------|------------|
| `$root_media` | Value of `storage.root_media` in config |
| `$HOME`, `${HOME}` | User's home directory |
| `~` | User's home directory |
| `$USER` | Current username |

See [docs/configuration.md](docs/configuration.md) for detailed guide.

## Available Profiles

| Profile | Description | Hardware |
|---------|-------------|----------|
| `x265-balanced` | Balanced quality/speed (CRF 23, medium) | VAAPI |
| `x265-quality` | High quality (CRF 20, slow preset) | VAAPI |
| `x265-fast` | Fast encoding (CRF 25, fast preset) | VAAPI |

## Supported File Types

**Video:** `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m2ts`, `.ts`

## Performance Tuning

Find optimal concurrent jobs for your hardware:

```bash
python tests/benchmark_concurrency.py x265-balanced 6 10
```

See [docs/concurrency-tuning.md](docs/concurrency-tuning.md) for tuning guide.

## Architecture

This project follows an **API-first architecture**:
- Daemon runs FastAPI server + job queue + worker threads
- CLI is a thin client making HTTP requests to daemon
- All interfaces have identical capabilities

See [docs/architecture.md](docs/architecture.md) for complete documentation.

## Documentation

- [Architecture](docs/architecture.md) - System design and components
- [Configuration](docs/configuration.md) - Configuration guide
- [API Reference](docs/api-reference.md) - REST API documentation
- [CLI Reference](docs/cli-reference.md) - CLI commands
- [Watch Folders](docs/watchfolders.md) - Watch folder setup
- [Concurrency Tuning](docs/concurrency-tuning.md) - Performance optimization
- [Roadmap](docs/roadmap.md) - Feature roadmap

## License

TBD

# Transcodr

A robust, production-ready video transcoding system with daemon, CLI, and API interfaces.

## Features

- **Web UI** - Built-in React web interface for job management, file browsing, and manual encoding
- **Daemon-based architecture** - Background service with REST API
- **Multi-profile encoding** - Encode one source to multiple formats simultaneously
- **Watch folders** - Automatic encoding via command files or direct media detection
- **Folder drop support** - Drop entire folder trees with automatic subdirectory processing
- **Hardware acceleration** - VAAPI (AMD/Intel), NVENC, QSV support
- **Safe file replacement** - Backup originals, validate output, atomic operations
- **Flexible output** - Replace original or output to destination folder
- **SQLite persistence** - Job queue survives daemon restarts
- **Portable configs** - Use `$root_media`, `$HOME`, `~` placeholders in paths

## Project Status: Version 0.3.3

### What's New in v0.3.3

**Web UI — Manual Encoding**
- Create Job page with multi-step form: select files, choose profiles, configure options, review and submit
- Built-in file browser for navigating the filesystem and selecting video files
- Profile selector with card-based UI showing codec, container, CRF, and destination status
- `use_temp_folder` option — encode to temp folder first, then move to output (default: on)
- `copy_source_to_temp` option — copy source to temp before multi-profile encoding (default: on)

**Encoding Improvements**
- Fixed disk space estimation: `source_size + min_free_space_gb` (was `source_size * 2 + 10GB`)
- Improved error message for insufficient temp space (shows path, breakdown, and suggestions)
- Validation errors (space check, bad profile) logged as warnings instead of error tracebacks

**API**
- All API endpoints moved under `/api` prefix for clean SPA separation
- New `GET /api/browse` endpoint for filesystem browsing

### What's New in v0.3.1 — v0.3.2

**Web UI — Basic Layout (v0.3.1)**
- React 19 + Vite + TypeScript + Tailwind CSS 4
- Left-nav layout with Jobs / Configuration / Settings / System
- Jobs activity and history pages with live progress polling
- Watch folders, profiles, and system status pages
- Dark/light mode support
- SPA served directly from the daemon (no separate web server needed)

**Bug Fixes (v0.3.2)**
- Duration tolerance improvements
- Watchfolder initial sweep on startup
- File stability detection for network files

### Previous Versions

<details>
<summary>v0.2.x release notes</summary>

**v0.2.3 — Profile-Level Destinations**
- Profiles can define their own `destination:` folder
- `use_profile_destination: true` in commands/watchfolders
- Per-source `max_concurrent_jobs` concurrency limits
- Configurable `profile_name_separator`

**v0.2.2 — Multi-Profile Reliability**
- Fixed race conditions with concurrent multi-profile encoding
- Ref-count based finalization
- All audio/subtitle stream mapping
- SQLite transaction fixes, container format fixes

**v0.2.1 — Watch Folder Improvements**
- `$root_media` placeholder and environment variable expansion
- Folder drop processing with nested subdirectory scanning
- Dedicated `src/watcher/` module

**v0.1 — Core**
- FFmpeg wrapper with progress streaming, profile management, safe file replacement
- FastAPI REST API with SQLite persistence, job queue, watch folders
- VAAPI hardware acceleration, full CLI client
</details>

## Quick Start

### 1. Setup

```bash
# Create conda environment
conda create -n transcodr python=3.12
conda activate transcodr

# Install dependencies
pip install -r requirements.txt

# Initialize configuration
python src/cli/init.py
```

### 2. Start the Daemon

```bash
python -m src.daemon
```

The daemon starts on `http://127.0.0.1:8765` by default. The Web UI is available at the same address.

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
| `destination` | Output folder (required for destination mode unless use_profile_destination is set) |
| `use_profile_destination` | Use each profile's destination field instead of a single folder |
| `recursive` | Process subdirectories |
| `preserve_structure` | Recreate folder structure in destination |
| `create_profile_folders` | Create subfolder per profile (e.g., `dest/x265-balanced/`) |
| `append_profile_name` | Add profile name to filename (e.g., `video_x265-balanced.mkv`) |
| `delete_source` | Delete source after successful encoding |
| `use_temp_folder` | Encode to temp folder first, then move to output (default: true) |
| `copy_source_to_temp` | Copy source to temp before multi-profile encoding (default: true) |
| `backup` | Create backup before replacing (default: true) |
| `priority` | Job priority 1-10 (default: 5) |
| `max_concurrent_jobs` | Limit concurrent jobs from this request |

### Example: YAML Encoding Request

```yaml
# encoding-request.yaml
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
# ~/.config/transcodr/watchfolders/commands.yaml
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
# ~/.config/transcodr/watchfolders/downloads.yaml
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
# ~/.config/transcodr/watchfolders/folder-drop.yaml
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
| `/api/status` | GET | Daemon status and queue info |
| `/api/health` | GET | Health check |
| `/api/browse` | GET | Browse filesystem for video files |
| `/api/jobs` | GET | List all jobs |
| `/api/jobs` | POST | Submit encoding job |
| `/api/jobs/{id}` | GET | Get job details |
| `/api/jobs/{id}` | DELETE | Cancel job |
| `/api/jobs/{id}/retry` | POST | Retry failed job |
| `/api/profiles` | GET | List all profiles |
| `/api/profiles/{name}` | GET | Get profile details |
| `/api/profiles/{name}` | DELETE | Delete user profile |
| `/api/watchfolders` | GET | List all watchfolders |
| `/api/watchfolders/{id}` | GET | Get watchfolder details |
| `/api/watchfolders/{id}` | DELETE | Remove watchfolder |
| `/api/watchfolders/{id}/pause` | POST | Pause watchfolder |
| `/api/watchfolders/{id}/resume` | POST | Resume watchfolder |
| `/api/queue/pause` | POST | Pause job queue |
| `/api/queue/resume` | POST | Resume job queue |
| `/api/reload` | POST | Reload configuration |
| `/api/purge` | POST | Purge job database |

See [docs/api-reference.md](docs/api-reference.md) for complete documentation.

## Configuration

Configuration is stored in `~/.config/transcodr/`:

```
~/.config/transcodr/
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
  temp_dir: /tmp/transcodr
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
- Daemon runs FastAPI server + job queue + worker threads + Web UI
- Web UI is a React SPA served directly by the daemon
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

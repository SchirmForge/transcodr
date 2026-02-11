# Changelog

All notable changes to Transcodr are documented in this file.

---

## v0.3.5

### Docker Support
- Multi-stage Dockerfile (Node for WebUI build, Python for runtime) with FFmpeg + VAAPI drivers
- `docker-compose.yml` with volume mounts for config, media, and temp directories
- Commented GPU passthrough sections for VAAPI (AMD/Intel) and NVIDIA
- `HEALTHCHECK` on `/api/health` endpoint
- Docker documentation (`docker/README.md`)

### Configuration Directory via Environment Variable
- New `TRANSCODR_CONFIG_DIR` environment variable overrides the default `~/.config/transcodr` config directory
- All config paths (config.yaml, profiles, watchfolders, jobs.db) derive from this directory
- Essential for Docker deployments where config is mounted at `/config`
- Falls back to `~/.config/transcodr` when not set

### Settings API
- `GET /api/config` — returns full daemon configuration (ffmpeg, daemon, storage, logging, validation)
- `PUT /api/config` — partial config update with validation, saves to disk and reloads live
- Warns when host/port changes require a daemon restart

### Settings Web UI
- **Storage** page: root media, temp directory, backup options, free space, extension mismatch policy, profile name separator
- **Encoding** page: FFmpeg binary path, hardware acceleration selector, duration tolerance, detected hardware display
- **Daemon** page: host, port, max concurrent jobs (with restart warning banner)
- **Logging** page: log level, log directory, rotation policy, per-job logs toggle
- Each page has Save/Cancel with dirty state tracking and success/error feedback
- Sidebar Settings section expanded with Storage, Encoding, Daemon, Logging sub-items

### Internal
- Replaced hardcoded `DEFAULT_CONFIG_PATH` class attribute with `get_default_config_path()` static method
- Updated all references across daemon, API, and CLI modules

---

## v0.3.4

### Extension Mismatch Handling
- New `on_extension_mismatch` config option for replace mode when source extension differs from profile container (e.g., `.mts` source with `.mkv` profile)
  - `rename` (default) — output uses correct extension, original is deleted, job completes with warning
  - `reject` — job fails with descriptive error
  - `keep` — output keeps source extension (wrong content), job completes with warning

### Warning Job Status
- New `warning` job status for jobs that completed with non-fatal issues
- `warning_message` field on jobs tracks what went wrong
- Web UI: amber badges and warning message display in job history
- History page filter and "Clear Warning" button for warning jobs
- `DELETE /api/queue/warning` endpoint to clear warning jobs

### Web UI Improvements
- Dynamic version display in sidebar (fetched from daemon API)
- Refresh button on file browser toolbar (Create Job page)
- Sidebar navigation renamed "Configuration" to "Encoding Rules"

### Internal
- Consolidated database schema (removed incremental ALTER TABLE migrations)
- Added `warning_message` column migration for existing databases
- Version displayed in daemon startup banner

---

## v0.3.3

### Manual Encoding via Web UI
- Create Job page with multi-step form (files, profiles, options, review)
- File browser endpoint (`GET /api/browse`) for filesystem navigation
- Profile selector with card-based UI (codec, container, CRF, destination status)
- `use_temp_folder` option — encode to temp folder first, then move to output
- `copy_source_to_temp` option — copy source to temp before multi-profile encoding

### Fixes
- Fixed disk space estimation formula (`source_size + min_free_space_gb` instead of `source_size * 2 + 10GB`)
- Improved error handling: `ValidationError` logged as warning, not error with traceback
- Improved insufficient temp space error message with actionable suggestions
- All API endpoints moved under `/api` prefix for clean SPA/API separation

---

## v0.3.2

### Fixes
- Duration tolerance default changed from 5s to 10s
- Watchfolder initial sweep on startup to detect existing files
- File stability detection improvements for large network files

---

## v0.3.1

### Web UI — Initial Release
- React + Vite + TypeScript stack
- Left-nav layout with Jobs / Configuration / Settings / System sections
- Tailwind CSS with custom brand color palette
- Dark/light mode support
- Jobs activity page with live progress polling
- Jobs history page with completed/failed filters
- Watch folders status list
- Profiles page with card-based display
- System status page with hardware info and queue status
- SPA served directly from daemon (no separate web server)

---

## v0.2.3

### Profile-Level Destinations
- Profile `destination:` field for absolute output path
- Path placeholder support (`$root_media`, `~`, `$HOME`)
- `use_profile_destination: true` for commands/watchfolders
- Validation that profile destination directory exists
- `create_profile_folders` cannot be mixed with `use_profile_destination`

### Concurrency Control
- Per-command/watchfolder `max_concurrent_jobs` limit
- Source-level tracking with database `source_id` column
- Respects global limit while allowing per-source restrictions

### Output Naming
- `profile_name_separator` config option (default: `_`)
- Configurable separator for `append_profile_name` feature

---

## v0.2.2

### Extract Profiles
- Stream copy support (`copy_streams`/`copy`)
- Time-based extraction (`start_time`, `duration`)
- Built-in extract profiles (3m at 3, 15, 30, 60, 90 minutes)

### Stream Mapping
- `audio.include_all` and `subtitles.include_all` (default: true)
- Explicit `-map 0:a?` / `-map 0:s?` handling
- VAAPI filter path uses `-filter_complex` with named outputs

### Container Handling
- Temp output uses profile `container` (not source extension)
- Profile loaded earlier to set output container reliably

### Watchfolder Reliability
- Hash-based file tracking (no `.processing` rename)
- Final rename/delete only after all profiles complete
- Ref-count based finalization (tracks partial failures)

### Fixes
- Profile cache reload via `/reload` endpoint
- SQLite autocommit to avoid nested transaction errors

---

## v0.2.1

### Watch Folder Improvements
- `root_media` config placeholder for portable command files
- Environment variable expansion (`$HOME`, `${HOME}`, `~`, `$USER`)
- Folder drop processing (`allow_folder_drop` option)
- Nested subdirectory scanning with stability detection
- `preserve_folder_structure` for dropped folders
- New file detection during encoding (re-scan after job submission)
- Folder completion tracking with `.processed` rename or delete

### Code Architecture
- Dedicated `src/watcher/` module (moved from config/ and api/)
- `WatchfolderConfigManager` for config loading
- `FolderProcessor` for folder stability and completion tracking
- Circular import resolution with TYPE_CHECKING

---

## v0.1

### Core Encoding
- FFmpeg wrapper with progress streaming
- ffprobe helpers (codec detection, duration, validation)
- Profile management (YAML-based, inheritance, hardware variants)
- Safe file replacement (cross-device, backup, rollback)
- Multi-profile encoding (one source, multiple outputs)
- Output mode: replace or destination

### Daemon & API
- FastAPI REST API
- Job queue with SQLite persistence
- Priority-based job ordering
- Concurrent job execution (configurable)
- Profile endpoints (list, details, delete)
- Watchfolder endpoints (unified, pause/resume)
- Configuration reload without restart
- Database purge endpoint

### Watch Folders
- Command watch folders (YAML command files)
- Media watch folders (direct video detection)
- File size stability detection
- Pause/resume support
- Unified watchfolder API

### Encoding Options
- `create_profile_folders` — subfolder per profile
- `append_profile_name` — profile name in filename
- `preserve_structure` — recreate folder structure
- `delete_source` — delete after successful encoding
- Configurable temp directory

### Hardware
- VAAPI detection and auto-selection (AMD/Intel GPU)
- Hardware variants in profiles

### CLI
- Full CLI client for daemon API
- Profile listing with hardware info
- Job management and monitoring
- Reload and purge commands
- Delete confirmations

### File Support
- Standard video: mkv, mp4, avi, mov, wmv, flv, webm
- Transport streams: m2ts, ts

### Testing & Benchmarking
- Concurrency benchmark tool
- Benchmark-to-profile saver
- Concurrency tuning guide

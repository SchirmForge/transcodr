# transcodr Roadmap

## Current Version: 0.3.6

## Use Cases Overview

| # | Use Case | Status | Notes |
|---|----------|--------|-------|
| 1 | Folder encoding with replacement | ✅ Done | CLI submit, recursive, patterns |
| 2 | Watch folders (command type) | ✅ Done | YAML command file watcher |
| 3 | Watch folders (media type) | ✅ Done | Direct video file detection with stability |
| 4 | Multi-profile encoding | ✅ Done | One source -> multiple outputs |
| 5 | Output organization | ✅ Done | Profile folders, append name, preserve structure |
| 6 | Hardware acceleration | ✅ Done | VAAPI auto-detection and selection |
| 7 | Parallel encoding | ✅ Done | Configurable max_concurrent_jobs |
| 8 | Folder drop processing | ✅ Done | Drop folders with nested subdirectories |
| 9 | Notifications | ❌ Pending | Email, Webhook, Desktop, Pushover, Gotify, ntfy |
| 10 | Video filters | ❌ Pending | Scale, crop, deinterlace, denoise, watermark |
| 11 | Distributed encoding | ❌ Pending | Controller/worker architecture |

---

## Completed Features (v0.1)

### Core Encoding
- [x] FFmpeg wrapper with progress streaming
- [x] ffprobe helpers (codec detection, duration, validation)
- [x] Profile management (YAML-based, inheritance, hardware variants)
- [x] Safe file replacement (cross-device, backup, rollback)
- [x] Multi-profile encoding (one source -> multiple outputs)
- [x] Output mode: replace or destination

### Daemon & API
- [x] FastAPI REST API
- [x] Job queue with SQLite persistence
- [x] Priority-based job ordering
- [x] Concurrent job execution (configurable)
- [x] Profile endpoints (list, details, delete)
- [x] Watchfolder endpoints (unified, pause/resume)
- [x] Configuration reload without restart
- [x] Database purge endpoint

### Watch Folders
- [x] Command watch folders (YAML command files)
- [x] Media watch folders (direct video detection)
- [x] File size stability detection
- [x] Pause/resume support
- [x] Unified watchfolder API

### Encoding Options
- [x] `create_profile_folders` - subfolder per profile
- [x] `append_profile_name` - profile name in filename
- [x] `preserve_structure` - recreate folder structure
- [x] `delete_source` - delete after successful encoding
- [x] Configurable temp directory

### Hardware
- [x] VAAPI detection and auto-selection (AMD/Intel GPU)
- [x] Hardware variants in profiles

### CLI
- [x] Full CLI client for daemon API
- [x] Profile listing with hardware info
- [x] Job management and monitoring
- [x] Reload and purge commands
- [x] Delete confirmations

### File Support
- [x] Standard video: mkv, mp4, avi, mov, wmv, flv, webm
- [x] Transport streams: m2ts, ts

### Testing & Benchmarking
- [x] Concurrency benchmark tool
- [x] Benchmark-to-profile saver
- [x] Concurrency tuning guide

---

## Completed Features (v0.2.1)

### Watch Folder Improvements
- [x] `root_media` config placeholder for portable command files
- [x] Environment variable expansion (`$HOME`, `${HOME}`, `~`, `$USER`)
- [x] Folder drop processing (`allow_folder_drop` option)
- [x] Nested subdirectory scanning with stability detection
- [x] `preserve_folder_structure` for dropped folders
- [x] New file detection during encoding (re-scan after job submission)
- [x] Folder completion tracking with `.processed` rename or delete

### Code Architecture
- [x] Dedicated `src/watcher/` module (moved from config/ and api/)
- [x] `WatchfolderConfigManager` for config loading
- [x] `FolderProcessor` for folder stability and completion tracking
- [x] Circular import resolution with TYPE_CHECKING

---

## Completed Features (v0.2.2)

### Extract Profiles
- [x] Stream copy support (`copy_streams`/`copy`)
- [x] Time-based extraction (`start_time`, `duration`)
- [x] Built-in extract profiles (3m at 3, 15, 30, 60, 90)

### Stream Mapping
- [x] `audio.include_all` and `subtitles.include_all` (default: true)
- [x] Explicit `-map 0:a?` / `-map 0:s?` handling
- [x] VAAPI filter path uses `-filter_complex` with named outputs

### Container Handling
- [x] Temp output uses profile `container` (not source extension)
- [x] Profile loaded earlier to set output container reliably

### Watchfolder Reliability
- [x] Hash-based file tracking (no `.processing` rename)
- [x] Final rename/delete only after all profiles complete
- [x] Ref-count based finalization (tracks partial failures)

### Runtime Fixes
- [x] Profile cache reload via `/reload` endpoint
- [x] SQLite autocommit to avoid nested transaction errors

---

## Completed Features (v0.2.3)

### Profile-Level Destinations
- [x] Profile `destination:` field for absolute output path
- [x] Path placeholder support (`$root_media`, `~`, `$HOME`)
- [x] `use_profile_destination: true` for commands/watchfolders
- [x] Validation that profile destination directory exists
- [x] `create_profile_folders` cannot be mixed with `use_profile_destination`

### Concurrency Control
- [x] Per-command/watchfolder `max_concurrent_jobs` limit
- [x] Source-level tracking with database `source_id` column
- [x] Respects global limit while allowing per-source restrictions

### Output Naming
- [x] `profile_name_separator` config option (default: `_`)
- [x] Configurable separator for `append_profile_name` feature

---

## Completed Features (v0.3.1)

### Web UI — Basic Layout
- [x] React + Vite + TypeScript stack
- [x] Left-nav layout with Jobs / Configuration / Settings / System sections
- [x] Tailwind CSS with custom brand color palette
- [x] Dark/light mode support
- [x] Jobs activity page with live progress polling
- [x] Jobs history page with completed/failed filters
- [x] Watch folders status list
- [x] Profiles page with card-based display
- [x] System status page with hardware info and queue status
- [x] SPA served directly from daemon (no separate web server)

---

## Completed Features (v0.3.2)

### Bug Fixes
- [x] Duration tolerance default changed from 5s to 10s
- [x] Watchfolder initial sweep on startup to detect existing files
- [x] File stability detection improvements for large network files

---

## Completed Features (v0.3.3)

### Manual Encoding via Web UI
- [x] Create Job page with multi-step form (files → profiles → options → review)
- [x] File browser endpoint (`GET /api/browse`) for filesystem navigation
- [x] Profile selector with card-based UI (codec, container, CRF, destination status)
- [x] `use_temp_folder` option — encode to temp folder first, then move to output
- [x] `copy_source_to_temp` option — copy source to temp before multi-profile encoding
- [x] Fixed disk space estimation formula (`source_size + min_free_space_gb` instead of `source_size * 2 + 10GB`)
- [x] Improved error handling: `ValidationError` logged as warning, not error with traceback
- [x] Improved insufficient temp space error message with actionable suggestions
- [x] All API endpoints moved under `/api` prefix for clean SPA/API separation

---

## Completed Features (v0.3.4)

### Extension Mismatch Handling
- [x] `on_extension_mismatch` config option for replace mode (rename, reject, keep)
- [x] `rename` (default): correct extension, delete original, complete with warning
- [x] `reject`: fail job with descriptive error
- [x] `keep`: keep source extension with wrong content, complete with warning

### Warning Job Status
- [x] New `warning` job status for non-fatal issues
- [x] `warning_message` field on jobs
- [x] Web UI: amber badges, warning message display, filter, "Clear Warning" button
- [x] `DELETE /api/queue/warning` endpoint

### Web UI Improvements
- [x] Dynamic version display in sidebar (from daemon API)
- [x] Refresh button on file browser toolbar
- [x] Sidebar navigation renamed "Configuration" to "Encoding Rules"

---

## Completed Features (v0.3.5)

### Docker Support
- [x] Multi-stage Dockerfile (Node for WebUI build, Python for runtime)
- [x] `docker-compose.yml` with config/media/temp volume mounts
- [x] GPU passthrough sections (VAAPI, NVIDIA)
- [x] Health check on `/api/health`
- [x] Docker documentation (`docker/README.md`)

### Configuration Environment Variable
- [x] `TRANSCODR_CONFIG_DIR` env var overrides default config directory
- [x] All config paths (config.yaml, profiles, watchfolders, jobs.db) derive from it
- [x] Falls back to `~/.config/transcodr` when not set

### Settings API
- [x] `GET /api/config` — read full daemon configuration
- [x] `PUT /api/config` — partial update, validate, save to disk, reload live

### Settings Web UI
- [x] Storage settings page (root media, temp dir, backup, free space, mismatch policy)
- [x] Encoding settings page (FFmpeg path, hardware accel, duration tolerance)
- [x] Daemon settings page (host, port, max concurrent jobs)
- [x] Logging settings page (level, directory, rotation, per-job logs)
- [x] Save/Cancel with dirty state tracking and feedback messages

---

## Completed Features (v0.3.6)

### Configuration & Runtime
- [x] Default config file generated from `src/config/default-config.yml`
- [x] Profiles and watchfolders fully respect `TRANSCODR_CONFIG_DIR`
- [x] Daemon logging reconfigured after config load so `logging.dir` is honored
- [x] Shared profile cache (`ProfileStore`) with explicit cache clear on reload

### Web UI
- [x] Added **Reload Configuration** action in Settings > General (`POST /api/reload`)
- [x] Added manual **Refresh** actions on Profiles and Watchfolders pages

### Docker
- [x] Added `docker/deploy.sh` helper (`--no-cache`, `--help`)

---

## Planned Features

### Version 0.4: Subtitles Management
- [ ] Subtitles are never burned in (always separate streams)
- [ ] Auto-detect external subtitle files (`.srt`, `.ass`, `.ssa`, `.sub`, `.idx`, `.vtt`)
- [ ] Language detection from filename (`.en.srt`, `.english.srt`, etc.)
- [ ] `auto_embed_subtitles` option (default: true)
- [ ] Copy/move other non-video files when preserving structure (nfo/jpg/txt/etc.)

### Version 0.4: Notifications
- [ ] Event types: job complete, batch complete, queue empty, error alerts
- [ ] Channels: Email, Webhook, Desktop, Pushover, Gotify, ntfy
- [ ] Configurable notification payloads and per-channel settings

### Version 0.4: Audio File Encoding
- [ ] Lossless audio formats: FLAC, WAV, ALAC, APE, WavPack, DSD
- [ ] Audio-specific encoding profiles

### Version 0.4: Video Analysis Profiles
- [ ] New `analysis` profile type with deterministic + perceptual phases
- [ ] Technical heuristics (bpp, bitrate/resolution mismatch, re-encode signals)
- [ ] Perceptual artifact scoring (blocking, banding, blur, ringing, temporal)
- [ ] Profile auto-selection: AV1 vs x265 vs keep-as-is

### Version 0.5: Distributed Encoding
- [ ] Controller/worker architecture (local, LAN, remote)
- [ ] Job distribution strategies (round-robin, capability, load, priority)
- [ ] Worker registration + heartbeat monitoring
- [ ] Remote transfer workflow (rsync/sftp/scp)
- [ ] Phased rollout: local -> LAN -> remote -> auto-discovery

### Version 0.5: Video Filters
- [ ] Profile schema for filter configuration (scale, crop, deinterlace, etc.)
- [ ] Filter-chain generation with ordering rules
- [ ] Preset filter profiles (1080p/720p, deinterlace-only, clean-archive)
- [ ] VAAPI filter compatibility

### Future Considerations
- HDR metadata preservation
- Chapter/metadata handling
- NVENC/QSV hardware support
- Blu-ray disc support (MPLS parsing)

---

## Open Bugs / Risks

- Validate file duration for extract profiles; only create jobs that fit - fixed
- When the runner throws an exception, mark file as `.failed` (not `.processing`) - fixed
- Catch and log runner exceptions consistently - in progress
- Disallow replace + disable_temp combo for multi-profile runs; enforce in runner - fixed - to be enforced also on manual creation webUI
- Client job names should not include `.processing` - fixed
- Avoid 60s fixed timeout when waiting for temp copy state - fixed - use ioctl now, this timeout method is still used as fallback method for network share
- Add input/output FFmpeg args to fix `.mts` stream-copy artifacts

---

## Version History

### v0.4 (Planned)
- Video analysis profiles (0.4.1)
- Distributed encoding (0.4.2)
- Video filters (0.4.3)

### v0.3 (Current - v0.3.6 Released)
- ✅ Web UI basic layout (0.3.1) - **DONE**
- ✅ Bug fixes (0.3.2) - **DONE**
- ✅ Manual encoding with web UI (0.3.3) - **DONE**
- ✅ Extension mismatch handling + warning status (0.3.4) - **DONE**
- ✅ Docker preparation + settings UI (0.3.5) - **DONE**
- ✅ Config/runtime polish + reload UX improvements (0.3.6) - **DONE**

### v0.2 (v0.2.3 Released)
- ✅ Watch folder improvements (0.2.1) - **DONE**
- ✅ Extract profiles and stream mapping (0.2.2) - **DONE**
- ✅ Profile/job parameters (0.2.3) - **DONE**
- Subtitles management (0.2.4)
- Notifications (0.2.5)
- Audio file encoding (0.2.6)

### v0.3.6 (Current)
- Default config generated from `src/config/default-config.yml`
- Profiles/watchfolders now consistently use `TRANSCODR_CONFIG_DIR`
- Logging reconfigured after config load so `logging.dir` is applied
- Settings > General includes Reload Configuration (`POST /api/reload`)
- Profiles/Watchfolders pages include manual Refresh actions
- Docker helper script: `docker/deploy.sh`

### v0.3.5
- Docker support: Dockerfile, docker-compose.yml, GPU passthrough
- `TRANSCODR_CONFIG_DIR` environment variable for config directory override
- Settings API: `GET /api/config`, `PUT /api/config`
- Settings Web UI: Storage, Encoding, Daemon, Logging pages

### v0.3.4
- Extension mismatch handling for replace mode (`on_extension_mismatch` config)
- Warning job status with `warning_message` field
- Web UI: amber warning display, dynamic version, file browser refresh button
- `DELETE /api/queue/warning` endpoint

### v0.3.3
- Create Job page with file browser, profile selector, and multi-step form
- File browser API endpoint (`GET /api/browse`)
- `use_temp_folder` and `copy_source_to_temp` options for encoding jobs
- Fixed disk space estimation formula
- Improved error handling for validation errors
- All API endpoints under `/api` prefix

### v0.2.3
- Profile-level `destination:` with path placeholder support
- `use_profile_destination: true` for commands/watchfolders
- Per-source `max_concurrent_jobs` concurrency limits
- Configurable `profile_name_separator` in config

### v0.2.2
- Stream copy + extract profiles
- Audio/subtitle stream mapping (include all)
- Container handling fix for temp outputs
- Watchfolder ref-count finalization
- Profile cache reload + SQLite autocommit fix

### v0.2.1
- `$root_media` placeholder and environment variable expansion
- Folder drop processing with nested subdirectory support
- Folder structure preservation for dropped folders
- FolderProcessor with stability detection and completion tracking
- Dedicated `src/watcher/` module architecture

### v0.1
- Core encoding pipeline with multi-profile support
- Daemon with REST API and SQLite persistence
- Command and media watch folders
- Full CLI client
- VAAPI hardware acceleration
- Output organization options

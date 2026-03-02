# transcodr Roadmap

## Current Version: 0.4.3

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
| 9 | Notifications | ✅ Done | Desktop, Email, Apprise (ntfy/Gotify/Pushover) |
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

## Completed Features (v0.3.7)

### Invalid Watchfolders & Profiles
- [x] Invalid watchfolders (missing location, unknown profile, missing destination) tracked and shown as **Invalid** badge in Web UI
- [x] Multiple validation errors per watchfolder each shown on their own line (expanded view)
- [x] Profile destination path validation (non-existent destination shows as Invalid)

### Web UI — Profiles & Watchfolders Detail
- [x] Profile cards show description, codec, container always visible
- [x] Watchfolder cards show full path, assigned profiles, output destination always visible
- [x] Media/command type badge on watchfolder cards
- [x] Error details, scan interval, patterns, runtime stats moved to expanded view
- [x] **See yaml…** button in expanded view opens read-only YAML modal

### API
- [x] `GET /api/profiles/{name}/yaml` — raw YAML source of a profile file
- [x] `GET /api/watchfolders/{folder_id}/yaml` — raw YAML source of a watchfolder config file

---

## Completed Features (v0.4.0)

### ETA Display
- [x] Estimated time of completion (ETA) shown in active job cards alongside progress and FPS
- [x] ETA calculated from current encoding rate and remaining frames

---

## Completed Features (v0.4.1)

### Subtitles Management
- [x] Auto-detect external subtitle files alongside source videos (`.srt`, `.ass`, `.ssa`, `.sub`, `.idx`, `.vtt`)
- [x] Language detection from subtitle filename patterns (`.en.srt`, `.english.srt`, etc.)
- [x] `auto_embed_subtitles` profile option (default: `true`) — embed detected external subtitles as streams
- [x] Subtitle streams never burned in; always kept as separate passthrough streams
- [x] Copy/move non-video sidecar files (`.nfo`, `.jpg`, `.txt`, etc.) when preserving folder structure

---

## Completed Features (v0.4.2)

### Global Temp Copy Control
- [x] `storage.enable_temp_copy` config option (default: `false`) — global default for temp copy behavior
- [x] Runner enforces: replace-mode multi-profile jobs require `enable_temp_copy: true`
- [x] Watchfolder-level `disable_temp_copy` remains for per-folder override

### Built-in Profile Import
- [x] `base_profile: true` YAML field marks profiles as base/template (not for direct use)
- [x] Built-in profiles no longer auto-installed; available for selective import
- [x] `GET /api/profiles/builtins/list` — list available built-in profiles with install status
- [x] `POST /api/profiles/import-builtins` — import selected profiles (optional `?overwrite=true`)

### Web UI — Profile Import
- [x] **Import built-in profiles** button on Profiles page
- [x] Checkbox modal with install-status indicators and success/error feedback
- [x] **base** badge on profile cards for template profiles

---

## Completed Features (v0.4.3)

### Notifications
- [x] Three notification channels: Desktop (`notify-send`), Email (SMTP), Apprise
- [x] Apprise covers ntfy, Gotify, Pushover, Telegram, and 80+ services via URL config
- [x] Four event triggers: `on_job_complete`, `on_batch_complete`, `on_queue_empty`, `on_error`
- [x] `on_batch_complete` fires after ALL jobs from one submission finish
- [x] `on_queue_empty` fires once when queue drains (False→True transition)

### DB Schema Versioning
- [x] `db_meta` table stores app version that last wrote the database
- [x] Daemon checks on startup; exits cleanly with error on version mismatch
- [x] Silent migration for pre-v0.4.3 databases (adds `batch_id` column)
- [x] `src/version.py` centralizes `APP_VERSION` and `DB_COMPATIBLE_VERSIONS`

### Per-Submission Batch Tracking
- [x] `batch_id` UUID column in jobs table — all jobs from one submission share a batch ID
- [x] Accurate batch-complete detection across concurrent submissions

---

## Planned Features

### Version 0.4 (remaining): Profile/Watchfolder Editor UI
- [ ] Create and edit profiles directly in the Web UI (YAML editor or form)
- [ ] Create and edit watchfolder configs directly in the Web UI

### Future: Audio File Encoding
- [ ] Lossless audio formats: FLAC, WAV, ALAC, APE, WavPack, DSD
- [ ] Audio-specific encoding profiles

### Future: Video Analysis Profiles
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
- Disallow replace + disable_temp combo for multi-profile runs; enforce in runner - fixed (enforced via `enable_temp_copy` guard in v0.4.2)
- Client job names should not include `.processing` - fixed
- Avoid 60s fixed timeout when waiting for temp copy state - fixed - use ioctl now, this timeout method is still used as fallback method for network share
- Add input/output FFmpeg args to fix `.mts` stream-copy artifacts

---

## Version History

### v0.4 (Current — v0.4.3 Released)
- ✅ ETA display in job cards (0.4.0) - **DONE**
- ✅ Subtitles management — external subtitle auto-detect and embed (0.4.1) - **DONE**
- ✅ Built-in profile import UI + `enable_temp_copy` global option (0.4.2) - **DONE**
- ✅ Notifications (Desktop, Email, Apprise) + DB schema versioning (0.4.3) - **DONE**
- Profile/Watchfolder editor UI (pending)

### v0.3 (v0.3.7 Released)
- ✅ Web UI basic layout (0.3.1) - **DONE**
- ✅ Bug fixes (0.3.2) - **DONE**
- ✅ Manual encoding with web UI (0.3.3) - **DONE**
- ✅ Extension mismatch handling + warning status (0.3.4) - **DONE**
- ✅ Docker preparation + settings UI (0.3.5) - **DONE**
- ✅ Config/runtime polish + reload UX improvements (0.3.6) - **DONE**
- ✅ Invalid WF/Profile tracking + detail improvements + YAML modal (0.3.7) - **DONE**

### v0.2 (v0.2.3 Released)
- ✅ Watch folder improvements (0.2.1) - **DONE**
- ✅ Extract profiles and stream mapping (0.2.2) - **DONE**
- ✅ Profile/job parameters (0.2.3) - **DONE**

### v0.1
- ✅ Core encoding pipeline with multi-profile support
- ✅ Daemon with REST API and SQLite persistence
- ✅ Command and media watch folders
- ✅ Full CLI client
- ✅ VAAPI hardware acceleration
- ✅ Output organization options

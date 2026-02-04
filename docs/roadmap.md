# VideoTranscode Roadmap

## Current Version: 0.2.3

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
- [x] `destination: profile` directive for commands/watchfolders
- [x] Validation that profile destination directory exists
- [x] `create_profile_folders` cannot be mixed with `destination: profile`

### Concurrency Control
- [x] Per-command/watchfolder `max_concurrent_jobs` limit
- [x] Source-level tracking with database `source_id` column
- [x] Respects global limit while allowing per-source restrictions

### Output Naming
- [x] `profile_name_separator` config option (default: `_`)
- [x] Configurable separator for `append_profile_name` feature

---

## Planned Features

### Version 0.2.4: Subtitles Management
- [ ] Subtitles are never burned in (always separate streams)
- [ ] Auto-detect external subtitle files (`.srt`, `.ass`, `.ssa`, `.sub`, `.idx`, `.vtt`)
- [ ] Language detection from filename (`.en.srt`, `.english.srt`, etc.)
- [ ] `auto_embed_subtitles` option (default: true)
- [ ] Copy/move other non-video files when preserving structure (nfo/jpg/txt/etc.)

### Version 0.2.5: Notifications
- [ ] Event types: job complete, batch complete, queue empty, error alerts
- [ ] Channels: Email, Webhook, Desktop, Pushover, Gotify, ntfy
- [ ] Configurable notification payloads and per-channel settings

### Version 0.2.6: Audio File Encoding
- [ ] Lossless audio formats: FLAC, WAV, ALAC, APE, WavPack, DSD
- [ ] Audio-specific encoding profiles

### Version 0.2.7: Web UI
- [ ] Left-nav layout with Jobs/Watch Folders/Profiles/Settings/System
- [ ] Jobs activity + history views with filters and ordering
- [ ] Job detail accordion with resubmit support
- [ ] Watch folder status list

### Version 0.3.1: Video Analysis Profiles
- [ ] New `analysis` profile type with deterministic + perceptual phases
- [ ] Technical heuristics (bpp, bitrate/resolution mismatch, re-encode signals)
- [ ] Perceptual artifact scoring (blocking, banding, blur, ringing, temporal)
- [ ] Profile auto-selection: AV1 vs x265 vs keep-as-is

### Version 0.3.2: Distributed Encoding
- [ ] Controller/worker architecture (local, LAN, remote)
- [ ] Job distribution strategies (round-robin, capability, load, priority)
- [ ] Worker registration + heartbeat monitoring
- [ ] Remote transfer workflow (rsync/sftp/scp)
- [ ] Phased rollout: local -> LAN -> remote -> auto-discovery

### Version 0.3.3: Video Filters
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

- Watchfolder should not start if a referenced profile is missing
- Validate file duration for extract profiles; only create jobs that fit
- When the runner throws an exception, mark file as `.failed` (not `.processing`)
- Catch and log runner exceptions consistently
- Disallow replace + disable_temp combo for multi-profile runs; enforce in runner
- Make `duration_tolerance` disable with 0 (default 5)
- Client job names should not include `.processing`
- Avoid 60s fixed timeout when waiting for temp copy state
- Add input/output FFmpeg args to fix `.mts` stream-copy artifacts
- Add audio stream selection options (first-only vs all)
- Web UI should allow selection of a specific workflow/command

---

## Version History

### v0.3 (Planned)
- Video analysis profiles (0.3.1)
- Distributed encoding (0.3.2)
- Video filters (0.3.3)

### v0.2 (In Progress)
- ✅ Watch folder improvements (0.2.1) - **DONE**
- ✅ Extract profiles and stream mapping (0.2.2) - **DONE**
- ✅ Profile/job parameters (0.2.3) - **DONE**
- Subtitles management (0.2.4)
- Notifications (0.2.5)
- Audio file encoding (0.2.6)
- Web UI (0.2.7)

### v0.2.3 (Current)
- Profile-level `destination:` with path placeholder support
- `destination: profile` directive for commands/watchfolders
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

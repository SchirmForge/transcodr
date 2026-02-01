# VideoTranscode Roadmap

## Current Version: 0.1

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
| 8 | Notifications | ❌ Pending | Desktop, webhooks, Signal/Pushover |
| 9 | Video filters | ❌ Pending | Resize, crop, deinterlace, logo |
| 10 | Distributed encoding | ❌ Pending | Multiple workers |

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

## Planned Features

### Version 0.2.1: Watch Folder Improvements
- [x] `root_media` config placeholder for portable command files
- [ ] Folder parsing for nested directories
- [ ] Sub-folder detection and recursive processing
- [ ] New file detection during encoding

### Version 0.2.2: Extract Profiles
- [ ] Stream copy support (`copy: true` for video/audio)
- [ ] Time-based extraction (`start_time`, `duration`)
- [ ] Built-in extract profiles (3min samples at 3', 15', 30', 60', 90')

### Version 0.2.3: Audio File Encoding
- [ ] Lossless audio support (FLAC, WAV, ALAC, APE, WavPack, DSD)
- [ ] Audio-specific encoding profiles

### Version 0.2.4: Subtitles Management
- [ ] Auto-detect external subtitle files (.srt, .ass, .ssa, .sub, .vtt)
- [ ] Auto-embed subtitles with language detection
- [ ] Language pattern matching (en, eng, english → eng)
- [ ] Never burn-in subtitles (always as separate streams)

### Version 0.2.5: Notifications
- [ ] Job completion notifications
- [ ] Batch/queue completion alerts
- [ ] Error notifications
- [ ] Channels: Email, Webhook, Desktop, Gotify, ntfy

### Version 0.2.6: Web UI
- [ ] Jobs activity/history views
- [ ] Watch folder management
- [ ] Profile management
- [ ] Settings configuration
- [ ] System status and logs

### Version 0.2.7: Video Filters
- [ ] Scale/resize with aspect ratio
- [ ] Crop (black bar removal)
- [ ] Deinterlace (yadif, bwdif)
- [ ] Denoise, sharpen
- [ ] Logo/watermark overlay
- [ ] HDR to SDR tonemap
- [ ] Filter chain generation

### Version 0.3.1: Distributed Encoding
- [ ] Controller/worker architecture
- [ ] Worker types: local, LAN, remote
- [ ] Job distribution strategies
- [ ] File transfer for remote workers
- [ ] Worker health monitoring

### Future Considerations
- HDR metadata preservation
- Chapter/metadata handling
- NVENC/QSV hardware support
- Blu-ray disc support (MPLS parsing)

---

## Quick Reference

### Commands
```bash
# Daemon
python -m src.daemon

# CLI
python -m src.cli.client status
python -m src.cli.client submit /path/to/video.mkv -p x265-balanced
python -m src.cli.client jobs
python -m src.cli.client profiles
python -m src.cli.client watch
python -m src.cli.client reload
python -m src.cli.client purge -y
```

### Configuration Locations
- Config: `~/.config/videotranscode/config.yaml`
- Profiles: `~/.config/videotranscode/profiles/`
- Watchfolders: `~/.config/videotranscode/watchfolders/`
- Database: `~/.config/videotranscode/jobs.db`

### API Endpoints
- Status: `GET /status`
- Jobs: `GET/POST /jobs`, `GET/DELETE /jobs/{id}`
- Profiles: `GET /profiles`, `GET/DELETE /profiles/{name}`
- Watchfolders: `GET /watchfolders`, `GET/DELETE /watchfolders/{id}`
- Admin: `POST /reload`, `POST /purge`

---

## Version History

### v0.3 (Planned)
- Distributed encoding with controller/worker architecture

### v0.2 (Planned)
- Watch folder improvements (0.2.1)
- Extract profiles (0.2.2)
- Audio file encoding (0.2.3)
- Subtitles management (0.2.4)
- Notifications (0.2.5)
- Web UI (0.2.6)
- Video filters (0.2.7)

### v0.1 (Current)
- Core encoding pipeline with multi-profile support
- Daemon with REST API and SQLite persistence
- Command and media watch folders
- Full CLI client
- VAAPI hardware acceleration
- Output organization options

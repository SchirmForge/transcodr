# VideoTranscode Roadmap

## Use Cases Overview

| # | Use Case | Status | Notes |
|---|----------|--------|-------|
| 1 | Folder encoding with replacement | ✅ Done | CLI submit, recursive, patterns |
| 2 | Hot-folder (watch folder) | ⚠️ Partial | Monitoring works. Command file watcher pending |
| 3 | Notifications | ❌ Pending | Desktop, webhooks, Signal/Pushover |
| 4 | Auto hardware selection | ⚠️ Partial | VAAPI done. NVENC/QSV pending |
| 5 | All FFmpeg codecs | ⚠️ Partial | Schema supports all. AV1/H264 profiles pending |
| 5b | Parallel encoding | ✅ Done | max_concurrent_jobs in config |
| 6 | Transform parameters | ❌ Pending | Filters (resize, crop, logo) |
| 7 | Performance testing | ✅ Done | `tests/benchmark_concurrency.py` |

---

## Implementation Phases

### Phase 1: Complete Core Features (High Priority)

| Feature | Effort | Description |
|---------|--------|-------------|
| Command file watcher | Medium | Drop YAML in watch folder to trigger encoding with specific settings |
| Video filters in profiles | Medium | Add resize, crop, logo support to profile schema |
| AV1/H264 built-in profiles | Low | Create profiles for libaom-av1, svt-av1, libx264 |
| Configurable temp_dir | Low | Make temp directory configurable in daemon settings |
| vtc CLI alias | Low | Create proper entry point for CLI |

**Command File Watcher:**
Enables dropping encoding command files (YAML) into watch folders:
```yaml
# encode-movie.yaml (dropped in /media/watch/)
source: movie.mkv
profiles:
  - x265-balanced
  - x265-mobile
```

**Video Filters in Profiles:**
```yaml
video:
  codec: libx265
  filters:
    scale: "1920:-2"        # Resize to 1080p
    crop: "1920:800:0:140"  # Crop to 2.39:1
    logo:
      file: /path/to/logo.png
      position: "overlay=W-w-10:10"
```

---

### Phase 2: Monitoring & Notifications (Medium Priority)

| Feature | Effort | Description |
|---------|--------|-------------|
| Desktop notifications | Low | D-Bus/libnotify for Linux (job complete/fail) |
| Webhook notifications | Low | HTTP POST on events (job complete, queue empty) |
| Pushover/Signal | Medium | Mobile push notifications |
| Tray icon | High | System tray for status monitoring |

**Architecture:**
```
src/notifications/
├── __init__.py
├── base.py          # Abstract NotificationBackend
├── desktop.py       # D-Bus/libnotify (Linux)
├── webhook.py       # HTTP POST to configurable URL
└── pushover.py      # Pushover API
```

**Configuration:**
```yaml
notifications:
  enabled: true
  backends:
    - type: desktop
      on_complete: true
      on_fail: true
    - type: webhook
      url: https://example.com/webhook
      on_complete: true
```

---

### Phase 3: Tooling & DX (Low Priority)

| Feature | Effort | Description |
|---------|--------|-------------|
| Dry-run mode | Low | Show FFmpeg command without executing |
| Profile validation | Low | CLI command to validate profile syntax |
| Job history/stats | Medium | Historical encoding statistics |
| Web UI | High | Browser-based monitoring dashboard |

---

### Phase 4: Extended Hardware Support (Deferred)

| Feature | Effort | Description |
|---------|--------|-------------|
| NVENC detection | Medium | NVIDIA GPU hardware encoding |
| NVENC profiles | Low | hevc_nvenc, h264_nvenc profiles |
| Intel QSV detection | Medium | Intel Quick Sync Video |
| QSV profiles | Low | hevc_qsv, h264_qsv profiles |
| Portable hardware selection | Low | Auto-select based on available hardware |

**Note:** VAAPI (AMD GPU) is fully working. NVENC/QSV deferred until needed.

---

## Completed Features

### Core Encoding
- [x] FFmpeg wrapper with progress streaming
- [x] ffprobe helpers (codec detection, duration, validation)
- [x] Profile management (YAML-based, inheritance, hardware variants)
- [x] Safe file replacement (cross-device, backup, rollback)
- [x] Multi-profile encoding (one source -> multiple outputs)

### Daemon & API
- [x] FastAPI REST API
- [x] Job queue with SQLite persistence
- [x] Watch folder monitoring
- [x] Priority-based job ordering
- [x] Concurrent job execution (configurable)

### Hardware
- [x] VAAPI detection and auto-selection (AMD GPU)
- [x] Hardware variants in profiles

### CLI
- [x] Full CLI client for daemon API
- [x] Profile listing with hardware info

### Testing & Benchmarking
- [x] Concurrency benchmark tool (`tests/benchmark_concurrency.py`)
- [x] Benchmark-to-profile saver (`tests/save_benchmark_to_profile.py`)
- [x] Concurrency tuning guide (`docs/concurrency-tuning.md`)

---

## Future Considerations (Not Planned)

| Feature | Notes |
|---------|-------|
| Distributed encoding | Multiple daemons sharing jobs |
| GUI application | Native desktop app for profile/job management |
| Web-based profile editor | Browser UI for creating/editing profiles |
| HDR metadata preservation | Complex, codec-specific |
| Chapter/metadata handling | Nice to have, low priority |

---

## Quick Reference

### Current Commands
```bash
# Daemon
python -m src.daemon              # Start daemon

# CLI
python -m src.cli.client status   # Daemon status
python -m src.cli.client submit   # Submit job
python -m src.cli.client jobs     # List jobs
python -m src.cli.client profiles # List profiles

# Benchmarking
python tests/benchmark_concurrency.py x265-balanced 8 10
python tests/benchmark_concurrency.py x265-balanced 8 10 --source /path/to/video.mkv --cleanup
```

### Configuration Locations
- Config: `~/.config/videotranscode/config.yaml`
- Profiles: `~/.config/videotranscode/profiles/`
- Database: `~/.config/videotranscode/jobs.db`

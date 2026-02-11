# Video Transcoding Tool - Architecture

## Overview
A robust, production-ready video transcoding system with a daemon at its core exposing an API. All user interfaces (CLI, Web UI, future GUI) are clients of this API, ensuring consistency and simplifying development.

---

## Core Principles
1. **API-first architecture** - All interfaces are API clients
2. **FFmpeg is external and replaceable** - No hard version dependencies
3. **Never corrupt original media** - Atomic operations with rollback
4. **Data-driven configuration** - Profiles and settings are files, not code
5. **Fail-safe defaults** - Conservative settings, explicit opt-in for destructive operations

---

## System Architecture

### High-Level Overview
```
┌─────────────────────────────────────────────────────────────┐
│                      User Interfaces                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CLI    │  │  Web UI  │  │   GUI    │  │  Scripts │   │
│  │ (Typer)  │  │ (React)  │  │ (Future) │  │ (Python) │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │
              ┌───────▼──────────┐
              │   API (FastAPI)  │ ← HTTP/REST + WebSocket
              │   /jobs          │
              │   /profiles      │
              │   /system        │
              └───────┬──────────┘
                      │
        ┌─────────────▼─────────────┐
        │       Daemon Core          │
        │  ┌──────────────────────┐ │
        │  │  Job Queue Manager   │ │
        │  │  - Prioritization    │ │
        │  │  - Concurrency       │ │
        │  │  - State persistence │ │
        │  └──────────┬───────────┘ │
        │             │              │
        │  ┌──────────▼───────────┐ │
        │  │     Job Runner       │ │
        │  │  - Execution         │ │
        │  │  - Progress tracking │ │
        │  │  - Error recovery    │ │
        │  └──────────┬───────────┘ │
        └─────────────┼──────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
    ┌───▼────┐   ┌───▼────┐   ┌───▼─────┐
    │FFmpeg  │   │Probe   │   │Replace  │
    │Wrapper │   │Helpers │   │Manager  │
    └────────┘   └────────┘   └─────────┘
```

### Key Architectural Decision: API-First

**All interfaces are API clients:**
- **CLI**: Makes HTTP requests to daemon API (thin client)
- **Web UI**: Same API, different presentation layer
- **Future GUI**: Same API, native interface
- **Scripts**: Direct HTTP/Python client library

**Benefits:**
1. **Single source of truth**: One codebase, one behavior
2. **Consistency**: All interfaces have identical capabilities
3. **Easier testing**: Test API once, all interfaces benefit
4. **Simpler development**: No duplicate logic between CLI and API
5. **Remote control**: CLI can control daemon on different machine
6. **Progressive enhancement**: Start with CLI, add Web UI seamlessly

**Fallback mode for CLI:**
When daemon is not running, CLI can operate in two modes:
- **Default**: Warn "Daemon not running, use 'transcode-cli daemon start'"
- **Direct mode**: `--no-daemon` flag bypasses API, runs encode directly (one-shot, no queue)

---

## Daemon Architecture

### Daemon Core Components

```python
# src/daemon.py
class TranscodeDaemon:
    """
    Main daemon process that:
    1. Exposes FastAPI HTTP/WebSocket server
    2. Manages job queue and worker threads
    3. Monitors hot folders (optional)
    4. Persists state to SQLite
    """
    def __init__(self, config: Config):
        self.config = config
        self.queue_manager = QueueManager(config)
        self.job_runner = JobRunner(config)
        self.api_server = create_api_app(self.queue_manager, self.job_runner)
        self.hot_folders = HotFolderMonitor(config) if config.hot_folders else None

    def start(self):
        """Start API server, job runner, hot folder monitor"""
        # Start worker threads
        self.job_runner.start_workers(self.config.daemon.max_concurrent_jobs)
        # Start hot folder monitor if configured
        if self.hot_folders:
            self.hot_folders.start()
        # Start API server (uvicorn)
        uvicorn.run(self.api_server, host="127.0.0.1", port=8765)

    def stop(self):
        """Graceful shutdown: finish current jobs, save state"""
        # Stop accepting new jobs
        # Wait for current jobs (max 30s timeout)
        # Stop hot folder monitor
        # Save state and exit

    def reload_config(self):
        """SIGHUP handler: reload config without restart"""
```

**Process management:**
- PID file: `/var/run/transcodr.pid` (single instance)
- Signal handlers: SIGTERM (graceful stop), SIGINT (interrupt), SIGHUP (reload config)
- Socket: Unix socket or TCP (127.0.0.1:8765)
- Systemd service (future)

---

## CLI Architecture (API Client)

### CLI as API Client

```python
# src/cli.py (Typer app)
import typer
import httpx

app = typer.Typer()

def get_api_client() -> httpx.Client:
    """Get HTTP client for daemon API"""
    return httpx.Client(base_url="http://127.0.0.1:8765", timeout=30.0)

def check_daemon_running() -> bool:
    """Ping daemon health endpoint"""
    try:
        response = get_api_client().get("/health")
        return response.status_code == 200
    except httpx.ConnectError:
        return False

@app.command()
def add(file: str, profile: str, priority: int = 0):
    """Add file to encode queue"""
    if not check_daemon_running():
        typer.echo("Error: Daemon not running. Start with: transcode-cli daemon start")
        raise typer.Exit(1)

    # Make API request
    response = get_api_client().post(
        "/jobs",
        json={"source_path": file, "profile": profile, "priority": priority}
    )

    if response.status_code == 201:
        job = response.json()
        typer.echo(f"Job created: {job['id']}")
    else:
        typer.echo(f"Error: {response.text}")

@app.command()
def encode(file: str, profile: str, no_daemon: bool = False):
    """
    Encode file (via daemon or direct)
    --no-daemon: Skip daemon, run directly (one-shot)
    """
    if no_daemon:
        # Direct mode: import core libraries, run encode synchronously
        from src.core.ffmpeg import FFmpegWrapper
        from src.profiles.manager import ProfileManager
        # ... run encoding directly
    else:
        # Daemon mode: POST to /jobs and wait
        add(file, profile)
```

**CLI commands** (all via API):
```bash
# Daemon control
transcode-cli daemon start [--foreground]    # Start daemon process
transcode-cli daemon stop                    # POST /system/shutdown
transcode-cli daemon status                  # GET /health
transcode-cli daemon logs [--follow]         # Read log file (not API)

# System info
transcode-cli version                        # GET /system/version
transcode-cli doctor                         # GET /system/health + local checks
transcode-cli hardware                       # GET /system/hardware

# Profiles
transcode-cli profile list                   # GET /profiles
transcode-cli profile show <name>            # GET /profiles/{name}

# Jobs
transcode-cli job add <file> --profile <name> --priority N   # POST /jobs
transcode-cli job list [--state queued]                       # GET /jobs
transcode-cli job show <id>                                   # GET /jobs/{id}
transcode-cli job cancel <id>                                 # DELETE /jobs/{id}
transcode-cli job logs <id>                                   # GET /jobs/{id}/logs

# Batch
transcode-cli batch add <dir> --profile <name> --recursive    # POST /jobs/batch

# Inspection (local, no API needed)
transcode-cli inspect <file>                 # Direct ffprobe call

# One-shot (bypass daemon)
transcode-cli encode <file> --profile <name> --no-daemon      # Direct encode
```

**Why some commands are local:**
- `daemon start`: Must spawn daemon process locally
- `inspect`: Lightweight, no need for daemon overhead
- `encode --no-daemon`: Explicit bypass for scripting or daemon-less use

---

## Web UI Architecture

### Stack

- **React 19** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS 4** for styling
- **React Router** for client-side routing
- **TanStack React Query** for data fetching and caching

### Serving

The Web UI is built as a static SPA (`webui/dist/`) and served directly by the daemon's FastAPI server:
- Static assets (`/assets/*`) are served via `StaticFiles`
- All other non-API routes fall through to `index.html` for client-side routing
- API endpoints live under the `/api` prefix, keeping them cleanly separated from the SPA

### Pages

```
Jobs > Activity         — Active and queued jobs with progress
Jobs > Create           — Multi-step form to submit encoding jobs
Jobs > History          — Completed and failed job history
Configuration > Watch Folders  — Watch folder status and management
Configuration > Profiles       — Available encoding profiles
Settings > General      — General settings
System > Status         — Daemon status, hardware, queue info
```

### Data Fetching

React Query handles all API communication with:
- 5-second stale time
- 10-second refetch interval for live data (job progress, queue status)
- Automatic cache invalidation on mutations

### File Browser

The Create Job page includes a filesystem browser that uses the `GET /api/browse` endpoint to navigate directories and select video files for encoding.

---

## API Design (FastAPI)

### REST Endpoints

```python
# src/api.py
from fastapi import FastAPI, WebSocket
from src.jobs.queue import QueueManager
from src.jobs.runner import JobRunner

def create_api_app(queue: QueueManager, runner: JobRunner) -> FastAPI:
    app = FastAPI(title="Video Transcode API")

    # Health & System
    @app.get("/health")
    def health():
        """Daemon health check"""
        return {
            "status": "ok",
            "queue_size": queue.size(),
            "active_jobs": runner.active_count()
        }

    @app.get("/system/version")
    def version():
        """Return app version, FFmpeg version"""
        return {
            "app": "1.0.0",
            "ffmpeg": get_ffmpeg_version()
        }

    @app.get("/system/hardware")
    def hardware():
        """Return available hardware acceleration"""
        return detect_hardware_accel()

    @app.post("/system/shutdown")
    def shutdown():
        """Graceful daemon shutdown"""
        # Signal main loop to stop

    # Jobs
    @app.post("/jobs", status_code=201)
    def create_job(job_request: JobRequest):
        """Create new encode job"""
        job = queue.add_job(
            source_path=job_request.source_path,
            profile=job_request.profile,
            priority=job_request.priority
        )
        return job.to_dict()

    @app.get("/jobs")
    def list_jobs(state: str = None):
        """List jobs, optionally filter by state"""
        jobs = queue.get_jobs(state=state)
        return [job.to_dict() for job in jobs]

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        """Get job details"""
        job = queue.get_job(job_id)
        return job.to_dict()

    @app.delete("/jobs/{job_id}")
    def cancel_job(job_id: str):
        """Cancel job"""
        queue.cancel_job(job_id)
        return {"status": "cancelled"}

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str):
        """Retry failed job"""
        queue.retry_job(job_id)
        return {"status": "queued"}

    @app.get("/jobs/{job_id}/logs")
    def get_job_logs(job_id: str):
        """Get job logs"""
        return {"logs": read_job_logs(job_id)}

    @app.websocket("/jobs/{job_id}/progress")
    async def job_progress(websocket: WebSocket, job_id: str):
        """WebSocket for real-time progress updates"""
        await websocket.accept()
        # Stream progress updates from job
        async for progress in runner.watch_progress(job_id):
            await websocket.send_json(progress)

    @app.post("/jobs/batch")
    def create_batch_job(batch_request: BatchRequest):
        """Create multiple jobs from directory scan"""
        files = scan_directory(
            batch_request.path,
            recursive=batch_request.recursive
        )
        jobs = [
            queue.add_job(file, batch_request.profile)
            for file in files
        ]
        return {"created": len(jobs), "jobs": [j.to_dict() for j in jobs]}

    # Profiles
    @app.get("/profiles")
    def list_profiles():
        """List available profiles"""
        return ProfileManager.list_profiles()

    @app.get("/profiles/{name}")
    def get_profile(name: str):
        """Get profile details"""
        profile = ProfileManager.load_profile(name)
        return profile.to_dict()

    return app
```

### WebSocket for Progress

**Use case**: Real-time progress updates for long-running encodes

**Client example** (Web UI):
```javascript
const ws = new WebSocket('ws://127.0.0.1:8765/jobs/abc123/progress');
ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  // { frame: 1234, fps: 45, time: "00:01:23", percent: 45.2 }
  updateProgressBar(progress.percent);
};
```

**CLI example** (watch job progress):
```bash
transcode-cli job watch <id>  # Opens WebSocket, shows live progress bar
```

---

## Configuration Management

### Configuration Hierarchy
```
~/.config/transcodr/
├── config.yaml              # Main app configuration
├── profiles/                # User custom profiles
│   ├── my-profile.yaml
│   └── ...
└── jobs.db                  # SQLite job persistence
```

### config.yaml Structure
```yaml
# API/Daemon settings
daemon:
  host: 127.0.0.1           # API bind address
  port: 8765                # API port
  max_concurrent_jobs: 2    # Worker thread count
  pid_file: /var/run/transcodr.pid

# FFmpeg settings
ffmpeg:
  binary_path: /usr/bin/ffmpeg  # Override system FFmpeg
  hardware_accel: auto           # auto|vaapi|nvenc|qsv|none

# Storage settings
storage:
  temp_dir: /tmp/transcodr
  backup_originals: true
  backup_dir: ./.originals      # Relative to source
  min_free_space_gb: 10

# Logging settings
logging:
  level: INFO                   # DEBUG|INFO|WARNING|ERROR
  dir: ~/.local/share/transcodr/logs
  rotation: daily
  per_job_logs: true            # Separate log file per job

# Hot folder monitoring (optional)
hot_folders:
  - path: /media/downloads
    profile: x265-main
    min_age_seconds: 300        # Wait for file completion
    recursive: true

# Notifications (future)
notifications:
  on_complete: []               # webhook, email, desktop
  on_error: []
```

### Profile Structure
```yaml
# profiles/x265-main.yaml
name: x265-main
description: "Main x265 encode for general purpose"

# Optional: inherit from another profile
extends: base-x265

video:
  codec: libx265
  crf: 20
  preset: slow
  pix_fmt: yuv420p10le
  # Optional hardware variants
  hardware_variants:
    vaapi:
      codec: hevc_vaapi
    nvenc:
      codec: hevc_nvenc
      preset: slow

audio:
  copy: true                    # Copy audio streams
  # OR explicit encode:
  # codec: aac
  # bitrate: 192k

subtitles:
  copy: true

container: mkv
```

---

## Job State Machine

### States and Transitions
```
┌─────────┐
│ PENDING │  Initial state when job created
└────┬────┘
     │
     v
┌────────────┐
│ VALIDATING │  Pre-flight checks (file exists, space, codec support)
└────┬───────┘
     │
     ├─── FAILED (validation error)
     │
     v
┌────────┐
│ QUEUED │  Waiting for worker thread
└────┬───┘
     │
     ├─── CANCELLED (user cancelled)
     │
     v
┌─────────┐
│ RUNNING │  FFmpeg process active
└────┬────┘
     │
     ├─── FAILED (encode error)
     ├─── CANCELLED (user cancelled mid-encode)
     │
     v
┌──────────────────┐
│ VALIDATING_OUTPUT│  Verify encoded file (duration, integrity)
└────┬─────────────┘
     │
     ├─── FAILED (corrupt output)
     │
     v
┌───────────┐
│ REPLACING │  Atomic file replacement with backup
└────┬──────┘
     │
     ├─── FAILED (replace error)
     │
     v
┌───────────┐
│ COMPLETED │  Success
└───────────┘

     ┌───────┐
     │RETRYING│  Failed jobs can be retried
     └───┬───┘
         │
         └──> PENDING (start over)
```

### Job Model (Pydantic + SQLite)

```python
# src/jobs/model.py
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

class JobState(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    VALIDATING_OUTPUT = "validating_output"
    REPLACING = "replacing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class Job(BaseModel):
    id: str                     # UUID
    state: JobState
    source_path: str
    profile: str
    priority: int = 0
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0

    # Progress tracking
    progress_percent: float = 0.0
    frames_processed: int = 0
    frames_total: int = 0
    current_fps: float = 0.0
    eta_seconds: int = 0

    # Metadata
    source_size_bytes: int = 0
    output_size_bytes: int = 0
    source_codec: str | None = None
    output_codec: str | None = None
```

### SQLite Schema

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    source_path TEXT NOT NULL,
    profile TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    progress_percent REAL DEFAULT 0.0,
    metadata JSON  -- Additional fields as JSON
);

CREATE INDEX idx_jobs_state ON jobs(state);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_jobs_priority ON jobs(priority DESC);
```

---

## Core Components

### 1. FFmpeg Wrapper

```python
# src/core/ffmpeg.py
import subprocess
from pathlib import Path

class FFmpegWrapper:
    def __init__(self, binary_path: str = "ffmpeg"):
        self.binary_path = binary_path
        self.version = self._detect_version()

    def _detect_version(self) -> str:
        """Detect FFmpeg version"""
        result = subprocess.run(
            [self.binary_path, "-version"],
            capture_output=True,
            text=True
        )
        # Parse version from output
        return version

    def run(
        self,
        args: list[str],
        progress_callback=None
    ) -> subprocess.CompletedProcess:
        """
        Run FFmpeg with given arguments.
        Parse stderr for progress if callback provided.
        """
        cmd = [self.binary_path] + args

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Stream stderr for progress
        for line in process.stderr:
            if progress_callback:
                progress = self._parse_progress(line)
                if progress:
                    progress_callback(progress)

        process.wait()
        return process

    def _parse_progress(self, line: str) -> dict | None:
        """Parse FFmpeg progress line"""
        # frame= 1234 fps=45 q=28.0 size=12345kB time=00:01:23.45
        # Return: {frame: 1234, fps: 45, time: "00:01:23.45"}
```

### 2. Probe Helpers

```python
# src/core/probe.py
import json
import subprocess

class ProbeHelper:
    def __init__(self, ffprobe_path: str = "ffprobe"):
        self.ffprobe_path = ffprobe_path

    def get_info(self, file_path: Path) -> dict:
        """Get comprehensive file info"""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)

    def get_duration(self, file_path: Path) -> float:
        """Get duration in seconds"""
        info = self.get_info(file_path)
        return float(info["format"]["duration"])

    def get_video_codec(self, file_path: Path) -> str:
        """Get video codec name"""
        info = self.get_info(file_path)
        for stream in info["streams"]:
            if stream["codec_type"] == "video":
                return stream["codec_name"]

    def validate_file(self, file_path: Path) -> bool:
        """Validate file is playable"""
        try:
            info = self.get_info(file_path)
            return "format" in info
        except Exception:
            return False
```

### 3. Safe File Replacement

```python
# src/core/replace.py
import os
import shutil
from pathlib import Path

class SafeReplacer:
    def __init__(self, config):
        self.config = config
        self.probe = ProbeHelper()

    def replace(
        self,
        original: Path,
        encoded: Path,
        backup: bool = True
    ) -> None:
        """
        Safely replace original with encoded file.
        Steps:
        1. Validate encoded file
        2. Compare durations (tolerance: 1%)
        3. Create backup if enabled
        4. Atomic rename
        5. Cleanup temp file
        """
        # 1. Validate encoded
        if not self.probe.validate_file(encoded):
            raise ValueError("Encoded file is corrupt")

        # 2. Compare durations
        orig_duration = self.probe.get_duration(original)
        enc_duration = self.probe.get_duration(encoded)

        diff_percent = abs(orig_duration - enc_duration) / orig_duration * 100
        if diff_percent > 1.0:
            raise ValueError(f"Duration mismatch: {diff_percent:.2f}%")

        # 3. Create backup
        if backup:
            backup_path = self._create_backup(original)

        try:
            # 4. Atomic rename (encoded → original)
            os.replace(str(encoded), str(original))
        except Exception as e:
            # Rollback: restore backup
            if backup:
                os.replace(str(backup_path), str(original))
            raise e

    def _create_backup(self, original: Path) -> Path:
        """Create backup in .originals/ directory"""
        backup_dir = original.parent / ".originals"
        backup_dir.mkdir(exist_ok=True)

        backup_path = backup_dir / original.name
        shutil.copy2(original, backup_path)
        return backup_path
```

### 4. Job Queue Manager

```python
# src/jobs/queue.py
import sqlite3
from pathlib import Path
from src.jobs.model import Job, JobState

class QueueManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tables if not exist"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                source_path TEXT NOT NULL,
                profile TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                metadata JSON
            )
        """)
        conn.commit()
        conn.close()

    def add_job(self, source_path: str, profile: str, priority: int = 0) -> Job:
        """Add new job to queue"""
        job = Job(
            id=str(uuid.uuid4()),
            state=JobState.PENDING,
            source_path=source_path,
            profile=profile,
            priority=priority,
            created_at=datetime.now()
        )
        # Save to DB
        self._save_job(job)
        return job

    def get_next_job(self) -> Job | None:
        """Get highest priority QUEUED job"""
        # SELECT * FROM jobs WHERE state='queued' ORDER BY priority DESC, created_at LIMIT 1

    def update_job(self, job: Job):
        """Update job in DB"""

    def get_jobs(self, state: JobState | None = None) -> list[Job]:
        """List jobs, optionally filter by state"""
```

### 5. Job Runner

```python
# src/jobs/runner.py
import threading
from src.jobs.queue import QueueManager
from src.core.ffmpeg import FFmpegWrapper

class JobRunner:
    def __init__(self, config, queue: QueueManager):
        self.config = config
        self.queue = queue
        self.ffmpeg = FFmpegWrapper()
        self.workers = []

    def start_workers(self, num_workers: int):
        """Start worker threads"""
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self):
        """Worker thread main loop"""
        while True:
            job = self.queue.get_next_job()
            if job:
                self._execute_job(job)
            else:
                time.sleep(1)  # Wait for jobs

    def _execute_job(self, job: Job):
        """Execute a single job"""
        try:
            # Update state: RUNNING
            job.state = JobState.RUNNING
            self.queue.update_job(job)

            # Build FFmpeg command from profile
            profile = ProfileManager.load_profile(job.profile)
            args = self._build_ffmpeg_args(job.source_path, profile)

            # Run FFmpeg with progress callback
            def progress_callback(progress):
                job.progress_percent = progress["percent"]
                job.current_fps = progress["fps"]
                self.queue.update_job(job)

            result = self.ffmpeg.run(args, progress_callback=progress_callback)

            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")

            # Validate and replace
            job.state = JobState.VALIDATING_OUTPUT
            # ... validation logic

            job.state = JobState.REPLACING
            # ... replacement logic

            job.state = JobState.COMPLETED

        except Exception as e:
            job.state = JobState.FAILED
            job.error_message = str(e)

        finally:
            self.queue.update_job(job)
```

---

## Pre-flight Validation

```python
# src/core/validator.py
class JobValidator:
    def validate(self, job: Job) -> list[str]:
        """
        Run pre-flight checks. Return list of errors (empty = valid)
        """
        errors = []

        # 1. File exists and readable
        if not Path(job.source_path).exists():
            errors.append("Source file not found")

        # 2. File is valid video
        if not self.probe.validate_file(job.source_path):
            errors.append("Source file is not a valid video")

        # 3. Sufficient disk space
        source_size = Path(job.source_path).stat().st_size
        free_space = shutil.disk_usage(Path(job.source_path).parent).free
        required = source_size * 2 + (10 * 1024**3)  # 2x + 10GB

        if free_space < required:
            errors.append(f"Insufficient disk space: {free_space} < {required}")

        # 4. Profile exists
        if not ProfileManager.profile_exists(job.profile):
            errors.append(f"Profile '{job.profile}' not found")

        # 5. FFmpeg supports codec
        profile = ProfileManager.load_profile(job.profile)
        if not self.ffmpeg.supports_codec(profile.video.codec):
            errors.append(f"FFmpeg does not support codec '{profile.video.codec}'")

        return errors
```

---

## Hardware Acceleration

```python
# src/core/hardware.py
def detect_hardware_accel() -> list[str]:
    """
    Detect available hardware acceleration.
    Returns: ['vaapi', 'nvenc', 'qsv'] (subset)
    """
    available = []

    # Check VAAPI (Intel/AMD)
    if Path("/dev/dri/renderD128").exists():
        available.append("vaapi")

    # Check NVENC (NVIDIA)
    result = subprocess.run(["nvidia-smi"], capture_output=True)
    if result.returncode == 0:
        available.append("nvenc")

    # Check QuickSync (Intel)
    # ... similar detection

    return available
```

---

## Watch Folder Architecture

### Watch Folder Types

Video Transcode supports two types of watch folders:

```
WatchfolderService
├── CommandFileWatcher (type: command)
│   └── Watches for *.yaml command files
│   └── Encoding settings come from the YAML file
│
└── MediaFileWatcher (type: media)
    └── Watches for video/audio files
    └── Encoding settings come from watchfolder config
    └── Uses size stability for readiness detection
```

### File Stability Detection

For media watch folders, files are detected using size-based stability:

```python
@dataclass
class PendingFile:
    """Tracks a pending file for size stability detection."""
    first_seen: float
    last_size: int
    stable_count: int = 0

def is_file_ready(file_path: Path) -> bool:
    """Check if file is ready using size stability."""
    current_size = file_path.stat().st_size

    if path_str not in pending_files:
        # First time seeing this file
        pending_files[path_str] = PendingFile(
            first_seen=time.time(),
            last_size=current_size,
        )
        return False

    pending = pending_files[path_str]

    if current_size == pending.last_size:
        # Size unchanged - increment stable count
        pending.stable_count += 1
    else:
        # Size changed - reset counter
        pending.last_size = current_size
        pending.stable_count = 0

    return pending.stable_count >= config.stability_scans
```

### Media File Lifecycle

When encoding files from a media watchfolder:

```
movie.mkv                    # Original file detected
movie.mkv.processing         # Renamed during encoding
movie.mkv.processed          # Encoding succeeded
movie.mkv.failed             # Encoding failed
```

This prevents re-detection of files during encoding.

### Configuration (v0.1)

Watch folders are configured in `~/.config/transcodr/watchfolders/`:

```yaml
# Command watchfolder
watchfolder_location: /tmp/encode-commands
watchfolder_type: command
scan_interval: 5

# Media watchfolder
watchfolder_location: /home/user/downloads
watchfolder_type: media
scan_interval: 10
stability_scans: 3
profiles:
  - x265-balanced
output_mode: destination
destination: /media/encoded/
```

---

## Testing Strategy

### Unit Tests
```python
# tests/unit/test_ffmpeg.py
def test_ffmpeg_version_detection(mock_subprocess):
    """Test FFmpeg version parsing"""

def test_progress_parsing():
    """Test FFmpeg progress line parsing"""

# tests/unit/test_profiles.py
def test_profile_loading():
    """Test profile YAML parsing"""

def test_profile_inheritance():
    """Test profile extends mechanism"""

# tests/unit/test_jobs.py
def test_job_state_transitions():
    """Test valid state machine transitions"""

def test_job_prioritization():
    """Test queue returns highest priority job"""
```

### Integration Tests
```python
# tests/integration/test_full_workflow.py
def test_encode_workflow(sample_video):
    """
    End-to-end test:
    1. Start daemon
    2. Submit job via API
    3. Wait for completion
    4. Verify output file
    5. Verify backup created
    """
```

### Test media
```
tests/
├── media/
│   ├── sample-h264.mp4      # 5-second test video
│   ├── sample-hevc.mkv
│   └── corrupted.avi
├── mocks/
│   └── ffmpeg.py            # Mock FFmpeg subprocess
└── conftest.py              # Pytest media
```

---

## Error Handling

### Error Taxonomy
```python
# src/core/errors.py
class TranscodeError(Exception):
    """Base exception"""

class ValidationError(TranscodeError):
    """Pre-flight validation failed"""

class FFmpegNotFoundError(TranscodeError):
    """FFmpeg binary not found"""

class InsufficientSpaceError(TranscodeError):
    """Not enough disk space"""

class EncodingError(TranscodeError):
    """FFmpeg encoding failed"""

class CorruptedOutputError(TranscodeError):
    """Output file validation failed"""

class ReplacementError(TranscodeError):
    """File replacement failed"""
```

### Retry Policy
```python
# src/jobs/retry.py
class RetryPolicy:
    """Define retry behavior per error type"""

    RETRYABLE_ERRORS = [
        "InsufficientSpaceError",  # Retry after cleanup
        "TemporaryIOError",        # Retry on transient I/O error
    ]

    MAX_RETRIES = 3
    BACKOFF_SECONDS = [60, 300, 900]  # 1min, 5min, 15min
```

---

## Logging & Observability

### Structured Logging
```python
# src/core/logging.py
import logging
import json

def setup_logging(config):
    """Setup JSON logging for daemon"""
    handler = logging.FileHandler(config.logging.dir / "daemon.log")
    handler.setFormatter(
        logging.Formatter(
            json.dumps({
                "timestamp": "%(asctime)s",
                "level": "%(levelname)s",
                "message": "%(message)s",
                "extra": "%(extra)s"
            })
        )
    )
    logging.root.addHandler(handler)

class JobLogger:
    """Context manager for per-job logging"""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.log_file = Path(f"~/.local/share/transcodr/logs/job-{job_id}.log")

    def __enter__(self):
        self.logger = logging.getLogger(f"job.{self.job_id}")
        handler = logging.FileHandler(self.log_file)
        self.logger.addHandler(handler)
        return self.logger

    def __exit__(self, *args):
        # Cleanup handlers
```

### Log Rotation
- Daily rotation for daemon log
- Keep 30 days of logs
- Per-job logs kept until job deleted

---

## Project Structure (Revised)

```
transcodr/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ffmpeg.py           # FFmpeg wrapper
│   │   ├── probe.py            # ffprobe helpers
│   │   ├── replace.py          # Safe file replacement
│   │   ├── hardware.py         # Hardware acceleration detection
│   │   ├── validator.py        # Pre-flight validation
│   │   ├── logging.py          # Logging setup
│   │   └── errors.py           # Exception types
│   ├── config/
│   │   ├── __init__.py
│   │   ├── manager.py          # Config loading/validation
│   │   └── schema.py           # Pydantic models
│   ├── profiles/
│   │   ├── __init__.py
│   │   ├── manager.py          # Profile management
│   │   ├── schema.py           # Pydantic models
│   │   └── builtin/            # Default profiles
│   │       ├── x265-main.yaml
│   │       └── x265-high.yaml
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── model.py            # Job state machine & Pydantic models
│   │   ├── queue.py            # Queue manager (SQLite)
│   │   ├── runner.py           # Job execution engine
│   │   ├── batch.py            # Batch directory scanning
│   │   └── retry.py            # Retry policy
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI application
│   │   ├── queue.py            # Job queue with SQLite
│   │   ├── watcher.py          # Watchfolder service
│   │   └── models.py           # API request/response models
│   ├── api.py                  # FastAPI app (API endpoints)
│   ├── cli.py                  # Typer CLI (API client)
│   ├── daemon.py               # Daemon main loop
│   └── client.py               # Python client library (optional)
├── tests/
│   ├── media/               # Sample media files
│   ├── mocks/                  # Mock objects
│   ├── unit/
│   │   ├── test_ffmpeg.py
│   │   ├── test_profiles.py
│   │   ├── test_jobs.py
│   │   └── test_api.py
│   └── integration/
│       └── test_full_workflow.py
├── docs/
│   ├── architecture.md         # This file
│   ├── user-guide.md           # End-user documentation
│   └── api-reference.md        # API endpoint documentation
├── webui/                      # Web UI (React + Vite + TypeScript)
│   ├── src/
│   │   ├── api/                # API client and types
│   │   ├── components/         # Shared components (Layout, ProfileSelector, etc.)
│   │   ├── hooks/              # React Query hooks
│   │   └── pages/              # Page components (jobs, configuration, settings, system)
│   ├── dist/                   # Built SPA (served by daemon)
│   ├── package.json
│   └── vite.config.ts
├── local-docs/                 # Development notes (not for users)
│   └── readme-dev.md
├── scripts/
│   └── install-systemd.sh      # Install systemd service (future)
├── .vscode/
│   └── launch.json
├── .gitignore
├── environment.yml             # Conda environment
├── pyproject.toml              # Package metadata
└── README.md                   # Project overview
```

---

## Implementation Roadmap

### Phase 1: Foundation (API-First)
1. Project structure
2. Config management (config.yaml loading)
3. Logging setup
4. FFmpeg wrapper with version detection
5. Probe helpers
6. Error types

### Phase 2: Profiles
1. Profile schema (Pydantic)
2. Profile manager (YAML loading)
3. Built-in default profiles
4. Profile validation

### Phase 3: Job System
1. Job model (Pydantic + SQLite)
2. Job state machine
3. Queue manager (SQLite persistence)
4. Pre-flight validator

### Phase 4: API (Core Daemon)
1. FastAPI app (basic endpoints)
2. Job creation endpoint (POST /jobs)
3. Job listing (GET /jobs)
4. Health check (GET /health)
5. Profile endpoints (GET /profiles)

### Phase 5: Job Execution
1. Job runner (worker threads)
2. FFmpeg command building from profiles
3. Progress tracking and parsing
4. Safe file replacement

### Phase 6: CLI (API Client)
1. CLI structure (Typer)
2. Daemon control commands (start/stop/status)
3. Job commands (add/list/show/cancel)
4. Profile commands (list/show)
5. Rich progress display

### Phase 7: Advanced Features
1. Hardware acceleration auto-detection
2. Profile hardware variants
3. Batch directory scanning
4. Hot folder monitoring
5. WebSocket progress streaming

### Phase 8: Production Hardening
1. Comprehensive error handling
2. Retry logic
3. Integration tests
4. Performance tuning
5. Documentation (user guide + API reference)

### Phase 9: Packaging & Deployment
1. Systemd service file
2. Installation script
3. Package for PyPI (optional)

---

## Security Considerations

1. **API Security**:
   - Bind to localhost by default (127.0.0.1)
   - Optional: Add API key authentication for remote access
   - Rate limiting on job creation

2. **Path Traversal**:
   - Validate all file paths (no `../` escapes)
   - Restrict operations to user's home directory

3. **Command Injection**:
   - NEVER use `shell=True` in subprocess
   - Always use list of args (not string)

4. **Resource Exhaustion**:
   - Limit concurrent jobs
   - Enforce disk space checks
   - Timeout on stuck jobs

5. **Log Sanitization**:
   - Redact sensitive paths in public logs
   - Secure per-job logs (file permissions)

---

## Performance Considerations

1. **I/O Optimization**:
   - Use fast storage for temp directory (SSD/ramdisk)
   - Avoid encoding to same disk as source

2. **Concurrency**:
   - Default: 1-2 concurrent encodes (CPU-bound)
   - GPU encoding: Higher concurrency possible
   - Monitor system resources

3. **Database**:
   - SQLite WAL mode for concurrent reads
   - Indexes on job state and priority
   - Periodic VACUUM to prevent bloat

4. **Progress Updates**:
   - Throttle DB updates (every 1s, not per-frame)
   - Use in-memory cache for active jobs

---

## Future Enhancements (Out of Scope for v1)

1. **Distributed**: Multiple worker nodes, central coordinator
3. **Cloud Storage**: S3/GCS input/output
4. **Advanced Profiles**: Conditional logic, scene-based encoding
5. **Analytics**: Space saved, processing stats
6. **Plugins**: User hooks for pre/post-processing
7. **AV1 Support**: When hardware acceleration matures

---

## Key Improvements Summary

1. **API-First Architecture** - CLI is an API client, enabling easy Web UI/GUI development
2. **Fallback Mode** - CLI can run without daemon for one-shot encodes
3. **WebSocket Progress** - Real-time updates for all clients
4. **Unified Interface** - All capabilities available to all clients equally
5. **Remote Control** - CLI can control daemon on different machine (future)
6. **Simplified Development** - Single codebase, no duplicate logic
7. **Progressive Enhancement** - Start minimal, add features without refactor

---

## Questions for Consideration

1. **Authentication**: Should API require auth, or trust localhost-only?
2. **Remote Access**: Should daemon support remote CLI connections?
3. **Fallback Mode**: Should CLI always require daemon, or allow --no-daemon?
4. **Profile Distribution**: Ship with opinionated profiles or minimal examples?
5. **Systemd**: Auto-install systemd service or manual setup?
6. **Multi-User**: Single-user tool or support shared daemon?
7. **WebSocket**: Required for v1 or defer to later?

---

*This architecture document is the single source of truth for the project design. Update as implementation progresses and requirements evolve.*

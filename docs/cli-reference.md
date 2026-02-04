# CLI Reference

The Video Transcode CLI communicates with the daemon via HTTP API.

## Prerequisites

The daemon must be running before using CLI commands:

```bash
python -m src.daemon
```

## Usage

```bash
python -m src.cli.client <command> [options]
```

---

## Commands Overview

| Command | Description |
|---------|-------------|
| `status` | Show daemon status |
| `submit` | Submit encoding job |
| `jobs` | List jobs |
| `job` | Show job details |
| `cancel` | Cancel a job |
| `retry` | Retry a failed job |
| `watch` | List watchfolders |
| `profiles` | List available profiles |
| `pause` | Pause the job queue |
| `resume` | Resume the job queue |
| `clear` | Clear completed/failed jobs |
| `reload` | Reload daemon configuration |
| `purge` | Purge all job history |

---

## Command Details

### status

Show daemon status including queue info and hardware capabilities.

```bash
python -m src.cli.client status
```

**Example output:**
```
============================================================
DAEMON STATUS
============================================================

  Running:     True
  Version:     0.1.0
  Uptime:      3600s

QUEUE:
  Total jobs:     15
  Pending:        3
  Running:        2 / 2
  Completed:      8
  Failed:         2

HARDWARE:
  VAAPI:          Yes
  NVIDIA:         No
  Intel QSV:      No
  Recommended:    vaapi
```

---

### submit

Submit an encoding job or register a watch folder.

```bash
python -m src.cli.client submit [source] [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `source` | Source file or folder path |
| `-p, --profile` | Profile(s) to use (can repeat) |
| `-d, --destination` | Destination folder |
| `--no-backup` | Don't backup originals |
| `-r, --recursive` | Process subdirectories |
| `-f, --file` | Load request from YAML file |
| `--watch` | Register as watch folder |
| `--min-age` | Minimum file age for watch folder (seconds) |

**Examples:**

```bash
# Encode single file (replace mode)
python -m src.cli.client submit /path/to/video.mkv -p x265-balanced

# Encode to destination folder
python -m src.cli.client submit /path/to/videos/ \
  -p x265-balanced \
  -d /path/to/output/ \
  -r true

# Multi-profile encoding
python -m src.cli.client submit /path/to/video.mkv \
  -p x265-balanced \
  -p x265-fast \
  -d /path/to/output/

# Load from YAML file
python -m src.cli.client submit -f /path/to/request.yaml

# Register watch folder
python -m src.cli.client submit /path/to/watch/ \
  --watch \
  --min-age 60 \
  -p x265-balanced \
  -d /path/to/output/
```

---

### jobs

List jobs in the queue.

```bash
python -m src.cli.client jobs [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --status` | Filter by status (pending, running, completed, failed) |
| `-l, --limit` | Maximum jobs to show (default: 20) |

**Examples:**

```bash
# List all jobs
python -m src.cli.client jobs

# List only running jobs
python -m src.cli.client jobs -s running

# List failed jobs
python -m src.cli.client jobs -s failed

# Show more jobs
python -m src.cli.client jobs -l 50
```

**Example output:**
```
ID             Status       Profile         Progress   Source
----------------------------------------------------------------------------------
abc123456789   running      x265-balanced   45%        movie.mkv
def987654321   pending      x265-fast       0%         video.mp4
ghi123456789   completed    x265-balanced   100%       clip.mkv

Total: 3 jobs
```

---

### job

Show detailed information about a specific job.

```bash
python -m src.cli.client job <job_id>
```

**Example:**

```bash
python -m src.cli.client job abc123456789
```

**Example output:**
```
============================================================
JOB DETAILS
============================================================

  ID:            abc12345-1234-5678-9abc-def012345678
  Status:        running
  Profile:       x265-balanced
  Source:        /media/videos/movie.mkv
  Output:        /media/encoded/movie.mkv

  Progress:      45.2%
  FPS:           125.3
  Frames:        5420 / 12000

  Source size:   5000.0 MB
  Output size:   1800.0 MB (36%)

  Created:       2025-01-15T10:30:00
  Started:       2025-01-15T10:31:00
```

---

### cancel

Cancel a running or pending job.

```bash
python -m src.cli.client cancel <job_id>
```

**Example:**

```bash
python -m src.cli.client cancel abc123456789
```

---

### retry

Retry a failed job.

```bash
python -m src.cli.client retry <job_id>
```

**Example:**

```bash
python -m src.cli.client retry abc123456789
```

---

### watch

List all watchfolders (config-based and API-registered).

```bash
python -m src.cli.client watch
```

**Example output:**
```
COMMAND WATCHFOLDERS (watch for YAML command files):
  /tmp/encode-commands [active] (config)

MEDIA WATCHFOLDERS (watch for video files):
  /home/user/downloads [active] (config)
    profiles: x265-balanced
    destination: /media/encoded/
    pending: 2, submitted: 5
```

---

### profiles

List available encoding profiles.

```bash
python -m src.cli.client profiles
```

**Example output:**
```
Profile            Codec        Hardware     Description
--------------------------------------------------------------------------------
x265-balanced      libx265      vaapi        Balanced x265 encoding - good quality..
x265-quality       libx265      vaapi        High quality x265 encoding
x265-fast          libx265      vaapi        Fast x265 encoding

Total: 3 profiles
Location: /home/user/.config/videotranscode/profiles
```

---

### pause

Pause the job queue. Running jobs continue, but no new jobs start.

```bash
python -m src.cli.client pause
```

---

### resume

Resume the job queue.

```bash
python -m src.cli.client resume
```

---

### clear

Clear completed or failed jobs from history.

```bash
python -m src.cli.client clear [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--failed` | Clear failed jobs instead of completed |

**Examples:**

```bash
# Clear completed jobs
python -m src.cli.client clear

# Clear failed jobs
python -m src.cli.client clear --failed
```

---

### reload

Reload daemon configuration without restarting.

```bash
python -m src.cli.client reload
```

This reloads:
- Main configuration file
- Watchfolder configurations
- Profile cache

---

### purge

Purge all jobs from the database (clear all history).

```bash
python -m src.cli.client purge [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |
| `--force` | Force purge even with active jobs |

**Examples:**

```bash
# Purge with confirmation prompt
python -m src.cli.client purge

# Purge without confirmation
python -m src.cli.client purge -y

# Force purge (cancel active jobs)
python -m src.cli.client purge -y --force
```

---

## YAML Request Format

For complex encoding requests, use a YAML file with `--file`:

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
append_profile_name: false
delete_source: false
backup: true
recursive: true
file_patterns:
  - "*.mkv"
  - "*.mp4"
  - "*.m2ts"
priority: 5
hardware_accel: auto
```

Submit with:
```bash
python -m src.cli.client submit -f encoding-request.yaml
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (connection failed, invalid arguments, etc.) |

---

## Configuration

The CLI reads daemon connection settings from:
```
~/.config/videotranscode/config.yaml
```

Default settings:
```yaml
daemon:
  host: 127.0.0.1
  port: 8765
```

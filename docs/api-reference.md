# API Reference

The Video Transcode daemon exposes a REST API on `http://127.0.0.1:8765` (configurable).

## Authentication

No authentication is currently required. The API binds to localhost by default for security.

## Base URL

```
http://localhost:8765
```

---

## Status Endpoints

### GET /status

Get daemon status and queue information.

**Response:**
```json
{
  "running": true,
  "version": "0.1.0",
  "uptime_seconds": 3600.5,
  "queue": {
    "total_jobs": 15,
    "pending_jobs": 3,
    "running_jobs": 2,
    "completed_jobs": 8,
    "failed_jobs": 2,
    "max_concurrent": 2,
    "current_concurrent": 2
  },
  "watch_folders": [...],
  "hardware": {
    "vaapi": true,
    "nvenc": false,
    "qsv": false,
    "recommended": "vaapi"
  },
  "config_path": "/home/user/.config/videotranscode/config.yaml"
}
```

---

## Job Endpoints

### GET /jobs

List all jobs.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (pending, running, completed, failed) |
| `limit` | int | Maximum number of jobs to return |
| `offset` | int | Number of jobs to skip |

**Response:**
```json
{
  "jobs": [
    {
      "id": "abc12345-1234-5678-9abc-def012345678",
      "status": "running",
      "profile": "x265-balanced",
      "source_path": "/media/video.mkv",
      "output_path": "/media/encoded/video.mkv",
      "progress": 45.2,
      "fps": 125.3,
      "frames_processed": 5420,
      "frames_total": 12000,
      "created_at": "2025-01-15T10:30:00Z",
      "started_at": "2025-01-15T10:31:00Z",
      "source_size_bytes": 5000000000,
      "output_size_bytes": 0
    }
  ],
  "total": 15
}
```

### POST /jobs

Submit a new encoding job.

**Request Body:**
```json
{
  "request": {
    "profiles": ["x265-balanced", "x265-fast"],
    "source": "/media/videos/movie.mkv",
    "output_mode": "destination",
    "destination": "/media/encoded/",
    "use_profile_destination": false,
    "preserve_structure": true,
    "create_profile_folders": false,
    "append_profile_name": false,
    "delete_source": false,
    "backup": true,
    "recursive": false,
    "file_patterns": ["*.mkv", "*.mp4"],
    "priority": 5,
    "max_concurrent_jobs": null,
    "hardware_accel": null
  }
}
```

**Request Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `profiles` | array | Yes | - | List of profile names |
| `source` | string | Yes | - | Source file or folder path |
| `output_mode` | string | No | `replace` | `replace` or `destination` |
| `destination` | string | Conditional | - | Required if output_mode is `destination` and `use_profile_destination` is false |
| `use_profile_destination` | bool | No | `false` | Use each profile's `destination` field instead of a single folder |
| `preserve_structure` | bool | No | `true` | Recreate folder structure in destination |
| `create_profile_folders` | bool | No | `false` | Create subfolder per profile (mutually exclusive with `use_profile_destination`) |
| `append_profile_name` | bool | No | `false` | Add profile name to filename |
| `delete_source` | bool | No | `false` | Delete source after encoding |
| `backup` | bool | No | `true` | Create backup (replace mode only) |
| `backup_dir` | string | No | `.originals` | Backup directory |
| `recursive` | bool | No | `true` | Process subdirectories |
| `file_patterns` | array | No | `["*.mkv", "*.mp4", ...]` | File patterns to match |
| `priority` | int | No | `5` | Priority 1-10 (10 = highest) |
| `max_concurrent_jobs` | int | No | `null` | Max concurrent jobs for this request |
| `hardware_accel` | string | No | `null` | Override hardware acceleration |

**Response:**
```json
{
  "success": true,
  "job_ids": [
    "abc12345-1234-5678-9abc-def012345678",
    "def67890-1234-5678-9abc-def012345678"
  ],
  "message": "Created 2 job(s)"
}
```

### GET /jobs/{id}

Get job details by ID.

**Response:**
```json
{
  "id": "abc12345-1234-5678-9abc-def012345678",
  "status": "completed",
  "profile": "x265-balanced",
  "source_path": "/media/video.mkv",
  "output_path": "/media/encoded/video.mkv",
  "profile_index": 0,
  "total_profiles": 2,
  "parent_job_id": null,
  "progress": 100.0,
  "fps": 0,
  "frames_processed": 12000,
  "frames_total": 12000,
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:31:00Z",
  "completed_at": "2025-01-15T10:45:00Z",
  "source_size_bytes": 5000000000,
  "output_size_bytes": 2000000000,
  "error_message": null
}
```

### DELETE /jobs/{id}

Cancel a job.

**Response:**
```json
{
  "success": true,
  "message": "Job cancelled: abc12345-1234-5678-9abc-def012345678"
}
```

---

## Profile Endpoints

### GET /profiles

List all available encoding profiles.

**Response:**
```json
{
  "profiles": [
    {
      "name": "x265-balanced",
      "description": "Balanced x265 encoding",
      "codec": "libx265",
      "container": "mkv",
      "hardware_variants": ["vaapi"],
      "source": "builtin"
    },
    {
      "name": "my-custom",
      "description": "My custom profile",
      "codec": "libx265",
      "container": "mkv",
      "hardware_variants": [],
      "source": "user"
    }
  ],
  "total": 2
}
```

### GET /profiles/{name}

Get profile details.

**Response:**
```json
{
  "name": "x265-balanced",
  "description": "Balanced x265 encoding - good quality and reasonable speed",
  "extends": "base-x265",
  "container": "mkv",
  "video": {
    "codec": "libx265",
    "crf": 23,
    "preset": "medium",
    "pix_fmt": "yuv420p10le"
  },
  "audio": {
    "copy_streams": true
  },
  "subtitles": {
    "copy_streams": true
  },
  "hardware_variants": {
    "vaapi": {
      "video": {
        "codec": "hevc_vaapi",
        "hwaccel": "vaapi"
      }
    }
  },
  "tags": ["balanced", "recommended", "vaapi"],
  "source": "builtin"
}
```

### DELETE /profiles/{name}

Delete a user profile. Built-in profiles cannot be deleted.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `confirm` | bool | Yes | Must be `true` to confirm deletion |

**Request:**
```
DELETE /profiles/my-custom?confirm=true
```

**Response:**
```json
{
  "success": true,
  "message": "Profile deleted: my-custom"
}
```

**Error (built-in profile):**
```json
{
  "detail": "Cannot delete built-in profiles"
}
```

---

## Watchfolder Endpoints

### GET /watchfolders

List all watchfolders (config-based and API-registered).

**Response:**
```json
{
  "watchfolders": [
    {
      "id": "commands",
      "path": "/tmp/encode-commands",
      "type": "command",
      "source": "config",
      "active": true,
      "paused": false,
      "scan_interval": 5
    },
    {
      "id": "downloads",
      "path": "/home/user/downloads",
      "type": "media",
      "source": "config",
      "active": true,
      "paused": false,
      "profiles": ["x265-balanced"],
      "destination": "/media/encoded/",
      "use_profile_destination": false
    }
  ],
  "total": 2
}
```

### GET /watchfolders/{id}

Get watchfolder details.

### DELETE /watchfolders/{id}

Remove a watchfolder. Config-based watchfolders cannot be removed via API.

**Response:**
```json
{
  "success": true,
  "message": "Watchfolder removed: my-folder"
}
```

### POST /watchfolders/{id}/pause

Pause a watchfolder.

**Response:**
```json
{
  "success": true,
  "message": "Watchfolder paused: downloads"
}
```

### POST /watchfolders/{id}/resume

Resume a paused watchfolder.

**Response:**
```json
{
  "success": true,
  "message": "Watchfolder resumed: downloads"
}
```

---

## Queue Control Endpoints

### POST /queue/pause

Pause the job queue. Running jobs continue, but no new jobs start.

**Response:**
```json
{
  "success": true,
  "message": "Queue paused"
}
```

### POST /queue/resume

Resume the job queue.

**Response:**
```json
{
  "success": true,
  "message": "Queue resumed"
}
```

### POST /queue/clear-completed

Clear completed jobs from history.

**Response:**
```json
{
  "success": true,
  "message": "Cleared 15 completed jobs"
}
```

### POST /queue/clear-failed

Clear failed jobs from history.

**Response:**
```json
{
  "success": true,
  "message": "Cleared 3 failed jobs"
}
```

---

## Admin Endpoints

### POST /reload

Reload configuration and watchfolders without restarting the daemon.

**Response:**
```json
{
  "success": true,
  "message": "Configuration reloaded successfully",
  "config_path": "/home/user/.config/videotranscode/config.yaml"
}
```

### POST /purge

Purge all jobs from the database.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `confirm` | bool | Yes | Must be `true` to confirm |
| `force` | bool | No | Force purge even with active jobs |

**Request:**
```
POST /purge?confirm=true&force=false
```

**Response:**
```json
{
  "success": true,
  "message": "Purged 25 job(s) from database",
  "jobs_purged": 25
}
```

**Error (active jobs without force):**
```json
{
  "detail": "Cannot purge: 2 job(s) in progress. Use force=true to override."
}
```

---

## Error Responses

All endpoints return standard HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Resource not found |
| 409 | Conflict (e.g., active jobs blocking purge) |
| 500 | Internal server error |

**Error Response Format:**
```json
{
  "detail": "Error message describing the problem"
}
```

---

## Examples

### Submit a simple encoding job

```bash
curl -X POST http://localhost:8765/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "profiles": ["x265-balanced"],
      "source": "/media/video.mkv",
      "output_mode": "replace"
    }
  }'
```

### Submit multi-profile job to destination

```bash
curl -X POST http://localhost:8765/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "profiles": ["x265-balanced", "x265-fast"],
      "source": "/media/videos/",
      "output_mode": "destination",
      "destination": "/media/encoded/",
      "preserve_structure": true,
      "create_profile_folders": true,
      "recursive": true
    }
  }'
```

### Check job status

```bash
curl http://localhost:8765/jobs/abc12345-1234-5678-9abc-def012345678
```

### List profiles

```bash
curl http://localhost:8765/profiles
```

### Reload configuration

```bash
curl -X POST http://localhost:8765/reload
```

### Purge database

```bash
curl -X POST "http://localhost:8765/purge?confirm=true"
```

# Commands Guide

Commands are YAML encoding requests that define what to encode and how. They can be submitted via:
- **API**: POST to `/jobs` endpoint
- **CLI**: `python -m src.cli.client submit`
- **Command watchfolder**: Drop `.yaml` files into a watched directory

## Quick Reference

### Minimal Examples

**Encode single file (replace in-place):**
```yaml
profile: x265-balanced
source: /media/videos/movie.mkv
```

**Encode folder to destination:**
```yaml
profiles:
  - x265-balanced
source: /media/videos/
destination: /media/encoded/
```

**Multi-profile with separate outputs:**
```yaml
profiles:
  - x265-archival     # Has destination: /media/archive
  - x265-streaming    # Has destination: /media/streaming
source: /media/videos/movie.mkv
use_profile_destination: true  # Use each profile's destination
```

---

## Command Schema Reference

### Core Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source` | path | **Yes** | - | File or folder to process |
| `profiles` | list | **Yes** | - | List of encoding profiles to apply |
| `profile` | string | No | - | Alias for single profile (converted to `profiles`) |

### Output Control

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output_mode` | string | `replace` | `replace` (in-place with backup) or `destination` |
| `destination` | path | null | Output folder path (required if output_mode is destination and use_profile_destination is false) |
| `use_profile_destination` | bool | `false` | Use each profile's destination field instead of a single folder |
| `preserve_structure` | bool | `true` | Recreate source folder hierarchy in destination |
| `create_profile_folders` | bool | `false` | Create subfolder per profile (e.g., `dest/x265-balanced/`) |
| `append_profile_name` | bool | `false` | Add profile name to filename (e.g., `video_x265-balanced.mkv`) |

> **Note:** `create_profile_folders` cannot be used with `use_profile_destination: true`.

### Source Handling

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `recursive` | bool | `true` | Process subdirectories when source is a folder |
| `file_patterns` | list | `["*.mkv", "*.mp4", ...]` | Glob patterns for file matching |
| `delete_source` | bool | `false` | Delete source after successful encoding |
| `backup` | bool | `true` | Backup originals before replace (replace mode only) |
| `backup_dir` | path | `.originals` | Backup directory (relative or absolute) |

### Job Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `priority` | int | `5` | Job priority 1-10 (higher = processed first) |
| `max_concurrent_jobs` | int | null | Limit concurrent jobs from this command |
| `hardware_accel` | string | null | Override hardware acceleration (`auto`, `vaapi`, `nvenc`, `qsv`, `none`) |

---

## Output Organization

### Option 1: Replace In-Place

Source file is replaced with encoded version. Original backed up to `.originals/`.

```yaml
profile: x265-balanced
source: /media/videos/movie.mkv
output_mode: replace
backup: true
```

### Option 2: Destination Folder

Output to a separate directory.

```yaml
profiles:
  - x265-balanced
source: /media/videos/
destination: /media/encoded/
```

### Option 3: Profile Folders

Create a subfolder for each profile.

```yaml
profiles:
  - x265-quality
  - x265-fast
source: /media/videos/movie.mkv
destination: /media/encoded/
create_profile_folders: true
```

Output:
```
/media/encoded/
├── x265-quality/
│   └── movie.mkv
└── x265-fast/
    └── movie.mkv
```

### Option 4: Profile Destinations

Each profile outputs to its own configured destination.

```yaml
profiles:
  - x265-archival     # Profile has: destination: /media/archive
  - x265-streaming    # Profile has: destination: /media/streaming
source: /media/videos/movie.mkv
use_profile_destination: true
```

Output:
```
/media/archive/movie.mkv      # From x265-archival profile
/media/streaming/movie.mkv    # From x265-streaming profile
```

### Option 5: Append Profile Name

Add profile name to filename (useful when outputting to same folder).

```yaml
profiles:
  - x265-quality
  - x265-fast
source: /media/videos/movie.mkv
destination: /media/encoded/
append_profile_name: true
```

Output:
```
/media/encoded/
├── movie_x265-quality.mkv
└── movie_x265-fast.mkv
```

The separator (`_` by default) can be changed in daemon config with `storage.profile_name_separator`.

---

## Path Placeholders

Commands support these placeholders for portable paths:

| Placeholder | Expands To |
|-------------|------------|
| `$root_media` | Value of `storage.root_media` in daemon config |
| `$HOME`, `${HOME}` | User's home directory |
| `~` | User's home directory |
| `$USER` | Current username |

```yaml
profile: x265-balanced
source: $root_media/incoming/
destination: $root_media/encoded/
```

---

## Concurrency Control

Limit how many jobs run simultaneously from a single command:

```yaml
profiles:
  - x265-balanced
source: /mnt/slow-nas/videos/
destination: /mnt/slow-nas/encoded/
max_concurrent_jobs: 1  # Only 1 job at a time
```

This is useful when:
- Source/destination are on slow storage (NAS, HDD)
- You want to limit resource usage for batch jobs
- You need predictable throughput

The limit cannot exceed the daemon's global `max_concurrent_jobs` setting.

---

## Complete Examples

### Batch Encode with Structure Preservation

```yaml
profiles:
  - x265-balanced
source: $root_media/movies/
destination: $root_media/encoded/
preserve_structure: true
recursive: true
file_patterns:
  - "*.mkv"
  - "*.mp4"
  - "*.m2ts"
priority: 3  # Low priority for background batch
```

### Multi-Profile to Different Destinations

```yaml
# Profiles must have destination: defined
profiles:
  - x265-archival      # destination: /media/archive
  - x265-streaming     # destination: /media/streaming
  - extract-3m-at-15   # destination: /media/samples
source: /media/incoming/movie.mkv
use_profile_destination: true
```

### High-Priority Single File

```yaml
profile: x265-fast
source: /media/urgent/video.mkv
destination: /media/output/
priority: 10
hardware_accel: vaapi
```

### Delete Source After Encoding

```yaml
profiles:
  - x265-balanced
source: /media/temp-recordings/
destination: /media/archive/
delete_source: true
recursive: true
```

---

## Command Watch Folder Setup

To automatically process command files, create a command-type watchfolder:

```yaml
# ~/.config/transcodr/watchfolders/commands.yaml
watchfolder_location: /var/spool/transcodr
watchfolder_type: command
scan_interval: 5
```

Then drop `.yaml` command files into `/var/spool/transcodr/`.

### Command File Lifecycle

1. Daemon scans directory every `scan_interval` seconds
2. New `.yaml` file detected, waits 2 seconds for write completion
3. Command parsed and validated
4. Jobs created and file moved to `processed/`
5. If validation fails: file moved to `failed/` with `.errors` file

---

## Troubleshooting

### Command Not Processed

1. Verify watchfolder is running: `python -m src.cli.client watch`
2. Check file extension is `.yaml`
3. Wait at least 5 seconds after dropping file
4. Check for syntax errors in YAML

### Command Moved to failed/

1. Read the `.errors` file in `failed/` directory
2. Common issues:
   - Source path doesn't exist
   - `destination` missing when using `output_mode: destination`
   - Profile not found
   - `use_profile_destination: true` used but profile has no destination

### Jobs Not Starting

1. Check queue status: `python -m src.cli.client status`
2. Verify `max_concurrent_jobs` isn't blocking
3. Check priority (lower priority jobs wait for higher ones)

---

## Best Practices

1. **Use `$root_media`** for portable commands that work across systems
2. **Set appropriate priority** - use lower values (1-4) for batch jobs
3. **Use `destination` mode** instead of `replace` for safety
4. **Limit `file_patterns`** to avoid scanning unnecessary files
5. **Use `max_concurrent_jobs`** for slow storage to avoid I/O saturation
6. **Test with a single file** before processing entire folders

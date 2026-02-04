# Watch Folders Guide

Watch folders automatically detect and encode files without manual intervention.

## Watch Folder Types

Video Transcode supports two types of watch folders:

| Type | Description | Use Case |
|------|-------------|----------|
| `command` | Watches for YAML command files | Dynamic encoding with per-file settings |
| `media` | Watches for video files directly | Automated encoding with fixed settings |

---

## Configuration Location

Watch folder configs are stored in:
```
~/.config/videotranscode/watchfolders/
```

Each `.yaml` file defines one watch folder.

---

## Command Watch Folders

Command watch folders monitor a directory for YAML encoding request files.

### Configuration

```yaml
# ~/.config/videotranscode/watchfolders/commands.yaml
watchfolder_location: /tmp/encode-commands
watchfolder_type: command
scan_interval: 5
```

### How It Works

1. Drop a YAML command file in the watched directory
2. Daemon detects the file and reads the encoding request
3. Jobs are created based on the request
4. The command file is deleted after processing

### Command File Format

```yaml
# /tmp/encode-commands/encode-movie.yaml
profile: x265-balanced
source: /media/videos/movie.mkv
output_mode: replace
backup: true
```

Or with multiple profiles:

```yaml
# /tmp/encode-commands/encode-folder.yaml
profiles:
  - x265-balanced
  - x265-fast
source: /media/videos/
output_mode: destination
destination: /media/encoded/
preserve_folder_structure: true
recursive: true
```

### Using $root_media Placeholder

Command files can use `$root_media` as a placeholder for a base path defined in `config.yaml`:

**config.yaml:**
```yaml
storage:
  root_media: /mnt/nas/videos   # Or ~/Videos, /home/$USER/media
```

**Command file:**
```yaml
profile: x265-balanced
source: $root_media/movies/
output_mode: destination
destination: $root_media/encoded/
recursive: true
```

This makes command files portable - change `root_media` in config and all paths update.

### Use Cases

- Remote job submission via file drop
- Integration with other tools/scripts
- Per-file encoding settings
- Portable command files with `$root_media` placeholder

---

## Media Watch Folders

Media watch folders monitor a directory for video files directly.

### Configuration

```yaml
# ~/.config/videotranscode/watchfolders/downloads.yaml
watchfolder_location: /home/user/downloads
watchfolder_type: media

# Scan settings
scan_interval: 10
stability_scans: 3

# File matching
file_patterns:
  - "*.mkv"
  - "*.mp4"
  - "*.m2ts"
recursive: false

# Encoding settings
profiles:
  - x265-balanced
output_mode: destination
destination: /media/encoded/
backup: true
priority: 5
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Location/Type** ||||
| `watchfolder_location` | path | required | Directory to monitor |
| `watchfolder_type` | string | `command` | `command` or `media` |
| **File Detection** ||||
| `scan_interval` | float | `5.0` | Seconds between scans (min: 1.0) |
| `stability_scans` | int | `2` | Consecutive stable size scans before processing |
| `file_patterns` | list | `["*.mkv", "*.mp4", ...]` | Glob patterns to match |
| `recursive` | bool | `false` | Detect files in watchfolder subdirectories (i.e.: multi-user mode) |
| `allow_folder_drop` | bool | `false` | Enable processing of dropped folders as complete units |
| **Encoding (media type)** ||||
| `profiles` | list | `[]` | Encoding profiles (required for media type) |
| `destination` | path | null | Output directory (required for media, must differ from watchfolder_location) |
| `temp_folder` | path | null | Temp folder for source copy during encoding |
| `disable_temp_copy` | bool | `false` | If true, encode directly from source without copying |
| `keep_processed_files` | bool | `true` | Keep source (rename to .processed) or delete after encoding |
| `preserve_folder_structure` | bool | `true` | Maintain folder hierarchy from source to destination |
| `hardware_accel` | string | null | Override hardware acceleration |
| `priority` | int | `5` | Job priority (1=lowest, 10=highest) |

> **Note:** `recursive` and `allow_folder_drop` are mutually exclusive. Use `recursive` for multi-user scenarios where files are dropped in user subdirectories. Use `allow_folder_drop` to process entire folders as units.

### File Stability Detection

For large files (especially over network/HDD), Video Transcode uses size-based stability detection:

1. File is detected in watched directory
2. File size is recorded
3. On next scan, size is compared
4. If size unchanged for `stability_scans` consecutive scans, file is ready
5. If size changed, counter resets

**Example:** With `scan_interval: 10` and `stability_scans: 3`:
- File must be unchanged for 30 seconds before processing

### File Lifecycle

When a media file is detected:

```
movie.mkv                    # Original file
movie.mkv.processing         # Renamed while encoding (prevents re-detection)
movie.mkv.processed          # Encoding succeeded
movie.mkv.failed             # Encoding failed
```

The original file is renamed to prevent re-detection during encoding.

### Source File Handling After Encoding

The `keep_processed_files` setting controls what happens to source files after successful encoding:

#### keep_processed_files: true (default)

Source files are renamed with a `.processed` suffix to prevent re-detection:

```yaml
keep_processed_files: true  # Default behavior
```

**Single File:**
```
movie.mkv                    # Original file
movie.mkv.processing         # During encoding
movie.mkv.processed          # After successful encoding
```

**Folder:**
```
MyMovie/                     # Original folder
MyMovie/                     # Files inside marked .processing during encoding
MyMovie.processed/           # After all files complete
```

#### keep_processed_files: false

Source files and folders are **permanently deleted** after successful encoding:

```yaml
keep_processed_files: false  # WARNING: Deletes source files!
```

**Single File:**
- File is deleted after successful encoding
- Only the encoded file in destination remains

**Folder:**
- Entire folder tree is deleted (including non-video files)
- Only encoded files in destination remain

> **Warning:** Use `keep_processed_files: false` with caution:
> - Source files cannot be recovered after deletion
> - For folders, ALL contents are deleted (not just video files)
> - Failed encodes leave source as `.failed` (not deleted)
> - Ensure destination has adequate space before enabling

### Folder Processing

When `allow_folder_drop: true` is set, folders dropped into a media watchfolder are processed as complete units.

> **Important:** Set `allow_folder_drop: true` to enable folder processing. By default, dropped folders are ignored.

#### How It Works

1. **Detection**: Folder detected at top level of watchfolder
2. **Registration**: Folder registered for recursive processing
3. **Initial Scan**: All video files matching `file_patterns` discovered recursively inside the folder
4. **Stability Detection**: Each file undergoes size stability checks individually
5. **Job Submission**: Ready files submitted for encoding as they become stable
6. **Continuous Re-scanning**: Folder re-scanned during encoding to catch new files
7. **Completion**: Folder complete when all jobs done and no new files detected

#### Completion Criteria

A folder is considered complete when ALL conditions are met:
- All encoding jobs finished (success or failure)
- No files waiting for stability checks
- Multiple scans show no new files (`stable_scans >= stability_scans`)

#### Example: Processing a Movie Folder

```yaml
# Enable folder processing
allow_folder_drop: true
```

```
/watchfolder/
└── My.Movie.2024/              # Dropped folder
    ├── movie.mkv               # Video file
    ├── movie.srt               # Subtitle (ignored - not in file_patterns)
    └── extras/
        └── trailer.mkv         # Nested video file
```

Processing flow:
1. Folder detected and registered
2. `movie.mkv` and `extras/trailer.mkv` discovered
3. Both files undergo stability checks
4. Jobs submitted as files become stable
5. After all jobs complete, folder marked complete
6. Based on `keep_processed_files`:
   - `true`: Folder renamed to `My.Movie.2024.processed/`
   - `false`: Entire folder tree deleted

> **Note:** Folders are always scanned recursively for video files. The `recursive` watchfolder setting controls single-file detection in subdirectories (a different feature).

### Temporary File Handling

By default, source files are copied to a temp folder before encoding to protect the original during the encode process.

#### temp_folder

Specifies where to copy source files during encoding:

```yaml
temp_folder: /fast-ssd/encode-temp
```

- Default: System temp directory (`/tmp/videotranscode`)
- Should be on fast storage (SSD preferred)
- Requires enough space for the largest source file

#### disable_temp_copy

When `true`, encodes directly from the source file without copying:

```yaml
disable_temp_copy: true
```

- **Pros**: Faster startup (no copy phase), uses less disk space
- **Cons**: Source must not change during encoding; slow source storage impacts encode speed
- Recommended only when source is on reliable, fast storage

### Important Notes

**Output Mode Requirement:**
Media watch folders must use `output_mode: destination`. Replace mode would cause infinite re-encoding loops (encoded file would be detected again).

**Destination Must Differ:**
The destination directory must be different from the watch folder location.

---

## Managing Watch Folders

### List Watch Folders

```bash
python -m src.cli.client watch
```

### Pause/Resume

Via CLI (future) or API:

```bash
# Pause
curl -X POST http://localhost:8765/watchfolders/downloads/pause

# Resume
curl -X POST http://localhost:8765/watchfolders/downloads/resume
```

### Reload Configuration

After editing watch folder or profile configs:

```bash
python -m src.cli.client reload
```

This reloads watchfolder configurations and clears the profile cache, ensuring any profile changes take effect immediately.

---

## Examples

### Simple Downloads Folder

Encode all videos from downloads to an encoded folder:

```yaml
# ~/.config/videotranscode/watchfolders/downloads.yaml
watchfolder_location: /home/user/Downloads
watchfolder_type: media
scan_interval: 30
stability_scans: 2
profiles:
  - x265-balanced
destination: /media/videos/
```

### Recording Server

Encode TV recordings from a PVR:

```yaml
# ~/.config/videotranscode/watchfolders/recordings.yaml
watchfolder_location: /media/recordings
watchfolder_type: media
scan_interval: 60
stability_scans: 3
file_patterns:
  - "*.ts"
  - "*.m2ts"
recursive: true
profiles:
  - x265-quality
destination: /media/archive/
priority: 3
```

### Multi-Profile Output

Create multiple versions for different devices:

```yaml
# ~/.config/videotranscode/watchfolders/ripping.yaml
watchfolder_location: /media/rips
watchfolder_type: media
scan_interval: 30
stability_scans: 2
file_patterns:
  - "*.mkv"
profiles:
  - x265-quality
  - x265-fast
destination: /media/encoded/
priority: 5
```

Output structure:
```
/media/encoded/
├── x265-quality/
│   └── movie.mkv
└── x265-fast/
    └── movie.mkv
```

### Command File Drop Zone

For integration with other tools:

```yaml
# ~/.config/videotranscode/watchfolders/commands.yaml
watchfolder_location: /var/spool/videotranscode
watchfolder_type: command
scan_interval: 5
```

### Auto-Delete After Encoding

For fully automated pipelines where source cleanup is desired:

```yaml
# ~/.config/videotranscode/watchfolders/auto-cleanup.yaml
watchfolder_location: /media/incoming
watchfolder_type: media
scan_interval: 30
stability_scans: 3

profiles:
  - x265-balanced

destination: /media/encoded/
keep_processed_files: false    # DELETE sources after encoding

# Recommended: use temp copy for safety
disable_temp_copy: false
temp_folder: /fast-ssd/temp
```

> **Warning:** With `keep_processed_files: false`:
> - Source files are permanently deleted after successful encoding
> - Source folders are completely removed (including non-video files)
> - Failed encodes leave source as `.failed` (not deleted)

### Folder Drop Processing

Process entire folders as units (e.g., movie folders with video + extras):

```yaml
# ~/.config/videotranscode/watchfolders/movies.yaml
watchfolder_location: /media/rips
watchfolder_type: media
scan_interval: 30
stability_scans: 3

allow_folder_drop: true    # Enable folder processing
recursive: false           # Cannot use both

profiles:
  - x265-balanced

destination: /media/movies/
preserve_folder_structure: true   # Keep folder/subfolder structure
```

Drop a folder:
```
/media/rips/My.Movie.2024/
├── My.Movie.2024.mkv
└── Extras/
    └── Trailer.mkv
```

Output:
```
/media/movies/My.Movie.2024/
├── My.Movie.2024.mkv
└── Extras/
    └── Trailer.mkv
```

### Multi-User Shared Watchfolder

Multiple users drop files in their own subdirectories:

```yaml
# ~/.config/videotranscode/watchfolders/shared.yaml
watchfolder_location: /shared/encode-queue
watchfolder_type: media
scan_interval: 60
stability_scans: 2

recursive: true            # Scan user subdirectories for files
allow_folder_drop: false   # Don't process folders as units

profiles:
  - x265-balanced

destination: /shared/encoded/
preserve_folder_structure: true   # Maintain user subdirectory in output
```

Users drop files:
```
/shared/encode-queue/
├── alice/
│   └── video1.mkv
└── bob/
    └── video2.mkv
```

Output:
```
/shared/encoded/
├── alice/
│   └── video1.mkv
└── bob/
    └── video2.mkv
```

---

## Troubleshooting

### Files Not Being Detected

1. Check file patterns match your files
2. Verify `recursive` setting if files are in subdirectories
3. Check scan interval (increase for slow storage)
4. Increase stability_scans for large files over network

### Infinite Encoding Loop

If files keep getting re-encoded:
- Ensure `output_mode: destination` is set
- Verify destination differs from watch folder
- Check that `.processing` suffix is being applied

### High CPU During Scans

- Increase `scan_interval`
- Reduce `recursive` if not needed
- Use specific `file_patterns` instead of `*.*`

### Files Stuck as .processing

If encoding fails or daemon crashes:
1. Check job status: `python -m src.cli.client jobs -s failed`
2. Manually rename `.processing` back to original or delete
3. Restart daemon

---

## Best Practices

1. **Use separate directories** for watch folder and destination
2. **Set appropriate stability_scans** for your storage speed
3. **Use specific file patterns** instead of matching everything
4. **Set lower priority** for automated folders vs manual submissions
5. **Monitor the queue** to avoid overloading
6. **Use destination mode** for media watch folders

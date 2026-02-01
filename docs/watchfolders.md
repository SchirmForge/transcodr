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
preserve_structure: true
recursive: true
```

### Use Cases

- Remote job submission via file drop
- Integration with other tools/scripts
- Per-file encoding settings

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
| `watchfolder_location` | path | required | Directory to monitor |
| `watchfolder_type` | string | `command` | `command` or `media` |
| `scan_interval` | float | 5.0 | Seconds between scans |
| `stability_scans` | int | 2 | Consecutive stable size scans before processing |
| `file_patterns` | list | `["*.mkv", "*.mp4", ...]` | Glob patterns to match |
| `recursive` | bool | false | Monitor subdirectories |
| `profiles` | list | required | Encoding profiles to use |
| `output_mode` | string | `destination` | Must be `destination` for media watch |
| `destination` | path | required | Output directory |
| `backup` | bool | true | Create backup (N/A for destination mode) |
| `priority` | int | 5 | Job priority (1-10) |
| `hardware_accel` | string | null | Override hardware acceleration |

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

After editing watch folder configs:

```bash
python -m src.cli.client reload
```

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
output_mode: destination
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
output_mode: destination
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
output_mode: destination
destination: /media/encoded/
create_profile_folders: true
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

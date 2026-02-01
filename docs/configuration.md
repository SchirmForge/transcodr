# Configuration Guide

## Prerequisites

### Conda Environment

This project uses a conda environment named `videotranscode`. To activate it:

```bash
# Option 1: Source the activation script
source activate.sh

# Option 2: Manually activate
conda activate videotranscode
```

If the environment doesn't exist, create it:

```bash
conda create -n videotranscode python=3.12
conda activate videotranscode
pip install -r requirements.txt
```

## Overview

Video Transcode uses a configuration directory located at:
```
~/.config/videotranscode/
```

This directory contains:
- **config.yaml** - Global configuration settings
- **profiles/** - User-defined and customized encoding profiles
- **watchfolders/** - Watch folder configurations
- **jobs.db** - Job history database (created automatically)

## Initial Setup

### 1. Initialize Configuration

Run the initialization script to create the configuration directory and copy built-in profiles:

```bash
python src/cli/init.py
```

This will:
- Create `~/.config/videotranscode/` directory structure
- Generate a default `config.yaml` with commented settings
- Copy built-in profiles to the profiles directory

### 2. Verify Setup

Check that the configuration was created:

```bash
ls -la ~/.config/videotranscode/
# Should show:
# config.yaml
# profiles/
```

```bash
ls -la ~/.config/videotranscode/profiles/
# Should show built-in profiles:
# base-x265.yaml
# x265-balanced.yaml
# x265-fast.yaml
# x265-quality.yaml
```

## Configuration File

The main configuration file is `~/.config/videotranscode/config.yaml`.

### Default Configuration

```yaml
# Video Transcode Configuration

# FFmpeg settings
ffmpeg:
  binary_path: ffmpeg              # Path to FFmpeg binary
  hardware_accel: auto             # Hardware acceleration: auto|vaapi|nvenc|qsv|none

# Daemon settings
daemon:
  host: 127.0.0.1                  # API bind address (127.0.0.1 for local only)
  port: 8765                       # API port
  max_concurrent_jobs: 1           # Maximum concurrent encoding jobs
  pid_file: null                   # PID file path (null for none)

# Storage settings
storage:
  temp_dir: /tmp/videotranscode    # Temporary directory for encoding
  backup_originals: true           # Create backup of original files
  backup_dir: ./.originals         # Backup directory (relative or absolute)
  min_free_space_gb: 10            # Minimum free space required (GB)

# Logging settings
logging:
  level: INFO                      # Log level: DEBUG|INFO|WARNING|ERROR|CRITICAL
  dir: null                        # Log directory (null for no file logging)
  rotation: daily                  # Log rotation policy
  per_job_logs: true               # Create separate log file per job

# Hot folder monitoring (optional)
hot_folders: []
```

### Configuration Sections

#### FFmpeg Settings

- **binary_path**: Path to FFmpeg binary (default: `ffmpeg` in PATH)
- **hardware_accel**: Hardware acceleration mode
  - `auto` - Automatically detect and use available hardware acceleration
  - `vaapi` - Force VAAPI (AMD/Intel on Linux)
  - `nvenc` - Force NVIDIA NVENC
  - `qsv` - Force Intel Quick Sync Video
  - `none` - Disable hardware acceleration

#### Daemon Settings

- **host**: API bind address
  - `127.0.0.1` - Local only (recommended)
  - `0.0.0.0` - All interfaces (WARNING: security risk)
- **port**: API port (default: 8765)
- **max_concurrent_jobs**: Maximum number of concurrent encoding jobs
  - Use benchmark tool to find optimal value for your hardware
  - See [Concurrency Tuning Guide](concurrency-tuning.md)
- **pid_file**: PID file path (optional, useful for daemon management)

#### Storage Settings

- **temp_dir**: Temporary directory for encoding
  - Should be on fast storage (SSD preferred)
  - Requires ~2x source file size + 10GB free space
- **backup_originals**: Create backup of original files before replacing
  - Recommended: `true`
- **backup_dir**: Where to store backups
  - `./.originals` - Relative to source file (default)
  - `/path/to/backups` - Absolute path
- **min_free_space_gb**: Minimum free space required to start encoding

#### Logging Settings

- **level**: Log verbosity
  - `DEBUG` - Very detailed (for troubleshooting)
  - `INFO` - Normal (default)
  - `WARNING` - Only warnings and errors
  - `ERROR` - Only errors
  - `CRITICAL` - Only critical errors
- **dir**: Log file directory
  - `null` - No file logging (console only)
  - `/path/to/logs` - Save logs to directory
- **rotation**: Log rotation policy
  - `daily` - Rotate logs daily
  - `size:10MB` - Rotate at 10MB (future feature)
- **per_job_logs**: Create separate log file per encoding job

#### Hot Folder Monitoring (Legacy)

Hot folders defined in `config.yaml` are a legacy feature. For new setups, use **Watch Folders** (see below).

```yaml
hot_folders:
  - path: /media/downloads
    profile: x265-balanced
    min_age_seconds: 300
    recursive: true
```

## Watch Folders

Watch folders are configured in separate YAML files in `~/.config/videotranscode/watchfolders/`.

See [Watch Folders Guide](watchfolders.md) for detailed documentation.

### Command Watch Folder

Monitors for YAML command files:

```yaml
# ~/.config/videotranscode/watchfolders/commands.yaml
watchfolder_location: /tmp/encode-commands
watchfolder_type: command
scan_interval: 5
```

### Media Watch Folder

Monitors for video files directly:

```yaml
# ~/.config/videotranscode/watchfolders/downloads.yaml
watchfolder_location: /home/user/downloads
watchfolder_type: media
scan_interval: 10
stability_scans: 3
profiles:
  - x265-balanced
output_mode: destination
destination: /media/encoded/
```

## Encoding Request Parameters

When submitting encoding jobs via CLI or API, these parameters control behavior:

### Output Modes

| Mode | Description |
|------|-------------|
| `replace` | Replace original file in-place (with optional backup) |
| `destination` | Output to separate folder |

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | required | Source file or folder path |
| `profiles` | list | required | Encoding profile(s) to use |
| `output_mode` | string | `replace` | `replace` or `destination` |
| `destination` | string | - | Output folder (required for destination mode) |
| `recursive` | bool | `true` | Process subdirectories |
| `file_patterns` | list | `["*.mkv", "*.mp4", ...]` | File patterns to match |
| `preserve_structure` | bool | `true` | Recreate folder structure in destination |
| `create_profile_folders` | bool | `false` | Create subfolder per profile |
| `append_profile_name` | bool | `false` | Add profile name to filename |
| `delete_source` | bool | `false` | Delete source after successful encoding |
| `backup` | bool | `true` | Create backup (replace mode only) |
| `backup_dir` | string | `.originals` | Backup directory |
| `priority` | int | `5` | Job priority (1-10, 10=highest) |
| `hardware_accel` | string | `null` | Override hardware acceleration |

### Example Request

```yaml
mode: encode
profiles:
  - x265-balanced
  - x265-fast
source: /media/videos/
output_mode: destination
destination: /media/encoded/
preserve_structure: true
create_profile_folders: true
append_profile_name: false
recursive: true
file_patterns:
  - "*.mkv"
  - "*.mp4"
  - "*.m2ts"
priority: 5
```

### Output Organization Examples

**Basic destination mode:**
```
Input:  /source/movie.mkv
Output: /dest/movie.mkv
```

**With `preserve_structure: true`:**
```
Input:  /source/subdir/movie.mkv
Output: /dest/subdir/movie.mkv
```

**With `create_profile_folders: true`:**
```
Input:  /source/movie.mkv
Output: /dest/x265-balanced/movie.mkv
        /dest/x265-fast/movie.mkv
```

**With `append_profile_name: true`:**
```
Input:  /source/movie.mkv
Output: /dest/movie_x265-balanced.mkv
        /dest/movie_x265-fast.mkv
```

**All options combined:**
```
Input:  /source/subdir/movie.mkv
Output: /dest/subdir/x265-balanced/movie_x265-balanced.mkv
        /dest/subdir/x265-fast/movie_x265-fast.mkv
```

## Profiles

Profiles define encoding settings for different use cases.

### Built-in Profiles

Video Transcode includes these built-in profiles:

1. **base-x265.yaml** - Base template for x265 profiles
2. **x265-fast.yaml** - Fast encoding, larger file sizes
3. **x265-balanced.yaml** - Balanced speed/quality (recommended)
4. **x265-quality.yaml** - High quality, slower encoding

### Profile Location

Profiles are loaded from these locations (in order of priority):

1. **User profiles**: `~/.config/videotranscode/profiles/`
2. **Built-in profiles**: `src/profiles/builtin/` (in source repo)

User profiles override built-in profiles with the same name.

### Creating Custom Profiles

#### Option 1: Copy and Modify

Copy a built-in profile and customize it:

```bash
cd ~/.config/videotranscode/profiles/
cp x265-balanced.yaml my-custom-profile.yaml
nano my-custom-profile.yaml
```

#### Option 2: Extend Existing Profile

Create a new profile that extends a built-in profile:

```yaml
name: my-custom-profile
extends: x265-balanced    # Inherit from x265-balanced

# Override specific settings
description: "My custom encoding settings"

video:
  crf: 20                 # Override CRF (lower = better quality)

# All other settings inherited from x265-balanced
```

#### Option 3: Create from Scratch

Create a completely new profile:

```yaml
name: my-profile
description: "My custom profile"
container: mkv

video:
  codec: libx265
  crf: 23
  preset: medium

audio:
  copy_streams: true      # Copy audio without re-encoding

# Optional: Hardware acceleration variants
hardware_variants:
  vaapi:
    video:
      codec: hevc_vaapi
      hwaccel: vaapi
      extra_options:
        qp: "25"
```

### Profile Examples

See [Profile Examples](profile-examples.md) for more profile configurations.

### Benchmark and Save Optimal Concurrency

After benchmarking, save the optimal concurrency to a profile:

```bash
# Run benchmark
python tests/benchmark_concurrency.py x265-balanced 10 10

# If optimal concurrency is 4, save it:
python tests/save_benchmark_to_profile.py x265-balanced 4
```

This creates a user profile that overrides the `recommended_concurrency` setting.

## Directory Structure

```
~/.config/videotranscode/
├── config.yaml              # Main configuration
├── profiles/                # User profiles directory
│   ├── base-x265.yaml      # Copied from built-in
│   ├── x265-balanced.yaml  # Copied from built-in
│   ├── x265-fast.yaml      # Copied from built-in
│   ├── x265-quality.yaml   # Copied from built-in
│   └── my-custom.yaml      # User-created profile
└── jobs.db                  # Job history (created automatically)
```

## Configuration Management

### View Current Configuration

```bash
cat ~/.config/videotranscode/config.yaml
```

### Validate Configuration

```bash
python -c "
from src.config.manager import ConfigManager
config = ConfigManager.load_config()
issues = ConfigManager.validate_config(config)
if issues:
    print('Issues found:')
    for issue in issues:
        print(f'  - {issue}')
else:
    print('Configuration is valid')
"
```

### Reset to Default

To reset configuration to defaults:

```bash
# Backup existing config
cp ~/.config/videotranscode/config.yaml ~/.config/videotranscode/config.yaml.backup

# Recreate default config
python src/cli/init.py
```

### Update Built-in Profiles

To update built-in profiles to the latest version:

```bash
# This will overwrite user profiles with built-in versions
# Make sure to backup any custom changes first!
python -c "
from src.config.manager import ConfigManager
ConfigManager.copy_builtin_profiles(overwrite=True)
print('Built-in profiles updated')
"
```

## Environment Variables

You can override the configuration directory location:

```bash
# Use custom config directory
export VIDEOTRANSCODE_CONFIG_DIR=/path/to/custom/config

# Run with custom config
python src/cli/init.py
```

(Note: This feature is planned but not yet implemented)

## Troubleshooting

### Configuration file not found

If you see "Config file not found", run the initialization:

```bash
python src/cli/init.py
```

### Profiles not found

If profiles are not found, reinitialize to copy built-in profiles:

```bash
python src/cli/init.py
```

### Permission errors

If you get permission errors, check that you have write access to:

```bash
ls -ld ~/.config/videotranscode/
```

If the directory is owned by root or another user, fix permissions:

```bash
sudo chown -R $USER:$USER ~/.config/videotranscode/
```

## Best Practices

1. **Always backup before changes**: Copy your config before making changes
2. **Use version control**: Keep your custom profiles in git
3. **Test profiles**: Test new profiles on sample files before batch processing
4. **Document changes**: Add comments to your custom profiles
5. **Run benchmarks**: Use the benchmark tool to optimize concurrency settings

## See Also

- [Concurrency Tuning Guide](concurrency-tuning.md) - Optimize concurrent job settings
- [Architecture](architecture.md) - System architecture and components
- [Profile Schema](profile-schema.md) - Profile configuration reference

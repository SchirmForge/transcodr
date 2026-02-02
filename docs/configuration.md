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
  root_media: ~/Videos             # Base path for  placeholder (supports ~ and $USER)

# Logging settings
logging:
  level: INFO                      # Log level: DEBUG|INFO|WARNING|ERROR|CRITICAL
  dir: null                        # Log directory (null for no file logging)
  rotation: daily                  # Log rotation policy
  per_job_logs: true               # Create separate log file per job
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
- **root_media**: Base path for `` placeholder
  - Default: `~/Videos`
  - Supports tilde expansion (`~`)
  - Supports environment variables (`$USER`, `$HOME`)
  - Example: `/home/$USER/media` or `/mnt/nas/videos`
  - Can be used in config.yaml and command files:
    ```yaml
    storage:
      root_media: /mnt/nas/videos
      backup_dir: /backups    # Expands to /mnt/nas/videos/backups
    ```

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

## Watch Folders

Watch folders are configured in separate YAML files in `~/.config/videotranscode/watchfolders/`.

See [Watch Folders Guide](watchfolders.md) for detailed documentation.

## Profiles

Profiles define encoding settings for different use cases.

See [Profiles Guide](profiles.md) for detailed documentation.

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
- [Watch Folders Guide](watchfolders.md) - Watch folders reference
- [Profiles Guide](profiles.md) - Profile configuration reference
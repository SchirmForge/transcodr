# Configuration Guide

## Prerequisites

### Conda Environment

This project uses a conda environment named `transcodr`. To activate it:

```bash
# Option 1: Source the activation script
source activate.sh

# Option 2: Manually activate
conda activate transcodr
```

If the environment doesn't exist, create it:

```bash
conda create -n transcodr python=3.12
conda activate transcodr
pip install -r requirements.txt
```

## Overview

Transcodr uses a configuration directory located at:
```
~/.config/transcodr/
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
- Create `~/.config/transcodr/` directory structure
- Generate a default `config.yaml` with commented settings
- Copy built-in profiles to the profiles directory

### 2. Verify Setup

Check that the configuration was created:

```bash
ls -la ~/.config/transcodr/
# Should show:
# config.yaml
# profiles/
```

```bash
ls -la ~/.config/transcodr/profiles/
# Should show built-in profiles:
# base-x265.yaml
# x265-balanced.yaml
# x265-fast.yaml
# x265-quality.yaml
```

## Configuration File

The main configuration file is `~/.config/transcodr/config.yaml`.
The generated default file comes from `config/config.yaml` in the repository root.

### Default Configuration

```yaml
# Transcodr Configuration

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
  temp_dir: /tmp/transcodr         # Temporary directory for encoding
  backup_originals: true           # Create backup of original files
  backup_dir: ./.originals         # Backup directory (relative or absolute)
  min_free_space_gb: 10            # Minimum free space required (GB)
  root_media: /media               # Base path for $root_media placeholder (supports ~ and $USER)
  on_extension_mismatch: rename    # rename (use correct ext), reject (fail job), keep (keep source ext)

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
- **on_extension_mismatch**: What to do when source extension differs from profile container in replace mode
  - `rename` (default) - Use correct extension, delete original, complete with warning
  - `reject` - Fail the job with descriptive error
  - `keep` - Keep source extension (wrong container content), complete with warning
- **root_media**: Base path for `$root_media` placeholder
  - Default in generated config: `/media`
  - Supports tilde expansion (`~`)
  - Supports environment variables (`$USER`, `$HOME`)
  - Example: `/home/$USER/media` or `/mnt/nas/videos`
  - Can be used in config.yaml and command files:
    ```yaml
    storage:
      root_media: /mnt/nas/videos
      backup_dir: /backups    # Expands to /mnt/nas/videos/backups
    ```
- **profile_name_separator**: Separator used when `append_profile_name: true`
  - Default: `_`
  - Example: `movie_x265-fast.mkv` vs `movie-x265-fast.mkv`
- **enable_temp_copy**: Copy source file to temp before encoding (default: `false`)
  - Required for replace-mode multi-profile jobs (daemon enforces this at job creation)
  - Set to `true` if you run multi-profile replace-mode jobs; leave `false` for destination-mode or single-profile jobs

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

## Notifications

Transcodr can send notifications when jobs complete, batches finish, the queue becomes idle, or errors occur. Three channel types are supported.

### Enabling Notifications

```yaml
notifications:
  enabled: true            # Master switch

  on_job_complete: false   # Notify after every individual job
  on_batch_complete: true  # Notify when all jobs from one submission finish
  on_queue_empty: true     # Notify when the queue becomes idle
  on_error: true           # Notify on critical errors

  desktop:
    enabled: false         # Requires notify-send (libnotify)

  email:
    enabled: false
    smtp_server: smtp.gmail.com
    smtp_port: 587
    use_tls: true
    smtp_user: ""
    smtp_password: ""      # Or set TRANSCODR_SMTP_PASSWORD environment variable
    from_address: transcodr@example.com
    recipients: []

  apprise:
    enabled: false
    urls: []
    # Examples:
    # - ntfy://ntfy.sh/my-topic
    # - gotifys://gotify.server.com/apptoken
    # - pover://UserKey@AppToken
```

### Notification Channels

#### Desktop (`notifications.desktop`)

Sends desktop notifications via `notify-send` (part of the `libnotify` package). Works on any Linux desktop with a notification daemon.

- **enabled**: Enable desktop notifications (default: `false`)
- Install: `sudo apt install libnotify-bin` (Debian/Ubuntu) or equivalent

#### Email (`notifications.email`)

Sends email via SMTP using the Python standard library. No additional packages required.

- **enabled**: Enable email notifications (default: `false`)
- **smtp_server**: SMTP server hostname (default: `smtp.gmail.com`)
- **smtp_port**: SMTP port (default: `587`)
- **use_tls**: Use STARTTLS (default: `true`)
- **smtp_user**: SMTP username
- **smtp_password**: SMTP password — prefer `TRANSCODR_SMTP_PASSWORD` env var to avoid storing credentials in config
- **from_address**: Sender address
- **recipients**: List of recipient addresses

#### Apprise (`notifications.apprise`)

Sends notifications via the [Apprise](https://github.com/caronc/apprise) library, which supports 80+ services including ntfy, Gotify, Pushover, Telegram, Slack, and more.

- **enabled**: Enable Apprise notifications (default: `false`)
- **urls**: List of Apprise-format URLs for notification services

Requires the optional `apprise` package:
```bash
pip install apprise
```

Example URLs:
| Service | URL format |
|---------|-----------|
| ntfy | `ntfy://ntfy.sh/my-topic` |
| Gotify | `gotifys://gotify.server.com/apptoken` |
| Pushover | `pover://UserKey@AppToken` |
| Telegram | `tgram://BotToken/ChatID` |

### Event Types

| Event | Config key | Description |
|-------|-----------|-------------|
| Job complete | `on_job_complete` | Fires after each individual job (can be noisy) |
| Batch complete | `on_batch_complete` | Fires after all jobs from one submission finish |
| Queue empty | `on_queue_empty` | Fires once when the queue drains completely |
| Error | `on_error` | Fires on critical daemon errors |

---

## Watch Folders

Watch folders are configured in separate YAML files in `~/.config/transcodr/watchfolders/`.

See [Watch Folders Guide](watchfolders.md) for detailed documentation.

## Profiles

Profiles define encoding settings for different use cases.

See [Profiles Guide](profiles.md) for detailed documentation.

## Directory Structure

```
~/.config/transcodr/
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
cat ~/.config/transcodr/config.yaml
```

### Validate Configuration

```bash
python -c "
from src.config.manager import ConfigManager
config = ConfigManager.load_config()
errors, warnings = ConfigManager.validate_config(config)
if errors:
    print('Errors found:')
    for error in errors:
        print(f'  - {error}')
if warnings:
    print('Warnings:')
    for warning in warnings:
        print(f'  - {warning}')
if not errors and not warnings:
    print('Configuration is valid')
"
```

### Reset to Default

To reset configuration to defaults:

```bash
# Backup existing config
cp ~/.config/transcodr/config.yaml ~/.config/transcodr/config.yaml.backup

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

### TRANSCODR_CONFIG_DIR

Override the default configuration directory (`~/.config/transcodr`) by setting the `TRANSCODR_CONFIG_DIR` environment variable. When set, all config paths — `config.yaml`, `profiles/`, `watchfolders/`, and `jobs.db` — derive from this directory.

```bash
# Use custom config directory
export TRANSCODR_CONFIG_DIR=/path/to/custom/config

# Run daemon with custom config location
python -m src.daemon

# Or set inline
TRANSCODR_CONFIG_DIR=/opt/transcodr/config python -m src.daemon
```

This is essential for Docker deployments where config is typically mounted at `/config`:

```yaml
# docker-compose.yml
environment:
  - TRANSCODR_CONFIG_DIR=/config
volumes:
  - ./config:/config
```

When `TRANSCODR_CONFIG_DIR` is not set, the default `~/.config/transcodr` is used. The CLI `--config` flag still takes precedence for the config file path when specified.
Since `v0.3.6`, profile and watchfolder loading also follows this directory consistently.

## Settings Web UI

All configuration sections can be edited directly from the Web UI under **Settings**:

- **General** — reload configuration/watchfolders without daemon restart
- **Storage** — root media, temp directory, backup options, free space, extension mismatch policy, profile name separator, enable temp copy
- **Encoding** — FFmpeg binary path, hardware acceleration selector, duration tolerance, detected hardware display
- **Daemon** — host, port, max concurrent jobs (changes require daemon restart)
- **Logging** — log level, log directory, rotation policy, per-job logs toggle

Each page has Save/Cancel buttons with dirty state tracking. Changes are validated, written to `config.yaml`, and reloaded live (except host/port changes which require a restart).

You can also read and update configuration programmatically via the Settings API endpoints (`GET /api/config` and `PUT /api/config`). See [API Reference](api-reference.md#configuration-endpoints) for details.

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
ls -ld ~/.config/transcodr/
```

If the directory is owned by root or another user, fix permissions:

```bash
sudo chown -R $USER:$USER ~/.config/transcodr/
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

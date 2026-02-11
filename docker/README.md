# Transcodr Docker

Run Transcodr in a Docker container.

## Quick Start

```bash
cd docker

# Create config directory and edit config
mkdir -p config
# Copy and edit config.yaml as needed (or let the daemon create defaults on first run)

# Update media path in docker-compose.yml
# Change /path/to/media to your actual media directory

# Build and start
docker compose up -d
```

The Web UI is available at http://localhost:8765

## Volume Mounts

| Mount | Container Path | Description |
|-------|---------------|-------------|
| Config | `/config` | Configuration files, profiles, watchfolders, jobs.db |
| Media | `/media` | Root media directory (set as `root_media` in config.yaml) |
| Temp | `/temp` | Temporary encoding directory (set as `temp_dir` in config.yaml) |

## Configuration

On first start, the daemon creates default configuration files in `/config`:

```
/config/
  config.yaml          # Main configuration
  profiles/            # Encoding profiles
  watchfolders/        # Watchfolder definitions
  jobs.db              # Job database
```

Edit `config/config.yaml` to set your paths:

```yaml
storage:
  root_media: /media       # Matches the /media volume mount
  temp_dir: /temp          # Matches the /temp volume mount
```

## GPU Passthrough

### AMD / Intel (VAAPI)

Uncomment the devices section in `docker-compose.yml`:

```yaml
devices:
  - /dev/dri:/dev/dri
```

### NVIDIA (NVENC)

Install [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html), then uncomment the deploy section:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - capabilities: [gpu]
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCODR_CONFIG_DIR` | `/config` | Configuration directory path |

## Building

```bash
# Build from project root
docker compose -f docker/docker-compose.yml build

# Or from docker directory
cd docker && docker compose build
```

## Logs

```bash
docker compose logs -f transcodr
```

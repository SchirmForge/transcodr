# Profiles Guide

Profiles define encoding settings for different use cases.

## Built-in Profiles

Video Transcode includes these built-in profiles:

1. **base-x265.yaml** - Base template for x265 profiles
2. **x265-fast.yaml** - Fast encoding, larger file sizes
3. **x265-balanced.yaml** - Balanced speed/quality (recommended)
4. **x265-quality.yaml** - High quality, slower encoding

## Profile Location

Profiles are loaded from these locations (in order of priority):

1. **User profiles**: `~/.config/videotranscode/profiles/`
2. **Built-in profiles**: `src/profiles/builtin/` (in source repo)

User profiles override built-in profiles with the same name.

## Creating Custom Profiles

### Option 1: Copy and Modify

Copy a built-in profile and customize it:

```bash
cd ~/.config/videotranscode/profiles/
cp x265-balanced.yaml my-custom-profile.yaml
nano my-custom-profile.yaml
```

### Option 2: Extend Existing Profile

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

### Option 3: Create from Scratch

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

---

## Profile Schema Reference

Profiles are defined in YAML with the following structure:

### Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique profile identifier |
| `description` | string | No | null | Human-readable description |
| `extends` | string | No | null | Parent profile to inherit from |
| `container` | string | No | `mkv` | Output format: `mkv`, `mp4`, `webm`, `avi` |
| `video` | object | Yes | - | Video encoding settings |
| `audio` | object | No | copy | Audio encoding settings |
| `subtitles` | object | No | copy | Subtitle handling settings |
| `hardware_variants` | object | No | null | Hardware-specific overrides |
| `recommended_concurrency` | int | No | null | Optimal concurrent jobs for this profile |
| `tags` | list | No | `[]` | Categorization tags |

### Video Settings (`video:`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `codec` | string | required | Video codec (e.g., `libx265`, `hevc_vaapi`) |
| `crf` | int | null | Constant Rate Factor (0-51, lower=better quality) |
| `bitrate` | string | null | Target bitrate (e.g., `5M`, `2000k`) |
| `preset` | string | null | Encoding preset (`ultrafast`, `fast`, `medium`, `slow`, `veryslow`) |
| `pix_fmt` | string | null | Pixel format (`yuv420p`, `yuv420p10le` for 10-bit) |
| `tune` | string | null | Tuning option (`film`, `animation`, `grain`) |
| `profile` | string | null | Codec profile (`main`, `main10`, `high`) |
| `level` | string | null | Codec level (`4.0`, `5.1`) |
| `max_bitrate` | string | null | Maximum bitrate for VBR |
| `bufsize` | string | null | Buffer size for rate control |
| `hwaccel` | string | null | Hardware acceleration method (`vaapi`, `cuda`, `qsv`) |
| `hwaccel_device` | string | null | Hardware device path (e.g., `/dev/dri/renderD128`) |
| `extra_options` | dict | `{}` | Additional FFmpeg options as key-value pairs |

> **Note:** `crf` and `bitrate` are mutually exclusive. Use one or the other.

#### Video Codec Examples

```yaml
# Software x265 (CPU)
video:
  codec: libx265
  crf: 23
  preset: medium
  pix_fmt: yuv420p10le

# VAAPI hardware encoding (AMD/Intel)
video:
  codec: hevc_vaapi
  hwaccel: vaapi
  hwaccel_device: /dev/dri/renderD128
  extra_options:
    qp: "25"
```

### Audio Settings (`audio:`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `copy_streams` | bool | `true` | Copy audio without re-encoding (alias: `copy`) |
| `codec` | string | null | Audio codec (`aac`, `opus`, `libmp3lame`) |
| `bitrate` | string | null | Audio bitrate (`192k`, `128k`) |
| `sample_rate` | int | null | Sample rate (`48000`, `44100`) |
| `channels` | int | null | Number of channels (`2` for stereo, `6` for 5.1) |
| `extra_options` | dict | `{}` | Additional FFmpeg audio options |

#### Audio Examples

```yaml
# Copy audio (default)
audio:
  copy: true

# Re-encode to AAC
audio:
  copy: false
  codec: aac
  bitrate: 192k
  channels: 2

# High-quality Opus
audio:
  copy: false
  codec: libopus
  bitrate: 256k
```

### Subtitle Settings (`subtitles:`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `copy_streams` | bool | `true` | Copy subtitle streams (alias: `copy`) |
| `codec` | string | null | Subtitle codec (`srt`, `ass`) |

#### Subtitle Examples

```yaml
# Copy subtitles (default)
subtitles:
  copy: true

# Convert to SRT
subtitles:
  copy: false
  codec: srt
```

---

## Hardware Variants

Hardware variants allow a single profile to work with different hardware acceleration backends. The appropriate variant is selected automatically based on available hardware.

### Defining Hardware Variants

```yaml
name: my-profile
video:
  codec: libx265
  crf: 23
  preset: medium

hardware_variants:
  vaapi:
    description: AMD/Intel VAAPI acceleration
    video:
      codec: hevc_vaapi
      hwaccel: vaapi
      hwaccel_device: /dev/dri/renderD128
      extra_options:
        qp: "25"

  nvenc:
    description: NVIDIA NVENC acceleration
    video:
      codec: hevc_nvenc
      hwaccel: cuda
      extra_options:
        cq: "25"
        preset: "p5"

  qsv:
    description: Intel Quick Sync Video
    video:
      codec: hevc_qsv
      hwaccel: qsv
      extra_options:
        global_quality: "25"
```

### Variant Selection

When encoding:
1. If `hardware_accel` is specified (in config or watchfolder), that variant is used
2. If `hardware_accel: auto`, the system detects available hardware
3. If no hardware variant matches, the base `video` settings are used (CPU encoding)

### Variant Structure

Each hardware variant contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video` | VideoSettings | Yes | Video settings override |
| `description` | string | No | Human-readable description |

> **Important:** The variant's `video` settings completely replace the base `video` settings - they are not merged.

### Hardware-Specific Parameters

Different hardware uses different quality parameters:

| Hardware | Quality Param | Range | Notes |
|----------|--------------|-------|-------|
| CPU (libx265) | `crf` | 0-51 | Lower = better |
| VAAPI | `qp` | 0-51 | Lower = better |
| NVENC | `cq` | 0-51 | Lower = better |
| QSV | `global_quality` | 1-51 | Lower = better |

---

## Profile Inheritance

Profiles can extend other profiles to inherit their settings. Only specified fields are overridden.

### Using extends

```yaml
# Child profile
name: x265-custom
extends: x265-balanced

description: "Custom profile based on balanced"

# Override only what you need
video:
  crf: 20  # Better quality than base (23)
```

### Inheritance Rules

1. Child profile inherits ALL settings from parent
2. Any field specified in child overrides the parent
3. Nested objects (video, audio, etc.) are completely replaced if specified
4. Multiple inheritance levels are supported (A extends B extends C)

### Example: Inheritance Chain

**base-x265.yaml:**
```yaml
name: base-x265
container: mkv
video:
  codec: libx265
  pix_fmt: yuv420p10le
audio:
  copy: true
subtitles:
  copy: true
```

**x265-balanced.yaml:**
```yaml
name: x265-balanced
extends: base-x265
description: "Balanced quality and speed"
video:
  codec: libx265
  crf: 23
  preset: medium
  pix_fmt: yuv420p10le
```

**my-archival.yaml:**
```yaml
name: my-archival
extends: x265-balanced
description: "High quality archival"
video:
  crf: 18  # Only override CRF
```

**Effective `my-archival` settings:**
- `container: mkv` (from base-x265)
- `video.codec: libx265` (from x265-balanced)
- `video.crf: 18` (from my-archival)
- `video.preset: medium` (from x265-balanced)
- `audio.copy: true` (from base-x265)
- `subtitles.copy: true` (from base-x265)

---

## Complete Profile Examples

### Software x265 Archival Profile

```yaml
name: x265-archival
description: "High quality archival encoding"
extends: base-x265
container: mkv

video:
  codec: libx265
  crf: 18
  preset: slow
  pix_fmt: yuv420p10le
  tune: film
  profile: main10
  level: "5.1"

audio:
  copy: false
  codec: aac
  bitrate: 256k
  channels: 2

subtitles:
  copy: true

hardware_variants:
  vaapi:
    description: VAAPI hardware encoding
    video:
      codec: hevc_vaapi
      hwaccel: vaapi
      hwaccel_device: /dev/dri/renderD128
      extra_options:
        qp: "20"
        compression_level: "6"

recommended_concurrency: 2

tags:
  - archival
  - high-quality
  - slow
```

### Quick Preview Profile

```yaml
name: preview
description: "Fast preview encoding for checking content"
container: mp4

video:
  codec: libx264
  crf: 28
  preset: ultrafast

audio:
  copy: true

subtitles:
  copy: false

recommended_concurrency: 4

tags:
  - fast
  - preview
  - testing
```

### Multi-Hardware Universal Profile

```yaml
name: universal-hevc
description: "HEVC encoding with all hardware acceleration options"
container: mkv

video:
  codec: libx265
  crf: 23
  preset: medium
  pix_fmt: yuv420p10le

audio:
  copy: true

subtitles:
  copy: true

hardware_variants:
  vaapi:
    description: AMD/Intel VAAPI
    video:
      codec: hevc_vaapi
      hwaccel: vaapi
      hwaccel_device: /dev/dri/renderD128
      extra_options:
        qp: "25"
        compression_level: "4"

  nvenc:
    description: NVIDIA NVENC
    video:
      codec: hevc_nvenc
      hwaccel: cuda
      extra_options:
        cq: "25"
        preset: "p5"
        rc: "vbr"

  qsv:
    description: Intel Quick Sync
    video:
      codec: hevc_qsv
      hwaccel: qsv
      extra_options:
        global_quality: "25"

tags:
  - hevc
  - universal
  - hardware
```

---

## Built-in Profiles

Video Transcode includes these built-in profiles:

| Profile | CRF | Preset | Use Case |
|---------|-----|--------|----------|
| `base-x265` | - | - | Base template (not for direct use) |
| `x265-fast` | 25 | fast | Quick conversions, testing |
| `x265-balanced` | 23 | medium | Most use cases (recommended) |
| `x265-quality` | 20 | slow | Archival, important content |

All built-in profiles:
- Use x265/HEVC codec
- Include VAAPI hardware variants
- Use 10-bit color depth (`yuv420p10le`)
- Copy audio and subtitle streams without re-encoding

## Benchmark and Save Optimal Concurrency

After benchmarking, save the optimal concurrency to a profile:

```bash
# Run benchmark
python tests/benchmark_concurrency.py x265-balanced 10 10

# If optimal concurrency is 4, save it:
python tests/save_benchmark_to_profile.py x265-balanced 4
```

This creates a user profile that overrides the `recommended_concurrency` setting.


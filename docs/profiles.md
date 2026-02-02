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

## Profile Examples

See [Profile Examples](profile-examples.md) for more profile configurations.

## Benchmark and Save Optimal Concurrency

After benchmarking, save the optimal concurrency to a profile:

```bash
# Run benchmark
python tests/benchmark_concurrency.py x265-balanced 10 10

# If optimal concurrency is 4, save it:
python tests/save_benchmark_to_profile.py x265-balanced 4
```

This creates a user profile that overrides the `recommended_concurrency` setting.


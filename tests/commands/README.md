# Test Command Files

This folder contains YAML command files for testing various encoding scenarios.

## Directory Structure

```
tests/commands/
├── README.md           # This file
├── replace/            # Replace mode tests (in-place encoding)
├── destination/        # Destination mode tests (output to folder)
├── watchfolders/       # Watchfolder configuration tests
└── multiprofile/       # Multi-profile encoding tests
```

## media Structure

```
$root_media/            # Should be set in the daemon configuration
├── original/           # Original source video files (DO NOT MODIFY)
├── replace/            # Copy files here before running replace tests
├── encoded/            # Target directory for destination mode
└── watchfolders/       # Watchfolder directories for testing
```

## Naming Convention

Command files use abbreviated codes to describe their configuration.
Format: `<type>_<options>.yaml`

### Type Prefixes

| Code | Description |
|------|-------------|
| `enc` | One-time encoding command |
| `wf`  | Watchfolder registration |

### Option Codes

| Code | Description | Values |
|------|-------------|--------|
| `rep` | Replace mode | (default) |
| `dst` | Destination mode | |
| `bak` | Backup enabled | `bak1` = yes, `bak0` = no |
| `rec` | Recursive | `rec1` = yes, `rec0` = no |
| `prs` | Preserve structure | `prs1` = yes, `prs0` = no |
| `pf`  | Profile folders | `pf1` = create, `pf0` = no |
| `apn` | Append profile name | `apn1` = yes, `apn0` = no |
| `del` | Delete source | `del1` = yes, `del0` = no |
| `np`  | Number of profiles | `np1`, `np2`, `np3` |
| `hw`  | Hardware accel | `hwv` = vaapi, `hwn` = nvenc, `hw0` = none |
| `pri` | Priority | `pri1` to `pri10` |
| `stb` | Stability scans | `stb2`, `stb3`, etc. |
| `int` | Scan interval | `int5`, `int10`, etc. (seconds) |

### Examples

| Filename | Description |
|----------|-------------|
| `enc_rep_bak1_np1.yaml` | Replace mode, backup on, single profile |
| `enc_dst_prs1_pf1_np2.yaml` | Destination, preserve structure, profile folders, 2 profiles |
| `enc_dst_apn1_del1_np3.yaml` | Destination, append profile name, delete source, 3 profiles |
| `wf_dst_stb3_int10_np1.yaml` | Watchfolder, destination, 3 stability scans, 10s interval |

## Test Profiles

The following profiles are used in tests (from built-in profiles):

- `x265-balanced` - Default H.265 profile
- `x265-fast` - Fast H.265 encoding
- `x264-compatible` - H.264 for compatibility

## Running Tests

1. Copy test files from `$root_media/original/` to appropriate location:
   - For replace tests: `$root_media/replace/`
   - For destination tests: source stays in `$root_media/original/`

2. Drop command file into watchfolder or submit via API:
   ```bash
   # Via CLI
   python -m src.cli.client encode tests/commands/replace/enc_rep_bak1_np1.yaml

   # Via API
   curl -X POST http://localhost:8765/jobs \
     -H "Content-Type: application/json" \
     -d @tests/commands/replace/enc_rep_bak1_np1.yaml
   ```

3. Check results in appropriate output directory.

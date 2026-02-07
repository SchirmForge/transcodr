# Concurrency Tuning Guide

## Overview

The optimal number of concurrent encoding jobs depends on:
- **Hardware acceleration type** (CPU, VAAPI, NVENC, etc.)
- **Profile settings** (quality, preset, codec)
- **System resources** (CPU cores, GPU capabilities, RAM, disk I/O)

This guide helps you find the optimal concurrency for your hardware.

---

## Quick Start

### 1. Run the Benchmark

```bash
python tests/benchmark_concurrency.py x265-balanced 6 10
```

**Arguments:**
- `x265-balanced` - Profile to benchmark
- `6` - Maximum concurrency to test (will test 1, 2, 3, 4, 5, 6)
- `10` - Test video duration in seconds (longer = more accurate, but slower)

**What it does:**
1. Creates test video files
2. Runs encoding with 1, 2, 3, ... N concurrent jobs
3. Measures throughput (frames per second) at each level
4. Identifies optimal concurrency
5. Shows efficiency comparison

### 2. Example Output

```
============================================================
BENCHMARK RESULTS
============================================================

Concurrency  Duration     Throughput      Avg FPS      Efficiency
--------------------------------------------------------------------------------
1            45.2s        66.4 fps        66.4 fps     100%
2            25.1s        119.5 fps       59.8 fps     180%
3            20.3s        147.8 fps       49.3 fps     223%
4            18.9s        158.7 fps       39.7 fps     239%  ← Optimal!
5            19.2s        156.2 fps       31.2 fps     235%
6            20.1s        149.3 fps       24.9 fps     225%

============================================================
OPTIMAL CONCURRENCY: 4 concurrent jobs
  Throughput: 158.7 fps
  Efficiency: 239% vs single job
============================================================
```

**Interpretation:**
- **Concurrency 1**: Baseline (100% efficiency)
- **Concurrency 4**: Best throughput (239% efficiency means 2.39x faster than single job)
- **Concurrency 6**: Diminishing returns (system bottleneck reached)

---

## Understanding the Results

### Key Metrics

1. **Throughput (FPS)**: Total frames encoded per second across all jobs
   - Higher is better
   - This is what you want to maximize

2. **Efficiency (%)**: Throughput compared to single job baseline
   - 100% = same as single job
   - 200% = twice as fast (perfect scaling for 2 jobs)
   - 400% = four times as fast (perfect scaling for 4 jobs)

3. **Avg FPS**: Average FPS per individual job
   - Decreases as concurrency increases (expected)
   - Useful for understanding per-job impact

### Scaling Patterns

#### Perfect Scaling (Rare)
```
Concurrency: 1 → 2 → 3 → 4
Efficiency:  100% → 200% → 300% → 400%
```
Each additional job doubles throughput. Only possible with:
- Infinite resources
- No shared bottlenecks
- Hardware-accelerated encoding with dedicated encoders

#### Good Scaling (VAAPI/NVENC)
```
Concurrency: 1 → 2 → 3 → 4
Efficiency:  100% → 180% → 240% → 270%
```
Diminishing returns but still worthwhile. Common with:
- Hardware encoding (GPU has limits)
- Shared memory bandwidth
- I/O contention

#### Poor Scaling (CPU)
```
Concurrency: 1 → 2 → 3 → 4
Efficiency:  100% → 120% → 110% → 95%
```
No benefit or worse performance. Indicates:
- CPU-bound (all cores already used)
- RAM bottleneck
- Disk I/O bottleneck

---

## Configuration

### Global Concurrency (Default)

Edit `~/.config/transcodr/config.yaml`:

```yaml
daemon:
  max_concurrent_jobs: 4  # Set based on benchmark results
```

This applies to all profiles unless overridden.

### Per-Profile Concurrency (Recommended)

After benchmarking, save results to profile:

```bash
# Benchmark the profile
python tests/benchmark_concurrency.py x265-balanced 8 10

# Save optimal concurrency to profile
python tests/save_benchmark_to_profile.py x265-balanced 4
```

This creates a user profile at `~/.config/transcodr/profiles/x265-balanced.yaml`:

```yaml
name: x265-balanced
extends: x265-balanced  # Inherits from built-in
recommended_concurrency: 4  # Override this setting
```

---

## Benchmark Best Practices

### 1. Test Different Profiles

Different profiles have different optimal concurrency:

```bash
# Hardware-accelerated profiles typically scale better
python tests/benchmark_concurrency.py x265-balanced 8 10  # VAAPI

# CPU profiles may saturate quickly
python tests/benchmark_concurrency.py x265-quality 4 10   # Slower preset
```

### 2. Use Realistic Test Duration

- **Short tests (5-10s)**: Quick, but less accurate
- **Long tests (30-60s)**: More accurate, includes steady-state behavior
- **Recommendation**: Start with 10s, use 30s for final validation

### 3. Test Under Real Conditions

- Close other applications during benchmark
- Test with representative input files (resolution, codec, bitrate)
- Consider disk speed (SSD vs HDD affects results)

### 4. Account for Headroom

If benchmark shows optimal concurrency of 4, consider using 3:
- Leaves resources for other system tasks
- Prevents system from becoming unresponsive
- Allows for variability in encode complexity

---

## Hardware-Specific Guidance

### AMD GPU (VAAPI)

**Expected behavior:**
- Good scaling up to 3-6 concurrent jobs
- Limited by video engine throughput and memory bandwidth
- Optimal concurrency: 3-5 for most AMD GPUs

**Benchmark command:**
```bash
python tests/benchmark_concurrency.py x265-balanced 8 10
```

**Typical results:**
- 1 job: 100% efficiency
- 2 jobs: 170-190% efficiency
- 3 jobs: 220-250% efficiency
- 4 jobs: 240-270% efficiency (peak)
- 5+ jobs: Diminishing returns

### NVIDIA GPU (NVENC)

**Expected behavior:**
- Excellent scaling (NVENC is very efficient)
- Can often handle 4-8+ concurrent encodes
- Optimal concurrency: 4-8 depending on GPU model

**Benchmark command:**
```bash
python tests/benchmark_concurrency.py x265-balanced 10 10
```

### Intel GPU (QSV)

**Expected behavior:**
- Good scaling similar to VAAPI
- Optimal concurrency: 2-4 for typical Intel iGPUs

### CPU Only (libx265)

**Expected behavior:**
- Poor scaling (cores already maxed)
- Optimal concurrency: 1-2 (maybe 2 if hyperthreading helps)

**Why?** Software encoding (libx265) already uses all CPU cores per job.

---

## Troubleshooting

### "Benchmark shows concurrency 1 is optimal"

**Possible causes:**
1. CPU-bound (all cores used by single job)
2. Disk I/O bottleneck (slow storage)
3. Insufficient RAM (swapping)
4. Hardware encoding not actually being used

**Solutions:**
- Verify hardware encoding: Check logs for `-hwaccel vaapi -c:v hevc_vaapi`
- Use faster storage for temp files
- Add more RAM
- Accept that 1 concurrent job is optimal for CPU encoding

### "Jobs fail with high concurrency"

**Possible causes:**
1. Out of memory (RAM)
2. Out of VRAM (GPU memory)
3. System becomes unstable

**Solutions:**
- Reduce concurrency
- Close other applications
- Upgrade hardware

### "Efficiency decreases after N jobs"

This is normal! It indicates you've found the bottleneck:
- **2-3 jobs**: Likely memory bandwidth or I/O
- **4-6 jobs**: Likely GPU video engine limit
- **8+ jobs**: Likely hitting hardware limits

**Action:** Use the concurrency level just before efficiency drops.

---

## Advanced: Automated Benchmarking

Run benchmarks for all profiles:

```bash
#!/bin/bash
# Benchmark all profiles

for profile in x265-balanced x265-quality x265-fast; do
    echo "Benchmarking $profile..."
    python tests/benchmark_concurrency.py $profile 8 10

    # Save results (adjust concurrency based on output)
    # python tests/save_benchmark_to_profile.py $profile 4
done
```

---

## Summary

1. **Run benchmark** for your most-used profile
2. **Identify optimal concurrency** (peak throughput)
3. **Save to profile** or global config
4. **Re-benchmark** after hardware changes or profile updates

**Example workflow:**
```bash
# Benchmark
python tests/benchmark_concurrency.py x265-balanced 8 10

# Results show optimal = 4
# Save to profile
python tests/save_benchmark_to_profile.py x265-balanced 4

# Or set globally in config.yaml
# daemon:
#   max_concurrent_jobs: 4
```

Happy encoding! 🎬

# Terminal Echo Issue - Fixed

## Problem

After running the benchmark script, the terminal stops displaying user input (echo is disabled), even though the input is still being processed by the shell. This makes the terminal appear broken.

**Symptoms:**
- After running `benchmark_concurrency.py`, commands typed in the terminal are invisible
- Commands still execute (input is processed), but nothing is shown
- Running `stty sane` manually restores the terminal

## Root Cause

FFmpeg can modify terminal settings when it detects it's running in an interactive terminal. Even when stdout/stderr are redirected, FFmpeg may still access `/dev/tty` directly to check if it's running interactively.

When FFmpeg runs in non-interactive mode (or is interrupted), it might disable terminal echo and not restore it, leaving the terminal in a corrupted state.

## Solution

### 1. Prevent FFmpeg from Accessing the Terminal

**File:** `src/core/ffmpeg.py`

Added `stdin=subprocess.DEVNULL` to the FFmpeg subprocess call:

```python
process = subprocess.Popen(
    cmd,
    stdin=subprocess.DEVNULL,  # ← Prevents FFmpeg from thinking it's interactive
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
```

This tells FFmpeg that it's not running in an interactive environment, preventing it from trying to control the terminal.

### 2. Save and Restore Terminal State

**File:** `tests/benchmark_concurrency.py`

Added terminal state management:

```python
def save_terminal_state():
    """Save current terminal state using stty -g."""
    global _terminal_state
    try:
        result = subprocess.run(
            ["stty", "-g"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            _terminal_state = result.stdout.strip()
    except Exception:
        pass

def restore_terminal_state():
    """Restore terminal state to saved state."""
    global _terminal_state
    if _terminal_state:
        try:
            subprocess.run(["stty", _terminal_state], timeout=1, check=False)
        except Exception:
            pass

# Register terminal restoration on exit
atexit.register(restore_terminal_state)
```

**In main():**
```python
def main():
    save_terminal_state()

    try:
        # ... entire benchmark logic ...
    finally:
        # Always restore terminal state, even on error/interrupt
        restore_terminal_state()
```

### 3. Apply to All FFmpeg Calls

Updated all direct FFmpeg subprocess calls in the benchmark script:
- `extract_clip_from_video()` - Clip extraction
- `create_test_files()` - Synthetic video generation

All now use `stdin=subprocess.DEVNULL`.

## How It Works

1. **On startup:** Save the current terminal state using `stty -g`
2. **During execution:** FFmpeg subprocess calls have no access to stdin (DEVNULL)
3. **On exit/error/interrupt:** Restore the saved terminal state via `finally` block and `atexit` handler

## Testing

To verify the fix works:

```bash
# Run benchmark and then interrupt it with Ctrl+C
python tests/benchmark_concurrency.py x265-balanced 10 10 --source video.mkv

# Press Ctrl+C during execution

# Terminal should still be functional
ls
echo "test"
```

If you still experience terminal echo issues, manually restore with:
```bash
stty sane
```

## Why This Happens

FFmpeg is designed to be user-friendly when run interactively. It:
- Detects if it's running in a terminal
- Disables echo for progress display (to overwrite progress lines)
- Shows interactive prompts for file overwrites
- Uses ANSI escape codes for formatting

When FFmpeg is interrupted or exits abnormally without restoring terminal settings, the terminal remains in "no echo" mode.

## Related Issues

This is a common issue with tools that manipulate terminal settings:
- FFmpeg (video processing)
- vim/nano (text editors)
- less/more (pagers)
- interactive debuggers

All of these can leave the terminal in a corrupted state if interrupted.

## Prevention

Always use `stdin=subprocess.DEVNULL` or `stdin=subprocess.PIPE` when calling FFmpeg from scripts to prevent terminal interaction.

```python
# Good - No terminal access
subprocess.run(["ffmpeg", ...], stdin=subprocess.DEVNULL, ...)

# Bad - Can access terminal
subprocess.run(["ffmpeg", ...], ...)
```

#!/usr/bin/env python3
"""Transcodr Daemon entry point."""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uvicorn

from src.config.manager import ConfigManager, expand_path
from src.core.logging import setup_logging


def main():
    """Run the video transcode daemon."""
    parser = argparse.ArgumentParser(
        description="Transcodr Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start daemon with default settings
  python -m src.daemon

  # Start on custom port
  python -m src.daemon --port 9000

  # Start with debug logging
  python -m src.daemon --debug

  # Start with auto-reload (development)
  python -m src.daemon --reload
""",
    )

    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: from config or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from config or 8765)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development mode)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: ~/.config/transcodr/config.yaml)",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level, console=True)
    logger = logging.getLogger(__name__)

    # Ensure configuration is initialized
    if not ConfigManager.DEFAULT_CONFIG_PATH.exists():
        logger.info("Configuration not found, initializing...")
        ConfigManager.initialize()

    # Load configuration with error handling
    config_path = args.config or ConfigManager.DEFAULT_CONFIG_PATH
    try:
        config = ConfigManager.load_config(args.config)
    except ValueError as e:
        print()
        print("=" * 70)
        print("CONFIGURATION ERROR")
        print("=" * 70)
        print()
        print(f"  Config file: {config_path}")
        print()
        print(f"  Error: {e}")
        print()
        print("Please fix the configuration file and try again.")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 70)
        print("CONFIGURATION ERROR")
        print("=" * 70)
        print()
        print(f"  Config file: {config_path}")
        print()
        print(f"  Unexpected error: {type(e).__name__}: {e}")
        print()
        print("Please fix the configuration file and try again.")
        print("=" * 70)
        sys.exit(1)

    # Determine host and port
    host = args.host or config.daemon.host
    port = args.port or config.daemon.port

    # Expand paths for display
    root_media_expanded = expand_path(config.storage.root_media)
    temp_dir_expanded = expand_path(config.storage.temp_dir)

    print("=" * 70)
    print("TRANSCODR DAEMON")
    print("=" * 70)
    print()
    print("SERVER:")
    print(f"  Host:              {host}")
    print(f"  Port:              {port}")
    print(f"  Workers:           {args.workers}")
    print(f"  Debug:             {args.debug}")
    print()
    print("CONFIGURATION:")
    print(f"  Config file:       {ConfigManager.DEFAULT_CONFIG_PATH}")
    print(f"  Profiles dir:      {ConfigManager.get_profiles_dir()}")
    print(f"  Watchfolders dir:  {ConfigManager.get_watchfolders_config_dir()}")
    print()
    print("STORAGE:")
    print(f"  Root media:        {root_media_expanded}")
    print(f"  Temp directory:    {temp_dir_expanded}")
    print(f"  Backup directory:  {config.storage.backup_dir}")
    print(f"  Backup originals:  {config.storage.backup_originals}")
    print(f"  Min free space:    {config.storage.min_free_space_gb} GB")
    print()
    print("ENCODING:")
    print(f"  Max concurrent:    {config.daemon.max_concurrent_jobs}")
    print(f"  Hardware accel:    {config.ffmpeg.hardware_accel}")
    print()
    print("ENDPOINTS:")
    print(f"  Web UI:            http://{host}:{port}")
    print(f"  API Docs:          http://{host}:{port}/api/docs")
    print(f"  Health:            http://{host}:{port}/api/health")
    print(f"  Status:            http://{host}:{port}/api/status")
    print()
    print("=" * 70)
    print()

    # Validate configuration
    errors, warnings = ConfigManager.validate_config(config)

    # Show warnings
    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print()

    # Fail on errors
    if errors:
        print("=" * 70)
        print("CONFIGURATION ERRORS")
        print("=" * 70)
        print()
        for error in errors:
            print(f"  ✗ {error}")
        print()
        print("Please fix the configuration and try again.")
        print("=" * 70)
        sys.exit(1)

    # Run with uvicorn
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        workers=args.workers,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()

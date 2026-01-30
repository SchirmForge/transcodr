#!/usr/bin/env python3
"""Video Transcode Daemon entry point."""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uvicorn

from src.config.manager import ConfigManager
from src.core.logging import setup_logging


def main():
    """Run the video transcode daemon."""
    parser = argparse.ArgumentParser(
        description="Video Transcode Daemon",
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
        help="Path to config file (default: ~/.config/videotranscode/config.yaml)",
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

    # Load configuration
    config = ConfigManager.load_config(args.config)

    # Determine host and port
    host = args.host or config.daemon.host
    port = args.port or config.daemon.port

    print("=" * 70)
    print("VIDEO TRANSCODE DAEMON")
    print("=" * 70)
    print()
    print(f"  Host:    {host}")
    print(f"  Port:    {port}")
    print(f"  Workers: {args.workers}")
    print(f"  Debug:   {args.debug}")
    print(f"  Config:  {ConfigManager.DEFAULT_CONFIG_PATH}")
    print()
    print(f"  API Docs:    http://{host}:{port}/docs")
    print(f"  Health:      http://{host}:{port}/health")
    print(f"  Status:      http://{host}:{port}/status")
    print()
    print("=" * 70)
    print()

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

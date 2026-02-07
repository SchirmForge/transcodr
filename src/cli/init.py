#!/usr/bin/env python3
"""Initialize transcodr configuration."""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.manager import ConfigManager
from src.core.logging import setup_logging


def main():
    """Initialize configuration directory and files."""
    setup_logging(level="INFO", console=True)

    print("=" * 70)
    print("Video Transcode - Configuration Initialization")
    print("=" * 70)
    print()

    # Check if config already exists
    config_file = ConfigManager.DEFAULT_CONFIG_PATH
    profiles_dir = ConfigManager.get_profiles_dir()

    if config_file.exists():
        print(f"⚠ Configuration file already exists: {config_file}")
        print()
        response = input("Reinitialize configuration? [y/N]: ")
        if response.lower() != 'y':
            print("Initialization cancelled.")
            return

    # Initialize
    print("Initializing configuration...")
    print()

    result = ConfigManager.initialize(force_copy_profiles=False)

    # Print results
    print("✓ Configuration directory created:")
    print(f"  {result['config_dir']}")
    print()

    if result['config_created']:
        print("✓ Configuration file created:")
        print(f"  {result['config_file']}")
    else:
        print("→ Configuration file already exists:")
        print(f"  {result['config_file']}")
    print()

    print("✓ Profiles directory created:")
    print(f"  {result['profiles_dir']}")
    print()

    if result['profiles_copied']:
        print(f"✓ Copied {len(result['profiles_copied'])} built-in profiles:")
        for profile_path in result['profiles_copied']:
            print(f"  - {profile_path.name}")
    else:
        print("→ No profiles copied (already exist)")
    print()

    print("=" * 70)
    print("Initialization complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print(f"  1. Review configuration: {config_file}")
    print(f"  2. Customize profiles: {profiles_dir}")
    print("  3. Run benchmark to find optimal concurrency:")
    print("     python tests/benchmark_concurrency.py x265-balanced 10 10")
    print()


if __name__ == "__main__":
    main()

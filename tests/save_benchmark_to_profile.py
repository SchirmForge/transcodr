#!/usr/bin/env python3
"""
Save benchmark-determined optimal concurrency to a profile.

Usage:
    python tests/save_benchmark_to_profile.py x265-balanced 4
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.profiles.manager import ProfileManager


def main():
    """Save recommended concurrency to profile."""
    if len(sys.argv) < 3:
        print("Usage: python tests/save_benchmark_to_profile.py <profile_name> <recommended_concurrency>")
        print("\nExample:")
        print("  python tests/save_benchmark_to_profile.py x265-balanced 4")
        sys.exit(1)

    profile_name = sys.argv[1]
    recommended_concurrency = int(sys.argv[2])

    manager = ProfileManager()

    # Load profile
    try:
        profile = manager.load_profile(profile_name)
    except FileNotFoundError:
        print(f"✗ Profile '{profile_name}' not found")
        sys.exit(1)

    print(f"Profile: {profile_name}")
    print(f"Current recommended concurrency: {profile.recommended_concurrency or 'Not set (use global setting)'}")
    print(f"New recommended concurrency: {recommended_concurrency}")

    # Update profile
    profile.recommended_concurrency = recommended_concurrency

    # Save to user profile directory
    try:
        saved_path = manager.save_profile(profile, overwrite=True)
        print(f"\n✓ Saved to: {saved_path}")
        print(f"\nNote: This creates/updates a user profile that overrides the built-in profile.")
        print(f"To use the built-in profile again, delete: {saved_path}")
    except Exception as e:
        print(f"\n✗ Failed to save profile: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

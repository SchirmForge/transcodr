"""Shared profile manager store."""

from typing import Optional

from .manager import ProfileManager

_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get the shared ProfileManager instance."""
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager


def clear_profile_cache() -> None:
    """Clear the shared profile cache."""
    get_profile_manager().clear_cache()

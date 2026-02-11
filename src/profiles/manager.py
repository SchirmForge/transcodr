"""Profile management - loading, validation, and inheritance."""

import logging
from pathlib import Path
from typing import Optional
import yaml

from .schema import Profile, VideoSettings, AudioSettings

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Manages encoding profiles.

    Handles loading from YAML files, profile inheritance, and validation.
    """

    def __init__(self, user_profile_dir: Optional[Path] = None):
        """
        Initialize profile manager.

        Args:
            user_profile_dir: Directory for user profiles (default: ~/.config/transcodr/profiles)
        """
        self.builtin_profile_dir = Path(__file__).parent / "builtin"

        if user_profile_dir is None:
            user_profile_dir = Path.home() / ".config" / "transcodr" / "profiles"

        self.user_profile_dir = user_profile_dir
        self._cache: dict[str, Profile] = {}

    def clear_cache(self):
        """Clear the profile cache to force reload from disk."""
        count = len(self._cache)
        self._cache.clear()
        if count > 0:
            logger.info(f"Cleared {count} cached profiles")

    def list_profiles(self) -> list[str]:
        """
        List all available profile names.

        Returns:
            List of profile names (builtin + user)
        """
        profiles = set()

        # Built-in profiles
        if self.builtin_profile_dir.exists():
            for profile_file in self.builtin_profile_dir.glob("*.yaml"):
                profiles.add(profile_file.stem)

        # User profiles
        if self.user_profile_dir.exists():
            for profile_file in self.user_profile_dir.glob("*.yaml"):
                profiles.add(profile_file.stem)

        return sorted(list(profiles))

    def profile_exists(self, name: str) -> bool:
        """
        Check if profile exists.

        Args:
            name: Profile name

        Returns:
            True if profile exists
        """
        return name in self.list_profiles()

    def _find_profile_file(self, name: str) -> Optional[Path]:
        """
        Find profile file by name.

        User profiles take precedence over built-in profiles.

        Args:
            name: Profile name

        Returns:
            Path to profile file or None if not found
        """
        # Check user profiles first
        user_profile = self.user_profile_dir / f"{name}.yaml"
        if user_profile.exists():
            return user_profile

        # Check built-in profiles
        builtin_profile = self.builtin_profile_dir / f"{name}.yaml"
        if builtin_profile.exists():
            return builtin_profile

        return None

    def load_profile(self, name: str) -> Profile:
        """
        Load profile by name.

        Handles profile inheritance and caching.

        Args:
            name: Profile name

        Returns:
            Profile object

        Raises:
            FileNotFoundError: If profile not found
            ValueError: If profile is invalid
        """
        # Check cache first
        if name in self._cache:
            logger.debug(f"Loading profile '{name}' from cache")
            return self._cache[name]

        # Find profile file
        profile_file = self._find_profile_file(name)
        if not profile_file:
            raise FileNotFoundError(f"Profile '{name}' not found")

        # Load YAML
        try:
            with open(profile_file, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in profile '{name}': {e}")

        # Handle inheritance
        if "extends" in data and data["extends"]:
            parent_name = data["extends"]
            logger.debug(f"Profile '{name}' extends '{parent_name}'")

            # Load parent profile
            parent_profile = self.load_profile(parent_name)

            # Merge with parent (child overrides parent)
            merged_data = self._merge_profiles(parent_profile.model_dump(), data)
            data = merged_data

        # Validate and create Profile object
        try:
            profile = Profile(**data)
            self._cache[name] = profile
            logger.info(f"Loaded profile '{name}' from {profile_file}")
            return profile
        except Exception as e:
            raise ValueError(f"Invalid profile '{name}': {e}")

    def _merge_profiles(self, parent_data: dict, child_data: dict) -> dict:
        """
        Merge child profile data with parent.

        Child values override parent values.

        Args:
            parent_data: Parent profile data
            child_data: Child profile data

        Returns:
            Merged profile data
        """
        merged = parent_data.copy()

        for key, value in child_data.items():
            if key == "extends":
                # Don't inherit the 'extends' field
                continue
            elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                # Recursively merge nested dicts
                merged[key] = self._merge_profiles(merged[key], value)
            else:
                # Override parent value
                merged[key] = value

        return merged

    def save_profile(self, profile: Profile, overwrite: bool = False) -> Path:
        """
        Save profile to user profile directory.

        Args:
            profile: Profile to save
            overwrite: Allow overwriting existing profile

        Returns:
            Path to saved profile file

        Raises:
            FileExistsError: If profile exists and overwrite=False
        """
        self.user_profile_dir.mkdir(parents=True, exist_ok=True)

        profile_file = self.user_profile_dir / f"{profile.name}.yaml"

        if profile_file.exists() and not overwrite:
            raise FileExistsError(f"Profile '{profile.name}' already exists")

        # Convert to dict and save as YAML
        profile_dict = profile.model_dump(mode="python", exclude_none=True)

        with open(profile_file, "w") as f:
            yaml.dump(
                profile_dict,
                f,
                default_flow_style=False,
                sort_keys=False,
                indent=2,
            )

        logger.info(f"Saved profile '{profile.name}' to {profile_file}")
        return profile_file

    def validate_profile(self, name: str) -> list[str]:
        """
        Validate profile and return list of issues.

        Args:
            name: Profile name

        Returns:
            List of validation issues (empty if valid)
        """
        issues = []

        try:
            profile = self.load_profile(name)

            # Check if codec is reasonable
            if not profile.video.codec:
                issues.append("Video codec is required")

            # Check CRF/bitrate mutual exclusivity
            if profile.video.crf is not None and profile.video.bitrate:
                issues.append("Cannot specify both CRF and bitrate")

            # Check audio settings
            if not profile.audio.copy_streams and not profile.audio.codec:
                issues.append("Audio codec required when not copying")

        except FileNotFoundError as e:
            issues.append(str(e))
        except ValueError as e:
            issues.append(str(e))

        return issues

    def get_profile_info(self, name: str) -> dict:
        """
        Get profile information for display.

        Args:
            name: Profile name

        Returns:
            Dict with profile info
        """
        try:
            profile = self.load_profile(name)
            return {
                "name": profile.name,
                "description": profile.description or "No description",
                "codec": profile.video.codec,
                "container": profile.container,
                "crf": profile.video.crf,
                "preset": profile.video.preset,
                "hardware_variants": list(profile.hardware_variants.keys()) if profile.hardware_variants else [],
                "audio": "copy" if profile.audio.copy_streams else profile.audio.codec,
                "tags": profile.tags,
                "destination": profile.destination,
            }
        except Exception as e:
            return {"name": name, "error": str(e)}

    def clear_cache(self):
        """Clear profile cache."""
        self._cache.clear()
        logger.debug("Profile cache cleared")

"""Safe file replacement with validation and backup."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from .probe import ProbeHelper
from .errors import ReplacementError, ValidationError

logger = logging.getLogger(__name__)


class SafeReplacer:
    """
    Safely replace original file with encoded file.

    Provides atomic file replacement with validation and optional backup.
    """

    def __init__(
        self,
        backup_originals: bool = True,
        backup_dir: Optional[Path] = None,
        duration_tolerance_percent: float = 1.0,
    ):
        """
        Initialize safe replacer.

        Args:
            backup_originals: Create backup of original files
            backup_dir: Backup directory (None = .originals in same dir)
            duration_tolerance_percent: Allowed duration difference percentage
        """
        self.backup_originals = backup_originals
        self.backup_dir = backup_dir
        self.duration_tolerance_percent = duration_tolerance_percent
        self.probe = ProbeHelper()

    def replace(
        self,
        original: Path,
        encoded: Path,
    ) -> None:
        """
        Safely replace original with encoded file.

        Steps:
        1. Validate encoded file
        2. Compare durations (tolerance check)
        3. Create backup if enabled
        4. Atomic rename (encoded → original)
        5. Cleanup on error (restore backup)

        Args:
            original: Original file path
            encoded: Encoded file path (typically in temp location)

        Raises:
            ValidationError: If encoded file is invalid
            ReplacementError: If replacement fails
        """
        logger.info(f"Starting safe replacement: {original.name}")

        # 1. Validate encoded file
        if not self.probe.validate_file(encoded):
            raise ValidationError(f"Encoded file is corrupt: {encoded}")

        # 2. Compare durations
        if not self.probe.compare_durations(
            original,
            encoded,
            tolerance_percent=self.duration_tolerance_percent,
        ):
            orig_duration = self.probe.get_duration(original)
            enc_duration = self.probe.get_duration(encoded)
            diff_percent = abs(orig_duration - enc_duration) / orig_duration * 100

            raise ValidationError(
                f"Duration mismatch: original={orig_duration:.1f}s, "
                f"encoded={enc_duration:.1f}s (diff={diff_percent:.2f}%)"
            )

        logger.info("Encoded file validated successfully")

        # 3. Create backup
        backup_path = None
        if self.backup_originals:
            try:
                backup_path = self._create_backup(original)
                logger.info(f"Created backup: {backup_path}")
            except Exception as e:
                raise ReplacementError(f"Failed to create backup: {e}")

        # 4. Atomic rename
        try:
            # Use os.replace for atomic operation (POSIX)
            logger.info(f"Replacing {original.name} with encoded version")
            os.replace(str(encoded), str(original))
            logger.info("File replacement completed successfully")

        except Exception as e:
            # 5. Rollback on error
            logger.error(f"Replacement failed: {e}")

            if backup_path and backup_path.exists():
                try:
                    logger.warning("Rolling back: restoring original from backup")
                    os.replace(str(backup_path), str(original))
                    logger.info("Rollback completed")
                except Exception as rollback_error:
                    logger.critical(f"Rollback failed: {rollback_error}")
                    raise ReplacementError(
                        f"Replacement and rollback both failed. "
                        f"Original backup at: {backup_path}"
                    )

            raise ReplacementError(f"File replacement failed: {e}")

    def _create_backup(self, original: Path) -> Path:
        """
        Create backup of original file.

        Args:
            original: Original file path

        Returns:
            Path to backup file
        """
        if self.backup_dir:
            # Use specified backup directory
            backup_dir = self.backup_dir
        else:
            # Use .originals subdirectory next to original
            backup_dir = original.parent / ".originals"

        # Create backup directory
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup filename: original_name.backup.ext
        backup_path = backup_dir / f"{original.stem}.backup{original.suffix}"

        # Copy file (preserving metadata)
        shutil.copy2(original, backup_path)

        return backup_path

    def cleanup_backup(self, backup_path: Path):
        """
        Remove backup file.

        Args:
            backup_path: Path to backup file
        """
        try:
            if backup_path.exists():
                backup_path.unlink()
                logger.info(f"Removed backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to remove backup: {e}")

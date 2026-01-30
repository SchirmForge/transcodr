"""Safe file replacement with validation and backup."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .probe import ProbeHelper
from .errors import ReplacementError, ValidationError

logger = logging.getLogger(__name__)


class SafeReplacer:
    """
    Safely replace original file with encoded file.

    Provides:
    - Copy source to temp directory before encoding (preserves original for multi-profile)
    - Safe replacement: rename original -> copy new -> delete old (or backup)
    - Validation of encoded file
    - Optional backup of original files
    """

    def __init__(
        self,
        backup_originals: bool = True,
        backup_dir: Optional[Path] = None,
        temp_dir: Optional[Path] = None,
        duration_tolerance_percent: float = 1.0,
    ):
        """
        Initialize safe replacer.

        Args:
            backup_originals: Create backup of original files
            backup_dir: Backup directory (None = .originals in same dir)
            temp_dir: Temp directory for source copies and encoding (None = system temp)
            duration_tolerance_percent: Allowed duration difference percentage
        """
        self.backup_originals = backup_originals
        self.backup_dir = backup_dir
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "videotranscode"
        self.duration_tolerance_percent = duration_tolerance_percent
        self.probe = ProbeHelper()

        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def copy_source_to_temp(self, source: Path) -> Path:
        """
        Copy source file to temp directory.

        This preserves the original file for multi-profile encoding where
        multiple encodings need to be done from the same source.

        Args:
            source: Source file path

        Returns:
            Path to temp copy of source
        """
        temp_source = self.temp_dir / f"source_{source.name}"

        logger.info(f"Copying source to temp: {source.name}")
        shutil.copy2(source, temp_source)
        logger.info(f"Source copied to: {temp_source}")

        return temp_source

    def replace(
        self,
        original: Path,
        encoded: Path,
    ) -> None:
        """
        Safely replace original with encoded file.

        Process:
        1. Validate encoded file
        2. Compare durations (tolerance check)
        3. Rename original to .old (temporary)
        4. Copy encoded file to original location
        5. If backup enabled: move .old to backup location
        6. If backup disabled: delete .old
        7. Cleanup temp encoded file

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

        # 3. Rename original to temporary name during replacement
        old_path = original.with_suffix(original.suffix + ".replacing")
        try:
            logger.info(f"Temporarily renaming original to: {old_path.name}")
            original.rename(old_path)
        except Exception as e:
            raise ReplacementError(f"Failed to rename original: {e}")

        # 4. Copy encoded file to original location
        try:
            logger.info(f"Copying encoded file to: {original.name}")
            shutil.copy2(encoded, original)
            logger.info("Encoded file copied successfully")
        except Exception as e:
            # Rollback: restore original from .old
            logger.error(f"Copy failed: {e}")
            try:
                logger.warning("Rolling back: restoring original")
                old_path.rename(original)
                logger.info("Rollback completed")
            except Exception as rollback_error:
                logger.critical(f"Rollback failed: {rollback_error}")
                raise ReplacementError(
                    f"Replacement and rollback both failed. "
                    f"Original file at: {old_path}"
                )
            raise ReplacementError(f"Failed to copy encoded file: {e}")

        # 5. Handle .old file (backup or delete)
        try:
            if self.backup_originals:
                # Move .old to backup location
                backup_path = self._get_backup_path(original)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Moving original to backup: {backup_path}")
                shutil.move(str(old_path), str(backup_path))
                logger.info(f"Backup created: {backup_path}")
            else:
                # Delete .old
                logger.info("Deleting old file (backup disabled)")
                old_path.unlink()
        except Exception as e:
            # Non-fatal: replacement succeeded, just log the error
            logger.warning(f"Failed to handle old file: {e}")

        # 6. Cleanup temp encoded file
        try:
            if encoded.exists():
                encoded.unlink()
                logger.debug(f"Removed temp encoded file: {encoded}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")

        logger.info("File replacement completed successfully")

    def _get_backup_path(self, original: Path) -> Path:
        """
        Get backup path for original file.

        Args:
            original: Original file path

        Returns:
            Path for backup file
        """
        if self.backup_dir:
            # Use specified backup directory
            backup_dir = self.backup_dir
            return backup_dir / f"{original.name}.backup"
        else:
            # Keep backup in same directory with .backup suffix
            # e.g., video.mkv -> video.mkv.backup
            return original.with_suffix(original.suffix + ".backup")

    def cleanup_temp_source(self, temp_source: Path):
        """
        Remove temp source copy after all encodings are complete.

        Args:
            temp_source: Path to temp source file
        """
        try:
            if temp_source.exists():
                temp_source.unlink()
                logger.info(f"Removed temp source: {temp_source}")
        except Exception as e:
            logger.warning(f"Failed to remove temp source: {e}")

    def cleanup_backup(self, original: Path):
        """
        Remove backup file for a given original.

        Args:
            original: Original file path (backup path is derived)
        """
        backup_path = self._get_backup_path(original)
        try:
            if backup_path.exists():
                backup_path.unlink()
                logger.info(f"Removed backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to remove backup: {e}")

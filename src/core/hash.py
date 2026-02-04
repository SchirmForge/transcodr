"""Fast file fingerprinting for duplicate detection."""

import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024  # 1MB


def compute_file_fingerprint(file_path: Path) -> str:
    """
    Compute a fast fingerprint for a file.

    Uses first 1MB + last 1MB + file size to create a unique identifier
    that's fast to compute even for large files.

    Args:
        file_path: Path to file

    Returns:
        Hex string fingerprint (e.g., "a1b2c3d4e5f6...")
    """
    stat = file_path.stat()
    file_size = stat.st_size

    hasher = hashlib.md5()
    hasher.update(str(file_size).encode())

    with open(file_path, 'rb') as f:
        # Hash first chunk
        hasher.update(f.read(CHUNK_SIZE))

        # Hash last chunk (if file is large enough)
        if file_size > CHUNK_SIZE * 2:
            f.seek(-CHUNK_SIZE, 2)  # Seek to last 1MB
            hasher.update(f.read(CHUNK_SIZE))

    return hasher.hexdigest()

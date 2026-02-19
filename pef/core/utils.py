"""Utility functions for file and path operations."""

import os
import unicodedata
from functools import lru_cache
from typing import Optional


def normalize_filename(filename: str) -> str:
    """Normalize a filename to NFC form for consistent matching.

    macOS filesystems use NFD (decomposed) Unicode normalization, while
    Windows, Linux, and most cloud services use NFC (composed). This can
    cause matching failures when the same filename has different byte
    representations.

    Example:
        "Café.jpg" in NFC: C a f é . j p g  (é as single codepoint U+00E9)
        "Café.jpg" in NFD: C a f e ́ . j p g  (e + combining accent U+0301)

    These look identical but are different byte sequences. Normalizing
    to NFC ensures consistent dictionary lookups regardless of source.

    Args:
        filename: Original filename (may be NFC or NFD).

    Returns:
        NFC-normalized filename.
    """
    return unicodedata.normalize("NFC", filename)


def exists(path: Optional[str]) -> bool:
    """Check if a path exists.

    Args:
        path: Path to check, or None.

    Returns:
        True if path exists, False if path is None or doesn't exist.
    """
    if path:
        return os.path.exists(path)
    return False


def get_unique_path(path: str, is_dir: bool = False) -> str:
    """Get a unique path by appending (n) suffix if path exists.

    For files, uses os.open() with O_CREAT | O_EXCL to atomically reserve
    the path. This prevents race conditions when multiple threads call this
    function concurrently for the same destination — each thread is
    guaranteed a distinct path without needing external locking.

    The created placeholder file is empty and will be overwritten by the
    caller (e.g., shutil.copy).

    Args:
        path: Desired path.
        is_dir: True if path is a directory, False for files.

    Returns:
        Original path if doesn't exist, or path with (n) suffix.

    Examples:
        >>> get_unique_path("/path/photo.jpg")  # doesn't exist
        '/path/photo.jpg'
        >>> get_unique_path("/path/photo.jpg")  # exists
        '/path/photo(1).jpg'
    """
    if is_dir:
        if not os.path.isdir(path):
            return path
        n = 1
        while os.path.isdir(f"{path}({n})"):
            n += 1
        return f"{path}({n})"
    else:
        # Use O_CREAT | O_EXCL for atomic file reservation.
        # This fails with FileExistsError if the path already exists,
        # guaranteeing no two callers can claim the same path.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return path
        except FileExistsError:
            pass

        base, ext = os.path.splitext(path)
        n = 1
        while True:
            candidate = f"{base}({n}){ext}"
            try:
                fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return candidate
            except FileExistsError:
                n += 1


def checkout_dir(path: str, onlynew: bool = False) -> str:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path.
        onlynew: If True, always create a new directory with unique name.

    Returns:
        Path to the directory (may have (n) suffix if onlynew=True).

    Raises:
        ValueError: If path exists as a file (not a directory).
    """
    # Check if path exists as a file (not directory)
    if os.path.isfile(path):
        raise ValueError(f"Cannot create directory: {path} exists as a file")

    if not os.path.isdir(path) and not onlynew:
        os.makedirs(path)
    elif onlynew:
        path = get_unique_path(path, is_dir=True)
        os.makedirs(path)
    return path


@lru_cache(maxsize=10000)
def get_album_name(filepath: str) -> str:
    """Get the name of the parent folder (album name).

    Results are cached for performance when called repeatedly with same paths.

    Args:
        filepath: Full path to a file.

    Returns:
        Name of the parent directory.

    Example:
        >>> get_album_name("/photos/Vacation 2023/photo.jpg")
        'Vacation 2023'
    """
    return os.path.basename(os.path.dirname(filepath))


def normalize_path(path: str) -> str:
    """Normalize a path for consistent handling.

    Handles:
    - Trailing slashes
    - Mixed forward/backward slashes
    - User home directory (~)
    - Leading/trailing whitespace

    Args:
        path: Path to normalize.

    Returns:
        Normalized path.
    """
    return os.path.normpath(os.path.expanduser(path.strip()))

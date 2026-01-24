"""Utility functions for file and path operations."""

import os
from typing import Optional


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
        if not os.path.isfile(path):
            return path
        base, ext = os.path.splitext(path)
        n = 1
        while os.path.isfile(f"{base}({n}){ext}"):
            n += 1
        return f"{base}({n}){ext}"


def checkout_dir(path: str, onlynew: bool = False) -> str:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path.
        onlynew: If True, always create a new directory with unique name.

    Returns:
        Path to the directory (may have (n) suffix if onlynew=True).
    """
    if not os.path.isdir(path) and not onlynew:
        os.makedirs(path)
    elif onlynew:
        path = get_unique_path(path, is_dir=True)
        os.makedirs(path)
    return path


def get_album_name(filepath: str) -> str:
    """Get the name of the parent folder (album name).

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


def truncate_filename(name: str, ext: str, max_length: int = 51) -> str:
    """Truncate a filename to fit within max length (Google Takeout limit).

    Args:
        name: Filename without extension.
        ext: File extension (including dot).
        max_length: Maximum total length (default 51 for Google Takeout).

    Returns:
        Truncated name if needed.
    """
    if len(name + ext) > max_length:
        return name[0:max_length - len(ext)]
    return name

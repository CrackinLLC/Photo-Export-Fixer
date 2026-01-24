# Task 03: Extract Utility Functions

## Objective
Extract general-purpose utility functions from `pef.py` into a dedicated module. These are pure functions with no dependencies on other pef modules.

## Prerequisites
- Task 01 (Module Structure) complete

## Files to Create
- `pef/core/utils.py`

## Functions to Extract

From `pef.py`:

| Line | Function | Purpose |
|------|----------|---------|
| 95-98 | `exists(path)` | Check if path exists |
| 100-120 | `get_unique_path(path, is_dir)` | Get unique path with (n) suffix |
| 122-128 | `checkout_dir(path, onlynew)` | Ensure directory exists |
| 196-197 | `get_album_name(filepath)` | Get parent folder name |

## Implementation

### `pef/core/utils.py`

```python
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
```

## Update `pef/core/__init__.py`

```python
"""Core library for Photo Export Fixer."""

from pef.core.utils import (
    exists,
    get_unique_path,
    checkout_dir,
    get_album_name,
    normalize_path,
)

__all__ = [
    "exists",
    "get_unique_path",
    "checkout_dir",
    "get_album_name",
    "normalize_path",
]
```

## Acceptance Criteria

1. [ ] `pef/core/utils.py` exists with all functions
2. [ ] All functions have docstrings with Args/Returns
3. [ ] Can import: `from pef.core.utils import exists, get_unique_path`
4. [ ] Can import: `from pef.core import exists, checkout_dir`
5. [ ] Original `pef.py` still works unchanged

## Verification

```python
# Test in Python REPL
from pef.core.utils import exists, get_unique_path, checkout_dir, get_album_name, normalize_path

# Test exists
print(exists(None))  # False
print(exists("C:/Windows"))  # True (on Windows)
print(exists("/nonexistent"))  # False

# Test get_album_name
print(get_album_name("/photos/Vacation/photo.jpg"))  # "Vacation"

# Test normalize_path
print(normalize_path("  ~/Photos/test/  "))  # Expanded and cleaned
print(normalize_path("C:\\Users\\test/photos\\"))  # Normalized slashes
```

## Migration Plan

After this task, the utility functions exist in both places:
1. Original in `pef.py` (for backwards compatibility)
2. New in `pef/core/utils.py` (for new code)

In Task 10 (CLI Refactor), `pef.py` will be updated to import from `pef.core.utils` instead of defining locally.

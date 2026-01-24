# Task 05: Extract Scanner

## Objective
Extract file discovery logic into a `FileScanner` class with progress callback support. This enables both CLI (tqdm) and GUI (tkinter) to show scanning progress.

## Prerequisites
- Task 01 (Module Structure) complete
- Task 02 (Models) complete
- Task 03 (Utils) complete

## Files to Create
- `pef/core/scanner.py`

## Current State Analysis

Lines 130-155 in `pef.py`:
```python
def get_file_names(path):
    content = os.walk(path)
    files = []
    jsons = []

    for dir_cont in content:
        for file in dir_cont[2]:
            if file.endswith(".json"):
                jsons.append(os.path.join(dir_cont[0], file))
            else:
                files.append({
                    "filename":  file,
                    "filepath":  os.path.join(dir_cont[0], file),
                    "albumname": get_album_name(os.path.join(dir_cont[0], file))
                })

    # Build index for O(1) lookups
    file_index = {}
    for file in files:
        key = (file["albumname"], file["filename"])
        if key not in file_index:
            file_index[key] = []
        file_index[key].append(file)

    return jsons, files, file_index
```

### Problems
1. No progress feedback during scanning (can take minutes for 80k+ files)
2. Returns raw dicts instead of typed objects
3. No way to cancel mid-scan

## Implementation

### `pef/core/scanner.py`

```python
"""File and directory scanning for Photo Export Fixer."""

import os
from typing import List, Dict, Tuple, Optional, Callable

from pef.core.models import FileInfo, FileIndex, ProgressCallback
from pef.core.utils import get_album_name


class FileScanner:
    """Scans directories to find JSON metadata and media files.

    Usage:
        scanner = FileScanner("/path/to/takeout")
        scanner.scan(on_progress=lambda cur, tot, msg: print(f"{cur}/{tot}"))

        print(f"Found {scanner.json_count} JSONs, {scanner.file_count} files")

        # Access results
        for json_path in scanner.jsons:
            ...
        for file_info in scanner.files:
            ...
    """

    def __init__(self, path: str):
        """Initialize scanner.

        Args:
            path: Root directory to scan.
        """
        self.path = path
        self.jsons: List[str] = []
        self.files: List[FileInfo] = []
        self.file_index: FileIndex = {}
        self._scanned = False

    def scan(self, on_progress: Optional[ProgressCallback] = None) -> None:
        """Scan the directory tree for JSON and media files.

        Args:
            on_progress: Optional callback for progress updates.
                        Called with (current_count, estimated_total, message).

        Note:
            Since we don't know the total files until scan completes,
            estimated_total is updated as we discover directories.
        """
        self.jsons = []
        self.files = []
        self.file_index = {}

        # First pass: count directories for progress estimation
        dir_count = 0
        for _ in os.walk(self.path):
            dir_count += 1

        # Second pass: actual scanning with progress
        dirs_processed = 0

        for dirpath, dirnames, filenames in os.walk(self.path):
            dirs_processed += 1

            if on_progress:
                on_progress(dirs_processed, dir_count, f"Scanning: {os.path.basename(dirpath)}")

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)

                if filename.endswith(".json"):
                    self.jsons.append(filepath)
                else:
                    file_info = FileInfo(
                        filename=filename,
                        filepath=filepath,
                        albumname=get_album_name(filepath)
                    )
                    self.files.append(file_info)

        # Build index for O(1) lookups
        self._build_index()
        self._scanned = True

        if on_progress:
            on_progress(dir_count, dir_count, "Scan complete")

    def _build_index(self) -> None:
        """Build the file index for fast lookups."""
        self.file_index = {}
        for file_info in self.files:
            key = (file_info.albumname, file_info.filename)
            if key not in self.file_index:
                self.file_index[key] = []
            self.file_index[key].append(file_info)

    @property
    def json_count(self) -> int:
        """Number of JSON files found."""
        return len(self.jsons)

    @property
    def file_count(self) -> int:
        """Number of media files found."""
        return len(self.files)

    @property
    def is_scanned(self) -> bool:
        """Whether scan() has been called."""
        return self._scanned

    def get_stats(self) -> Dict[str, int]:
        """Get scanning statistics.

        Returns:
            Dict with json_count, file_count, album_count keys.
        """
        albums = set(f.albumname for f in self.files)
        return {
            "json_count": self.json_count,
            "file_count": self.file_count,
            "album_count": len(albums),
        }


def scan_directory(
    path: str,
    on_progress: Optional[ProgressCallback] = None
) -> Tuple[List[str], List[FileInfo], FileIndex]:
    """Convenience function to scan a directory.

    Args:
        path: Directory to scan.
        on_progress: Optional progress callback.

    Returns:
        Tuple of (json_paths, file_infos, file_index).

    This provides backwards compatibility with the original get_file_names() function.
    """
    scanner = FileScanner(path)
    scanner.scan(on_progress)
    return scanner.jsons, scanner.files, scanner.file_index


# Backwards-compatible function signature
def get_file_names(path: str) -> Tuple[List[str], List[Dict], Dict]:
    """Scan directory and return files (backwards compatible).

    This returns dicts instead of FileInfo objects for compatibility
    with existing code. New code should use FileScanner directly.

    Args:
        path: Directory to scan.

    Returns:
        Tuple of (json_paths, file_dicts, file_index_dicts).
    """
    scanner = FileScanner(path)
    scanner.scan()

    # Convert FileInfo to dict for backwards compatibility
    files_as_dicts = [
        {
            "filename": f.filename,
            "filepath": f.filepath,
            "albumname": f.albumname,
        }
        for f in scanner.files
    ]

    # Convert index to use dicts
    index_as_dicts = {}
    for key, file_list in scanner.file_index.items():
        index_as_dicts[key] = [
            {
                "filename": f.filename,
                "filepath": f.filepath,
                "albumname": f.albumname,
            }
            for f in file_list
        ]

    return scanner.jsons, files_as_dicts, index_as_dicts
```

## Progress Callback Examples

### CLI with tqdm:
```python
from tqdm import tqdm

pbar = None

def cli_progress(current, total, message):
    global pbar
    if pbar is None:
        pbar = tqdm(total=total, desc="Scanning")
    pbar.n = current
    pbar.set_description(message[:40])
    pbar.refresh()

scanner = FileScanner(path)
scanner.scan(on_progress=cli_progress)
pbar.close()
```

### GUI with tkinter:
```python
def gui_progress(current, total, message):
    progress_var.set(current / total * 100)
    status_label.config(text=message)
    root.update_idletasks()

scanner = FileScanner(path)
scanner.scan(on_progress=gui_progress)
```

## Acceptance Criteria

1. [ ] `pef/core/scanner.py` exists with `FileScanner` class
2. [ ] `FileScanner.scan()` accepts optional progress callback
3. [ ] Progress callback receives (current, total, message)
4. [ ] `FileScanner` returns `FileInfo` objects (not dicts)
5. [ ] `get_file_names()` backwards-compatible function exists
6. [ ] Original `pef.py` still works unchanged

## Verification

```python
import os
from pef.core.scanner import FileScanner, get_file_names

# Test FileScanner with progress
def progress(cur, tot, msg):
    print(f"[{cur}/{tot}] {msg}")

scanner = FileScanner("D:/Photos/_Google Photos Backup/Google Photos")
scanner.scan(on_progress=progress)
print(f"Found: {scanner.json_count} JSONs, {scanner.file_count} files")
print(f"Stats: {scanner.get_stats()}")

# Verify first file is FileInfo
if scanner.files:
    f = scanner.files[0]
    print(f"Type: {type(f)}, filename: {f.filename}")

# Test backwards-compatible function
jsons, files, index = get_file_names("D:/Photos/_Google Photos Backup/Google Photos")
print(f"Backwards compat: {len(jsons)} JSONs, {len(files)} files")
if files:
    print(f"File dict keys: {files[0].keys()}")
```

## Performance Notes

- The two-pass approach (count dirs, then scan) adds minimal overhead
- For very large directories, consider single-pass with indeterminate progress
- File index building is O(n) and happens after scanning

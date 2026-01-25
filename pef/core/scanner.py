"""File and directory scanning for Photo Export Fixer."""

import logging
import os
import warnings
from typing import List, Dict, Tuple, Optional, Iterator

from pef.core.models import FileInfo, FileIndex, ProgressCallback
from pef.core.utils import get_album_name

logger = logging.getLogger(__name__)


def _fast_walk(path: str) -> Iterator[Tuple[str, List[str], List[str]]]:
    """Fast directory walker using os.scandir (20-30% faster than os.walk).

    Uses os.scandir() which provides DirEntry objects with cached stat info,
    avoiding redundant syscalls.

    Args:
        path: Root directory to walk.

    Yields:
        Tuples of (dirpath, dirnames, filenames) like os.walk().
    """
    try:
        with os.scandir(path) as entries:
            dirs = []
            files = []
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(entry.name)
                    else:
                        files.append(entry.name)
                except OSError as e:
                    # Log and skip entries we can't access
                    logger.debug(f"Cannot access entry {entry.path}: {e}")
                    continue
            yield path, dirs, files
            for d in dirs:
                yield from _fast_walk(os.path.join(path, d))
    except OSError as e:
        # Log and skip directories we can't access
        logger.debug(f"Cannot access directory {path}: {e}")


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

        Uses single-pass scanning with os.scandir for best performance.

        Args:
            on_progress: Optional callback for progress updates.
                        Called with (current_count, estimated_total, message).

        Note:
            Progress shows files discovered rather than percentage complete,
            since total count isn't known until scan finishes.
        """
        self.jsons = []
        self.files = []
        self.file_index = {}

        # Single-pass scanning using fast_walk (no double traversal)
        files_found = 0
        # Start with moderate interval, but report at least every second or so
        # For small folders this gives immediate feedback
        progress_interval = 100
        last_dir = ""

        for dirpath, dirnames, filenames in _fast_walk(self.path):
            album_name = os.path.basename(dirpath)

            # Show directory change for immediate feedback
            if on_progress and dirpath != last_dir:
                last_dir = dirpath
                # Only show dir updates when we have some files found
                if files_found > 0:
                    on_progress(files_found, files_found, f"Scanning: {album_name}...")

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)

                if filename.endswith(".json"):
                    self.jsons.append(filepath)
                else:
                    file_info = FileInfo(
                        filename=filename,
                        filepath=filepath,
                        album_name=album_name
                    )
                    self.files.append(file_info)

                files_found += 1

                # Update progress periodically
                # Adaptive: more frequent updates for smaller collections
                if on_progress and files_found % progress_interval == 0:
                    on_progress(files_found, files_found, f"Found {files_found} files...")
                    # Increase interval as we find more files to reduce overhead
                    if files_found >= 1000 and progress_interval < 500:
                        progress_interval = 500

        # Build index for O(1) lookups
        self._build_index()
        self._scanned = True

        if on_progress:
            total = len(self.jsons) + len(self.files)
            on_progress(total, total, "Scan complete")

    def _build_index(self) -> None:
        """Build the file index for fast lookups."""
        self.file_index = {}
        for file_info in self.files:
            key = (file_info.album_name, file_info.filename)
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

    def iter_jsons(self) -> Iterator[str]:
        """Iterate over JSON paths without storing them all in memory.

        This is a generator-based alternative for memory-constrained environments.
        Note: Cannot be used with matching since file_index won't be available.

        Yields:
            JSON file paths as they are discovered.
        """
        for dirpath, dirnames, filenames in _fast_walk(self.path):
            for filename in filenames:
                if filename.endswith(".json"):
                    yield os.path.join(dirpath, filename)

    @property
    def is_scanned(self) -> bool:
        """Whether scan() has been called."""
        return self._scanned

    def get_stats(self) -> Dict[str, int]:
        """Get scanning statistics.

        Returns:
            Dict with json_count, file_count, album_count keys.
        """
        albums = set(f.album_name for f in self.files)
        return {
            "json_count": self.json_count,
            "file_count": self.file_count,
            "album_count": len(albums),
        }

    def lookup(self, album_name: str, filename: str) -> List[FileInfo]:
        """Look up files by album and filename.

        Args:
            album_name: Album (folder) name.
            filename: File name.

        Returns:
            List of matching FileInfo objects (may be empty).
        """
        return self.file_index.get((album_name, filename), [])


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


# Backwards-compatible function signature (deprecated)
def get_file_names(path: str) -> Tuple[List[str], List[Dict], Dict]:
    """Scan directory and return files (backwards compatible).

    .. deprecated::
        Use FileScanner class directly instead.

    Args:
        path: Directory to scan.

    Returns:
        Tuple of (json_paths, file_dicts, file_index_dicts).
    """
    warnings.warn(
        "get_file_names() is deprecated. Use FileScanner class directly instead.",
        DeprecationWarning,
        stacklevel=2
    )
    scanner = FileScanner(path)
    scanner.scan()

    # Convert FileInfo to dict for backwards compatibility
    files_as_dicts = [
        {
            "filename": f.filename,
            "filepath": f.filepath,
            "album_name": f.album_name,
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
                "album_name": f.album_name,
            }
            for f in file_list
        ]

    return scanner.jsons, files_as_dicts, index_as_dicts

"""File and directory scanning for Photo Export Fixer."""

import os
from typing import List, Dict, Tuple, Optional

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

    def lookup(self, albumname: str, filename: str) -> List[FileInfo]:
        """Look up files by album and filename.

        Args:
            albumname: Album (folder) name.
            filename: File name.

        Returns:
            List of matching FileInfo objects (may be empty).
        """
        return self.file_index.get((albumname, filename), [])


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

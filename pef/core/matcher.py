"""File matching logic for Photo Export Fixer.

This module handles the complex logic of matching JSON metadata files
to their corresponding media files, including:
- Google's 51-character filename truncation
- Duplicate file naming convention: photo(1).jpg
- Suffix variations: photo.jpg, photo-edited.jpg
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from pef.core.models import FileInfo, FileIndex
from pef.core.utils import get_album_name


# Default suffixes that Google may add to filenames
DEFAULT_SUFFIXES = ["", "-edited"]


@dataclass
class MatchResult:
    """Result of attempting to match a JSON to its media file(s)."""
    found: bool
    files: List[FileInfo]
    json_path: str
    title: str

    @property
    def is_matched(self) -> bool:
        """Alias for found."""
        return self.found


@dataclass
class ParsedTitle:
    """Parsed components of a file title from JSON metadata."""
    name: str           # Base filename without extension
    extension: str      # File extension including dot
    brackets: Optional[str]  # Duplicate suffix like "(1)" or None

    def build_filename(self, suffix: str = "") -> str:
        """Build a filename with optional suffix.

        Args:
            suffix: Suffix to insert (e.g., "-edited").

        Returns:
            Complete filename like "photo-edited(1).jpg".
        """
        if self.brackets:
            return f"{self.name}{suffix}{self.brackets}{self.extension}"
        return f"{self.name}{suffix}{self.extension}"


class FileMatcher:
    """Matches JSON metadata files to their corresponding media files.

    Usage:
        matcher = FileMatcher(file_index)
        result = matcher.find_match(json_path, title)
        if result.found:
            for file in result.files:
                process(file)
    """

    # Google truncates filenames at 51 characters total
    MAX_FILENAME_LENGTH = 51

    # Pattern for duplicate naming: photo(1).json, photo(2).json, etc.
    BRACKET_PATTERN = re.compile(r"\(([1-9][0-9]{0,2})\)\.json$")

    def __init__(
        self,
        file_index: FileIndex,
        suffixes: Optional[List[str]] = None
    ):
        """Initialize matcher.

        Args:
            file_index: Index from FileScanner, mapping (album, filename) to FileInfo list.
            suffixes: List of suffixes to try (default: ["", "-edited"]).
        """
        self.file_index = file_index
        self.suffixes = suffixes if suffixes is not None else DEFAULT_SUFFIXES

    def parse_title(self, title: str, json_path: str) -> ParsedTitle:
        """Parse a title into components, handling Google's quirks.

        Args:
            title: The "title" field from JSON metadata.
            json_path: Path to the JSON file (used for bracket detection).

        Returns:
            ParsedTitle with name, extension, and optional brackets.
        """
        name, ext = os.path.splitext(title)

        # Handle Google's 51-character truncation
        if len(name + ext) > self.MAX_FILENAME_LENGTH:
            name = name[:self.MAX_FILENAME_LENGTH - len(ext)]

        # Detect duplicate naming convention from JSON path
        # e.g., "photo.jpg(1).json" means the file is "photo(1).jpg"
        brackets = None
        if json_path.endswith(").json"):
            match = self.BRACKET_PATTERN.search(json_path)
            if match:
                brackets = f"({match.group(1)})"

        return ParsedTitle(name=name, extension=ext, brackets=brackets)

    def find_match(self, json_path: str, title: str) -> MatchResult:
        """Find media file(s) matching a JSON metadata file.

        Args:
            json_path: Path to the JSON metadata file.
            title: The "title" field from the JSON.

        Returns:
            MatchResult indicating whether match was found and the file(s).
        """
        parsed = self.parse_title(title, json_path)
        album_name = get_album_name(json_path)

        # Try each suffix variation
        for suffix in self.suffixes:
            filename = parsed.build_filename(suffix)
            key = (album_name, filename)

            if key in self.file_index:
                return MatchResult(
                    found=True,
                    files=self.file_index[key],
                    json_path=json_path,
                    title=title
                )

        # No match found
        return MatchResult(
            found=False,
            files=[],
            json_path=json_path,
            title=title
        )

    def find_match_in_index(
        self,
        json_path: str,
        title: str,
        file_index: FileIndex
    ) -> MatchResult:
        """Find match using a different file index (for extend mode).

        Args:
            json_path: Path to the JSON metadata file.
            title: The "title" field from the JSON.
            file_index: Alternative file index to search in.

        Returns:
            MatchResult indicating whether match was found.
        """
        parsed = self.parse_title(title, json_path)
        album_name = get_album_name(json_path)

        for suffix in self.suffixes:
            filename = parsed.build_filename(suffix)
            key = (album_name, filename)

            if key in file_index:
                return MatchResult(
                    found=True,
                    files=file_index[key],
                    json_path=json_path,
                    title=title
                )

        return MatchResult(
            found=False,
            files=[],
            json_path=json_path,
            title=title
        )


# Convenience function for backwards compatibility
def find_file(
    jsondata: dict,
    file_index: dict,
    suffixes: List[str]
) -> Tuple[bool, List[dict]]:
    """Find file matching JSON metadata (backwards compatible).

    Args:
        jsondata: Dict with "title" and "filepath" keys.
        file_index: Index mapping (album, filename) to file dicts.
        suffixes: List of suffixes to try.

    Returns:
        Tuple of (found: bool, files: list of dicts).

    Note:
        New code should use FileMatcher class directly.
    """
    matcher = FileMatcher(file_index, suffixes)
    result = matcher.find_match(jsondata["filepath"], jsondata["title"])

    if result.found:
        # Convert FileInfo back to dict for compatibility
        file_dicts = []
        for f in result.files:
            if isinstance(f, FileInfo):
                file_dicts.append({
                    "filename": f.filename,
                    "filepath": f.filepath,
                    "albumname": f.albumname,
                })
            else:
                file_dicts.append(f)  # Already a dict
        return True, file_dicts
    else:
        return False, [{"jsonpath": jsondata["filepath"], "title": jsondata["title"]}]

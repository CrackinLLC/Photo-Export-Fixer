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
from typing import List, Optional

from pef.core.models import FileInfo, FileIndex
from pef.core.utils import get_album_name, normalize_filename


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
    duplicate_suffix: Optional[str]  # Duplicate marker like "(1)" or None

    def build_filename(self, suffix: str = "") -> str:
        """Build a filename with optional suffix.

        Args:
            suffix: Suffix to insert (e.g., "-edited").

        Returns:
            Complete filename like "photo-edited(1).jpg".
        """
        if self.duplicate_suffix:
            return f"{self.name}{suffix}{self.duplicate_suffix}{self.extension}"
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

        Normalizes the title to NFC for consistent matching across platforms
        (macOS uses NFD, Windows/Linux use NFC).

        Args:
            title: The "title" field from JSON metadata.
            json_path: Path to the JSON file (used for bracket detection).

        Returns:
            ParsedTitle with name, extension, and optional brackets.
        """
        # Normalize title to NFC for consistent matching
        title = normalize_filename(title)
        name, ext = os.path.splitext(title)

        # Handle Google's 51-character truncation
        if len(name + ext) > self.MAX_FILENAME_LENGTH:
            name = name[:self.MAX_FILENAME_LENGTH - len(ext)]

        # Detect duplicate naming convention from JSON path
        # e.g., "photo.jpg(1).json" means the file is "photo(1).jpg"
        duplicate_suffix = None
        if json_path.endswith(").json"):
            match = self.BRACKET_PATTERN.search(json_path)
            if match:
                duplicate_suffix = f"({match.group(1)})"

        return ParsedTitle(name=name, extension=ext, duplicate_suffix=duplicate_suffix)

    def find_match(
        self,
        json_path: str,
        title: str,
        file_index: Optional[FileIndex] = None
    ) -> MatchResult:
        """Find media file(s) matching a JSON metadata file.

        Uses tiered matching:
        - Tier 1: Fast matching (exact, suffix, bracket from JSON path)
        - Tier 2: Extended matching (suffix + bracket combinations)

        Args:
            json_path: Path to the JSON metadata file.
            title: The "title" field from the JSON.
            file_index: Optional alternative index to search in.
                       If None, uses self.file_index.

        Returns:
            MatchResult indicating whether match was found and the file(s).
        """
        index = file_index if file_index is not None else self.file_index
        parsed = self.parse_title(title, json_path)
        # Normalize album name to match normalized keys in file index
        album_name = normalize_filename(get_album_name(json_path))

        # Tier 1: Fast matching (existing logic)
        result = self._tier1_match(parsed, album_name, index, json_path, title)
        if result.found:
            return result

        # Tier 2: Extended matching for suffix+bracket combinations
        return self._tier2_match(parsed, album_name, index, json_path, title)

    def _tier1_match(
        self,
        parsed: ParsedTitle,
        album_name: str,
        index: FileIndex,
        json_path: str,
        title: str
    ) -> MatchResult:
        """Tier 1: Fast matching with direct suffix application.

        Tries each configured suffix with the parsed duplicate marker (if any).
        """
        # Try each suffix variation
        for suffix in self.suffixes:
            filename = parsed.build_filename(suffix)
            key = (album_name, filename)

            if key in index:
                return MatchResult(
                    found=True,
                    files=index[key],
                    json_path=json_path,
                    title=title
                )

        return MatchResult(found=False, files=[], json_path=json_path, title=title)

    def _tier2_match(
        self,
        parsed: ParsedTitle,
        album_name: str,
        index: FileIndex,
        json_path: str,
        title: str
    ) -> MatchResult:
        """Tier 2: Extended matching for suffix+bracket combinations.

        Handles cases like photo-edited(1).jpg where:
        - JSON is photo.jpg.json (no bracket)
        - File is photo-edited(1).jpg (suffix AND bracket)

        This catches edited duplicates that Tier 1 misses.
        """
        # Only try tier 2 if we have suffixes beyond empty string
        # and the JSON doesn't already have a bracket marker
        if parsed.duplicate_suffix:
            # Already has a bracket from JSON, tier 1 should have found it
            return MatchResult(found=False, files=[], json_path=json_path, title=title)

        # Try each non-empty suffix with bracket variations
        for suffix in self.suffixes:
            if not suffix:
                continue  # Skip empty suffix, already tried without brackets

            # Check for suffix+(n) combinations up to (10)
            for n in range(1, 11):
                filename = f"{parsed.name}{suffix}({n}){parsed.extension}"
                key = (album_name, filename)

                if key in index:
                    return MatchResult(
                        found=True,
                        files=index[key],
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

    def find_all_related_files(
        self,
        json_path: str,
        title: str,
        file_index: Optional[FileIndex] = None
    ) -> MatchResult:
        """Find ALL files related to a JSON, including edited variants.

        Unlike find_match which returns on first match, this method collects
        all files that should receive the same metadata:
        - photo.jpg (original)
        - photo-edited.jpg (edited version)
        - photo-edited(1).jpg, photo-edited(2).jpg, etc. (edited duplicates)

        Args:
            json_path: Path to the JSON metadata file.
            title: The "title" field from the JSON.
            file_index: Optional alternative index to search in.

        Returns:
            MatchResult with all related files (may be empty if no matches).
        """
        index = file_index if file_index is not None else self.file_index
        parsed = self.parse_title(title, json_path)
        # Normalize album name to match normalized keys in file index
        album_name = normalize_filename(get_album_name(json_path))

        all_files: List[FileInfo] = []

        # Collect all suffix variations
        for suffix in self.suffixes:
            # Base filename with suffix (and original bracket if any)
            filename = parsed.build_filename(suffix)
            key = (album_name, filename)
            if key in index:
                all_files.extend(index[key])

            # Also check for bracket variations (1) through (10)
            # This catches -edited(1), -edited(2), etc.
            for n in range(1, 11):
                if parsed.duplicate_suffix:
                    # Already has bracket, don't add another
                    break
                bracket_filename = f"{parsed.name}{suffix}({n}){parsed.extension}"
                bracket_key = (album_name, bracket_filename)
                if bracket_key in index:
                    all_files.extend(index[bracket_key])

        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in all_files:
            if f.filepath not in seen:
                seen.add(f.filepath)
                unique_files.append(f)

        return MatchResult(
            found=len(unique_files) > 0,
            files=unique_files,
            json_path=json_path,
            title=title
        )


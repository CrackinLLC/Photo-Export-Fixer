# Task 06: Extract Matcher (Deduplicate!)

## Objective
Extract and deduplicate the file matching logic that currently appears in 4 places. This is the most important refactoring for maintainability.

## Prerequisites
- Task 01 (Module Structure) complete
- Task 02 (Models) complete
- Task 03 (Utils) complete

## Files to Create
- `pef/core/matcher.py`

## Current State Analysis

The same matching logic appears in 4 places:

### 1. `find_file()` (lines 235-263)
```python
def find_file(jsondata, file_index, suffixes):
    name, ext = os.path.splitext(jsondata["title"])
    if len(name + ext) > 51:
        name = name[0:51-len(ext)]
    brackets = None
    if jsondata["filepath"].endswith(").json"):
        bracket_match = re.findall("\\([1-999]\\)\\.json", jsondata["filepath"])
        if bracket_match:
            brackets = bracket_match[-1][:-5]
    album_name = get_album_name(jsondata["filepath"])
    for suffix in suffixes:
        if brackets:
            filename = name + suffix + brackets + ext
        else:
            filename = name + suffix + ext
        key = (album_name, filename)
        if key in file_index:
            return True, file_index[key]
    return False, [{"jsonpath": jsondata["filepath"], "title": jsondata["title"]}]
```

### 2. `dry_run_main()` (lines 416-440) - Same logic duplicated
### 3. `dry_run_extend()` (lines 526-554) - Same logic duplicated
### 4. `extend_metadata()` (lines 628-659) - Same logic duplicated

### Problems
1. **4x code duplication** - Bug fixes must be applied 4 times
2. **Inconsistent handling** - Some use dicts, some use different return types
3. **Not testable** - Logic buried in larger functions

## Implementation

### `pef/core/matcher.py`

```python
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
from typing import List, Optional, Tuple

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

    def find_match_from_metadata(self, json_path: str, title: str, file_index: FileIndex) -> MatchResult:
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
```

## Usage Examples

### New style (with FileMatcher):
```python
from pef.core.matcher import FileMatcher
from pef.core.scanner import FileScanner

scanner = FileScanner(path)
scanner.scan()

matcher = FileMatcher(scanner.file_index)

for json_path in scanner.jsons:
    with open(json_path) as f:
        data = json.load(f)

    result = matcher.find_match(json_path, data["title"])
    if result.found:
        for file in result.files:
            print(f"Matched: {file.filepath}")
```

### Old style (backwards compatible):
```python
from pef.core.matcher import find_file

found, files = find_file(jsondata, file_index, suffixes)
```

## Acceptance Criteria

1. [ ] `pef/core/matcher.py` exists with `FileMatcher` class
2. [ ] `FileMatcher.parse_title()` handles 51-char truncation correctly
3. [ ] `FileMatcher.parse_title()` extracts brackets from JSON path
4. [ ] `FileMatcher.find_match()` tries all suffix combinations
5. [ ] `find_file()` backwards-compatible function works
6. [ ] Original `pef.py` still works unchanged

## Verification

```python
from pef.core.matcher import FileMatcher, ParsedTitle

# Test ParsedTitle
matcher = FileMatcher({})

# Normal case
p = matcher.parse_title("photo.jpg", "/album/photo.jpg.json")
assert p.name == "photo"
assert p.extension == ".jpg"
assert p.brackets is None
assert p.build_filename() == "photo.jpg"
assert p.build_filename("-edited") == "photo-edited.jpg"

# With brackets
p = matcher.parse_title("photo.jpg", "/album/photo.jpg(1).json")
assert p.brackets == "(1)"
assert p.build_filename() == "photo(1).jpg"
assert p.build_filename("-edited") == "photo-edited(1).jpg"

# Long filename (51+ chars)
long_name = "a" * 50 + ".jpg"  # 54 chars total
p = matcher.parse_title(long_name, "/album/test.json")
assert len(p.name + p.extension) == 51

print("All matcher tests passed!")
```

## Test Cases to Cover

1. **Normal matching**: `photo.jpg` -> `photo.jpg`
2. **With suffix**: `photo.jpg` -> `photo-edited.jpg`
3. **With brackets**: `photo.jpg(1).json` -> `photo(1).jpg`
4. **Suffix + brackets**: `photo.jpg(1).json` -> `photo-edited(1).jpg`
5. **Long filename**: 60-char name truncated to 51
6. **Multiple matches**: Same file in index multiple times
7. **No match**: JSON without corresponding file

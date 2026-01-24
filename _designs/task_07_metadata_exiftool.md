# Task 07: Extract Metadata & ExifTool

## Objective
Extract EXIF metadata building and ExifTool management into dedicated modules.

## Prerequisites
- Task 01 (Module Structure) complete
- Task 02 (Models) complete

## Files to Create
- `pef/core/metadata.py`
- `pef/core/exiftool.py`

## Current State Analysis

### ExifTool management (lines 20-80)
- `get_exiftool_path()` - Find or download ExifTool
- `auto_download_exiftool()` - Download for Windows

### Metadata builders (lines 200-233)
- `build_gps_tags(geo_data)` - Convert Google geoData to EXIF tags
- `build_people_tags(people_list)` - Convert people array to EXIF tags

## Implementation

### `pef/core/metadata.py`

```python
"""EXIF metadata tag builders for Photo Export Fixer.

Converts Google Photos JSON metadata into ExifTool-compatible tag dictionaries.
"""

from typing import Dict, List, Optional, Any

from pef.core.models import GeoData, Person


def build_gps_tags(geo_data: Optional[GeoData]) -> Dict[str, Any]:
    """Convert GPS coordinates to ExifTool tag dictionary.

    Args:
        geo_data: GeoData object with lat/lon/alt, or None.

    Returns:
        Dict of ExifTool tags, empty if geo_data is None/invalid.

    Example:
        >>> build_gps_tags(GeoData(40.7128, -74.0060, 10))
        {
            'GPSLatitude': 40.7128,
            'GPSLatitudeRef': 'N',
            'GPSLongitude': 74.0060,
            'GPSLongitudeRef': 'W',
            'GPSAltitude': 10,
            'GPSAltitudeRef': 0,
        }
    """
    if not geo_data or not geo_data.is_valid():
        return {}

    return {
        "GPSLatitude": abs(geo_data.latitude),
        "GPSLatitudeRef": "N" if geo_data.latitude >= 0 else "S",
        "GPSLongitude": abs(geo_data.longitude),
        "GPSLongitudeRef": "E" if geo_data.longitude >= 0 else "W",
        "GPSAltitude": abs(geo_data.altitude),
        "GPSAltitudeRef": 0 if geo_data.altitude >= 0 else 1,
    }


def build_gps_tags_from_dict(geo_dict: Optional[Dict]) -> Dict[str, Any]:
    """Convert Google's geoData dict to ExifTool tags (backwards compatible).

    Args:
        geo_dict: Google's geoData dict with latitude/longitude/altitude keys.

    Returns:
        Dict of ExifTool tags.
    """
    geo_data = GeoData.from_dict(geo_dict)
    return build_gps_tags(geo_data)


def build_people_tags(people: List[Person]) -> Dict[str, Any]:
    """Convert people list to ExifTool tag dictionary.

    Writes to multiple tag locations for maximum compatibility:
    - PersonInImage: XMP-iptcExt standard
    - Keywords: IPTC keywords
    - Subject: XMP-dc subject
    - XPKeywords: Windows Explorer

    Args:
        people: List of Person objects.

    Returns:
        Dict of ExifTool tags, empty if no people.

    Example:
        >>> build_people_tags([Person("Alice"), Person("Bob")])
        {
            'PersonInImage': ['Alice', 'Bob'],
            'Keywords': ['Alice', 'Bob'],
            'Subject': ['Alice', 'Bob'],
            'XPKeywords': 'Alice;Bob',
        }
    """
    if not people:
        return {}

    names = [p.name for p in people]

    return {
        "PersonInImage": names,           # XMP-iptcExt (list for multiple)
        "Keywords": names,                # IPTC keywords
        "Subject": names,                 # XMP-dc subject
        "XPKeywords": ";".join(names),   # Windows (semicolon-separated)
    }


def build_people_tags_from_list(people_list: Optional[List[Dict]]) -> Dict[str, Any]:
    """Convert Google's people array to ExifTool tags (backwards compatible).

    Args:
        people_list: Google's people array with name dicts.

    Returns:
        Dict of ExifTool tags.
    """
    people = Person.from_list(people_list)
    return build_people_tags(people)


def build_all_tags(
    geo_data: Optional[GeoData] = None,
    people: Optional[List[Person]] = None,
    description: str = ""
) -> Dict[str, Any]:
    """Build complete ExifTool tag dictionary from all metadata.

    Args:
        geo_data: Optional GPS coordinates.
        people: Optional list of people.
        description: Optional description/caption.

    Returns:
        Combined dict of all tags.
    """
    tags = {}
    tags.update(build_gps_tags(geo_data))
    tags.update(build_people_tags(people or []))

    if description:
        tags["ImageDescription"] = description
        tags["Caption-Abstract"] = description  # IPTC
        tags["Description"] = description       # XMP-dc

    return tags
```

### `pef/core/exiftool.py`

```python
"""ExifTool management for Photo Export Fixer.

Handles finding, downloading, and initializing ExifTool.
"""

import os
import shutil
import sys
from typing import Optional, Any

# ExifTool download URL (Windows executable)
EXIFTOOL_URL = "https://exiftool.org/exiftool-13.11.zip"
EXIFTOOL_DIR = "tools/exiftool"
EXIFTOOL_EXE = "exiftool.exe"


def get_exiftool_path(base_dir: Optional[str] = None) -> Optional[str]:
    """Find ExifTool executable.

    Checks in order:
    1. System PATH
    2. Local tools directory
    3. Attempts auto-download (Windows only)

    Args:
        base_dir: Base directory for local tools folder.
                 Defaults to directory containing this module.

    Returns:
        Path to exiftool executable, or None if not found.
    """
    # 1. Check system PATH
    if shutil.which("exiftool"):
        return "exiftool"

    # 2. Check local tools folder
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    local_path = os.path.join(base_dir, EXIFTOOL_DIR, EXIFTOOL_EXE)
    if os.path.exists(local_path):
        return local_path

    # 3. Attempt auto-download (Windows only)
    if sys.platform == "win32":
        if auto_download_exiftool(base_dir):
            return local_path

    return None


def auto_download_exiftool(base_dir: str) -> bool:
    """Download ExifTool for Windows.

    Args:
        base_dir: Base directory to install into.

    Returns:
        True if download succeeded, False otherwise.
    """
    import urllib.request
    import zipfile

    tools_dir = os.path.join(base_dir, EXIFTOOL_DIR)
    os.makedirs(tools_dir, exist_ok=True)

    zip_path = os.path.join(tools_dir, "exiftool.zip")

    try:
        print("Downloading ExifTool...")
        urllib.request.urlretrieve(EXIFTOOL_URL, zip_path)

        print("Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tools_dir)

        # Rename the executable (comes as exiftool(-k).exe)
        for f in os.listdir(tools_dir):
            if f.startswith("exiftool") and f.endswith(".exe"):
                old_path = os.path.join(tools_dir, f)
                new_path = os.path.join(tools_dir, EXIFTOOL_EXE)
                if old_path != new_path:
                    os.rename(old_path, new_path)
                break

        os.remove(zip_path)
        print("ExifTool installed successfully!")
        return True

    except Exception as e:
        print(f"Auto-download failed: {e}")
        return False


def print_install_instructions() -> None:
    """Print manual installation instructions."""
    print("ExifTool not found. Please install it:")
    print("  1. Download from https://exiftool.org/")
    print("  2. Extract and rename exiftool(-k).exe to exiftool.exe")
    print("  3. Place in PATH or in ./tools/exiftool/")


def is_exiftool_available() -> bool:
    """Check if ExifTool is available.

    Returns:
        True if ExifTool can be found.
    """
    return get_exiftool_path() is not None


class ExifToolManager:
    """Manages ExifTool lifecycle for batch operations.

    Usage:
        with ExifToolManager() as et:
            et.write_tags("/path/to/file.jpg", {"GPSLatitude": 40.7})

    Or for processing many files:
        manager = ExifToolManager()
        manager.start()
        for file in files:
            manager.write_tags(file, tags)
        manager.stop()
    """

    def __init__(self):
        """Initialize manager."""
        self._helper = None
        self._exiftool_path = None

    def start(self) -> bool:
        """Start ExifTool process.

        Returns:
            True if started successfully, False otherwise.
        """
        try:
            import exiftool
        except ImportError:
            print("pyexiftool not installed. Run: pip install pyexiftool")
            return False

        self._exiftool_path = get_exiftool_path()
        if not self._exiftool_path:
            print_install_instructions()
            return False

        try:
            self._helper = exiftool.ExifToolHelper(executable=self._exiftool_path)
            self._helper.run()
            return True
        except Exception as e:
            print(f"Failed to start ExifTool: {e}")
            return False

    def stop(self) -> None:
        """Stop ExifTool process."""
        if self._helper:
            try:
                self._helper.terminate()
            except:
                pass
            self._helper = None

    def write_tags(self, filepath: str, tags: dict) -> bool:
        """Write tags to a file.

        Args:
            filepath: Path to file.
            tags: Dict of ExifTool tags.

        Returns:
            True if successful, False otherwise.
        """
        if not self._helper or not tags:
            return False

        try:
            self._helper.set_tags(filepath, tags)
            return True
        except Exception as e:
            # Log but don't raise - allow processing to continue
            return False

    @property
    def is_running(self) -> bool:
        """Check if ExifTool is running."""
        return self._helper is not None

    def __enter__(self) -> "ExifToolManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
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

from pef.core.metadata import (
    build_gps_tags,
    build_people_tags,
    build_all_tags,
)

from pef.core.exiftool import (
    get_exiftool_path,
    is_exiftool_available,
    ExifToolManager,
)

__all__ = [
    # utils
    "exists",
    "get_unique_path",
    "checkout_dir",
    "get_album_name",
    "normalize_path",
    # metadata
    "build_gps_tags",
    "build_people_tags",
    "build_all_tags",
    # exiftool
    "get_exiftool_path",
    "is_exiftool_available",
    "ExifToolManager",
]
```

## Acceptance Criteria

1. [ ] `pef/core/metadata.py` exists with tag builders
2. [ ] `pef/core/exiftool.py` exists with ExifTool management
3. [ ] `build_gps_tags()` produces correct EXIF tags
4. [ ] `build_people_tags()` writes to all 4 tag locations
5. [ ] `ExifToolManager` supports context manager pattern
6. [ ] `get_exiftool_path()` finds or downloads ExifTool
7. [ ] Original `pef.py` still works unchanged

## Verification

```python
from pef.core.models import GeoData, Person
from pef.core.metadata import build_gps_tags, build_people_tags, build_all_tags
from pef.core.exiftool import get_exiftool_path, ExifToolManager

# Test GPS tags
geo = GeoData(latitude=40.7128, longitude=-74.0060, altitude=10)
gps_tags = build_gps_tags(geo)
print("GPS tags:", gps_tags)
assert gps_tags["GPSLatitudeRef"] == "N"
assert gps_tags["GPSLongitudeRef"] == "W"

# Test people tags
people = [Person("Alice"), Person("Bob")]
people_tags = build_people_tags(people)
print("People tags:", people_tags)
assert "Alice" in people_tags["Keywords"]
assert people_tags["XPKeywords"] == "Alice;Bob"

# Test ExifTool path
path = get_exiftool_path()
print(f"ExifTool at: {path}")

# Test ExifToolManager (if available)
with ExifToolManager() as et:
    if et.is_running:
        print("ExifTool started successfully")
```

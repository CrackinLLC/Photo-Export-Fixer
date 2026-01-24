# Task 02: Create Data Models

## Objective
Define data classes and type aliases to replace the dictionaries currently used throughout the code. This improves type safety and IDE support.

## Prerequisites
- Task 01 (Module Structure) complete

## Files to Create
- `pef/core/models.py`

## Current State Analysis

The code currently uses dictionaries for:
1. **File info** (lines 141-145):
   ```python
   {"filename": file, "filepath": os.path.join(...), "albumname": get_album_name(...)}
   ```

2. **JSON metadata** (lines 175-182):
   ```python
   {"filepath": path, "title": content["title"], "date": datetime.fromtimestamp(...),
    "geoData": content.get("geoData"), "people": content.get("people"), "description": ...}
   ```

3. **Unprocessed items** (lines 730-733, 767-770):
   ```python
   {"filename": ..., "filepath": ..., "title": ..., "time": ...}
   ```

4. **Processed items** (lines 757-762):
   ```python
   file["procpath"] = ...; file["jsonpath"] = ...; file["time"] = ...
   ```

## Implementation

### `pef/core/models.py`

```python
"""Data models for Photo Export Fixer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Callable, Any


@dataclass
class FileInfo:
    """Represents a media file found during scanning."""
    filename: str
    filepath: str
    albumname: str

    # Populated during processing
    procpath: Optional[str] = None
    jsonpath: Optional[str] = None
    processed_time: Optional[str] = None


@dataclass
class GeoData:
    """GPS coordinates from Google Photos metadata."""
    latitude: float
    longitude: float
    altitude: float = 0.0

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> Optional["GeoData"]:
        """Create from Google's geoData dict, or None if invalid."""
        if not data or data.get("latitude", 0) == 0:
            return None
        return cls(
            latitude=data["latitude"],
            longitude=data["longitude"],
            altitude=data.get("altitude", 0.0)
        )

    def is_valid(self) -> bool:
        """Check if coordinates are meaningful (not 0,0)."""
        return self.latitude != 0 or self.longitude != 0


@dataclass
class Person:
    """A person tagged in a photo."""
    name: str

    @classmethod
    def from_list(cls, data: Optional[List[Dict]]) -> List["Person"]:
        """Create list from Google's people array."""
        if not data:
            return []
        return [cls(name=p["name"]) for p in data if "name" in p]


@dataclass
class JsonMetadata:
    """Metadata extracted from a Google Takeout JSON file."""
    filepath: str
    title: str
    date: datetime
    geo_data: Optional[GeoData] = None
    people: List[Person] = field(default_factory=list)
    description: str = ""

    def has_location(self) -> bool:
        """Check if this metadata includes GPS coordinates."""
        return self.geo_data is not None and self.geo_data.is_valid()

    def has_people(self) -> bool:
        """Check if this metadata includes people tags."""
        return len(self.people) > 0

    def get_people_names(self) -> List[str]:
        """Get list of people names."""
        return [p.name for p in self.people]


@dataclass
class UnprocessedItem:
    """An item (file or JSON) that couldn't be matched/processed."""
    filename: str
    filepath: str
    title: str = ""
    reason: str = ""
    processed_time: str = ""
    procpath: Optional[str] = None  # Path after copying to Unprocessed folder


@dataclass
class ProcessingStats:
    """Statistics from a processing run."""
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    with_gps: int = 0
    with_people: int = 0
    unmatched_jsons: int = 0
    unmatched_files: int = 0

    def total_files(self) -> int:
        return self.processed + self.skipped + self.errors


# Type aliases for callbacks
# (current_item, total_items, message) -> None
ProgressCallback = Callable[[int, int, str], None]

# File index type: (albumname, filename) -> list of FileInfo
FileIndex = Dict[tuple, List[FileInfo]]
```

## Migration Notes

After creating models.py, subsequent tasks will update functions to use these classes:
- Task 05 (Scanner): Return `List[FileInfo]` instead of list of dicts
- Task 06 (Matcher): Accept `JsonMetadata` instead of dict
- Task 08 (Processor): Use `ProcessingStats` for return values

## Acceptance Criteria

1. [ ] `pef/core/models.py` exists with all dataclasses
2. [ ] All dataclasses have proper type hints
3. [ ] Helper methods (`from_dict`, `is_valid`, etc.) work correctly
4. [ ] Can import: `from pef.core.models import FileInfo, JsonMetadata`
5. [ ] Original `pef.py` still works (no changes to it yet)

## Verification

```python
# Test in Python REPL
from pef.core.models import FileInfo, JsonMetadata, GeoData, Person, ProcessingStats

# Test FileInfo
f = FileInfo(filename="test.jpg", filepath="/path/test.jpg", albumname="Album1")
print(f)

# Test GeoData
geo = GeoData.from_dict({"latitude": 40.7128, "longitude": -74.0060, "altitude": 10})
print(geo, geo.is_valid())

# Test JsonMetadata
meta = JsonMetadata(
    filepath="/path/test.json",
    title="test.jpg",
    date=datetime.now(),
    geo_data=geo,
    people=Person.from_list([{"name": "Alice"}, {"name": "Bob"}])
)
print(meta.has_location(), meta.has_people(), meta.get_people_names())
```

## Notes

- Using `@dataclass` for automatic `__init__`, `__repr__`, `__eq__`
- `field(default_factory=list)` for mutable defaults
- Type aliases at module level for documentation
- `Optional[X]` for nullable fields

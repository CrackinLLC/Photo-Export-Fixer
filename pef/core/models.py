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
    """GPS coordinates from photo metadata."""
    latitude: float
    longitude: float
    altitude: float = 0.0

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> Optional["GeoData"]:
        """Create from geoData dict, or None if invalid."""
        if not data or (data.get("latitude", 0) == 0 and data.get("longitude", 0) == 0):
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
        """Create list from people array."""
        if not data:
            return []
        return [cls(name=p["name"]) for p in data if "name" in p]


@dataclass
class JsonMetadata:
    """Metadata extracted from a photo export JSON file."""
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


@dataclass
class ProcessingResult:
    """Result from processing a batch of files."""
    stats: ProcessingStats
    processed_files: List[FileInfo] = field(default_factory=list)
    unprocessed_files: List[UnprocessedItem] = field(default_factory=list)
    unprocessed_jsons: List[UnprocessedItem] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


# Type aliases for callbacks
# (current_item, total_items, message) -> None
ProgressCallback = Callable[[int, int, str], None]

# File index type: (albumname, filename) -> list of FileInfo
FileIndex = Dict[tuple, List[FileInfo]]

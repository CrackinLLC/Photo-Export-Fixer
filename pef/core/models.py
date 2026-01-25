"""Data models for Photo Export Fixer."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Callable, Tuple


@dataclass(slots=True)
class FileInfo:
    """Represents a media file found during scanning.

    Uses __slots__ for 30-50% memory reduction on large collections.
    """
    filename: str
    filepath: str
    album_name: str

    # Populated during processing
    output_path: Optional[str] = None
    json_path: Optional[str] = None
    processed_time: Optional[str] = None


@dataclass(slots=True)
class GeoData:
    """GPS coordinates from photo metadata.

    Uses __slots__ for memory efficiency.
    """
    latitude: float
    longitude: float
    altitude: float = 0.0

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> Optional["GeoData"]:
        """Create from geoData dict, or None if missing/empty.

        Note: (0,0) coordinates are valid (equator/prime meridian intersection)
        and will be accepted. Only missing/None data is rejected.
        """
        if not data:
            return None
        # Check for required keys - latitude and longitude must be present
        if "latitude" not in data or "longitude" not in data:
            return None
        return cls(
            latitude=data["latitude"],
            longitude=data["longitude"],
            altitude=data.get("altitude", 0.0)
        )

    def is_valid(self) -> bool:
        """Check if coordinates are valid GPS values.

        Note: (0,0) is a valid location (Gulf of Guinea, off coast of Africa).
        This method checks for reasonable coordinate ranges.
        """
        return -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180


@dataclass(slots=True)
class Person:
    """A person tagged in a photo.

    Uses __slots__ for memory efficiency.
    """
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

    @property
    def filename(self) -> str:
        """Get the filename from the filepath."""
        return os.path.basename(self.filepath)

    def get_coordinates_string(self) -> Optional[str]:
        """Get GPS coordinates as 'lat,lng' string, or None if no location."""
        if self.has_location():
            return f"{self.geo_data.latitude},{self.geo_data.longitude}"
        return None


@dataclass
class UnprocessedItem:
    """A file that was copied but had no matching JSON metadata."""
    relative_path: str  # Path relative to output root (e.g., "Album/photo.jpg")
    reason: str         # Why it wasn't processed (e.g., "No matching JSON found")
    source_path: str = ""  # Original source path


@dataclass
class MotionPhotoInfo:
    """Information about a motion photo sidecar file."""
    relative_path: str  # Path relative to output (e.g., "Album/photo.jpg.MP")
    parent_image: str   # The parent image filename (e.g., "photo.jpg")
    extension: str      # Original extension (.MP, .MP~2, etc.)


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
class DryRunResult:
    """Results from a dry-run analysis."""
    json_count: int = 0
    file_count: int = 0
    matched_count: int = 0
    unmatched_json_count: int = 0
    unmatched_file_count: int = 0
    with_gps: int = 0
    with_people: int = 0
    exiftool_available: bool = False
    exiftool_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class ProcessRunResult:
    """Results from a full processing run.

    Contains output paths, timing information, and statistics.
    Returned by PEFOrchestrator.process() and extend().
    """
    stats: ProcessingStats
    output_dir: str           # Root output directory (source_processed/)
    pef_dir: str              # Metadata directory (source_processed/_pef/)
    summary_file: str         # Path to summary.txt
    elapsed_time: float
    start_time: str
    end_time: str
    errors: List[str] = field(default_factory=list)
    resumed: bool = False
    skipped_count: int = 0
    interrupted: bool = False
    motion_photo_count: int = 0
    unprocessed_items: List[UnprocessedItem] = field(default_factory=list)

# Type aliases for callbacks
# (current_item, total_items, message) -> None
ProgressCallback = Callable[[int, int, str], None]

# File index type: (album_name, filename) -> list of FileInfo
FileIndex = Dict[Tuple[str, str], List[FileInfo]]

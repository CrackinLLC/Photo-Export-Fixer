"""Core processing logic for Photo Export Fixer."""

from pef.core.models import (
    FileInfo,
    GeoData,
    Person,
    JsonMetadata,
    UnprocessedItem,
    ProcessingStats,
    ProcessRunResult,
    DryRunResult,
    ProgressCallback,
    FileIndex,
)

from pef.core.utils import (
    exists,
    get_unique_path,
    checkout_dir,
    get_album_name,
    normalize_path,
)

from pef.core.logger import (
    BufferedLogger,
    SummaryLogger,
    NullLogger,
    create_logger,
)

from pef.core.scanner import (
    FileScanner,
    scan_directory,
)

from pef.core.matcher import (
    FileMatcher,
    MatchResult,
    ParsedTitle,
    DEFAULT_SUFFIXES,
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

from pef.core.processor import (
    FileProcessor,
)

from pef.core.orchestrator import (
    PEFOrchestrator,
)

__all__ = [
    # Models
    "FileInfo",
    "GeoData",
    "Person",
    "JsonMetadata",
    "UnprocessedItem",
    "ProcessingStats",
    "ProcessRunResult",
    "DryRunResult",
    "ProgressCallback",
    "FileIndex",
    # Utils
    "exists",
    "get_unique_path",
    "checkout_dir",
    "get_album_name",
    "normalize_path",
    # Logger
    "BufferedLogger",
    "SummaryLogger",
    "NullLogger",
    "create_logger",
    # Scanner
    "FileScanner",
    "scan_directory",
    # Matcher
    "FileMatcher",
    "MatchResult",
    "ParsedTitle",
    "DEFAULT_SUFFIXES",
    # Metadata
    "build_gps_tags",
    "build_people_tags",
    "build_all_tags",
    # ExifTool
    "get_exiftool_path",
    "is_exiftool_available",
    "ExifToolManager",
    # Processor
    "FileProcessor",
    # Orchestrator
    "PEFOrchestrator",
]

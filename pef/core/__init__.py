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
    ProcessResult,
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
    get_file_names,
)

from pef.core.matcher import (
    FileMatcher,
    MatchResult,
    ParsedTitle,
    find_file,
    DEFAULT_SUFFIXES,
)

from pef.core.metadata import (
    build_gps_tags,
    build_gps_tags_from_dict,
    build_people_tags,
    build_people_tags_from_list,
    build_all_tags,
)

from pef.core.exiftool import (
    get_exiftool_path,
    is_exiftool_available,
    ExifToolManager,
)

from pef.core.processor import (
    FileProcessor,
    copy_modify,
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
    "ProcessResult",
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
    "get_file_names",
    # Matcher
    "FileMatcher",
    "MatchResult",
    "ParsedTitle",
    "find_file",
    "DEFAULT_SUFFIXES",
    # Metadata
    "build_gps_tags",
    "build_gps_tags_from_dict",
    "build_people_tags",
    "build_people_tags_from_list",
    "build_all_tags",
    # ExifTool
    "get_exiftool_path",
    "is_exiftool_available",
    "ExifToolManager",
    # Processor
    "FileProcessor",
    "copy_modify",
    # Orchestrator
    "PEFOrchestrator",
    "DryRunResult",
    "ProcessResult",
]

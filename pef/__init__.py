"""Photo Export Fixer - Process and organize photo exports from various services.

High-level API:
    from pef import PEFOrchestrator

    orchestrator = PEFOrchestrator("/path/to/takeout", "/path/to/output")

    # Preview what will be processed
    result = orchestrator.dry_run()
    print(f"Found {result.matched_count} files to process")

    # Process files
    result = orchestrator.process()
    print(f"Processed {result.stats.processed} files")

For more details, see:
    https://github.com/CrackinLLC/Photo-Export-Fixer
"""

__version__ = "3.2.0"
__author__ = "CrackinLLC"
__repo__ = "https://github.com/CrackinLLC/Photo-Export-Fixer"

# Public API exports
from pef.core.orchestrator import PEFOrchestrator
from pef.core.models import (
    ProcessRunResult,
    DryRunResult,
    ProcessingStats,
    JsonMetadata,
    FileInfo,
    GeoData,
    Person,
)

__all__ = [
    "PEFOrchestrator",
    "ProcessRunResult",
    "DryRunResult",
    "ProcessingStats",
    "JsonMetadata",
    "FileInfo",
    "GeoData",
    "Person",
    "__version__",
]

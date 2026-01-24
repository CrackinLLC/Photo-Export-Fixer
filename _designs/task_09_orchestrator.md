# Task 09: Create Orchestrator

## Objective
Create a high-level `PEFOrchestrator` class that coordinates scanning, matching, and processing. This is the single entry point that both CLI and GUI will use.

## Prerequisites
- Task 01 (Module Structure) complete
- Task 02-08 (All core modules) complete

## Files to Create
- `pef/core/orchestrator.py`

## Design Goals

1. **Single entry point** for all operations (dry-run, process, extend)
2. **UI-agnostic** - uses callbacks for progress, not tqdm directly
3. **Stateless operations** - each call is independent
4. **Clean error handling** - returns results, doesn't print

## Implementation

### `pef/core/orchestrator.py`

```python
"""High-level orchestrator for Photo Export Fixer.

Coordinates scanning, matching, and processing operations.
Used by both CLI and GUI.
"""

import os
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable

from pef.core.models import (
    FileInfo, JsonMetadata, GeoData, Person,
    ProcessingStats, ProgressCallback
)
from pef.core.utils import exists, checkout_dir
from pef.core.scanner import FileScanner
from pef.core.matcher import FileMatcher, DEFAULT_SUFFIXES
from pef.core.processor import FileProcessor
from pef.core.logger import BufferedLogger, SummaryLogger
from pef.core.exiftool import is_exiftool_available


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
class ProcessResult:
    """Results from a processing run."""
    stats: ProcessingStats
    output_dir: str
    processed_dir: str
    unprocessed_dir: str
    log_file: str
    elapsed_time: float
    start_time: str
    end_time: str
    errors: List[str] = field(default_factory=list)


class PEFOrchestrator:
    """Coordinates all Google Takeout processing operations.

    Usage:
        orchestrator = PEFOrchestrator(
            source_path="/path/to/takeout",
            dest_path="/path/to/output"  # optional
        )

        # Dry run to preview
        result = orchestrator.dry_run(on_progress=my_callback)
        print(f"Would process: {result.matched_count} files")

        # Actual processing
        result = orchestrator.process(on_progress=my_callback)
        print(f"Processed: {result.stats.processed} files")

        # Extend metadata on existing files
        result = orchestrator.extend(on_progress=my_callback)
    """

    def __init__(
        self,
        source_path: str,
        dest_path: Optional[str] = None,
        suffixes: Optional[List[str]] = None,
        write_exif: bool = True
    ):
        """Initialize orchestrator.

        Args:
            source_path: Path to Google Takeout directory.
            dest_path: Output directory (default: source_path + "_pefProcessed").
            suffixes: Filename suffixes to try (default: ["", "-edited"]).
            write_exif: Whether to write EXIF metadata.
        """
        self.source_path = source_path
        self.dest_path = dest_path or f"{source_path}_pefProcessed"
        self.suffixes = suffixes or DEFAULT_SUFFIXES
        self.write_exif = write_exif

    def dry_run(
        self,
        on_progress: Optional[ProgressCallback] = None
    ) -> DryRunResult:
        """Preview what would be processed without making changes.

        Args:
            on_progress: Optional callback for progress updates.

        Returns:
            DryRunResult with counts and statistics.
        """
        result = DryRunResult()

        # Validate source
        if not exists(self.source_path):
            result.errors.append(f"Source path does not exist: {self.source_path}")
            return result

        # Check ExifTool
        if self.write_exif:
            result.exiftool_available = is_exiftool_available()
            if result.exiftool_available:
                from pef.core.exiftool import get_exiftool_path
                result.exiftool_path = get_exiftool_path()

        # Scan files
        if on_progress:
            on_progress(0, 100, "Scanning files...")

        scanner = FileScanner(self.source_path)
        scanner.scan(on_progress)

        result.json_count = scanner.json_count
        result.file_count = scanner.file_count

        # Analyze matches
        matcher = FileMatcher(scanner.file_index, self.suffixes)

        total_jsons = len(scanner.jsons)
        for i, json_path in enumerate(scanner.jsons):
            if on_progress and i % 100 == 0:
                on_progress(i, total_jsons, f"Analyzing: {os.path.basename(json_path)}")

            try:
                metadata = self._read_json(json_path)
                if not metadata:
                    result.unmatched_json_count += 1
                    continue

                match = matcher.find_match(json_path, metadata.title)
                if match.found:
                    result.matched_count += 1
                    if metadata.has_location():
                        result.with_gps += 1
                    if metadata.has_people():
                        result.with_people += 1
                else:
                    result.unmatched_json_count += 1

            except Exception as e:
                result.unmatched_json_count += 1

        result.unmatched_file_count = result.file_count - result.matched_count

        if on_progress:
            on_progress(total_jsons, total_jsons, "Analysis complete")

        return result

    def process(
        self,
        on_progress: Optional[ProgressCallback] = None
    ) -> ProcessResult:
        """Run full processing.

        Args:
            on_progress: Optional callback for progress updates.

        Returns:
            ProcessResult with statistics and paths.
        """
        start_time = time.time()
        start_date = time.strftime("%Y-%m-%d %H:%M:%S")

        # Create output directory
        output_dir = checkout_dir(self.dest_path, onlynew=True)

        result = ProcessResult(
            stats=ProcessingStats(),
            output_dir=output_dir,
            processed_dir=os.path.join(output_dir, "Processed"),
            unprocessed_dir=os.path.join(output_dir, "Unprocessed"),
            log_file=os.path.join(output_dir, "logs.txt"),
            elapsed_time=0,
            start_time=start_date,
            end_time=""
        )

        # Validate source
        if not exists(self.source_path):
            result.errors.append(f"Source path does not exist: {self.source_path}")
            return result

        # Scan
        if on_progress:
            on_progress(0, 100, "Scanning files...")

        scanner = FileScanner(self.source_path)
        scanner.scan()

        # Process
        processed_files = []
        unprocessed_jsons = []
        matched_file_paths = set()

        with BufferedLogger(output_dir) as logger:
            logger.log(f"Started processing: {self.source_path}")

            with FileProcessor(output_dir, logger=logger, write_exif=self.write_exif) as processor:
                matcher = FileMatcher(scanner.file_index, self.suffixes)

                total = len(scanner.jsons)
                for i, json_path in enumerate(scanner.jsons):
                    if on_progress:
                        on_progress(i, total, f"Processing: {os.path.basename(json_path)}")

                    metadata = self._read_json(json_path)
                    if not metadata:
                        unprocessed_jsons.append({
                            "filename": os.path.basename(json_path),
                            "filepath": json_path,
                            "title": "Invalid JSON",
                            "time": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        continue

                    match = matcher.find_match(json_path, metadata.title)
                    if match.found:
                        for file_info in match.files:
                            try:
                                dest = processor.process_file(file_info, metadata)
                                matched_file_paths.add(file_info.filepath)
                                processed_files.append({
                                    "filename": file_info.filename,
                                    "filepath": file_info.filepath,
                                    "procpath": dest,
                                    "jsonpath": json_path,
                                    "time": time.strftime("%Y-%m-%d %H:%M:%S")
                                })
                            except Exception as e:
                                result.errors.append(f"Error processing {file_info.filepath}: {e}")
                    else:
                        unprocessed_jsons.append({
                            "filename": os.path.basename(json_path),
                            "filepath": json_path,
                            "title": metadata.title,
                            "time": time.strftime("%Y-%m-%d %H:%M:%S")
                        })

                # Handle unmatched files
                unmatched_files = [
                    f for f in scanner.files
                    if f.filepath not in matched_file_paths
                ]

                if on_progress:
                    on_progress(0, len(unmatched_files), "Copying unmatched files...")

                unprocessed_file_records = []
                for i, file_info in enumerate(unmatched_files):
                    if on_progress and i % 100 == 0:
                        on_progress(i, len(unmatched_files), f"Copying: {file_info.filename}")

                    dest = processor.process_unmatched_file(file_info)
                    unprocessed_file_records.append({
                        "filename": file_info.filename,
                        "filepath": file_info.filepath,
                        "procpath": dest
                    })

                result.stats = processor.stats

        # Write summary log
        end_time = time.time()
        end_date = time.strftime("%Y-%m-%d %H:%M:%S")
        result.elapsed_time = round(end_time - start_time, 3)
        result.end_time = end_date

        summary = SummaryLogger(output_dir)
        summary.write_summary(
            processed=processed_files,
            unprocessed=unprocessed_file_records,
            unprocessed_jsons=unprocessed_jsons,
            elapsed_time=result.elapsed_time,
            start_time=start_date,
            end_time=end_date
        )

        if on_progress:
            on_progress(total, total, "Processing complete")

        return result

    def extend(
        self,
        on_progress: Optional[ProgressCallback] = None
    ) -> ProcessResult:
        """Add metadata to already-processed files.

        Args:
            on_progress: Optional callback for progress updates.

        Returns:
            ProcessResult with statistics.
        """
        start_time = time.time()
        start_date = time.strftime("%Y-%m-%d %H:%M:%S")

        result = ProcessResult(
            stats=ProcessingStats(),
            output_dir=self.dest_path,
            processed_dir=os.path.join(self.dest_path, "Processed"),
            unprocessed_dir="",
            log_file="",
            elapsed_time=0,
            start_time=start_date,
            end_time=""
        )

        # Validate paths
        if not exists(self.source_path):
            result.errors.append(f"Source path does not exist: {self.source_path}")
            return result

        processed_path = result.processed_dir
        if not exists(processed_path):
            result.errors.append(f"Processed folder not found: {processed_path}")
            return result

        # Scan both directories
        if on_progress:
            on_progress(0, 100, "Scanning source...")

        source_scanner = FileScanner(self.source_path)
        source_scanner.scan()

        if on_progress:
            on_progress(0, 100, "Scanning processed files...")

        dest_scanner = FileScanner(processed_path)
        dest_scanner.scan()

        # Process
        matcher = FileMatcher(dest_scanner.file_index, self.suffixes)

        with FileProcessor(self.dest_path, write_exif=True) as processor:
            total = len(source_scanner.jsons)

            for i, json_path in enumerate(source_scanner.jsons):
                if on_progress and i % 100 == 0:
                    on_progress(i, total, f"Extending: {os.path.basename(json_path)}")

                metadata = self._read_json(json_path)
                if not metadata or (not metadata.has_location() and not metadata.has_people()):
                    result.stats.skipped += 1
                    continue

                match = matcher.find_match(json_path, metadata.title)
                if match.found:
                    for file_info in match.files:
                        if processor.extend_metadata(file_info.filepath, metadata):
                            result.stats.processed += 1
                            if metadata.has_location():
                                result.stats.with_gps += 1
                            if metadata.has_people():
                                result.stats.with_people += 1
                        else:
                            result.stats.errors += 1
                else:
                    result.stats.skipped += 1

        result.elapsed_time = round(time.time() - start_time, 3)
        result.end_time = time.strftime("%Y-%m-%d %H:%M:%S")

        if on_progress:
            on_progress(total, total, "Extend complete")

        return result

    def _read_json(self, path: str) -> Optional[JsonMetadata]:
        """Read and parse a JSON metadata file.

        Args:
            path: Path to JSON file.

        Returns:
            JsonMetadata object, or None if invalid.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)

            if not content or "title" not in content:
                return None

            if "photoTakenTime" not in content or "timestamp" not in content["photoTakenTime"]:
                return None

            return JsonMetadata(
                filepath=path,
                title=content["title"],
                date=datetime.fromtimestamp(int(content["photoTakenTime"]["timestamp"])),
                geo_data=GeoData.from_dict(content.get("geoData")),
                people=Person.from_list(content.get("people")),
                description=content.get("description", "")
            )
        except:
            return None
```

## Update `pef/core/__init__.py`

Add to exports:
```python
from pef.core.orchestrator import PEFOrchestrator, DryRunResult, ProcessResult
```

## Usage Examples

### From CLI:
```python
from pef.core.orchestrator import PEFOrchestrator
from tqdm import tqdm

def make_progress_callback(desc):
    pbar = tqdm(desc=desc)
    def callback(current, total, message):
        pbar.total = total
        pbar.n = current
        pbar.set_description(message[:40])
        pbar.refresh()
    return callback, pbar

orchestrator = PEFOrchestrator(source_path, dest_path)

# Dry run
callback, pbar = make_progress_callback("Analyzing")
result = orchestrator.dry_run(on_progress=callback)
pbar.close()
print(f"Would process: {result.matched_count}")

# Process
callback, pbar = make_progress_callback("Processing")
result = orchestrator.process(on_progress=callback)
pbar.close()
print(f"Processed: {result.stats.processed}")
```

### From GUI:
```python
def gui_callback(current, total, message):
    progress_bar['value'] = (current / total) * 100
    status_label.config(text=message)
    root.update_idletasks()

result = orchestrator.process(on_progress=gui_callback)
```

## Acceptance Criteria

1. [ ] `pef/core/orchestrator.py` exists with `PEFOrchestrator` class
2. [ ] `dry_run()` returns `DryRunResult` with all statistics
3. [ ] `process()` returns `ProcessResult` with stats and paths
4. [ ] `extend()` works for adding metadata to existing files
5. [ ] All methods accept `on_progress` callback
6. [ ] No direct printing (results returned, not printed)
7. [ ] Original `pef.py` still works unchanged

## Verification

```python
from pef.core.orchestrator import PEFOrchestrator

def progress(cur, tot, msg):
    print(f"[{cur}/{tot}] {msg}")

orch = PEFOrchestrator(
    source_path="D:/Photos/_Google Photos Backup/Google Photos",
    write_exif=False
)

# Test dry run
result = orch.dry_run(on_progress=progress)
print(f"\nDry run results:")
print(f"  JSONs: {result.json_count}")
print(f"  Files: {result.file_count}")
print(f"  Would match: {result.matched_count}")
print(f"  With GPS: {result.with_gps}")
print(f"  With people: {result.with_people}")
```

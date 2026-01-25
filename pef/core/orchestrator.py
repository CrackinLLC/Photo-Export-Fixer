"""High-level orchestrator for Photo Export Fixer.

Coordinates scanning, matching, and processing operations.
Used by both CLI and GUI.
"""

import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

# Use orjson for faster JSON parsing (3-10x faster than stdlib json)
try:
    import orjson
    _USE_ORJSON = True
except ImportError:
    import json
    _USE_ORJSON = False

from pef.core.models import (
    JsonMetadata, GeoData, Person,
    ProcessingStats, ProgressCallback, DryRunResult, ProcessRunResult
)
from pef.core.utils import exists, checkout_dir
from pef.core.scanner import FileScanner
from pef.core.matcher import FileMatcher, DEFAULT_SUFFIXES
from pef.core.processor import FileProcessor
from pef.core.logger import PEFLogger
from pef.core.exiftool import is_exiftool_available
from pef.core.state import StateManager

logger = logging.getLogger(__name__)

# Name of the metadata directory within output
PEF_DIR_NAME = "_pef"


def _adaptive_interval(total: int) -> int:
    """Calculate adaptive progress update interval based on total count.

    More frequent updates for smaller collections, less frequent for larger ones.

    Args:
        total: Total number of items to process.

    Returns:
        Update interval (report progress every N items).
    """
    if total < 50:
        return 1  # Every item for tiny collections
    elif total < 200:
        return 10
    elif total < 1000:
        return 25
    elif total < 5000:
        return 50
    else:
        return 100


class PEFOrchestrator:
    """Coordinates all Photo Export processing operations.

    Supports automatic resume: if processing is interrupted, re-running
    with the same output directory will skip already-processed files.

    Usage:
        orchestrator = PEFOrchestrator(
            source_path="/path/to/takeout",
            dest_path="/path/to/output"  # optional
        )

        # Dry run to preview
        result = orchestrator.dry_run(on_progress=my_callback)
        print(f"Would process: {result.matched_count} files")

        # Actual processing (auto-resumes if interrupted)
        result = orchestrator.process(on_progress=my_callback)
        print(f"Processed: {result.stats.processed} files")

        # Force fresh start (ignore previous progress)
        result = orchestrator.process(force=True)
    """

    def __init__(
        self,
        source_path: str,
        dest_path: Optional[str] = None,
        suffixes: Optional[List[str]] = None,
        write_exif: bool = True,
        verbose: bool = False,
        rename_mp: bool = False
    ):
        """Initialize orchestrator.

        Args:
            source_path: Path to photo export directory.
            dest_path: Output directory (default: source_path + "_processed").
            suffixes: Filename suffixes to try (default: ["", "-edited"]).
            write_exif: Whether to write EXIF metadata.
            verbose: If True, log all operations. If False, only log errors/warnings.
            rename_mp: If True, rename .MP files to .MP4 for better compatibility.
        """
        self.source_path = source_path
        self.dest_path = dest_path or f"{source_path}_processed"
        self.suffixes = suffixes or DEFAULT_SUFFIXES
        self.write_exif = write_exif
        self.verbose = verbose
        self.rename_mp = rename_mp
        self._active_state: Optional[StateManager] = None

    def save_progress(self) -> bool:
        """Save current processing progress for later resume.

        Call this on interrupt (e.g., Ctrl+C) to ensure progress is saved.

        Returns:
            True if progress was saved, False if no active processing.
        """
        if self._active_state:
            self._active_state.save()
            return True
        return False

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

        # Phase 1: Scan files
        if on_progress:
            on_progress(0, 100, "[1/3] Scanning files...")

        scanner = FileScanner(self.source_path)
        scanner.scan(on_progress)

        result.json_count = scanner.json_count
        result.file_count = scanner.file_count

        # Validate Takeout structure
        if scanner.json_count == 0:
            result.errors.append(
                "No JSON metadata files found. This may not be a valid Google Takeout directory."
            )

        # Phase 2: Read all JSONs concurrently for faster analysis
        if on_progress:
            on_progress(0, 100, "[2/3] Reading metadata...")

        json_metadata = self._read_jsons_batch(scanner.jsons)

        # Phase 3: Analyze matches
        matcher = FileMatcher(scanner.file_index, self.suffixes)

        total_jsons = len(scanner.jsons)
        interval = _adaptive_interval(total_jsons)

        for i, json_path in enumerate(scanner.jsons):
            if on_progress and i % interval == 0:
                on_progress(i, total_jsons, f"[3/3] Analyzing: {os.path.basename(json_path)}")

            metadata = json_metadata.get(json_path)
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

        result.unmatched_file_count = result.file_count - result.matched_count

        if on_progress:
            on_progress(total_jsons, total_jsons, "Analysis complete")

        return result

    def process(
        self,
        on_progress: Optional[ProgressCallback] = None,
        force: bool = False
    ) -> ProcessRunResult:
        """Run full processing with automatic resume support.

        If a previous run was interrupted, processing will automatically
        resume from where it left off (unless force=True).

        Args:
            on_progress: Optional callback for progress updates.
            force: If True, start fresh and ignore any previous progress.

        Returns:
            ProcessRunResult with statistics and paths.
        """
        start_time = time.time()
        start_date = time.strftime("%Y-%m-%d %H:%M:%S")

        # Validate source BEFORE creating output directory
        if not exists(self.source_path):
            result = ProcessRunResult(
                stats=ProcessingStats(),
                output_dir=self.dest_path,
                pef_dir="",
                summary_file="",
                elapsed_time=0,
                start_time=start_date,
                end_time=""
            )
            result.errors.append(f"Source path does not exist: {self.source_path}")
            return result

        # Check for resume before creating new directory
        # State file is now in _pef subdirectory
        potential_pef_dir = os.path.join(self.dest_path, PEF_DIR_NAME)
        state = StateManager(potential_pef_dir)
        resuming = False

        if not force and state.can_resume():
            state.load()
            # Validate source path matches
            if state.source_path == self.source_path:
                resuming = True
                output_dir = self.dest_path
                logger.info(f"Resuming: {state.processed_count} files already processed")
            else:
                logger.warning(
                    f"Source path changed (was: {state.source_path}). Starting fresh."
                )
                output_dir = checkout_dir(self.dest_path, onlynew=True)
        elif not force and state.is_completed():
            # Already completed - create new directory
            logger.info("Previous run completed. Creating new output directory.")
            output_dir = checkout_dir(self.dest_path, onlynew=True)
        else:
            # Fresh start or force
            if exists(self.dest_path) and force:
                # Force mode with existing directory - reuse it
                output_dir = self.dest_path
            else:
                output_dir = checkout_dir(self.dest_path, onlynew=True)

        # Create _pef directory for all metadata/logs
        pef_dir = os.path.join(output_dir, PEF_DIR_NAME)
        os.makedirs(pef_dir, exist_ok=True)

        result = ProcessRunResult(
            stats=ProcessingStats(),
            output_dir=output_dir,
            pef_dir=pef_dir,
            summary_file=os.path.join(pef_dir, "summary.txt"),
            elapsed_time=0,
            start_time=start_date,
            end_time=""
        )

        # Phase 1: Scan
        if on_progress:
            on_progress(0, 100, "[1/3] Scanning files...")

        scanner = FileScanner(self.source_path)
        scanner.scan()

        # Initialize or update state manager (stored in _pef for resume)
        self._active_state = StateManager(pef_dir)
        if resuming:
            self._active_state.load()
        else:
            self._active_state.create(self.source_path, len(scanner.jsons))

        # Filter to unprocessed JSONs
        jsons_to_process = self._active_state.filter_unprocessed(scanner.jsons)
        skipped_count = len(scanner.jsons) - len(jsons_to_process)

        # Populate resume info on result
        result.resumed = resuming
        result.skipped_count = skipped_count

        if skipped_count > 0 and on_progress:
            on_progress(0, 100, f"Resuming: skipping {skipped_count} already processed")

        # Phase 2: Process matched files
        processed_files = []
        unmatched_jsons = []  # JSONs that couldn't find matching files
        matched_file_paths = set()

        with PEFLogger(pef_dir, verbose=self.verbose) as pef_logger:
            if resuming:
                pef_logger.log(f"Resuming processing: {self.source_path} ({skipped_count} already done)")
            else:
                pef_logger.log(f"Started processing: {self.source_path}")

            with FileProcessor(
                output_dir,
                logger=pef_logger,
                write_exif=self.write_exif,
                verbose=self.verbose,
                rename_mp=self.rename_mp
            ) as processor:
                matcher = FileMatcher(scanner.file_index, self.suffixes)

                total = len(jsons_to_process)
                interval = _adaptive_interval(total)

                for i, json_path in enumerate(jsons_to_process):
                    if on_progress and i % interval == 0:
                        on_progress(i, total, f"[2/3] Processing: {os.path.basename(json_path)}")

                    # Periodic flush of batched metadata writes for progress visibility
                    if i > 0 and i % 500 == 0:
                        processor.flush_metadata_writes()

                    metadata = self._read_json(json_path)
                    if not metadata:
                        # Invalid JSON - still save it to unmatched_data
                        unmatched_jsons.append(json_path)
                        self._active_state.mark_processed(json_path)
                        continue

                    # Use find_all_related_files to get original AND all edited variants
                    match = matcher.find_all_related_files(json_path, metadata.title)
                    if match.found:
                        any_success = False
                        for file_info in match.files:
                            try:
                                dest = processor.process_file(file_info, metadata)
                                matched_file_paths.add(file_info.filepath)
                                processed_files.append({
                                    "filename": file_info.filename,
                                    "filepath": file_info.filepath,
                                    "output_path": dest,
                                    "json_path": json_path
                                })
                                any_success = True
                            except Exception as e:
                                result.errors.append(f"Error processing {file_info.filepath}: {e}")
                        # Count GPS/people per JSON, not per file
                        if any_success:
                            if metadata.has_location():
                                processor.stats.with_gps += 1
                            if metadata.has_people():
                                processor.stats.with_people += 1
                    else:
                        # No matching file found - save JSON to unmatched_data
                        unmatched_jsons.append(json_path)

                    # Mark this JSON as processed for resume capability
                    self._active_state.mark_processed(json_path)

                # Phase 3: Handle unmatched files (copy all, track as unprocessed)
                unmatched_files = [
                    f for f in scanner.files
                    if f.filepath not in matched_file_paths
                ]

                if on_progress:
                    on_progress(0, len(unmatched_files), "[3/3] Copying unmatched files...")

                unmatched_interval = _adaptive_interval(len(unmatched_files))

                for i, file_info in enumerate(unmatched_files):
                    if on_progress and i % unmatched_interval == 0:
                        on_progress(i, len(unmatched_files), f"[3/3] Copying: {file_info.filename}")

                    processor.copy_unmatched_file(file_info)

                result.stats = processor.stats
                result.unprocessed_items = processor.unprocessed_items
                result.motion_photo_count = len(processor.motion_photos)

                # Write unprocessed.txt and motion_photos.txt
                pef_logger.write_unprocessed(processor.unprocessed_items)
                pef_logger.write_motion_photos(processor.motion_photos)

            # Phase 4: Copy unmatched JSONs to _pef/unmatched_data/
            if unmatched_jsons:
                self._copy_unmatched_jsons(unmatched_jsons, pef_dir, on_progress)

            # Write summary
            end_time = time.time()
            end_date = time.strftime("%Y-%m-%d %H:%M:%S")
            result.elapsed_time = round(end_time - start_time, 3)
            result.end_time = end_date

            from pef.core.exiftool import get_exiftool_path
            exiftool_path = get_exiftool_path() if is_exiftool_available() else None

            pef_logger.write_summary(
                source_path=self.source_path,
                output_dir=output_dir,
                stats=result.stats,
                elapsed_time=result.elapsed_time,
                start_time=start_date,
                end_time=end_date,
                motion_photo_count=result.motion_photo_count,
                unprocessed_count=len(result.unprocessed_items),
                unmatched_json_count=len(unmatched_jsons),
                exiftool_available=is_exiftool_available(),
                exiftool_path=exiftool_path
            )

        # Mark processing as complete and clear active state
        self._active_state.complete()
        self._active_state = None

        if on_progress:
            on_progress(total, total, "Processing complete")

        return result

    def _copy_unmatched_jsons(
        self,
        json_paths: List[str],
        pef_dir: str,
        on_progress: Optional[ProgressCallback] = None
    ) -> None:
        """Copy unmatched JSON files to _pef/unmatched_data/ preserving structure.

        Args:
            json_paths: List of unmatched JSON file paths.
            pef_dir: Path to the _pef directory.
            on_progress: Optional progress callback.
        """
        unmatched_data_dir = os.path.join(pef_dir, "unmatched_data")

        for json_path in json_paths:
            # Get relative path from source to preserve structure
            try:
                rel_path = os.path.relpath(json_path, self.source_path)
            except ValueError:
                # On Windows, relpath fails across drives
                rel_path = os.path.basename(json_path)

            dest_path = os.path.join(unmatched_data_dir, rel_path)
            dest_dir = os.path.dirname(dest_path)

            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(json_path, dest_path)

    def _read_json(self, path: str) -> Optional[JsonMetadata]:
        """Read and parse a JSON metadata file.

        Args:
            path: Path to JSON file.

        Returns:
            JsonMetadata object, or None if invalid.
        """
        try:
            # Read file in binary mode for orjson compatibility
            with open(path, "rb") as f:
                raw = f.read()

            # Parse JSON using orjson (faster) or stdlib json
            if _USE_ORJSON:
                content = orjson.loads(raw)
            else:
                content = json.loads(raw.decode("utf-8"))

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
        except Exception as e:
            logger.debug(f"Error reading JSON {path}: {e}")
            return None

    # Threshold for switching from sequential to parallel JSON reading.
    # Below this, thread pool overhead outweighs benefits.
    _PARALLEL_JSON_THRESHOLD = 50

    # Default worker count for parallel JSON reading.
    # 8 threads provides good I/O overlap without excessive context switching.
    _DEFAULT_JSON_WORKERS = 8

    def _read_jsons_batch(
        self,
        paths: List[str],
        max_workers: int = _DEFAULT_JSON_WORKERS
    ) -> Dict[str, Optional[JsonMetadata]]:
        """Read multiple JSON files concurrently using thread pool.

        Uses ThreadPoolExecutor for 2-4x faster I/O on larger collections.

        Args:
            paths: List of JSON file paths to read.
            max_workers: Maximum concurrent threads (default: 8).

        Returns:
            Dict mapping path -> JsonMetadata (or None if invalid).
        """
        results: Dict[str, Optional[JsonMetadata]] = {}

        if not paths:
            return results

        # For small batches, sequential is faster due to thread overhead
        if len(paths) < self._PARALLEL_JSON_THRESHOLD:
            for path in paths:
                results[path] = self._read_json(path)
            return results

        # Use thread pool for larger batches
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self._read_json, path): path
                for path in paths
            }

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    results[path] = future.result()
                except Exception as e:
                    logger.debug(f"Thread error reading {path}: {e}")
                    results[path] = None

        return results

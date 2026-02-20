"""High-level orchestrator for Photo Export Fixer.

Coordinates scanning, matching, and processing operations.
Used by both CLI and GUI.
"""

import logging
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Tuple

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

        # Cache from dry_run for reuse in process()
        self._cached_scanner: Optional[FileScanner] = None
        self._cached_metadata: Optional[Dict[str, Optional['JsonMetadata']]] = None

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
        on_progress: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> DryRunResult:
        """Preview what would be processed without making changes.

        Args:
            on_progress: Optional callback for progress updates.
            cancel_event: Optional threading.Event for cooperative cancellation.
                When set, analysis stops and returns partial results.

        Returns:
            DryRunResult with counts and statistics.
        """
        result = DryRunResult()

        # Clear any previous cache before starting a new dry run
        self._clear_cache()

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
            on_progress(0, 100, "[1/2] Scanning files...")

        scanner = FileScanner(self.source_path)
        scanner.scan(on_progress)

        result.json_count = scanner.json_count
        result.file_count = scanner.file_count

        # Validate Takeout structure
        if scanner.json_count == 0:
            result.errors.append(
                "No JSON metadata files found. This may not be a valid Google Takeout directory."
            )

        # Phase 2: Read and analyze in chunks to bound peak memory per-chunk.
        # Metadata is accumulated across chunks for caching (~170MB at 200K files).
        # This trades higher peak memory for skipping redundant disk I/O when
        # process() is called after dry_run() (the common GUI Preview → Start flow).
        matcher = FileMatcher(scanner.file_index, self.suffixes, scanner.lowercase_index)

        total_jsons = len(scanner.jsons)
        interval = _adaptive_interval(total_jsons)
        chunk_size = self._DRY_RUN_CHUNK_SIZE
        processed = 0
        all_metadata: Dict[str, Optional[JsonMetadata]] = {}

        if on_progress:
            on_progress(0, total_jsons, "[2/2] Analyzing metadata...")

        for chunk_start in range(0, total_jsons, chunk_size):
            if cancel_event and cancel_event.is_set():
                result.cancelled = True
                if on_progress:
                    on_progress(processed, total_jsons, "Preview cancelled")
                return result

            chunk_paths = scanner.jsons[chunk_start:chunk_start + chunk_size]
            chunk_metadata = self._read_jsons_batch(chunk_paths, cancel_event=cancel_event)
            all_metadata.update(chunk_metadata)

            for json_path in chunk_paths:
                if cancel_event and cancel_event.is_set():
                    result.cancelled = True
                    if on_progress:
                        on_progress(processed, total_jsons, "Preview cancelled")
                    return result

                if on_progress and processed % interval == 0:
                    on_progress(processed, total_jsons, f"[2/2] Analyzing: {os.path.basename(json_path)}")

                metadata = chunk_metadata.get(json_path)
                if not metadata:
                    result.unmatched_json_count += 1
                    processed += 1
                    continue

                match = matcher.find_match(json_path, metadata.title)
                if match.found:
                    result.matched_count += 1
                    if metadata.has_location():
                        result.with_gps += 1
                    if metadata.has_people():
                        result.with_people += 1
                else:
                    logger.debug(
                        "No matching media file for Takeout JSON (title=%s): %s",
                        metadata.title, json_path
                    )
                    result.unmatched_json_count += 1

                processed += 1

        result.unmatched_file_count = result.file_count - result.matched_count

        if on_progress:
            on_progress(total_jsons, total_jsons, "Analysis complete")

        # Cache scanner and metadata for reuse in process()
        self._cached_scanner = scanner
        self._cached_metadata = all_metadata

        return result

    def process(
        self,
        on_progress: Optional[ProgressCallback] = None,
        force: bool = False,
        cancel_event: Optional[threading.Event] = None
    ) -> ProcessRunResult:
        """Run full processing with automatic resume support.

        If a previous run was interrupted, processing will automatically
        resume from where it left off (unless force=True).

        Args:
            on_progress: Optional callback for progress updates.
            force: If True, start fresh and ignore any previous progress.
            cancel_event: Optional threading.Event for cooperative cancellation.
                When set, processing saves progress and returns early.

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
            # Fresh start or force — no prior state file exists
            # Use checkout_dir for both cases: it creates missing dirs
            # and raises ValueError if path exists as a file
            output_dir = checkout_dir(self.dest_path)

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

        # Phase 1: Scan (skip if cached from dry_run)
        use_cache = self._cached_scanner is not None
        if use_cache:
            scanner = self._cached_scanner
            cached_metadata = self._cached_metadata
            if on_progress:
                on_progress(0, 0, "[1/3] Using cached scan results...")
            logger.info("Using cached scanner from preview (%d files, %d JSONs)",
                        scanner.file_count, scanner.json_count)
        else:
            cached_metadata = None
            if on_progress:
                on_progress(0, 0, "[1/3] Scanning files...")

            def scan_progress(current, total, message):
                if on_progress:
                    on_progress(current, 0, f"[1/3] {message}")

            scanner = FileScanner(self.source_path)
            scanner.scan(on_progress=scan_progress if on_progress else None)

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
                rename_mp=self.rename_mp,
                cancel_event=cancel_event
            ) as processor:
                if processor.exiftool_error:
                    result.errors.append(f"ExifTool: {processor.exiftool_error}")
                matcher = FileMatcher(scanner.file_index, self.suffixes, scanner.lowercase_index)

                total = len(jsons_to_process)
                interval = _adaptive_interval(total)

                # Choose metadata source: cached dict or pipelined disk reads
                if cached_metadata is not None:
                    logger.info("Using cached metadata from preview")
                    metadata_iter = self._iter_cached_metadata(
                        jsons_to_process, cached_metadata
                    )
                else:
                    metadata_iter = self._iter_pipelined_metadata(
                        jsons_to_process, cancel_event
                    )

                # Unified processing loop — metadata source is abstracted
                for i, json_path, metadata in metadata_iter:
                    if cancel_event and cancel_event.is_set():
                        self._active_state.save()
                        result.cancelled = True
                        if on_progress:
                            on_progress(i, total, "Cancelled — saving progress")
                        break

                    if on_progress and i % interval == 0:
                        on_progress(i, total, f"[2/3] Processing: {os.path.basename(json_path)}")

                    if i > 0 and i % 500 == 0:
                        processor.flush_metadata_writes()

                    if not metadata:
                        unmatched_jsons.append(json_path)
                        self._active_state.mark_processed(json_path)
                        continue

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
                        if any_success:
                            if metadata.has_location():
                                processor.stats.with_gps += 1
                            if metadata.has_people():
                                processor.stats.with_people += 1
                    else:
                        logger.debug(
                            "No matching media file for Takeout JSON (title=%s): %s",
                            metadata.title, json_path
                        )
                        unmatched_jsons.append(json_path)

                    self._active_state.mark_processed(json_path)

                # Phase 3: Handle unmatched files (copy all, track as unprocessed)
                unmatched_files = [
                    f for f in scanner.files
                    if f.filepath not in matched_file_paths
                ]

                if not result.cancelled and on_progress:
                    on_progress(0, len(unmatched_files), "[3/3] Copying unmatched files...")

                unmatched_interval = _adaptive_interval(len(unmatched_files))

                for i, file_info in enumerate(unmatched_files):
                    if cancel_event and cancel_event.is_set():
                        self._active_state.save()
                        result.cancelled = True
                        if on_progress:
                            on_progress(i, len(unmatched_files), "Cancelled — saving progress")
                        break

                    if on_progress and i % unmatched_interval == 0:
                        on_progress(i, len(unmatched_files), f"[3/3] Copying: {file_info.filename}")

                    try:
                        processor.copy_unmatched_file(file_info)
                    except Exception as e:
                        logger.warning(f"Failed to copy unmatched file {file_info.filepath}: {e}")
                        result.errors.append(f"Error copying {file_info.filepath}: {e}")

                result.stats = processor.stats
                result.unprocessed_items = processor.unprocessed_items
                result.motion_photo_count = len(processor.motion_photos)

                # Write unprocessed.txt and motion_photos.txt
                pef_logger.write_unprocessed(processor.unprocessed_items)
                pef_logger.write_motion_photos(processor.motion_photos)

            # Skip remaining phases if cancelled
            if result.cancelled:
                end_time = time.time()
                result.elapsed_time = round(end_time - start_time, 3)
                result.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
                self._active_state = None
                self._clear_cache()
                return result

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

        # Clear cache after processing completes (no stale data for next run)
        self._clear_cache()

        if on_progress:
            on_progress(total, total, "Processing complete")

        return result

    def _clear_cache(self) -> None:
        """Clear cached scanner and metadata from dry_run."""
        self._cached_scanner = None
        self._cached_metadata = None

    def _iter_cached_metadata(
        self,
        json_paths: List[str],
        cached: Dict[str, Optional[JsonMetadata]]
    ) -> Iterator[Tuple[int, str, Optional[JsonMetadata]]]:
        """Yield (index, json_path, metadata) from cached dict."""
        for i, json_path in enumerate(json_paths):
            yield i, json_path, cached.get(json_path)

    def _iter_pipelined_metadata(
        self,
        json_paths: List[str],
        cancel_event: Optional[threading.Event] = None
    ) -> Iterator[Tuple[int, str, Optional[JsonMetadata]]]:
        """Yield (index, json_path, metadata) using pipelined disk reads.

        Pre-reads the next batch while the caller processes the current one,
        overlapping I/O with processing for better throughput.
        """
        batch_size = self._PIPELINE_BATCH_SIZE

        with ThreadPoolExecutor(max_workers=1) as pipeline_executor:
            prefetch_future = None

            # Kick off pre-read of first batch
            first_batch = json_paths[:batch_size]
            if first_batch:
                prefetch_future = pipeline_executor.submit(
                    self._read_jsons_batch, first_batch,
                    self._DEFAULT_JSON_WORKERS, cancel_event
                )

            current_batch_metadata: Dict[str, Optional[JsonMetadata]] = {}

            for i, json_path in enumerate(json_paths):
                # At each batch boundary, collect pre-read results and
                # kick off pre-read of the next batch
                if i % batch_size == 0:
                    # Collect the pre-read batch, using timeout to allow
                    # cancel checks if the prefetch is slow
                    if prefetch_future is not None:
                        while True:
                            try:
                                current_batch_metadata = prefetch_future.result(timeout=1.0)
                                break
                            except TimeoutError:
                                if cancel_event and cancel_event.is_set():
                                    current_batch_metadata = {}
                                    break
                                continue
                            except Exception:
                                current_batch_metadata = {}
                                break
                    else:
                        current_batch_metadata = {}

                    # Start pre-reading the next batch
                    next_start = i + batch_size
                    if next_start < len(json_paths):
                        next_batch = json_paths[next_start:next_start + batch_size]
                        prefetch_future = pipeline_executor.submit(
                            self._read_jsons_batch, next_batch,
                            self._DEFAULT_JSON_WORKERS, cancel_event
                        )
                    else:
                        prefetch_future = None

                yield i, json_path, current_batch_metadata.get(json_path)

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
            try:
                shutil.copy(json_path, dest_path)
            except OSError as e:
                logger.warning(f"Failed to copy unmatched JSON {json_path}: {e}")

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
                logger.debug(
                    "Skipping non-Takeout JSON (missing 'title' field): %s", path
                )
                return None

            if "photoTakenTime" not in content or "timestamp" not in content["photoTakenTime"]:
                logger.debug(
                    "Skipping non-Takeout JSON (missing 'photoTakenTime.timestamp'): %s", path
                )
                return None

            # Timestamp conversion: Google Takeout stores photoTakenTime as a UTC
            # epoch (seconds since 1970-01-01 00:00:00 UTC). We convert to local time
            # using datetime.fromtimestamp(), which applies the system's local timezone.
            # This means the same export processed in different timezones will produce
            # different dates. This is intentional: users expect file dates to match
            # their local clock at the time the photo was taken. For UTC-consistent
            # dates, use datetime.fromtimestamp(ts, tz=timezone.utc) instead.
            return JsonMetadata(
                filepath=path,
                title=content["title"],
                date=datetime.fromtimestamp(int(content["photoTakenTime"]["timestamp"])),
                geo_data=GeoData.from_dict(content.get("geoData")),
                people=Person.from_list(content.get("people")),
                description=content.get("description", "")
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.debug("Invalid/corrupt JSON %s: %s", path, e)
            return None
        except Exception as e:
            logger.debug("Error reading JSON %s: %s", path, e)
            return None

    # Threshold for switching from sequential to parallel JSON reading.
    # Below this, thread pool overhead outweighs benefits.
    _PARALLEL_JSON_THRESHOLD = 50

    # Default worker count for parallel JSON reading.
    # 8 threads provides good I/O overlap without excessive context switching.
    _DEFAULT_JSON_WORKERS = 8

    # Chunk size for streaming dry_run analysis.
    # Read this many JSONs at a time, then discard before reading next chunk.
    # Keeps peak memory bounded regardless of export size.
    _DRY_RUN_CHUNK_SIZE = 1000

    # Batch size for pipelined JSON pre-reading in process().
    # Pre-reads the next batch while processing the current one.
    _PIPELINE_BATCH_SIZE = 500

    def _read_jsons_batch(
        self,
        paths: List[str],
        max_workers: int = _DEFAULT_JSON_WORKERS,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Optional[JsonMetadata]]:
        """Read multiple JSON files concurrently using thread pool.

        Uses ThreadPoolExecutor for 2-4x faster I/O on larger collections.

        Args:
            paths: List of JSON file paths to read.
            max_workers: Maximum concurrent threads (default: 8).
            cancel_event: Optional threading.Event for cooperative cancellation.

        Returns:
            Dict mapping path -> JsonMetadata (or None if invalid).
        """
        results: Dict[str, Optional[JsonMetadata]] = {}

        if not paths:
            return results

        # For small batches, sequential is faster due to thread overhead
        if len(paths) < self._PARALLEL_JSON_THRESHOLD:
            for path in paths:
                if cancel_event and cancel_event.is_set():
                    break
                results[path] = self._read_json(path)
            return results

        # Use thread pool for larger batches
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self._read_json, path): path
                for path in paths
            }

            for future in as_completed(future_to_path):
                if cancel_event and cancel_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                path = future_to_path[future]
                try:
                    results[path] = future.result()
                except Exception as e:
                    logger.debug(f"Thread error reading {path}: {e}")
                    results[path] = None

        return results

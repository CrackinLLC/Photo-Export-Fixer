"""File processing operations for Photo Export Fixer.

Handles copying, date modification, and metadata writing.
"""

import logging
import os
import shutil
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import filedate

logger = logging.getLogger(__name__)

from pef.core.models import FileInfo, JsonMetadata, ProcessingStats, ProgressCallback
from pef.core.utils import checkout_dir, get_unique_path
from pef.core.metadata import build_gps_tags, build_people_tags
from pef.core.logger import BufferedLogger
from pef.core.exiftool import ExifToolManager


class FileProcessor:
    """Processes files by copying, setting dates, and writing metadata.

    Supports batch metadata writing for improved performance (10-50x faster).
    Supports parallel file copying for I/O-bound speedup.

    Usage:
        with FileProcessor(output_dir) as processor:
            for file, metadata in matches:
                processor.process_file(file, metadata)
            processor.copy_unmatched_files(unmatched_files)
            # Remaining writes flushed automatically on exit

        print(processor.stats)
    """

    DEFAULT_BATCH_SIZE = 100
    DEFAULT_COPY_WORKERS = 4

    def __init__(
        self,
        output_dir: str,
        logger: Optional[BufferedLogger] = None,
        write_exif: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        verbose: bool = False,
        copy_workers: int = DEFAULT_COPY_WORKERS
    ):
        """Initialize processor.

        Args:
            output_dir: Root output directory.
            logger: Optional logger for detailed logging.
            write_exif: Whether to write EXIF metadata (default True).
            batch_size: Number of files to batch for metadata writing (default 100).
            verbose: If True, log all operations. If False, only log errors/warnings.
            copy_workers: Number of parallel workers for file copying (default 4).
        """
        self.output_dir = output_dir
        self.processed_dir = os.path.join(output_dir, "Processed")
        self.unprocessed_dir = os.path.join(output_dir, "Unprocessed")
        self.logger = logger
        self.write_exif = write_exif
        self.verbose = verbose
        self.stats = ProcessingStats()

        self._exiftool: Optional[ExifToolManager] = None
        self._pending_writes: List[Tuple[str, dict]] = []
        self._batch_size = batch_size
        self._copy_workers = copy_workers

    def start(self) -> None:
        """Start the processor (initialize ExifTool if needed)."""
        if self.write_exif:
            self._exiftool = ExifToolManager()
            if not self._exiftool.start():
                self._exiftool = None
                self.write_exif = False

    def stop(self) -> None:
        """Stop the processor (cleanup ExifTool)."""
        if self._exiftool:
            self._exiftool.stop()
            self._exiftool = None

    def __enter__(self) -> "FileProcessor":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - flush pending writes before stopping."""
        self.flush_metadata_writes()
        self.stop()

    def _build_tags(self, metadata: JsonMetadata) -> dict:
        """Build EXIF tags dict from metadata.

        Args:
            metadata: JSON metadata to convert.

        Returns:
            Dict of ExifTool tags, empty if no metadata to write.
        """
        tags = {}

        if metadata.geo_data:
            tags.update(build_gps_tags(metadata.geo_data))

        if metadata.people:
            tags.update(build_people_tags(metadata.people))

        return tags

    def queue_metadata_write(self, filepath: str, tags: dict) -> None:
        """Queue a metadata write for batch processing.

        When the queue reaches batch_size, it automatically flushes.

        Args:
            filepath: Path to file.
            tags: Dict of ExifTool tags to write.
        """
        if not tags:
            return

        self._pending_writes.append((filepath, tags))

        if len(self._pending_writes) >= self._batch_size:
            self.flush_metadata_writes()

    def flush_metadata_writes(self) -> int:
        """Flush all pending metadata writes as a batch.

        Returns:
            Number of files successfully written.
        """
        if not self._pending_writes:
            return 0

        if not self._exiftool:
            # ExifTool not available - clear queue and count as errors
            error_count = len(self._pending_writes)
            self.stats.errors += error_count
            if self.logger:
                self.logger.log(f"ExifTool unavailable, {error_count} metadata writes skipped")
            self._pending_writes = []
            return 0

        # Take ownership of pending writes to avoid issues if callback queues more
        batch = self._pending_writes
        self._pending_writes = []

        if self.logger and self.verbose:
            self.logger.log(f"Flushing batch of {len(batch)} metadata writes...")

        results = self._exiftool.write_tags_batch(batch)

        # Track errors with file paths for debugging
        errors = 0
        for i, success in enumerate(results):
            if not success:
                errors += 1
                filepath = batch[i][0] if i < len(batch) else "unknown"
                logger.debug(f"Metadata write failed for: {filepath}")

        successes = len(results) - errors

        if errors > 0:
            self.stats.errors += errors
            if self.logger:
                self.logger.log(f"Batch write: {successes} succeeded, {errors} failed")

        return successes

    @property
    def pending_writes_count(self) -> int:
        """Number of metadata writes pending in the batch queue."""
        return len(self._pending_writes)

    def process_file(
        self,
        file: FileInfo,
        metadata: JsonMetadata
    ) -> str:
        """Copy a file, set its dates, and write metadata.

        Args:
            file: Source file info. Note: This object is mutated to set
                  procpath and jsonpath attributes.
            metadata: JSON metadata for this file.

        Returns:
            Path to the processed file.
        """
        # Create album directory
        album_dir = checkout_dir(os.path.join(self.processed_dir, file.album_name))

        # Get unique destination path
        dest_path = get_unique_path(os.path.join(album_dir, file.filename))

        # Copy file
        if self.logger and self.verbose:
            self.logger.log(f"Copying: {file.filepath} -> {dest_path}")
        shutil.copy(file.filepath, dest_path)

        # Set file dates
        try:
            filedate.File(dest_path).set(created=metadata.date, modified=metadata.date)
        except Exception as e:
            if self.logger:
                self.logger.log(f"Warning: Could not set file dates on {dest_path}: {e}")

        # Queue EXIF metadata write (batched for performance)
        if self._exiftool and self.write_exif:
            tags = self._build_tags(metadata)
            if tags:
                self.queue_metadata_write(dest_path, tags)

        # Update file info
        file.output_path = dest_path
        file.json_path = metadata.filepath

        # Update stats (GPS/people counted per JSON by orchestrator)
        self.stats.processed += 1

        if self.logger and self.verbose:
            self.logger.log(f"Processed: {file.filename}")

        return dest_path

    def _copy_and_set_date(
        self,
        src_path: str,
        dest_path: str,
        date: datetime
    ) -> Tuple[str, Optional[str]]:
        """Copy a file and set its dates (for parallel execution).

        Args:
            src_path: Source file path.
            dest_path: Destination file path.
            date: Date to set on the file.

        Returns:
            Tuple of (dest_path, error_message or None).
        """
        try:
            shutil.copy(src_path, dest_path)
            try:
                filedate.File(dest_path).set(created=date, modified=date)
            except Exception as e:
                # Date setting failure is non-fatal
                return (dest_path, f"Warning: Could not set dates: {e}")
            return (dest_path, None)
        except Exception as e:
            return (dest_path, f"Error: {e}")

    def process_files_batch(
        self,
        files_with_metadata: List[Tuple[FileInfo, JsonMetadata]]
    ) -> List[Tuple[FileInfo, str, Optional[str]]]:
        """Process multiple files with parallel copying.

        Args:
            files_with_metadata: List of (FileInfo, JsonMetadata) tuples.

        Returns:
            List of (FileInfo, dest_path, error_or_none) tuples.
        """
        if not files_with_metadata:
            return []

        # Prepare all destinations and tasks
        tasks = []
        for file, metadata in files_with_metadata:
            album_dir = checkout_dir(os.path.join(self.processed_dir, file.album_name))
            dest_path = get_unique_path(os.path.join(album_dir, file.filename))
            tasks.append((file, metadata, dest_path))

        results = []

        # Use ThreadPoolExecutor for parallel copying
        with ThreadPoolExecutor(max_workers=self._copy_workers) as executor:
            # Submit all copy jobs
            future_to_task = {
                executor.submit(
                    self._copy_and_set_date,
                    task[0].filepath,  # file.filepath
                    task[2],           # dest_path
                    task[1].date       # metadata.date
                ): task
                for task in tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                file, metadata, dest_path = future_to_task[future]
                try:
                    _, error = future.result()

                    if error and self.logger:
                        self.logger.log(f"{error} for {dest_path}")

                    # Update file info
                    file.output_path = dest_path
                    file.json_path = metadata.filepath

                    # Queue metadata write
                    if self._exiftool and self.write_exif and not error:
                        tags = self._build_tags(metadata)
                        if tags:
                            self.queue_metadata_write(dest_path, tags)

                    self.stats.processed += 1
                    results.append((file, dest_path, error))

                except Exception as e:
                    error_msg = f"Error processing {file.filepath}: {e}"
                    if self.logger:
                        self.logger.log(error_msg)
                    results.append((file, dest_path, error_msg))

        return results

    def _write_metadata(self, filepath: str, metadata: JsonMetadata) -> bool:
        """Write EXIF metadata to a file immediately (not batched).

        For bulk processing, use queue_metadata_write() instead.

        Args:
            filepath: Path to file.
            metadata: Metadata to write.

        Returns:
            True if successful.
        """
        tags = self._build_tags(metadata)

        if not tags:
            return True

        try:
            return self._exiftool.write_tags(filepath, tags)
        except Exception as e:
            if self.logger:
                self.logger.log(f"Warning: Could not write metadata to {filepath}: {e}")
            self.stats.errors += 1
            return False

    def copy_unmatched_file(self, file: FileInfo) -> str:
        """Copy an unmatched file to Unprocessed folder.

        Args:
            file: File to copy.

        Returns:
            Path to copied file.
        """
        # Create Unprocessed directory
        checkout_dir(self.unprocessed_dir)

        # Get unique destination path
        dest_path = get_unique_path(os.path.join(self.unprocessed_dir, file.filename))

        # Copy file
        if self.logger and self.verbose:
            self.logger.log(f"Copying unprocessed: {file.filepath}")
        shutil.copy(file.filepath, dest_path)

        file.output_path = dest_path
        self.stats.unmatched_files += 1

        return dest_path

    def copy_unmatched_files(
        self,
        files: List[FileInfo],
        on_progress: Optional[ProgressCallback] = None
    ) -> List[FileInfo]:
        """Copy all unmatched files to Unprocessed folder.

        Args:
            files: List of unmatched files.
            on_progress: Optional progress callback.

        Returns:
            List of files with output_path set.
        """
        total = len(files)

        for i, file in enumerate(files):
            self.copy_unmatched_file(file)

            if on_progress:
                on_progress(i + 1, total, f"Copying: {file.filename}")

        return files


# Backwards-compatible function (deprecated)
def copy_modify(
    file: dict,
    date: datetime,
    copyto: str,
    geo_data: Optional[Dict[str, Any]] = None,
    people: Optional[List[Dict[str, Any]]] = None,
    exiftool_helper: Optional[Any] = None
) -> str:
    """Copy and modify a file (backwards compatible).

    .. deprecated::
        Use FileProcessor.process_file() instead.

    Args:
        file: Dict with filename, filepath, albumname keys.
        date: Date to set on file.
        copyto: Destination directory.
        geo_data: Optional Google geoData dict.
        people: Optional Google people list.
        exiftool_helper: Optional ExifToolHelper instance.

    Returns:
        Path to copied file.
    """
    warnings.warn(
        "copy_modify() is deprecated. Use FileProcessor.process_file() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    from pef.core.metadata import build_gps_tags_from_dict, build_people_tags_from_list

    # Create album directory (support both old and new attribute names)
    album_name = file.get("album_name") or file.get("albumname")
    album_dir = checkout_dir(os.path.join(copyto, album_name))

    # Get unique destination path
    dest_path = get_unique_path(os.path.join(album_dir, file["filename"]))

    # Copy file
    shutil.copy(file["filepath"], dest_path)

    # Set file dates
    try:
        filedate.File(dest_path).set(created=date, modified=date)
    except Exception:
        pass  # Continue processing even if date setting fails

    # Write EXIF metadata
    if exiftool_helper:
        tags = {}
        tags.update(build_gps_tags_from_dict(geo_data))
        tags.update(build_people_tags_from_list(people))

        if tags:
            try:
                exiftool_helper.set_tags(dest_path, tags)
            except Exception as e:
                logger.debug(f"Failed to write EXIF to {dest_path}: {e}")

    return dest_path

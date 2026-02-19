"""File processing operations for Photo Export Fixer.

Handles copying, date modification, and metadata writing.
"""

import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import filedate

from pef.core.models import FileInfo, JsonMetadata, ProcessingStats, ProgressCallback, UnprocessedItem, MotionPhotoInfo
from pef.core.utils import checkout_dir, get_unique_path
from pef.core.metadata import build_gps_tags, build_people_tags
from pef.core.logger import BufferedLogger
from pef.core.exiftool import ExifToolManager

logger = logging.getLogger(__name__)

# Motion photo extensions
MOTION_PHOTO_EXTENSIONS = {".mp", ".mp~2"}


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

    # Number of metadata writes to batch before flushing to ExifTool.
    # Higher values reduce process overhead but increase memory usage and
    # delay between copy and metadata write.
    DEFAULT_BATCH_SIZE = 100

    # Number of parallel workers for file copying.
    # 4 workers provides good I/O overlap on SSDs without overwhelming the disk.
    DEFAULT_COPY_WORKERS = 4

    def __init__(
        self,
        output_dir: str,
        logger: Optional[BufferedLogger] = None,
        write_exif: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        verbose: bool = False,
        copy_workers: int = DEFAULT_COPY_WORKERS,
        rename_mp: bool = False
    ):
        """Initialize processor.

        Args:
            output_dir: Root output directory. Files are copied here mirroring
                       the source directory structure.
            logger: Optional logger for detailed logging.
            write_exif: Whether to write EXIF metadata (default True).
            batch_size: Number of files to batch for metadata writing (default 100).
            verbose: If True, log all operations. If False, only log errors/warnings.
            copy_workers: Number of parallel workers for file copying (default 4).
            rename_mp: If True, rename .MP files to .MP4 for better compatibility.
        """
        self.output_dir = output_dir
        self.logger = logger
        self.write_exif = write_exif
        self.verbose = verbose
        self.rename_mp = rename_mp
        self.stats = ProcessingStats()

        # Track unprocessed files and motion photos
        self.unprocessed_items: List[UnprocessedItem] = []
        self.motion_photos: List[MotionPhotoInfo] = []

        self._exiftool: Optional[ExifToolManager] = None
        self._pending_writes: List[Tuple[str, Dict[str, Any]]] = []
        self._batch_size = batch_size
        self._copy_workers = copy_workers

        # Cache for created directories (avoids redundant os.makedirs calls)
        self._created_dirs: set = set()

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

    def _get_album_dir(self, album_name: str) -> str:
        """Get album directory path, creating it if needed.

        Uses caching to avoid redundant os.makedirs() calls.

        Args:
            album_name: Name of the album (folder).

        Returns:
            Path to the album directory.
        """
        album_dir = os.path.join(self.output_dir, album_name)
        if album_dir not in self._created_dirs:
            checkout_dir(album_dir)
            self._created_dirs.add(album_dir)
        return album_dir

    def _build_tags(self, metadata: JsonMetadata) -> Dict[str, Any]:
        """Build EXIF tags dict from metadata.

        Args:
            metadata: JSON metadata to convert.

        Returns:
            Dict of ExifTool tags, empty if no metadata to write.
        """
        # Early return if no metadata to write
        if not metadata.geo_data and not metadata.people:
            return {}

        tags = {}

        if metadata.geo_data:
            tags.update(build_gps_tags(metadata.geo_data))

        if metadata.people:
            tags.update(build_people_tags(metadata.people))

        return tags

    def queue_metadata_write(self, filepath: str, tags: Dict[str, Any]) -> None:
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
                logger.warning(f"Metadata write failed for: {filepath}")

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

        Files are copied to output_dir preserving album structure at root.
        (e.g., output_dir/AlbumName/photo.jpg)

        Args:
            file: Source file info. Note: This object is mutated to set
                  output_path and json_path attributes.
            metadata: JSON metadata for this file.

        Returns:
            Path to the processed file.
        """
        # Create album directory directly under output_dir (no /Processed subdir)
        album_dir = self._get_album_dir(file.album_name)

        # Get unique destination path
        dest_path = get_unique_path(os.path.join(album_dir, file.filename))

        # Copy file
        if self.logger and self.verbose:
            self.logger.log(f"Copying: {file.filepath} -> {dest_path}")
        try:
            shutil.copy(file.filepath, dest_path)
        except OSError as e:
            logger.warning(f"Failed to copy {file.filepath}: {e}")
            if self.logger:
                self.logger.log(f"Error: Failed to copy {file.filepath}: {e}")
            self.stats.errors += 1
            return ""

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
            album_dir = self._get_album_dir(file.album_name)
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

            # Collect results as they complete.
            # Thread safety note: stats mutations (processed, errors) and
            # metadata queue writes happen here in the main thread's
            # as_completed() loop, NOT inside worker threads. Workers only
            # perform I/O (copy + date set) and return results. This means
            # no locking is needed for shared state — the main thread is
            # the sole writer.
            for future in as_completed(future_to_task):
                file, metadata, dest_path = future_to_task[future]
                try:
                    _, error = future.result()

                    if error and error.startswith("Error:"):
                        # Copy failed - track as error
                        if self.logger:
                            self.logger.log(f"{error} for {file.filepath}")
                        self.stats.errors += 1
                        results.append((file, dest_path, error))
                        continue

                    if error and self.logger:
                        # Warning (e.g., date set failed) - non-fatal
                        self.logger.log(f"{error} for {dest_path}")

                    # Copy succeeded - update file info
                    file.output_path = dest_path
                    file.json_path = metadata.filepath

                    # Queue metadata write
                    if self._exiftool and self.write_exif:
                        tags = self._build_tags(metadata)
                        if tags:
                            self.queue_metadata_write(dest_path, tags)

                    self.stats.processed += 1
                    results.append((file, dest_path, error))

                except Exception as e:
                    error_msg = f"Error: {e}"
                    if self.logger:
                        self.logger.log(f"{error_msg} for {file.filepath}")
                    self.stats.errors += 1
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

    def copy_unmatched_file(self, file: FileInfo, reason: str = "No matching JSON found") -> str:
        """Copy an unmatched file preserving album structure.

        Files without metadata are still copied to the output directory,
        maintaining the same album/folder structure as processed files.
        They are tracked in the unprocessed_items list for logging.

        Args:
            file: File to copy.
            reason: Reason why this file wasn't processed.

        Returns:
            Path to copied file.
        """
        # Create album directory under output_dir (same structure as processed)
        album_dir = self._get_album_dir(file.album_name)

        # Check if this is a motion photo sidecar
        ext_lower = os.path.splitext(file.filename)[1].lower()
        is_motion_photo = ext_lower in MOTION_PHOTO_EXTENSIONS

        # Determine destination filename (optionally rename .MP to .MP4)
        dest_filename = file.filename
        if is_motion_photo and self.rename_mp:
            # Rename .MP or .MP~2 to .MP4
            base = os.path.splitext(file.filename)[0]
            dest_filename = base + ".MP4"

        # Get unique destination path
        dest_path = get_unique_path(os.path.join(album_dir, dest_filename))

        # Copy file
        if self.logger and self.verbose:
            self.logger.log(f"Copying unprocessed: {file.filepath}")
        try:
            shutil.copy(file.filepath, dest_path)
        except OSError as e:
            logger.warning(f"Failed to copy unmatched file {file.filepath}: {e}")
            if self.logger:
                self.logger.log(f"Error: Failed to copy unmatched file {file.filepath}: {e}")
            self.stats.errors += 1
            return ""

        file.output_path = dest_path
        self.stats.unmatched_files += 1

        # Track this as unprocessed
        relative_path = os.path.join(file.album_name, dest_filename)
        self.unprocessed_items.append(UnprocessedItem(
            relative_path=relative_path,
            reason=reason,
            source_path=file.filepath
        ))

        # Track motion photos separately
        if is_motion_photo:
            # Try to find the parent image name (e.g., photo.jpg from photo.jpg.MP)
            parent_image = file.filename
            if parent_image.lower().endswith(".mp"):
                parent_image = parent_image[:-3]  # Remove .MP
            elif parent_image.lower().endswith(".mp~2"):
                parent_image = parent_image[:-5]  # Remove .MP~2

            self.motion_photos.append(MotionPhotoInfo(
                relative_path=relative_path,
                parent_image=parent_image,
                extension=ext_lower
            ))

        return dest_path

    def copy_unmatched_files(
        self,
        files: List[FileInfo],
        on_progress: Optional[ProgressCallback] = None
    ) -> List[FileInfo]:
        """Copy all unmatched files preserving album structure.

        Args:
            files: List of unmatched files.
            on_progress: Optional progress callback.

        Returns:
            List of files with output_path set.
        """
        total = len(files)

        for i, file in enumerate(files):
            # Determine reason based on file type
            ext_lower = os.path.splitext(file.filename)[1].lower()
            if ext_lower in MOTION_PHOTO_EXTENSIONS:
                reason = f"Motion photo sidecar (parent: {file.filename.rsplit('.', 1)[0]})"
            else:
                reason = "No matching JSON found"

            self.copy_unmatched_file(file, reason=reason)

            if on_progress:
                on_progress(i + 1, total, f"Copying: {file.filename}")

        return files

    def copy_unmatched_files_parallel(
        self,
        files: List[FileInfo],
        on_progress: Optional[ProgressCallback] = None
    ) -> List[Tuple[FileInfo, str, Optional[str]]]:
        """Copy unmatched files in parallel preserving album structure.

        Destinations are prepared sequentially (for path uniqueness safety),
        then files are copied in parallel using ThreadPoolExecutor.

        Args:
            files: List of unmatched files.
            on_progress: Optional progress callback.

        Returns:
            List of (FileInfo, dest_path, error_or_none) tuples.
        """
        if not files:
            return []

        # Prepare destinations sequentially (get_unique_path needs sequential access)
        tasks = []
        for file in files:
            album_dir = self._get_album_dir(file.album_name)
            ext_lower = os.path.splitext(file.filename)[1].lower()
            is_motion_photo = ext_lower in MOTION_PHOTO_EXTENSIONS

            dest_filename = file.filename
            if is_motion_photo and self.rename_mp:
                base = os.path.splitext(file.filename)[0]
                dest_filename = base + ".MP4"

            dest_path = get_unique_path(os.path.join(album_dir, dest_filename))
            tasks.append((file, dest_path, dest_filename, is_motion_photo, ext_lower))

        results = []
        completed = 0
        total = len(tasks)

        # Copy in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self._copy_workers) as executor:
            future_to_task = {
                executor.submit(shutil.copy, task[0].filepath, task[1]): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                file, dest_path, dest_filename, is_motion_photo, ext_lower = future_to_task[future]
                try:
                    future.result()

                    # Copy succeeded - update tracking (main thread only)
                    file.output_path = dest_path
                    self.stats.unmatched_files += 1

                    relative_path = os.path.join(file.album_name, dest_filename)

                    # Determine reason and track
                    if is_motion_photo:
                        parent_image = file.filename
                        if parent_image.lower().endswith(".mp"):
                            parent_image = parent_image[:-3]
                        elif parent_image.lower().endswith(".mp~2"):
                            parent_image = parent_image[:-5]

                        reason = f"Motion photo sidecar (parent: {parent_image})"
                        self.motion_photos.append(MotionPhotoInfo(
                            relative_path=relative_path,
                            parent_image=parent_image,
                            extension=ext_lower
                        ))
                    else:
                        reason = "No matching JSON found"

                    self.unprocessed_items.append(UnprocessedItem(
                        relative_path=relative_path,
                        reason=reason,
                        source_path=file.filepath
                    ))

                    if self.logger and self.verbose:
                        self.logger.log(f"Copying unprocessed: {file.filepath}")

                    results.append((file, dest_path, None))

                except OSError as e:
                    logger.warning(f"Failed to copy unmatched file {file.filepath}: {e}")
                    if self.logger:
                        self.logger.log(f"Error: Failed to copy unmatched file {file.filepath}: {e}")
                    self.stats.errors += 1
                    results.append((file, "", str(e)))

                completed += 1
                if on_progress:
                    on_progress(completed, total, f"Copying: {file.filename}")

        return results

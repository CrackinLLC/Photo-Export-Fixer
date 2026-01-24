"""File processing operations for Photo Export Fixer.

Handles copying, date modification, and metadata writing.
"""

import logging
import os
import shutil
import warnings
from datetime import datetime
from typing import Optional, List, Any

import filedate

logger = logging.getLogger(__name__)

from pef.core.models import FileInfo, JsonMetadata, ProcessingStats, ProgressCallback
from pef.core.utils import checkout_dir, get_unique_path
from pef.core.metadata import build_gps_tags, build_people_tags
from pef.core.logger import BufferedLogger
from pef.core.exiftool import ExifToolManager


class FileProcessor:
    """Processes files by copying, setting dates, and writing metadata.

    Usage:
        with FileProcessor(output_dir) as processor:
            for file, metadata in matches:
                processor.process_file(file, metadata)
            processor.process_unmatched(unmatched_files)

        print(processor.stats)
    """

    def __init__(
        self,
        output_dir: str,
        logger: Optional[BufferedLogger] = None,
        write_exif: bool = True
    ):
        """Initialize processor.

        Args:
            output_dir: Root output directory.
            logger: Optional logger for detailed logging.
            write_exif: Whether to write EXIF metadata (default True).
        """
        self.output_dir = output_dir
        self.processed_dir = os.path.join(output_dir, "Processed")
        self.unprocessed_dir = os.path.join(output_dir, "Unprocessed")
        self.logger = logger
        self.write_exif = write_exif
        self.stats = ProcessingStats()

        self._exiftool: Optional[ExifToolManager] = None

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
        """Context manager exit."""
        self.stop()

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
        album_dir = checkout_dir(os.path.join(self.processed_dir, file.albumname))

        # Get unique destination path
        dest_path = get_unique_path(os.path.join(album_dir, file.filename))

        # Copy file
        if self.logger:
            self.logger.log(f"Copying: {file.filepath} -> {dest_path}")
        shutil.copy(file.filepath, dest_path)

        # Set file dates
        try:
            filedate.File(dest_path).set(created=metadata.date, modified=metadata.date)
        except Exception as e:
            if self.logger:
                self.logger.log(f"Warning: Could not set file dates on {dest_path}: {e}")

        # Write EXIF metadata
        if self._exiftool and self.write_exif:
            self._write_metadata(dest_path, metadata)

        # Update file info
        file.procpath = dest_path
        file.jsonpath = metadata.filepath

        # Update stats (GPS/people counted per JSON by orchestrator)
        self.stats.processed += 1

        if self.logger:
            self.logger.log(f"Processed: {file.filename}")

        return dest_path

    def _write_metadata(self, filepath: str, metadata: JsonMetadata) -> bool:
        """Write EXIF metadata to a file.

        Args:
            filepath: Path to file.
            metadata: Metadata to write.

        Returns:
            True if successful.
        """
        tags = {}

        if metadata.geo_data:
            tags.update(build_gps_tags(metadata.geo_data))

        if metadata.people:
            tags.update(build_people_tags(metadata.people))

        if not tags:
            return True

        try:
            return self._exiftool.write_tags(filepath, tags)
        except Exception as e:
            if self.logger:
                self.logger.log(f"Warning: Could not write metadata to {filepath}: {e}")
            self.stats.errors += 1
            return False

    def process_unmatched_file(self, file: FileInfo) -> str:
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
        if self.logger:
            self.logger.log(f"Copying unprocessed: {file.filepath}")
        shutil.copy(file.filepath, dest_path)

        file.procpath = dest_path
        self.stats.unmatched_files += 1

        return dest_path

    def process_unmatched_files(
        self,
        files: List[FileInfo],
        on_progress: Optional[ProgressCallback] = None
    ) -> List[FileInfo]:
        """Copy all unmatched files to Unprocessed folder.

        Args:
            files: List of unmatched files.
            on_progress: Optional progress callback.

        Returns:
            List of files with procpath set.
        """
        total = len(files)

        for i, file in enumerate(files):
            self.process_unmatched_file(file)

            if on_progress:
                on_progress(i + 1, total, f"Copying: {file.filename}")

        return files

    def extend_metadata(self, filepath: str, metadata: JsonMetadata) -> bool:
        """Write metadata to an existing file without copying.

        Args:
            filepath: Path to existing file.
            metadata: Metadata to write.

        Returns:
            True if successful.
        """
        if not self._exiftool:
            return False

        return self._write_metadata(filepath, metadata)


# Backwards-compatible function (deprecated)
def copy_modify(
    file: dict,
    date: datetime,
    copyto: str,
    geo_data: Optional[dict] = None,
    people: Optional[list] = None,
    exiftool_helper: Any = None
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

    # Create album directory
    album_dir = checkout_dir(os.path.join(copyto, file["albumname"]))

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

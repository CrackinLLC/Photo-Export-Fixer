# Task 08: Extract Processor

## Objective
Extract file processing operations (copy, date modification, metadata writing) into a `FileProcessor` class.

## Prerequisites
- Task 01 (Module Structure) complete
- Task 02 (Models) complete
- Task 03 (Utils) complete
- Task 04 (Logger) complete
- Task 07 (Metadata & ExifTool) complete

## Files to Create
- `pef/core/processor.py`

## Current State Analysis

### Copy and modify function (lines 265-289)
```python
def copy_modify(file, date, copyto, geo_data=None, people=None, exiftool_helper=None, saveto=None):
    copyto = checkout_dir(os.path.join(copyto, file["albumname"]))
    new_file = get_unique_path(os.path.join(copyto, file["filename"]))
    shutil.copy(file["filepath"], new_file)
    filedate.File(new_file).set(created=date, modified=date)
    if exiftool_helper:
        tags = {}
        tags.update(build_gps_tags(geo_data))
        tags.update(build_people_tags(people))
        if tags:
            try:
                exiftool_helper.set_tags(new_file, tags)
            except Exception as e:
                if saveto:
                    log_detail(saveto, f"Warning: Could not write metadata to {new_file}: {e}")
    return new_file
```

### Copy unprocessed function (lines 291-302)
```python
def copy_unprocessed(unprocessed, saveto):
    to_return = []
    for file in tqdm(unprocessed, desc="Copying"):
        log_detail(saveto, f"Copying unprocessed file: {file['filepath']}")
        new_file = get_unique_path(os.path.join(saveto, checkout_dir(os.path.join(saveto, "Unprocessed")), file["filename"]))
        shutil.copy(file["filepath"], new_file)
        log_detail(saveto, f"Successfully copied unprocessed file to: {new_file}\n")
        file["procpath"] = new_file
        to_return.append(file)
    return to_return
```

## Implementation

### `pef/core/processor.py`

```python
"""File processing operations for Photo Export Fixer.

Handles copying, date modification, and metadata writing.
"""

import os
import shutil
from datetime import datetime
from typing import Optional, List, Callable, Dict, Any

import filedate

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
            file: Source file info.
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
        filedate.File(dest_path).set(created=metadata.date, modified=metadata.date)

        # Write EXIF metadata
        if self._exiftool and self.write_exif:
            self._write_metadata(dest_path, metadata)

        # Update file info
        file.procpath = dest_path
        file.jsonpath = metadata.filepath

        # Update stats
        self.stats.processed += 1
        if metadata.has_location():
            self.stats.with_gps += 1
        if metadata.has_people():
            self.stats.with_people += 1

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


# Backwards-compatible function
def copy_modify(
    file: dict,
    date: datetime,
    copyto: str,
    geo_data: Optional[dict] = None,
    people: Optional[list] = None,
    exiftool_helper: Any = None,
    saveto: Optional[str] = None
) -> str:
    """Copy and modify a file (backwards compatible).

    Args:
        file: Dict with filename, filepath, albumname keys.
        date: Date to set on file.
        copyto: Destination directory.
        geo_data: Optional Google geoData dict.
        people: Optional Google people list.
        exiftool_helper: Optional ExifToolHelper instance.
        saveto: Optional log directory.

    Returns:
        Path to copied file.
    """
    from pef.core.metadata import build_gps_tags_from_dict, build_people_tags_from_list

    # Create album directory
    album_dir = checkout_dir(os.path.join(copyto, file["albumname"]))

    # Get unique destination path
    dest_path = get_unique_path(os.path.join(album_dir, file["filename"]))

    # Copy file
    shutil.copy(file["filepath"], dest_path)

    # Set file dates
    filedate.File(dest_path).set(created=date, modified=date)

    # Write EXIF metadata
    if exiftool_helper:
        tags = {}
        tags.update(build_gps_tags_from_dict(geo_data))
        tags.update(build_people_tags_from_list(people))

        if tags:
            try:
                exiftool_helper.set_tags(dest_path, tags)
            except Exception as e:
                pass  # Silently continue

    return dest_path
```

## Usage Examples

### New style (with FileProcessor):
```python
from pef.core.processor import FileProcessor
from pef.core.logger import BufferedLogger

with BufferedLogger(output_dir) as logger:
    with FileProcessor(output_dir, logger=logger) as processor:
        for file, metadata in matched_files:
            processor.process_file(file, metadata)

        processor.process_unmatched_files(unmatched_files)

        print(f"Processed: {processor.stats.processed}")
        print(f"With GPS: {processor.stats.with_gps}")
```

### Old style (backwards compatible):
```python
from pef.core.processor import copy_modify

new_path = copy_modify(file_dict, date, copyto, geo_data, people, exiftool_helper)
```

## Acceptance Criteria

1. [ ] `pef/core/processor.py` exists with `FileProcessor` class
2. [ ] `FileProcessor` supports context manager pattern
3. [ ] `process_file()` copies, sets dates, writes metadata
4. [ ] `process_unmatched_files()` accepts progress callback
5. [ ] `extend_metadata()` writes to existing files
6. [ ] `copy_modify()` backwards-compatible function works
7. [ ] Stats tracking works correctly
8. [ ] Original `pef.py` still works unchanged

## Verification

```python
import tempfile
import os
from datetime import datetime
from pef.core.processor import FileProcessor
from pef.core.models import FileInfo, JsonMetadata, GeoData, Person
from pef.core.logger import BufferedLogger

# Create test file
with tempfile.TemporaryDirectory() as tmpdir:
    # Create source file
    src_dir = os.path.join(tmpdir, "source", "Album1")
    os.makedirs(src_dir)
    src_file = os.path.join(src_dir, "test.txt")
    with open(src_file, "w") as f:
        f.write("test content")

    # Create output dir
    out_dir = os.path.join(tmpdir, "output")

    # Process
    file = FileInfo(filename="test.txt", filepath=src_file, albumname="Album1")
    metadata = JsonMetadata(
        filepath="/fake/test.json",
        title="test.txt",
        date=datetime(2023, 6, 15, 12, 0, 0),
        geo_data=GeoData(40.7, -74.0),
        people=[Person("Alice")]
    )

    with BufferedLogger(out_dir) as logger:
        with FileProcessor(out_dir, logger=logger, write_exif=False) as processor:
            dest = processor.process_file(file, metadata)
            print(f"Processed to: {dest}")
            print(f"Stats: {processor.stats}")
            assert os.path.exists(dest)
            assert processor.stats.processed == 1
```

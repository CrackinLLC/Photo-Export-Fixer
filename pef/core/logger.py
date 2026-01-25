"""Logging utilities for Photo Export Fixer."""

import os
import time
from typing import Optional, TextIO, List, Dict, Any, Union


class BufferedLogger:
    """Buffered file logger with context manager support.

    Usage:
        with BufferedLogger("/path/to/logs") as logger:
            logger.log("Processing started")
            logger.log("File processed: photo.jpg")
        # File is automatically closed

    Or manual management:
        logger = BufferedLogger("/path/to/logs")
        try:
            logger.log("Processing...")
        finally:
            logger.close()
    """

    def __init__(self, output_dir: str, filename: str = "detailed_logs.txt"):
        """Initialize logger.

        Args:
            output_dir: Directory to write log file.
            filename: Name of log file (default: detailed_logs.txt).
        """
        self.output_dir = output_dir
        self.filename = filename
        self.filepath = os.path.join(output_dir, filename)
        self._handle: Optional[TextIO] = None

    def _open(self) -> None:
        """Open the log file for writing (lazy initialization)."""
        if self._handle is None:
            os.makedirs(self.output_dir, exist_ok=True)
            self._handle = open(self.filepath, "a", encoding="utf-8")

    def log(self, message: str) -> None:
        """Write a timestamped message to the log.

        Args:
            message: Message to log.
        """
        self._open()  # Lazy open on first log
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._handle.write(f"{timestamp} - {message}\n")

    def flush(self) -> None:
        """Flush the log buffer to disk."""
        if self._handle:
            self._handle.flush()

    def close(self) -> None:
        """Close the log file."""
        if self._handle:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "BufferedLogger":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures file is closed."""
        self.close()

    @property
    def is_open(self) -> bool:
        """Check if logger is open."""
        return self._handle is not None


class SummaryLogger:
    """Logger for the summary logs.txt file.

    Collects processing results and writes a formatted summary at the end.
    """

    def __init__(self, output_dir: str, filename: str = "logs.txt"):
        """Initialize summary logger.

        Args:
            output_dir: Directory to write log file.
            filename: Name of log file (default: logs.txt).
        """
        self.output_dir = output_dir
        self.filepath = os.path.join(output_dir, filename)

    def write_summary(
        self,
        processed: List[Dict[str, Any]],
        unprocessed: List[Dict[str, Any]],
        unprocessed_jsons: List[Dict[str, Any]],
        elapsed_time: float,
        start_time: str,
        end_time: str
    ) -> None:
        """Write the processing summary to file.

        Args:
            processed: List of processed file records.
            unprocessed: List of unprocessed file records.
            unprocessed_jsons: List of unprocessed JSON records.
            elapsed_time: Total processing time in seconds.
            start_time: Start timestamp string.
            end_time: End timestamp string.
        """
        with open(self.filepath, "w", encoding="utf-8") as f:
            # Processed files section
            if processed:
                f.write("Processed files:\n\n")
                for file in processed:
                    f.write(f"    {file.get('filename', 'unknown')}:\n")
                    f.write(f"        original file:     {file.get('filepath', '')}\n")
                    f.write(f"        destination file:  {file.get('output_path') or file.get('procpath', '')}\n")
                    f.write(f"        source json:       {file.get('json_path') or file.get('jsonpath', '')}\n")
                    f.write(f"    time processed:        {file.get('time', '')}\n\n")

            # Unprocessed JSONs section
            if unprocessed_jsons:
                f.write("Unprocessed jsons:\n\n")
                for file in unprocessed_jsons:
                    f.write(f"    {file.get('filename', 'unknown')}:\n")
                    f.write(f"        original file:     {file.get('filepath', '')}\n")
                    f.write(f"        this json file did not find his pair among files: {file.get('title', '')}\n")
                    f.write(f"    time processed:        {file.get('time', '')}\n\n")

            # Unprocessed files section
            if unprocessed:
                f.write("Unprocessed files:\n\n")
                for file in unprocessed:
                    f.write(f"    {file.get('filename', 'unknown')}:\n")
                    f.write(f"        original file:     {file.get('filepath', '')}\n")
                    f.write(f"        copied file:       {file.get('output_path') or file.get('procpath', '')}\n")
                    f.write("        json-based search have not reached this file\n\n")

            # Summary statistics
            f.write(f"Processed: {len(processed)} files\n")
            f.write(f"Unprocessed: {len(unprocessed)} files, {len(unprocessed_jsons)} jsons\n")
            f.write(f"Time used: {elapsed_time} seconds\n")
            f.write(f"Started: {start_time}\n")
            f.write(f"Ended:   {end_time}\n")


class NullLogger:
    """A logger that does nothing - useful for testing or when logging is disabled."""

    def log(self, message: str) -> None:
        """No-op log method."""
        pass

    def flush(self) -> None:
        """No-op flush method."""
        pass

    def close(self) -> None:
        """No-op close method."""
        pass

    def __enter__(self) -> "NullLogger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    @property
    def is_open(self) -> bool:
        return True


def create_logger(output_dir: str, enabled: bool = True) -> Union[BufferedLogger, NullLogger]:
    """Create a logger instance.

    Args:
        output_dir: Directory for log file.
        enabled: If False, returns a NullLogger that does nothing.

    Returns:
        Configured logger instance.
    """
    if enabled:
        return BufferedLogger(output_dir)
    return NullLogger()


class PEFLogger:
    """New unified logger for PEF that writes to the _pef directory.

    Handles all logging output:
    - summary.txt: Concise summary (always generated)
    - verbose.txt: Detailed log (only with --verbose)
    - unprocessed.txt: Files without metadata
    - motion_photos.txt: Info about motion photos
    """

    def __init__(self, pef_dir: str, verbose: bool = False):
        """Initialize PEF logger.

        Args:
            pef_dir: The _pef directory path.
            verbose: Whether to create verbose.txt.
        """
        self.pef_dir = pef_dir
        self.verbose = verbose
        self._verbose_logger: Optional[BufferedLogger] = None

        os.makedirs(pef_dir, exist_ok=True)

        if verbose:
            self._verbose_logger = BufferedLogger(pef_dir, filename="verbose.txt")

    def log(self, message: str) -> None:
        """Log a message to verbose.txt (if verbose mode enabled).

        Args:
            message: Message to log.
        """
        if self._verbose_logger:
            self._verbose_logger.log(message)

    def close(self) -> None:
        """Close any open log files."""
        if self._verbose_logger:
            self._verbose_logger.close()

    def __enter__(self) -> "PEFLogger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def write_summary(
        self,
        source_path: str,
        output_dir: str,
        stats: Any,  # ProcessingStats
        elapsed_time: float,
        start_time: str,
        end_time: str,
        motion_photo_count: int = 0,
        unprocessed_count: int = 0,
        unmatched_json_count: int = 0,
        exiftool_available: bool = False,
        exiftool_path: Optional[str] = None
    ) -> str:
        """Write concise summary.txt.

        Returns:
            Path to summary file.
        """
        filepath = os.path.join(self.pef_dir, "summary.txt")

        # Format duration nicely
        if elapsed_time >= 60:
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            duration = f"{minutes}m {seconds}s"
        else:
            duration = f"{elapsed_time:.1f}s"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("Photo Export Fixer - Processing Summary\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Source:    {source_path}\n")
            f.write(f"Output:    {output_dir}\n")
            f.write(f"Started:   {start_time}\n")
            f.write(f"Completed: {end_time}\n")
            f.write(f"Duration:  {duration}\n\n")

            f.write(f"Files Processed:     {stats.processed:,}\n")
            f.write(f"  With GPS data:     {stats.with_gps:,}\n")
            f.write(f"  With people tags:  {stats.with_people:,}\n")

            if unprocessed_count > 0:
                f.write(f"Files Unprocessed:   {unprocessed_count:,}  (see unprocessed.txt)\n")
            else:
                f.write("Files Unprocessed:   0\n")

            if motion_photo_count > 0:
                f.write(f"Motion Photos:       {motion_photo_count:,}  (see motion_photos.txt)\n")

            if unmatched_json_count > 0:
                f.write(f"Unmatched JSONs:     {unmatched_json_count:,}  (see unmatched_data/)\n")

            if stats.errors > 0:
                f.write(f"Errors:              {stats.errors:,}\n")

            f.write("\n")
            if exiftool_available:
                path_str = exiftool_path if exiftool_path else "in PATH"
                f.write(f"ExifTool: Available ({path_str})\n")
            else:
                f.write("ExifTool: Not available (metadata not written)\n")

        return filepath

    def write_unprocessed(
        self,
        items: List[Any]  # List[UnprocessedItem]
    ) -> Optional[str]:
        """Write unprocessed.txt with files that didn't get metadata.

        Args:
            items: List of UnprocessedItem objects.

        Returns:
            Path to file, or None if no items.
        """
        if not items:
            return None

        filepath = os.path.join(self.pef_dir, "unprocessed.txt")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Files without metadata\n")
            f.write("# Format: relative_path | reason\n\n")

            for item in items:
                f.write(f"{item.relative_path} | {item.reason}\n")

        return filepath

    def write_motion_photos(
        self,
        items: List[Any]  # List[MotionPhotoInfo]
    ) -> Optional[str]:
        """Write motion_photos.txt with info about motion photo files.

        Args:
            items: List of MotionPhotoInfo objects.

        Returns:
            Path to file, or None if no items.
        """
        if not items:
            return None

        filepath = os.path.join(self.pef_dir, "motion_photos.txt")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("Motion Photos Information\n")
            f.write("=" * 40 + "\n\n")
            f.write("Motion Photos are short video clips captured alongside still images.\n")
            f.write("Google Photos stores these as separate .MP files alongside the .jpg.\n\n")
            f.write("These files have been preserved in their original locations. If you're\n")
            f.write("importing to Immich or similar platforms, you may need to:\n")
            f.write("- Rename .MP to .MP4 for compatibility\n")
            f.write("- Or use the --rename-mp flag when running PEF\n\n")
            f.write(f"Motion photo files found ({len(items)} total):\n\n")

            for item in items:
                f.write(f"{item.relative_path}\n")

        return filepath

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
                    f.write(f"        destination file:  {file.get('procpath', '')}\n")
                    f.write(f"        source json:       {file.get('jsonpath', '')}\n")
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
                    f.write(f"        copied file:       {file.get('procpath', '')}\n")
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

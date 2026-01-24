# Task 04: Extract Logger

## Objective
Replace the global `_log_handle` and `_log_path` variables with a proper `BufferedLogger` class that supports context manager pattern.

## Prerequisites
- Task 01 (Module Structure) complete

## Files to Create
- `pef/core/logger.py`

## Current State Analysis

Lines 304-329 in `pef.py`:
```python
# Module-level log handle for buffered logging
_log_handle = None
_log_path = None

def init_logger(saveto):
    global _log_handle, _log_path
    _log_path = os.path.join(saveto, "detailed_logs.txt")
    _log_handle = open(_log_path, "a", encoding="utf-8")

def close_logger():
    global _log_handle
    if _log_handle:
        _log_handle.close()
        _log_handle = None

def log_detail(saveto, message):
    global _log_handle
    if _log_handle:
        _log_handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    else:
        # Fallback to original behavior if logger not initialized
        with open(os.path.join(saveto, "detailed_logs.txt"), "a", encoding="utf-8") as logfile:
            logfile.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
```

### Problems
1. Global state (`_log_handle`, `_log_path`)
2. Must remember to call `close_logger()`
3. `saveto` parameter in `log_detail` is confusing when logger is initialized

## Implementation

### `pef/core/logger.py`

```python
"""Logging utilities for Photo Export Fixer."""

import os
import time
from typing import Optional, TextIO


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
        self._open()

    def _open(self) -> None:
        """Open the log file for writing."""
        os.makedirs(self.output_dir, exist_ok=True)
        self._handle = open(self.filepath, "a", encoding="utf-8")

    def log(self, message: str) -> None:
        """Write a timestamped message to the log.

        Args:
            message: Message to log.
        """
        if self._handle:
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
        processed: list,
        unprocessed: list,
        unprocessed_jsons: list,
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


# Convenience function for simple logging (backwards compatibility)
def create_logger(output_dir: str) -> BufferedLogger:
    """Create a BufferedLogger instance.

    Args:
        output_dir: Directory for log file.

    Returns:
        Configured BufferedLogger instance.
    """
    return BufferedLogger(output_dir)
```

## Usage Example

### New style (with context manager):
```python
from pef.core.logger import BufferedLogger, SummaryLogger

# Detailed logging
with BufferedLogger(output_dir) as logger:
    logger.log("Processing started")
    for file in files:
        logger.log(f"Processing: {file}")
    logger.log("Processing complete")

# Summary logging
summary = SummaryLogger(output_dir)
summary.write_summary(processed, unprocessed, unprocessed_jsons, elapsed, start, end)
```

### Old style (manual management):
```python
logger = BufferedLogger(output_dir)
try:
    logger.log("Processing...")
finally:
    logger.close()
```

## Acceptance Criteria

1. [ ] `pef/core/logger.py` exists with `BufferedLogger` and `SummaryLogger` classes
2. [ ] `BufferedLogger` supports context manager (`with` statement)
3. [ ] `BufferedLogger.log()` writes timestamped messages
4. [ ] `SummaryLogger.write_summary()` produces same format as current `savelogs()`
5. [ ] Original `pef.py` still works unchanged

## Verification

```python
import os
import tempfile
from pef.core.logger import BufferedLogger, SummaryLogger

# Test BufferedLogger
with tempfile.TemporaryDirectory() as tmpdir:
    with BufferedLogger(tmpdir) as logger:
        logger.log("Test message 1")
        logger.log("Test message 2")

    # Verify file contents
    with open(os.path.join(tmpdir, "detailed_logs.txt")) as f:
        content = f.read()
        print(content)
        assert "Test message 1" in content
        assert "Test message 2" in content

# Test SummaryLogger
with tempfile.TemporaryDirectory() as tmpdir:
    summary = SummaryLogger(tmpdir)
    summary.write_summary(
        processed=[{"filename": "test.jpg", "filepath": "/a", "procpath": "/b", "jsonpath": "/c", "time": "now"}],
        unprocessed=[],
        unprocessed_jsons=[],
        elapsed_time=10.5,
        start_time="2024-01-01 10:00:00",
        end_time="2024-01-01 10:00:10"
    )
    with open(os.path.join(tmpdir, "logs.txt")) as f:
        print(f.read())
```

## Migration Notes

The current global state pattern will be replaced in Task 10 (CLI Refactor):
- `init_logger(saveto)` -> `logger = BufferedLogger(saveto)`
- `log_detail(saveto, msg)` -> `logger.log(msg)`
- `close_logger()` -> `logger.close()` (or use `with` statement)
- `savelogs(...)` -> `SummaryLogger(saveto).write_summary(...)`

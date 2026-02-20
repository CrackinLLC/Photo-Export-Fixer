"""Processing state management for resume capability.

Tracks which JSON files have been processed, enabling efficient resume
after interruption without re-processing files.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Use orjson for faster JSON parsing if available
try:
    import orjson
    _USE_ORJSON = True
except ImportError:
    _USE_ORJSON = False

logger = logging.getLogger(__name__)


class StateManager:
    """Manages processing state for resume capability.

    Tracks processed JSON paths in a state file, enabling resume after
    interruption. Saves state periodically to survive crashes.

    Usage:
        state = StateManager(output_dir)

        if state.can_resume():
            state.load()
            jsons = state.filter_unprocessed(all_jsons)
        else:
            state.create(source_path, len(all_jsons))

        for json_path in jsons:
            # process...
            state.mark_processed(json_path)

        state.complete()
    """

    STATE_FILENAME = "processing_state.json"
    SAVE_INTERVAL = 100  # Auto-save every N files

    def __init__(self, output_dir: str):
        """Initialize state manager.

        Args:
            output_dir: Output directory where state file will be stored.
        """
        self.output_dir = output_dir
        self.state_path = os.path.join(output_dir, self.STATE_FILENAME)
        self._processed: Set[str] = set()
        self._source_path: str = ""
        self._started_at: str = ""
        self._status: str = "pending"
        self._total_count: int = 0
        self._pending_saves: int = 0

    def can_resume(self) -> bool:
        """Check if resumable state exists.

        Returns:
            True if state file exists and status is 'in_progress'.
        """
        if not os.path.exists(self.state_path):
            return False
        state = self._read_state_file()
        return state is not None and state.get("status") == "in_progress"

    def is_completed(self) -> bool:
        """Check if processing was already completed.

        Returns:
            True if state file exists and status is 'completed'.
        """
        if not os.path.exists(self.state_path):
            return False
        state = self._read_state_file()
        return state is not None and state.get("status") == "completed"

    def _cleanup_temp_files(self) -> None:
        """Remove orphaned temp files from interrupted state saves."""
        try:
            for f in os.listdir(self.output_dir):
                if f.startswith(".state_") and f.endswith(".tmp"):
                    try:
                        os.unlink(os.path.join(self.output_dir, f))
                    except OSError:
                        pass
        except OSError:
            pass

    def load(self) -> bool:
        """Load existing state from file.

        Returns:
            True if state was loaded successfully.
        """
        self._cleanup_temp_files()
        state = self._read_state_file()
        if not state:
            return False

        self._processed = {os.path.normpath(p) for p in state.get("processed_jsons", [])}
        self._source_path = state.get("source_path", "")
        self._started_at = state.get("started_at", "")
        self._status = state.get("status", "pending")
        self._total_count = state.get("total_json_count", 0)
        return True

    def create(self, source_path: str, total_count: int) -> None:
        """Create new processing state.

        Args:
            source_path: Path to source directory being processed.
            total_count: Total number of JSON files to process.
        """
        self._cleanup_temp_files()
        self._processed = set()
        self._source_path = source_path
        self._started_at = datetime.now().isoformat()
        self._status = "in_progress"
        self._total_count = total_count
        self._pending_saves = 0
        self._save()

    def _save_interval(self) -> int:
        """Calculate adaptive save interval based on processed count."""
        return max(100, len(self._processed) // 100)

    def mark_processed(self, json_path: str) -> None:
        """Mark a JSON file as processed.

        Auto-saves state periodically based on an adaptive save interval
        that grows with the number of processed files.

        Args:
            json_path: Path to the processed JSON file.
        """
        self._processed.add(os.path.normpath(json_path))
        self._pending_saves += 1

        if self._pending_saves >= self._save_interval():
            self._save()
            self._pending_saves = 0

    def is_processed(self, json_path: str) -> bool:
        """Check if a JSON file was already processed.

        Args:
            json_path: Path to check.

        Returns:
            True if the JSON was already processed.
        """
        return os.path.normpath(json_path) in self._processed

    def filter_unprocessed(self, all_jsons: List[str]) -> List[str]:
        """Filter a list to only include unprocessed JSONs.

        Args:
            all_jsons: List of all JSON paths.

        Returns:
            List of JSON paths that haven't been processed yet.
        """
        return [j for j in all_jsons if os.path.normpath(j) not in self._processed]

    def complete(self) -> None:
        """Mark processing as complete and save final state."""
        self._status = "completed"
        self._save()

    def save(self) -> None:
        """Force save current state to file."""
        self._save()
        self._pending_saves = 0

    @property
    def processed_count(self) -> int:
        """Number of JSONs that have been processed."""
        return len(self._processed)

    @property
    def total_count(self) -> int:
        """Total number of JSONs to process."""
        return self._total_count

    @property
    def source_path(self) -> str:
        """Source path being processed."""
        return self._source_path

    @property
    def status(self) -> str:
        """Current processing status."""
        return self._status

    def _save(self) -> None:
        """Write state to file atomically.

        Writes to a temporary file in the same directory, then atomically
        replaces the target file via os.replace(). This prevents corruption
        if the process crashes mid-write.
        """
        state = {
            "version": 1,
            "source_path": self._source_path,
            "started_at": self._started_at,
            "last_updated": datetime.now().isoformat(),
            "status": self._status,
            "total_json_count": self._total_count,
            "processed_count": len(self._processed),
            "processed_jsons": sorted(self._processed)
        }

        try:
            os.makedirs(self.output_dir, exist_ok=True)

            fd, tmp_path = tempfile.mkstemp(
                dir=self.output_dir, suffix=".tmp", prefix=".state_"
            )
            try:
                if _USE_ORJSON:
                    with open(fd, "wb") as f:
                        f.write(orjson.dumps(state, option=orjson.OPT_INDENT_2))
                else:
                    with open(fd, "w", encoding="utf-8") as f:
                        json.dump(state, f, indent=2)

                os.replace(tmp_path, self.state_path)
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        except Exception as e:
            logger.warning(f"Failed to save state to {self.state_path}: {e}")

    def _read_state_file(self) -> Optional[Dict[str, Any]]:
        """Read and parse state file.

        Returns:
            Parsed state dict, or None if file doesn't exist or is invalid.
        """
        if not os.path.exists(self.state_path):
            return None

        try:
            if _USE_ORJSON:
                with open(self.state_path, "rb") as f:
                    return orjson.loads(f.read())
            else:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        except Exception as e:
            logger.warning(f"Failed to read state file {self.state_path}: {e}")
            return None

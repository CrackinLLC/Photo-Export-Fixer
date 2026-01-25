"""ExifTool management for Photo Export Fixer.

Handles finding, downloading, and initializing ExifTool.
"""

import logging
import os
import shutil
import sys
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# ExifTool paths
EXIFTOOL_DIR = os.path.join("tools", "exiftool")
EXIFTOOL_EXE = "exiftool.exe" if sys.platform == "win32" else "exiftool"


def get_exiftool_path(base_dir: Optional[str] = None) -> Optional[str]:
    """Find ExifTool executable.

    Checks in order:
    1. System PATH
    2. Local tools directory
    3. Attempts auto-download (Windows only)

    Args:
        base_dir: Base directory for local tools folder.
                 Defaults to directory containing this module.

    Returns:
        Path to exiftool executable, or None if not found.
    """
    # 1. Check system PATH
    if shutil.which("exiftool"):
        return "exiftool"

    # 2. Check local tools folder
    if base_dir is None:
        # Go up from pef/core/ to project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    local_path = os.path.join(base_dir, EXIFTOOL_DIR, EXIFTOOL_EXE)
    if os.path.exists(local_path):
        return local_path

    # 3. Attempt auto-download (Windows only)
    if sys.platform == "win32":
        if auto_download_exiftool(base_dir):
            return local_path

    # Not found
    logger.warning("ExifTool not found. Install from https://exiftool.org/")
    return None


def auto_download_exiftool(base_dir: str) -> bool:
    """Download ExifTool for Windows.

    Fetches the latest version dynamically from exiftool.org.

    Args:
        base_dir: Base directory to install into.

    Returns:
        True if download succeeded, False otherwise.
    """
    import urllib.error
    import urllib.request
    import zipfile

    tools_dir = os.path.join(base_dir, EXIFTOOL_DIR)
    os.makedirs(tools_dir, exist_ok=True)

    zip_path = os.path.join(tools_dir, "exiftool.zip")

    try:
        # Get latest version number from exiftool.org
        logger.info("Checking for latest ExifTool version...")
        with urllib.request.urlopen("https://exiftool.org/ver.txt") as response:
            version = response.read().decode().strip()
        logger.info(f"Latest version: {version}")

        # Download from SourceForge (64-bit Windows)
        url = f"https://sourceforge.net/projects/exiftool/files/exiftool-{version}_64.zip/download"
        logger.info(f"Downloading ExifTool {version}...")
        urllib.request.urlretrieve(url, zip_path)

        logger.info("Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tools_dir)

        # Find the extracted subdirectory and move contents to tools_dir
        for item in os.listdir(tools_dir):
            item_path = os.path.join(tools_dir, item)
            if os.path.isdir(item_path) and item.startswith("exiftool"):
                # This is the extracted folder - move its contents up
                for sub_item in os.listdir(item_path):
                    src = os.path.join(item_path, sub_item)
                    dst = os.path.join(tools_dir, sub_item)
                    if sub_item.startswith("exiftool") and sub_item.endswith(".exe"):
                        # Rename the exe to exiftool.exe
                        dst = os.path.join(tools_dir, EXIFTOOL_EXE)
                    shutil.move(src, dst)
                # Remove the now-empty subdirectory
                shutil.rmtree(item_path, ignore_errors=True)
                break

        os.remove(zip_path)
        logger.info("ExifTool installed successfully!")
        return True

    except urllib.error.URLError as e:
        logger.warning(f"Network error downloading ExifTool: {e}")
        return False
    except zipfile.BadZipFile as e:
        logger.warning(f"Downloaded file is corrupted: {e}")
        return False
    except OSError as e:
        logger.warning(f"File system error during ExifTool install: {e}")
        return False
    except Exception as e:
        logger.warning(f"Auto-download failed: {e}")
        return False


def print_install_instructions() -> None:
    """Print manual installation instructions."""
    logger.info("ExifTool not found. Please install it:")
    logger.info("  1. Download from https://exiftool.org/")
    logger.info("  2. Extract and rename exiftool(-k).exe to exiftool.exe")
    logger.info("  3. Place in PATH or in ./tools/exiftool/")


def is_exiftool_available() -> bool:
    """Check if ExifTool is available.

    Returns:
        True if ExifTool can be found.
    """
    # Check PATH first (quick)
    if shutil.which("exiftool"):
        return True

    # Check local tools folder
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    local_path = os.path.join(base_dir, EXIFTOOL_DIR, EXIFTOOL_EXE)
    return os.path.exists(local_path)


class ExifToolManager:
    """Manages ExifTool lifecycle for batch operations.

    Usage:
        with ExifToolManager() as et:
            et.write_tags("/path/to/file.jpg", {"GPSLatitude": 40.7})

    Or for processing many files:
        manager = ExifToolManager()
        manager.start()
        for file in files:
            manager.write_tags(file, tags)
        manager.stop()
    """

    def __init__(self, base_dir: Optional[str] = None):
        """Initialize manager.

        Args:
            base_dir: Base directory for local tools folder.
        """
        self._helper = None
        self._exiftool_path = None
        self._base_dir = base_dir

    def start(self) -> bool:
        """Start ExifTool process.

        Returns:
            True if started successfully, False otherwise.
        """
        try:
            import exiftool
        except ImportError:
            logger.warning("pyexiftool not installed. Run: pip install pyexiftool")
            return False

        self._exiftool_path = get_exiftool_path(self._base_dir)
        if not self._exiftool_path:
            return False

        try:
            self._helper = exiftool.ExifToolHelper(executable=self._exiftool_path)
            self._helper.run()
            return True
        except Exception as e:
            logger.error(f"Failed to start ExifTool: {e}")
            return False

    def stop(self) -> None:
        """Stop ExifTool process."""
        if self._helper:
            try:
                self._helper.terminate()
            except Exception as e:
                logger.debug(f"Error stopping ExifTool: {e}")
            self._helper = None

    def write_tags(self, filepath: str, tags: dict) -> bool:
        """Write tags to a file.

        Args:
            filepath: Path to file.
            tags: Dict of ExifTool tags.

        Returns:
            True if successful, False otherwise.
        """
        if not self._helper or not tags:
            return False

        try:
            self._helper.set_tags(filepath, tags)
            return True
        except Exception as e:
            logger.debug(f"Failed to write tags to {filepath}: {e}")
            return False

    def read_tags(self, filepath: str, tags: Optional[List[str]] = None) -> dict:
        """Read tags from a file.

        Args:
            filepath: Path to file.
            tags: Optional list of specific tags to read.

        Returns:
            Dict of tag values, empty if error.
        """
        if not self._helper:
            return {}

        try:
            if tags:
                result = self._helper.get_tags(filepath, tags)
            else:
                result = self._helper.get_metadata(filepath)
            return result[0] if result else {}
        except Exception as e:
            logger.debug(f"Failed to read tags from {filepath}: {e}")
            return {}

    def write_tags_batch(
        self,
        file_tags_pairs: List[Tuple[str, dict]]
    ) -> List[bool]:
        """Write tags to multiple files efficiently.

        Processes files in a batch to reduce ExifTool invocation overhead.
        Each file can have different tags.

        Args:
            file_tags_pairs: List of (filepath, tags_dict) tuples.

        Returns:
            List of success booleans, one per file in same order.
        """
        if not self._helper or not file_tags_pairs:
            return [False] * len(file_tags_pairs) if file_tags_pairs else []

        results = []
        for filepath, tags in file_tags_pairs:
            if not tags:
                results.append(True)  # No tags to write = success
                continue
            try:
                self._helper.set_tags(filepath, tags)
                results.append(True)
            except Exception as e:
                logger.debug(f"Batch write failed for {filepath}: {e}")
                results.append(False)

        return results

    def read_tags_batch(
        self,
        filepaths: List[str],
        tags: Optional[List[str]] = None
    ) -> List[dict]:
        """Read tags from multiple files efficiently.

        Uses pyexiftool's native batch support for better performance.

        Args:
            filepaths: List of file paths to read.
            tags: Optional list of specific tags to read.

        Returns:
            List of tag dicts, one per file in same order.
            Empty dict for files that failed to read.
        """
        if not self._helper or not filepaths:
            return [{} for _ in filepaths] if filepaths else []

        try:
            if tags:
                # pyexiftool's get_tags accepts a list of files
                results = self._helper.get_tags(filepaths, tags)
            else:
                results = self._helper.get_metadata(filepaths)
            return results if results else [{} for _ in filepaths]
        except Exception as e:
            logger.debug(f"Batch read failed: {e}")
            return [{} for _ in filepaths]

    @property
    def is_running(self) -> bool:
        """Check if ExifTool is running."""
        return self._helper is not None

    @property
    def exiftool_path(self) -> Optional[str]:
        """Get the path to ExifTool executable."""
        return self._exiftool_path

    def __enter__(self) -> "ExifToolManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

"""Command-line interface for Photo Export Fixer."""

import argparse
import sys
from typing import List, Optional

from tqdm import tqdm

from pef.core.orchestrator import PEFOrchestrator
from pef.core.utils import exists, normalize_path
from pef.cli.wizard import run_wizard


# Program description
DESCRIPTION = """Photo Export Fixer

This program processes Google Takeout data by analyzing files in a specified folder.
It identifies `.json` files for metadata (e.g., creation date, file name) and processes
the corresponding files accordingly.

Files without a matching `.json` file or those that cannot be located are marked as
unprocessed and copied to a separate folder for review.

Processed files are copied and modified based on their metadata, while unprocessed
ones are logged.

More details can be found in the README file.
Git repository: https://github.com/CrackinLLC/Photo-Export-Fixer
"""

# Default suffixes
DEFAULT_SUFFIXES = ["", "-edited"]


def create_progress_callback(desc: str = "Processing"):
    """Create a tqdm-based progress callback.

    Args:
        desc: Description for progress bar.

    Returns:
        Tuple of (callback function, tqdm instance).
    """
    pbar = tqdm(total=100, desc=desc)

    def callback(current: int, total: int, message: str):
        pbar.total = total
        pbar.n = current
        # Truncate message to fit
        pbar.set_description(message[:40] if len(message) > 40 else message)
        pbar.refresh()

    return callback, pbar


def run_dry_run(
    path: str,
    destination: Optional[str],
    suffixes: List[str],
    extend_mode: bool = False
) -> int:
    """Run dry-run mode.

    Args:
        path: Source path.
        destination: Optional destination path.
        suffixes: Filename suffixes.
        extend_mode: If True, dry-run for extend mode.

    Returns:
        Exit code (0 for success).
    """
    print("\n=== DRY RUN MODE ===")
    print("No files will be copied or modified.\n")

    if not exists(path):
        print(f"Error: Path does not exist: {path}")
        return 1

    dest = destination or f"{path}_pefProcessed"

    if extend_mode:
        print(f"Source JSONs: {path}")
        print(f"Target files: {dest}/Processed")
    else:
        print(f"Source: {path}")
        print(f"Destination: {dest}")

    orchestrator = PEFOrchestrator(
        source_path=path,
        dest_path=dest,
        suffixes=suffixes
    )

    print("\nScanning files...")
    callback, pbar = create_progress_callback("Analyzing")

    try:
        result = orchestrator.dry_run(on_progress=callback)
    finally:
        pbar.close()

    print(f"\nFound:")
    print(f"  {result.json_count} JSON metadata files")
    print(f"  {result.file_count} media files")

    if extend_mode:
        print(f"\nWould update: {result.matched_count} files")
        print(f"Would skip: {result.unmatched_json_count} (no metadata or no match)")
    else:
        print(f"\nWould process:")
        print(f"  {result.matched_count} files with matching JSON")
        print(f"  {result.unmatched_json_count} JSONs without matching file")
        print(f"  {result.unmatched_file_count} files without matching JSON")

    print(f"\nMetadata available:")
    print(f"  {result.with_gps} files with GPS coordinates")
    print(f"  {result.with_people} files with people tags")

    if result.exiftool_available:
        print(f"\nExifTool: Found at {result.exiftool_path}")
    else:
        print("\nExifTool: Not found (GPS/people tags won't be written)")

    print("\n=== END DRY RUN ===")
    return 0


def run_process(
    path: str,
    destination: Optional[str],
    suffixes: List[str],
    write_exif: bool
) -> int:
    """Run main processing.

    Args:
        path: Source path.
        destination: Optional destination path.
        suffixes: Filename suffixes.
        write_exif: Whether to write EXIF metadata.

    Returns:
        Exit code (0 for success).
    """
    if not exists(path):
        print(f"Error: Path does not exist: {path}")
        return 1

    orchestrator = PEFOrchestrator(
        source_path=path,
        dest_path=destination,
        suffixes=suffixes,
        write_exif=write_exif
    )

    print("\nProcess started...")
    print(f"Working in directory: {path}")

    callback, pbar = create_progress_callback("Processing")

    try:
        result = orchestrator.process(on_progress=callback)
    finally:
        pbar.close()

    if result.errors:
        print(f"\nWarnings/Errors:")
        for error in result.errors[:10]:  # Show first 10
            print(f"  {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more")

    print("\nFinished!")
    print(f"Processed: {result.stats.processed} files")
    print(f"  With GPS: {result.stats.with_gps}")
    print(f"  With people: {result.stats.with_people}")
    print(f"Unprocessed: {result.stats.unmatched_files} files, {result.stats.unmatched_jsons} jsons")
    print(f"Time used: {result.elapsed_time} seconds")
    print(f"\nFolder with processed files:\n  {result.processed_dir}")
    print(f"Folder with unprocessed files:\n  {result.unprocessed_dir}")
    print(f"Logs saved in:\n  {result.log_file}")

    return 0


def run_extend(
    path: str,
    destination: Optional[str],
    suffixes: List[str]
) -> int:
    """Run extend metadata mode.

    Args:
        path: Source path (with JSONs).
        destination: Path to processed folder.
        suffixes: Filename suffixes.

    Returns:
        Exit code (0 for success).
    """
    if not exists(path):
        print(f"Error: Source path does not exist: {path}")
        return 1

    extend_path = destination or f"{path}_pefProcessed"

    if not exists(extend_path):
        print(f"Error: Processed folder not found at: {extend_path}")
        print("Make sure you've run the main processing first.")
        return 1

    orchestrator = PEFOrchestrator(
        source_path=path,
        dest_path=extend_path,
        suffixes=suffixes,
        write_exif=True
    )

    print("\nExtend mode: Adding metadata to already-processed files...")

    callback, pbar = create_progress_callback("Extending")

    try:
        result = orchestrator.extend(on_progress=callback)
    finally:
        pbar.close()

    print(f"\nExtend complete!")
    print(f"  Updated: {result.stats.processed} files")
    print(f"    With GPS: {result.stats.with_gps}")
    print(f"    With people: {result.stats.with_people}")
    print(f"  Skipped: {result.stats.skipped} (no metadata or no match)")
    print(f"  Errors: {result.stats.errors}")
    print(f"Time used: {result.elapsed_time} seconds")

    return 0


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Arguments to parse (default: sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-p", "--path",
        help="The full path to the directory containing Takeout folders",
        type=str,
        default=None
    )

    parser.add_argument(
        "-d", "--destination",
        help="The directory where processed files will be saved",
        type=str,
        default=None
    )

    parser.add_argument(
        "-s", "--suffix",
        action="append",
        help="Additional suffixes to try when matching files",
        type=str,
        default=None
    )

    parser.add_argument(
        "-e", "--extend",
        help="Extend metadata on already-processed files",
        action="store_true"
    )

    parser.add_argument(
        "--no-exif",
        help="Skip EXIF metadata writing (faster, timestamps only)",
        action="store_true"
    )

    parser.add_argument(
        "--dry-run",
        help="Show what would be done without making changes",
        action="store_true"
    )

    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for CLI.

    Args:
        args: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parsed = parse_args(args)

    # Get path (from args or wizard)
    path = parsed.path
    if not path:
        path = run_wizard()
        if not path:
            return 1

    # Normalize paths
    path = normalize_path(path)
    destination = normalize_path(parsed.destination) if parsed.destination else None

    # Get suffixes
    suffixes = parsed.suffix if parsed.suffix else DEFAULT_SUFFIXES

    # Dispatch to appropriate mode
    if parsed.extend:
        if parsed.dry_run:
            return run_dry_run(path, destination, suffixes, extend_mode=True)
        return run_extend(path, destination, suffixes)
    elif parsed.dry_run:
        return run_dry_run(path, destination, suffixes)
    else:
        return run_process(path, destination, suffixes, write_exif=not parsed.no_exif)


if __name__ == "__main__":
    sys.exit(main())

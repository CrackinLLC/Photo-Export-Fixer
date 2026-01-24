import os
import re
import json
import sys
from datetime import datetime
import filedate
import shutil
import time
from tqdm import tqdm
import argparse

# Optional dependency for EXIF metadata writing
try:
    import exiftool

    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False


def get_exiftool_path():
    """Find or download ExifTool, return path to executable."""
    # 1. Check if already in PATH
    if shutil.which("exiftool"):
        return "exiftool"

    # 2. Check local tools folder
    local_path = os.path.join(
        os.path.dirname(__file__), "tools", "exiftool", "exiftool.exe"
    )
    if os.path.exists(local_path):
        return local_path

    # 3. Attempt auto-download (Windows only)
    if sys.platform == "win32":
        if auto_download_exiftool():
            return local_path

    # 4. Fallback: instructions
    print("ExifTool not found. Please install it:")
    print("  1. Download from https://exiftool.org/")
    print("  2. Extract and rename exiftool(-k).exe to exiftool.exe")
    print("  3. Place in PATH or in ./tools/exiftool/")
    return None


def auto_download_exiftool():
    """Download ExifTool for Windows. Returns True on success."""
    import urllib.request
    import zipfile

    tools_dir = os.path.join(os.path.dirname(__file__), "tools", "exiftool")
    os.makedirs(tools_dir, exist_ok=True)

    zip_path = os.path.join(tools_dir, "exiftool.zip")

    try:
        # Get latest version number from exiftool.org
        print("Checking for latest ExifTool version...")
        with urllib.request.urlopen("https://exiftool.org/ver.txt") as response:
            version = response.read().decode().strip()
        print(f"Latest version: {version}")

        # Download from SourceForge (64-bit Windows)
        url = f"https://sourceforge.net/projects/exiftool/files/exiftool-{version}_64.zip/download"
        print(f"Downloading ExifTool {version}...")
        urllib.request.urlretrieve(url, zip_path)

        print("Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tools_dir)

        # Find the extracted subdirectory and move contents to tools_dir
        import shutil

        for item in os.listdir(tools_dir):
            item_path = os.path.join(tools_dir, item)
            if os.path.isdir(item_path) and item.startswith("exiftool"):
                # This is the extracted folder - move its contents up
                for sub_item in os.listdir(item_path):
                    src = os.path.join(item_path, sub_item)
                    dst = os.path.join(tools_dir, sub_item)
                    if sub_item.startswith("exiftool") and sub_item.endswith(".exe"):
                        # Rename the exe to exiftool.exe
                        dst = os.path.join(tools_dir, "exiftool.exe")
                    shutil.move(src, dst)
                # Remove the now-empty subdirectory
                os.rmdir(item_path)
                break

        os.remove(zip_path)
        print("ExifTool installed successfully!")
        return True

    except Exception as e:
        print(f"Auto-download failed: {e}")
        return False


description = (
    "Photo Export Fixer (PEF)\n\n"
    "This program processes photo export data (currently Google Takeout) by analyzing files in a "
    "specified folder. It identifies `.json` files for metadata (e.g., creation date, file name) "
    "and processes the corresponding files accordingly.\n\n"
    "Files without a matching `.json` file or those that cannot be located are marked as unprocessed "
    "and copied to a separate folder for review.\n\n"
    "Processed files are copied and modified based on their metadata, while unprocessed ones are logged.\n\n"
    "More details can be found in the README file.\n"
    "Git repository for this project: https://github.com/CrackinLLC/Photo-Export-Fixer\n"
)


def exists(path):  # check if path exists
    if path:
        return os.path.exists(path)
    else:
        return False


def get_unique_path(
    path, is_dir=False
):  # get unique path, to directory or file, if path exists, add number to it
    if is_dir:
        if not os.path.isdir(path):
            return path
        else:
            n = 1
            while os.path.isdir(f"{path}({n})"):
                n += 1
            path = f"{path}({n})"
        return path

    if not is_dir:
        if not os.path.isfile(path):
            return path
        else:
            path, ext = os.path.splitext(
                path
            )  # split path and extension to add number in the end of the filename before extension
            n = 1
            while os.path.isfile(f"{path}({n}){ext}"):
                n += 1
            path = f"{path}({n}){ext}"
        return path


def checkout_dir(
    path, onlynew=False
):  # check if directory exists, if not, create new. onlynew forces to create new repository in any case. Return is needed to give path to the new repository.
    if not os.path.isdir(path) and not onlynew:
        os.makedirs(path)
    elif onlynew:
        path = get_unique_path(path, is_dir=True)
        os.makedirs(path)
    return path


def get_file_names(
    path,
):  # get all files from all folders inside directory given and return them in structured form.
    content = os.walk(path)

    files = []
    jsons = []

    for dir_cont in content:
        for file in dir_cont[2]:
            if file.endswith(".json"):
                jsons.append(os.path.join(dir_cont[0], file))
            else:
                files.append(
                    {
                        "filename": file,
                        "filepath": os.path.join(dir_cont[0], file),
                        "albumname": get_album_name(os.path.join(dir_cont[0], file)),
                    }
                )

    # Build index for O(1) lookups: key = (albumname, filename)
    file_index = {}
    for file in files:
        key = (file["albumname"], file["filename"])
        if key not in file_index:
            file_index[key] = []
        file_index[key].append(file)

    return jsons, files, file_index


def unpack_json(path, savelogsto):  # get what needed from single json file.
    # Log the processing of the JSON file
    log_detail(savelogsto, f"Processing JSON file: {path}")
    if exists(path):
        try:
            # Open the JSON file and load its content
            with open(path, "r", encoding="utf-8") as file:
                content = json.load(file)
            # Check for required keys
            if (
                not content
                or "title" not in content
                or "photoTakenTime" not in content
                or "timestamp" not in content["photoTakenTime"]
            ):
                # If the required keys are missing, log the error and return None
                log_detail(
                    savelogsto, f"Invalid JSON structure in file, skipping: {path}"
                )
                return None
            # Extract the required information including metadata
            log_detail(savelogsto, f"Extracting data from JSON file: {path}")
            return {
                "filepath": path,
                "title": content["title"],
                "date": datetime.fromtimestamp(
                    int(content["photoTakenTime"]["timestamp"])
                ),
                "geoData": content.get("geoData"),
                "people": content.get("people"),
                "description": content.get("description", ""),
            }
        except Exception as e:
            log_detail(
                savelogsto, f"Error processing JSON file, error: {e}, skipping: {path}"
            )
            return None
    else:
        log_detail(savelogsto, f"JSON file does not exist, skipping: {path}")
        return None


def gener_names(
    filename, suffixes, album
):  # generate possible file names using suffixes provided.
    if filename["brackets"]:
        return [
            os.path.join(
                album,
                (filename["name"] + suf + filename["brackets"] + filename["extension"]),
            )
            for suf in suffixes
        ]
    else:
        return [
            os.path.join(album, (filename["name"] + suf + filename["extension"]))
            for suf in suffixes
        ]


def get_album_name(filepath):  # get name of the folder the file is in
    return os.path.basename(os.path.dirname(filepath))


def build_gps_tags(geo_data):
    """Convert Google's geoData to ExifTool tag dict."""
    if not geo_data or geo_data.get("latitude", 0) == 0:
        return {}

    lat = geo_data["latitude"]
    lon = geo_data["longitude"]
    alt = geo_data.get("altitude", 0)

    return {
        "GPSLatitude": abs(lat),
        "GPSLatitudeRef": "N" if lat >= 0 else "S",
        "GPSLongitude": abs(lon),
        "GPSLongitudeRef": "E" if lon >= 0 else "W",
        "GPSAltitude": abs(alt),
        "GPSAltitudeRef": 0 if alt >= 0 else 1,
    }


def build_people_tags(people_list):
    """Convert Google's people array to ExifTool tag dict."""
    if not people_list:
        return {}

    names = [p["name"] for p in people_list if "name" in p]
    if not names:
        return {}

    return {
        "PersonInImage": names,  # XMP-iptcExt (list for multiple)
        "Keywords": names,  # IPTC keywords
        "Subject": names,  # XMP-dc subject
        "XPKeywords": ";".join(names),  # Windows (semicolon-separated)
    }


def find_file(
    jsondata, file_index, suffixes
):  # get full path to the file using O(1) dictionary lookup
    name, ext = os.path.splitext(jsondata["title"])

    # Handle long filenames (Google truncates at 51 chars)
    if len(name + ext) > 51:
        name = name[0 : 51 - len(ext)]

    # Handle duplicate naming convention e.g., photo(1).jpg
    brackets = None
    if jsondata["filepath"].endswith(").json"):
        bracket_match = re.findall("\\([1-999]\\)\\.json", jsondata["filepath"])
        if bracket_match:
            brackets = bracket_match[-1][:-5]

    album_name = get_album_name(jsondata["filepath"])

    # Generate all possible filenames and check dictionary (O(1) lookup)
    for suffix in suffixes:
        if brackets:
            filename = name + suffix + brackets + ext
        else:
            filename = name + suffix + ext

        key = (album_name, filename)
        if key in file_index:
            return True, file_index[key]

    # Not found
    return False, [{"jsonpath": jsondata["filepath"], "title": jsondata["title"]}]


def copy_modify(
    file, date, copyto, geo_data=None, people=None, exiftool_helper=None, saveto=None
):
    """Copy file, set dates, and optionally write EXIF metadata."""

    copyto = checkout_dir(
        os.path.join(copyto, file["albumname"])
    )  # create directory for the copied file, if it does not exist

    new_file = get_unique_path(
        os.path.join(copyto, file["filename"])
    )  # get unique path to the new file, to not overwrite existing files

    shutil.copy(file["filepath"], new_file)

    filedate.File(new_file).set(created=date, modified=date)

    # Write EXIF metadata if ExifTool available
    if exiftool_helper:
        tags = {}
        tags.update(build_gps_tags(geo_data))
        tags.update(build_people_tags(people))

        if tags:
            try:
                exiftool_helper.set_tags(new_file, tags)
            except Exception as e:
                if saveto:
                    log_detail(
                        saveto, f"Warning: Could not write metadata to {new_file}: {e}"
                    )

    return new_file


def copy_unprocessed(
    unprocessed, saveto
):  # copy all files that were not returned during json-based search
    to_return = []
    for file in tqdm(unprocessed, desc="Copying"):
        # log the copying of unprocessed files
        log_detail(saveto, f"Copying unprocessed file: {file['filepath']}")
        new_file = get_unique_path(
            os.path.join(
                saveto,
                checkout_dir(os.path.join(saveto, "Unprocessed")),
                file["filename"],
            )
        )
        shutil.copy(file["filepath"], new_file)
        # log the successful copying of the unprocessed file
        log_detail(saveto, f"Successfully copied unprocessed file to: {new_file}\n")
        file["procpath"] = new_file
        to_return.append(file)
    return to_return  # return list with all unprocessed files, with path to the copied unmodified files


# Module-level log handle for buffered logging
_log_handle = None
_log_path = None


def init_logger(saveto):
    """Initialize the logger with a persistent file handle."""
    global _log_handle, _log_path
    _log_path = os.path.join(saveto, "detailed_logs.txt")
    _log_handle = open(_log_path, "a", encoding="utf-8")


def close_logger():
    """Close the log file handle."""
    global _log_handle
    if _log_handle:
        _log_handle.close()
        _log_handle = None


def log_detail(saveto, message):
    """Append a message to the detailed log file using buffered I/O."""
    global _log_handle
    if _log_handle:
        _log_handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    else:
        # Fallback to original behavior if logger not initialized
        with open(
            os.path.join(saveto, "detailed_logs.txt"), "a", encoding="utf-8"
        ) as logfile:
            logfile.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")


def savelogs(
    saveto, processed, unprocessed, unprocessed_jsons, endtime, startdate, enddate
):  # save everything that was done in separate file
    with open(os.path.join(saveto, "logs.txt"), "w", encoding="utf-8") as logfile:
        if processed:  # if any files were processed
            logfile.write("Processed files:\n\n")

        for file in processed:
            filename = file["filename"]
            filepath = file["filepath"]
            procpath = file["procpath"]
            jsonname = file["jsonpath"]
            time_ = file["time"]
            logfile.write(f"    {filename}:\n")
            logfile.write(f"        original file:     {filepath}\n")
            logfile.write(f"        destination file:  {procpath}\n")
            logfile.write(f"        source json:       {jsonname}\n")
            logfile.write(f"    time processed:        {time_}\n\n")

        if unprocessed_jsons:  # if any jsons were unprocessed
            logfile.write("Unprocessed jsons:\n\n")
        for file in unprocessed_jsons:
            filename = file["filename"]
            filepath = file["filepath"]
            title = file["title"]
            time_ = file["time"]
            logfile.write(f"    {filename}:\n")
            logfile.write(f"        original file:     {filepath}\n")
            logfile.write(
                f"        this json file did not find his pair among files: {title}\n"
            )
            logfile.write(f"    time processed:        {time_}\n\n")

        if unprocessed:  # if any files were unprocessed
            logfile.write("Unprocessed files:\n\n")
        for file in unprocessed:
            filename = file["filename"]
            filepath = file["filepath"]
            procpath = file["procpath"]
            logfile.write(f"    {filename}:\n")
            logfile.write(f"        original file:     {filepath}\n")
            logfile.write(f"        copied file:       {procpath}\n")
            logfile.write("        json-based search have not reached this file\n\n")

        logfile.write(f"Processed: {len(processed)} files\n")
        logfile.write(
            f"Unprocessed: {len(unprocessed)} files, {len(unprocessed_jsons)} jsons\n"
        )
        logfile.write(f"Time used: {endtime} seconds\n")
        logfile.write(f"Started: {startdate}\n")
        logfile.write(f"Ended:   {enddate}\n")


def dry_run_main(path, suffixes, destination):
    """Show what would be processed without making changes."""
    print("\n=== DRY RUN MODE ===")
    print("No files will be copied or modified.\n")

    if not exists(path):
        print(f"Error: Path does not exist: {path}")
        return

    print(f"Source: {path}")
    if destination:
        print(f"Destination: {destination}")
    else:
        print(f"Destination: {path}_pefProcessed")

    print("\nScanning files...")
    jsons, files, file_index = get_file_names(path)

    print("\nFound:")
    print(f"  {len(jsons)} JSON metadata files")
    print(f"  {len(files)} media files")

    # Count how many would match
    matched = 0
    unmatched_jsons = 0
    with_gps = 0
    with_people = 0

    for jsonpath in jsons:
        try:
            with open(jsonpath, "r", encoding="utf-8") as f:
                content = json.load(f)

            if not content or "title" not in content:
                unmatched_jsons += 1
                continue

            # Check if file would be found
            title = content["title"]
            name, ext = os.path.splitext(title)
            if len(name + ext) > 51:
                name = name[0 : 51 - len(ext)]

            brackets = None
            if jsonpath.endswith(").json"):
                bracket_match = re.findall("\\([1-999]\\)\\.json", jsonpath)
                if bracket_match:
                    brackets = bracket_match[-1][:-5]

            album_name = get_album_name(jsonpath)

            found = False
            for suffix in suffixes:
                if brackets:
                    filename = name + suffix + brackets + ext
                else:
                    filename = name + suffix + ext

                key = (album_name, filename)
                if key in file_index:
                    matched += 1
                    found = True
                    break

            if not found:
                unmatched_jsons += 1

            # Count metadata
            geo = content.get("geoData", {})
            if geo and geo.get("latitude", 0) != 0:
                with_gps += 1
            if content.get("people"):
                with_people += 1

        except Exception:
            unmatched_jsons += 1

    unmatched_files = len(files) - matched

    print("\nWould process:")
    print(f"  {matched} files with matching JSON")
    print(f"  {unmatched_jsons} JSONs without matching file")
    print(f"  {unmatched_files} files without matching JSON")

    print("\nMetadata available:")
    print(f"  {with_gps} files with GPS coordinates")
    print(f"  {with_people} files with people tags")

    if EXIFTOOL_AVAILABLE:
        exiftool_path = get_exiftool_path()
        if exiftool_path:
            print(f"\nExifTool: Found at {exiftool_path}")
        else:
            print("\nExifTool: Not found (GPS/people tags won't be written)")
    else:
        print("\nExifTool: pyexiftool not installed (GPS/people tags won't be written)")

    print("\n=== END DRY RUN ===")


def dry_run_extend(source_path, output_path, suffixes):
    """Show what metadata would be extended without making changes."""
    print("\n=== DRY RUN MODE (EXTEND) ===")
    print("No files will be modified.\n")

    if not exists(source_path):
        print(f"Error: Source path does not exist: {source_path}")
        return

    processed_path = os.path.join(output_path, "Processed")
    if not exists(processed_path):
        print(f"Error: Processed folder not found: {processed_path}")
        return

    print(f"Source JSONs: {source_path}")
    print(f"Target files: {processed_path}")

    print("\nScanning...")
    jsons, _, _ = get_file_names(source_path)
    _, processed_files, file_index = get_file_names(processed_path)

    print(f"  {len(jsons)} JSON files in source")
    print(f"  {len(processed_files)} files in processed folder")

    would_update = 0
    would_skip = 0
    with_gps = 0
    with_people = 0

    for jsonpath in jsons:
        try:
            with open(jsonpath, "r", encoding="utf-8") as f:
                content = json.load(f)

            if not content or "title" not in content:
                would_skip += 1
                continue

            # Check for metadata
            geo = content.get("geoData", {})
            has_gps = geo and geo.get("latitude", 0) != 0
            has_people = bool(content.get("people"))

            if not has_gps and not has_people:
                would_skip += 1
                continue

            # Check if matching file exists
            title = content["title"]
            name, ext = os.path.splitext(title)
            if len(name + ext) > 51:
                name = name[0 : 51 - len(ext)]

            brackets = None
            if jsonpath.endswith(").json"):
                bracket_match = re.findall("\\([1-999]\\)\\.json", jsonpath)
                if bracket_match:
                    brackets = bracket_match[-1][:-5]

            album_name = get_album_name(jsonpath)

            found = False
            for suffix in suffixes:
                if brackets:
                    filename = name + suffix + brackets + ext
                else:
                    filename = name + suffix + ext

                key = (album_name, filename)
                if key in file_index:
                    would_update += 1
                    if has_gps:
                        with_gps += 1
                    if has_people:
                        with_people += 1
                    found = True
                    break

            if not found:
                would_skip += 1

        except Exception:
            would_skip += 1

    print(f"\nWould update: {would_update} files")
    print(f"Would skip: {would_skip} (no metadata or no match)")
    print("\nMetadata to write:")
    print(f"  {with_gps} with GPS coordinates")
    print(f"  {with_people} with people tags")

    print("\n=== END DRY RUN ===")


def extend_metadata(source_path, output_path, suffixes):
    """Add metadata to already-processed files without re-copying them."""
    print("\nExtend mode: Adding metadata to already-processed files...")

    if not EXIFTOOL_AVAILABLE:
        print("Error: pyexiftool not installed. Run 'pip install pyexiftool'")
        return

    exiftool_path = get_exiftool_path()
    if not exiftool_path:
        return

    # Check paths exist
    if not exists(source_path):
        print(f"Error: Source path does not exist: {source_path}")
        return

    processed_path = os.path.join(output_path, "Processed")
    if not exists(processed_path):
        print(f"Error: Processed folder not found: {processed_path}")
        return

    # Get all JSONs from source and all files from output
    print(f"Scanning source: {source_path}")
    jsons, _, _ = get_file_names(source_path)
    print(f"Found {len(jsons)} JSON files")

    print(f"Scanning output: {processed_path}")
    _, processed_files, file_index = get_file_names(processed_path)
    print(f"Found {len(processed_files)} processed files")

    # Statistics
    updated = 0
    skipped = 0
    errors = 0

    # Log file for debugging
    log_path = os.path.join(os.path.dirname(__file__), "extend_debug.log")
    print(f"Logging to: {log_path}", flush=True)

    total = len(jsons)
    with open(log_path, "w", encoding="utf-8") as logfile:
        logfile.write(f"Starting extend: {total} JSON files to process\n")
        logfile.flush()

        with exiftool.ExifToolHelper(executable=exiftool_path) as et:
            logfile.write("ExifTool started successfully\n")
            logfile.flush()

            for i, jsonpath in enumerate(tqdm(jsons, desc="Extending metadata")):
                # Print and log progress every 100 files
                if i % 100 == 0:
                    msg = f"Progress: {i}/{total} ({i * 100 // total}%) - Updated: {updated}, Skipped: {skipped}, Errors: {errors}"
                    print(f"\n  {msg}", flush=True)
                    logfile.write(f"{msg}\n")
                    logfile.flush()
                try:
                    # Read JSON file directly for full data
                    with open(jsonpath, "r", encoding="utf-8") as f:
                        content = json.load(f)

                    if not content or "title" not in content:
                        skipped += 1
                        continue

                    # Build tags
                    tags = {}
                    tags.update(build_gps_tags(content.get("geoData")))
                    tags.update(build_people_tags(content.get("people")))

                    if not tags:
                        skipped += 1
                        continue

                    # Find matching processed file using same logic as find_file
                    title = content["title"]
                    name, ext = os.path.splitext(title)

                    if len(name + ext) > 51:
                        name = name[0 : 51 - len(ext)]

                    brackets = None
                    if jsonpath.endswith(").json"):
                        bracket_match = re.findall("\\([1-999]\\)\\.json", jsonpath)
                        if bracket_match:
                            brackets = bracket_match[-1][:-5]

                    album_name = get_album_name(jsonpath)

                    # Try each suffix
                    found = False
                    for suffix in suffixes:
                        if brackets:
                            filename = name + suffix + brackets + ext
                        else:
                            filename = name + suffix + ext

                        key = (album_name, filename)
                        if key in file_index:
                            for match in file_index[key]:
                                try:
                                    et.set_tags(match["filepath"], tags)
                                    updated += 1
                                    found = True
                                except Exception as e:
                                    errors += 1
                                    logfile.write(
                                        f"ERROR setting tags on {match['filepath']}: {e}\n"
                                    )
                                    logfile.flush()
                            break

                    if not found:
                        skipped += 1

                except Exception as e:
                    errors += 1
                    logfile.write(f"ERROR processing {jsonpath}: {e}\n")
                logfile.flush()

        logfile.write(
            f"Completed: Updated={updated}, Skipped={skipped}, Errors={errors}\n"
        )

    print("\nExtend complete!")
    print(f"  Updated: {updated} files")
    print(f"  Skipped: {skipped} (no metadata or no match)")
    print(f"  Errors: {errors}")


def main(
    path, suffixes, destination, write_exif=True
):  # main function, where everything is being done
    start_time = (
        time.time()
    )  # saving current time to return time program ran in the end
    start_date = time.strftime("%Y-%m-%d %H:%M:%S")

    # log lists:
    processed = []
    unprocessed = []
    unprocessed_jsons = []

    # check if path provided exists:
    if not exists(path):
        print("Sorry, path you provided does not exist")
        return

    if not destination:  # if destination is not provided, create destination
        # creating new folder for all modified files
        saveto = checkout_dir(path + "_pefProcessed", onlynew=True)
    else:  # if destination is provided, use it directly
        if not exists(destination):
            print(f"Destination {destination} does not exist, creating it...")
        saveto = checkout_dir(destination, onlynew=True)

    # Initialize ExifTool if metadata writing is enabled
    exiftool_helper = None
    if write_exif and EXIFTOOL_AVAILABLE:
        exiftool_path = get_exiftool_path()
        if exiftool_path:
            try:
                exiftool_helper = exiftool.ExifToolHelper(executable=exiftool_path)
                exiftool_helper.run()
                print("ExifTool initialized - will write GPS and people metadata")
            except Exception as e:
                print(f"Warning: Could not initialize ExifTool: {e}")
                print("Continuing without metadata writing...")
                exiftool_helper = None
    elif write_exif and not EXIFTOOL_AVAILABLE:
        print(
            "Note: pyexiftool not installed. Run 'pip install pyexiftool' to enable metadata writing."
        )

    # let people know, what you work with
    print("\nProcess started...")
    print(f"\nWorking in directory {path}")

    # get lists with json files and non-json files, plus index for fast lookup
    jsons, files, file_index = get_file_names(path)

    # Initialize buffered logger
    init_logger(saveto)

    # adding first line to the detailed_logs.txt file
    log_detail(saveto, f"Started processing directory: {path}\n")

    # main loop: (tqdm is for dynamic progress bar in terminal)
    for jsonpath in tqdm(jsons, desc="Files processed"):
        # get everithing from json:
        jsondata = unpack_json(jsonpath, saveto)

        if not jsondata:
            unprocessed_jsons.append(
                {
                    "filename": os.path.basename(jsonpath),
                    "filepath": jsonpath,
                    "title": "Title is missing",
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            # log the scipping of the JSON file
            log_detail(saveto, f"Skipping JSON file in the main loop: {jsonpath}\n")
            continue  # if json is empty, skip it

        # look for file pair based on json data
        # log the search for the file pairs based on json data
        log_detail(
            saveto,
            f'Searching for file pairs based on "title" from JSON: {jsondata["title"]}',
        )
        exist, files_ = find_file(jsondata, file_index, suffixes)
        for file in files_:
            if exist:
                # copy and modify file, if found
                # log the copying and modification of the file
                log_detail(saveto, f"Copying and modifying file: {file['filepath']}")
                procpath = copy_modify(
                    file,
                    jsondata["date"],
                    checkout_dir(os.path.join(saveto, "Processed")),
                    geo_data=jsondata.get("geoData"),
                    people=jsondata.get("people"),
                    exiftool_helper=exiftool_helper,
                    saveto=saveto,
                )
                # save path to modified file
                file["procpath"] = procpath
                file["jsonpath"] = jsonpath
                file["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                # log the successful processing of the file
                log_detail(saveto, f"Successfully processed file: {file['filename']}\n")
                processed.append(file)
            else:
                # log the unprocessed JSON file
                log_detail(
                    saveto,
                    f"Unprocessed JSON file, no pair found for: {file['jsonpath']}\n",
                )
                # add info about jsons which have not found any pair, to present it in logs
                unprocessed_jsons.append(
                    {
                        "filename": os.path.basename(file["jsonpath"]),
                        "filepath": file["jsonpath"],
                        "title": file["title"],
                        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

    print("\nWorking with unprocessed files...")

    # log the processing of unprocessed files
    log_detail(saveto, "Processing unprocessed files...\n")
    # make list of files, which have not been processed, based by list of all files and processed ones, and that save name and path separately not to extract it every time needed
    unprocessed = [
        {"filename": os.path.basename(file), "filepath": file}
        for file in tqdm(
            list(
                set([file["filepath"] for file in files])
                - set([file["filepath"] for file in processed])
            ),
            desc="Analizing",
        )
    ]

    print("\nFinal steps with unprocessed files...")
    # copy unprocessed jsons and files to separate folder, to not lose any file
    if unprocessed_jsons:
        unprocessed_jsons = copy_unprocessed(unprocessed_jsons, saveto)
    if unprocessed:
        unprocessed = copy_unprocessed(unprocessed, saveto)

    # calculate time, needed for program
    end_time = round(time.time() - start_time, 3)
    end_date = time.strftime("%Y-%m-%d %H:%M:%S")

    # log the end of the processing
    log_detail(
        saveto,
        f"Finished processing directory: {path}, readable logs are in {saveto}/logs.txt",
    )

    # Close the buffered logger
    close_logger()

    # Close ExifTool if it was initialized
    if exiftool_helper:
        try:
            exiftool_helper.terminate()
        except Exception:
            pass

    # create and save logs into separate file inside "saveto" folder
    savelogs(
        saveto,
        processed,
        unprocessed,
        unprocessed_jsons,
        end_time,
        start_date,
        end_date,
    )

    print("\nFinished!")
    print(f"Processed {len(processed)} files")
    print(f"Unprocessed: {len(unprocessed)} files, {len(unprocessed_jsons)} jsons")
    print(f"Time used: {end_time} seconds")
    procpath = os.path.join(saveto, "Processed")
    print(f"\nFolder with processed files:\n{procpath}")
    unprocpath = os.path.join(saveto, "Unprocessed")
    print(f"Folder with unprocessed files:\n{unprocpath}")
    print(f"Logs are saved in {saveto}/logs.txt")
    print(f"Detailed logs are saved in {saveto}/detailed_logs.txt\n")


def wizard():  # wizard mode, if user have not given the argument before running
    print(
        "\nYou have not given arguments needed, so you have been redirected to the Wizard setup"
    )
    try:
        path = input("Enter path to your folder with takeouts: ")
        return path
    except Exception:
        pass


def parse(
    description,
):  # start point of the program, where variable "path" is being created
    suffixes = [
        "",
        "-edited",
    ]  # text google can add to the name of the file and without making separate json
    # this means that file cat.png and cat-edited.png have only one json - cat.png.supplemental-metadata.json

    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-p",
        "--path",
        help="The full path to the repository containing Takeout folders",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-d",
        "--destination",
        help="The directory where the processed files will be saved",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-s",
        "--suffix",
        action="append",
        help="Additional suffixes you want to add",
        type=str,
        default=suffixes,
    )
    parser.add_argument(
        "-e",
        "--extend",
        help="Extend metadata on already-processed files (looks for <source>_pefProcessed)",
        action="store_true",
    )
    parser.add_argument(
        "--no-exif",
        help="Skip EXIF metadata writing (faster, timestamps only)",
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        help="Show what would be done without making changes",
        action="store_true",
    )

    args = parser.parse_args()

    if not args.path:
        path = wizard()
    else:
        path = args.path

    # Normalize paths to handle trailing slashes, mixed slashes, whitespace, etc.
    if path:
        path = os.path.normpath(os.path.expanduser(path.strip()))

    suffixes = args.suffix
    destination = args.destination
    if destination:
        destination = os.path.normpath(os.path.expanduser(destination.strip()))

    # Handle extend mode
    if args.extend:
        # Find processed folder automatically
        if destination:
            extend_path = destination
        else:
            extend_path = path + "_pefProcessed"

        if not exists(extend_path):
            print(f"Error: Processed folder not found at: {extend_path}")
            print(
                "Make sure you've run the main processing first, or specify --destination if you used a custom output location."
            )
            return

        if args.dry_run:
            dry_run_extend(path, extend_path, suffixes)
        else:
            extend_metadata(path, extend_path, suffixes)
    elif args.dry_run:
        dry_run_main(path, suffixes, destination)
    else:
        main(path, suffixes, destination, write_exif=not args.no_exif)


if __name__ == "__main__":  # run the program
    parse(description)

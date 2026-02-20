# Photo Export Fixer (PEF)

When you export your photos from Google Photos using [Google Takeout](https://takeout.google.com/), the metadata (dates, GPS coordinates, people tags) gets stored in separate `.json` files instead of being embedded in the images. This means your photos show incorrect dates, have no location info, and lose their people tags when you import them anywhere else.

Photo Export Fixer reads those JSON sidecar files and applies the metadata back to your actual photos and videos. Your originals are never modified -- everything gets copied to a new output folder with corrected dates, embedded GPS coordinates, and people tags written in standard formats that any photo app can read.

## Table of Contents

- [Installation](#installation)
- [Using the GUI](#using-the-gui)
- [Using the Command Line](#using-the-command-line)
- [Preparing Your Google Takeout](#preparing-your-google-takeout)
- [What Gets Fixed](#what-gets-fixed)
- [Output Structure](#output-structure)
- [Resuming Interrupted Processing](#resuming-interrupted-processing)
- [Motion Photos](#motion-photos)
- [The Suffix System](#the-suffix-system)
- [Verifying Results](#verifying-results)
- [Troubleshooting](#troubleshooting)
- [Python API](#python-api)
- [Contributing](#contributing)
- [License](#license)

## Installation

**Requires Python 3.9 or later.**

```bash
git clone https://github.com/CrackinLLC/Photo-Export-Fixer.git
cd Photo-Export-Fixer
pip install -r requirements.txt
```

### ExifTool (optional but recommended)

ExifTool is needed to embed GPS coordinates and people tags into your photos. Without it, PEF still fixes file dates -- you just won't get location or people metadata written into the files.

| Platform | How to install |
|----------|----------------|
| Windows  | Nothing to do -- PEF downloads it automatically on first run |
| macOS    | `brew install exiftool` |
| Linux    | `sudo apt install libimage-exiftool-perl` |

## Using the GUI

The GUI is the easiest way to use PEF. Launch it with:

```bash
python pef_gui.py
```

Or equivalently:

```bash
python pef.py --gui
```

> **Linux users:** You may need to install tkinter first: `sudo apt install python3-tk`

### Step-by-step walkthrough

**1. Select your source directory**

Click **Browse** next to "Source Directory" and navigate to the folder containing your extracted Google Takeout files. This should be the folder that contains subfolders like `Google Photos/`, album folders, and the `.json` sidecar files.

**2. Set a destination (optional)**

The destination defaults to `<source folder>_processed`. You can change it or leave it blank. The folder will be created if it doesn't exist.

**3. Click Preview (recommended)**

Before processing anything, click the **Preview** button. PEF will scan your source folder and show you a summary:

```
Found:
  5,234 JSON metadata files
  5,108 media files

Would process:
  5,100 files with matching metadata
  134 JSONs without matching file
  8 files without matching JSON

Metadata available:
  3,205 files with GPS coordinates
  2,456 files with people tags

ExifTool: Enabled (will write GPS/people tags)
```

This reads your files without copying or modifying anything. Use it to confirm PEF found your Takeout data correctly before committing to a full run.

**4. Click Start**

PEF will confirm the destination path, then begin processing. You'll see a progress view showing:

- Current phase (Scanning, Processing, Copying unmatched)
- A progress bar with file count and percentage
- Elapsed time per phase and total

When processing completes, a summary dialog shows the results and offers to open the output folder.

### Advanced options

Click **Advanced Options** in the GUI to expand additional settings:

| Option | What it does |
|--------|-------------|
| **Write EXIF metadata** | Embed GPS coordinates and people tags into files. Requires ExifTool. Enabled by default when ExifTool is available. |
| **Start fresh** | Ignore any saved progress from a previous interrupted run and start over. |
| **Verbose logging** | Log every operation to `_pef/verbose.txt`, not just errors. Useful for debugging. |
| **Rename .MP to .MP4** | Rename motion photo sidecar files from `.MP` to `.MP4` for better compatibility with video players (e.g., Immich). |

The GUI also shows the current ExifTool status. On Windows, if ExifTool isn't found, you can click **Install** to download it automatically. On macOS/Linux, a **How to Install** button shows platform-specific instructions.

### Cancelling and resuming

You can click **Cancel** during processing. PEF will save your progress, and you can resume later by clicking **Start** again with the same source and destination. If cancellation takes too long (more than 30 seconds), a **Force Quit** button appears.

If you close the window during processing, progress is saved automatically.

## Using the Command Line

### Basic usage

```bash
python pef.py --path "/path/to/your/takeout"
```

Output goes to `<source>_processed` by default. To specify a destination:

```bash
python pef.py --path "/path/to/your/takeout" --destination "/path/to/output"
```

If you run without arguments, PEF prompts you for the path interactively:

```bash
python pef.py
# Enter path to your folder with takeouts: _
```

### Preview before processing

```bash
python pef.py --path "/path/to/your/takeout" --dry-run
```

Output:

```
=== DRY RUN MODE ===
No files will be copied or modified.

Source: /path/to/your/takeout
Found:
  5,234 JSON metadata files
  5,108 media files

Would process:
  5,100 files with matching JSON
  134 JSONs without matching file
  8 files without matching JSON

Metadata available:
  3,205 files with GPS coordinates
  2,456 files with people tags

ExifTool: Found at /usr/local/bin/exiftool
=== END DRY RUN ===
```

### All CLI options

```
python pef.py --help

Options:
  -p, --path PATH          Source folder containing Takeout data
  -d, --destination PATH   Output folder (default: <source>_processed)
  -s, --suffix SUFFIX      Extra filename suffixes to match (repeatable)
  --dry-run                Preview without making changes
  --no-exif                Skip GPS/people embedding (faster, dates still fixed)
  --rename-mp              Rename .MP motion photo files to .MP4
  --force                  Ignore saved progress, start fresh
  -v, --verbose            Log all operations, not just errors
  -V, --version            Show version number
  --gui                    Launch the graphical interface instead
```

### CLI examples

Process a Takeout export, skipping EXIF writing for speed:

```bash
python pef.py --path "D:/Photos/Takeout" --no-exif
```

Process with an additional suffix for sticker variants:

```bash
python pef.py --path "D:/Photos/Takeout" -s "-sticker"
```

Resume a previously interrupted run:

```bash
# Same command as before -- PEF detects saved progress automatically
python pef.py --path "D:/Photos/Takeout"
```

Force a fresh start, ignoring saved progress:

```bash
python pef.py --path "D:/Photos/Takeout" --force
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Error (bad path, invalid arguments, or cancelled wizard) |
| 2    | Completed with some file-level errors |
| 130  | Interrupted by Ctrl+C (progress saved) |

## Preparing Your Google Takeout

1. Go to [Google Takeout](https://takeout.google.com/)
2. Click **Deselect all**, then scroll down and select only **Google Photos**
3. Choose your preferred export format and file size (`.zip`, 2GB chunks is common)
4. Google will email you download links when the export is ready
5. Download all zip files
6. Extract everything into a single folder
7. Point PEF at that folder

The folder structure from Takeout typically looks something like:

```
My Takeout/
├── Google Photos/
│   ├── Album Name/
│   │   ├── photo.jpg
│   │   ├── photo.jpg.json
│   │   ├── photo-edited.jpg
│   │   └── ...
│   ├── Photos from 2023/
│   │   └── ...
│   └── ...
```

Point PEF at the top-level folder that contains everything.

**Tip:** Keep only photo-related content in the source folder. Other files won't cause problems, but they'll slow down scanning and show up in the unprocessed report.

## What Gets Fixed

For each photo/video that has a matching JSON sidecar:

| Metadata | Where it comes from | Where it gets written |
|----------|--------------------|-----------------------|
| **Date taken** | `photoTakenTime.timestamp` in JSON | File creation and modification timestamps |
| **GPS coordinates** | `geoData.latitude/longitude/altitude` in JSON | EXIF GPS tags (`GPSLatitude`, `GPSLongitude`, etc.) |
| **People tags** | `people[].name` in JSON | Written to four formats for broad compatibility: XMP `PersonInImage`, IPTC `Keywords`, XMP `Subject`, and Windows `XPKeywords` |
| **Description** | `description` in JSON | EXIF `ImageDescription`, IPTC `Caption-Abstract`, XMP `Description` |

GPS and people tags require ExifTool. Date correction works without it.

### Google Takeout quirks PEF handles

- **Filename truncation:** Google truncates filenames at 51 UTF-8 bytes, sometimes splitting multi-byte characters. PEF uses byte-aware matching to handle this.
- **Duplicate numbering:** When multiple files share a name, Google appends `(1)`, `(2)`, etc. to the JSON filename but places the number differently in the media filename. PEF handles both conventions.
- **Edited variants:** `photo.jpg` and `photo-edited.jpg` share a single `photo.jpg.json`. PEF finds all variants and applies the same metadata to each.
- **GPS placeholder (0, 0):** Google uses coordinates `(0.0, 0.0)` to mean "no location data." PEF recognizes this and skips writing GPS tags for these files.
- **Unicode normalization:** macOS and Windows use different Unicode representations (NFD vs NFC). PEF normalizes all filenames to NFC for consistent cross-platform matching.
- **Case mismatches:** If a JSON refers to `IMG_1234.JPG` but the file is `IMG_1234.jpg`, PEF will still match them.

## Output Structure

```
YourTakeout_processed/
├── Album Name/
│   ├── photo1.jpg              # dates corrected, GPS + people embedded
│   ├── photo2.jpg
│   └── video.mp4
├── Photos from 2023/
│   └── ...
├── Trip to Iceland/
│   └── ...
└── _pef/
    ├── summary.txt             # what happened (always created)
    ├── verbose.txt             # detailed per-file log (with --verbose)
    ├── unprocessed.txt         # files without matching metadata
    ├── motion_photos.txt       # info about .MP sidecar files
    ├── processing_state.json   # saved progress for resume
    └── unmatched_data/         # JSON files with no matching media
        └── ...
```

All files are copied to the output folder -- both matched and unmatched -- preserving the original album/folder structure. Your source folder is never modified.

After a run, check `_pef/summary.txt` for an overview and `_pef/unprocessed.txt` if you want to understand which files didn't have matching metadata.

## Resuming Interrupted Processing

PEF saves progress during processing. If the operation gets interrupted (Ctrl+C, closing the window, power failure), run the same command or click Start again and PEF picks up where it left off:

```bash
# First attempt -- interrupted partway through
python pef.py --path "/path/to/takeout"
# Interrupted! Saving progress...

# Later -- same command resumes automatically
python pef.py --path "/path/to/takeout"
# Resuming: 2,500 files already processed
# Continues from where it stopped...
```

In the GUI, the progress view shows a "Prior session progress" line indicating how many files were processed in the previous run.

To discard saved progress and start over, use `--force` on the CLI or check **Start fresh** in the GUI's Advanced Options.

## Motion Photos

Google Photos captures short video clips alongside still images and stores them as `.MP` or `.MP~2` files. These don't have their own JSON metadata -- they're associated with the parent image.

PEF copies these files alongside your photos and lists them in `_pef/motion_photos.txt`. If you're importing into a platform that doesn't recognize `.MP` files (like Immich), use the **Rename .MP to .MP4** option:

```bash
python pef.py --path "/path/to/takeout" --rename-mp
```

## The Suffix System

Google sometimes creates multiple versions of a photo that share a single JSON file. For example, `photo.jpg` and `photo-edited.jpg` both use `photo.jpg.json` for their metadata.

By default, PEF handles `""` (original filename) and `"-edited"`. When a JSON file is processed, PEF finds all matching variants and applies the same metadata to each.

If you see files in `_pef/unprocessed.txt` with a consistent pattern like `photo-sticker.jpg`, you can add that suffix:

```bash
python pef.py --path "/path/to/takeout" -s "-sticker"
```

Multiple suffixes can be combined:

```bash
python pef.py --path "/path/to/takeout" -s "-sticker" -s "-effects"
```

**Be careful:** only add suffixes you've actually confirmed in your export. An incorrect suffix could cause the wrong metadata to be applied to an unrelated file.

## Verifying Results

After processing, you can confirm that metadata was applied correctly:

1. **Check the summary:** Open `_pef/summary.txt` in the output folder. It shows total files processed, how many got GPS data, how many got people tags, and any errors.

2. **Check file dates:** Browse the output folder and sort by date. Photos should now show their original taken date instead of the export date.

3. **Check GPS data:** Open a photo that should have location info in any photo viewer that displays EXIF data (Windows: right-click > Properties > Details; macOS: Preview > Tools > Show Inspector). Look for GPS Latitude/Longitude fields.

4. **Review unprocessed files:** Open `_pef/unprocessed.txt` to see which files didn't have matching metadata. Common reasons:
   - No matching JSON (Google didn't provide metadata for this file)
   - Motion photo sidecar (`.MP` files don't have their own JSON)
   - Album metadata JSON (describes the album, not a specific file)
   - Files from a split export where the JSON is in a different zip

## Troubleshooting

### "No JSON metadata files found"

PEF didn't find any `.json` files in the source directory. Make sure you're pointing at the extracted Takeout contents, not the zip file itself. The source folder should contain subfolders with `.json` files alongside the photos.

### Many files in unprocessed.txt

This is normal for Takeout exports. Check the file for patterns:
- If many share a suffix like `-sticker`, add it with `-s "-sticker"` and reprocess.
- If they're `.MP` files, those are motion photo sidecars and are expected.
- If they're from a split Takeout download, make sure all zip files were extracted into the same folder.

### ExifTool not found (Windows)

PEF tries to download ExifTool automatically on Windows. If that fails (usually a network issue):
1. Download manually from [exiftool.org](https://exiftool.org/)
2. Place the `exiftool.exe` file in `./tools/exiftool/` inside the PEF directory
3. Restart PEF

### ExifTool not found (macOS / Linux)

Install via your package manager:
```bash
# macOS
brew install exiftool

# Ubuntu/Debian
sudo apt install libimage-exiftool-perl

# Fedora
sudo dnf install perl-Image-ExifTool
```

### "File not found" errors with long paths (Windows)

Windows has a 260-character path limit by default. PEF handles this automatically by using extended-length path prefixes, but you can also enable long path support system-wide:

**Option A:** Registry (requires admin + restart):
1. Open **regedit**
2. Navigate to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem`
3. Set `LongPathsEnabled` to `1`
4. Restart your computer

**Option B:** PowerShell (requires admin):
```powershell
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1
```

### Processing seems slow

- Use `--no-exif` (CLI) or uncheck **Write EXIF metadata** (GUI) if you only need date correction. Skipping EXIF writing is significantly faster.
- Avoid running from network drives -- local SSDs are much faster for this workload.
- Large collections (50,000+ files) will naturally take a while. PEF uses parallel file copying and batched metadata writes to keep things moving.

### Files have wrong dates after processing

Usually means a suffix matched files it shouldn't have. Be conservative with `-s` flags -- only add patterns you've confirmed in your export. You can reprocess with `--force` after removing the problematic suffix.

## Python API

PEF can be used as a library in your own Python scripts:

```python
from pef import PEFOrchestrator

orchestrator = PEFOrchestrator(
    source_path="/path/to/takeout",
    dest_path="/path/to/output",
    write_exif=True,
    verbose=False,
    rename_mp=False,
)

# Preview first
result = orchestrator.dry_run()
print(f"Found {result.matched_count} files to process")
print(f"  {result.with_gps} with GPS, {result.with_people} with people tags")

# Process
result = orchestrator.process()
print(f"Processed {result.stats.processed} files")
```

The `process()` method accepts an `on_progress` callback for tracking progress and a `cancel_event` (`threading.Event`) for cooperative cancellation.

## Requirements

- **Python 3.9+**
- **Dependencies** (installed via `pip install -r requirements.txt`):
  - `filedate` -- cross-platform file timestamp modification
  - `pyexiftool` -- Python wrapper for ExifTool
  - `tqdm` -- CLI progress bars
  - `orjson` -- fast JSON parsing (falls back to stdlib `json` if unavailable)
- **ExifTool** (optional) -- for GPS and people tag embedding

## Contributing

Found a bug or have a feature request?

- [Open an issue](https://github.com/CrackinLLC/Photo-Export-Fixer/issues)
- Fork, branch, and submit a PR

To run the test suite:

```bash
pip install -r requirements.txt
pytest
```

## License

MIT License. See [LICENSE](LICENSE) for details.

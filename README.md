# Photo Export Fixer (PEF)

Google Takeout exports your photos with metadata stored in separate JSON files rather than embedded in the images themselves. This means your photos often show up with incorrect dates, no GPS coordinates, and missing people tags when imported into other applications.

**Photo Export Fixer** reads Google's JSON sidecar files and applies that metadata to your actual photos and videos—fixing creation dates, embedding GPS coordinates, and adding people tags. Your files come out organized, properly dated, and with metadata embedded in standard formats that any photo application can read.

## What It Does

- **Fixes dates** — Sets file creation/modification timestamps from Google's metadata
- **Embeds GPS coordinates** — Writes location data into EXIF so any photo app can read it
- **Embeds people tags** — Face recognition names get written to standard XMP fields
- **Preserves your folder structure** — Albums stay as albums
- **Handles Google's quirks** — Deals with truncated filenames, `-edited` variants, duplicate naming, and other Takeout oddities
- **Never touches your originals** — Everything gets copied to a new folder

## Quick Start

```bash
# Clone and install
git clone https://github.com/CrackinLLC/Photo-Export-Fixer.git
cd Photo-Export-Fixer
pip install -r requirements.txt

# Run it
python pef.py --path "/path/to/your/takeout"
```

Your processed files end up in a new folder next to your source, named `<source>_processed`.

## Installation

**Python 3.9+** required.

```bash
git clone https://github.com/CrackinLLC/Photo-Export-Fixer.git
cd Photo-Export-Fixer
pip install -r requirements.txt
```

For GPS and people tag embedding, you'll also need **ExifTool**:

| Platform | Installation                                    |
| -------- | ----------------------------------------------- |
| Windows  | Automatic—downloaded on first run to `./tools/` |
| macOS    | `brew install exiftool`                         |
| Linux    | `sudo apt install libimage-exiftool-perl`       |

If ExifTool isn't available, dates still get fixed—you just won't get the embedded GPS/people metadata.

## Usage

### Basic Processing

```bash
python pef.py --path "/path/to/takeout"
```

Or run without arguments for an interactive prompt:

```bash
python pef.py
# → Enter path to your folder with takeouts:
```

### Preview First (Recommended)

Before processing a large collection, preview what will happen:

```bash
python pef.py --path "/path/to/takeout" --dry-run
```

Output:

```
=== DRY RUN MODE ===
No files will be copied or modified.

Source: /path/to/takeout
Found:
  5234 JSON metadata files
  5108 media files

Would process:
  5100 files with matching JSON
  134 JSONs without matching file
  8 files without matching JSON

Metadata available:
  3205 files with GPS coordinates
  2456 files with people tags

ExifTool: Found at /usr/local/bin/exiftool
=== END DRY RUN ===
```

### All Options

```
python pef.py --help

Options:
  -p, --path PATH          Source folder containing Takeout data
  -d, --destination PATH   Output folder (default: <source>_processed)
  -s, --suffix SUFFIX      Extra filename suffixes to match (can repeat)
  --dry-run                Preview without making changes
  --no-exif                Skip GPS/people embedding (faster)
  --rename-mp              Rename .MP motion photo files to .MP4
  --force                  Ignore saved progress, start fresh
  -v, --verbose            Log all operations, not just errors
  -V, --version            Show version
```

## Resumable Processing

If processing gets interrupted, run the same command again and PEF picks up where it left off.

```bash
# Started processing, hit Ctrl+C halfway through
python pef.py --path "/path/to/takeout"
# "Interrupted! Saving progress..."

# Later, run the same command
python pef.py --path "/path/to/takeout"
# "Resuming: 2500 files already processed"
# Continues from where it stopped...
```

To start fresh instead of resuming, use `--force`:

```bash
python pef.py --path "/path/to/takeout" --force
```

## Output Structure

After processing:

```
YourTakeout_processed/
├── Album Name/
│   ├── photo1.jpg           (with corrected dates + embedded metadata)
│   ├── photo2.jpg
│   └── video.mp4
├── Photos from 2019/
│   └── ...
├── Trip to Iceland/
│   └── ...
└── _pef/
    ├── summary.txt          (processing summary)
    ├── verbose.txt          (detailed log, only with --verbose)
    ├── unprocessed.txt      (files without matching metadata)
    ├── motion_photos.txt    (info about .MP sidecar files)
    ├── unmatched_data/      (JSON files that didn't match any media)
    │   └── ...
    └── processing_state.json (for resume capability)
```

All files—both matched and unmatched—are copied to the output directory, preserving the original album/folder structure. Files without matching JSON metadata are listed in `_pef/unprocessed.txt` so you can review them.

## Motion Photos

Google Photos stores motion photos (short video clips captured with still images) as separate `.MP` files alongside the `.jpg`. These files don't have their own JSON metadata—they're associated with the parent image.

PEF copies these files alongside your photos. If you're importing to a platform that doesn't recognize the `.MP` extension, use `--rename-mp` to rename them to `.MP4`:

```bash
python pef.py --path "/path/to/takeout" --rename-mp
```

Motion photo files found during processing are listed in `_pef/motion_photos.txt`.

## The Suffix System

Google sometimes creates multiple versions of a photo that share a single JSON file. For example, `photo.jpg` and `photo-edited.jpg` both use `photo.jpg.json` for their metadata.

By default, PEF handles `""` (original) and `"-edited"`. When a JSON file is processed, all matching variants receive the same metadata.

If you notice files in `_pef/unprocessed.txt` with patterns like `photo-sticker.jpg`, you can add that suffix:

```bash
python pef.py --path "/path/to/takeout" -s "-sticker"
```

Multiple suffixes can be specified:

```bash
python pef.py --path "/path/to/takeout" -s "-sticker" -s "-effects"
```

**Note:** Only add suffixes you've actually verified in your export. Adding incorrect suffixes can cause wrong metadata to be applied to unrelated files.

## Why Files End Up Unprocessed

Files appear in `_pef/unprocessed.txt` when:

1. **No matching JSON** — The file exists but Google didn't provide metadata for it
2. **JSON exists, file doesn't** — Metadata refers to a file that's missing (sometimes happens with split exports)
3. **Album metadata** — Some JSONs describe the album itself, not a specific file
4. **Motion photo sidecars** — `.MP` files don't have their own JSON
5. **Filename encoding issues** — Files with special characters sometimes get mangled during export

Review `_pef/unprocessed.txt` after a run. If you see patterns (many `-sticker` files, for example), consider adding that suffix and reprocessing.

## How It Works

1. **Scans** your Takeout folder for all JSON metadata files and media files
2. **Indexes** everything for fast lookup (dictionary-based, O(1) matching)
3. **Matches** each JSON to its corresponding media file(s), handling Google's filename quirks
4. **Copies** all files to the output folder, preserving album structure
5. **Fixes timestamps** on matched files using `photoTakenTime` from the JSON
6. **Embeds metadata** (GPS, people) via ExifTool if available
7. **Tracks unmatched items** for review
8. **Logs** what happened so you can verify the results

Performance is a priority—dictionary-based matching, batched ExifTool writes, and parallel file operations keep processing fast even for large collections.

## Preparing Your Takeout

1. Go to [Google Takeout](https://takeout.google.com/)
2. Select only Google Photos (smaller download, faster processing)
3. Choose your preferred archive format and size
4. Download all the zip files
5. Extract everything into a single folder
6. Point PEF at that folder

**Tip:** Keep only photo-related content in the source folder. Other files won't cause problems, but they'll slow down scanning and appear in unprocessed.txt.

## Troubleshooting

### "No JSON metadata files found"

Your source folder doesn't look like a Takeout export. Make sure you're pointing at the extracted contents, not the zip file itself.

### Many unprocessed files with `-edited` suffix

This is handled by default. Check if there's a different pattern in your unprocessed files.

### ExifTool not found (Windows)

Should auto-download on first run. If that fails, manually download from [exiftool.org](https://exiftool.org/) and place it in `./tools/exiftool/`.

### Processing is slow

- Use `--no-exif` if you only need date correction (significantly faster)
- Avoid running from network drives
- SSDs are much faster than HDDs for this workload

### Files have wrong dates

Usually means a suffix matched files it shouldn't have. Be conservative with `-s` flags—only add patterns you've verified.

## Requirements

- Python 3.9 or later
- Dependencies in `requirements.txt`:
  - `filedate` (timestamp modification)
  - `pyexiftool` (ExifTool integration)
  - `orjson` (fast JSON parsing, optional but recommended)
- ExifTool (optional, for GPS/people metadata)

## Future Enhancements

- **GUI** — Graphical interface for users who prefer not to use the command line
- **Multi-service support** — Extend beyond Google Takeout to support exports from Amazon Photos, iCloud, Facebook, and other services. Each service has its own metadata format and directory structure, so this will use a provider-based architecture that can be extended for new services.

## Contributing

Found a bug or have a feature request? Contributions are welcome.

- [Open an issue](https://github.com/CrackinLLC/Photo-Export-Fixer/issues)
- Fork, branch, and submit a PR

## License

MIT License. See LICENSE file for details.

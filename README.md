# Photo Export Fixer (PEF)

Got a Google Takeout dump with thousands of photos dated "today" instead of when you actually took them? Yeah, we've all been there.

**Photo Export Fixer** restores your photo metadata—creation dates, GPS coordinates, people tags—by reading Google's JSON sidecar files and applying that data to your actual photos and videos. Your files come out organized, properly dated, and with all that metadata baked right in.

## What It Does

- **Fixes dates** — Sets file creation/modification timestamps from Google's metadata
- **Embeds GPS coordinates** — Writes location data into EXIF so any photo app can read it
- **Embeds people tags** — Face recognition names get written to standard metadata fields
- **Preserves your folder structure** — Albums stay as albums, "Photos from 2008" stays as-is
- **Handles Google's quirks** — Deals with truncated filenames, `-edited` variants, and other Takeout weirdness
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

That's it. Your processed files end up in a new folder next to your source, named `<source>_pefProcessed`.

## Installation

**Python 3.9+** required.

```bash
git clone https://github.com/CrackinLLC/Photo-Export-Fixer.git
cd Photo-Export-Fixer
pip install -r requirements.txt
```

For GPS and people tag embedding, you'll also need **ExifTool**:

| Platform | Installation |
|----------|--------------|
| Windows | Automatic—downloaded on first run to `./tools/` |
| macOS | `brew install exiftool` |
| Linux | `sudo apt install libimage-exiftool-perl` |

No ExifTool? No problem—dates still get fixed, you just won't get the embedded GPS/people metadata.

## Usage

### Basic Processing

```bash
python pef.py --path "/path/to/takeout"
```

Or run without arguments to get an interactive prompt:

```bash
python pef.py
# → Enter path to your folder with takeouts:
```

### Preview First (Recommended)

Before processing 50,000 photos, maybe check what you're dealing with:

```bash
python pef.py --path "/path/to/takeout" --dry-run
```

Output looks like:
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
  -d, --destination PATH   Output folder (default: <source>_pefProcessed)
  -s, --suffix SUFFIX      Extra filename suffixes to match (can repeat)
  --dry-run                Preview without making changes
  --no-exif                Skip GPS/people embedding (faster)
  --force                  Ignore saved progress, start fresh
  -v, --verbose            Log everything, not just errors
  -V, --version            Show version
```

## Resumable Processing

Processing gets interrupted? Just run the same command again—PEF picks up where it left off.

```bash
# Started processing, hit Ctrl+C halfway through
python pef.py --path "/path/to/takeout"
# "Interrupted! Saving progress..."
# "Progress saved. You can resume by running the same command again."

# Later, run the exact same command
python pef.py --path "/path/to/takeout"
# "Resuming: 2500 files already processed"
# Continues from file 2501...
```

Want to start over instead? Use `--force`:

```bash
python pef.py --path "/path/to/takeout" --force
```

## Output Structure

After processing, you get:

```
YourTakeout_pefProcessed/
├── Processed/
│   ├── Album Name/
│   │   ├── photo1.jpg      (with corrected dates + embedded metadata)
│   │   └── photo2.jpg
│   ├── Photos from 2019/
│   │   └── ...
│   └── Trip to Iceland/
│       └── ...
├── Unprocessed/
│   ├── orphan_file.jpg     (no matching JSON found)
│   └── ...
├── logs.txt                 (summary of what happened)
├── detailed_logs.txt        (step-by-step operations)
└── processing_state.json    (for resume capability)
```

## The Suffix Thing

Google does this annoying thing where `photo.jpg` and `photo-edited.jpg` share a single JSON file (`photo.jpg.json`). By default, PEF handles `""` (no suffix) and `"-edited"`.

If you see files in your Unprocessed folder with patterns like `photo-sticker.jpg`, add that suffix:

```bash
python pef.py --path "/path/to/takeout" -s "-sticker"
```

You can add multiple:

```bash
python pef.py --path "/path/to/takeout" -s "-sticker" -s "-effects"
```

**Heads up:** Only add suffixes you've actually verified. Adding random ones can cause wrong metadata to be applied to unrelated files.

## Why Files End Up Unprocessed

Stuff lands in the Unprocessed folder when:

1. **No matching JSON** — The file exists but Google didn't provide metadata for it
2. **JSON exists, file doesn't** — Metadata refers to a file that's missing (sometimes Google splits exports weirdly)
3. **Album metadata** — Some JSONs just describe the album itself, not a specific file
4. **System files** — Things like `.DS_Store` on Mac
5. **Character encoding issues** — Filenames with special characters sometimes get mangled by Google

Check your Unprocessed folder after a run. If you see patterns (lots of `-sticker` files, for example), that's a hint you might want to add a suffix and reprocess.

## How It Works

1. **Scans** your Takeout folder for all JSON metadata files and media files
2. **Indexes** everything for fast matching (we're talking O(1) lookups, not searching through 50k files)
3. **Matches** each JSON to its corresponding media file, handling Google's filename quirks
4. **Copies** matched files to the output folder, preserving album structure
5. **Fixes timestamps** using the `photoTakenTime` from the JSON
6. **Embeds metadata** (GPS, people) via ExifTool if available
7. **Collects unmatched items** into the Unprocessed folder
8. **Logs everything** so you can review what happened

The whole thing is designed to be fast—dictionary-based matching, batched ExifTool writes, parallel file operations where it helps.

## Preparing Your Takeout

1. Go to [Google Takeout](https://takeout.google.com/)
2. Select only Google Photos (faster download)
3. Choose your preferred archive format and size
4. Download all the zip files
5. Extract everything into a single folder
6. Point PEF at that folder

**Tip:** Keep only photo-related stuff in the source folder. Random other files won't break anything, but they'll slow down scanning and end up in Unprocessed.

## Troubleshooting

### "No JSON metadata files found"
Your source folder doesn't look like a Takeout export. Make sure you're pointing at the extracted contents, not the zip file.

### Lots of unprocessed files with `-edited`
This is normal—it's handled by default. Check if there's a different pattern in your unprocessed files.

### ExifTool not found (Windows)
Should auto-download. If it fails, manually download from [exiftool.org](https://exiftool.org/) and put it in `./tools/`.

### Processing is slow
- Use `--no-exif` if you only care about dates (much faster)
- Make sure you're not running from a network drive
- SSDs are significantly faster than HDDs for this workload

### Files have wrong dates
Usually means a suffix matched files it shouldn't have. Be conservative with `-s` flags—only add patterns you've verified.

## Requirements

- Python 3.9 or later
- Dependencies in `requirements.txt`:
  - `tqdm` (progress bars)
  - `filedate` (timestamp modification)
  - `orjson` (fast JSON parsing, optional)
- ExifTool (optional, for GPS/people metadata)

## Version History

### 3.2 (Current)
- Resumable processing—interrupt and continue later
- Better progress tracking with phase indicators
- Fixed GPS coordinates at (0,0) being incorrectly rejected
- Added `--version` flag
- Improved public API for library usage
- Better error logging

### 3.1
- Renamed to Photo Export Fixer (PEF)
- Architecture redesign for future multi-service support

### 3.0
- EXIF metadata writing (GPS, people tags)
- Dry run mode
- 10-100x faster file matching
- Auto-download ExifTool on Windows

### 2.0
- Album organization
- Custom destination folders
- Duplicate filename handling

## Contributing

Found a bug? Got a feature idea? PRs welcome.

- [Open an issue](https://github.com/CrackinLLC/Photo-Export-Fixer/issues)
- Fork, branch, PR

## License

MIT—do whatever you want with it.

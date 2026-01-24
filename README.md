# Photo Export Fixer (PEF)

Photo Export Fixer (PEF) is a utility designed to help you restore original creation and modification dates of photo exports quickly and effectively. Currently supports **Google Photos** exports via Google Takeout, with architecture designed to support additional services in the future.

Whether you're frustrated with scattered files or incorrect dates, this tool provides a solution that automates sorting, updates file attributes, and simplifies your workflow.

---

## The Problem

When downloading your Google Photos data via Google Takeout, you may encounter several issues:

- **Randomly Packed Archives:** Photos and videos are distributed across various zip files and folders without consistent organization.
- **Incorrect Dates:** File creation and modification dates are often set to today's date or a very old date, making it impossible to detect when the photos were originally taken.
- **Manually Sorting Files:** Organizing hundreds or thousands of files into proper folders can be overwhelming and time-consuming.

---

## The Solution

This utility solves these problems:

- **Organizes Your Photos as You chose on the Google Takeout page:** Photos are organized into folders like "Photos from 2008", into folders with album names, etc.
- **Corrects File Attributes:** Updates the creation and modification dates of files to match the timestamps from their metadata.
- **Writes EXIF Metadata:** Embeds GPS coordinates and people tags directly into your photos and videos for maximum compatibility with other apps.
- **Manages Unprocessed Files:** Automatically relocates unmatched or unprocessable files to an "Unprocessed" folder for manual review.
- **Generates Logs:** Creates a `logs.txt` file summarizing the operations for processed and unprocessed files.
- **Generates Detailed Logs:** Creates a `detailed_logs.txt` file, showing how everything was done step by step and helps to find errors.

---

## Setup and Usage

**Note:**
The program **does not change** any source folders or files, does not delete or modify them; it strictly **copies** all processed and unprocessed files. Ensure you have sufficient free space to accommodate slightly more than the total size of the input folder!

### 1. **Prepare Your Takeout Data**

- Download your Google Photos archives from Google Takeout.
- Unpack the downloaded zip files into a single folder. This folder will be the input for the program.
- Ensure the folder contains only Google Photos data, as unrelated files may slow down the process and will be moved into the "Unprocessed" folder.

### 2. **Install Python and Dependencies**

- Install Python (version 3.9.6 or later is preferred; it was not tested on older versions).
- Clone this repository:

  ```bash
  git clone https://github.com/CrackinLLC/Photo-Export-Fixer.git
  cd Photo-Export-Fixer
  ```

- Install the required dependencies:

  - #### Windows:

  ```bash
  pip install -r requirements.txt
  ```

  - #### macOS/Linux:

  ```bash
  pip3 install -r requirements.txt
  ```

### 3. **Run the Script**

Run the program via the terminal:

- #### Windows:

```bash
python pef.py --path <your-path-to-unpacked-folder>
```

- #### macOS/Linux:

```bash
python3 pef.py --path <your-path-to-unpacked-folder>
```

Ensure `<your-path-to-unpacked-folder>` is enclosed in quotation marks `"`, if names of your folders contain special characters or spaces.

---

Alternatively, you can run the script without arguments, and the program will prompt you to paste the path interactively:

- #### Windows:

```bash
python pef.py
```

- #### macOS/Linux:

```bash
python3 pef.py
```

#### Expected output:

```bash
You have not given arguments needed, so you have been redirected to the Wizard setup
Enter path to your folder with takeouts:
```

---

## EXIF Metadata (GPS & People Tags)

Google Photos stores valuable metadata in the JSON files, including GPS coordinates and people tags from face recognition. This program can write that metadata directly into your photo and video files for maximum compatibility with other apps.

### What Gets Written

- **GPS Coordinates:** Latitude, longitude, and altitude are written to standard EXIF GPS tags
- **People Tags:** Names are written to multiple locations for maximum compatibility:
  - `XMP-iptcExt:PersonInImage` (IPTC standard)
  - `IPTC:Keywords` and `XMP-dc:Subject` (for Lightroom, Bridge, etc.)
  - `XMP:XPKeywords` (for Windows Explorer)

### Requirements

EXIF metadata writing requires **ExifTool**:

- **Windows:** ExifTool is automatically downloaded to `./tools/exiftool/` on first run
- **macOS/Linux:** Install via package manager:
  ```bash
  # macOS
  brew install exiftool

  # Ubuntu/Debian
  sudo apt install libimage-exiftool-perl
  ```

If ExifTool is not available, the program will still work but will only set file timestamps (not GPS/people metadata).

### Skipping EXIF Writing

If you only need timestamps corrected and want faster processing, use the `--no-exif` flag:

```bash
python pef.py --path /path/to/takeout --no-exif
```

---

## What You'll Get

Once the program finishes processing:

1. A new folder will appear as a sibling to the folder you provided, named with `_pefProcessed` suffix. This folder will include:
   - A `Processed` folder containing subfolders organized as Google Takeout organised, e.g., `Photos from 2008`, `Sea 2023`, etc.
   - An `Unprocessed` folder containing files and metadata that couldn't be matched or processed.
   - A `logs.txt` file summarizing:
     - Processed files with updated attributes.
     - Unprocessed files and metadata for review.
   - A `detailed_logs.txt` file, showing step by step every:
     - Skip
     - Copy
     - Extraction
     - Change
2. A terminal output summarizing:
   - The number of processed/unprocessed files.
   - The total time taken for processing.
3. If ExifTool is available, your files will also have:
   - GPS coordinates embedded (if available in the JSON)
   - People tags embedded (if face recognition data exists)

---

## Dry Run Mode

Before processing a large collection, use `--dry-run` to preview what would happen:

```bash
python pef.py --path /path/to/takeout --dry-run
```

This shows:
- How many JSON and media files were found
- How many files would be processed vs. unprocessed
- How many files have GPS coordinates
- How many files have people tags
- Whether ExifTool is available

Example output:
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

---

## Extend Mode

If you've already processed files and want to add GPS/people metadata without re-copying everything, use `--extend`:

```bash
python pef.py --path /path/to/original/takeout --extend
```

This will:
1. Scan the original JSON files for GPS and people data
2. Find the matching files in your already-processed `_pefProcessed/Processed` folder
3. Write the metadata directly to those files (no copying)

This is much faster than re-processing and is useful when:
- You processed files before EXIF writing was available
- You want to update metadata without duplicating files

---

## Terminal running

Running from terminal supports arguments. Example with help:

- #### Windows:

```bash
python pef.py -h
```

- #### macOS/Linux:

```bash
python3 pef.py -h
```

#### Expected output:

```bash
Photo Export Fixer (PEF)

This program processes photo export data (currently Google Takeout) by analyzing files in a specified folder. It identifies `.json` files for metadata (e.g., creation date, file name) and processes the corresponding files accordingly.

Files without a matching `.json` file or those that cannot be located are marked as unprocessed and copied to a separate folder for review.

Processed files are copied and modified based on their metadata, while unprocessed ones are logged.

More details can be found in the README file.
Git repository for this project: https://github.com/CrackinLLC/Photo-Export-Fixer

optional arguments:
  -h, --help                  show this help message and exit
  -p PATH, --path PATH        The full path to the repository containing Takeout folders
  -d DESTINATION, --destination DESTINATION
                              The directory where the processed files will be saved
  -s SUFFIX, --suffix SUFFIX  Additional suffixes you want to add
  -e, --extend                Extend metadata on already-processed files
  --no-exif                   Skip EXIF metadata writing (faster, timestamps only)
  --dry-run                   Show what would be done without making changes
```

### Detailed explanation of every argument:

- **`-h` or `--help`** - Returns help, where the program is briefly presented and arguments are displayed.

- **`-p <path>` or `--path <path>`** - Argument which must be followed by the path to the directory with all takeouts. Takes only one argument, is mandatory, but if not given, wizard setup mode asks `<path>` again.

- **`-d <destination>` or `--destination <destination>`** - Argument which must be followed by the path to the directory where you want to have processed files. Takes only one argument, is **not** mandatory, if not given, folder `<source>_pefProcessed` will be created as a sibling to the source folder.

- **`-s <suffix>` or `--suffix <suffix>`** - Argument which uses the "append" principle and can be specified multiple times to add multiple suffixes. By default, it is set to `["", "-edited"]`. To add multiple suffixes, the argument has to be specified separately for each value. Example:

  - ```bash
    pef.py --path /Users/photolover/my-takeouts -s "-stickers" -s "-connect"
    ```

- **`-e` or `--extend`** - Extend metadata on files that were already processed. Use this to add GPS coordinates and people tags to files from a previous run without re-copying everything.

- **`--no-exif`** - Skip writing EXIF metadata (GPS, people tags). Use this for faster processing if you only need the file timestamps corrected.

- **`--dry-run`** - Preview what would happen without making any changes. Shows file counts, how many would match, and metadata statistics. Highly recommended before running on large datasets.

---

## Suffixes

You might wonder - what exactly are these suffixes? While they may not seem entirely logical, we must work around Google's peculiar conventions, so let's get used to them.

### The Issue

In an ideal situation:

- Each file would have its corresponding JSON data file, meaning the number of JSONs and other associated files would be equal.

However, during development, I discovered that this isn't always the case:

- Often, there are fewer JSON files compared to other files.
- Initially, I ignored the extra, "unprocessed" files, assuming Google forgot to provide JSON data for them.

But after testing the program on larger datasets, I uncovered a pattern:

- Many unprocessed files contained the suffix `-edited` before their file extension (e.g., `cat-edited.png`), but don't have a JSON associated with the `cat-edited.png` file. At the same time, files without suffixes were processed correctly, as a JSON with metadata for them exists.
- These unprocessed files had counterparts without the `-edited` suffix (e.g., `cat.png`) that were being processed correctly.
- Google implicitly expects us to treat `cat.png` and `cat-edited.png` as sharing a single JSON file (`cat.json`).

This quirk is exactly why **suffixes were implemented**.

### Suffix Solution

Since I cannot predict all the variations Google might append to filenames, such as `-edited`, `-sticker`, or others, suffixes allow you to manually address this issue when running the program.

If you notice files in the `Unprocessed` folder with suffixes (e.g., `-sticker`) that should be treated as their base counterparts (e.g., `file-sticker.png` → `file.png`), you can specify the suffix, which will be used as an additional filter, to handle more files during execution.

Keep in mind that the creation date for files with suffixes is obtained from the JSON file related to the file with the same name but without the suffix, as files with suffixes in their name do not have their own JSON file.

### Preset suffixes:

- ` ` - actually, nothing. Usually, nothing is added, so this suffix is obligatory.
- `-edited` - important suffix, which, as I understand, Google adds to files you edited in Google Photos. I do not know why the exact modification date is not saved, but not to leave such files unprocessed, this suffix exists.

### Usage

To utilize suffixes, simply pass them as arguments when running the program from the terminal, as demonstrated earlier.

For example:

```bash
pef.py -p <path> -s -sticker
```

### Note:

You should not add suffixes if you do not have problems with a lot of **unprocessed** files, or if you are not fully aware of what you are doing. It can lead to incorrect file handling or potential data loss.

---

## About `separate.py`: Separate All JSONs and Unprocessed Files

In some cases, after running the main script, you may notice a large number of unprocessed files. This often means that additional suffixes are needed to match more files correctly. However, to avoid any risk of overwriting or mixing up already correctly processed files, it's best to handle unprocessed files and all JSONs separately.

That's why the `separate.py` script was created. Its purpose is to **separate all JSON files and Non-JSON files from a source directory and copy them into a new, separate output directory**. This allows you to copy only `.json` files, to safely experiment with different suffixes or processing strategies on the remaining files, without affecting your original or previously processed data.

### Why Use `separate.py`?

- **Safe:** By copying all files to a new location, nothing is changed, only a new folder is created.
- **Full Coverage:** Ensures that every JSON and Non-JSON file is available, making it easier to run the script **again** with all `.json` files and unprocessed files after the first run.
- **Organized Output:** The script creates a clear folder structure, separating JSONs and other files for easy review and further processing.

### How to Run

From your terminal, use the following command:

- #### Windows:

```bash
python separate.py -s <path-to-your-source-folder> -d <path-to-output-folder>
```

- #### macOS/Linux:

```bash
python3 separate.py -s <path-to-your-source-folder> -d <path-to-output-folder>
```

**Example:**

```bash
python3 separate.py -s "/Users/yourname/Takeout" -d "/Users/yourname/TakeoutSeparated"
```

After running, you'll find two subfolders in the `SeparateOutput` folder in your output directory:
- `jsons/` — containing all JSON files from the source.
- `files/` — containing all other files.

This workflow makes it easy to review, reprocess, or experiment with your data as needed.

### Help command

Help command is available for `separate.py`:

- #### Windows:

```bash
python separate.py -h
```

- #### macOS/Linux:

```bash
python3 separate.py -h
```

---

## Running the script again

Sometimes, after getting the output, you can be really disappointed. Maybe you get tons of unprocessed files with `-sticker` at the end of the name of each file, right before the extension, or a lot of files with `(1)` before the extension—what to do?

In such cases, you should consider using the **suffixes** function of this script (as described above), and also `separate.py`.

It is true that you can just run the script again, just adding the suffix. It will definitely work, but accuracy can be affected. Some files can get the wrong dates assigned—which is not what anyone would want. Suffixes are powerful, but with great power comes great responsibility, so you should do everything in the right way.

### How to run the script again correctly:

- Create a new folder for files.
- Copy all unprocessed files. You can copy them, or just copy the folder with them, and paste it into the folder you just created.
- Use `separate.py` according to the documentation to separate all `.json` files.
- Copy those `.json` files or the folder containing them to the same folder where your unprocessed files were copied.

This is the end of preparation. Now, use that folder as `<path>` to run `pef.py` again. You can add any suffixes and do not worry about inaccuracy—you are working only with unprocessed files; files that were processed are not affected. After finishing, you can copy files you processed using the **suffixes** function to the folder with all processed files, and enjoy it!

### Why not just run again?

It is a logical question: why make those copies when you can just run the script again with suffixes? But it is very important not to do so, because it can cause such problems:

- Wrong date assignment: if you add `(1)` as a suffix, `name.jpg` and `name(1).jpg` will both get the date from `name.something.json`, not from `name.something.json` and `name.something(1).json` as they should. Usually, `name.jpg` and `name(1).jpg` are completely unrelated, so up to 50% of your photos can get incorrect dates.
- If you put something like `xd` as a suffix, a lot of files can get wrong dates because of the same reason. More importantly, you can get completely unexpected results, and the final output will not be as accurate as possible.

It is better just to do it as described, spend 2 more minutes, but be confident about results and enjoy accuracy.

---

## How PEF Works: Step-by-Step

1. **Gather Input Data:**
   The program scans the input folder and generates a list of all files with their full paths. It then separates the data into two lists:
   - **JSON Files** (metadata files).
   - **Other Files** (media files like `.jpg`, `.png`, etc.).

2. **Create Output Folder:**
   A new folder named `<source>_pefProcessed` is created as a sibling to the source folder (or in the destination directory if provided). All processed files are stored in `Processed` folder.

3. **Process JSON Files:**
   For every JSON file:
   - **Extract Metadata:** The program reads the JSON file to retrieve the name of the associated file, its original creation date, GPS coordinates, and people tags.
   - **Handle Naming Exceptions:** Google often shortens filenames or does not add parentheses like `(1)` to the name of the file to which the JSON file refers. The program resolves these issues to accurately match files.
   - **Copy & Modify Files:**
     - Matched files are copied into a subfolder named by folder they were originally in - it could be album name, something like `Photos from 2008`, etc.
     - Creation and modification dates are corrected.
     - GPS coordinates and people tags are embedded into the file's EXIF data (if ExifTool is available).
     - Matched files are added to the list of processed files.
   - **Unmatched JSONs:** If no corresponding file is found, the JSON is added to the list of unprocessed JSONs.

4. **Handle Unprocessed Files:**
   After processing JSONs, the program compares the list of all files with the list of processed files. Any difference is saved as unprocessed files.

5. **Copy Unprocessed Files:**
   Any unmatched files and JSONs are copied to the `Unprocessed` folder inside the output directory for review.

6. **Save Logs:**
   Information about all operations is saved in a `logs.txt` file that includes:
   - **Processed Files:** Original path, new path, name, path to source JSON and time processed.
   - **Unprocessed Files:** Original path, new path, and name.
   - **Unprocessed JSONs:** Original path, new path, name of the file they are referred to, time processed.

### Script does not modify original files!

---

## Why Files Might Not Be Found

Files and metadata may fail to match for several reasons:

1. **Unrelated Files:**
   Unwanted or system-related files like `.DS_Store` (Mac).

2. **Filename Changes:**
   - **Special Characters (Case 1):** A file named `can't.png` is stored as `can_t.png`, but the JSON still refers to `can't.png`.
   - **Local Symbols (Case 2):** Names with Cyrillic, Arabic, or other special characters may appear mismatched due to unpredictable encoding changes by Google.

3. **Missing JSON:**
   A file might lack a corresponding JSON file entirely, preventing processing.

4. **Album JSON:**
   Albums also have their own `.json` files, I am not sure why it is needed, but the script ignores it. Example of content in such file:

   ```
   {
     "title": "TripMountains"
   }
   ```

In all such cases, files and JSONs are copied to the `unprocessed` folder for manual review.

---

## Final Result

At the end of execution, you'll see:

- Correctly organized and dated files.
- A separate folder for anything unprocessed.
- Comprehensive logs to review any anomalies.

---

## Future Plans

- Support for additional photo export services (Amazon Photos, Apple iCloud, Facebook, etc.)
- GUI interface for easier use
- Resume capability for interrupted processing

---

## Contact

If you encounter issues or have questions, feel free to:

- Open an [issue](https://github.com/CrackinLLC/Photo-Export-Fixer/issues) on GitHub.

---

## Version History

### Version 3.1 (Current)
- **Renamed to Photo Export Fixer (PEF)** - New name reflecting broader scope
- **Architecture redesign** - Prepared for multi-service support

### Version 3.0
- **EXIF Metadata Writing:** GPS coordinates and people tags from Google Photos are now embedded directly into your files using ExifTool.
- **Extend Mode:** Add metadata to already-processed files without re-copying everything (`--extend` flag).
- **Dry Run Mode:** Preview what would happen before processing (`--dry-run` flag).
- **Performance Improvements:** 10-100x faster file matching using dictionary-based lookups instead of linear search.
- **Buffered Logging:** Significantly faster logging with single file handle instead of open/close per entry.
- **Path Handling:** Better handling of Windows paths with trailing backslashes and mixed slashes.
- **Auto-download ExifTool:** On Windows, ExifTool is automatically downloaded if not found.

### Version 2.0
- Added destination argument.
- Added sorting by albums.
- Prevented rewriting files with same names - now numbers like `(1)` are added.
- Changed logic how script looks for the files.

---

## Already Solved Issues

- If the processed folder contained any unrelated `.json` files, the program would crash. This is now resolved.
- Missing `UTF-8` encoding when opening log files could cause the program to crash.
- Numbers in brackets worked incorrectly with suffixes, which led to some files not being found.

---

## Contribute

Contributions are welcome! Feel free to submit pull requests or open issues.

# PEF Architecture Refactoring Plan

## Current State Analysis

### Problems Identified

1. **Single 878-line file** - Everything in one monolithic `pef.py`
2. **Duplicated code** - File matching logic repeated 4 times (in `find_file`, `dry_run_main`, `dry_run_extend`, `extend_metadata`)
3. **No progress indicator in dry-run/extend** - User can't tell if it's working
4. **Global state for logging** - `_log_handle` module-level globals are error-prone
5. **No separation of concerns** - Scanning, matching, copying, metadata writing all mixed
6. **Untestable** - Functions do too much, hard to unit test
7. **Inconsistent patterns** - Some functions use classes, most don't

### Code Duplication Examples

The file matching logic (handle 51-char truncation, brackets, suffixes) appears in:
- `find_file()` (lines 235-263)
- `dry_run_main()` (lines 416-440)
- `dry_run_extend()` (lines 526-554)
- `extend_metadata()` (lines 628-659)

---

## Proposed Architecture

### Module Structure

```
pef/
├── __init__.py
├── __main__.py          # Entry point: `python -m pef`
│
├── core/                # Core library - NO UI dependencies
│   ├── __init__.py
│   ├── scanner.py       # File/JSON discovery and indexing
│   ├── matcher.py       # JSON-to-file matching logic (deduplicated)
│   ├── processor.py     # Copy, date setting, metadata writing
│   ├── metadata.py      # EXIF/GPS/people tag builders
│   ├── exiftool.py      # ExifTool download and wrapper
│   ├── logger.py        # Buffered logging class
│   ├── models.py        # Data classes (FileInfo, JsonMetadata, etc.)
│   └── utils.py         # Path helpers (exists, get_unique_path, etc.)
│
├── providers/           # Service-specific handlers (future)
│   ├── __init__.py
│   ├── base.py          # Base provider interface
│   ├── google.py        # Google Takeout provider
│   ├── amazon.py        # Amazon Photos provider (future)
│   └── apple.py         # iCloud provider (future)
│
├── cli/                 # Command-line interface
│   ├── __init__.py
│   ├── main.py          # CLI entry point, argument parsing
│   └── wizard.py        # Interactive wizard mode
│
├── gui/                 # Graphical interface (future)
│   ├── __init__.py
│   ├── main.py          # GUI entry point
│   ├── main_window.py   # Main application window
│   ├── progress.py      # Progress dialog/widgets
│   └── settings.py      # Settings/preferences dialog
│
└── tests/
    ├── __init__.py
    ├── test_matcher.py
    ├── test_scanner.py
    ├── test_metadata.py
    └── fixtures/        # Sample JSON files for testing
```

### Architecture Layers

```
┌─────────────────────────────────────────────────┐
│                   UI Layer                       │
│  ┌──────────────┐          ┌──────────────┐     │
│  │     CLI      │          │     GUI      │     │
│  │  (cli/)      │          │   (gui/)     │     │
│  └──────┬───────┘          └──────┬───────┘     │
└─────────┼─────────────────────────┼─────────────┘
          │                         │
          ▼                         ▼
┌─────────────────────────────────────────────────┐
│              Core Library (core/)                │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐         │
│  │ Scanner │ │ Matcher │ │ Processor │         │
│  └─────────┘ └─────────┘ └───────────┘         │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐         │
│  │ Models  │ │ Logger  │ │ ExifTool  │         │
│  └─────────┘ └─────────┘ └───────────┘         │
└─────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│            Providers (providers/)                │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐         │
│  │ Google  │ │ Amazon  │ │  Apple    │         │
│  └─────────┘ └─────────┘ └───────────┘         │
└─────────────────────────────────────────────────┘
```

**Key principle:** Core library has ZERO knowledge of CLI or GUI. It uses callbacks/events for progress reporting so either UI can hook in.

### Key Abstractions

#### 1. `models.py` - Data Classes
```python
@dataclass
class FileInfo:
    filename: str
    filepath: str
    albumname: str

@dataclass
class JsonMetadata:
    filepath: str
    title: str
    date: datetime
    geo_data: Optional[dict]
    people: Optional[list]
    description: str

@dataclass
class ProcessingStats:
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    with_gps: int = 0
    with_people: int = 0

# Callback type for progress reporting (UI-agnostic)
ProgressCallback = Callable[[int, int, str], None]  # (current, total, message)
```

#### 2. `scanner.py` - File Discovery
```python
class FileScanner:
    def __init__(self, path: str):
        self.path = path
        self.jsons: List[str] = []
        self.files: List[FileInfo] = []
        self.file_index: Dict[tuple, List[FileInfo]] = {}

    def scan(self, on_progress: Optional[ProgressCallback] = None) -> None:
        """Scan directory and build index.

        Args:
            on_progress: Optional callback for progress updates.
                         CLI passes tqdm wrapper, GUI passes Qt signal.
        """

    def get_json_count(self) -> int: ...
    def get_file_count(self) -> int: ...
```

#### 3. `matcher.py` - Deduplicated Matching Logic
```python
class FileMatcher:
    def __init__(self, file_index: dict, suffixes: List[str]):
        self.file_index = file_index
        self.suffixes = suffixes

    def find_match(self, json_path: str, title: str) -> Optional[List[FileInfo]]:
        """Single source of truth for matching logic."""
        # Handles: 51-char truncation, brackets, suffixes
        # Returns None if no match, list of FileInfo if found

    @staticmethod
    def parse_title(title: str, json_path: str) -> Tuple[str, str, Optional[str]]:
        """Extract name, extension, brackets from title."""
```

#### 4. `logger.py` - Proper Logging Class
```python
class BufferedLogger:
    def __init__(self, path: str):
        self.handle = open(path, "a", encoding="utf-8")

    def log(self, message: str) -> None:
        self.handle.write(f"{timestamp()} - {message}\n")

    def close(self) -> None:
        self.handle.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
```

#### 5. `processor.py` - Processing Operations
```python
class FileProcessor:
    def __init__(self, output_dir: str, logger: BufferedLogger, exiftool=None):
        self.output_dir = output_dir
        self.logger = logger
        self.exiftool = exiftool
        self.stats = ProcessingStats()

    def process_file(self, file: FileInfo, metadata: JsonMetadata) -> str:
        """Copy file, set dates, write EXIF. Returns new path."""

    def process_unmatched(self, files: List[FileInfo]) -> None:
        """Copy unmatched files to Unprocessed folder."""

    def run(self, jsons: List[str], matcher: FileMatcher,
            on_progress: Optional[ProgressCallback] = None) -> ProcessingStats:
        """Main processing loop with progress callback."""
```

#### 6. `orchestrator.py` - High-Level Operations
```python
class PEFOrchestrator:
    """Coordinates scanning, matching, processing. Used by both CLI and GUI."""

    def __init__(self, source_path: str, dest_path: str = None,
                 suffixes: List[str] = None, write_exif: bool = True):
        self.source_path = source_path
        self.dest_path = dest_path or f"{source_path}_pefProcessed"
        self.suffixes = suffixes or ["", "-edited"]
        self.write_exif = write_exif

    def dry_run(self, on_progress: ProgressCallback = None) -> dict:
        """Preview what would happen. Returns stats dict."""

    def process(self, on_progress: ProgressCallback = None) -> ProcessingStats:
        """Run full processing. Returns stats."""

    def extend(self, on_progress: ProgressCallback = None) -> ProcessingStats:
        """Extend metadata on existing files. Returns stats."""
```

---

## Implementation Plan

### Phase 1: Create Module Structure (no behavior change)
1. Create `pef/` package directory with `core/`, `cli/`, `gui/`, `providers/` subdirs
2. Move utility functions to `core/utils.py`
3. Move data structures to `core/models.py`
4. Keep `pef.py` working as entry point (thin wrapper)

### Phase 2: Extract Scanner with Callbacks
1. Create `core/scanner.py` with `FileScanner` class
2. Add `on_progress` callback parameter (not tqdm directly)
3. CLI wraps callback with tqdm, GUI wraps with Qt signal
4. Add unit tests for scanner

### Phase 3: Extract Matcher (deduplicate!)
1. Create `core/matcher.py` with `FileMatcher` class
2. Single implementation of matching logic
3. Replace 4 duplicate implementations
4. Add unit tests for edge cases (51-char, brackets, suffixes)

### Phase 4: Extract Logger
1. Create `core/logger.py` with `BufferedLogger` class
2. Remove global `_log_handle` state
3. Use context manager pattern

### Phase 5: Extract Processor
1. Create `core/processor.py` with `FileProcessor` class
2. Consolidate copy/modify/metadata logic
3. Add progress callback support

### Phase 6: Extract Metadata & ExifTool
1. Create `core/metadata.py` for tag builders
2. Create `core/exiftool.py` for download/wrapper

### Phase 7: Create Orchestrator
1. Create `core/orchestrator.py` with `PEFOrchestrator` class
2. Single entry point for dry_run, process, extend operations
3. Both CLI and GUI will use this class

### Phase 8: Refactor CLI
1. Create `cli/main.py` for argument parsing
2. Create `cli/wizard.py` for interactive mode
3. CLI uses `PEFOrchestrator` with tqdm progress wrapper
4. Create `__main__.py` for entry point

### Phase 9: Add Tests
1. Create `tests/` directory
2. Add fixtures (sample JSON files from real Google Takeout)
3. Unit tests for each core module
4. Integration test for full workflow

### Phase 10: Add GUI (future)
1. Framework: tkinter (built-in, no extra dependencies)
2. Create `gui/main_window.py` with file picker, progress bar
3. GUI uses `PEFOrchestrator` with tkinter progress wrapper
4. No additional requirements.txt changes needed

### Phase 11: Add Provider Abstraction (future)
1. Create `providers/base.py` with abstract provider interface
2. Create `providers/google.py` for Google Takeout
3. Prepare for Amazon, Apple, Facebook providers

---

## Benefits

1. **Testable** - Each module can be unit tested independently
2. **Maintainable** - Changes isolated to relevant modules
3. **No duplication** - Matching logic in one place
4. **Progress everywhere** - Scanner class supports progress bars consistently
5. **Clean state** - No global variables, proper classes
6. **Extensible** - Easy to add new features (resume, filters, providers)

---

## Verification

1. Run existing functionality: `python -m pef --dry-run --path <test_path>`
2. Run unit tests: `pytest pef/tests/`
3. Verify extend mode: `python -m pef --extend --path <test_path>`
4. Compare output with pre-refactor version on small dataset

---

## Files to Create/Modify

**New files (core library):**
- `pef/__init__.py`
- `pef/__main__.py`
- `pef/core/__init__.py`
- `pef/core/scanner.py`
- `pef/core/matcher.py`
- `pef/core/processor.py`
- `pef/core/orchestrator.py`
- `pef/core/metadata.py`
- `pef/core/exiftool.py`
- `pef/core/logger.py`
- `pef/core/models.py`
- `pef/core/utils.py`

**New files (CLI):**
- `pef/cli/__init__.py`
- `pef/cli/main.py`
- `pef/cli/wizard.py`

**New files (Providers):**
- `pef/providers/__init__.py`
- `pef/providers/base.py`
- `pef/providers/google.py`

**New files (GUI - future):**
- `pef/gui/__init__.py`
- `pef/gui/main.py`
- `pef/gui/main_window.py`
- `pef/gui/progress.py`

**New files (tests):**
- `pef/tests/__init__.py`
- `pef/tests/test_matcher.py`
- `pef/tests/test_scanner.py`
- `pef/tests/test_processor.py`
- `pef/tests/fixtures/` (sample JSON files)

**Modified files:**
- `pef.py` - Keep as thin wrapper: `from pef.cli.main import main; main()`
- `requirements.txt` - Add pytest

---

## Decisions Made

1. **GUI Framework:** tkinter (built-in, no extra dependencies)
2. **Testing scope:** Unit tests + Integration tests with real sample files
3. **Backwards compatibility:** Allow minor CLI changes if they improve usability
4. **Multi-service support:** Provider abstraction layer for future services

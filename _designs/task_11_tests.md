# Task 11: Add Tests

## Objective
Create unit tests and integration tests for the core library modules.

## Prerequisites
- Task 01-10 (All core and CLI modules) complete

## Files to Create
- `pef/tests/__init__.py`
- `pef/tests/test_utils.py`
- `pef/tests/test_models.py`
- `pef/tests/test_matcher.py`
- `pef/tests/test_scanner.py`
- `pef/tests/test_processor.py`
- `pef/tests/test_orchestrator.py`
- `pef/tests/fixtures/` (sample data)
- `pytest.ini` or `pyproject.toml` (pytest config)

## Update Requirements

Add to `requirements.txt`:
```
pytest>=7.0.0
pytest-cov>=4.0.0
```

## Implementation

### `pef/tests/__init__.py`

```python
"""Tests for Photo Export Fixer."""
```

### `pef/tests/conftest.py`

```python
"""Pytest configuration and fixtures."""

import os
import json
import tempfile
import shutil
from datetime import datetime
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_takeout(temp_dir: str) -> str:
    """Create a sample Google Takeout structure for testing.

    Structure:
        temp_dir/
        ├── Album1/
        │   ├── photo1.jpg
        │   ├── photo1.jpg.json
        │   ├── photo2.jpg
        │   ├── photo2.jpg.json
        │   └── video.mp4
        └── Album2/
            ├── image.png
            ├── image.png.json
            └── image-edited.png
    """
    # Album1
    album1 = os.path.join(temp_dir, "Album1")
    os.makedirs(album1)

    # Photo 1 with GPS
    with open(os.path.join(album1, "photo1.jpg"), "wb") as f:
        f.write(b"fake jpg data")

    with open(os.path.join(album1, "photo1.jpg.json"), "w") as f:
        json.dump({
            "title": "photo1.jpg",
            "photoTakenTime": {"timestamp": "1609459200"},  # 2021-01-01
            "geoData": {"latitude": 40.7128, "longitude": -74.0060, "altitude": 10},
            "people": [{"name": "Alice"}, {"name": "Bob"}],
            "description": "Test photo 1"
        }, f)

    # Photo 2 without GPS
    with open(os.path.join(album1, "photo2.jpg"), "wb") as f:
        f.write(b"fake jpg data 2")

    with open(os.path.join(album1, "photo2.jpg.json"), "w") as f:
        json.dump({
            "title": "photo2.jpg",
            "photoTakenTime": {"timestamp": "1612137600"},  # 2021-02-01
        }, f)

    # Video without JSON (unmatched)
    with open(os.path.join(album1, "video.mp4"), "wb") as f:
        f.write(b"fake video data")

    # Album2
    album2 = os.path.join(temp_dir, "Album2")
    os.makedirs(album2)

    # Image with -edited variant
    with open(os.path.join(album2, "image.png"), "wb") as f:
        f.write(b"fake png data")

    with open(os.path.join(album2, "image-edited.png"), "wb") as f:
        f.write(b"fake edited png data")

    with open(os.path.join(album2, "image.png.json"), "w") as f:
        json.dump({
            "title": "image.png",
            "photoTakenTime": {"timestamp": "1614556800"},  # 2021-03-01
            "people": [{"name": "Charlie"}]
        }, f)

    return temp_dir


@pytest.fixture
def sample_json_with_long_name(temp_dir: str) -> str:
    """Create a JSON for a file with a long name (>51 chars)."""
    album = os.path.join(temp_dir, "LongNames")
    os.makedirs(album)

    long_name = "a" * 50 + ".jpg"  # 54 chars total
    truncated_name = "a" * 47 + ".jpg"  # 51 chars (truncated)

    with open(os.path.join(album, truncated_name), "wb") as f:
        f.write(b"fake data")

    json_path = os.path.join(album, f"{long_name}.json")
    with open(json_path, "w") as f:
        json.dump({
            "title": long_name,
            "photoTakenTime": {"timestamp": "1609459200"},
        }, f)

    return temp_dir


@pytest.fixture
def sample_json_with_brackets(temp_dir: str) -> str:
    """Create JSONs for duplicate-named files with (1), (2) suffixes."""
    album = os.path.join(temp_dir, "Duplicates")
    os.makedirs(album)

    # Original
    with open(os.path.join(album, "photo.jpg"), "wb") as f:
        f.write(b"original")

    with open(os.path.join(album, "photo.jpg.json"), "w") as f:
        json.dump({
            "title": "photo.jpg",
            "photoTakenTime": {"timestamp": "1609459200"},
        }, f)

    # Duplicate (1)
    with open(os.path.join(album, "photo(1).jpg"), "wb") as f:
        f.write(b"duplicate 1")

    # Note: Google names duplicate JSONs as photo.jpg(1).json
    with open(os.path.join(album, "photo.jpg(1).json"), "w") as f:
        json.dump({
            "title": "photo.jpg",
            "photoTakenTime": {"timestamp": "1609459201"},
        }, f)

    return temp_dir
```

### `pef/tests/test_utils.py`

```python
"""Tests for pef.core.utils module."""

import os
import tempfile

import pytest

from pef.core.utils import (
    exists,
    get_unique_path,
    checkout_dir,
    get_album_name,
    normalize_path,
)


class TestExists:
    """Tests for exists() function."""

    def test_none_returns_false(self):
        assert exists(None) is False

    def test_empty_string_returns_false(self):
        assert exists("") is False

    def test_nonexistent_path_returns_false(self):
        assert exists("/this/path/does/not/exist/12345") is False

    def test_existing_file_returns_true(self, temp_dir):
        filepath = os.path.join(temp_dir, "test.txt")
        with open(filepath, "w") as f:
            f.write("test")
        assert exists(filepath) is True

    def test_existing_dir_returns_true(self, temp_dir):
        assert exists(temp_dir) is True


class TestGetUniquePath:
    """Tests for get_unique_path() function."""

    def test_nonexistent_file_returns_same(self, temp_dir):
        path = os.path.join(temp_dir, "new_file.txt")
        assert get_unique_path(path) == path

    def test_existing_file_adds_suffix(self, temp_dir):
        path = os.path.join(temp_dir, "test.txt")
        with open(path, "w") as f:
            f.write("test")

        result = get_unique_path(path)
        assert result == os.path.join(temp_dir, "test(1).txt")

    def test_multiple_existing_increments(self, temp_dir):
        base = os.path.join(temp_dir, "test.txt")
        for i in range(3):
            suffix = f"({i})" if i > 0 else ""
            name = f"test{suffix}.txt"
            with open(os.path.join(temp_dir, name), "w") as f:
                f.write("test")

        result = get_unique_path(base)
        assert result == os.path.join(temp_dir, "test(3).txt")

    def test_directory_mode(self, temp_dir):
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)

        result = get_unique_path(subdir, is_dir=True)
        assert result == os.path.join(temp_dir, "subdir(1)")


class TestCheckoutDir:
    """Tests for checkout_dir() function."""

    def test_creates_missing_directory(self, temp_dir):
        path = os.path.join(temp_dir, "new_dir")
        result = checkout_dir(path)
        assert result == path
        assert os.path.isdir(path)

    def test_onlynew_creates_unique(self, temp_dir):
        path = os.path.join(temp_dir, "dir")
        os.makedirs(path)

        result = checkout_dir(path, onlynew=True)
        assert result == os.path.join(temp_dir, "dir(1)")
        assert os.path.isdir(result)


class TestGetAlbumName:
    """Tests for get_album_name() function."""

    def test_extracts_parent_folder(self):
        assert get_album_name("/photos/Vacation 2023/photo.jpg") == "Vacation 2023"

    def test_handles_windows_paths(self):
        assert get_album_name("C:\\Photos\\Album\\image.png") == "Album"


class TestNormalizePath:
    """Tests for normalize_path() function."""

    def test_strips_whitespace(self):
        assert normalize_path("  /path/to/file  ") == os.path.normpath("/path/to/file")

    def test_expands_home(self):
        result = normalize_path("~/photos")
        assert "~" not in result
```

### `pef/tests/test_matcher.py`

```python
"""Tests for pef.core.matcher module."""

import pytest

from pef.core.matcher import FileMatcher, ParsedTitle
from pef.core.models import FileInfo


class TestParsedTitle:
    """Tests for ParsedTitle dataclass."""

    def test_build_filename_simple(self):
        pt = ParsedTitle(name="photo", extension=".jpg", brackets=None)
        assert pt.build_filename() == "photo.jpg"

    def test_build_filename_with_suffix(self):
        pt = ParsedTitle(name="photo", extension=".jpg", brackets=None)
        assert pt.build_filename("-edited") == "photo-edited.jpg"

    def test_build_filename_with_brackets(self):
        pt = ParsedTitle(name="photo", extension=".jpg", brackets="(1)")
        assert pt.build_filename() == "photo(1).jpg"

    def test_build_filename_with_suffix_and_brackets(self):
        pt = ParsedTitle(name="photo", extension=".jpg", brackets="(1)")
        assert pt.build_filename("-edited") == "photo-edited(1).jpg"


class TestFileMatcher:
    """Tests for FileMatcher class."""

    @pytest.fixture
    def simple_index(self):
        """Create a simple file index for testing."""
        return {
            ("Album1", "photo.jpg"): [
                FileInfo("photo.jpg", "/path/Album1/photo.jpg", "Album1")
            ],
            ("Album1", "photo-edited.jpg"): [
                FileInfo("photo-edited.jpg", "/path/Album1/photo-edited.jpg", "Album1")
            ],
            ("Album1", "photo(1).jpg"): [
                FileInfo("photo(1).jpg", "/path/Album1/photo(1).jpg", "Album1")
            ],
        }

    def test_parse_title_simple(self, simple_index):
        matcher = FileMatcher(simple_index)
        result = matcher.parse_title("photo.jpg", "/Album1/photo.jpg.json")

        assert result.name == "photo"
        assert result.extension == ".jpg"
        assert result.brackets is None

    def test_parse_title_long_name(self, simple_index):
        matcher = FileMatcher(simple_index)
        long_name = "a" * 50 + ".jpg"  # 54 chars
        result = matcher.parse_title(long_name, "/Album1/test.json")

        assert len(result.name + result.extension) == 51

    def test_parse_title_with_brackets(self, simple_index):
        matcher = FileMatcher(simple_index)
        result = matcher.parse_title("photo.jpg", "/Album1/photo.jpg(1).json")

        assert result.brackets == "(1)"

    def test_find_match_exact(self, simple_index):
        matcher = FileMatcher(simple_index)
        result = matcher.find_match("/path/Album1/photo.jpg.json", "photo.jpg")

        assert result.found is True
        assert len(result.files) == 1
        assert result.files[0].filename == "photo.jpg"

    def test_find_match_with_suffix(self, simple_index):
        # Create index without the base file, only edited version
        index = {
            ("Album1", "photo-edited.jpg"): [
                FileInfo("photo-edited.jpg", "/path/Album1/photo-edited.jpg", "Album1")
            ],
        }
        matcher = FileMatcher(index, suffixes=["", "-edited"])
        result = matcher.find_match("/path/Album1/photo.jpg.json", "photo.jpg")

        assert result.found is True
        assert result.files[0].filename == "photo-edited.jpg"

    def test_find_match_with_brackets(self, simple_index):
        matcher = FileMatcher(simple_index)
        result = matcher.find_match("/path/Album1/photo.jpg(1).json", "photo.jpg")

        assert result.found is True
        assert result.files[0].filename == "photo(1).jpg"

    def test_find_match_not_found(self, simple_index):
        matcher = FileMatcher(simple_index)
        result = matcher.find_match("/path/Album1/missing.jpg.json", "missing.jpg")

        assert result.found is False
        assert len(result.files) == 0
```

### `pef/tests/test_scanner.py`

```python
"""Tests for pef.core.scanner module."""

import os
import pytest

from pef.core.scanner import FileScanner
from pef.core.models import FileInfo


class TestFileScanner:
    """Tests for FileScanner class."""

    def test_scan_finds_files(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        assert scanner.json_count == 4  # 3 in Album1, 1 in Album2
        assert scanner.file_count == 5  # 3 in Album1, 2 in Album2

    def test_scan_builds_index(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        # Check index has correct keys
        assert ("Album1", "photo1.jpg") in scanner.file_index
        assert ("Album2", "image.png") in scanner.file_index

    def test_scan_returns_file_info(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        assert all(isinstance(f, FileInfo) for f in scanner.files)

    def test_scan_with_progress_callback(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        calls = []

        def callback(current, total, message):
            calls.append((current, total, message))

        scanner.scan(on_progress=callback)

        assert len(calls) > 0
        # Last call should indicate completion
        last_call = calls[-1]
        assert "complete" in last_call[2].lower()

    def test_get_stats(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        stats = scanner.get_stats()
        assert stats["json_count"] == 4
        assert stats["file_count"] == 5
        assert stats["album_count"] == 2
```

### `pef/tests/test_models.py`

```python
"""Tests for pef.core.models module."""

from datetime import datetime

import pytest

from pef.core.models import (
    FileInfo,
    GeoData,
    Person,
    JsonMetadata,
    ProcessingStats,
)


class TestGeoData:
    """Tests for GeoData dataclass."""

    def test_from_dict_valid(self):
        data = {"latitude": 40.7128, "longitude": -74.0060, "altitude": 10}
        geo = GeoData.from_dict(data)

        assert geo is not None
        assert geo.latitude == 40.7128
        assert geo.longitude == -74.0060
        assert geo.altitude == 10

    def test_from_dict_none(self):
        assert GeoData.from_dict(None) is None

    def test_from_dict_zero_coords(self):
        data = {"latitude": 0, "longitude": 0}
        assert GeoData.from_dict(data) is None

    def test_is_valid(self):
        geo = GeoData(40.7, -74.0)
        assert geo.is_valid() is True

        geo_zero = GeoData(0, 0)
        assert geo_zero.is_valid() is False


class TestPerson:
    """Tests for Person dataclass."""

    def test_from_list_valid(self):
        data = [{"name": "Alice"}, {"name": "Bob"}]
        people = Person.from_list(data)

        assert len(people) == 2
        assert people[0].name == "Alice"
        assert people[1].name == "Bob"

    def test_from_list_none(self):
        assert Person.from_list(None) == []

    def test_from_list_filters_invalid(self):
        data = [{"name": "Alice"}, {"other": "data"}, {"name": "Bob"}]
        people = Person.from_list(data)

        assert len(people) == 2


class TestJsonMetadata:
    """Tests for JsonMetadata dataclass."""

    def test_has_location(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            geo_data=GeoData(40.7, -74.0)
        )
        assert meta.has_location() is True

    def test_has_location_false(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now()
        )
        assert meta.has_location() is False

    def test_has_people(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            people=[Person("Alice")]
        )
        assert meta.has_people() is True

    def test_get_people_names(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            people=[Person("Alice"), Person("Bob")]
        )
        assert meta.get_people_names() == ["Alice", "Bob"]


class TestProcessingStats:
    """Tests for ProcessingStats dataclass."""

    def test_defaults(self):
        stats = ProcessingStats()
        assert stats.processed == 0
        assert stats.errors == 0

    def test_total_files(self):
        stats = ProcessingStats(processed=10, skipped=5, errors=2)
        assert stats.total_files() == 17
```

### `pytest.ini`

```ini
[pytest]
testpaths = pef/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=pef --cov-report=html

# Run specific test file
pytest pef/tests/test_matcher.py

# Run specific test
pytest pef/tests/test_matcher.py::TestFileMatcher::test_find_match_exact
```

## Acceptance Criteria

1. [ ] All test files created
2. [ ] Fixtures provide sample data
3. [ ] `pytest` runs all tests successfully
4. [ ] Test coverage > 80% for core modules
5. [ ] Tests cover edge cases (long names, brackets, etc.)

## Test Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| utils.py | 95% |
| models.py | 90% |
| matcher.py | 95% |
| scanner.py | 85% |
| processor.py | 80% |
| orchestrator.py | 75% |

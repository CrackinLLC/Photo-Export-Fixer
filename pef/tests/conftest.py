"""Pytest configuration and fixtures."""

import os
import json
import tempfile
import shutil
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
            "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
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
def sample_long_filename(temp_dir: str) -> str:
    """Create a sample with long filename (51-char truncation scenario).

    Google Takeout truncates filenames longer than 51 characters.
    The JSON title contains the original full name, but the actual file
    and JSON filename are truncated.

    Structure:
        temp_dir/
        └── Album/
            ├── aaaaa...aaa.jpg           (47 chars: 44 a's + .jpg, truncated from 54)
            └── aaaaa...aaa.jpg.json      (original title: 50 a's + .jpg = 54 chars)
    """
    album = os.path.join(temp_dir, "Album")
    os.makedirs(album)

    # Original filename would be 54 chars (50 a's + .jpg)
    original_name = "a" * 50 + ".jpg"  # 54 chars total

    # Truncated to 51 chars: 47 chars + .jpg = 51 (but file extension needs room)
    # Actually, Google truncates the name part to fit: 47 a's + .jpg = 51 chars
    truncated_name = "a" * 47 + ".jpg"  # 51 chars

    # Create the truncated file
    with open(os.path.join(album, truncated_name), "wb") as f:
        f.write(b"fake long filename data")

    # JSON filename is also truncated, but title contains original
    json_filename = truncated_name + ".json"
    with open(os.path.join(album, json_filename), "w") as f:
        json.dump({
            "title": original_name,  # Original full 54-char name
            "photoTakenTime": {"timestamp": "1609459200"},
        }, f)

    return temp_dir


@pytest.fixture
def sample_duplicates(temp_dir: str) -> str:
    """Create a sample with duplicate files (bracket notation scenario).

    When Google Takeout exports duplicate files with the same name,
    it adds (1), (2), etc. to both the file and JSON.

    Structure:
        temp_dir/
        └── Album/
            ├── photo.jpg
            ├── photo.jpg.json
            ├── photo(1).jpg
            ├── photo.jpg(1).json      (note: brackets on JSON, not on title inside)
            ├── photo(2).jpg
            └── photo.jpg(2).json
    """
    album = os.path.join(temp_dir, "Album")
    os.makedirs(album)

    # Original file
    with open(os.path.join(album, "photo.jpg"), "wb") as f:
        f.write(b"original photo data")
    with open(os.path.join(album, "photo.jpg.json"), "w") as f:
        json.dump({
            "title": "photo.jpg",
            "photoTakenTime": {"timestamp": "1609459200"},
        }, f)

    # First duplicate - file has (1), JSON filename has (1) after .jpg
    with open(os.path.join(album, "photo(1).jpg"), "wb") as f:
        f.write(b"duplicate 1 data")
    with open(os.path.join(album, "photo.jpg(1).json"), "w") as f:
        json.dump({
            "title": "photo.jpg",  # Title is still the original name
            "photoTakenTime": {"timestamp": "1612137600"},
        }, f)

    # Second duplicate
    with open(os.path.join(album, "photo(2).jpg"), "wb") as f:
        f.write(b"duplicate 2 data")
    with open(os.path.join(album, "photo.jpg(2).json"), "w") as f:
        json.dump({
            "title": "photo.jpg",  # Title is still the original name
            "photoTakenTime": {"timestamp": "1614556800"},
        }, f)

    return temp_dir

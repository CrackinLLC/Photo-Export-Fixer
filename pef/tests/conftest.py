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

"""Tests for pef.core.utils module."""

import os

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
        # Note: os.path.basename(os.path.dirname(...)) works cross-platform
        path = os.path.join("photos", "Vacation 2023", "photo.jpg")
        assert get_album_name(path) == "Vacation 2023"

    def test_handles_windows_paths(self):
        # Use os.path.join to create platform-appropriate path
        path = os.path.join("C:", "Photos", "Album", "image.png")
        assert get_album_name(path) == "Album"


class TestNormalizePath:
    """Tests for normalize_path() function."""

    def test_strips_whitespace(self):
        result = normalize_path("  /path/to/file  ")
        assert result.strip() == result

    def test_expands_home(self):
        result = normalize_path("~/photos")
        assert "~" not in result

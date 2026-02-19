"""Tests for pef.core.utils module."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

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

    def test_creates_placeholder_file(self, temp_dir):
        """Verify get_unique_path creates an empty placeholder file."""
        path = os.path.join(temp_dir, "new_file.txt")
        result = get_unique_path(path)
        assert result == path
        assert os.path.exists(path)
        assert os.path.getsize(path) == 0

    def test_concurrent_same_destination_no_overwrites(self, temp_dir):
        """Verify concurrent calls for the same path produce unique paths."""
        base_path = os.path.join(temp_dir, "photo.jpg")
        num_threads = 20

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(get_unique_path, base_path)
                for _ in range(num_threads)
            ]
            results = [f.result() for f in as_completed(futures)]

        # All paths must be unique
        assert len(set(results)) == num_threads
        # All paths must exist on disk (placeholder files)
        for path in results:
            assert os.path.exists(path)


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

    def test_existing_dir_no_onlynew_returns_same(self, temp_dir):
        """Verify existing directory returned as-is when onlynew=False."""
        path = os.path.join(temp_dir, "existing")
        os.makedirs(path)

        result = checkout_dir(path, onlynew=False)
        assert result == path
        assert os.path.isdir(result)

    def test_onlynew_creates_multiple_unique(self, temp_dir):
        """Verify onlynew creates sequentially numbered directories."""
        path = os.path.join(temp_dir, "dir")
        os.makedirs(path)

        result1 = checkout_dir(path, onlynew=True)
        assert result1 == os.path.join(temp_dir, "dir(1)")

        result2 = checkout_dir(path, onlynew=True)
        assert result2 == os.path.join(temp_dir, "dir(2)")

    def test_creates_nested_directories(self, temp_dir):
        """Verify nested directories are created."""
        path = os.path.join(temp_dir, "a", "b", "c")
        result = checkout_dir(path)

        assert result == path
        assert os.path.isdir(path)

    def test_raises_error_if_file_exists(self, temp_dir):
        """Verify error raised when path is an existing file."""
        filepath = os.path.join(temp_dir, "is_a_file")
        with open(filepath, "w") as f:
            f.write("test content")

        with pytest.raises(ValueError) as excinfo:
            checkout_dir(filepath)

        assert "exists as a file" in str(excinfo.value)


class TestGetAlbumName:
    """Tests for get_album_name() function."""

    def test_extracts_parent_folder(self):
        # Note: os.path.basename(os.path.dirname(...)) works cross-platform
        path = os.path.join("photos", "Vacation 2023", "photo.jpg")
        assert get_album_name(path) == "Vacation 2023"

    def test_handles_nested_paths(self):
        # Test with deeply nested path structure
        path = os.path.join("root", "Photos", "Album", "image.png")
        assert get_album_name(path) == "Album"

    def test_handles_single_level(self):
        # Test with minimal path
        path = os.path.join("Album", "image.png")
        assert get_album_name(path) == "Album"


class TestNormalizePath:
    """Tests for normalize_path() function."""

    def test_strips_whitespace(self):
        result = normalize_path("  /path/to/file  ")
        assert result.strip() == result

    def test_expands_home(self):
        result = normalize_path("~/photos")
        assert "~" not in result

    @patch("pef.core.utils.sys")
    def test_long_path_gets_prefix_on_windows(self, mock_sys):
        """Paths >= 260 chars get \\\\?\\ prefix on Windows."""
        mock_sys.platform = "win32"
        # Build a path that exceeds 260 chars
        long_path = "C:\\Users\\test\\" + "a" * 250 + "\\file.txt"
        assert len(long_path) >= 260

        result = normalize_path(long_path)
        assert result.startswith("\\\\?\\")

    @patch("pef.core.utils.sys")
    def test_short_path_no_prefix_on_windows(self, mock_sys):
        """Paths < 260 chars should NOT get \\\\?\\ prefix."""
        mock_sys.platform = "win32"
        short_path = "C:\\Users\\test\\file.txt"
        assert len(short_path) < 260

        result = normalize_path(short_path)
        assert not result.startswith("\\\\?\\")

    @patch("pef.core.utils.sys")
    def test_no_prefix_on_non_windows(self, mock_sys):
        """Long paths on non-Windows should NOT get \\\\?\\ prefix."""
        mock_sys.platform = "linux"
        long_path = "/home/test/" + "a" * 260 + "/file.txt"
        assert len(long_path) >= 260

        result = normalize_path(long_path)
        assert not result.startswith("\\\\?\\")

    @patch("pef.core.utils.sys")
    def test_no_double_prefix(self, mock_sys):
        """Already-prefixed paths should not get double prefix."""
        mock_sys.platform = "win32"
        prefixed_path = "\\\\?\\" + "C:\\Users\\test\\" + "a" * 250 + "\\file.txt"

        result = normalize_path(prefixed_path)
        assert not result.startswith("\\\\?\\\\\\?\\")
        assert result.startswith("\\\\?\\")

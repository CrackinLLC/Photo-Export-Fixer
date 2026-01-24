"""Tests for pef.core.scanner module."""

import os
import warnings
import pytest

from pef.core.scanner import FileScanner, scan_directory, get_file_names
from pef.core.models import FileInfo


class TestFileScanner:
    """Tests for FileScanner class."""

    def test_scan_finds_files(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        assert scanner.json_count == 3  # photo1.json, photo2.json, image.json
        assert scanner.file_count == 5  # photo1, photo2, video, image, image-edited

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
        assert stats["json_count"] == 3
        assert stats["file_count"] == 5
        assert stats["album_count"] == 2

    def test_lookup(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        result = scanner.lookup("Album1", "photo1.jpg")
        assert len(result) == 1
        assert result[0].filename == "photo1.jpg"

    def test_lookup_nonexistent(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()

        result = scanner.lookup("Album1", "nonexistent.jpg")
        assert len(result) == 0

    def test_is_scanned_false_initially(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        assert scanner.is_scanned is False

    def test_is_scanned_true_after_scan(self, sample_takeout):
        scanner = FileScanner(sample_takeout)
        scanner.scan()
        assert scanner.is_scanned is True

    def test_empty_directory(self, temp_dir):
        scanner = FileScanner(temp_dir)
        scanner.scan()
        assert scanner.json_count == 0
        assert scanner.file_count == 0


class TestScanDirectory:
    """Tests for scan_directory() convenience function."""

    def test_returns_tuple(self, sample_takeout):
        result = scan_directory(sample_takeout)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_finds_files(self, sample_takeout):
        jsons, files, index = scan_directory(sample_takeout)
        assert len(jsons) == 3
        assert len(files) == 5
        assert isinstance(index, dict)


class TestGetFileNames:
    """Tests for get_file_names() backwards-compatible function."""

    def test_returns_tuple(self, sample_takeout):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = get_file_names(sample_takeout)

            # Should emit deprecation warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_returns_correct_types(self, sample_takeout):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            jsons, files, index = get_file_names(sample_takeout)

        # jsons is list of paths
        assert isinstance(jsons, list)
        assert all(isinstance(j, str) for j in jsons)

        # files is list of dicts
        assert isinstance(files, list)
        assert all(isinstance(f, dict) for f in files)
        assert all("filename" in f and "filepath" in f for f in files)

        # index is dict
        assert isinstance(index, dict)

    def test_correct_counts(self, sample_takeout):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            jsons, files, index = get_file_names(sample_takeout)

        assert len(jsons) == 3
        assert len(files) == 5

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

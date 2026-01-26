"""Tests for Unicode normalization (cross-platform filename compatibility)."""

import unicodedata

import pytest

from pef.core.utils import normalize_filename
from pef.core.scanner import FileScanner
from pef.core.matcher import FileMatcher
from pef.core.models import FileInfo


class TestNormalizeFilename:
    """Test the normalize_filename utility function."""

    def test_nfc_passthrough(self):
        """NFC input should pass through unchanged."""
        nfc = "Café.jpg"
        result = normalize_filename(nfc)
        assert result == nfc
        assert result.encode() == nfc.encode()

    def test_nfd_to_nfc(self):
        """NFD input should be converted to NFC."""
        # Create NFD string explicitly (simulates macOS filesystem)
        nfd = unicodedata.normalize("NFD", "Café.jpg")
        nfc = unicodedata.normalize("NFC", "Café.jpg")

        # NFD and NFC are different strings with different bytes
        assert nfd != nfc  # Different string representations
        assert nfd.encode() != nfc.encode()  # Different bytes

        # normalize_filename should produce NFC
        result = normalize_filename(nfd)
        assert result == nfc
        assert result.encode() == nfc.encode()

    def test_ascii_unchanged(self):
        """ASCII filenames should pass through unchanged."""
        ascii_name = "photo123.jpg"
        assert normalize_filename(ascii_name) == ascii_name

    def test_various_accented_characters(self):
        """Test normalization of various accented characters."""
        test_cases = [
            "naïve.jpg",       # i with diaeresis
            "résumé.pdf",      # multiple accents
            "Ängström.tiff",   # Swedish
            "Müller.heic",     # German umlaut
            "señor.png",       # Spanish ñ
            "crème.jpg",       # French accent
        ]

        for filename in test_cases:
            # Create both NFD and NFC versions
            nfd = unicodedata.normalize("NFD", filename)
            nfc = unicodedata.normalize("NFC", filename)

            # Both should normalize to the same NFC result
            assert normalize_filename(nfd) == normalize_filename(nfc)
            assert normalize_filename(nfd).encode() == nfc.encode()

    def test_asian_characters(self):
        """Test normalization of Asian characters."""
        test_cases = [
            "日本語.png",      # Japanese
            "한국어.jpg",      # Korean
            "中文.heic",       # Chinese
        ]

        for filename in test_cases:
            # These typically don't have NFD/NFC differences,
            # but should still pass through correctly
            result = normalize_filename(filename)
            assert result == filename

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert normalize_filename("") == ""

    def test_extension_preserved(self):
        """File extension should be preserved after normalization."""
        nfd = unicodedata.normalize("NFD", "tëst.JPEG")
        result = normalize_filename(nfd)
        assert result.endswith(".JPEG")


class TestScannerNormalization:
    """Test that FileScanner normalizes filenames."""

    def test_scanner_normalizes_filenames(self, tmp_path):
        """Scanner should store NFC-normalized filenames."""
        # Create a file with NFD name (simulating macOS)
        nfd_name = unicodedata.normalize("NFD", "tëst.jpg")
        nfc_name = unicodedata.normalize("NFC", "tëst.jpg")
        (tmp_path / nfd_name).touch()

        scanner = FileScanner(str(tmp_path))
        scanner.scan()

        # The stored filename should be NFC
        assert len(scanner.files) == 1
        assert scanner.files[0].filename.encode() == nfc_name.encode()

    def test_scanner_index_uses_normalized_keys(self, tmp_path):
        """File index should use NFC-normalized keys."""
        # Create file with NFD name
        nfd_name = unicodedata.normalize("NFD", "Café.jpg")
        nfc_name = unicodedata.normalize("NFC", "Café.jpg")
        (tmp_path / nfd_name).touch()

        scanner = FileScanner(str(tmp_path))
        scanner.scan()

        # Lookup with NFC name should succeed
        album = tmp_path.name
        results = scanner.lookup(album, nfc_name)
        assert len(results) == 1

    def test_scanner_preserves_original_filepath(self, tmp_path):
        """Scanner should preserve original filepath for file operations."""
        # Create file with NFD name
        nfd_name = unicodedata.normalize("NFD", "tëst.jpg")
        (tmp_path / nfd_name).touch()

        scanner = FileScanner(str(tmp_path))
        scanner.scan()

        # The filepath should be the actual filesystem path
        assert len(scanner.files) == 1
        # filepath should exist and be usable for file operations
        import os
        assert os.path.exists(scanner.files[0].filepath)

    def test_scanner_normalizes_album_name(self, tmp_path):
        """Scanner should normalize album (directory) names."""
        # Create subdirectory with NFD name
        nfd_album = unicodedata.normalize("NFD", "Vacación")
        nfc_album = unicodedata.normalize("NFC", "Vacación")
        album_dir = tmp_path / nfd_album
        album_dir.mkdir()
        (album_dir / "photo.jpg").touch()

        scanner = FileScanner(str(tmp_path))
        scanner.scan()

        # Album name should be NFC
        assert len(scanner.files) == 1
        assert scanner.files[0].album_name.encode() == nfc_album.encode()


class TestMatcherNormalization:
    """Test that FileMatcher handles normalized lookups."""

    def test_matcher_finds_nfd_file_with_nfc_title(self):
        """Matcher should find file when title (NFC) differs from filename (NFD)."""
        # Simulate: filesystem has NFD filename, JSON has NFC title
        nfd_filename = unicodedata.normalize("NFD", "Café.jpg")
        nfc_title = unicodedata.normalize("NFC", "Café.jpg")
        # After scanner normalization, both become NFC
        normalized = unicodedata.normalize("NFC", "Café.jpg")

        # Create file index with normalized filename (as scanner would)
        file_info = FileInfo(
            filename=normalized,
            filepath="/path/to/" + nfd_filename,  # Original path
            album_name="Album"
        )
        file_index = {("Album", normalized): [file_info]}

        matcher = FileMatcher(file_index)
        result = matcher.find_match("/path/Album/Café.jpg.json", nfc_title)

        assert result.found
        assert len(result.files) == 1

    def test_matcher_normalizes_title(self):
        """Matcher should normalize titles from JSON."""
        # JSON title might be NFD or NFC depending on source
        nfd_title = unicodedata.normalize("NFD", "naïve.jpg")
        nfc_filename = unicodedata.normalize("NFC", "naïve.jpg")

        file_info = FileInfo(
            filename=nfc_filename,
            filepath="/path/to/naïve.jpg",
            album_name="Album"
        )
        file_index = {("Album", nfc_filename): [file_info]}

        matcher = FileMatcher(file_index)
        # Pass NFD title - should still match
        result = matcher.find_match("/path/Album/naïve.jpg.json", nfd_title)

        assert result.found

    def test_matcher_normalizes_album_in_lookup(self):
        """Matcher should normalize album name from JSON path."""
        nfc_album = unicodedata.normalize("NFC", "Ängström")
        nfc_filename = "photo.jpg"

        file_info = FileInfo(
            filename=nfc_filename,
            filepath=f"/path/{nfc_album}/photo.jpg",
            album_name=nfc_album
        )
        file_index = {(nfc_album, nfc_filename): [file_info]}

        matcher = FileMatcher(file_index)
        # JSON path has NFD album name
        nfd_album = unicodedata.normalize("NFD", "Ängström")
        json_path = f"/path/{nfd_album}/photo.jpg.json"

        result = matcher.find_match(json_path, "photo.jpg")
        assert result.found

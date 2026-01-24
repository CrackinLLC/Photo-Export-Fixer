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

"""Tests for pef.core.matcher module."""

import warnings
import pytest

from pef.core.matcher import FileMatcher, ParsedTitle, find_file, DEFAULT_SUFFIXES
from pef.core.models import FileInfo


class TestParsedTitle:
    """Tests for ParsedTitle dataclass."""

    def test_build_filename_simple(self):
        pt = ParsedTitle(name="photo", extension=".jpg", duplicate_suffix=None)
        assert pt.build_filename() == "photo.jpg"

    def test_build_filename_with_suffix(self):
        pt = ParsedTitle(name="photo", extension=".jpg", duplicate_suffix=None)
        assert pt.build_filename("-edited") == "photo-edited.jpg"

    def test_build_filename_with_brackets(self):
        pt = ParsedTitle(name="photo", extension=".jpg", duplicate_suffix="(1)")
        assert pt.build_filename() == "photo(1).jpg"

    def test_build_filename_with_suffix_and_brackets(self):
        pt = ParsedTitle(name="photo", extension=".jpg", duplicate_suffix="(1)")
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
        assert result.duplicate_suffix is None

    def test_parse_title_long_name(self, simple_index):
        matcher = FileMatcher(simple_index)
        long_name = "a" * 50 + ".jpg"  # 54 chars
        result = matcher.parse_title(long_name, "/Album1/test.json")

        assert len(result.name + result.extension) == 51

    def test_parse_title_with_brackets(self, simple_index):
        matcher = FileMatcher(simple_index)
        result = matcher.parse_title("photo.jpg", "/Album1/photo.jpg(1).json")

        assert result.duplicate_suffix == "(1)"

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


class TestFindFile:
    """Tests for find_file() backwards-compatible function."""

    @pytest.fixture
    def dict_index(self):
        """Create index using dict format for backwards compat."""
        return {
            ("Album1", "photo.jpg"): [
                {"filename": "photo.jpg", "filepath": "/path/Album1/photo.jpg", "albumname": "Album1"}
            ],
            ("Album1", "photo-edited.jpg"): [
                {"filename": "photo-edited.jpg", "filepath": "/path/Album1/photo-edited.jpg", "albumname": "Album1"}
            ],
        }

    def test_emits_deprecation_warning(self, dict_index):
        jsondata = {"title": "photo.jpg", "filepath": "/Album1/photo.jpg.json"}

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            find_file(jsondata, dict_index, DEFAULT_SUFFIXES)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_returns_tuple(self, dict_index):
        jsondata = {"title": "photo.jpg", "filepath": "/Album1/photo.jpg.json"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = find_file(jsondata, dict_index, DEFAULT_SUFFIXES)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_finds_match(self, dict_index):
        jsondata = {"title": "photo.jpg", "filepath": "/Album1/photo.jpg.json"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            found, files = find_file(jsondata, dict_index, DEFAULT_SUFFIXES)

        assert found is True
        assert len(files) == 1
        assert files[0]["filename"] == "photo.jpg"

    def test_not_found(self, dict_index):
        jsondata = {"title": "missing.jpg", "filepath": "/Album1/missing.jpg.json"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            found, files = find_file(jsondata, dict_index, DEFAULT_SUFFIXES)

        assert found is False
        # When not found, returns a list with json info for logging purposes
        assert len(files) == 1
        assert files[0]["title"] == "missing.jpg"


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_is_matched_true_when_found(self):
        from pef.core.matcher import MatchResult
        result = MatchResult(found=True, files=[], json_path="/test.json", title="test.jpg")
        assert result.is_matched is True

    def test_is_matched_false_when_not_found(self):
        from pef.core.matcher import MatchResult
        result = MatchResult(found=False, files=[], json_path="/test.json", title="test.jpg")
        assert result.is_matched is False

    def test_is_matched_alias_for_found(self):
        from pef.core.matcher import MatchResult
        result = MatchResult(found=True, files=[], json_path="/test.json", title="test.jpg")
        assert result.is_matched == result.found


class TestFileMatcherFindMatchInIndex:
    """Tests for FileMatcher.find_match_in_index() method."""

    def test_uses_provided_index_not_default(self):
        """Verify find_match_in_index uses the provided index, not self.file_index."""
        default_index = {
            ("Album1", "photo.jpg"): [FileInfo("photo.jpg", "/default/photo.jpg", "Album1")]
        }
        alternate_index = {
            ("Album1", "photo.jpg"): [FileInfo("photo.jpg", "/alternate/photo.jpg", "Album1")]
        }

        matcher = FileMatcher(default_index)
        result = matcher.find_match_in_index(
            "/path/Album1/photo.jpg.json",
            "photo.jpg",
            alternate_index
        )

        assert result.found is True
        assert result.files[0].filepath == "/alternate/photo.jpg"

    def test_returns_empty_when_not_in_provided_index(self):
        """Verify returns not found when file not in provided index."""
        default_index = {
            ("Album1", "photo.jpg"): [FileInfo("photo.jpg", "/default/photo.jpg", "Album1")]
        }
        empty_index = {}

        matcher = FileMatcher(default_index)
        result = matcher.find_match_in_index(
            "/path/Album1/photo.jpg.json",
            "photo.jpg",
            empty_index
        )

        assert result.found is False
        assert len(result.files) == 0

    def test_tries_suffixes_in_order(self):
        """Verify suffixes are tried in order."""
        index = {
            ("Album1", "photo-edited.jpg"): [
                FileInfo("photo-edited.jpg", "/path/photo-edited.jpg", "Album1")
            ]
        }

        matcher = FileMatcher({}, suffixes=["", "-edited", "-backup"])
        result = matcher.find_match_in_index(
            "/path/Album1/photo.jpg.json",
            "photo.jpg",
            index
        )

        assert result.found is True
        assert result.files[0].filename == "photo-edited.jpg"


class TestDefaultSuffixes:
    """Tests for DEFAULT_SUFFIXES constant."""

    def test_default_suffixes_exists(self):
        assert DEFAULT_SUFFIXES is not None
        assert isinstance(DEFAULT_SUFFIXES, list)

    def test_default_suffixes_contains_empty(self):
        assert "" in DEFAULT_SUFFIXES

    def test_default_suffixes_contains_edited(self):
        assert "-edited" in DEFAULT_SUFFIXES

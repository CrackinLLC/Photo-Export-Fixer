"""Tests for pef.core.matcher module."""

import pytest

from pef.core.matcher import FileMatcher, ParsedTitle, DEFAULT_SUFFIXES
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

    def test_parse_title_long_ascii_name(self, simple_index):
        """ASCII-only filename >51 chars — verify byte-based truncation (same as codepoint for ASCII)."""
        matcher = FileMatcher(simple_index)
        long_name = "a" * 50 + ".jpg"  # 54 bytes / 54 chars
        result = matcher.parse_title(long_name, "/Album1/test.json")

        full = result.name + result.extension
        assert len(full.encode("utf-8")) == 51

    def test_parse_title_cjk_truncation(self, simple_index):
        """CJK filename exceeding 51 UTF-8 bytes but under 51 codepoints — verify byte-based truncation."""
        matcher = FileMatcher(simple_index)
        # Each CJK char is 3 UTF-8 bytes. 16 chars = 48 bytes + ".jpg" (4 bytes) = 52 bytes > 51
        cjk_name = "\u4e00" * 16 + ".jpg"
        result = matcher.parse_title(cjk_name, "/Album1/test.json")

        full = result.name + result.extension
        # Budget for name = 51 - 4 (.jpg) = 47 bytes. 47 // 3 = 15 chars = 45 bytes
        assert len(full.encode("utf-8")) <= 51
        assert result.name == "\u4e00" * 15  # 15 CJK chars fit in 45 bytes

    def test_parse_title_emoji_truncation(self, simple_index):
        """Emoji filename (4-byte chars) — verify truncation at valid UTF-8 boundary."""
        matcher = FileMatcher(simple_index)
        # Each emoji is 4 UTF-8 bytes. 13 emojis = 52 bytes + ".jpg" (4 bytes) = 56 bytes
        emoji_name = "\U0001F600" * 13 + ".jpg"
        result = matcher.parse_title(emoji_name, "/Album1/test.json")

        full = result.name + result.extension
        assert len(full.encode("utf-8")) <= 51
        # Budget = 47 bytes, 47 // 4 = 11 emojis = 44 bytes
        assert result.name == "\U0001F600" * 11

    def test_parse_title_mixed_ascii_cjk_truncation(self, simple_index):
        """Mixed ASCII/CJK filename — verify correct truncation point."""
        matcher = FileMatcher(simple_index)
        # "hello" (5 bytes) + 16 CJK chars (48 bytes) = 53 bytes + ".jpg" (4) = 57 bytes
        mixed_name = "hello" + "\u4e00" * 16 + ".jpg"
        result = matcher.parse_title(mixed_name, "/Album1/test.json")

        full = result.name + result.extension
        assert len(full.encode("utf-8")) <= 51
        # Budget = 47 bytes. "hello" = 5 bytes, remaining = 42 bytes, 42 // 3 = 14 CJK chars
        assert result.name == "hello" + "\u4e00" * 14

    def test_parse_title_no_truncation_under_limit(self, simple_index):
        """Short filename should not be truncated."""
        matcher = FileMatcher(simple_index)
        result = matcher.parse_title("short.jpg", "/Album1/test.json")
        assert result.name == "short"
        assert result.extension == ".jpg"

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


class TestFileMatcherWithAlternateIndex:
    """Tests for FileMatcher.find_match() with alternate file_index parameter."""

    def test_uses_provided_index_not_default(self):
        """Verify find_match uses the provided index, not self.file_index."""
        default_index = {
            ("Album1", "photo.jpg"): [FileInfo("photo.jpg", "/default/photo.jpg", "Album1")]
        }
        alternate_index = {
            ("Album1", "photo.jpg"): [FileInfo("photo.jpg", "/alternate/photo.jpg", "Album1")]
        }

        matcher = FileMatcher(default_index)
        result = matcher.find_match(
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
        result = matcher.find_match(
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
        result = matcher.find_match(
            "/path/Album1/photo.jpg.json",
            "photo.jpg",
            index
        )

        assert result.found is True
        assert result.files[0].filename == "photo-edited.jpg"


class TestTier3CaseInsensitiveMatching:
    """Tests for Tier 3 case-insensitive matching fallback."""

    def test_case_insensitive_match(self):
        """Match 'IMG_001.JPG' title against file indexed as 'img_001.jpg'."""
        file_index = {
            ("Album1", "img_001.jpg"): [
                FileInfo("img_001.jpg", "/path/Album1/img_001.jpg", "Album1")
            ],
        }
        lowercase_index = {
            ("album1", "img_001.jpg"): [
                FileInfo("img_001.jpg", "/path/Album1/img_001.jpg", "Album1")
            ],
        }
        matcher = FileMatcher(file_index, lowercase_index=lowercase_index)
        result = matcher.find_match("/path/Album1/IMG_001.JPG.json", "IMG_001.JPG")

        assert result.found is True
        assert result.files[0].filename == "img_001.jpg"

    def test_exact_match_preferred_over_case_insensitive(self):
        """When both 'Photo.jpg' and 'photo.jpg' exist, title 'Photo.jpg' gets exact match."""
        file_index = {
            ("Album1", "Photo.jpg"): [
                FileInfo("Photo.jpg", "/path/Album1/Photo.jpg", "Album1")
            ],
            ("Album1", "photo.jpg"): [
                FileInfo("photo.jpg", "/path/Album1/photo.jpg", "Album1")
            ],
        }
        lowercase_index = {
            ("album1", "photo.jpg"): [
                FileInfo("Photo.jpg", "/path/Album1/Photo.jpg", "Album1"),
                FileInfo("photo.jpg", "/path/Album1/photo.jpg", "Album1"),
            ],
        }
        matcher = FileMatcher(file_index, lowercase_index=lowercase_index)
        result = matcher.find_match("/path/Album1/Photo.jpg.json", "Photo.jpg")

        assert result.found is True
        # Exact match from Tier 1, not case-insensitive from Tier 3
        assert len(result.files) == 1
        assert result.files[0].filename == "Photo.jpg"

    def test_no_lowercase_index_skips_tier3(self):
        """Without lowercase_index, Tier 3 is skipped and match fails."""
        file_index = {
            ("Album1", "img_001.jpg"): [
                FileInfo("img_001.jpg", "/path/Album1/img_001.jpg", "Album1")
            ],
        }
        matcher = FileMatcher(file_index)
        result = matcher.find_match("/path/Album1/IMG_001.JPG.json", "IMG_001.JPG")

        assert result.found is False

    def test_case_insensitive_with_suffix(self):
        """Case-insensitive match works with suffix variations."""
        file_index = {}
        lowercase_index = {
            ("album1", "photo-edited.jpg"): [
                FileInfo("photo-edited.jpg", "/path/Album1/photo-edited.jpg", "Album1")
            ],
        }
        matcher = FileMatcher(file_index, suffixes=["", "-edited"], lowercase_index=lowercase_index)
        result = matcher.find_match("/path/Album1/PHOTO.JPG.json", "PHOTO.JPG")

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

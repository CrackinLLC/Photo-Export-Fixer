"""Tests for pef.core.models module."""

from datetime import datetime


from pef.core.models import (
    FileInfo,
    GeoData,
    Person,
    JsonMetadata,
    ProcessingStats,
    UnprocessedItem,
    DryRunResult,
    ProcessRunResult,
)


class TestGeoData:
    """Tests for GeoData dataclass."""

    def test_from_dict_valid(self):
        data = {"latitude": 40.7128, "longitude": -74.0060, "altitude": 10}
        geo = GeoData.from_dict(data)

        assert geo is not None
        assert geo.latitude == 40.7128
        assert geo.longitude == -74.0060
        assert geo.altitude == 10

    def test_from_dict_none(self):
        assert GeoData.from_dict(None) is None

    def test_from_dict_empty_dict(self):
        """Empty dict should return None."""
        assert GeoData.from_dict({}) is None

    def test_from_dict_missing_latitude(self):
        """Missing latitude should return None."""
        data = {"longitude": -74.0}
        assert GeoData.from_dict(data) is None

    def test_from_dict_missing_longitude(self):
        """Missing longitude should return None."""
        data = {"latitude": 40.7}
        assert GeoData.from_dict(data) is None

    def test_from_dict_zero_coords_are_valid(self):
        """(0,0) is a valid location (Gulf of Guinea) and should be accepted."""
        data = {"latitude": 0, "longitude": 0}
        geo = GeoData.from_dict(data)

        assert geo is not None
        assert geo.latitude == 0
        assert geo.longitude == 0

    def test_from_dict_default_altitude(self):
        """Missing altitude should default to 0."""
        data = {"latitude": 40.7, "longitude": -74.0}
        geo = GeoData.from_dict(data)

        assert geo is not None
        assert geo.altitude == 0.0

    def test_is_valid_normal_coords(self):
        geo = GeoData(40.7, -74.0)
        assert geo.is_valid() is True

    def test_is_valid_zero_coords(self):
        """(0,0) is a valid GPS location."""
        geo_zero = GeoData(0, 0)
        assert geo_zero.is_valid() is True

    def test_is_valid_extreme_coords(self):
        """Extreme but valid coordinates should be accepted."""
        geo_north_pole = GeoData(90.0, 0.0)
        geo_south_pole = GeoData(-90.0, 0.0)
        geo_date_line = GeoData(0.0, 180.0)
        geo_date_line_neg = GeoData(0.0, -180.0)

        assert geo_north_pole.is_valid() is True
        assert geo_south_pole.is_valid() is True
        assert geo_date_line.is_valid() is True
        assert geo_date_line_neg.is_valid() is True

    def test_is_valid_rejects_invalid_latitude(self):
        """Latitude outside -90 to 90 should be invalid."""
        geo_too_high = GeoData(95.0, 0.0)
        geo_too_low = GeoData(-95.0, 0.0)

        assert geo_too_high.is_valid() is False
        assert geo_too_low.is_valid() is False

    def test_is_valid_rejects_invalid_longitude(self):
        """Longitude outside -180 to 180 should be invalid."""
        geo_too_high = GeoData(0.0, 185.0)
        geo_too_low = GeoData(0.0, -185.0)

        assert geo_too_high.is_valid() is False
        assert geo_too_low.is_valid() is False


class TestPerson:
    """Tests for Person dataclass."""

    def test_from_list_valid(self):
        data = [{"name": "Alice"}, {"name": "Bob"}]
        people = Person.from_list(data)

        assert len(people) == 2
        assert people[0].name == "Alice"
        assert people[1].name == "Bob"

    def test_from_list_none(self):
        assert Person.from_list(None) == []

    def test_from_list_filters_invalid(self):
        data = [{"name": "Alice"}, {"other": "data"}, {"name": "Bob"}]
        people = Person.from_list(data)

        assert len(people) == 2


class TestJsonMetadata:
    """Tests for JsonMetadata dataclass."""

    def test_has_location(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            geo_data=GeoData(40.7, -74.0)
        )
        assert meta.has_location() is True

    def test_has_location_false(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now()
        )
        assert meta.has_location() is False

    def test_has_people(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            people=[Person("Alice")]
        )
        assert meta.has_people() is True

    def test_get_people_names(self):
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            people=[Person("Alice"), Person("Bob")]
        )
        assert meta.get_people_names() == ["Alice", "Bob"]

    def test_filename_property(self):
        """Verify filename property extracts basename from filepath."""
        meta = JsonMetadata(
            filepath="/path/to/album/photo.jpg.json",
            title="photo.jpg",
            date=datetime.now()
        )
        assert meta.filename == "photo.jpg.json"

    def test_get_coordinates_string_with_location(self):
        """Verify get_coordinates_string returns formatted string."""
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            geo_data=GeoData(40.7128, -74.0060)
        )
        assert meta.get_coordinates_string() == "40.7128,-74.006"

    def test_get_coordinates_string_without_location(self):
        """Verify get_coordinates_string returns None when no location."""
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now()
        )
        assert meta.get_coordinates_string() is None

    def test_get_coordinates_string_zero_coords(self):
        """Verify get_coordinates_string works for (0,0) location."""
        meta = JsonMetadata(
            filepath="/test.json",
            title="test.jpg",
            date=datetime.now(),
            geo_data=GeoData(0.0, 0.0)
        )
        assert meta.get_coordinates_string() == "0.0,0.0"


class TestProcessingStats:
    """Tests for ProcessingStats dataclass."""

    def test_defaults(self):
        stats = ProcessingStats()
        assert stats.processed == 0
        assert stats.errors == 0

    def test_total_files(self):
        stats = ProcessingStats(processed=10, skipped=5, errors=2)
        assert stats.total_files() == 17


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_basic_creation(self):
        fi = FileInfo(
            filename="photo.jpg",
            filepath="/path/to/photo.jpg",
            album_name="Album"
        )
        assert fi.filename == "photo.jpg"
        assert fi.filepath == "/path/to/photo.jpg"
        assert fi.album_name == "Album"

    def test_optional_fields(self):
        fi = FileInfo(
            filename="photo.jpg",
            filepath="/path/to/photo.jpg",
            album_name="Album"
        )
        assert fi.output_path is None
        assert fi.json_path is None


class TestUnprocessedItem:
    """Tests for UnprocessedItem dataclass."""

    def test_basic_creation(self):
        item = UnprocessedItem(
            relative_path="Album/photo.jpg",
            reason="No matching JSON found"
        )
        assert item.relative_path == "Album/photo.jpg"
        assert item.reason == "No matching JSON found"
        assert item.source_path == ""

    def test_with_all_fields(self):
        item = UnprocessedItem(
            relative_path="Album/photo.jpg",
            reason="No matching JSON found",
            source_path="/path/to/photo.jpg"
        )
        assert item.relative_path == "Album/photo.jpg"
        assert item.reason == "No matching JSON found"
        assert item.source_path == "/path/to/photo.jpg"


class TestDryRunResult:
    """Tests for DryRunResult dataclass."""

    def test_defaults(self):
        result = DryRunResult()
        assert result.json_count == 0
        assert result.file_count == 0
        assert result.matched_count == 0
        assert result.exiftool_available is False
        assert result.errors == []

    def test_with_counts(self):
        result = DryRunResult(
            json_count=100,
            file_count=150,
            matched_count=95,
            with_gps=50,
            with_people=30
        )
        assert result.json_count == 100
        assert result.unmatched_json_count == 0
        assert result.unmatched_file_count == 0


class TestProcessRunResultClass:
    """Tests for ProcessRunResult dataclass."""

    def test_basic_creation(self):
        stats = ProcessingStats(processed=10)
        result = ProcessRunResult(
            stats=stats,
            output_dir="/output",
            pef_dir="/output/_pef",
            summary_file="/output/_pef/summary.txt",
            elapsed_time=5.5,
            start_time="2021-01-01 12:00:00",
            end_time="2021-01-01 12:00:05"
        )
        assert result.stats.processed == 10
        assert result.output_dir == "/output"
        assert result.elapsed_time == 5.5
        assert result.errors == []

    def test_resume_fields_defaults(self):
        """Verify resume fields default to False/0."""
        stats = ProcessingStats()
        result = ProcessRunResult(
            stats=stats,
            output_dir="/output",
            pef_dir="/output/_pef",
            summary_file="/output/_pef/summary.txt",
            elapsed_time=0,
            start_time="",
            end_time=""
        )
        assert result.resumed is False
        assert result.skipped_count == 0
        assert result.interrupted is False

    def test_resume_fields_set_explicitly(self):
        """Verify resume fields can be set explicitly."""
        stats = ProcessingStats()
        result = ProcessRunResult(
            stats=stats,
            output_dir="/output",
            pef_dir="/output/_pef",
            summary_file="/output/_pef/summary.txt",
            elapsed_time=0,
            start_time="",
            end_time="",
            resumed=True,
            skipped_count=100,
            interrupted=True
        )
        assert result.resumed is True
        assert result.skipped_count == 100
        assert result.interrupted is True

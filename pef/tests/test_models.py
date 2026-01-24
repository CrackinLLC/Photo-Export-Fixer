"""Tests for pef.core.models module."""

from datetime import datetime

import pytest

from pef.core.models import (
    FileInfo,
    GeoData,
    Person,
    JsonMetadata,
    ProcessingStats,
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

    def test_from_dict_zero_coords(self):
        data = {"latitude": 0, "longitude": 0}
        assert GeoData.from_dict(data) is None

    def test_is_valid(self):
        geo = GeoData(40.7, -74.0)
        assert geo.is_valid() is True

        geo_zero = GeoData(0, 0)
        assert geo_zero.is_valid() is False


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
            albumname="Album"
        )
        assert fi.filename == "photo.jpg"
        assert fi.filepath == "/path/to/photo.jpg"
        assert fi.albumname == "Album"

    def test_optional_fields(self):
        fi = FileInfo(
            filename="photo.jpg",
            filepath="/path/to/photo.jpg",
            albumname="Album"
        )
        assert fi.procpath is None
        assert fi.jsonpath is None

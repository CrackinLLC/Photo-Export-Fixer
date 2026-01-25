"""Tests for pef.core.metadata module."""

import pytest

from pef.core.metadata import (
    build_gps_tags,
    build_gps_tags_from_dict,
    build_people_tags,
    build_people_tags_from_list,
    build_all_tags,
)
from pef.core.models import GeoData, Person


class TestBuildGpsTags:
    """Tests for build_gps_tags() function."""

    def test_none_returns_empty(self):
        assert build_gps_tags(None) == {}

    def test_zero_coords_are_valid(self):
        """(0,0) is a valid location (Gulf of Guinea) and should produce GPS tags."""
        geo = GeoData(0, 0)
        tags = build_gps_tags(geo)

        assert tags["GPSLatitude"] == 0
        assert tags["GPSLatitudeRef"] == "N"
        assert tags["GPSLongitude"] == 0
        assert tags["GPSLongitudeRef"] == "E"

    def test_positive_coords(self):
        geo = GeoData(40.7128, 74.0060, 10)
        tags = build_gps_tags(geo)

        assert tags["GPSLatitude"] == 40.7128
        assert tags["GPSLatitudeRef"] == "N"
        assert tags["GPSLongitude"] == 74.0060
        assert tags["GPSLongitudeRef"] == "E"
        assert tags["GPSAltitude"] == 10
        assert tags["GPSAltitudeRef"] == 0

    def test_negative_latitude(self):
        geo = GeoData(-33.8688, 151.2093)  # Sydney
        tags = build_gps_tags(geo)

        assert tags["GPSLatitude"] == 33.8688  # Absolute value
        assert tags["GPSLatitudeRef"] == "S"

    def test_negative_longitude(self):
        geo = GeoData(40.7128, -74.0060)  # NYC
        tags = build_gps_tags(geo)

        assert tags["GPSLongitude"] == 74.0060  # Absolute value
        assert tags["GPSLongitudeRef"] == "W"

    def test_negative_altitude(self):
        geo = GeoData(31.5, 35.5, -400)  # Dead Sea
        tags = build_gps_tags(geo)

        assert tags["GPSAltitude"] == 400  # Absolute value
        assert tags["GPSAltitudeRef"] == 1  # Below sea level

    def test_zero_altitude(self):
        geo = GeoData(40.7, -74.0, 0)
        tags = build_gps_tags(geo)

        assert tags["GPSAltitude"] == 0
        assert tags["GPSAltitudeRef"] == 0


class TestBuildGpsTagsFromDict:
    """Tests for build_gps_tags_from_dict() backwards-compat function."""

    def test_none_returns_empty(self):
        assert build_gps_tags_from_dict(None) == {}

    def test_valid_dict(self):
        geo_dict = {"latitude": 40.7128, "longitude": -74.0060, "altitude": 10}
        tags = build_gps_tags_from_dict(geo_dict)

        assert "GPSLatitude" in tags
        assert tags["GPSLatitude"] == 40.7128

    def test_zero_coords_are_valid(self):
        """(0,0) is a valid location and should produce GPS tags."""
        geo_dict = {"latitude": 0, "longitude": 0}
        tags = build_gps_tags_from_dict(geo_dict)

        assert tags["GPSLatitude"] == 0
        assert tags["GPSLatitudeRef"] == "N"
        assert tags["GPSLongitude"] == 0
        assert tags["GPSLongitudeRef"] == "E"


class TestBuildPeopleTags:
    """Tests for build_people_tags() function."""

    def test_empty_list_returns_empty(self):
        assert build_people_tags([]) == {}

    def test_single_person(self):
        people = [Person("Alice")]
        tags = build_people_tags(people)

        assert tags["PersonInImage"] == ["Alice"]
        assert tags["Keywords"] == ["Alice"]
        assert tags["Subject"] == ["Alice"]
        assert tags["XPKeywords"] == "Alice"

    def test_multiple_people(self):
        people = [Person("Alice"), Person("Bob"), Person("Charlie")]
        tags = build_people_tags(people)

        assert tags["PersonInImage"] == ["Alice", "Bob", "Charlie"]
        assert tags["Keywords"] == ["Alice", "Bob", "Charlie"]
        assert tags["XPKeywords"] == "Alice;Bob;Charlie"

    def test_special_characters_in_name(self):
        people = [Person("O'Brien"), Person("Jean-Pierre")]
        tags = build_people_tags(people)

        assert "O'Brien" in tags["PersonInImage"]
        assert "Jean-Pierre" in tags["PersonInImage"]

    def test_unicode_names(self):
        people = [Person("日本語"), Person("Müller")]
        tags = build_people_tags(people)

        assert "日本語" in tags["PersonInImage"]
        assert "Müller" in tags["PersonInImage"]


class TestBuildPeopleTagsFromList:
    """Tests for build_people_tags_from_list() backwards-compat function."""

    def test_none_returns_empty(self):
        assert build_people_tags_from_list(None) == {}

    def test_empty_list_returns_empty(self):
        assert build_people_tags_from_list([]) == {}

    def test_valid_list(self):
        people_list = [{"name": "Alice"}, {"name": "Bob"}]
        tags = build_people_tags_from_list(people_list)

        assert tags["PersonInImage"] == ["Alice", "Bob"]

    def test_filters_invalid_entries(self):
        people_list = [{"name": "Alice"}, {"other": "data"}, {"name": "Bob"}]
        tags = build_people_tags_from_list(people_list)

        assert tags["PersonInImage"] == ["Alice", "Bob"]


class TestBuildAllTags:
    """Tests for build_all_tags() function."""

    def test_empty_returns_empty(self):
        assert build_all_tags() == {}

    def test_gps_only(self):
        geo = GeoData(40.7, -74.0)
        tags = build_all_tags(geo_data=geo)

        assert "GPSLatitude" in tags
        assert "PersonInImage" not in tags
        assert "ImageDescription" not in tags

    def test_people_only(self):
        people = [Person("Alice")]
        tags = build_all_tags(people=people)

        assert "PersonInImage" in tags
        assert "GPSLatitude" not in tags

    def test_description_only(self):
        tags = build_all_tags(description="Test caption")

        assert tags["ImageDescription"] == "Test caption"
        assert tags["Caption-Abstract"] == "Test caption"
        assert tags["Description"] == "Test caption"

    def test_all_fields(self):
        geo = GeoData(40.7, -74.0)
        people = [Person("Alice")]
        tags = build_all_tags(
            geo_data=geo,
            people=people,
            description="Photo of Alice"
        )

        assert "GPSLatitude" in tags
        assert "PersonInImage" in tags
        assert tags["ImageDescription"] == "Photo of Alice"

    def test_empty_description_not_included(self):
        geo = GeoData(40.7, -74.0)
        tags = build_all_tags(geo_data=geo, description="")

        assert "ImageDescription" not in tags

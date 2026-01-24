"""EXIF metadata tag builders for Photo Export Fixer.

Converts Google Photos JSON metadata into ExifTool-compatible tag dictionaries.
"""

from typing import Dict, List, Optional, Any

from pef.core.models import GeoData, Person


def build_gps_tags(geo_data: Optional[GeoData]) -> Dict[str, Any]:
    """Convert GPS coordinates to ExifTool tag dictionary.

    Args:
        geo_data: GeoData object with lat/lon/alt, or None.

    Returns:
        Dict of ExifTool tags, empty if geo_data is None/invalid.

    Example:
        >>> build_gps_tags(GeoData(40.7128, -74.0060, 10))
        {
            'GPSLatitude': 40.7128,
            'GPSLatitudeRef': 'N',
            'GPSLongitude': 74.0060,
            'GPSLongitudeRef': 'W',
            'GPSAltitude': 10,
            'GPSAltitudeRef': 0,
        }
    """
    if not geo_data or not geo_data.is_valid():
        return {}

    return {
        "GPSLatitude": abs(geo_data.latitude),
        "GPSLatitudeRef": "N" if geo_data.latitude >= 0 else "S",
        "GPSLongitude": abs(geo_data.longitude),
        "GPSLongitudeRef": "E" if geo_data.longitude >= 0 else "W",
        "GPSAltitude": abs(geo_data.altitude),
        "GPSAltitudeRef": 0 if geo_data.altitude >= 0 else 1,
    }


def build_gps_tags_from_dict(geo_dict: Optional[Dict]) -> Dict[str, Any]:
    """Convert Google's geoData dict to ExifTool tags (backwards compatible).

    Args:
        geo_dict: Google's geoData dict with latitude/longitude/altitude keys.

    Returns:
        Dict of ExifTool tags.
    """
    geo_data = GeoData.from_dict(geo_dict)
    return build_gps_tags(geo_data)


def build_people_tags(people: List[Person]) -> Dict[str, Any]:
    """Convert people list to ExifTool tag dictionary.

    Writes to multiple tag locations for maximum compatibility:
    - PersonInImage: XMP-iptcExt standard
    - Keywords: IPTC keywords
    - Subject: XMP-dc subject
    - XPKeywords: Windows Explorer

    Args:
        people: List of Person objects.

    Returns:
        Dict of ExifTool tags, empty if no people.

    Example:
        >>> build_people_tags([Person("Alice"), Person("Bob")])
        {
            'PersonInImage': ['Alice', 'Bob'],
            'Keywords': ['Alice', 'Bob'],
            'Subject': ['Alice', 'Bob'],
            'XPKeywords': 'Alice;Bob',
        }
    """
    if not people:
        return {}

    names = [p.name for p in people]

    return {
        "PersonInImage": names,           # XMP-iptcExt (list for multiple)
        "Keywords": names,                # IPTC keywords
        "Subject": names,                 # XMP-dc subject
        "XPKeywords": ";".join(names),   # Windows (semicolon-separated)
    }


def build_people_tags_from_list(people_list: Optional[List[Dict]]) -> Dict[str, Any]:
    """Convert Google's people array to ExifTool tags (backwards compatible).

    Args:
        people_list: Google's people array with name dicts.

    Returns:
        Dict of ExifTool tags.
    """
    people = Person.from_list(people_list)
    return build_people_tags(people)


def build_all_tags(
    geo_data: Optional[GeoData] = None,
    people: Optional[List[Person]] = None,
    description: str = ""
) -> Dict[str, Any]:
    """Build complete ExifTool tag dictionary from all metadata.

    Args:
        geo_data: Optional GPS coordinates.
        people: Optional list of people.
        description: Optional description/caption.

    Returns:
        Combined dict of all tags.
    """
    tags = {}
    tags.update(build_gps_tags(geo_data))
    tags.update(build_people_tags(people or []))

    if description:
        tags["ImageDescription"] = description
        tags["Caption-Abstract"] = description  # IPTC
        tags["Description"] = description       # XMP-dc

    return tags

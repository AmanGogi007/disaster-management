"""Coordinate validation and geographic helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass


EARTH_RADIUS_M = 6_371_008.8


def validate_latitude(lat: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"latitude out of range: {lat}")


def validate_longitude(lon: float) -> None:
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"longitude out of range: {lon}")


def validate_coordinates(lat: float, lon: float) -> None:
    validate_latitude(lat)
    validate_longitude(lon)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bbox_from_point(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) bbox around a point.

    Uses a flat-earth approximation that is accurate enough for radii
    up to ~500 km.  Good enough for V0.1 query construction.
    """
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")
    dlat = radius_km / 111.32
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = radius_km / (111.32 * cos_lat)
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        validate_coordinates(self.lat, self.lon)

    def to_dict(self) -> dict:
        return {"lat": self.lat, "lon": self.lon}
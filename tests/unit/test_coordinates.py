"""Coordinate validation and great-circle distance."""
import math

from geo.coordinates import (
    bbox_from_point, haversine_m, validate_coordinates, validate_latitude, validate_longitude,
)


def test_validate_latitude():
    validate_latitude(0)
    validate_latitude(90)
    validate_latitude(-90)
    try:
        validate_latitude(91)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_validate_longitude():
    validate_longitude(0)
    validate_longitude(180)
    validate_longitude(-180)
    try:
        validate_longitude(181)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_validate_coordinates():
    validate_coordinates(30.0, 75.0)
    try:
        validate_coordinates(100, 0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_haversine_zero():
    assert haversine_m(30.0, 75.0, 30.0, 75.0) == 0.0


def test_haversine_known():
    # London (51.5074, -0.1278) ↔ Paris (48.8566, 2.3522) ≈ 343 km
    d = haversine_m(51.5074, -0.1278, 48.8566, 2.3522)
    assert 340_000 < d < 350_000


def test_bbox_symmetric():
    s, w, n, e = bbox_from_point(0.0, 0.0, 100)
    assert s < 0 < n
    assert w < 0 < e


def test_bbox_rejects_zero():
    try:
        bbox_from_point(0, 0, 0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
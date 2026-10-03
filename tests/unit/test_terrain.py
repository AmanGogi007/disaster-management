"""Synthetic-DEM terrain tests using the spec's downhill-slope fixture."""
import numpy as np

from geo.raster.dem import AffineTransform, DEM
from geo.terrain.analysis import summarize, aspect_to_cardinal
from geo.watershed.flow import (
    d8_flow_direction, flow_accumulation, path_distance_km, trace_downhill,
    drainage_direction_cardinal,
)


def make_slope_dem() -> DEM:
    rows = [
        [100, 100, 100, 100, 100],
        [90, 90, 90, 90, 100],
        [80, 80, 80, 80, 100],
        [70, 70, 70, 70, 100],
        [60, 60, 60, 60, 100],
    ]
    elev = np.asarray(rows, dtype=float)
    t = AffineTransform(
        origin_lon=0.0,
        origin_lat=5 * 0.01,
        pixel_size_lon=0.01,
        pixel_size_lat=0.01,
    )
    return DEM(elevation=elev, transform=t, nodata=None)


def test_point_elevation_matches_grid():
    dem = make_slope_dem()
    # origin_lon=0, origin_lat=0.05, pix=0.01 → top-left cell centre at (0.005, 0.045).
    assert dem.value_at(0.045, 0.005) == 100.0
    # Bottom-left cell centre at (0.005, 0.005).
    assert dem.value_at(0.005, 0.005) == 60.0
    # Middle cell on the slope.
    assert dem.value_at(0.025, 0.005) == 80.0


def test_slope_and_aspect_on_synthetic_dem():
    dem = make_slope_dem()
    # Interior point on the slope: row 2, col 1 → lat=0.025, lon=0.015.
    s = summarize(dem, lat=0.025, lon=0.015)
    assert s.point_elevation_m is not None
    assert s.slope_deg is not None
    assert s.slope_deg > 0.05
    # Aspect of pure south-facing slope ≈ 180°
    assert s.aspect_deg is not None
    assert 150 < s.aspect_deg < 210
    assert s.relief_m == 40.0


def test_aspect_to_cardinal():
    assert aspect_to_cardinal(0) == "N"
    assert aspect_to_cardinal(90) == "E"
    assert aspect_to_cardinal(180) == "S"
    assert aspect_to_cardinal(270) == "W"
    assert aspect_to_cardinal(45) == "NE"
    assert aspect_to_cardinal(None) is None


def test_d8_flow_direction_moves_downhill():
    dem = make_slope_dem()
    fdir = d8_flow_direction(dem)
    # Top-left cell (0,0) should drain roughly south (D8 code 7).
    # Accept SW(8) or S(7) for the top row.
    assert int(fdir[0, 0]) in (7, 8)


def test_flow_accumulation_increases_downhill():
    dem = make_slope_dem()
    fdir = d8_flow_direction(dem)
    acc = flow_accumulation(fdir)
    # Bottom row should accumulate at least as much as top row.
    assert acc[-1, :].sum() > acc[0, :].sum()


def test_trace_downhill_distance_positive():
    dem = make_slope_dem()
    fdir = d8_flow_direction(dem)
    path = trace_downhill(dem, fdir, lat=0.005 * 4, lon=0.005)
    assert len(path) >= 2
    assert path_distance_km(path) > 0


def test_drainage_direction_cardinal_south():
    # Path that moves from north to south.
    pts = [(10.0, 5.0), (9.9, 5.0), (9.8, 5.0)]
    assert drainage_direction_cardinal(pts) == "S"
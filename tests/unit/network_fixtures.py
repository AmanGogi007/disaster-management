"""Synthetic fixtures for V0.2 hydrological network tests.

Each fixture is a small DEM plus a set of OSM WaterFeature objects built
around it.  Layouts are deliberately hand-drawn so individual tests can
reason about the expected graph topology.
"""
from __future__ import annotations

import numpy as np

from packages.geo.hydrology.features import FeatureType, WaterFeature
from packages.geo.raster.dem import AffineTransform, DEM


# ---------------------------------------------------------------------------
# A toy DEM: a single ridge running west → east; elevation drops as you move
# south.  Width = 20 cells (1 km), height = 20 cells (1 km), pixel = 50 m.
# ---------------------------------------------------------------------------
def make_toy_dem() -> DEM:
    rows = 20
    cols = 20
    pix = 0.0005  # ~50 m
    elev = np.zeros((rows, cols), dtype=float)
    for r in range(rows):
        for c in range(cols):
            # North (row 0) = 100 m, South (row 19) = 10 m.  +5 m ridge column at col 10.
            elev[r, c] = 100.0 - 5.0 * r + (5.0 if c == 10 else 0.0)
    t = AffineTransform(
        origin_lon=-0.005,
        origin_lat=rows * pix,
        pixel_size_lon=pix,
        pixel_size_lat=pix,
    )
    return DEM(elevation=elev, transform=t, nodata=None)


# Origin lat = 20*0.0005 = 0.01, lon = -0.005.
# Pixel size = 0.0005°.
# Cell centres:
#   row 0  → lat 0.01 - 0.5*0.0005 = 0.00975
#   row 19 → lat 0.01 - 19.5*0.0005 = 0.00025
#   col 0  → lon -0.005 + 0.5*0.0005 = -0.00475
#   col 19 → lon -0.005 + 19.5*0.0005 = 0.00475


def _feature(fid: str, name: str | None, ftype: FeatureType,
             row: int, col: int, geom_rows_cols: list[tuple[int, int]] | None = None) -> WaterFeature:
    """Create a feature positioned at a specific DEM cell."""
    t = make_toy_dem().transform
    lat = t.lat_at_row(row)
    lon = t.lon_at_col(col)
    tags: dict = {}
    if geom_rows_cols:
        pts = [(t.lat_at_row(r), t.lon_at_col(c)) for r, c in geom_rows_cols]
        tags["__geometry__"] = pts
    return WaterFeature(
        osm_id=fid,
        name=name,
        type=ftype,
        latitude=lat, longitude=lon,
        distance_km=0.0,
        geometry_kind="way" if geom_rows_cols else "node",
        tags=tags,
    )


def upstream_dam_fixture():
    """Plot sits on a river; dam is upstream of the plot."""
    return {
        "features": [
            # Main river flowing south, with the dam on its upper segment.
            _feature("r1", "River A", FeatureType.RIVER, row=5, col=10,
                     geom_rows_cols=[(0, 10), (19, 10)]),
            # Dam at row=2 (upstream of plot).
            _feature("d1", "Dam U", FeatureType.DAM, row=2, col=10),
            # Downstream dam, past the plot attachment.
            _feature("d2", "Dam D", FeatureType.DAM, row=15, col=10),
        ],
        # Plot is on the river at row=5 (between Dam U at row=2 and Dam D at row=15).
        "plot": (5, 10),
    }


def disconnected_dam_fixture():
    """Plot is on a river; a dam exists nearby but on a different drainage line."""
    return {
        "features": [
            _feature("r1", "River A", FeatureType.RIVER, row=5, col=10,
                     geom_rows_cols=[(0, 10), (19, 10)]),
            # Disconnected dam on a parallel ridge that doesn't share nodes.
            _feature("d1", "Lone Dam", FeatureType.DAM, row=5, col=5),
        ],
        "plot": (5, 10),
    }


def tributary_fixture():
    """Two rivers meet.  Plot sits on the main one upstream of the confluence."""
    return {
        "features": [
            # Main river south-flowing.
            _feature("r1", "Main", FeatureType.RIVER, row=5, col=10,
                     geom_rows_cols=[(0, 10), (19, 10)]),
            # Tributary flowing west, joining the main river around row=12.
            _feature("t1", "Trib", FeatureType.STREAM, row=12, col=10,
                     geom_rows_cols=[(12, 5), (12, 10)]),
            # A reservoir on the tributary.
            _feature("res", "Trib Reservoir", FeatureType.RESERVOIR, row=12, col=7),
        ],
        "plot": (5, 10),  # upstream of confluence → tributary is DOWNSTREAM
    }


def multiple_upstream_dams_fixture():
    """Two rivers converge above the plot → both upstream."""
    return {
        "features": [
            # Two branches converge at (8, 10).
            _feature("r1", "West Branch", FeatureType.RIVER, row=8, col=10,
                     geom_rows_cols=[(8, 5), (8, 10)]),
            _feature("r2", "East Branch", FeatureType.RIVER, row=8, col=10,
                     geom_rows_cols=[(8, 15), (8, 10)]),
            # Continues south past the plot.
            _feature("r3", "Main", FeatureType.RIVER, row=8, col=10,
                     geom_rows_cols=[(8, 10), (19, 10)]),
            _feature("d1", "Dam W", FeatureType.DAM, row=8, col=6),
            _feature("d2", "Dam E", FeatureType.DAM, row=8, col=14),
        ],
        "plot": (15, 10),
    }


def plot_not_attached_fixture():
    """Plot sits on a hilltop, DEM downhill trace never reaches a river."""
    return {
        "features": [
            _feature("r1", "River A", FeatureType.RIVER, row=15, col=10,
                     geom_rows_cols=[(15, 5), (15, 15)]),
            _feature("d1", "Some Dam", FeatureType.DAM, row=15, col=10),
        ],
        # Plot at row=0 col=0 — uphill, no river in downhill path within grid.
        "plot": (0, 0),
    }
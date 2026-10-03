"""DEM synthesis for the bundled Punjab sample.

Builds a smooth synthetic surface representing the general topography
around the Sutlej basin.  This is **NOT** real survey-grade data — it
is explicitly labelled as such so the V0.1 demo can run end-to-end
without external downloads.  Real providers slot in via
``packages/geo/terrain/provider.py``.
"""
from __future__ import annotations

import numpy as np

from ..raster.dem import AffineTransform, DEM


def make_sample_dem_punjab(
    center_lat: float = 30.7,
    center_lon: float = 76.0,
    size_px: int = 200,
    pixel_deg: float = 0.005,  # ~500 m
) -> DEM:
    """A smooth synthetic landscape around central Punjab.

    - Higher elevation towards the north-east (Shivaliks).
    - Lower elevation towards the south-west (plains, Sutlej corridor).
    - Mild random relief on top.
    """
    rows = np.arange(size_px).reshape(-1, 1)
    cols = np.arange(size_px).reshape(1, -1)
    r_norm = rows / (size_px - 1)  # 0..1, north -> south
    c_norm = cols / (size_px - 1)  # 0..1, west  -> east
    surface = (
        300.0 * (1.0 - r_norm)        # north higher
        + 80.0 * c_norm                # east slightly higher
        + 30.0 * np.sin(r_norm * np.pi * 2)
        + 20.0 * np.cos(c_norm * np.pi * 3)
    )
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, 2.0, size=surface.shape)
    elev = surface + noise

    transform = AffineTransform(
        origin_lon=center_lon - (size_px / 2) * pixel_deg,
        origin_lat=center_lat + (size_px / 2) * pixel_deg,
        pixel_size_lon=pixel_deg,
        pixel_size_lat=pixel_deg,
    )
    return DEM(elevation=elev, transform=transform, crs="EPSG:4326", nodata=-9999.0)
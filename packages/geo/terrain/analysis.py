"""Terrain analysis: elevation sampling, slope, aspect, relief."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..raster.dem import DEM


@dataclass
class TerrainSummary:
    point_elevation_m: float | None
    min_m: float | None
    max_m: float | None
    mean_m: float | None
    relief_m: float | None
    slope_deg: float | None
    aspect_deg: float | None  # 0=N, 90=E, 180=S, 270=W
    pixel_size_m: float

    def to_dict(self) -> dict:
        return {
            "point_elevation_m": _round_or_none(self.point_elevation_m),
            "min_m": _round_or_none(self.min_m),
            "max_m": _round_or_none(self.max_m),
            "mean_m": _round_or_none(self.mean_m),
            "relief_m": _round_or_none(self.relief_m),
            "slope_deg": _round_or_none(self.slope_deg, 2),
            "aspect_deg": _round_or_none(self.aspect_deg, 1),
            "pixel_size_m": _round_or_none(self.pixel_size_m, 1),
        }


def _round_or_none(v, ndigits: int = 2):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return round(float(v), ndigits)


def _valid_mask(dem: DEM) -> np.ndarray:
    if dem.nodata is None:
        return np.ones(dem.elevation.shape, dtype=bool)
    return dem.elevation != dem.nodata


def summarize(dem: DEM, lat: float, lon: float) -> TerrainSummary:
    """Compute point elevation, slope, aspect, and relief for a DEM."""
    elev = dem.elevation
    mask = _valid_mask(dem)
    valid_vals = elev[mask]

    if valid_vals.size == 0:
        return TerrainSummary(
            point_elevation_m=None, min_m=None, max_m=None, mean_m=None,
            relief_m=None, slope_deg=None, aspect_deg=None, pixel_size_m=_pixel_m(dem),
        )

    min_v = float(valid_vals.min())
    max_v = float(valid_vals.max())
    mean_v = float(valid_vals.mean())
    relief = max_v - min_v

    point_elev = dem.value_at(lat, lon)
    slope, aspect = _local_slope_aspect(dem, lat, lon)

    return TerrainSummary(
        point_elevation_m=point_elev,
        min_m=min_v,
        max_m=max_v,
        mean_m=mean_v,
        relief_m=relief,
        slope_deg=slope,
        aspect_deg=aspect,
        pixel_size_m=_pixel_m(dem),
    )


def _pixel_m(dem: DEM) -> float:
    t = dem.transform
    center_lat = (t.origin_lat - (dem.rows / 2) * t.pixel_size_lat)
    return float(t.pixel_size_lon * 111_320.0 * max(0.1, math.cos(math.radians(center_lat))))


def _local_slope_aspect(dem: DEM, lat: float, lon: float) -> tuple[float | None, float | None]:
    """Estimate slope/aspect at a point using a 3x3 Horn kernel."""
    t = dem.transform
    col = t.col_at_lon(lon)
    row = t.row_at_lat(lat)
    if col <= 0 or col >= dem.cols - 1 or row <= 0 or row >= dem.rows - 1:
        return None, None
    a = dem.elevation[row - 1, col - 1]
    b = dem.elevation[row - 1, col]
    c = dem.elevation[row - 1, col + 1]
    d = dem.elevation[row, col - 1]
    f = dem.elevation[row, col + 1]
    g = dem.elevation[row + 1, col - 1]
    h = dem.elevation[row + 1, col]
    i = dem.elevation[row + 1, col + 1]

    pix_m = _pixel_m(dem)
    if pix_m <= 0:
        return None, None
    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pix_m)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * pix_m)

    rise = math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy)
    slope_deg = math.degrees(math.atan(rise))

    if dz_dx == 0 and dz_dy == 0:
        aspect_deg = None
    else:
        # dz_dy is measured along the southward axis (row index ↑ = south ↓),
        # so +dz_dy points south.  dz_dx points east.  Aspect is the compass
        # bearing the slope faces, i.e. the downslope direction: north
        # component = dz_dy, east component = -dz_dx.  Negating dz_dx is what
        # puts E and W on the correct sides; without it the aspect is mirrored
        # about the north-south axis (E reports as W).
        aspect_rad = math.atan2(-dz_dx, dz_dy)
        aspect_deg = (math.degrees(aspect_rad) + 360.0) % 360.0
    return slope_deg, aspect_deg


def aspect_to_cardinal(deg: float | None) -> str | None:
    if deg is None:
        return None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg + 22.5) // 45) % 8
    return dirs[idx]
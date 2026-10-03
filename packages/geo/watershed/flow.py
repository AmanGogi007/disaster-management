"""Watershed / flow direction analysis (D8)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..raster.dem import DEM
from ..coordinates import haversine_m


D8_OFFSETS = [
    (-1, -1, math.sqrt(2)),
    (-1, 0, 1.0),
    (-1, 1, math.sqrt(2)),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (1, -1, math.sqrt(2)),
    (1, 0, 1.0),
    (1, 1, math.sqrt(2)),
]


@dataclass
class FlowResult:
    flow_direction: np.ndarray  # int8 D8 codes (1..8) or 0 for flat/outlet
    flow_accumulation: np.ndarray  # cell counts
    drainage_to: tuple[int, int] | None  # cell that drains the plot point

    def to_dict(self) -> dict:
        return {
            "drainage_to_cell": list(self.drainage_to) if self.drainage_to else None,
        }


def d8_flow_direction(dem: DEM) -> np.ndarray:
    rows, cols = dem.elevation.shape
    out = np.zeros((rows, cols), dtype=np.int8)
    elev = dem.elevation
    pix_m = _pixel_m(dem)
    for r in range(rows):
        for c in range(cols):
            best_drop = 0.0
            best_dir = 0
            z = elev[r, c]
            for idx, (dr, dc, diag) in enumerate(D8_OFFSETS, start=1):
                nr, nc = r + dr, c + dc
                if nr < 0 or nc < 0 or nr >= rows or nc >= cols:
                    continue
                # Slope = drop / distance (so diagonals compete fairly with
                # orthogonal neighbours).
                slope = (z - elev[nr, nc]) / (diag * pix_m)
                if slope > best_drop:
                    best_drop = slope
                    best_dir = idx
            out[r, c] = best_dir
    return out


def flow_accumulation(fdir: np.ndarray) -> np.ndarray:
    rows, cols = fdir.shape
    acc = np.ones_like(fdir, dtype=np.int32)
    # Process cells by descending elevation proxy: iterate in raster order,
    # which is correct when fdir points downhill (rows ~ flow distance).
    for r in range(rows):
        for c in range(cols):
            d = int(fdir[r, c])
            if d == 0:
                continue
            dr, dc, _ = D8_OFFSETS[d - 1]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                acc[nr, nc] += acc[r, c]
    return acc


def trace_downhill(dem: DEM, fdir: np.ndarray, lat: float, lon: float, max_steps: int = 5000) -> list[tuple[float, float]]:
    t = dem.transform
    col = t.col_at_lon(lon)
    row = t.row_at_lat(lat)
    if row < 0 or row >= dem.rows or col < 0 or col >= dem.cols:
        return []
    path: list[tuple[float, float]] = []
    seen: set[tuple[int, int]] = set()
    r, c = row, col
    for _ in range(max_steps):
        if (r, c) in seen:
            break
        seen.add((r, c))
        path.append((t.lat_at_row(r), t.lon_at_col(c)))
        d = int(fdir[r, c])
        if d == 0:
            break
        dr, dc, _ = D8_OFFSETS[d - 1]
        nr, nc = r + dr, c + dc
        if nr < 0 or nc < 0 or nr >= dem.rows or nc >= dem.cols:
            break
        r, c = nr, nc
    return path


def _pixel_m(dem: DEM) -> float:
    t = dem.transform
    center_lat = (t.origin_lat - (dem.rows / 2) * t.pixel_size_lat)
    return float(t.pixel_size_lon * 111_320.0 * max(0.1, math.cos(math.radians(center_lat))))


def path_distance_km(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        total += haversine_m(lat1, lon1, lat2, lon2)
    return total / 1000.0


def drainage_direction_cardinal(flow_path: list[tuple[float, float]]) -> str | None:
    if len(flow_path) < 2:
        return None
    lat1, lon1 = flow_path[0]
    lat2, lon2 = flow_path[-1]
    if abs(lat2 - lat1) < 1e-6 and abs(lon2 - lon1) < 1e-6:
        return None
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    if abs(dlat) >= abs(dlon):
        return "S" if dlat < 0 else "N"
    return "E" if dlon > 0 else "W"
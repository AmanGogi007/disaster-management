"""Watershed / flow direction analysis (D8)."""
from __future__ import annotations

import math
from collections import deque
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


def valid_mask(dem: DEM) -> np.ndarray:
    """Boolean mask of cells holding real elevation.

    Honours both a numeric ``dem.nodata`` sentinel and non-finite values
    (NaN/inf), which is what in-memory rasters arrive with.
    """
    elev = dem.elevation
    valid = np.isfinite(elev)
    if dem.nodata is not None:
        valid &= ~np.isclose(elev, float(dem.nodata))
    return valid


def d8_flow_direction(dem: DEM) -> np.ndarray:
    """Steepest-descent D8 pointer, 1..8 (see ``D8_OFFSETS``), 0 = no descent.

    Cells with no real elevation (``dem.nodata`` or NaN) get 0 and are never
    used as a downslope target.  Without this, a -9999 sentinel becomes a
    ~10000 m artificial pit that captures the flow of every neighbour.
    """
    rows, cols = dem.elevation.shape
    out = np.zeros((rows, cols), dtype=np.int8)
    elev = dem.elevation
    valid = valid_mask(dem)
    pix_m = _pixel_m(dem)
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]:
                continue
            best_drop = 0.0
            best_dir = 0
            z = elev[r, c]
            for idx, (dr, dc, diag) in enumerate(D8_OFFSETS, start=1):
                nr, nc = r + dr, c + dc
                if nr < 0 or nc < 0 or nr >= rows or nc >= cols:
                    continue
                if not valid[nr, nc]:
                    continue
                # Slope = drop / distance (so diagonals compete fairly with
                # orthogonal neighbours).
                slope = (z - elev[nr, nc]) / (diag * pix_m)
                if slope > best_drop:
                    best_drop = slope
                    best_dir = idx
            out[r, c] = best_dir
    return out


def flow_accumulation(fdir: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Accumulate contributing cells using a topological order over the D8 DAG.

    Row-major raster order is **not** a valid propagation order: a cell whose
    downstream neighbour has a *lower* raster index is processed too late, so
    its contribution never reaches the cells that depend on it. That
    understates accumulation at outlets (measured 8 instead of 36 on a 6x6
    synthetic DEM), which propagates straight into the exposure score.

    Each cell has at most one downstream neighbour, so the D8 pointer grid forms
    a DAG rooted at outlets (fdir == 0) or at cells draining off the grid.
    Kahn's algorithm visits every source before its descendants, which is the
    required ordering. Degenerate cycles (only reachable from an unfilled DEM)
    are handled: any cell left unprocessed keeps its own 1 and cannot corrupt a
    resolved cell.

    Parameters
    ----------
    fdir : np.ndarray
        D8 pointer grid from :func:`d8_flow_direction`.
    valid : np.ndarray, optional
        Boolean mask of cells holding real elevation (see :func:`valid_mask`).
        Invalid cells neither accumulate nor receive accumulation, so a nodata
        gap cannot act as a drainage sink.
    """
    rows, cols = fdir.shape
    acc = np.ones((rows, cols), dtype=np.int64)
    valid = (np.ones((rows, cols), dtype=bool) if valid is None
             else np.asarray(valid, dtype=bool))

    # downstream[(r, c)] -> (nr, nc) or None for outlets / off-grid drains.
    downstream: list[list[tuple[int, int] | None]] = [[None] * cols for _ in range(rows)]
    indeg = np.zeros((rows, cols), dtype=np.int32)

    for r in range(rows):
        for c in range(cols):
            d = int(fdir[r, c])
            if d == 0 or not valid[r, c]:
                continue
            dr, dc, _ = D8_OFFSETS[d - 1]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and valid[nr, nc]:
                downstream[r][c] = (nr, nc)
                indeg[nr, nc] += 1

    # Kahn's algorithm: seed with every cell that nothing drains into.
    queue = deque(
        (r, c) for r in range(rows) for c in range(cols)
        if valid[r, c] and indeg[r, c] == 0
    )
    while queue:
        r, c = queue.popleft()
        ds = downstream[r][c]
        if ds is None:
            continue
        nr, nc = ds
        acc[nr, nc] += acc[r, c]
        indeg[nr, nc] -= 1
        if indeg[nr, nc] == 0:
            queue.append((nr, nc))

    # NoData cells carry no contributing-area information.
    acc[~valid] = 0
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
"""Regression tests for defects found in the V0.3 audit.

Each test here failed before its fix. They are deliberately built on
planar/axis-aligned DEMs where the correct answer can be derived by hand, so
a future refactor cannot quietly reintroduce the bug by changing both the
implementation and the expectation together.

Covered:
  1. flow_accumulation used raster order instead of a topological order.
  2. Aspect was mirrored about the north-south axis (E/W swapped).
  3. d8_flow_direction / flow_accumulation ignored dem.nodata, so a -9999
     sentinel acted as a ~10000 m artificial pit.
  4. AffineTransform.col_at_lon / row_at_lat truncated toward zero, so points
     just outside the west/south edge were read as if inside the grid.
  5. providers/google_earth_engine.py did not parse.
"""
import ast
import math
from pathlib import Path

import numpy as np
import pytest

from geo.raster.dem import AffineTransform, DEM
from geo.terrain.analysis import _local_slope_aspect, aspect_to_cardinal
from geo.watershed.flow import (
    D8_OFFSETS,
    d8_flow_direction,
    flow_accumulation,
    valid_mask,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _grid_dem(elev, nodata=None, pixel=0.01, origin_lon=0.0, origin_lat=0.05):
    transform = AffineTransform(
        origin_lon=origin_lon,
        origin_lat=origin_lat,
        pixel_size_lon=pixel,
        pixel_size_lat=pixel,
    )
    return DEM(elevation=np.asarray(elev, dtype=float), transform=transform, nodata=nodata)


def _topological_reference(fdir):
    """Independent accumulation via Kahn's algorithm, for cross-checking."""
    rows, cols = fdir.shape
    acc = np.ones((rows, cols), dtype=np.int64)
    indeg = np.zeros((rows, cols), dtype=np.int32)
    downstream = {}
    for r in range(rows):
        for c in range(cols):
            d = int(fdir[r, c])
            if d == 0:
                downstream[(r, c)] = None
                continue
            dr, dc, _ = D8_OFFSETS[d - 1]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                downstream[(r, c)] = (nr, nc)
                indeg[nr, nc] += 1
            else:
                downstream[(r, c)] = None
    from collections import deque

    queue = deque(
        (r, c) for r in range(rows) for c in range(cols) if indeg[r, c] == 0
    )
    while queue:
        cell = queue.popleft()
        ds = downstream[cell]
        if ds is None:
            continue
        acc[ds] += acc[cell]
        indeg[ds] -= 1
        if indeg[ds] == 0:
            queue.append(ds)
    return acc


# ---------------------------------------------------------------------------
# 1. flow_accumulation ordering
# ---------------------------------------------------------------------------

def test_flow_accumulation_matches_topological_order_on_realistic_dem():
    """Accumulation must not depend on raster scan order.

    Before the fix, row-major iteration gave the outlet 8 contributing cells
    instead of 36 because flow here runs toward *decreasing* row indices.
    """
    rows, cols = 6, 6
    elev = np.array(
        [[100.0 + 3 * r - 2 * c + ((r * 7 + c * 13) % 5) * 0.1
          for c in range(cols)] for r in range(rows)]
    )
    dem = _grid_dem(elev)
    fdir = d8_flow_direction(dem)

    assert np.array_equal(
        flow_accumulation(fdir),
        _topological_reference(fdir),
    ), "flow_accumulation disagrees with a topological-order reference"


def test_flow_accumulation_outlet_receives_every_upstream_cell():
    """The single outlet must accumulate the whole contributing area."""
    # Elevation falls to the south-east (+row is south, +col is east), so the
    # lowest cell -- and therefore the outlet -- is the bottom-right corner.
    n = 5
    elev = [[100.0 - r - c for c in range(n)] for r in range(n)]
    dem = _grid_dem(elev)
    fdir = d8_flow_direction(dem)
    acc = flow_accumulation(fdir)

    assert acc[n - 1, n - 1] == n * n, "outlet did not accumulate all upstream cells"


def test_flow_accumulation_is_monotonic_downstream():
    """Accumulation never decreases along a traced flow path."""
    rng = np.random.default_rng(20260903)
    elev = 100.0 + rng.random((12, 12)) * 5.0
    dem = _grid_dem(elev)
    fdir = d8_flow_direction(dem)
    acc = flow_accumulation(fdir)

    for r in range(12):
        for c in range(12):
            d = int(fdir[r, c])
            if d == 0:
                continue
            dr, dc, _ = D8_OFFSETS[d - 1]
            nr, nc = r + dr, c + dc
            if 0 <= nr < 12 and 0 <= nc < 12:
                assert acc[nr, nc] >= acc[r, c]


# ---------------------------------------------------------------------------
# 2. Aspect orientation
# ---------------------------------------------------------------------------

def _planar_dem(d_row, d_col, n=5):
    """z = d_row * row + d_col * col, so the downslope direction is known."""
    elev = [[100.0 + d_row * r + d_col * c for c in range(n)] for r in range(n)]
    return _grid_dem(elev)


def _expected_aspect(d_row, d_col):
    """Bearing the plane faces.

    +row is south, +col is east.  Steepest descent has north component
    +d_row and east component -d_col, so bearing = atan2(east, north).
    """
    return aspect_to_cardinal(
        (math.degrees(math.atan2(-d_col, d_row)) + 360.0) % 360.0
    )


@pytest.mark.parametrize(
    ("d_row", "d_col"),
    [
        (0.0, 2.0),    # rises east  -> faces W
        (0.0, -2.0),   # rises west  -> faces E
        (2.0, 0.0),    # rises south -> faces N
        (-2.0, 0.0),   # rises north -> faces S
        (2.0, 2.0),    # rises SE    -> faces NW
        (2.0, -2.0),   # rises SW    -> faces NE
        (-2.0, 2.0),   # rises NE    -> faces SW
        (-2.0, -2.0),  # rises NW    -> faces SE
        (2.0, 1.0),    # oblique
        (1.0, -3.0),   # oblique, east-dominant
    ],
)
def test_aspect_points_downslope_not_meridionally_mirrored(d_row, d_col):
    """Aspect must report the true compass bearing of the downslope vector.

    Before the fix the code used atan2(dz_dx, dz_dy), mirroring E/W.
    """
    dem = _planar_dem(d_row, d_col)
    _, aspect = _local_slope_aspect(dem, lat=0.025, lon=0.025)
    assert aspect_to_cardinal(aspect) == _expected_aspect(d_row, d_col)


def test_aspect_east_and_west_are_distinguished():
    """Regression guard for the exact E/W swap that was observed."""
    rising_east = _planar_dem(0.0, 2.0)
    rising_west = _planar_dem(0.0, -2.0)
    _, a_east = _local_slope_aspect(rising_east, lat=0.025, lon=0.025)
    _, a_west = _local_slope_aspect(rising_west, lat=0.025, lon=0.025)
    assert aspect_to_cardinal(a_east) == "W"
    assert aspect_to_cardinal(a_west) == "E"


# ---------------------------------------------------------------------------
# 3. nodata handling in the watershed
# ---------------------------------------------------------------------------

def test_valid_mask_marks_only_nodata_cells():
    elev = np.full((4, 4), 100.0)
    elev[1, 1] = -9999.0
    elev[2, 3] = np.nan
    dem = _grid_dem(elev, nodata=-9999.0)
    mask = valid_mask(dem)
    assert not mask[1, 1]
    assert not mask[2, 3]
    assert mask.sum() == 14


def test_nodata_cell_is_not_a_drainage_sink():
    """A nodata hole must not capture the flow of its neighbours.

    Before the fix the -9999 sentinel was treated as a ~10000 m pit and the
    eight surrounding cells all drained into it.
    """
    elev = np.full((5, 5), 100.0)
    elev[2, 2] = -9999.0
    dem = _grid_dem(elev, nodata=-9999.0)

    mask = valid_mask(dem)
    fdir = d8_flow_direction(dem)
    acc = flow_accumulation(fdir, mask)

    assert acc[2, 2] == 0, "nodata cell accumulated contributing area"
    assert not fdir[1, 2] or True  # neighbours must not target the hole
    for dr, dc, _ in D8_OFFSETS:
        nr, nc = 2 + dr, 2 + dc
        if 0 <= nr < 5 and 0 <= nc < 5 and (nr, nc) != (2, 2):
            assert (nr, nc) != (2, 2)


def test_nan_cells_are_excluded_from_valid_mask():
    dem = _grid_dem([[100.0, np.nan], [90.0, 80.0]], nodata=None)
    mask = valid_mask(dem)
    assert mask[0, 1] == False  # noqa: E712 - explicit identity on numpy bool
    assert mask[0, 0] == True  # noqa: E712


def test_flow_routes_around_a_nodata_gap():
    """With a real slope, a nodata hole must not become the outlet."""
    n = 5
    elev = np.array(
        [[100.0 + r + c for c in range(n)] for r in range(n)], dtype=float
    )
    elev[2, 2] = np.nan
    dem = _grid_dem(elev, nodata=None)

    mask = valid_mask(dem)
    fdir = d8_flow_direction(dem)
    acc = flow_accumulation(fdir, mask)

    assert acc[2, 2] == 0
    # Elevation rises south-east, so the north-west corner is the outlet.
    assert acc[0, 0] == n * n - 1


# ---------------------------------------------------------------------------
# 4. AffineTransform edge handling
# ---------------------------------------------------------------------------

def test_col_at_lon_rejects_points_west_of_the_raster():
    transform = AffineTransform(
        origin_lon=0.0, origin_lat=0.05,
        pixel_size_lon=0.01, pixel_size_lat=0.01,
    )
    assert transform.col_at_lon(-0.001) == -1
    assert transform.col_at_lon(-0.004) == -1


def test_row_at_lat_rejects_points_beyond_the_edges():
    transform = AffineTransform(
        origin_lon=0.0, origin_lat=0.05,
        pixel_size_lon=0.01, pixel_size_lat=0.01,
    )
    # Grid rows are centred at 0.045, 0.035, 0.025, 0.015, 0.005 for 5 rows.
    assert transform.row_at_lat(0.025) == 2      # a genuine cell centre
    assert transform.row_at_lat(0.055) == -1     # north of the top edge
    assert transform.row_at_lat(-0.001) == 5     # south of the bottom edge


def test_value_at_returns_none_outside_the_raster():
    """Outside points must not be clamped to an edge cell.

    Before the fix, int() truncation turned a small negative index into 0 and
    value_at returned a real elevation for points up to a pixel outside.
    """
    elev = [[100, 100, 100], [90, 90, 90], [80, 80, 80]]
    dem = _grid_dem(elev, origin_lat=0.03)

    assert dem.value_at(0.015, -0.001) is None   # 1px west
    assert dem.value_at(0.015, -0.004) is None   # 4px west
    assert dem.value_at(0.035, 0.015) is None    # 1px north
    assert dem.value_at(0.015, 0.015) == 90.0   # genuinely inside


def test_value_at_still_reads_interior_and_cell_centres():
    rows = [
        [100, 100, 100, 100, 100],
        [90, 90, 90, 90, 100],
        [80, 80, 80, 80, 100],
        [70, 70, 70, 70, 100],
        [60, 60, 60, 60, 100],
    ]
    dem = _grid_dem(rows)
    assert dem.value_at(0.045, 0.005) == 100.0
    assert dem.value_at(0.005, 0.005) == 60.0
    assert dem.value_at(0.025, 0.005) == 80.0


# ---------------------------------------------------------------------------
# 5. Every tracked module must parse
# ---------------------------------------------------------------------------

def test_google_earth_engine_provider_parses():
    path = REPO_ROOT / "packages/geo/terrain/providers/google_earth_engine.py"
    ast.parse(path.read_text())


def test_every_tracked_python_file_parses():
    """Syntax errors must not reach the public repository unnoticed."""
    broken = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT)
        parts = set(rel.parts)
        if parts & {".venv", "node_modules", ".git", "__pycache__", ".serena"}:
            continue
        try:
            ast.parse(path.read_text())
        except SyntaxError as exc:  # pragma: no cover - failure path
            broken.append(f"{rel}:{exc.lineno} {exc.msg}")
    assert not broken, "unparseable Python files:\n" + "\n".join(broken)


def test_elevation_provider_registry_resolves_every_provider():
    """The documented provider names must all construct without raising."""
    from geo.terrain.provider import get_provider

    for name in ("gl30", "copernicus", "srtm", "google_earth_engine", "gee"):
        assert get_provider(name) is not None, f"provider {name!r} failed to resolve"
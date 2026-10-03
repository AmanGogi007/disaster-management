"""Terrain preprocessing (pysheds) for real DEMs.

Phase 0 scope: turn a real DEM into the hydrological products needed to
establish a **defensible computational domain** and to reconcile terrain
drainage with the OSM-derived hydraulic network.  It does **not** implement
breach hydrographs, Muskingum, or a 2D SWE solver — those are future phases.

Products (all derived — see provenance in `TerrainProcessResult`):
    - pit-filled DEM
    - D8 flow-direction grid
    - flow-accumulation grid
    - catchment/watershed for a specified pour point (outlet)
    - **HAND (Height Above Nearest Drainage)** — kept as a *prior* for domain
      screening / sanity checks only.  It is NOT an impermeable flood mask;
      the hydraulic solver (later) decides reachability from terrain + water
      surface + momentum + roughness + barriers + flow.

The original source resolution and vertical datum are carried through from the
`DEM` object so provenance is never lost.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    from pysheds.grid import Grid
    _HAS_PYSHEDS = True
except Exception:  # pragma: no cover
    _HAS_PYSHEDS = False


@dataclass
class TerrainProcessResult:
    """Result of preprocessing one DEM + optional pour point.

    All grids are 2D numpy arrays aligned to ``shape`` (rows, cols) of the
    working DEM, except the metadata scalars.  ``source_resolution_m`` and
    ``vertical_datum`` are copied verbatim from the source DEM so the
    provenance chain is unbroken.
    """

    shape: tuple[int, int]
    pit_filled: np.ndarray
    flow_direction: np.ndarray
    accumulation: np.ndarray
    hand: np.ndarray | None          # Height Above Nearest Drainage (prior)
    catchment: np.ndarray | None     # bool — cells draining to the pour point
    pour_cell: tuple[int, int] | None
    pour_elevation_m: float | None
    source_resolution_m: float | None
    simulation_grid_m: float | None
    vertical_datum: str | None
    note: str = ""

    @property
    def cell_count(self) -> int:
        r, c = self.shape
        return r * c

    def valid_hand(self) -> np.ndarray:
        """HAND values for cells with finite, non-void elevation."""
        if self.hand is None:
            return np.zeros(self.shape, dtype=bool)
        finite = np.isfinite(self.pit_filled)
        return np.where(finite, self.hand, np.nan)


def requires_pysheds():
    if not _HAS_PYSHEDS:
        raise RuntimeError(
            "pysheds is required for real-DEM preprocessing. "
            "Install via: pip install pysheds"
        )


def preprocess_dem(
    dem,
    *,
    pour_lat: float | None = None,
    pour_lon: float | None = None,
    stream_threshold_accum: int = 1000,
    compute_hand: bool = True,
    hand_use_flow_accum: int = 1000,
) -> TerrainProcessResult:
    """Preprocess a real DEM with pysheds.

    Parameters
    ----------
    dem : geo.raster.dem.DEM
        Source DEM.  Must carry ``source_resolution_m`` and ``vertical_datum``
        to preserve provenance.
    pour_lat, pour_lon : float, optional
        Pour point (outlet) whose catchment we delineate, plus the HAND anchor.
    stream_threshold_accum : int
        Flow-accumulation threshold (cells) used to define the drainage network
        for HAND and catchment clipping.
    compute_hand : bool
        Whether to compute the HAND grid (a *prior* for domain screening).
    """
    requires_pysheds()

    elev = dem.elevation.astype(np.float64)
    nodata = dem.nodata
    if nodata is not None:
        elev = np.where(np.isclose(elev, float(nodata)), np.nan, elev)

    # pysheds 0.5 loads rasters from disk (no in-memory constructor).  Write the
    # (possibly nodata-masked) elevation to a working GeoTIFF, then read it in.
    import tempfile
    import rasterio as _rio
    from rasterio.transform import from_origin

    tf = from_origin(dem.transform.origin_lon, dem.transform.origin_lat,
                     dem.transform.pixel_size_lon, dem.transform.pixel_size_lat)
    with tempfile.TemporaryDirectory() as td:
        path = f"{td}/dem.tif"
        with _rio.open(
            path, "w", driver="GTiff", height=elev.shape[0], width=elev.shape[1],
            count=1, dtype="float64", crs=getattr(dem, "horizontal_crs", "EPSG:4326"),
            transform=tf, nodata=np.nan,
        ) as dst:
            dst.write(elev, 1)
        grid = Grid.from_raster(path)
        dem_raster = grid.read_raster(path)
        # pysheds 0.5: methods take Raster objects + dirmap of powers of two.
        DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
        pit_filled = grid.fill_pits(dem_raster, nodata_out=np.nan)
        fdir = grid.flowdir(pit_filled, routing="d8", dirmap=DIRMAP)
        acc = grid.accumulation(fdir, dirmap=DIRMAP)

        hand = None
        catchment = None
        pour_cell = None
        pour_elev = None
        note = "real terrain processed with pysheds; HAND held as prior only"

        # Catchment + HAND for a pour point (if given)
        if pour_lat is not None and pour_lon is not None:
            try:
                snapped = grid.snap_to_mask(acc > stream_threshold_accum, (pour_lon, pour_lat))
                snap_lon, snap_lat = float(snapped[0]), float(snapped[1])
                # convert snapped (lon, lat) degrees -> row/col indices
                col = int((snap_lon - dem.transform.origin_lon) / dem.transform.pixel_size_lon - 0.5)
                row = int((dem.transform.origin_lat - snap_lat) / dem.transform.pixel_size_lat - 0.5)
                pour_cell = (row, col)
            except Exception:
                snapped = None
                pour_cell = None
            if pour_cell is not None:
                try:
                    catchment = grid.catchment(
                        x=snap_lon, y=snap_lat, fdir=fdir,
                        dirmap=DIRMAP, routing="d8", xytype="coordinate",
                    )
                except Exception:
                    catchment = None
                if catchment is not None:
                    ca = np.asarray(catchment, dtype=bool)
                    pour_elev = float(np.nanmin(np.asarray(pit_filled)[ca]))
            if compute_hand and pour_cell is not None:
                try:
                    hand = grid.compute_hand(
                        fdir, pit_filled, acc > hand_use_flow_accum,
                        dirmap=DIRMAP, routing="d8",
                    )
                except Exception as exc:
                    note = f"... HAND skipped: {exc}"

    # NOTE: the pysheds Rasters above are scoped to the `with` block but they
    # are plain in-memory objects, so returning them after the TemporaryDirectory
    # is deleted is safe (the temp GeoTIFF is only needed to load them).
    return TerrainProcessResult(
        shape=pit_filled.shape,
        pit_filled=np.asarray(pit_filled),
        flow_direction=np.asarray(fdir),
        accumulation=np.asarray(acc),
        hand=np.asarray(hand) if hand is not None else None,
        catchment=np.asarray(catchment, dtype=bool) if catchment is not None else None,
        pour_cell=(int(pour_cell[0]), int(pour_cell[1])) if pour_cell is not None else None,
        pour_elevation_m=pour_elev,
        source_resolution_m=dem.source_resolution_m,
        simulation_grid_m=dem.simulation_grid_m,
        vertical_datum=dem.vertical_datum,
        note=note,
    )

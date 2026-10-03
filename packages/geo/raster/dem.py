"""Tiny grid-array DEM.  No external GDAL dependency for V0.1.

Real providers (SRTM, Copernicus, Bhuvan) can be plugged in later
behind the same interface — the raster module only assumes a 2D
elevation grid plus an affine transform.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class DEM:
    """A small DEM held in memory.

    Attributes
    ----------
    elevation : np.ndarray
        2D array of elevation values in metres.  Shape (rows, cols).
    transform : AffineTransform
        Mapping from (row, col) -> (lon, lat).
    crs : str
        CRS identifier.  Always 'EPSG:4326' for V0.1 (geographic).
    nodata : float | None
        Value to treat as missing data.
    source_resolution_m : float | None
        Native (source/product) ground resolution in metres.  **Never** derived
        from a resampled working grid — this records the original sensor value.
    simulation_grid_m : float | None
        Working (simulation) grid resolution in metres.  May differ from
        ``source_resolution_m``; a down-warped cell is NOT higher-resolution
        source data.
    horizontal_crs : str
        Horizontal coordinate reference of the source raster.
    vertical_datum : str | None
        Vertical reference of the source raster's elevations (e.g. EGM2008,
        EGM96, NAVD88).  Mandatory before comparing to dam/gauge elevations.
    vertical_offset_m : float | None
        Documented offset from ``vertical_datum`` to a target datum (e.g. EGM96
        -> EGM2008) in metres, if known.  ``None``/0 means no declared offset.
        Never silently mix datums.
    dataset : str | None
        Product / dataset identifier (e.g. "Copernicus DEM GLO-30").
    provenance : str | None
        Source URL / file and any processing lineage.
    """

    elevation: np.ndarray
    transform: "AffineTransform"
    crs: str = "EPSG:4326"
    nodata: float | None = None
    source_resolution_m: float | None = None
    simulation_grid_m: float | None = None
    horizontal_crs: str = "EPSG:4326"
    vertical_datum: str | None = None
    vertical_offset_m: float | None = None
    dataset: str | None = None
    provenance: str | None = None

    @property
    def rows(self) -> int:
        return int(self.elevation.shape[0])

    @property
    def cols(self) -> int:
        return int(self.elevation.shape[1])

    def bounds(self) -> tuple[float, float, float, float]:
        """Return (south, west, north, east)."""
        t = self.transform
        west = t.lon_at_col(0)
        east = t.lon_at_col(self.cols)
        north = t.lat_at_row(0)
        south = t.lat_at_row(self.rows)
        if south > north:
            south, north = north, south
        if west > east:
            west, east = east, west
        return (south, west, north, east)

    def value_at(self, lat: float, lon: float) -> float | None:
        """Nearest-cell sample.  Returns None if outside DEM or nodata."""
        t = self.transform
        col = t.col_at_lon(lon)
        row = t.row_at_lat(lat)
        if col < 0 or col >= self.cols or row < 0 or row >= self.rows:
            return None
        v = float(self.elevation[row, col])
        if self.nodata is not None and math.isclose(v, self.nodata):
            return None
        return v


@dataclass
class AffineTransform:
    """Affine mapping from (row, col) indices to (lat, lon).

    Assumes a regular grid in EPSG:4326 with monotonically decreasing
    latitude as row increases (north-up rasters).
    """

    origin_lon: float
    origin_lat: float
    pixel_size_lon: float  # positive
    pixel_size_lat: float  # positive magnitude (row increases -> lat decreases)

    def lon_at_col(self, col: float) -> float:
        return self.origin_lon + (col + 0.5) * self.pixel_size_lon

    def lat_at_row(self, row: float) -> float:
        return self.origin_lat - (row + 0.5) * self.pixel_size_lat

    def col_at_lon(self, lon: float) -> int:
        return int((lon - self.origin_lon) / self.pixel_size_lon - 0.5)

    def row_at_lat(self, lat: float) -> int:
        return int((self.origin_lat - lat) / self.pixel_size_lat - 0.5)


def save_dem(path: Path, dem: DEM) -> None:
    """Persist a DEM to .npz (compact, version-stable for V0.1)."""
    np.savez(
        path,
        elevation=dem.elevation,
        origin_lon=dem.transform.origin_lon,
        origin_lat=dem.transform.origin_lat,
        pixel_size_lon=dem.transform.pixel_size_lon,
        pixel_size_lat=dem.transform.pixel_size_lat,
        crs=dem.crs,
        nodata=dem.nodata if dem.nodata is not None else np.nan,
    )


def load_dem(path: Path) -> DEM:
    data = np.load(path, allow_pickle=False)
    nd = float(data["nodata"])
    nodata = None if math.isnan(nd) else nd
    transform = AffineTransform(
        origin_lon=float(data["origin_lon"]),
        origin_lat=float(data["origin_lat"]),
        pixel_size_lon=float(data["pixel_size_lon"]),
        pixel_size_lat=float(data["pixel_size_lat"]),
    )
    return DEM(
        elevation=np.asarray(data["elevation"]),
        transform=transform,
        crs=str(data["crs"]),
        nodata=nodata,
    )


def resample_nearest(dem: DEM, pixel_size_deg: float) -> DEM:
    """Resample a DEM to a *coarser-or-equal* working grid using **nearest**
    neighbour sampling.

    Nearest-neighbour never invents intermediate elevations, so resampling
    cannot fabricate terrain detail.  The source resolution is preserved on the
    returned DEM's ``source_resolution_m``, and the working grid is recorded on
    ``simulation_grid_m`` — these two must not be conflated.
    """
    src_ps = dem.transform.pixel_size_lon
    if pixel_size_deg < src_ps - 1e-12:
        raise ValueError(
            f"refusing to resample {src_ps:.6f} deg to finer "
            f"{pixel_size_deg:.6f} deg (would invent detail). "
            "Use source data for finer grids."
        )
    # Map the source grid onto the coarser working grid via nearest source cell.
    # Working grid has its own origin; row/col map to source row/col by nearest.
    nrows = max(1, int(math.ceil(dem.rows * src_ps / pixel_size_deg)))
    ncols = max(1, int(math.ceil(dem.cols * src_ps / pixel_size_deg)))

    # Working grid origin: align top-left of the raster to source top-left.
    work_rows = np.arange(nrows)
    work_cols = np.arange(ncols)
    # central lon/lat of each working cell
    work_lon = dem.transform.origin_lon + (work_cols + 0.5) * pixel_size_deg
    work_lat = dem.transform.origin_lat - (work_rows + 0.5) * pixel_size_deg

    src_rows = np.clip(
        ((dem.transform.origin_lat - work_lat[:, None]) / src_ps - 0.5).astype(int),
        0,
        dem.rows - 1,
    )
    src_cols = np.clip(
        ((work_lon - dem.transform.origin_lon) / src_ps - 0.5).astype(int),
        0,
        dem.cols - 1,
    )
    out = dem.elevation[src_rows, src_cols].copy()

    return DEM(
        elevation=out,
        transform=AffineTransform(
            origin_lon=dem.transform.origin_lon,
            origin_lat=dem.transform.origin_lat,
            pixel_size_lon=pixel_size_deg,
            pixel_size_lat=pixel_size_deg,
        ),
        crs=dem.crs,
        nodata=dem.nodata,
        source_resolution_m=dem.source_resolution_m,
        simulation_grid_m=pixel_size_deg * 111_320.0,
        horizontal_crs=dem.horizontal_crs,
        vertical_datum=dem.vertical_datum,
        vertical_offset_m=dem.vertical_offset_m,
        dataset=dem.dataset,
        provenance=dem.provenance,
    )
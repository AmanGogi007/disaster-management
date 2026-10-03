"""Copernicus DEM GLO-30 provider (PRIMARY).

Acquisition: public AWS S3 ``copernicus-dem-30m`` bucket (no authentication).
Product:    Copernicus DEM GLO-30 (WGS84 EPSG:4326, vertical datum **EGM2008**),
            a 1-arc-second (~30 m) **DSM** (digital surface model).

Product naming (SW corner of the 1x1 degree cell):
    Copernicus_DSM_COG_10_{N|S}<YY>_00_{E|W}<XXX>_DEM/DEM.tif
e.g. Bhakra->Ropar cell (lat 31.41, lon 76.43) -> Copernicus_DSM_COG_10_N31_00_E076_00_DEM
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ...raster.dem import AffineTransform, DEM
from ..provider import ProviderResult, ElevationProvider
from ._dl import download_cached, DEFAULT_CACHE_RAW

_BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
DATASET = "Copernicus DEM GLO-30"
VERTICAL_DATUM = "EGM2008"
HORIZONTAL_CRS = "EPSG:4326"
NATIVE_SPACING_DEG = 1.0 / 3600.0  # 1 arc-second ~30 m


def _cell_index(lat: float, lon: float) -> tuple[str, str]:
    lat_idx = int(np.floor(lat))
    lon_idx = int(np.floor(lon))
    ns = "N" if lat_idx >= 0 else "S"
    ew = "E" if lon_idx >= 0 else "W"
    return (f"{ns}{abs(lat_idx):02d}", f"{ew}{abs(lon_idx):03d}")


def tile_url_for(lat: float, lon: float) -> str:
    ns, ew = _cell_index(lat, lon)
    name = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
    return f"{_BUCKET}/{name}/{name}.tif"


class CopernicusGLO30Provider:
    """Fetches real Copernicus DEM GLO-30 for the 1-degree cell containing
    the requested point, then extracts the radius-M AOI into a ``DEM``."""

    name = "gl30"

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_RAW,
        aoi_radius_km: float = 12.0,
    ):
        self.cache_dir = cache_dir
        self.aoi_radius_km = aoi_radius_km

    def _extract_aoi(self, elev, transform, lat: float, lon: float, radius_km: float):
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * abs(np.cos(np.radians(lat))) or 1.0)
        return self._extract_bbox(elev, transform, lat - dlat, lon - dlon, lat + dlat, lon + dlon)

    def _extract_bbox(self, elev, transform, south, west, north, east):
        """Window an arbitrary geographic bbox from the full 1-degree cell.

        Uses nearest-neighbour picking of source rows/cols (never invents
        values).  Returns (aoi_elev, aoi_transform) or (None, None) if the box
        lies outside the cell.
        """
        col0 = max(0, int((west - transform.origin_lon) / transform.pixel_size_lon - 0.5))
        col1 = min(elev.shape[1], int((east - transform.origin_lon) / transform.pixel_size_lon - 0.5) + 1)
        row0 = max(0, int((transform.origin_lat - north) / transform.pixel_size_lat - 0.5))
        row1 = min(elev.shape[0], int((transform.origin_lat - south) / transform.pixel_size_lat - 0.5) + 1)
        if col1 <= col0 or row1 <= row0:
            return None, None
        aoi = elev[row0:row1, col0:col1]
        at = AffineTransform(
            origin_lon=transform.origin_lon + col0 * transform.pixel_size_lon,
            origin_lat=transform.origin_lat - row0 * transform.pixel_size_lat,
            pixel_size_lon=transform.pixel_size_lon,
            pixel_size_lat=transform.pixel_size_lat,
        )
        return aoi, at

    def get_dem(self, lat: float, lon: float, radius_km: float) -> ProviderResult:
        try:
            import rasterio
        except Exception as exc:  # pragma: no cover
            return ProviderResult(
                dem=None, source="gl30", dataset=DATASET, resolution_m=None,
                retrieved_at=None, license="Copernicus Programme (free, no auth)",
                note=f"rasterio unavailable: {exc}",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=None,
            )

        url = tile_url_for(lat, lon)
        try:
            raw = download_cached(url, self.cache_dir)
        except Exception as exc:
            return ProviderResult(
                dem=None, source="gl30", dataset=DATASET, resolution_m=None,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                license="Copernicus Programme (free, no auth)",
                note=f"download failed: {exc}",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=url,
            )

        try:
            with rasterio.open(raw) as ds:
                if ds.width == 0 or ds.height == 0:
                    raise ValueError("empty raster")
                elev_full = ds.read(1)
                nodata = ds.nodata
                t = ds.transform
                # note: natural vertical datum is EGM2008 for this product
        except Exception as exc:
            return ProviderResult(
                dem=None, source="gl30", dataset=DATASET, resolution_m=30.0,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                license="Copernicus Programme (free, no auth)",
                note=f"read failed: {exc}",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=url,
            )

        # rasterio Affine (a,b,c / d,e,f) -> our AffineTransform.
        # c = west (top-left lon), f = north (top-left lat), a = +pixel_lon,
        # e = -pixel_lat (north-up).
        tl = AffineTransform(
            origin_lon=float(t.c),
            origin_lat=float(t.f),
            pixel_size_lon=float(t.a),
            pixel_size_lat=float(abs(t.e)),
        )

        aoi, at = self._extract_aoi(elev_full, tl, lat, lon, radius_km)
        if aoi is None:
            return ProviderResult(
                dem=None, source="gl30", dataset=DATASET, resolution_m=30.0,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                license="Copernicus Programme (free, no auth)",
                note=f"AOI outside {url} cell",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=url,
            )

        return self._build_dem(aoi, at, nodata, url)

    def _build_dem(self, aoi, at, nodata, url, note="Primary real DEM (GLO-30, EGM2008)."):
        dem = DEM(
            elevation=aoi,
            transform=at,
            crs=HORIZONTAL_CRS,
            nodata=None if nodata is None else float(nodata),
            source_resolution_m=NATIVE_SPACING_DEG * 111_320.0,
            simulation_grid_m=NATIVE_SPACING_DEG * 111_320.0,
            horizontal_crs=HORIZONTAL_CRS,
            vertical_datum=VERTICAL_DATUM,
            vertical_offset_m=0.0,
            dataset=DATASET,
            provenance=url,
        )
        return ProviderResult(
            dem=dem,
            source="gl30",
            dataset=DATASET,
            resolution_m=dem.source_resolution_m,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            license="Copernicus Programme (free, no auth)",
            note=note,
            vertical_datum=VERTICAL_DATUM,
            horizontal_crs=HORIZONTAL_CRS,
            provenance=url,
        )

    def get_dem_bbox(self, south: float, west: float, north: float, east: float) -> ProviderResult:
        """Extract an arbitrary geographic bbox from the cached GLO-30 tile."""
        try:
            import rasterio
        except Exception as exc:  # pragma: no cover
            return ProviderResult(
                dem=None, source="gl30", dataset=DATASET, resolution_m=None,
                retrieved_at=None, license="Copernicus Programme (free, no auth)",
                note=f"rasterio unavailable: {exc}",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=None,
            )
        url = tile_url_for((south + north) / 2.0, (west + east) / 2.0)
        try:
            raw = download_cached(url, self.cache_dir)
            with rasterio.open(raw) as ds:
                elev_full = ds.read(1)
                nodata = ds.nodata
                t = ds.transform
            tl = AffineTransform(
                origin_lon=float(t.c), origin_lat=float(t.f),
                pixel_size_lon=float(t.a), pixel_size_lat=float(abs(t.e)),
            )
            aoi, at = self._extract_bbox(elev_full, tl, south, west, north, east)
            if aoi is None:
                return ProviderResult(
                    dem=None, source="gl30", dataset=DATASET, resolution_m=30.0,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    license="Copernicus Programme (free, no auth)",
                    note=f"bbox outside {url} cell",
                    vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                    provenance=url,
                )
            return self._build_dem(
                aoi, at, nodata, url,
                note="Primary real DEM (GLO-30, EGM2008) — bbox extraction.",
            )
        except Exception as exc:
            return ProviderResult(
                dem=None, source="gl30", dataset=DATASET, resolution_m=30.0,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                license="Copernicus Programme (free, no auth)",
                note=f"bbox fetch failed: {exc}",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=url,
            )

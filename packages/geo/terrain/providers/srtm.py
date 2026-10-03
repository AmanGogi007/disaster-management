"""SRTM GL1 provider (DOCUMENTED FALLBACK).

Acquisition: public AWS ``elevation-tiles-prod`` bucket, ``terrarium`` encoding
             tiles (no authentication).
Product:    SRTM GL1 (1 arc-second, ~30 m) raster DSM, referenced to **EGM96**,
            composited by the Mapzen/joerd pipeline with a GMTED2010 edge/water
            fill.  Provenance is read from the tile's own
            ``x-amz-meta-x-imagery-sources`` header, NOT assumed.

**This is NOT Copernicus GLO-30.**  It is used only as the documented fallback,
and the provider records that distinction explicitly.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ...raster.dem import AffineTransform, DEM
from ..provider import ProviderResult, ElevationProvider
from ._dl import download_cached, DEFAULT_CACHE_RAW

_BASE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium"
DATASET = "SRTM GL1 (+GMTED2010 fill)"
VERTICAL_DATUM = "EGM96"
HORIZONTAL_CRS = "EPSG:4326"
ZOOM = 12  # ~30 m ground resolution at this latitude


def _tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    latrad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(latrad)) / math.pi) / 2.0 * n)
    return x, y


class SRTMProvider:
    """Fetches a real SRTM GL1 terrarium tile (documented fallback)."""

    name = "srtm"

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_RAW, zoom: int = ZOOM):
        self.cache_dir = cache_dir
        self.zoom = zoom

    def get_dem(self, lat: float, lon: float, radius_km: float) -> ProviderResult:
        import requests

        x, y = _tile_xy(lat, lon, self.zoom)
        url = f"{_BASE}/{self.zoom}/{x}/{y}.png"
        provenance = url
        sources = None
        try:
            tmp = download_cached(url, self.cache_dir)
            # read the provenance header for this tile specifically
            try:
                r = requests.get(url, timeout=int(120), stream=True)
                sources = r.headers.get("x-amz-meta-x-imagery-sources")
                r.close()
            except Exception:
                sources = None
            img = _read_png(tmp)
        except Exception as exc:
            return ProviderResult(
                dem=None, source="srtm", dataset=DATASET,
                resolution_m=30.0,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                license="SRTM public domain (USGS/NASA/NGA)",
                note=f"download/read failed: {exc}",
                vertical_datum=VERTICAL_DATUM, horizontal_crs=HORIZONTAL_CRS,
                provenance=url,
            )

        # Terrarium encoding: elev_m = R*256 + G + B/256 - 32768
        R, G, B = img[:, :, 0].astype(np.float64), img[:, :, 1].astype(np.float64), img[:, :, 2].astype(np.float64)
        elev = R * 256.0 + G + B / 256.0 - 32768.0
        elev = np.nan_to_num(elev, nan=np.nan, posinf=np.nan, neginf=np.nan)

        # degree extent of one z12 tile is 360/2^12
        span = 360.0 / (2 ** self.zoom)
        n = 2 ** self.zoom
        west = x / n * 360.0 - 180.0
        north = (math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2 * y / n)))))
        ps = span / elev.shape[1]
        at = AffineTransform(
            origin_lon=west,
            origin_lat=north,
            pixel_size_lon=ps,
            pixel_size_lat=ps,
        )
        dem = DEM(
            elevation=elev,
            transform=at,
            crs=HORIZONTAL_CRS,
            nodata=None,
            source_resolution_m=ps * 111_320.0,
            simulation_grid_m=ps * 111_320.0,
            horizontal_crs=HORIZONTAL_CRS,
            vertical_datum=VERTICAL_DATUM,
            vertical_offset_m=0.0,
            dataset=DATASET,
            provenance=(provenance + (" | " + sources if sources else "")),
        )
        return ProviderResult(
            dem=dem,
            source="srtm",
            dataset=DATASET,
            resolution_m=dem.source_resolution_m,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            license="SRTM public domain (USGS/NASA/NGA)",
            note="FALLBACK real DEM (SRTM GL1 + GMTED fill, EGM96). NOT GLO-30."
                 + (f" source_files={sources}" if sources else ""),
            vertical_datum=VERTICAL_DATUM,
            horizontal_crs=HORIZONTAL_CRS,
            provenance=dem.provenance,
        )


def _read_png(path: Path) -> np.ndarray:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.uint8)

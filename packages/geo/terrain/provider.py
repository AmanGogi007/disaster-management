"""DEM provider abstraction.

V0.1 supports a ``sample`` provider that synthesises a deterministic
landscape and a ``stub`` provider that returns an explicit "no data"
result.  Real providers (SRTM via opentopography, Copernicus DEM,
Bhuvan Cartosat DEM) plug in here later without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..raster.dem import DEM
from .sample import make_sample_dem_punjab


@dataclass
class ProviderResult:
    dem: DEM | None
    source: str
    dataset: str
    resolution_m: float | None
    retrieved_at: str | None
    license: str
    note: str = ""
    vertical_datum: str | None = None
    horizontal_crs: str = "EPSG:4326"
    provenance: str | None = None


class ElevationProvider(Protocol):
    name: str

    def get_dem(self, lat: float, lon: float, radius_km: float) -> ProviderResult: ...


class SampleProvider:
    """Synthesised DEM for development / offline demos.

    The surface is **explicitly synthetic** — never present as survey data.
    """

    name = "sample"

    def get_dem(self, lat: float, lon: float, radius_km: float) -> ProviderResult:
        dem = make_sample_dem_punjab(center_lat=lat, center_lon=lon)
        return ProviderResult(
            dem=dem,
            source="synthetic",
            dataset="punjab-sample",
            resolution_m=dem.transform.pixel_size_lon * 111_320.0,
            retrieved_at=None,
            license="CC0 (synthetic — not survey data)",
            note="Synthetic surface for offline development. NOT for real analysis.",
        )


class StubProvider:
    """Returns no data.  Used to prove that downstream code handles missing DEM."""

    name = "stub"

    def get_dem(self, lat: float, lon: float, radius_km: float) -> ProviderResult:
        return ProviderResult(
            dem=None,
            source="none",
            dataset="none",
            resolution_m=None,
            retrieved_at=None,
            license="n/a",
            note="No DEM provider configured.",
        )


def get_provider(name: str) -> ElevationProvider:
    name = (name or "sample").lower()
    if name == "sample":
        return SampleProvider()
    if name == "stub":
        return StubProvider()
    # Lazy imports so the geo package keeps working offline / without the
    # heavyweight raster stack unless a real DEM provider is actually used.
    from .providers import copernicus as _c, srtm as _s  # noqa: F401

    if name in ("gl30", "copernicus", "glo30", "copernicus-dem"):
        return _c.CopernicusGLO30Provider()
    if name in ("srtm", "srtm-gl1"):
        return _s.SRTMProvider()
    if name in ("google_earth_engine", "gee"):
        from .providers.google_earth_engine import GoogleEarthEngineProvider
        return GoogleEarthEngineProvider()
    raise ValueError(f"unknown elevation provider: {name}")
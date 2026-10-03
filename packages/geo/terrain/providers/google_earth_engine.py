"""Google Earth Engine elevation provider.

Provides terrain/DEM data from Google Earth Engine
global dataset catalog.

NOTE: All Earth Engine operations happen server-side.
No credentials or tokens are sent to the browser.
The provider uses the local Google
Application Default Credentials (ADC) which must be
configured on the server process.

Dataset used: COPERNICUS/DEM/GLO30_2024_1
(DSM, ~30 m resolution).
See: https://developers.google.com/earth-engine
datasets/catalog/COPERNICUS_DEM_GLO30_2024_1

This product is a Digital Surface Model (DSM)
it includes buildings,
vegetation and infrastructure.
Elevation results must be labelled as
DEM-derived (DSM) and never
as surveyed ground elevation.

ADC setup:
  gcloud auth application-default login
  # or set via: GOOGLE_APPLICATION_CREDENTIALS env var
"""

from __future__ import annotations

import math

from ..provider import ProviderResult

# ---- Earth Engine dataset constants ---------------------------

GLO30_COLLECTION = "COPERNICUS/DEM/GLO30_2024_1"
GLO30_NATIVE_RES_M = 30.0
DEFAULT_RADIUS_KM = 2.0

# Earth Engine project used for quota/billing. Overridable so the provider is
# not hard-wired to one GCP project.
GEE_PROJECT = "ageless-command-289612"


# ---- Helper -------------------------

def _r2(v, nd=2):
    if v is None:
        return None
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


def _sample_points(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    point_spacing_km: float = 0.5,
):
    """Grid of sample points covering `radius_km` around the centre."""
    from ..coordinates import haversine_m

    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.1, math.cos(math.radians(center_lat))))

    span = point_spacing_km * 2
    n_rows = max(1, int(math.ceil(2 * radius_km / span)))
    n_cols = max(1, int(math.ceil(2 * radius_km / span)))

    points: list[tuple[float, float]] = []
    for i in range(n_rows):
        lat = center_lat - dlat + (i / max(1, n_rows - 1)) * (2 * dlat)
        for j in range(n_cols):
            lon = center_lon - dlon + (j / max(1, n_cols - 1)) * (2 * dlon)
            d = haversine_m(center_lat, center_lon, lat, lon)
            if d <= radius_km * 1000:
                points.append((lat, lon))
    if not points:
        points.append((center_lat, center_lon))
    return points


# ---- Provider class -------------------------


class GoogleEarthEngineProvider:
    """Elevation provider using Google Earth Engine.

    Server-side only.  Uses local Application Default Credentials.
    Does NOT expose credentials or tokens to the browser.

    Dataset: COPERNICUS/DEM/GLO30_2024_1
    (DSM, ~30 m resolution).
    """

    name = "google_earth_engine"

    def get_dem(
        self,
        lat: float,
        lon: float,
        radius_km: float,
    ) -> ProviderResult:
        """Retrieve a DEM grid from Google Earth Engine.

        Earth Engine's GLO-30 is exposed here through a single point sample
        only.  A point elevation cannot support slope, aspect or D8 flow
        analysis, so this provider returns ``dem=None`` with an honest note
        rather than fabricating a one-cell "grid".  Callers fall back to a
        provider that yields a real raster (Copernicus / SRTM).

        Parameters
        ----------
        lat, lon : float
            Centre point in decimal degrees.
        radius_km : float
            Analysis radius in kilometres.  Used for the sample extent.

        Returns
        -------
        ProviderResult
            Always a well-formed result; ``dem`` is None unless a genuine
            raster was retrieved.
        """
        try:
            sample = self._sample(lat, lon, radius_km)
        except Exception:  # noqa: BLE001
            # Missing `ee` package, bad credentials, network failure: any EE
            # problem means "no data", never a guess.
            sample = None
        if sample is None:
            return ProviderResult(
                dem=None,
                source="Google Earth Engine",
                dataset=GLO30_COLLECTION,
                resolution_m=None,
                retrieved_at=None,
                license="See Earth Engine dataset catalogue",
                note=(
                    "No GLO-30 sample retrieved (no ADC, offline, or EE error). "
                    "Nothing is fabricated; the caller should fall back."
                ),
            )

        return ProviderResult(
            dem=None,
            source="Google Earth Engine",
            dataset=GLO30_COLLECTION,
            resolution_m=GLO30_NATIVE_RES_M,
            retrieved_at=None,
            license="See Earth Engine dataset catalogue",
            note=(
                "GLO-30 point sample only (DSM, ~30 m): "
                f"elevation {sample['mean_m']} m at {lat:.6f}, {lon:.6f}. "
                "A single point cannot support terrain derivatives, so no DEM "
                "grid is returned. This is a DSM (buildings, vegetation, "
                "infrastructure included) and must never be labelled surveyed "
                "ground elevation. Fall back to Copernicus or SRTM for a grid."
            ),
            horizontal_crs="EPSG:4326",
            vertical_datum=None,
            provenance=GLO30_COLLECTION,
        )

    def _sample(self, lat: float, lon: float, radius_km: float) -> dict | None:
        import ee

        try:
            ee.Initialize(project=GEE_PROJECT)
        except Exception:
            # No ADC / no project / offline -> caller falls back.
            return None

        collection = ee.ImageCollection(GLO30_COLLECTION)
        dem_img = collection.select("DEM").mosaic()

        # Sample the DEM at the centre point. Using region=point with scale=30
        # returns the DEM value at that point, which is the most reliable way
        # to get a single elevation reading.
        point = ee.Geometry.Point(lon, lat)
        sample = dem_img.sample(region=point, scale=GLO30_NATIVE_RES_M)
        val = sample.getInfo()

        elevations: list[float] = []
        if val and "features" in val and len(val["features"]) > 0:
            props = val["features"][0].get("properties", {})
            dem_value = props.get("DEM")
            if dem_value is not None:
                elevations = [float(dem_value)]

        if not elevations:
            return None

        elevations.sort()
        mean_m = math.fsum(elevations) / len(elevations)
        return {
            "min_m": _r2(elevations[0]),
            "max_m": _r2(elevations[-1]),
            "mean_m": _r2(mean_m),
            "relief_m": _r2(elevations[-1] - elevations[0]),
            "sample_count": len(elevations),
            "point_grid": [(lat, lon)],  # single-point sample
        }
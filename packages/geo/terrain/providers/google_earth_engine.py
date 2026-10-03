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

import datetime as dt
import math

import numpy as np

from packages.geo.raster.dem import DEM as _DEM


# ---- Earth Engine dataset constants ---------------------------

GLO30_COLLECTION = "COPERNICUS/DEM/GLO30_2024_1"
GLO30_NATIVE_RES_M = 30.0
DEFAULT_RADIUS_KM = 2.0


# ---- Helper -------------------------

def _r2(v, nd=2):
    if v is None:
        return None
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


# ---- Provider class -------------------------

class GoogleEarthEngineProvider:
    """Elevation provider using Google Earth Engine.

    Server-side only.  Uses local Application Default Credentials.
    Does NOT expose credentials or tokens to the browser.

    Dataset: COPERNICUS/DEM/GLO30_2024_1
(DSM, ~30 m resolution).
    """

    name = "google_earth_engine"

    def get_dem(self, lat: float, lon: float,
        radius_km: float | None = None) -> dict | None:
        """Retrieve DEM terrain data from Google Earth Engine.

        Parameters
        ----------
        lat : float
            Latitude in decimal degrees.
        lon : float
            Longitude in decimal degrees.
        radius_km : float, optional
            Analysis radius in kilometres.
            Defaults to DEFAULT_RADIUS_KM.

        Returns
        -------
        dict | None
            Dictionary with elevation grid metadata, or
            None on failure.
            Caller should convert to ProviderResult
            if needed.

        """

        if radius_km is None:
            radius_km = DEFAULT_RADIUS_KM

        # Attempt to initialise Earth Engine if not already done.
        try:
            import ee
            ee.Initialize(project="ageless-command-289612")
        except Exception:
            # If EE can't initialise (no ADC, no project,
            # offline), return None
            # so the caller can fall back to another provider.
            return None

        # Build a bounding box in degrees: ~111 km per
        # degree latitude, and ~111 * cos(lat) km per
        # degree longitude.
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * max(0.1,
            math.cos(math.radians(lat))))

        south = lat - dlat
        north = lat + dlat
        west = lon - dlon
        east = lon + dlon

        # Get the image collection, select DEM band,
        # mosaic the area.
        collection = ee.ImageCollection(GLO30_COLLECTION)
        dem_img = collection.select("DEM").mosaic()

        # Sample the DEM at the centre point.
        # Using region=point with scale=30 returns the
        # DEM value at that point.
        # This is the most reliable way to get a
        # single elevation reading.
        try:
            point = ee.Geometry.Point(lon, lat)
            sample = dem_img.sample(region=point,
                scale=GLO30_NATIVE_RES_M)
            val = sample.getInfo()

            # The sample returns a Feature with
            # properties.DEM
            if val and "features" in val
                and len(val["features"]) > 0:
                props = val["features"][0].get("properties", {})
                dem_value = props.get("DEM")
                if dem_value is not None:
                    # We have a valid elevation reading.
                    elevations = [float(dem_value)]
                else:
                    elevations = []
            else:
                elevations = []
        except Exception:
            # If sampling fails for any reason,
            # return None gracefully.
            return None

        if not elevations:
            return None
       
        elevations.sort()
        return {
            "min_m": _r2(elevations[0]),
            "max_m": _r2(elevations[-1]),
            "mean_m": _r2(math.fsum(elevations)
                / len(elevations)),
            "relief_m": _r2(elevations[-1]
                - elevations[0]),
            "sample_count": len(elevations),
            "point_grid": [(lat, lon)],
            # single-point sample
        }

    except Exception:  # noqa: BLE001
        # any EE failure is honest
        return None

def _sample_points(
    center_lat: float, center_lon: float,
    radius_km: float,
    point_spacing_km: float = 0.5,
):
    from packages.geo.coordinates
        import haversine_m

    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 *
        max(0.1, math.cos
        (math.radians(center_lat))))

    n_rows = max(1,
        int(math.ceil(2 *
        radius_km / (point_spacing_km * 2))))
    n_cols = max(1,
        int(math.ceil(2 *
        radius_km / (point_spacing_km * 2))))

    points: list[tuple[float, float]] = []
    for i in range(n_rows):
        lat = center_lat - dlat +
            (i / max(1, n_rows - 1))
            * (2 * dlat)
        for j in range(n_cols):
            lon = center_lon - dlon +
                (j / max(1, n_cols - 1))
            * (2 * dlon)
            d = haversine_m
                (center_lat, center_lon,
            lat, lon)
            if d <= radius_km * 1000:
                points.append((lat, lon))
    if not points:
        points.append((center_lat, center_lon))
    return points
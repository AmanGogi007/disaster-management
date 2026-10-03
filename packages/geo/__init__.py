"""Re-export the public engine API."""
from .orchestrator import analyze, AnalysisReport, VERSION  # noqa: F401
from .coordinates import LatLon, haversine_m, bbox_from_point, validate_coordinates  # noqa: F401
from .analysis.exposure import ExposureInputs, ExposureResult, ScoreWeights, compute_exposure  # noqa: F401
from .hydrology import HydrologyProvider, OSMProvider, StubProvider, get_provider  # noqa: F401
from .hydrology.features import FeatureType, WaterFeature  # noqa: F401
from .terrain.analysis import TerrainSummary, summarize, aspect_to_cardinal  # noqa: F401
from .terrain.provider import ElevationProvider, SampleProvider, StubProvider as ElevStub  # noqa: F401
from .watershed.flow import (  # noqa: F401
    d8_flow_direction, flow_accumulation, trace_downhill,
    path_distance_km, drainage_direction_cardinal,
)
from .raster.dem import DEM, AffineTransform  # noqa: F401
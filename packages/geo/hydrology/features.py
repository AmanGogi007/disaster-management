"""Hydrology feature data classes."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeatureType(str, Enum):
    RIVER = "river"
    STREAM = "stream"
    CANAL = "canal"
    LAKE = "lake"
    RESERVOIR = "reservoir"
    POND = "pond"
    WETLAND = "wetland"
    DRAIN = "drain"
    DAM = "dam"
    WEIR = "weir"


@dataclass
class WaterFeature:
    osm_id: str
    name: str | None
    type: FeatureType
    latitude: float
    longitude: float
    distance_km: float | None = None
    elevation_m: float | None = None
    geometry_kind: str = "node"  # node | way | relation
    tags: dict[str, Any] = field(default_factory=dict)
    source: str = "OpenStreetMap"
    source_dataset: str = "osm-overpass"
    confidence: str = "medium"

    def to_dict(self) -> dict:
        return {
            "osm_id": self.osm_id,
            "name": self.name,
            "type": self.type.value,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "distance_km": round(self.distance_km, 3) if self.distance_km is not None else None,
            "elevation_m": round(self.elevation_m, 2) if self.elevation_m is not None else None,
            "geometry_kind": self.geometry_kind,
            "source": self.source,
            "source_dataset": self.source_dataset,
            "confidence": self.confidence,
            "tags": {k: v for k, v in self.tags.items() if k in _ALLOWED_TAGS},
        }


_ALLOWED_TAGS = {
    "water", "waterway", "natural", "landuse", "place", "name", "name:en",
    "wetland", "reservoir_type", "intermittent", "tidal",
}
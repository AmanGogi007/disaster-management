"""Configuration loader (env-driven, no required secrets)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    elevation_provider: str
    hydrology_provider: str
    overpass_url: str
    historical_flood_provider: str
    cache_dir: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            elevation_provider=os.environ.get("ELEVATION_PROVIDER", "sample"),
            hydrology_provider=os.environ.get("HYDROLOGY_PROVIDER", "osm-geometry"),
            overpass_url=os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter"),
            historical_flood_provider=os.environ.get("HISTORICAL_FLOOD_PROVIDER", "stub"),
            cache_dir=os.environ.get("CACHE_DIR", "./data/cache"),
        )
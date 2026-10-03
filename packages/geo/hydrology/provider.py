"""Hydrology providers.

V0.1 ships an OpenStreetMap (Overpass) provider and a stub.  Both
return fully-formed ``WaterFeature`` objects so downstream code is
identical for real and offline modes.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Protocol

from ..coordinates import bbox_from_point, haversine_m
from .features import FeatureType, WaterFeature


@dataclass
class HydrologyResult:
    features: list[WaterFeature]
    source: str
    dataset: str
    retrieved_at: str | None
    license: str
    note: str = ""
    error: str | None = None


class HydrologyProvider(Protocol):
    name: str

    def get_features(self, lat: float, lon: float, radius_km: float) -> HydrologyResult: ...


class StubProvider:
    """Returns an empty result.  Used when running offline without Overpass."""

    name = "stub"

    def get_features(self, lat: float, lon: float, radius_km: float) -> HydrologyResult:
        return HydrologyResult(
            features=[],
            source="none",
            dataset="none",
            retrieved_at=None,
            license="n/a",
            note="Hydrology provider not configured.",
        )


_OSM_QUERY = """
[out:json][timeout:25];
(
  node["waterway"~"river|stream|canal|drain|weir"]({s}, {w}, {n}, {e});
  way["waterway"~"river|stream|canal|drain|weir"]({s}, {w}, {n}, {e});
  node["natural"="water"]({s}, {w}, {n}, {e});
  way["natural"="water"]({s}, {w}, {n}, {e});
  node["water"="reservoir"]({s}, {w}, {n}, {e});
  way["water"="reservoir"]({s}, {w}, {n}, {e});
  node["water"="lake"]({s}, {w}, {n}, {e});
  way["water"="lake"]({s}, {w}, {n}, {e});
  node["water"="pond"]({s}, {w}, {n}, {e});
  way["water"="pond"]({s}, {w}, {n}, {e});
  node["natural"="wetland"]({s}, {w}, {n}, {e});
  way["natural"="wetland"]({s}, {w}, {n}, {e});
  node["waterway"="dam"]({s}, {w}, {n}, {e});
  way["waterway"="dam"]({s}, {w}, {n}, {e});
);
out center tags;
"""


_OSM_QUERY_GEOMETRY = """
[out:json][timeout:60];
(
  way["waterway"~"river|stream|canal|drain"]({s}, {w}, {n}, {e});
);
out geom tags;
"""

_OSM_QUERY_NODES = """
[out:json][timeout:25];
(
  node["waterway"~"river|stream|canal|drain|weir|dam"]({s}, {w}, {n}, {e});
  node["natural"="water"]({s}, {w}, {n}, {e});
  way["natural"="water"]({s}, {w}, {n}, {e});
  node["water"="reservoir"]({s}, {w}, {n}, {e});
  way["water"="reservoir"]({s}, {w}, {n}, {e});
  node["water"="lake"]({s}, {w}, {n}, {e});
  way["water"="lake"]({s}, {w}, {n}, {e});
  node["water"="pond"]({s}, {w}, {n}, {e});
  way["water"="pond"]({s}, {w}, {n}, {e});
  node["natural"="wetland"]({s}, {w}, {n}, {e});
  way["natural"="wetland"]({s}, {w}, {n}, {e});
  way["waterway"="dam"]({s}, {w}, {n}, {e});
  way["waterway"="weir"]({s}, {w}, {n}, {e});
);
out center tags;
"""


class OSMProvider:
    """OpenStreetMap Overpass provider — centroid-based (V0.1)."""

    name = "osm"
    LICENSE = "ODbL 1.0 — © OpenStreetMap contributors"

    def __init__(self, overpass_url: str = "https://overpass-api.de/api/interpreter") -> None:
        self.overpass_url = overpass_url

    def get_features(self, lat: float, lon: float, radius_km: float) -> HydrologyResult:
        s, w, n, e = bbox_from_point(lat, lon, radius_km)
        query = _OSM_QUERY.format(s=s, w=w, n=n, e=e)
        try:
            payload = self._fetch(query)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            return HydrologyResult(
                features=[],
                source="OpenStreetMap",
                dataset="osm-overpass",
                retrieved_at=None,
                license=self.LICENSE,
                error=f"Overpass request failed: {exc}",
            )

        features = list(_parse_payload(payload, lat, lon))
        return HydrologyResult(
            features=features,
            source="OpenStreetMap",
            dataset="osm-overpass",
            retrieved_at=None,
            license=self.LICENSE,
            note=f"{len(features)} features within {radius_km} km",
        )

    def _fetch(self, query: str) -> dict:
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request(
            self.overpass_url,
            data=data,
            headers={"User-Agent": "location-hazard-engine/0.2 (research)"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — intended public API
            body = resp.read().decode("utf-8")
        return json.loads(body)


class OSMGeometryProvider:
    """OSM provider that fetches *full way geometry* — required for V0.2
    network construction.
    """

    name = "osm-geometry"
    LICENSE = "ODbL 1.0 — © OpenStreetMap contributors"

    def __init__(self, overpass_url: str = "https://overpass-api.de/api/interpreter") -> None:
        self.overpass_url = overpass_url

    def get_features(self, lat: float, lon: float, radius_km: float) -> HydrologyResult:
        s, w, n, e = bbox_from_point(lat, lon, radius_km)
        try:
            ways_payload = self._fetch(_OSM_QUERY_GEOMETRY.format(s=s, w=w, n=n, e=e))
            nodes_payload = self._fetch(_OSM_QUERY_NODES.format(s=s, w=w, n=n, e=e))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            return HydrologyResult(
                features=[],
                source="OpenStreetMap",
                dataset="osm-overpass",
                retrieved_at=None,
                license=self.LICENSE,
                error=f"Overpass request failed: {exc}",
            )

        features: list[WaterFeature] = []
        for el in ways_payload.get("elements", []):
            geom = el.get("geometry") or []
            pts = [(float(g["lat"]), float(g["lon"])) for g in geom if "lat" in g and "lon" in g]
            if len(pts) < 2:
                continue
            tags = el.get("tags", {}) or {}
            ftype = _classify(tags)
            if ftype is None:
                continue
            tags["__geometry__"] = pts
            mid = pts[len(pts) // 2]
            dist = haversine_m(lat, lon, mid[0], mid[1])
            features.append(WaterFeature(
                osm_id=str(el.get("id", "")),
                name=tags.get("name") or tags.get("name:en"),
                type=ftype,
                latitude=mid[0], longitude=mid[1],
                distance_km=dist / 1000.0,
                geometry_kind="way",
                tags=dict(tags),
                confidence="medium",
            ))
        features.extend(_parse_payload(nodes_payload, lat, lon))
        return HydrologyResult(
            features=features,
            source="OpenStreetMap",
            dataset="osm-overpass",
            retrieved_at=None,
            license=self.LICENSE,
            note=f"{len(features)} features within {radius_km} km (geometry: {sum(1 for f in features if (f.tags or {}).get('__geometry__'))})",
        )

    def _fetch(self, query: str) -> dict:
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request(
            self.overpass_url,
            data=data,
            headers={"User-Agent": "location-hazard-engine/0.2 (research)"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — intended public API
            body = resp.read().decode("utf-8")
        return json.loads(body)


def _parse_payload(payload: dict, lat: float, lon: float) -> Iterable[WaterFeature]:
    for el in payload.get("elements", []):
        geom_kind = el.get("type", "node")
        tags = el.get("tags", {}) or {}

        ftype = _classify(tags)
        if ftype is None:
            continue

        if geom_kind == "node":
            p_lat = el.get("lat")
            p_lon = el.get("lon")
        elif geom_kind == "way":
            center = el.get("center") or {}
            p_lat = center.get("lat")
            p_lon = center.get("lon")
        elif geom_kind == "relation":
            center = el.get("center") or {}
            p_lat = center.get("lat")
            p_lon = center.get("lon")
        else:
            continue
        if p_lat is None or p_lon is None:
            continue

        dist_m = haversine_m(lat, lon, p_lat, p_lon)
        yield WaterFeature(
            osm_id=str(el.get("id", "")),
            name=tags.get("name") or tags.get("name:en"),
            type=ftype,
            latitude=float(p_lat),
            longitude=float(p_lon),
            distance_km=dist_m / 1000.0,
            geometry_kind=geom_kind,
            tags=dict(tags),
            confidence=_confidence_for(geom_kind, ftype),
        )


def _classify(tags: dict) -> FeatureType | None:
    wway = tags.get("waterway")
    water = tags.get("water")
    natural = tags.get("natural")

    if wway == "river":
        return FeatureType.RIVER
    if wway in ("stream", "brook", "creek"):
        return FeatureType.STREAM
    if wway == "canal":
        return FeatureType.CANAL
    if wway == "drain":
        return FeatureType.DRAIN
    if wway == "weir":
        return FeatureType.WEIR
    if wway == "dam":
        return FeatureType.DAM
    if water == "reservoir":
        return FeatureType.RESERVOIR
    if water == "lake":
        return FeatureType.LAKE
    if water == "pond":
        return FeatureType.POND
    if natural == "wetland":
        return FeatureType.WETLAND
    if natural == "water":
        return FeatureType.LAKE
    return None


def _confidence_for(geom_kind: str, ftype: FeatureType) -> str:
    if ftype == FeatureType.DAM and geom_kind in ("way", "relation"):
        return "high"
    if geom_kind == "relation":
        return "high"
    if geom_kind == "way":
        return "medium"
    return "low"


def get_provider(name: str, overpass_url: str | None = None) -> HydrologyProvider:
    name = (name or "osm").lower()
    if name == "osm":
        return OSMProvider(overpass_url=overpass_url or "https://overpass-api.de/api/interpreter")
    if name == "osm-geometry":
        return OSMGeometryProvider(overpass_url=overpass_url or "https://overpass-api.de/api/interpreter")
    if name == "stub":
        return StubProvider()
    raise ValueError(f"unknown hydrology provider: {name}")
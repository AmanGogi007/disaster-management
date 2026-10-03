"""Top-level analysis orchestrator — V0.1 + V0.2 (network layer)."""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from .analysis.exposure import ExposureInputs, ExposureResult, ScoreWeights, compute_exposure
from .coordinates import validate_coordinates
from .hydrology import HydrologyProvider, WaterFeature, get_provider as get_hydro_provider
from .hydrology.features import FeatureType
from .network.builder import build_network as build_network_graph
from .network.graph import (
    HydrologicalNetwork, NetworkEdge, NetworkFeatureLink,
    REL_DISCONNECTED, REL_DOWNSTREAM, REL_PLOT, REL_TRIBUTARY, REL_UNKNOWN,
    REL_UPSTREAM,
)
from .raster.dem import DEM
from .terrain.analysis import TerrainSummary, summarize
from .terrain.provider import ElevationProvider, get_provider as get_elev_provider
from .watershed.flow import (
    d8_flow_direction,
    flow_accumulation,
    path_distance_km,
    trace_downhill,
    drainage_direction_cardinal,
)


@dataclass
class AnalysisReport:
    location: dict
    terrain: dict
    hydrology: dict
    watershed: dict
    historical_floods: dict
    risk: dict
    data_provenance: list[dict]
    notes: list[str]
    version: str
    network: dict | None = None
    upstream: dict | None = None
    downstream: dict | None = None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "location": self.location,
            "terrain": self.terrain,
            "hydrology": self.hydrology,
            "watershed": self.watershed,
            "historical_floods": self.historical_floods,
            "risk": self.risk,
            "network": self.network,
            "upstream": self.upstream,
            "downstream": self.downstream,
            "data_provenance": self.data_provenance,
            "notes": self.notes,
        }


VERSION = "0.2.0"


def analyze(
    lat: float,
    lon: float,
    radius_km: float = 50.0,
    elevation_provider: ElevationProvider | None = None,
    hydrology_provider: HydrologyProvider | None = None,
    historical_flood_count: int = 0,
    historical_flood_source: str = "none",
    store: "AnalysisStore | None" = None,
) -> AnalysisReport:
    validate_coordinates(lat, lon)
    if radius_km <= 0 or radius_km > 200:
        raise ValueError("radius_km must be in (0, 200]")

    elevation_provider = elevation_provider or get_elev_provider(os.environ.get("ELEVATION_PROVIDER", "sample"))
    hydrology_provider = hydrology_provider or get_hydro_provider(os.environ.get("HYDROLOGY_PROVIDER", "osm-geometry"))

    provenance: list[dict] = []
    notes: list[str] = []

    # --- terrain --------------------------------------------------------------
    elev_result = elevation_provider.get_dem(lat, lon, radius_km)
    provenance.append({
        "source": elev_result.source,
        "dataset": elev_result.dataset,
        "resolution_m": elev_result.resolution_m,
        "license": elev_result.license,
        "note": elev_result.note,
    })
    if elev_result.dem is None:
        report = AnalysisReport(
            location={"latitude": lat, "longitude": lon, "radius_km": radius_km},
            terrain={"available": False},
            hydrology={"available": False},
            watershed={"available": False},
            historical_floods={"available": False},
            risk={
                "score": None, "category": "unknown", "confidence": "low",
                "contributing_factors": [],
                "limitations": ["DEM unavailable; risk score not produced."],
            },
            data_provenance=provenance,
            notes=["Elevation provider returned no data; no analysis produced."],
            version=VERSION,
        )
        if store is not None:
            store.put(report)
        return report

    dem = elev_result.dem
    terrain_summary: TerrainSummary = summarize(dem, lat, lon)

    # --- hydrology ------------------------------------------------------------
    hydro_result = hydrology_provider.get_features(lat, lon, radius_km)
    if hydro_result.error:
        notes.append(f"Hydrology provider error: {hydro_result.error}")
    provenance.append({
        "source": hydro_result.source,
        "dataset": hydro_result.dataset,
        "license": hydro_result.license,
        "note": hydro_result.note,
        "error": hydro_result.error,
    })
    features = hydro_result.features
    features.sort(key=lambda f: (f.distance_km or 1e9))

    nearest_river = _first(features, FeatureType.RIVER)
    nearest_reservoir = _first(features, FeatureType.RESERVOIR)
    nearest_dam = _first(features, FeatureType.DAM)

    # --- watershed / flow -----------------------------------------------------
    fdir = d8_flow_direction(dem)
    facc = flow_accumulation(fdir)
    t = dem.transform
    cell_row = t.row_at_lat(lat)
    cell_col = t.col_at_lon(lon)
    if 0 <= cell_row < dem.rows and 0 <= cell_col < dem.cols:
        facc_plot = int(facc[cell_row, cell_col])
    else:
        facc_plot = None
    flow_path = trace_downhill(dem, fdir, lat, lon)
    flow_distance_km = path_distance_km(flow_path)

    # --- relative water elevation (sampled from DEM) --------------------------
    nearest_water_elev: float | None = None
    elev_diff_to_water: float | None = None
    if nearest_river is not None:
        sampled = dem.value_at(nearest_river.latitude, nearest_river.longitude)
        if sampled is not None:
            nearest_water_elev = sampled
            if terrain_summary.point_elevation_m is not None:
                elev_diff_to_water = terrain_summary.point_elevation_m - sampled

    # --- exposure score -------------------------------------------------------
    connection = _infer_connection(nearest_dam, nearest_river, nearest_reservoir)
    weights = _load_weights()

    inputs = ExposureInputs(
        nearest_river_km=nearest_river.distance_km if nearest_river else None,
        nearest_reservoir_km=nearest_reservoir.distance_km if nearest_reservoir else None,
        nearest_dam_km=nearest_dam.distance_km if nearest_dam else None,
        plot_elevation_m=terrain_summary.point_elevation_m,
        nearest_water_elevation_m=nearest_water_elev,
        slope_deg=terrain_summary.slope_deg,
        flow_accumulation_at_plot=facc_plot,
        historical_flood_events=historical_flood_count,
        hydraulic_connection=connection,
    )
    exposure: ExposureResult = compute_exposure(inputs, weights)

    # --- V0.2 hydrological network -------------------------------------------
    network = build_network_graph(
        features=features,
        dem=dem,
        plot_lat=lat, plot_lon=lon,
    )
    net_summary = _summarise_network(network, lat, lon)
    upstream_summary = _upstream_summary(network)
    downstream_summary = _downstream_summary(network)

    report = AnalysisReport(
        location={"latitude": lat, "longitude": lon, "radius_km": radius_km},
        terrain={
            "available": True,
            **terrain_summary.to_dict(),
            "relative_to_nearest_water_m": (
                round(elev_diff_to_water, 2) if elev_diff_to_water is not None else None
            ),
        },
        hydrology={
            "available": True,
            "feature_count": len(features),
            "nearest_river": _feature_dict(nearest_river, dem),
            "nearest_reservoir": _feature_dict(nearest_reservoir, dem),
            "nearest_dam": _feature_dict(nearest_dam, dem),
            "features": [_feature_dict(f, dem) for f in features[:100]],
        },
        watershed={
            "available": True,
            "flow_accumulation_cells": facc_plot,
            "downstream_trace_km": round(flow_distance_km, 3),
            "downstream_direction": drainage_direction_cardinal(flow_path),
            "downstream_trace_sample": [
                {"lat": round(p[0], 5), "lon": round(p[1], 5)}
                for p in flow_path[:: max(1, len(flow_path) // 20)][:21]
            ],
        },
        historical_floods={
            "available": historical_flood_count > 0 or historical_flood_source != "none",
            "events_within_radius": historical_flood_count,
            "source": historical_flood_source,
            "note": "Real historical-flood datasets (NRSC/Bhuvan, CWC) plug in here.",
        },
        risk=exposure.to_dict(),
        network=net_summary,
        upstream=upstream_summary,
        downstream=downstream_summary,
        data_provenance=provenance,
        notes=notes + [
            "V0.2 — terrain + hydrology + hydrological network.",
            "Network edges inferred from DEM-sampled endpoint elevations.",
            "No hydraulic simulation, no dam-break model, no arrival time.",
        ],
        version=VERSION,
    )
    if store is not None:
        store.put(report)
    return report


def _summarise_network(network: HydrologicalNetwork, plot_lat: float,
                       plot_lon: float) -> dict:
    by_rel: dict[str, int] = defaultdict(int)
    dams = []
    reservoirs = []
    for fl in network.feature_links:
        by_rel[fl.relationship] += 1
        if fl.feature_type in ("dam", "weir"):
            dams.append({
                "id": fl.feature_id,
                "name": fl.name,
                "latitude": round(fl.latitude, 5),
                "longitude": round(fl.longitude, 5),
                "relationship": fl.relationship,
                "distance_km": fl.distance_km,
                "elevation_m": fl.elevation_m,
                "confidence": fl.confidence,
                "notes": fl.notes,
                "data_source": fl.data_source,
            })
        elif fl.feature_type == "reservoir":
            reservoirs.append({
                "id": fl.feature_id,
                "name": fl.name,
                "latitude": round(fl.latitude, 5),
                "longitude": round(fl.longitude, 5),
                "relationship": fl.relationship,
                "distance_km": fl.distance_km,
                "confidence": fl.confidence,
                "notes": fl.notes,
                "data_source": fl.data_source,
            })
    return {
        "available": True,
        "node_count": len(network.nodes),
        "edge_count": len(network.edges),
        "plot_attachment_node_id": network.plot_attachment_node_id,
        "watershed_label": network.watershed_label,
        "methodology": network.methodology,
        "feature_relationship_counts": dict(by_rel),
        "dams": dams,
        "reservoirs": reservoirs,
        "edges_sample": [e.to_dict() for e in network.edges[:50]],
    }


def _upstream_summary(network: HydrologicalNetwork) -> dict:
    if network.plot_attachment_node_id is None:
        return {
            "available": False,
            "reason": "Plot could not be attached to a river network node.",
        }
    trace = network.upstream_trace(network.plot_attachment_node_id)
    up_nodes = set(network.upstream_of(network.plot_attachment_node_id))
    return {
        "available": True,
        "upstream_node_count": len(up_nodes),
        "main_stem": trace["main_stem"],
        "tributaries": trace["tributaries"],
        "upstream_dams": trace["upstream_dams"],
        "upstream_reservoirs": trace["upstream_reservoirs"],
        "upstream_rivers": trace["upstream_rivers"],
        "disconnected_features": trace["disconnected_features"],
        # Back-compat key consumed by the web UI (geographic-only features).
        "disconnected_dams_within_radius": trace["disconnected_features"],
        "note": ("Upstream is determined by directed graph reachability from "
                 "the plot attachment node, NOT geographic proximity."),
    }


def _downstream_summary(network: HydrologicalNetwork) -> dict:
    if network.plot_attachment_node_id is None:
        return {
            "available": False,
            "reason": "Plot could not be attached to a river network node.",
        }
    trace = network.downstream_trace(network.plot_attachment_node_id)
    down_nodes = set(network.downstream_of(network.plot_attachment_node_id))
    down_links = [fl for fl in network.feature_links
                  if fl.relationship == REL_DOWNSTREAM
                  and fl.feature_type in ("dam", "weir", "reservoir")]
    return {
        "available": True,
        "downstream_node_count": len(down_nodes),
        "trace_steps": trace,
        "downstream_dams": [fl.to_dict() for fl in down_links
                            if fl.feature_type in ("dam", "weir")],
        "downstream_reservoirs": [fl.to_dict() for fl in down_links
                                  if fl.feature_type == "reservoir"],
        "note": "Downstream is determined by directed graph reachability.",
    }


def _first(features: list[WaterFeature], ftype: FeatureType) -> WaterFeature | None:
    for f in features:
        if f.type == ftype:
            return f
    return None


def _feature_dict(f: WaterFeature | None, dem: DEM) -> dict | None:
    if f is None:
        return None
    d = f.to_dict()
    sampled = dem.value_at(f.latitude, f.longitude)
    d["sampled_dem_elevation_m"] = round(sampled, 2) if sampled is not None else None
    return d


def _infer_connection(dam, river, reservoir) -> str:
    """V0.1 heuristic — replaced by upstream graph analysis in V0.2."""
    if dam is None and reservoir is None and river is None:
        return "none"
    if dam is None and reservoir is None:
        return "unlikely"
    if (dam is not None and (dam.distance_km or 1e9) < 60) or (
        reservoir is not None and (reservoir.distance_km or 1e9) < 30
    ):
        return "possible"
    return "unknown"


def _load_weights() -> ScoreWeights:
    return ScoreWeights(
        distance=float(os.environ.get("FLOOD_DISTANCE_WEIGHT", "0.25")),
        elevation=float(os.environ.get("FLOOD_ELEVATION_WEIGHT", "0.25")),
        connectivity=float(os.environ.get("FLOOD_CONNECTIVITY_WEIGHT", "0.20")),
        historical=float(os.environ.get("FLOOD_HISTORICAL_WEIGHT", "0.15")),
        flow_accumulation=float(os.environ.get("FLOOD_FLOW_ACCUMULATION_WEIGHT", "0.15")),
    )


class AnalysisStore:
    """In-memory store mapping analysis_id -> AnalysisReport.

    V0.2 keeps this single-process (good enough for local development and
    the API contract).  Real persistence belongs to V0.3+.
    """

    def __init__(self) -> None:
        self._items: dict[str, AnalysisReport] = {}
        self._counter = 0

    def put(self, report: AnalysisReport) -> str:
        self._counter += 1
        aid = f"an_{self._counter:06d}_{int(report.location['latitude']*1000)}_{int(report.location['longitude']*1000)}"
        self._items[aid] = report
        return aid

    def get(self, analysis_id: str) -> AnalysisReport | None:
        return self._items.get(analysis_id)

    def ids(self) -> list[str]:
        return list(self._items.keys())
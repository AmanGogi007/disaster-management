"""Phase 1b — local hydraulic topology (design §J.1 flow).

Organises the gathered evidence into a *descriptive* local topology around the
plot: resolved channel, local channels/drains, potential barriers, crossings,
flood-control structures, and the DEM-derived flow direction at the plot reach.

Deliberate non-claims (per §J.1 / user directive):

* OSM presence of a feature is NOT proof of hydraulic connectivity.
* Feature geometry is NOT interpreted into blockage/conveyance — no culvert
  opening sizes, no surcharge, no flow cross-sections.
* The topology output does NOT set connectivity; that is solely the job of
  ``assess_connectivity`` (which stays UNRESOLVED on the flat 30 m reach).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LocalHydraulicTopology:
    plot_lat: float
    plot_lon: float
    channel: dict = field(default_factory=dict)
    local_channels: list[dict] = field(default_factory=list)
    barriers: list[dict] = field(default_factory=list)
    crossings: list[dict] = field(default_factory=list)
    flood_structures: list[dict] = field(default_factory=list)
    plot_cell: dict = field(default_factory=dict)
    reach_direction_status: str = "unresolved"
    flow_direction_note: str = ""
    connectivity_statement: str = (
        "Topology is descriptive; hydraulic connectivity is decided only by "
        "assess_connectivity (UNRESOLVED at 30 m DEM resolution for a flat "
        "reach)."
    )
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plot_lat": self.plot_lat,
            "plot_lon": self.plot_lon,
            "channel": self.channel,
            "local_channels": self.local_channels,
            "barriers": self.barriers,
            "crossings": self.crossings,
            "flood_structures": self.flood_structures,
            "plot_cell": self.plot_cell,
            "reach_direction_status": self.reach_direction_status,
            "flow_direction_note": self.flow_direction_note,
            "connectivity_statement": self.connectivity_statement,
            "caveats": self.caveats,
        }


def _waterway_nodes(rec: dict) -> set[str]:
    return set(rec.get("nodes") or [])


def _geometric_colocation(rec: dict, waterway_points: list[tuple[float, float]],
                          tolerance_m: float = 100.0) -> bool:
    """True if any point of ``rec`` lies within tolerance of a waterway point.

    Complements node-id sharing: OSM frequently maps a bridge and the river it
    crosses with separate node ids, so geometric overlap is the only honest way
    to detect the physical crossing.
    """
    pts = rec.get("points") or rec.get("endpoints") or []
    if not pts or not waterway_points:
        return False
    from ..coordinates import haversine_m
    for a in pts:
        for b in waterway_points:
            if haversine_m(a[0], a[1], b[0], b[1]) <= tolerance_m:
                return True
    return False


def _barrier_kind(tags: dict) -> str:
    if tags.get("embankment") == "yes":
        return "embankment"
    if tags.get("cutting") == "yes":
        return "cutting"
    if tags.get("barrier"):
        return f"barrier:{tags['barrier']}"
    if tags.get("railway"):
        return f"railway:{tags['railway']}"
    if tags.get("highway"):
        return f"highway:{tags['highway']}"
    return "unspecified"


def _dem_direction_note(dem, proc, lat: float, lon: float) -> tuple[str, dict, str]:
    """Classify the plot reach direction from the preprocessed D8 grid.

    Returns (status, plot_cell_dict, note).  Raises nothing: any missing DEM/
    proc input yields 'unresolved' honestly.
    """
    if dem is None or proc is None or proc.flow_direction is None:
        return ("unresolved",
                dict(row=None, col=None, elevation_m=None, fdir=None, is_flat=None),
                "No DEM/flow-direction grid available; reach direction unresolved.")
    try:
        t = dem.transform
        row = t.row_at_lat(lat)
        col = t.col_at_lon(lon)
    except Exception:
        return ("unresolved",
                dict(row=None, col=None, elevation_m=None, fdir=None, is_flat=None),
                "Could not map the plot into the DEM grid; direction unresolved.")

    valid = {1, 2, 4, 8, 16, 32, 64, 128}
    d = None
    if 0 <= row < proc.flow_direction.shape[0] and 0 <= col < proc.flow_direction.shape[1]:
        d = int(proc.flow_direction[row, col])

    elev = None
    try:
        import numpy as np
        if 0 <= row < dem.elevation.shape[0] and 0 <= col < dem.elevation.shape[1]:
            z = dem.elevation[row, col]
            if np.isfinite(z):
                elev = float(z)
    except Exception:
        elev = None

    is_flat = d is not None and d not in valid
    if d in valid:
        return ("resolvable",
                dict(row=row, col=col, elevation_m=elev, fdir=d, is_flat=False),
                f"D8 flow direction {d} is resolvable at the plot cell.")
    return ("unresolved",
            dict(row=row, col=col, elevation_m=elev, fdir=d, is_flat=is_flat),
            "D8 at the plot cell is flat/sink (sentinel) — no resolvable "
            "downhill direction at 30 m DEM resolution.")


def build_local_topology(
    gather_result,
    dem=None,
    proc=None,
    *,
    plot_lat: float,
    plot_lon: float,
) -> LocalHydraulicTopology:
    """Build the descriptive local topology from gathered evidence (+optional
    DEM/proc for the reach-direction determination).
    """
    raw = gather_result.raw_items if gather_result else {}
    rec = gather_result.channel_reconciliation if gather_result else None
    topo = LocalHydraulicTopology(plot_lat=plot_lat, plot_lon=plot_lon)

    # 1. Resolved channel.
    if rec is not None:
        topo.channel = {
            "resolved": rec.resolved,
            "main_stem_ids": rec.main_stem_ids,
            "tributary_ids": rec.tributary_ids,
            "unconnected_ids": rec.unconnected_ids,
            "min_plot_distance_km": rec.min_plot_distance_km,
            "confidence": rec.confidence,
            "note": rec.note,
        }
    else:
        topo.channel = {"resolved": None, "note": "No channel reconciliation."}

    # 2. Local channels / drains.
    for item in raw.get("channels_drains", []):
        tags = item.get("tags") or {}
        topo.local_channels.append({
            "osm_id": item.get("osm_id"),
            "kind": tags.get("waterway"),
            "name": item.get("name"),
            "min_distance_km": item.get("min_distance_km") or item.get("distance_km"),
            "length_km": item.get("length_km"),
        })

    # 3. Potential barriers (roads/railways/embankments).
    for item in raw.get("embankments_road_rail", []):
        tags = item.get("tags") or {}
        topo.barriers.append({
            "osm_id": item.get("osm_id"),
            "kind": _barrier_kind(tags),
            "name": item.get("name"),
            "min_distance_km": item.get("min_distance_km") or item.get("distance_km"),
            "length_km": item.get("length_km"),
            "note": "May act as a barrier only where no hydraulic opening "
                    "(culvert/bridge) exists; opening data not in OSM.",
        })
    topo.barriers.sort(key=lambda b: (b.get("min_distance_km") or 999.0))

    # 4. Crossings: bridge/culvert ways that (a) share a waterway node id, or
    #    (b) lie geometrically on the waterway (separate node ids in OSM).
    waterway_nodes: set[str] = set()
    waterway_points: list[tuple[float, float]] = []
    for kind in ("channel_centerline", "channels_drains"):
        for item in raw.get(kind, []):
            waterway_nodes |= _waterway_nodes(item)
            waterway_points.extend(item.get("points") or item.get("endpoints") or [])
    for item in raw.get("bridges_culverts", []):
        tags = item.get("tags") or {}
        kind = "bridge" if tags.get("bridge") == "yes" else (
            "culvert" if tags.get("culvert") == "yes" else "tunnel/crossing")
        shared = _waterway_nodes(item) & waterway_nodes
        geo_colocated = _geometric_colocation(item, waterway_points)
        topo.crossings.append({
            "osm_id": item.get("osm_id"),
            "kind": kind,
            "name": item.get("name"),
            "min_distance_km": item.get("min_distance_km") or item.get("distance_km"),
            "on_waterway": bool(shared) or geo_colocated,
            "shared_node_count": len(shared),
            "geometrically_colocated": geo_colocated,
        })

    # 5. Flood-control structures.
    for item in raw.get("flood_control", []):
        tags = item.get("tags") or {}
        topo.flood_structures.append({
            "osm_id": item.get("osm_id"),
            "kind": tags.get("waterway") or tags.get("landuse") or "structure",
            "name": item.get("name"),
            "min_distance_km": item.get("min_distance_km") or item.get("distance_km"),
        })

    # 6. Reach direction from the DEM.
    if proc is not None and getattr(proc, "flow_direction", None) is not None:
        status, cell, note = _dem_direction_note(dem, proc, plot_lat, plot_lon)
        topo.reach_direction_status = status
        topo.plot_cell = cell
        topo.flow_direction_note = note
    else:
        topo.reach_direction_status = "unresolved"
        topo.plot_cell = {}
        topo.flow_direction_note = "No DEM/proc supplied; direction not assessed."

    topo.caveats = [
        "OSM feature presence does NOT prove hydraulic connectivity.",
        "No culvert/bridge opening sizes: crossings are locations only, not "
        "conveyance estimates.",
        "A crossing marked on_waterway means it shares a waterway node id or "
        "lies within 100 m of a waterway geometry (OSM maps them with separate "
        "node ids) — it is a location flag, not an opening-size estimate.",
        "No vertical (elevation) relationship between OSM objects and the DEM; "
        "absolute heights are not comparable across datums.",
        f"Reach direction at the plot: {topo.reach_direction_status} — "
        f"{topo.flow_direction_note}",
    ]
    return topo
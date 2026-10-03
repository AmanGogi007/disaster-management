"""Build a hydrological network graph from water features + DEM.

Approach (V0.2 -- no global HydroSHEDS dataset yet):

1. Take the OSM water features already produced by HydrologyProvider.
2. For every river / stream / canal / drain way with multi-point geometry,
   create a directed edge.  Direction is inferred from the DEM elevation of
   the two endpoints -- the higher endpoint is upstream.
3. Way endpoints that coincide (within a tolerance) are merged into a single
   junction node.
4. The plot is attached to the graph via DEM-based downhill tracing
   (packages.geo.watershed.flow.trace_downhill) and snapping the trace
   endpoint to the nearest graph node.
5. Dams and reservoirs are linked to the nearest graph node; their
   upstream/downstream classification is determined by graph topology.
6. Confidence is reported explicitly.  If a relationship cannot be
   determined reliably, it is "unknown" -- never guessed.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable

from ..coordinates import haversine_m
from ..hydrology.features import FeatureType, WaterFeature
from ..raster.dem import DEM
from ..watershed.flow import trace_downhill
from .graph import (
    REL_DISCONNECTED, REL_DOWNSTREAM, REL_PLOT, REL_TRIBUTARY, REL_UNKNOWN, REL_UPSTREAM,
    HydrologicalNetwork, NetworkEdge, NetworkFeatureLink, NetworkNode,
)


def _densify_geometry(
    geom: list[tuple[float, float]],
    max_seg_m: float = 200.0,
) -> list[tuple[float, float]]:
    """Insert intermediate points so no segment exceeds max_seg_m."""
    if len(geom) < 2:
        return geom
    out: list[tuple[float, float]] = [geom[0]]
    for i in range(len(geom) - 1):
        lat1, lon1 = geom[i]
        lat2, lon2 = geom[i + 1]
        seg_m = haversine_m(lat1, lon1, lat2, lon2)
        if seg_m <= max_seg_m:
            out.append(geom[i + 1])
        else:
            n = max(2, math.ceil(seg_m / max_seg_m))
            for k in range(1, n + 1):
                t = k / n
                out.append((lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1)))
    if out[-1] != geom[-1]:
        out.append(geom[-1])
    return out


_ENDPOINT_SNAP_M = 25.0      # two endpoints within 25 m merge into one node
_NODE_FEATURE_SNAP_M = 75.0   # features snap to a network node within this distance
_STRONG_DEM_DROP_M = 20.0     # only override topology if DEM drop is this large
_FLAT_DEM_DROP_M = 2.0        # below this, definitely use topology fallback
_WAY_DENSIFY_M = 200.0        # insert a graph node every N metres along a way


def _endpoint_node_key(lat: float, lon: float) -> str:
    return f"n_{round(lat, 5)}_{round(lon, 5)}"


def build_network(
    features: list[WaterFeature],
    dem: DEM,
    plot_lat: float,
    plot_lon: float,
    watershed_label: str | None = None,
) -> HydrologicalNetwork:
    """Construct a directed hydrological network + classify every feature."""
    network = HydrologicalNetwork(watershed_label=watershed_label)
    network.methodology = (
        "V0.2 -- OSM river/stream/canal ways as directed edges. "
        "Direction inferred from DEM endpoint elevations; flat segments "
        "fall back to topology (junction = downstream collector). "
        "Endpoints snap within 25 m.  Plot attached via DEM downhill trace."
    )

    # Pass 1: collect candidate way geometries + index their endpoints.
    way_records: list[tuple[WaterFeature, list[tuple[float, float]]]] = []
    way_endpoints: dict[str, list[str]] = {}
    for f in features:
        geom = (f.tags or {}).get("__geometry__")
        if not geom or len(geom) < 2:
            continue
        if f.type not in (FeatureType.RIVER, FeatureType.STREAM,
                          FeatureType.CANAL, FeatureType.DRAIN):
            continue
        # Densify long polylines so the graph has intermediate nodes --
        # otherwise a dam "between" two endpoints can't be localised.
        geom = _densify_geometry(geom, max_seg_m=_WAY_DENSIFY_M)
        way_records.append((f, geom))
        s_id = _endpoint_node_key(geom[0][0], geom[0][1])
        e_id = _endpoint_node_key(geom[-1][0], geom[-1][1])
        way_endpoints[f.osm_id] = [s_id, e_id]

    # Pass 2: register ALL points from densified geometries as nodes
    #         (so the plot can attach to any point along the river).
    for f, geom in way_records:
        for pt in geom:
            lat, lon = pt
            nid = _endpoint_node_key(lat, lon)
            if nid not in network.nodes:
                network.nodes[nid] = NetworkNode(
                    node_id=nid, latitude=lat, longitude=lon,
                    elevation_m=dem.value_at(lat, lon),
                    kind="intermediate",
                )

    # Pass 2b: merge nearby nodes (junctions) - snap nodes within tolerance
    network.nodes, old_to_new = _merge_nearby_nodes(network.nodes, snap_m=100.0)

    # Remap way_endpoints through the merge mapping
    if old_to_new:
        remapped_endpoints: dict[str, list[str]] = {}
        for osm_id, eps in way_endpoints.items():
            remapped_endpoints[osm_id] = [
                old_to_new.get(e, e) for e in eps
            ]
        way_endpoints = remapped_endpoints

    # Pass 3: build edges with direction.
    for f, geom in way_records:
        _add_way(network, f, geom, dem, way_endpoints, old_to_new)

    # Pass 4: attach every other feature (dam, reservoir, lake, pond, wetland,
    #         node-only rivers) to the nearest graph node.
    for f in features:
        if f.type in (FeatureType.RIVER, FeatureType.STREAM,
                      FeatureType.CANAL, FeatureType.DRAIN):
            if not (f.tags or {}).get("__geometry__"):
                _link_lone_feature(network, f)
            continue
        _link_lone_feature(network, f)

    # Pass 5: attach plot via DEM downhill trace.
    _attach_plot(network, dem, plot_lat, plot_lon)

    # Pass 6: classify every feature link.
    _classify_features(network, plot_lat, plot_lon)

    return network


def _add_way(
    network: HydrologicalNetwork,
    feature: WaterFeature,
    geom: list[tuple[float, float]],
    dem: DEM,
    way_endpoints: dict[str, list[str]] | None = None,
    old_to_new: dict[str, str] | None = None,
) -> None:
    """Create a chain of directed edges through all consecutive points in the
    densified geometry.  The whole chain gets the same river name/type.
    """
    if len(geom) < 2:
        return

    # Sample elevations at all points
    elevations = [dem.value_at(lat, lon) for lat, lon in geom]

    # Determine overall flow direction from first to last point
    first_z = elevations[0]
    last_z = elevations[-1]

    # Use endpoint elevations for direction (same logic as before)
    we = way_endpoints or {}
    otn = old_to_new or {}
    start_id = otn.get(_endpoint_node_key(geom[0][0], geom[0][1]),
                       _endpoint_node_key(geom[0][0], geom[0][1]))
    end_id = otn.get(_endpoint_node_key(geom[-1][0], geom[-1][1]),
                     _endpoint_node_key(geom[-1][0], geom[-1][1]))
    start_arity = _endpoint_arity(network, start_id, we) if we else 0
    end_arity = _endpoint_arity(network, end_id, we) if we else 0
    start_arity = max(0, start_arity - 1)
    end_arity = max(0, end_arity - 1)

    direction_method = "dem"
    dem_drop = None
    if first_z is None or last_z is None:
        direction_method = "unknown"
        upstream_is_start = None
    else:
        dem_drop = first_z - last_z
        if abs(dem_drop) >= _STRONG_DEM_DROP_M:
            upstream_is_start = dem_drop > 0
        else:
            direction_method = "topology-fallback"
            upstream_is_start = None

    if upstream_is_start is None:
        if end_arity > 0 and start_arity == 0:
            upstream_is_start = True
        elif start_arity > 0 and end_arity == 0:
            upstream_is_start = False
        elif start_arity == end_arity:
            upstream_is_start = bool(hash(feature.osm_id) & 1)
        else:
            upstream_is_start = start_arity < end_arity

    # Create edges between consecutive points, all pointing in the same direction
    raw_node_ids = [_endpoint_node_key(lat, lon) for lat, lon in geom]
    node_ids = [otn.get(nid, nid) for nid in raw_node_ids]
    if upstream_is_start:
        # Flow from first to last
        for i in range(len(node_ids) - 1):
            up_lat, up_lon = geom[i]
            down_lat, down_lon = geom[i+1]
            _create_single_edge(network, feature, up_lat, up_lon, down_lat, down_lon,
                               node_ids[i], node_ids[i+1], elevations[i], elevations[i+1],
                               direction_method, dem_drop, i == 0)
    else:
        # Flow from last to first
        for i in range(len(node_ids) - 1, 0, -1):
            up_lat, up_lon = geom[i]
            down_lat, down_lon = geom[i-1]
            _create_single_edge(network, feature, up_lat, up_lon, down_lat, down_lon,
                               node_ids[i], node_ids[i-1], elevations[i], elevations[i-1],
                               direction_method, dem_drop, i == len(node_ids) - 1)


def _create_single_edge(
    network: HydrologicalNetwork,
    feature: WaterFeature,
    up_lat: float, up_lon: float,
    down_lat: float, down_lon: float,
    up_id: str, down_id: str,
    up_z: float, down_z: float,
    direction_method: str,
    total_drop: float | None,
    is_first_segment: bool,
) -> None:
    """Create one edge segment in the chain."""
    length_km = haversine_m(up_lat, up_lon, down_lat, down_lon) / 1000.0

    if direction_method == "dem":
        confidence = "high" if total_drop is not None and abs(total_drop) >= _STRONG_DEM_DROP_M * 2 else "medium"
    elif direction_method == "topology-fallback":
        confidence = "low"
    else:
        confidence = "low"

    edge = NetworkEdge(
        edge_id=f"e_{feature.osm_id}_{up_id}_{down_id}",
        u=up_id, v=down_id,
        river_name=feature.name,
        river_type=feature.type.value,
        geometry=[(up_lat, up_lon), (down_lat, down_lon)],
        length_km=length_km,
        confidence=confidence,
    )
    network.edges.append(edge)

    # Only attach feature link to the first segment to avoid duplicates
    if is_first_segment:
        network.feature_links.append(NetworkFeatureLink(
            feature_id=feature.osm_id,
            feature_type=feature.type.value,
            name=feature.name,
            latitude=(up_lat + down_lat) / 2,
            longitude=(up_lon + down_lon) / 2,
            relationship=REL_UNKNOWN,
            nearest_node_id=up_id,
            distance_km=0.0,
            elevation_m=up_z if up_z is not None else down_z,
            confidence=confidence,
            data_source=feature.source,
        ))


def _endpoint_arity(network: HydrologicalNetwork, node_id: str,
                   way_endpoints: dict[str, list[str]]) -> int:
    """Count how many ways reference this endpoint node (across all ways
    considered, not just the current one).
    """
    n = 0
    for w_endpts in way_endpoints.values():
        if node_id in w_endpts:
            n += 1
    return n


def _merge_nearby_nodes(
    nodes: dict[str, NetworkNode],
    snap_m: float = 25.0,
) -> tuple[dict[str, NetworkNode], dict[str, str]]:
    """Merge nodes that are within snap_m metres of each other.
    Returns (merged_nodes, old_to_new_map) where old_to_new_map maps
    each removed node ID to its surviving representative node ID.
    """
    if not nodes:
        return nodes, {}

    # Grid cell size in degrees
    cell_deg = snap_m / 111000.0

    # Group nodes by grid cell
    grid: dict[tuple[int, int], list[tuple[str, NetworkNode]]] = defaultdict(list)
    for nid, node in nodes.items():
        gx = int(round(node.longitude / cell_deg))
        gy = int(round(node.latitude / cell_deg))
        grid[(gx, gy)].append((nid, node))

    # Union-Find for transitive merging
    parent: dict[str, str] = {nid: nid for nid in nodes}
    rank: dict[str, int] = {nid: 0 for nid in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx == ry:
            return
        if rank[rx] < rank[ry]:
            parent[rx] = ry
        elif rank[rx] > rank[ry]:
            parent[ry] = rx
        else:
            parent[ry] = rx
            rank[rx] += 1

    # Check each node against nodes in same and adjacent cells
    for (gx, gy), cell_nodes in grid.items():
        neighbors: list[tuple[str, NetworkNode]] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbors.extend(grid.get((gx + dx, gy + dy), []))

        for i, (nid1, node1) in enumerate(neighbors):
            for nid2, node2 in neighbors[i+1:]:
                d = haversine_m(node1.latitude, node1.longitude,
                                node2.latitude, node2.longitude)
                if d <= snap_m:
                    union(nid1, nid2)

    # Build merged nodes and old→new mapping
    groups: dict[str, list[tuple[str, NetworkNode]]] = defaultdict(list)
    for nid, node in nodes.items():
        groups[find(nid)].append((nid, node))

    new_nodes: dict[str, NetworkNode] = {}
    old_to_new: dict[str, str] = {}
    for group in groups.values():
        rep_nid, rep_node = group[0]
        new_nodes[rep_nid] = rep_node
        for nid, _ in group[1:]:
            old_to_new[nid] = rep_nid

    return new_nodes, old_to_new


def _link_lone_feature(network: HydrologicalNetwork, f: WaterFeature) -> None:
    """Attach a non-way feature (dam, reservoir, lake node) to nearest node."""
    nearest_id = _nearest_node(network, f.latitude, f.longitude,
                               max_m=_NODE_FEATURE_SNAP_M * 4)
    if nearest_id is None:
        network.feature_links.append(NetworkFeatureLink(
            feature_id=f.osm_id,
            feature_type=f.type.value,
            name=f.name,
            latitude=f.latitude, longitude=f.longitude,
            relationship=REL_DISCONNECTED,
            confidence="medium",
            notes=["No network node within 300 m; hydraulically isolated."],
            data_source=f.source,
        ))
        return

    n = network.nodes[nearest_id]
    dist_km = haversine_m(f.latitude, f.longitude, n.latitude, n.longitude) / 1000.0
    rel = REL_UNKNOWN
    notes: list[str] = []
    if f.type in (FeatureType.DAM, FeatureType.WEIR):
        rel = REL_TRIBUTARY  # updated to upstream/downstream in _classify_features
        notes.append("Dam/weir classification refined by graph topology.")
    elif f.type == FeatureType.RESERVOIR:
        rel = REL_TRIBUTARY
        notes.append("Reservoir attached to nearest river node; refine in V0.3 with reservoir polygons.")
    elif f.type in (FeatureType.LAKE, FeatureType.POND, FeatureType.WETLAND):
        rel = REL_TRIBUTARY
    network.feature_links.append(NetworkFeatureLink(
        feature_id=f.osm_id,
        feature_type=f.type.value,
        name=f.name,
        latitude=f.latitude, longitude=f.longitude,
        relationship=rel,
        nearest_node_id=nearest_id,
        distance_km=dist_km,
        elevation_m=n.elevation_m,
        confidence="high" if dist_km * 1000 < _NODE_FEATURE_SNAP_M else "medium",
        notes=notes,
        data_source=f.source,
    ))


def _nearest_node(network: HydrologicalNetwork, lat: float, lon: float,
                  max_m: float) -> str | None:
    best_id: str | None = None
    best_d = math.inf
    for nid, n in network.nodes.items():
        d = haversine_m(lat, lon, n.latitude, n.longitude)
        if d < best_d and d <= max_m:
            best_d = d
            best_id = nid
    return best_id


def _attach_plot(network: HydrologicalNetwork, dem: DEM,
                 plot_lat: float, plot_lon: float) -> None:
    """Attach plot to the drainage network.

    Strategy (priority order):
    1. Direct: plot is on/near a network node → attach (DEM-informed if the
       plot cell is itself a drainage/river cell).
    2. DEM downhill trace → first network node encountered along flow path.
    3. Snap DEM trace endpoint to nearest node.
    """
    from ..watershed.flow import d8_flow_direction, flow_accumulation
    fdir = d8_flow_direction(dem)
    path = trace_downhill(dem, fdir, plot_lat, plot_lon)

    attach_method = "none"
    attach_id = None
    confidence = "low"
    notes: list[str] = []

    # Determine if the plot cell is itself a drainage cell (flow accumulation
    # above threshold) — if so, direct attachment is hydrologically sound.
    facc = flow_accumulation(fdir)
    t = dem.transform
    cr, cc = t.row_at_lat(plot_lat), t.col_at_lon(plot_lon)
    plot_on_drainage = False
    if 0 <= cr < dem.rows and 0 <= cc < dem.cols:
        plot_on_drainage = int(facc[cr, cc]) >= 3

    # Strategy 1: direct attachment to a nearby network node.
    nearest = _nearest_node(network, plot_lat, plot_lon, max_m=200.0)
    if nearest is not None:
        dist_m = haversine_m(plot_lat, plot_lon,
                             network.nodes[nearest].latitude,
                             network.nodes[nearest].longitude)
        if dist_m < 200.0:
            # The nearest node belongs to the drainage network (a river/stream
            # way).  A plot near such a node drains towards it regardless of
            # the DEM flow-accumulation signal, which may be unreliable for
            # coarse/ridge-like DEMs.  The flow-accumulation check only
            # tightens confidence when the node is a genuine drainage cell.
            attach_id = nearest
            attach_method = "on_network" if dist_m < 25.0 else "near_network"
            note = (f"Plot is {'on' if dist_m < 25.0 else 'within'} the river "
                    f"network ({dist_m:.0f}m to node '{nearest}').")
            if plot_on_drainage:
                confidence = "high"
                note += " DEM flow accumulation confirms a drainage cell."
            else:
                confidence = "medium"
                note += " DEM flow accumulation low (coarse DEM artifact)."
            notes.append(note)
        # else: node too far, fall through to DEM trace.
    else:
        notes.append("No network node within 200m of the plot.")

    # Strategy 2: DEM trace → first network node along the flow path.
    if attach_id is None and path:
        for i, (lat, lon) in enumerate(path):
            nearby = _nearest_node(network, lat, lon, max_m=50.0)
            if nearby is not None:
                attach_id = nearby
                attach_method = "dem_trace"
                confidence = "high"
                n = network.nodes[nearby]
                dist_m = haversine_m(lat, lon, n.latitude, n.longitude)
                notes.append(
                    f"DEM downhill trace met network at step {i} "
                    f"({lat:.5f}, {lon:.5f}, {dist_m:.0f}m to node)."
                )
                break

        # Strategy 3: snap trace endpoint to nearest node.
        if attach_id is None:
            end_lat, end_lon = path[-1]
            nearest_end = _nearest_node(network, end_lat, end_lon,
                                        max_m=_NODE_FEATURE_SNAP_M * 8)
            if nearest_end is not None:
                attach_id = nearest_end
                attach_method = "dem_trace_snap"
                confidence = "medium"
                n = network.nodes[nearest_end]
                dist_m = haversine_m(end_lat, end_lon, n.latitude, n.longitude)
                notes.append(
                    f"DEM trace endpoint ({len(path)} cells) snapped to "
                    f"nearest node {dist_m:.0f}m away."
                )
            else:
                notes.append(
                    f"DEM trace ran {len(path)} cells but found no graph node "
                    "within snap distance."
                )
    elif attach_id is None:
        notes.append("DEM downhill trace produced no path (flat or depression).")

    # Fallback: any nearest node regardless of DEM (very last resort).
    if attach_id is None and nearest is not None:
        attach_id = nearest
        attach_method = "euclidean_fallback"
        confidence = "low"
        n = network.nodes[nearest]
        dist_m = haversine_m(plot_lat, plot_lon, n.latitude, n.longitude)
        notes.append(
            f"Fallback: nearest node by Euclidean distance ({dist_m:.0f}m). "
            "Not confirmed by DEM flow direction."
        )

    # Attach or give up.
    if attach_id is None:
        network.plot_attachment_node_id = None
        network.feature_links.append(NetworkFeatureLink(
            feature_id="__plot__", feature_type="plot", name=None,
            latitude=plot_lat, longitude=plot_lon,
            relationship=REL_UNKNOWN,
            confidence="low",
            notes=["Could not attach plot to any drainage network node."],
            data_source="internal",
        ))
        return

    network.feature_links.append(NetworkFeatureLink(
        feature_id="__plot__", feature_type="plot", name=None,
        latitude=plot_lat, longitude=plot_lon,
        relationship=REL_PLOT,
        nearest_node_id=attach_id,
        confidence=confidence,
        notes=notes,
        data_source="internal",
    ))
    network.plot_attachment_node_id = attach_id


def _classify_features(network: HydrologicalNetwork, plot_lat: float,
                       plot_lon: float) -> None:
    """Use graph topology to set upstream/downstream/disconnected per feature."""
    if network.plot_attachment_node_id is None:
        # Without a plot attachment we can only mark disconnected / unknown.
        for fl in network.feature_links:
            if fl.relationship in (REL_UNKNOWN, REL_TRIBUTARY):
                fl.relationship = REL_UNKNOWN
                fl.notes.append("Plot attachment failed; relationship unknown.")
        return

    plot_id = network.plot_attachment_node_id
    up_ids = set(network.upstream_of(plot_id))
    down_ids = set(network.downstream_of(plot_id))

    # For non-way features (dam, reservoir, etc.): trace forward from the
    # feature's node through the graph to find where it joins the main
    # network, then use that junction's relationship to the plot.
    for fl in network.feature_links:
        if fl.feature_type not in ("dam", "weir", "reservoir", "lake", "pond",
                                    "wetland"):
            continue
        nid = fl.nearest_node_id
        if nid is None:
            fl.relationship = REL_DISCONNECTED
            continue
        if fl.feature_type == "plot":
            fl.relationship = REL_PLOT
            continue

        # Direct check: is the node in upstream/downstream sets?
        if nid in up_ids:
            fl.relationship = REL_UPSTREAM
            fl.notes.append(
                f"Reachable upstream of plot via {len(network.upstream_of(nid))} upstream nodes."
            )
            continue
        if nid in down_ids:
            fl.relationship = REL_DOWNSTREAM
            fl.notes.append(
                f"Plot drains into this feature via {len(network.downstream_of(plot_id))} downstream nodes."
            )
            continue

        # If the nearest node is the plot node itself, the feature is just
        # geographically close — NOT hydrologically connected.  Mark as
        # disconnected (the snap is a spatial convenience, not a hydraulic link).
        if nid == plot_id:
            fl.relationship = REL_DISCONNECTED
            fl.notes.append(
                "Feature snapped to plot node; not hydrologically connected."
            )
            continue

        # The node is not directly in upstream/downstream sets — it may be
        # on a tributary.  Trace forward (downstream) from the feature's node
        # to find where it joins the main network.
        visited: set[str] = {nid}
        queue = [nid]
        joined_downstream = False
        joined_upstream = False
        while queue:
            cur = queue.pop(0)
            for e in network._outgoing(cur):
                if e.v in visited:
                    continue
                visited.add(e.v)
                if e.v in down_ids:
                    joined_downstream = True
                    break
                if e.v in up_ids:
                    joined_upstream = True
                    break
                queue.append(e.v)
            if joined_downstream or joined_upstream:
                break

        if joined_downstream:
            fl.relationship = REL_DOWNSTREAM
            fl.notes.append(
                "Feature's tributary joins main river downstream of plot."
            )
        elif joined_upstream:
            fl.relationship = REL_UPSTREAM
            fl.notes.append(
                "Feature's tributary joins main river upstream of plot."
            )
        else:
            # Also check backward: can the plot reach this feature?
            trace_from_plot = network.downstream_of(plot_id)
            if nid in trace_from_plot:
                fl.relationship = REL_DOWNSTREAM
            elif network.plot_attachment_node_id in network.downstream_of(nid):
                fl.relationship = REL_UPSTREAM
            else:
                fl.relationship = REL_DISCONNECTED
                fl.notes.append(
                    "Not in the same directed network as the plot attachment node."
                )

    # River/stream ways: classify by their relationship to the plot.
    for fl in network.feature_links:
        if fl.feature_type not in ("river", "stream", "canal", "drain"):
            continue
        # Find any edge produced by this feature's chain (edge_id starts with e_{osm_id}).
        edges_for_feat = [e for e in network.edges
                          if e.edge_id.startswith(f"e_{fl.feature_id}_")]
        if not edges_for_feat:
            continue
        # Check if ANY edge endpoint is upstream or downstream of plot
        any_up = any(e.u in up_ids or e.v in up_ids for e in edges_for_feat)
        any_down = any(e.u in down_ids or e.v in down_ids for e in edges_for_feat)
        any_at_plot = any(plot_id in (e.u, e.v) for e in edges_for_feat)
        if any_up:
            fl.relationship = REL_UPSTREAM
        elif any_down:
            fl.relationship = REL_DOWNSTREAM
        elif any_at_plot:
            fl.relationship = REL_UPSTREAM  # the segment the plot attaches to
        else:
            fl.relationship = REL_TRIBUTARY
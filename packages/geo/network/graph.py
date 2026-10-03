"""Hydrological network data structures."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..coordinates import haversine_m


# Hydrological relationship of an arbitrary feature with respect to the plot.
REL_UPSTREAM = "upstream"          # feature drains into / towards the plot
REL_DOWNSTREAM = "downstream"      # plot drains into / towards the feature
REL_TRIBUTARY = "tributary"        # lateral connection (not strict upstream/downstream)
REL_DISCONNECTED = "disconnected"  # no shared drainage system
REL_UNKNOWN = "unknown"            # cannot be determined reliably
REL_PLOT = "plot"                  # the plot itself


@dataclass
class NetworkNode:
    """A graph node — typically a polyline endpoint / junction / feature."""
    node_id: str
    latitude: float
    longitude: float
    elevation_m: float | None = None
    kind: str = "junction"          # junction | endpoint | feature
    feature_id: str | None = None   # reference to a WaterFeature
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkEdge:
    """A directed edge: u (upstream) -> v (downstream)."""
    edge_id: str
    u: str                          # upstream node id
    v: str                          # downstream node id
    river_name: str | None = None
    river_type: str | None = None    # FeatureType value (river/stream/canal/...)
    geometry: list[tuple[float, float]] = field(default_factory=list)
    length_km: float = 0.0
    confidence: str = "medium"

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "u": self.u,
            "v": self.v,
            "river_name": self.river_name,
            "river_type": self.river_type,
            "geometry": [[round(lat, 6), round(lon, 6)] for lat, lon in self.geometry],
            "length_km": round(self.length_km, 3),
            "confidence": self.confidence,
        }


@dataclass
class NetworkFeatureLink:
    """How a WaterFeature relates to the network / the plot."""
    feature_id: str
    feature_type: str               # FeatureType value
    name: str | None
    latitude: float
    longitude: float
    relationship: str               # REL_* above
    nearest_node_id: str | None = None
    distance_km: float | None = None
    elevation_m: float | None = None
    confidence: str = "medium"
    notes: list[str] = field(default_factory=list)
    data_source: str = "OpenStreetMap"

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "name": self.name,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "relationship": self.relationship,
            "nearest_node_id": self.nearest_node_id,
            "distance_km": round(self.distance_km, 3) if self.distance_km is not None else None,
            "elevation_m": round(self.elevation_m, 2) if self.elevation_m is not None else None,
            "confidence": self.confidence,
            "notes": self.notes,
            "data_source": self.data_source,
        }


@dataclass
class HydrologicalNetwork:
    """Directed river/stream graph with feature-to-network relationships."""

    nodes: dict[str, NetworkNode] = field(default_factory=dict)
    edges: list[NetworkEdge] = field(default_factory=list)
    feature_links: list[NetworkFeatureLink] = field(default_factory=list)
    plot_attachment_node_id: str | None = None
    watershed_label: str | None = None
    methodology: str = ""

    # -- topology helpers -----------------------------------------------------

    def _outgoing(self, node_id: str) -> list[NetworkEdge]:
        return [e for e in self.edges if e.u == node_id]

    def _incoming(self, node_id: str) -> list[NetworkEdge]:
        return [e for e in self.edges if e.v == node_id]

    def upstream_of(self, node_id: str) -> list[str]:
        """All node IDs that flow (transitively) into the given node."""
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            cur = stack.pop()
            for e in self._incoming(cur):
                if e.u in seen:
                    continue
                seen.add(e.u)
                stack.append(e.u)
        return list(seen)

    def downstream_of(self, node_id: str) -> list[str]:
        """All node IDs the given node drains into (transitively)."""
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            cur = stack.pop()
            for e in self._outgoing(cur):
                if e.v in seen:
                    continue
                seen.add(e.v)
                stack.append(e.v)
        return list(seen)

    # -- detailed traces -----------------------------------------------------

    def downstream_trace(self, node_id: str) -> list[dict]:
        """BFS downstream from node_id, returning structured step records.

        Each record contains:
          - edge_id, u, v (node IDs)
          - river_name, river_type
          - length_km, confidence
          - elevation_up_m, elevation_down_m (if nodes have elevation)
          - cumulative_distance_km
        """
        steps: list[dict] = []
        seen: set[str] = {node_id}
        queue: deque[str] = deque([node_id])
        cumulative_km = 0.0
        while queue:
            cur = queue.popleft()
            for e in self._outgoing(cur):
                if e.v in seen:
                    continue
                seen.add(e.v)
                cumulative_km += e.length_km
                up_node = self.nodes.get(e.u)
                down_node = self.nodes.get(e.v)
                steps.append({
                    "edge_id": e.edge_id,
                    "u": e.u,
                    "v": e.v,
                    "river_name": e.river_name,
                    "river_type": e.river_type,
                    "length_km": round(e.length_km, 4),
                    "cumulative_distance_km": round(cumulative_km, 4),
                    "confidence": e.confidence,
                    "elevation_up_m": round(up_node.elevation_m, 2) if up_node and up_node.elevation_m is not None else None,
                    "elevation_down_m": round(down_node.elevation_m, 2) if down_node and down_node.elevation_m is not None else None,
                })
                queue.append(e.v)
        return steps

    def upstream_trace(self, node_id: str) -> dict:
        """BFS upstream from node_id, returning structured records.

        Returns:
          - main_stem: list of edge steps along the primary upstream path
          - tributaries: list of {confluence_node, tributary_edges} records
          - upstream_dams: feature links classified as upstream
          - upstream_reservoirs: feature links classified as upstream
          - upstream_rivers: feature links classified as upstream
          - disconnected_features: feature links classified as disconnected
          - total_upstream_nodes: count of reachable upstream nodes
        """
        # (REL_UPSTREAM, REL_DISCONNECTED defined in this module)

        # BFS backward to find all upstream nodes and the paths
        seen: set[str] = set()
        queue: deque[str] = deque([node_id])
        upstream_nodes: set[str] = set()

        # parent maps a downstream node -> the edge that flows INTO it from its
        # upstream neighbour.  parent[X] = edge whose v == X.
        parent: dict[str, str] = {}

        while queue:
            cur = queue.popleft()
            for e in self._incoming(cur):
                if e.u in seen:
                    continue
                seen.add(e.u)
                upstream_nodes.add(e.u)
                parent[cur] = e.edge_id
                queue.append(e.u)

        # Reconstruct the main stem by walking upstream from node_id.
        main_stem_edges: list[str] = []
        cur = node_id
        while cur in parent:
            eid = parent[cur]
            main_stem_edges.append(eid)
            e = next(x for x in self.edges if x.edge_id == eid)
            cur = e.u
        main_stem_edges.reverse()

        # Build main_stem steps
        main_stem = []
        cum_km = 0.0
        for eid in main_stem_edges:
            e = next(x for x in self.edges if x.edge_id == eid)
            cum_km += e.length_km
            up_node = self.nodes.get(e.u)
            down_node = self.nodes.get(e.v)
            main_stem.append({
                "edge_id": e.edge_id,
                "u": e.u,
                "v": e.v,
                "river_name": e.river_name,
                "river_type": e.river_type,
                "length_km": round(e.length_km, 4),
                "cumulative_distance_km": round(cum_km, 4),
                "confidence": e.confidence,
                "elevation_up_m": round(up_node.elevation_m, 2) if up_node and up_node.elevation_m is not None else None,
                "elevation_down_m": round(down_node.elevation_m, 2) if down_node and down_node.elevation_m is not None else None,
            })

        # Identify tributaries: edges whose v is an upstream node but whose u
        # is NOT on the main stem path.
        main_stem_nodes = set()
        for eid in main_stem_edges:
            e = next(x for x in self.edges if x.edge_id == eid)
            main_stem_nodes.add(e.u)
        main_stem_nodes.add(node_id)

        tributaries = []
        for uid in upstream_nodes:
            if uid in main_stem_nodes:
                continue
            for e in self._outgoing(uid):
                if e.v in main_stem_nodes:
                    # This edge joins the main stem — it's a tributary entry.
                    # Collect the tributary's upstream chain.
                    trib_chain = []
                    trib_cur = uid
                    visited_trib: set[str] = {uid}
                    while trib_cur is not None:
                        in_edges = self._incoming(trib_cur)
                        # Find the parent edge in this tributary chain.
                        parent_e = None
                        for ie in in_edges:
                            if ie.u in upstream_nodes and ie.u not in main_stem_nodes and ie.u not in visited_trib:
                                parent_e = ie
                                break
                        if parent_e is not None:
                            trib_chain.append({
                                "edge_id": parent_e.edge_id,
                                "u": parent_e.u,
                                "v": parent_e.v,
                                "river_name": parent_e.river_name,
                                "river_type": parent_e.river_type,
                                "length_km": round(parent_e.length_km, 4),
                                "confidence": parent_e.confidence,
                            })
                            visited_trib.add(parent_e.u)
                            trib_cur = parent_e.u
                        else:
                            break
                    trib_chain.reverse()
                    tributaries.append({
                        "confluence_node": e.v,
                        "tributary_entry_edge": e.edge_id,
                        "tributary_river_name": e.river_name,
                        "tributary_chain": trib_chain,
                    })

        # Collect upstream features
        upstream_dams = [f.to_dict() for f in self.feature_links
                         if f.feature_type in ("dam", "weir")
                         and f.relationship == REL_UPSTREAM]
        upstream_reservoirs = [f.to_dict() for f in self.feature_links
                               if f.feature_type == "reservoir"
                               and f.relationship == REL_UPSTREAM]
        upstream_rivers = [f.to_dict() for f in self.feature_links
                           if f.feature_type in ("river", "stream", "canal", "drain")
                           and f.relationship == REL_UPSTREAM]
        disconnected = [f.to_dict() for f in self.feature_links
                        if f.relationship == REL_DISCONNECTED]

        return {
            "main_stem": main_stem,
            "tributaries": tributaries,
            "upstream_dams": upstream_dams,
            "upstream_reservoirs": upstream_reservoirs,
            "upstream_rivers": upstream_rivers,
            "disconnected_features": disconnected,
            "total_upstream_nodes": len(upstream_nodes),
        }

    # -- feature classification ----------------------------------------------

    def classify_feature(self, feature_id: str) -> str | None:
        for f in self.feature_links:
            if f.feature_id == feature_id:
                return f.relationship
        return None

    # -- path building -------------------------------------------------------

    def path_between(
        self,
        from_node: str,
        to_node: str,
    ) -> list[tuple[float, float]] | None:
        """Return concatenated edge geometries (lat, lon tuples) along the
        shortest directed path from ``from_node`` to ``to_node``, or ``None``
        if no directed path exists.
        """
        if from_node == to_node:
            n = self.nodes.get(from_node)
            return [(n.latitude, n.longitude)] if n else None
        # BFS over directed edges.
        parent: dict[str, str | None] = {from_node: None}
        stack = [from_node]
        found = False
        while stack:
            cur = stack.pop(0)
            if cur == to_node:
                found = True
                break
            for e in self._outgoing(cur):
                if e.v not in parent:
                    parent[e.v] = e.edge_id
                    stack.append(e.v)
        if not found:
            return None
        # Reconstruct.
        edge_ids: list[str] = []
        cur = to_node
        while parent[cur] is not None:
            edge_ids.append(parent[cur])  # type: ignore[arg-type]
            cur = self._edge_endpoint(edge_ids[-1], to_node=cur)
        edge_ids.reverse()
        pts: list[tuple[float, float]] = []
        for eid in edge_ids:
            e = next(x for x in self.edges if x.edge_id == eid)
            if not pts:
                pts.append((self.nodes[e.u].latitude, self.nodes[e.u].longitude))
            for lat, lon in e.geometry[1:]:
                pts.append((lat, lon))
        return pts

    def _edge_endpoint(self, edge_id: str, to_node: str) -> str:
        e = next(x for x in self.edges if x.edge_id == edge_id)
        if to_node == e.v:
            return e.u
        return e.v
"""Phase 1 — gather + reconcile local hydraulic evidence (design §J.3).

Fetches the plot-level evidence categories from OpenStreetMap (Overpass) and
records each with an explicit availability/quality status, provenance,
resolution, datum and coverage.  It feeds the ``EvidenceContract`` consumed by
``assess_connectivity`` (§J.1/J.4).

Every source is classified into one of four statuses — **never converted into
an assumption**:

* ``obtained``     — present, authoritative enough, adequate fit for purpose
* ``unavailable``  — not obtainable / not present in the queried sources
* ``insufficient`` — present but resolution/coverage inadequate for the claim
* ``conflicting``  — present but multiple features disagree (surfaced, low
                     confidence; never silently reconciled)

The flood solver is NOT invoked here.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

from ..coordinates import bbox_from_point, haversine_m
from .evidence import (
    EvidenceCategory,
    EvidenceContract,
    EvidenceRow,
    EvidenceStatus,
)


# Availability/quality classification for a gathered source.
OBTAINED = "obtained"
UNAVAILABLE = "unavailable"
INSUFFICIENT = "insufficient"
CONFLICTING = "conflicting"

_STATUS_TO_EVIDENCE = {
    OBTAINED: EvidenceStatus.AVAILABLE,
    UNAVAILABLE: EvidenceStatus.MISSING,
    INSUFFICIENT: EvidenceStatus.PARTIAL,
    CONFLICTING: EvidenceStatus.AVAILABLE,  # surfaced, low confidence via note
}

OVERPASS_DEFAULT = "https://overpass-api.de/api/interpreter"
# Ordered mirror failover: the primary public Overpass instance is frequently
# rate-limited or down, so we cycle through functional mirrors. A failure is
# only reported after every mirror has been tried.
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
LICENSE = "ODbL 1.0 — © OpenStreetMap contributors"
USER_AGENT = "location-hazard-engine/0.2 (research)"


@dataclass
class SourceRecord:
    """Provenance + availability of one gathered evidence category."""
    category: EvidenceCategory
    status: str                    # obtained | unavailable | insufficient | conflicting
    count: int = 0
    source: str = "OpenStreetMap"
    dataset: str = "osm-overpass"
    retrieved_at: str | None = None
    license: str = LICENSE
    resolution_note: str = ""
    datum_note: str = ""           # OSM geometry is WGS84 geographic; DEM datum separate
    coverage_km: float = 0.0
    confidence: str = "medium"
    note: str = ""
    sample: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "status": self.status,
            "count": self.count,
            "source": self.source,
            "dataset": self.dataset,
            "retrieved_at": self.retrieved_at,
            "license": self.license,
            "resolution_note": self.resolution_note,
            "datum_note": self.datum_note,
            "coverage_km": self.coverage_km,
            "confidence": self.confidence,
            "note": self.note,
            "sample": self.sample[:5],
        }


# --- Overpass queries (full geometry) for each evidence category -------------

# Sutlej centreline + local waterways/drains: rivers, streams, canals, drains.
_QUERY_WATERWAYS = """
[out:json][timeout:60];
(
  way["waterway"~"river|stream|canal|drain"]({s},{w},{n},{e});
);
out geom tags;
"""

# Embankments: roads/railways mapped as embankments or on/cut/embankment tag,
# plus any waterway barrier = embankment.
_QUERY_EMBANKMENTS = """
[out:json][timeout:60];
(
  way["embankment"="yes"]({s},{w},{n},{e});
  way["cutting"="yes"]({s},{w},{n},{e});
  way["barrier"~"embankment|wall"]({s},{w},{n},{e});
  way["highway"~"trunk|primary|motorway"]({s},{w},{n},{e});
  way["railway"~"rail|narrow_gauge"]({s},{w},{n},{e});
);
out geom tags;
"""

# Bridges & culverts: waterways with bridge, plus culvert=yes, plus man_made.
_QUERY_BRIDGES_CULVERTS = """
[out:json][timeout:60];
(
  way["bridge"="yes"]({s},{w},{n},{e});
  way["culvert"="yes"]({s},{w},{n},{e});
  way["tunnel"~"culvert|flooded"]({s},{w},{n},{e});
);
out geom tags;
"""

# Flood-control structures: dams, weirs, sluice_gate, flood_barrier, etc.
_QUERY_FLOOD_CONTROL = """
[out:json][timeout:60];
(
  node["waterway"~"dam|weir|sluice_gate|fish_pass"]({s},{w},{n},{e});
  way["waterway"~"dam|weir|sluice_gate|fish_pass"]({s},{w},{n},{e});
  node["waterway"="lock_gate"]({s},{w},{n},{e});
  way["waterway"="lock_gate"]({s},{w},{n},{e});
  node["landuse"~"basin|reservoir"]({s},{w},{n},{e});
  way["landuse"~"basin|reservoir"]({s},{w},{n},{e});
);
out geom tags;
"""


def _fetch(query: str, overpass_url: str, timeout: int = 60) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        overpass_url, data=data,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public API
        return json.loads(resp.read().decode("utf-8"))


class OverpassError(Exception):
    pass


def _way_length_km(pts: list[tuple[float, float]]) -> float:
    if len(pts) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(pts)):
        total += haversine_m(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])
    return round(total / 1000.0, 3)


def _way_min_distance_km(pts: list[tuple[float, float]], lat: float, lon: float) -> float | None:
    if not pts:
        return None
    best = min(haversine_m(lat, lon, p[0], p[1]) for p in pts)
    return round(best / 1000.0, 3)


def _gather_ways(query: str, lat: float, lon: float, radius_km: float,
                 overpass_url: str) -> list[dict]:
    s, w, n, e = bbox_from_point(lat, lon, radius_km)
    payload = _fetch(query.format(s=s, w=w, n=n, e=e), overpass_url)
    out: list[dict] = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {}) or {}
        nodes = [str(x) for x in (el.get("nodes") or [])]
        if el.get("type") == "way":
            geom = el.get("geometry") or []
            pts = [(float(g["lat"]), float(g["lon"]))
                   for g in geom if "lat" in g and "lon" in g]
            mid = pts[len(pts) // 2] if pts else (lat, lon)
        else:  # node
            mid = (float(el.get("lat", lat)), float(el.get("lon", lon)))
            pts = [mid]
        step = max(1, len(pts) // 200)
        rec = {
            "osm_id": str(el.get("id", "")),
            "tags": tags,
            "mid": mid,
            "distance_km": round(haversine_m(lat, lon, mid[0], mid[1]) / 1000.0, 3),
            "min_distance_km": _way_min_distance_km(pts, lat, lon),
            "length_km": _way_length_km(pts),
            "nodes": nodes,
            "endpoints": [pts[0], pts[-1]] if len(pts) >= 2 else pts,
            "points": pts[::step][:200],
            "name": tags.get("name") or tags.get("name:en") or tags.get("ref"),
            "npoints": len(pts),
        }
        out.append(rec)
    return out


def _safe_gather(query: str, lat: float, lon: float, radius_km: float,
                 overpass_url: str, retries: int = 3, backoff_s: float = 2.0) -> tuple[list[dict], str | None]:
    """Fetch with mirror failover; transient Overpass failures never masquerade
    as a genuine 'unavailable' (that would fabricate a false negative for a
    category that may actually be present).  We cycle the primary + every mirror
    in ``OVERPASS_MIRRORS`` once (a dead host will time out anyway, so burning
    repeated retries on the same URL just delays failover to a live mirror);
    only after every mirror is exhausted is the error returned and the caller
    records 'unavailable' with clarity that it is a fetch failure, not
    certified absence.
    """
    import time as _time
    urls = []
    for u in OVERPASS_MIRRORS:
        if u not in urls:
            urls.append(u)
    if overpass_url and overpass_url not in urls:
        urls.append(overpass_url)
    last_err: str | None = None
    for attempt, url in enumerate(urls):
        try:
            return _gather_ways(query, lat, lon, radius_km, url), None
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, json.JSONDecodeError, OverpassError) as exc:
            last_err = f"Overpass query failed on {url}: {exc}"
            if attempt < len(urls) - 1:
                _time.sleep(backoff_s)
    return [], last_err


def _sample_ways(items: list[dict]) -> list[dict]:
    out = []
    for i in items:
        out.append({
            "osm_id": i["osm_id"],
            "name": i["name"],
            "tags": {k: v for k, v in i["tags"].items() if k in
                     ("name", "waterway", "highway", "railway", "bridge",
                      "culvert", "embankment", "barrier", "tunnel",
                      "man_made", "ref")},
            "mid": i["mid"],
            "distance_km": i["distance_km"],
            "min_distance_km": i.get("min_distance_km"),
            "length_km": i.get("length_km"),
            "points": i.get("points", []),
            "endpoints": i.get("endpoints", []),
        })
    return out


def _record(category: EvidenceCategory, items: list[dict], error: str | None,
            radius_km: float, *, resolution_note: str, note: str) -> SourceRecord:
    if error is not None:
        return SourceRecord(
            category=category, status=UNAVAILABLE, count=0,
            retrieved_at=None, coverage_km=radius_km,
            resolution_note=resolution_note,
            note=f"{note} — {error}", confidence="low",
        )
    if not items:
        return SourceRecord(
            category=category, status=UNAVAILABLE, count=0,
            retrieved_at=_now(), coverage_km=radius_km,
            resolution_note=resolution_note,
            note=f"{note} — none found within {radius_km} km.",
            confidence="low",
        )
    names = {i["name"] for i in items if i["name"]}
    return SourceRecord(
        category=category, status=OBTAINED, count=len(items),
        retrieved_at=_now(), coverage_km=radius_km,
        resolution_note=resolution_note,
        datum_note="OSM geometry is WGS84 (EPSG:4326); no vertical datum — "
                   "relates to DEM only via horizontal CRS; do NOT use for "
                   "absolute elevation.",
        note=f"{note} — found {len(items)}.", confidence="medium",
        sample=_sample_ways(items),
    )


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _row_from_record(rec: SourceRecord, *, target: str) -> EvidenceRow:
    st = _STATUS_TO_EVIDENCE[rec.status]
    note = f"{rec.status} ({rec.count} found); {rec.note}"
    if rec.status == CONFLICTING:
        note = f"CONFLICTING evidence for {target}: {rec.note}"
        rec.confidence = "low"
    return EvidenceRow(
        category=rec.category,
        status=st,
        source=rec.source,
        reference=rec.dataset,
        note=note,
        confidence=rec.confidence,
    )


@dataclass
class ChannelReconciliation:
    """Result of resolving which OSM river way(s) form the Sutlej main stem.

    Uses OSM's own network topology (ways sharing endpoint node ids), not
    guesswork: river segments of the same stem are connected end-to-end via
    junction nodes.  A river is 'resolved' when exactly one connected component
    contains the Sutlej-named ways; everything else is tagged tributary or
    unconnected and reported (never silently dropped).
    """
    resolved: bool
    main_stem_ids: list[str]
    tributary_ids: list[str] = field(default_factory=list)
    unconnected_ids: list[str] = field(default_factory=list)
    unconfirmed_ids: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    confidence: str = "medium"
    min_plot_distance_km: float | None = None
    note: str = ""
    ways: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "resolved": self.resolved,
            "main_stem_ids": self.main_stem_ids,
            "tributary_ids": self.tributary_ids,
            "unconnected_ids": self.unconnected_ids,
            "unconfirmed_ids": self.unconfirmed_ids,
            "conflicts": self.conflicts,
            "confidence": self.confidence,
            "min_plot_distance_km": self.min_plot_distance_km,
            "note": self.note,
            "ways": self.ways,
        }


_SUTLEJ_NAMES = {"sutlej", "satluj", "shatadru"}


def _is_sutlej_named(item: dict) -> bool:
    name = (item.get("name") or "").lower().strip()
    return name in _SUTLEJ_NAMES


def reconcile_channel_network(
    river_ways: list[dict],
    join_tolerance_m: float = 75.0,
) -> ChannelReconciliation:
    """Partition river ways into connected components and identify the Sutlej
    main stem.

    Connectivity uses BOTH sources of evidence from OSM's own geometry, never
    guesswork:

    * exact node-id sharing (ways that share a junction node), and
    * near-coincident endpoints (within ``join_tolerance_m``) — OSM frequently
      joins consecutive river segments at the same coordinate but with distinct
      node ids; treating only node ids would falsely report mapping gaps.

    A river is 'resolved' when exactly one connected component contains the
    Sutlej-named ways; everything else is tagged tributary or unconnected and
    reported (never silently dropped).
    """
    ways = [w for w in river_ways if (w.get("tags") or {}).get("waterway") == "river"]
    if not ways:
        return ChannelReconciliation(
            resolved=False, main_stem_ids=[], conflicts=["No waterway=river ways."],
            confidence="low", note="No river ways to reconcile.",
        )

    def _endpoints(w: dict) -> list[tuple[float, float]]:
        return w.get("endpoints") or []

    def _share_endpoint(a: dict, b: dict) -> bool:
        ea, eb = _endpoints(a), _endpoints(b)
        for pa in ea:
            for pb in eb:
                if haversine_m(pa[0], pa[1], pb[0], pb[1]) <= join_tolerance_m:
                    return True
        return False

    # Component-finding over shared endpoint nodes AND coincident endpoints.
    node_to_ways: dict[str, set[str]] = {}
    for w in ways:
        for nd in w.get("nodes") or []:
            node_to_ways.setdefault(nd, set()).add(w["osm_id"])
    adj: dict[str, set[str]] = {w["osm_id"]: set() for w in ways}
    for nd, ws in node_to_ways.items():
        ws = list(ws)
        for i in range(len(ws)):
            for j in range(i + 1, len(ws)):
                adj[ws[i]].add(ws[j])
                adj[ws[j]].add(ws[i])
    for i in range(len(ways)):
        for j in range(i + 1, len(ways)):
            if _share_endpoint(ways[i], ways[j]):
                adj[ways[i]["osm_id"]].add(ways[j]["osm_id"])
                adj[ways[j]["osm_id"]].add(ways[i]["osm_id"])

    comp_of: dict[str, int] = {}
    components: list[set[str]] = []
    for w in ways:
        wid = w["osm_id"]
        if wid in comp_of:
            continue
        stack = [wid]
        comp: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in comp_of:
                continue
            comp_of[cur] = len(components)
            comp.add(cur)
            for nb in adj.get(cur, ()):
                if nb not in comp_of:
                    stack.append(nb)
        components.append(comp)

    by_id = {w["osm_id"]: w for w in ways}
    comp_sutlej = [
        (i, {wid for wid in comp if _is_sutlej_named(by_id[wid])})
        for i, comp in enumerate(components)
    ]
    named_comps = [i for i, s in comp_sutlej if s]
    main_comp: int | None = None
    unconfirmed_ids: list[str] = []
    conflicts: list[str] = []
    if not named_comps:
        main_comp = max(range(len(components)), key=lambda i: (
            sum(by_id[w].get("length_km") or 0.0 for w in components[i]), len(components[i])))
        conflicts.append("No way named 'Sutlej'; used the largest connected channel "
                         "component as the best candidate (verify against authoritative maps).")
    elif len(named_comps) > 1:
        conflicts.append(
            f"Sutlej-named ways fall into {len(named_comps)} disconnected components "
            "— the OSM mapping has a gap and no single main stem can be proven from "
            "topology alone. All candidates are surfaced as 'unconfirmed'; do NOT "
            "silently pick one.")
        for i in named_comps:
            unconfirmed_ids.extend(sorted(components[i]))
        main_comp = None
    else:
        main_comp = named_comps[0]

    main_sorted: list[str] = []
    min_dist: float | None = None
    if main_comp is not None:
        main_sorted = [w["osm_id"] for w in sorted(
            (by_id[wid] for wid in components[main_comp]),
            key=lambda w: w.get("min_distance_km") or 999.0,
        )]
        min_dist = min((by_id[wid].get("min_distance_km") for wid in components[main_comp]
                        if by_id[wid].get("min_distance_km") is not None), default=None)

    # Way-adjacency degree per node (across ALL river ways): a serial segment has
    # its endpoints shared with neighbours (degree>=2); a branch/leaf has one
    # endpoint unique to it (degree 1).
    node_way_count: dict[str, int] = {}
    for w in ways:
        for nd in w.get("nodes") or []:
            node_way_count[nd] = node_way_count.get(nd, 0) + 1

    def _is_leaf(w: dict) -> bool:
        nodes = w.get("nodes") or []
        if not nodes:
            return False
        return node_way_count.get(nodes[0], 0) == 1 or node_way_count.get(nodes[-1], 0) == 1

    in_main: set[str] = set(main_sorted) if main_comp is not None else set()
    branch_in_main: set[str] = set()
    shared_comps: set[str] = set()
    unconnected_ids: list[str] = []
    confirmable_main = set(components[main_comp]) if main_comp is not None else set()

    for i, comp in enumerate(components):
        if i == main_comp:
            troph = {wid for wid in comp
                     if not _is_sutlej_named(by_id[wid]) and _is_leaf(by_id[wid])}
            branch_in_main |= troph
            continue
        if main_comp is None:
            # No confirmed main stem: nothing confirmable; keep as ambiguous.
            unconnected_ids.extend(sorted(comp))
            continue
        shared = any(
            set(by_id[a].get("nodes") or []) & set(by_id[b].get("nodes") or [])
            for a in comp for b in confirmable_main
        )
        if shared:
            shared_comps |= comp
        else:
            unconnected_ids.extend(sorted(comp))

    tributary_ids = sorted(branch_in_main | shared_comps)
    main_stem_ids = [wid for wid in main_sorted if wid not in branch_in_main]

    def _row(wid: str, role: str) -> dict:
        w = by_id[wid]
        return {
            "osm_id": wid, "name": w.get("name"), "role": role,
            "distance_km": w.get("min_distance_km") or w.get("distance_km"),
            "length_km": w.get("length_km"),
        }

    way_rows = [_row(wid, "main_stem") for wid in main_stem_ids]
    way_rows += [_row(wid, "tributary") for wid in tributary_ids]
    way_rows += [_row(wid, "unconfirmed") for wid in sorted(unconfirmed_ids)]
    way_rows += [_row(wid, "unconnected") for wid in sorted(unconnected_ids)]

    resolved = len(named_comps) == 1
    if resolved:
        note = (
            f"Main stem = {len(main_stem_ids)} connected way(s): "
            f"{', '.join(main_stem_ids)} (min {min_dist} km from plot). "
            + (f"Tributaries: {', '.join(sorted(tributary_ids))}. " if tributary_ids else "")
            + (f"Unconnected river way(s): {', '.join(sorted(unconnected_ids))}. " if unconnected_ids else "")
        ).strip()
    else:
        note = ("Main stem NOT resolvable from OSM topology alone. "
                + (f"Unconfirmed candidates: {', '.join(sorted(unconfirmed_ids))}. " if unconfirmed_ids else "")
                + (f"Best-candidate main stem (no Sutlej-named way): {', '.join(main_stem_ids)}. " if main_stem_ids else "")
                + (f"Unconnected river way(s): {', '.join(sorted(unconnected_ids))}. " if unconnected_ids else "")
        ).strip()
    if conflicts:
        note += " Conflicts: " + " | ".join(conflicts)

    return ChannelReconciliation(
        resolved=resolved,
        main_stem_ids=main_stem_ids,
        tributary_ids=tributary_ids,
        unconnected_ids=sorted(unconnected_ids),
        unconfirmed_ids=sorted(unconfirmed_ids),
        conflicts=conflicts,
        confidence="medium" if resolved else "low",
        min_plot_distance_km=min_dist,
        note=note,
        ways=way_rows,
    )


@dataclass
class EvidenceGatherResult:
    records: list[SourceRecord]
    contract: EvidenceContract
    fetched_at: str
    prologue: str = ""
    raw_items: dict[str, list[dict]] = field(default_factory=dict)
    channel_reconciliation: ChannelReconciliation | None = None

    def to_dict(self) -> dict:
        return {
            "fetched_at": self.fetched_at,
            "records": [r.to_dict() for r in self.records],
            "contract": self.contract.to_dict(),
            "channel_reconciliation": (
                self.channel_reconciliation.to_dict()
                if self.channel_reconciliation else None
            ),
        }


def gather_plot_evidence(
    lat: float,
    lon: float,
    radius_km: float = 3.0,
    overpass_url: str = OVERPASS_DEFAULT,
) -> EvidenceGatherResult:
    """Fetch + reconcile the plot-level evidence for (lat, lon).

    Parameters
    ----------
    radius_km : search radius around the plot (local evidence scale).
    overpass_url : Overpass API endpoint.

    Returns
    -------
    EvidenceGatherResult with one SourceRecord per category and the reconciled
    EvidenceContract for downstream ``assess_connectivity``.
    """
    records: list[SourceRecord] = []
    contract = EvidenceContract(lat, lon)
    raw_items: dict[str, list[dict]] = {}

    # 1. Sutlej centreline / channel geometry (rivers).
    channels, err = _safe_gather(_QUERY_WATERWAYS, lat, lon, radius_km, overpass_url)
    raw_items[EvidenceCategory.CHANNEL_CENTERLINE.value] = channels
    rivers = [i for i in channels if (i["tags"] or {}).get("waterway") == "river"]
    local = [i for i in channels if (i["tags"] or {}).get("waterway") in
             ("stream", "canal", "drain")]
    raw_items[EvidenceCategory.CHANNELS_DRAINS.value] = local

    channel_conflict: ChannelReconciliation | None = None
    rec_ch = _record(
        EvidenceCategory.CHANNEL_CENTERLINE,
        rivers or channels, err, radius_km,
        resolution_note="OSM centreline; horizontal accuracy ~meters; no width/depth.",
        note="Sutlej / channel centreline + local waterways",
    )
    if rivers and len(rivers) > 0 and err is None:
        channel_conflict = reconcile_channel_network(rivers)
        if channel_conflict.resolved:
            main_ways = [i for i in rivers if i["osm_id"] in channel_conflict.main_stem_ids]
            rec_ch.status = OBTAINED
            rec_ch.count = len(main_ways)
            rec_ch.confidence = channel_conflict.confidence
            rec_ch.note = (
                f"Reconciled via OSM network topology. {channel_conflict.note}"
            )
            rec_ch.sample = _sample_ways(main_ways)
            rec_ch.resolution_note = (
                "OSM centreline; horizontal accuracy ~meters; no width/depth. "
                "Duplicate/tributary ways identified via shared node ids."
            )
        else:
            rec_ch.status = CONFLICTING
            rec_ch.count = len(rivers)
            rec_ch.confidence = "low"
            rec_ch.note = f"Reconciled via OSM network topology. {channel_conflict.note}"
    records.append(rec_ch)
    contract.rows.append(_row_from_record(rec_ch, target="Sutlej centreline"))

    # 2. Local channels / drains (non-river waterways: stream/canal/drain).
    rec_dr = _record(
        EvidenceCategory.CHANNELS_DRAINS, local, err, radius_km,
        resolution_note="OSM drain/canal/stream; no bathymetry; ~meter x-y.",
        note="Local channels/drains/streams",
    )
    records.append(rec_dr)
    contract.rows.append(_row_from_record(rec_dr, target="local drainage"))

    # 3. Roads/railways / embankments that could block or route floodwater.
    emb, err_emb = _safe_gather(_QUERY_EMBANKMENTS, lat, lon, radius_km, overpass_url)
    raw_items[EvidenceCategory.EMBANKMENTS_ROAD_RAIL.value] = emb
    rec_emb = _record(
        EvidenceCategory.EMBANKMENTS_ROAD_RAIL, emb, err_emb, radius_km,
        resolution_note="Identifies embankments/roads/railways that may act as "
                        "barriers; not a hydraulic analysis — gaps/culverts not "
                        "assessed here.",
        note="Roads/railways/embankments (potential barriers)",
    )
    records.append(rec_emb)
    contract.rows.append(_row_from_record(rec_emb, target="embankments"))

    # 4. Bridges / culverts — conveyance + blocking points.
    bc, err_bc = _safe_gather(_QUERY_BRIDGES_CULVERTS, lat, lon, radius_km, overpass_url)
    raw_items[EvidenceCategory.BRIDGES_CULVERTS.value] = bc
    rec_bc = _record(
        EvidenceCategory.BRIDGES_CULVERTS, bc, err_bc, radius_km,
        resolution_note="OSM point/way locations; effective opening size NOT "
                        "available — treat as locations only.",
        note="Bridges/culverts/tunnels",
    )
    records.append(rec_bc)
    contract.rows.append(_row_from_record(rec_bc, target="bridges/culverts"))

    # 5. Flood-control structures (dams, weirs, sluice gates, locks).
    fc, err_fc = _safe_gather(_QUERY_FLOOD_CONTROL, lat, lon, radius_km, overpass_url)
    raw_items[EvidenceCategory.FLOOD_CONTROL.value] = fc
    rec_fc = _record(
        EvidenceCategory.FLOOD_CONTROL, fc, err_fc, radius_km,
        resolution_note="OSM point/way locations; operational data NOT in OSM.",
        note="Flood-control structures (dams/weirs/gates)",
    )
    records.append(rec_fc)
    contract.rows.append(_row_from_record(rec_fc, target="flood-control structures"))

    # 6. Gauge observations — not derivable from OSM; mark unavailable here and
    #    note the authoritative sources to pull later (CWC/BBMB/India-WRIS).
    rec_ga = SourceRecord(
        category=EvidenceCategory.GAUGE_OBSERVATIONS,
        status=UNAVAILABLE, count=0, retrieved_at=_now(),
        coverage_km=radius_km,
        resolution_note="Gauge stage/discharge from CWC / India-WRIS / BBMB — not "
                        "available via OSM. Requires external reconciliation "
                        "(datum vs EGM2008).",
        note="CWC/India-WRIS/BBMB gauge data not yet ingested; recorded as "
             "unavailable pending external data step.",
        confidence="low",
    )
    records.append(rec_ga)
    contract.rows.append(_row_from_record(rec_ga, target="gauge observations"))

    # 7. Documented flood extents — historical events; not in OSM.
    rec_fe = SourceRecord(
        category=EvidenceCategory.DOCUMENTED_FLOOD_EXTENTS,
        status=UNAVAILABLE, count=0, retrieved_at=_now(), coverage_km=radius_km,
        resolution_note="Historical flood extents event-based (build validation "
                        "dataset later); not available via OSM.",
        note="No documented flood extents ingested yet.",
        confidence="low",
    )
    records.append(rec_fe)
    contract.rows.append(_row_from_record(rec_fe, target="flood extents"))

    # 8. Local survey / high-resolution elevation — not in OSM.
    for cat, label in ((EvidenceCategory.LOCAL_SURVEY, "local survey"),
                       (EvidenceCategory.HIGH_RES_DEM, "high-res DEM")):
        rec = SourceRecord(
            category=cat, status=UNAVAILABLE, count=0, retrieved_at=_now(),
            coverage_km=radius_km,
            resolution_note=("Requires surveyed ground points / <30 m elevation "
                             "(drone/LiDAR/survey) — not in OSM."),
            note=f"{label} not yet obtained; required for plot-level credibility.",
            confidence="low",
        )
        records.append(rec)
        contract.rows.append(_row_from_record(rec, target=label))

    return EvidenceGatherResult(
        records=records,
        contract=contract,
        fetched_at=_now(),
        prologue="Evidence gathered from OpenStreetMap (Overpass) + recorded "
                 "availability for non-OSM sources. No missing evidence is "
                 "converted into an assumption.",
        raw_items=raw_items,
        channel_reconciliation=channel_conflict,
    )

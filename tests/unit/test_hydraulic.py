"""Phase 1 — hydraulic evidence/connectivity/domain unit tests.

These test the design contracts (§J.1/J.3/J.4) with pure logic + small synthetic
DEMs.  No live network or heavy pysheds run; connectivity reads the D8
``flow_direction`` grid directly via a lightweight stand-in proc object.
"""
import numpy as np
import pytest

from geo.hydraulic import (
    EvidenceCategory,
    EvidenceContract,
    EvidenceRow,
    EvidenceStatus,
    ConnectivityResult,
    ConnectivityStatus,
    UNRESOLVED_MESSAGE,
    assess_connectivity,
    extract_connected_domain,
)
from geo.raster.dem import AffineTransform, DEM


# --- helpers ---------------------------------------------------------------


def make_proc(flow_direction, shape=None):
    """Lightweight TerrainProcessResult stand-in (no pysheds needed)."""
    shape = tuple(shape or flow_direction.shape)

    class Proc:
        def __init__(self):
            self.flow_direction = flow_direction
            self.shape = shape

        @property
        def cell_count(self):
            return self.shape[0] * self.shape[1]

    return Proc()


def make_slope_dem_with_valid_fdir(rows=5, cols=5):
    """A DEM with a resolvable southward slope; plot at a mid cell -> D8 valid."""
    yy = np.linspace(1, 0, rows)[:, None] * np.ones((1, cols))
    elev = 100.0 + 30.0 * yy
    t = AffineTransform(origin_lon=0.0, origin_lat=rows * 0.01,
                        pixel_size_lon=0.01, pixel_size_lat=0.01)
    dem = DEM(elevation=elev, transform=t, nodata=None)
    return dem


def flat_fdir(rows=5, cols=5):
    """Flow-direction grid with flat sentinel (-1) everywhere, as pysheds uses."""
    return np.full((rows, cols), -1, dtype=np.int64)


def valid_fdir(rows=5, cols=5, value=4):  # "4" is in the valid dirmap set
    return np.full((rows, cols), value, dtype=np.int64)


def full_contract(plot=(0.025, 0.005)):
    lat, lon = plot
    return EvidenceContract(lat, lon, rows=[
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE,
                    source="OpenStreetMap", reference="919730633"),
        EvidenceRow(EvidenceCategory.CHANNELS_DRAINS, EvidenceStatus.AVAILABLE,
                    note="mapped drain C connects plot to channel"),
        EvidenceRow(EvidenceCategory.LOCAL_SURVEY, EvidenceStatus.AVAILABLE),
        EvidenceRow(EvidenceCategory.HIGH_RES_DEM, EvidenceStatus.AVAILABLE),
    ])


# --- evidence contract (J.3) -----------------------------------------------


def test_plot_level_not_credible_without_survey_and_highres():
    """A plot/building answer is NOT credible on GLO-30 alone (J.3/J.8)."""
    c = EvidenceContract(1.0, 2.0, rows=[
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE),
    ])
    assert c.plot_level_credible is False
    missing = {e.value for e in c.missing_plot_level_evidence()}
    assert missing == {"local_survey", "high_res_dem"}


def test_plot_level_credible_when_all_required_present():
    c = EvidenceContract(1.0, 2.0, rows=[
        EvidenceRow(EvidenceCategory.LOCAL_SURVEY, EvidenceStatus.AVAILABLE),
        EvidenceRow(EvidenceCategory.HIGH_RES_DEM, EvidenceStatus.AVAILABLE),
    ])
    assert c.plot_level_credible is True


# --- connectivity — no-fabricated-path (J.1) --------------------------------


def test_flat_reach_is_unresolved_never_fabricated():
    """Flat Ropar-style reach -> UNRESOLVED with the verbatim J.1 message."""
    dem = make_slope_dem_with_valid_fdir()
    proc = make_proc(flat_fdir())
    c = full_contract()  # has channel + documented drain + survey + highres
    conn = assess_connectivity(dem, proc, c, plot_lat=0.025, plot_lon=0.005)
    assert conn.status == ConnectivityStatus.UNRESOLVED
    assert conn.reason == UNRESOLVED_MESSAGE
    assert conn.path_established is False


def test_connected_requires_documented_link_and_resolvable_reach():
    """Connected only when BOTH a documented link and a resolvable path exist."""
    dem = make_slope_dem_with_valid_fdir()
    proc = make_proc(valid_fdir())
    c = full_contract()
    conn = assess_connectivity(dem, proc, c, plot_lat=0.025, plot_lon=0.005)
    assert conn.status == ConnectivityStatus.CONNECTED
    assert conn.path_established is True


def test_no_documented_link_is_unresolved_even_with_slope():
    """A resolvable slope ALONE is not enough — no fabricated connectivity."""
    dem = make_slope_dem_with_valid_fdir()
    proc = make_proc(valid_fdir())
    c = EvidenceContract(0.025, 0.005, rows=[
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE),
    ])
    conn = assess_connectivity(dem, proc, c, plot_lat=0.025, plot_lon=0.005)
    assert conn.status == ConnectivityStatus.UNRESOLVED
    # explicitly NOT connected-despite-resolution


def test_definitive_barrier_is_not_connected():
    """A survey-confirmed impermeable barrier -> NOT_CONNECTED."""
    c = EvidenceContract(1.0, 2.0, rows=[
        EvidenceRow(EvidenceCategory.EMBANKMENTS_ROAD_RAIL, EvidenceStatus.AVAILABLE,
                    note="survey-confirmed embankment with no hydraulic opening"),
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE),
    ])
    conn = assess_connectivity(None, None, c, plot_lat=1.0, plot_lon=2.0)
    assert conn.status == ConnectivityStatus.NOT_CONNECTED


def test_missing_channel_is_unresolved():
    c = EvidenceContract(1.0, 2.0)  # no channel centreline evidence
    conn = assess_connectivity(None, None, c, plot_lat=1.0, plot_lon=2.0)
    assert conn.status == ConnectivityStatus.UNRESOLVED


def test_connectivity_reports_checks():
    dem = make_slope_dem_with_valid_fdir()
    proc = make_proc(valid_fdir())
    conn = assess_connectivity(dem, proc, full_contract(),
                               plot_lat=0.025, plot_lon=0.005)
    names = {ch["check"] for ch in conn.checks}
    assert {"channel_centerline_present", "documented_local_drainage",
            "terrain_reach_resolvable", "definitive_barrier"} <= names


def test_flat_sentinel_variants_all_unresolvable():
    """-1 (flat), -2 (sink/nodata) and 0 must all be treated as not resolvable."""
    dem = make_slope_dem_with_valid_fdir()
    for sentinel in (-2, -1, 0):
        proc = make_proc(np.full((5, 5), sentinel, dtype=np.int64))
        conn = assess_connectivity(dem, proc, full_contract(),
                                   plot_lat=0.025, plot_lon=0.005)
        assert conn.status == ConnectivityStatus.UNRESOLVED, sentinel


# --- domain extraction (J.2/J.4) --------------------------------------------


def test_domain_unresolved_does_not_extract():
    conn = ConnectivityResult(status=ConnectivityStatus.UNRESOLVED,
                              reason=UNRESOLVED_MESSAGE)
    dom = extract_connected_domain(conn)
    assert dom.outcome == "unresolved"
    assert dom.domain is None
    assert dom.domain_cells is None
    assert dom.message == UNRESOLVED_MESSAGE


def test_domain_not_connected_does_not_extract():
    conn = ConnectivityResult(status=ConnectivityStatus.NOT_CONNECTED,
                              reason="barrier")
    dom = extract_connected_domain(conn)
    assert dom.outcome == "not_connected"
    assert dom.domain_cells is None


def test_domain_connected_quantifies_from_real_grid():
    dem = make_slope_dem_with_valid_fdir(cols=6, rows=4)
    proc = make_proc(valid_fdir(rows=4, cols=6), shape=(4, 6))
    conn = ConnectivityResult(status=ConnectivityStatus.CONNECTED,
                              reason="connected", path_established=True)
    dom = extract_connected_domain(conn, dem, proc)
    assert dom.outcome == "connected"
    assert dom.domain_cells == 24  # rows*cols
    assert dom.domain_extent_sqkm is not None


# --- evidence gathering / reconciliation (sources.py, offline logic) ---------


def _record_helper(category, items, error=None):
    from geo.hydraulic.sources import _record
    return _record(category, items, error, radius_km=3.0,
                   resolution_note="test", note="test source")


def test_record_obtained_maps_to_available():
    from geo.hydraulic.sources import OBTAINED
    from geo.hydraulic.evidence import EvidenceStatus
    rec = _record_helper(EvidenceCategory.CHANNEL_CENTERLINE,
                         [{"osm_id": "1", "name": "Sutlej", "tags": {},
                           "mid": (31.05, 76.53), "distance_km": 0.28,
                           "npoints": 10}])
    assert rec.status == OBTAINED
    assert rec.count == 1
    # And it maps into an AVAILABLE EvidenceRow for the contract.
    from geo.hydraulic.sources import _row_from_record
    row = _row_from_record(rec, target="Sutlej")
    assert row.status == EvidenceStatus.AVAILABLE


def test_record_empty_is_unavailable_not_assumed():
    from geo.hydraulic.sources import UNAVAILABLE, _row_from_record
    from geo.hydraulic.evidence import EvidenceStatus
    rec = _record_helper(EvidenceCategory.FLOOD_CONTROL, [])
    assert rec.status == UNAVAILABLE
    row = _row_from_record(rec, target="flood control")
    assert row.status == EvidenceStatus.MISSING  # genuinely none -> missing, never assumed present


def test_record_error_marks_unavailable_low_confidence():
    """A fetch failure is 'unavailable/low', NOT certified absence, and is
    never upgraded to present."""
    from geo.hydraulic.sources import _row_from_record
    rec = _record_helper(EvidenceCategory.CHANNEL_CENTERLINE, [], error="Overpass query failed")
    assert rec.status == "unavailable"
    assert rec.confidence == "low"
    row = _row_from_record(rec, target="Sutlej")
    assert row.status.value == "missing"
    assert "Overpass query failed" in row.note


def test_record_conflicting_sets_low_confidence():
    from geo.hydraulic.sources import _row_from_record
    rec = _record_helper(EvidenceCategory.CHANNEL_CENTERLINE,
                         [{"osm_id": "1", "name": "Sutlej", "tags": {}, "mid": (1, 1), "distance_km": 0.1, "npoints": 2},
                          {"osm_id": "2", "name": "other", "tags": {}, "mid": (1.1, 1.1), "distance_km": 0.2, "npoints": 2}])
    rec.status = "conflicting"
    row = _row_from_record(rec, target="Sutlej centreline")
    assert row.confidence == "low"
    assert "CONFLICTING" in row.note


def test_plot_level_credible_false_without_highres_and_survey():
    """With all the OSM-obtainable categories present but no survey/high-res DEM,
    the contract still refuses plot-level credibility."""
    c = EvidenceContract(31.05, 76.53, rows=[
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE),
        EvidenceRow(EvidenceCategory.CHANNELS_DRAINS, EvidenceStatus.AVAILABLE),
        EvidenceRow(EvidenceCategory.EMBANKMENTS_ROAD_RAIL, EvidenceStatus.AVAILABLE),
        EvidenceRow(EvidenceCategory.BRIDGES_CULVERTS, EvidenceStatus.AVAILABLE),
    ])
    assert c.plot_level_credible is False
    assert c.missing_plot_level_evidence()  # survey + high-res


# --- channel reconciliation (sources.reconcile_channel_network) -------------


def _river_way(osm_id, nodes, name=None, pts=None, waterway="river"):
    return {
        "osm_id": osm_id, "name": name, "tags": {"waterway": waterway},
        "nodes": [str(x) for x in nodes], "endpoints": list(pts or ()),
        "distance_km": 1.0, "min_distance_km": 0.5, "length_km": 5.0,
    }


def test_reconcile_joins_ways_sharing_junction_node():
    """Two Sutlej segments sharing an endpoint node resolve to one main stem."""
    from geo.hydraulic.sources import reconcile_channel_network
    a = _river_way("a", [1, 2, 3], name="Sutlej", pts=[(1, 1), (2, 2), (3, 3)])
    b = _river_way("b", [3, 4, 5], name="Sutlej", pts=[(3, 3), (4, 4), (5, 5)])
    rec = reconcile_channel_network([a, b])
    assert rec.resolved is True
    assert set(rec.main_stem_ids) == {"a", "b"}
    assert rec.unconnected_ids == []


def test_reconcile_joins_coincident_endpoints_with_distinct_node_ids():
    """OSM joins river segments at the same coordinate but different node ids;
    reconciliation must still connect them (within tolerance), not report a gap."""
    from geo.hydraulic.sources import reconcile_channel_network
    a = _river_way("a", [1, 2], name="Sutlej", pts=[(0, 0), (1, 1)])
    b = _river_way("b", [9, 8], name="Sutlej", pts=[(1.0003, 1.0004), (2, 2)])  # ~50 m apart
    rec = reconcile_channel_network([a, b], join_tolerance_m=200.0)
    assert rec.resolved is True
    assert set(rec.main_stem_ids) == {"a", "b"}


def test_reconcile_reports_disconnected_sutlej_ways_as_unresolved():
    """Two named-Sutlej ways far apart with no shared/coincident endpoints are
    genuinely gapped; reconciliation keeps the conflict visible and surfaces
    both as unconfirmed instead of silently picking one."""
    from geo.hydraulic.sources import reconcile_channel_network
    a = _river_way("a", [1, 2], name="Sutlej", pts=[(0, 0), (1, 1)])
    b = _river_way("b", [3, 4], name="Sutlej", pts=[(5, 5), (6, 6)])
    rec = reconcile_channel_network([a, b])
    assert rec.resolved is False
    assert rec.conflicts  # mapping gap surfaced, not guessed away
    assert set(rec.unconfirmed_ids) == {"a", "b"}  # both surfaced as candidates
    assert rec.main_stem_ids == []  # no silent pick


def test_reconcile_tags_tributary_and_unconnected_separately():
    """A way connected to the main stem is a tributary; a far-away way is
    unconnected — never silently dropped."""
    from geo.hydraulic.sources import reconcile_channel_network
    main = _river_way("main", [1, 2, 3], name="Sutlej", pts=[(0, 0), (1, 1), (2, 2)])
    trib = _river_way("trib", [3, 7, 8], name=None, pts=[(2, 2), (3, 3), (4, 4)])
    far = _river_way("far", [9, 10], name=None, pts=[(10, 10), (11, 11)])
    rec = reconcile_channel_network([main, trib, far])
    assert rec.resolved is True
    assert rec.main_stem_ids == ["main"]
    assert rec.tributary_ids == ["trib"]
    assert rec.unconnected_ids == ["far"]


# --- local topology (topology.build_local_topology) -------------------------


def _minimal_gather(channel_items=None, drain_items=None, bridge_items=None,
                    reconciliation=None):
    from geo.hydraulic.sources import EvidenceGatherResult
    return EvidenceGatherResult(
        records=[], contract=EvidenceContract(31.05, 76.53),
        fetched_at="t", prologue="",
        raw_items={
            "channel_centerline": channel_items or [],
            "channels_drains": drain_items or [],
            "bridges_culverts": bridge_items or [],
            "embankments_road_rail": [],
            "flood_control": [],
        },
        channel_reconciliation=reconciliation,
    )


def test_topology_marks_crossing_on_waterway_geometrically():
    """A bridge that lies on a waterway (separate node ids) must be flagged as
    on_waterway via geometric colocation — node-id matching alone would miss it."""
    from geo.hydraulic import build_local_topology
    from geo.hydraulic.sources import ChannelReconciliation
    river = _river_way("r", [1, 2, 3], name="Sutlej", pts=[(0, 0), (1, 1), (2, 2)])
    bridge = {
        "osm_id": "br", "name": "bridge", "tags": {"bridge": "yes"},
        "nodes": ["x", "y"], "points": [(1.0003, 0.9997)], "distance_km": 0.5,
        "min_distance_km": 0.5, "length_km": 2.0,
    }
    g = _minimal_gather(channel_items=[river], bridge_items=[bridge],
                        reconciliation=ChannelReconciliation(
                            resolved=True, main_stem_ids=["r"], min_plot_distance_km=0.1))
    topo = build_local_topology(g, dem=None, proc=None, plot_lat=31.05, plot_lon=76.53)
    assert len(topo.crossings) == 1
    assert topo.crossings[0]["on_waterway"] is True
    assert topo.crossings[0]["geometrically_colocated"] is True
    # No DEM/proc -> reach direction honestly unresolved.
    assert topo.reach_direction_status == "unresolved"


def test_topology_barrier_and_reach_direction():
    """Barriers are listed descriptively (never inferred as blockage), and the
    plot-cell reach direction follows the D8 grid (flat -> unresolved)."""
    from geo.hydraulic import build_local_topology
    from geo.hydraulic.sources import ChannelReconciliation
    barrier = {
        "osm_id": "rw", "name": None, "tags": {"railway": "rail"},
        "distance_km": 2.0, "min_distance_km": 2.0, "length_km": 10.0,
        "nodes": [], "points": [],
    }
    g = _minimal_gather(
        channel_items=[_river_way("r", [1, 2], name="Sutlej", pts=[(0, 0), (1, 1)])],
        reconciliation=ChannelReconciliation(resolved=True, main_stem_ids=["r"]))
    g.raw_items["embankments_road_rail"] = [barrier]
    proc = make_proc(flat_fdir(rows=5, cols=5), shape=(5, 5))
    dem = make_slope_dem_with_valid_fdir(rows=5, cols=5)
    topo = build_local_topology(g, dem, proc, plot_lat=0.025, plot_lon=0.005)
    assert topo.barriers[0]["kind"] == "railway:rail"
    # The connectivity statement is descriptive-only (no fabricated conclusion).
    assert "assess_connectivity" in topo.connectivity_statement
    assert topo.reach_direction_status == "unresolved"  # flat sentinel


# --- authoritative flood evidence (flood_evidence.py, offline logic) -------------


def _nwdp_body(package_id: str, names: list[str]) -> bytes:
    pkg = {
        "title": package_id,
        "metadata_modified": "2026-09-01T00:00:00",
        "resources": [{"name": n, "format": "CSV", "size": 1234,
                       "url": f"https://nwdp.in/download/{n}"} for n in names],
    }
    return json.dumps({"success": True, "result": pkg}).encode()


def _flood_stub(everything_down: bool = False,
                bhakra_bbmb: bool = False,
                sutlej_resources: bool = False) -> callable:
    """Deterministic fetch stub mirroring the real NWDP/BBMB accessibility.
    - everything_down: all fetches raise (network outage).
    - bhakra_bbmb: BBMB bulletin pages return a parseable Bhakra row.
    - sutlej_resources: CWC packages list an Indus/Sutlej resource.
    """
    def _fx(url: str, timeout_s: float):
        if everything_down:
            raise ConnectionError("simulated network outage")
        body = b"<html>no data</html>"
        if "package_show" in url:
            if "river-water-level-telemetry" in url:
                names = (["River Water Level CWC Satluj (1991-2020) Telemetry Hourly"] if sutlej_resources
                         else ["River Water Level Telemetry Hourly CWC Subernarekha (1991-2020)"])
                body = _nwdp_body("rwl", names)
            elif "river-discharge" in url:
                names = (["River Discharge CWC Punjab (1950 - 2000) Manual Daily"] if sutlej_resources
                         else ["River Discharge CWC Andhra Pradesh (1950 - 2000)"])
                body = _nwdp_body("discharge", names)
            elif "reservoir-water-level-manual" in url:
                body = _nwdp_body("res_manual", ["Reservoir Water Level Bhakra (1970-2025) Manual Daily"])
            elif "reservoir-water-level-telemetry" in url:
                body = _nwdp_body("res_tele", ["Reservoir Water Level Bhakra (2026-2030) Telemetry Hourly"])
        elif "bbmb.gov.in" in url and bhakra_bbmb:
            body = ("Bhakra 1678.97 Level Ft Inflows 95435 Cusecs Outflows 73459 Cusecs"
                    ).encode()
        return 200, body
    return _fx


import json  # noqa: E402


def test_cwc_sutlej_series_unavailable_when_package_has_no_indus():
    from geo.hydraulic.flood_evidence import gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub())
    rec = next(r for r in res.records if r.title.startswith("CWC gauge series for the Sutlej"))
    assert rec.status == "unavailable"
    assert "no" in rec.uncertainty_note.lower() and "publishes" not in rec.note
    # The national dataset itself is recorded obtained (reachable), coverage noted.
    nat = next(r for r in res.records if "national NWDP dataset" in r.title)
    assert nat.status == "obtained"


def test_placeholder_bbmb_values_flagged_insufficient_not_obtained():
    from geo.hydraulic.flood_evidence import gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub())
    rec = next(r for r in res.records if "Bhakra reservoir level" in r.title
               and "NWDP manual-daily" in r.title)
    assert rec.status == "insufficient"
    assert any("placeholder" in str(s) for s in rec.sample)
    assert rec.confidence == "low"


def test_cwc_package_with_sutlej_resource_is_obtained():
    from geo.hydraulic.flood_evidence import gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub(sutlej_resources=True))
    nat = next(r for r in res.records if "national NWDP dataset" in r.title)
    assert nat.status == "obtained"
    # Sanity: the availability conclusion follows the data, not the stub mode.
    assert any(r.title.startswith("CWC gauge series") for r in res.records)


def test_bbmb_bulletin_live_capture_parses_bhakra_row():
    from geo.hydraulic.flood_evidence import gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub(bhakra_bbmb=True))
    live = next(r for r in res.records if "live capture" in r.title)
    assert live.status == "obtained"
    assert live.sample[0]["reservoir_level_ft"] == 1678.97
    assert live.sample[0]["inflow_cusecs"] == 95435
    assert live.sample[0]["outflow_cusecs"] == 73459


def test_network_outage_recorded_as_fetch_failure_not_fabricated():
    from geo.hydraulic.flood_evidence import gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub(everything_down=True))
    for r in res.records:
        if r.status == "obtained":
            continue  # cited documented records stay obtained (research-cited)
    bbmb = next(r for r in res.records if "daily live value" in r.title)
    assert bbmb.status == "unavailable"
    assert "fetch failure" in bbmb.uncertainty_note.lower()
    cwc_nat = next(r for r in res.records if "national NWDP dataset" in r.title)
    assert cwc_nat.status == "unavailable"
    # The documented (cited) records must still be present and honest.
    assert any(r.title.startswith("Sutlej peak flow at Ropar") for r in res.records)


def test_gauge_to_plot_gate_is_verbatim_and_always_present():
    from geo.hydraulic.flood_evidence import GAUGE_TO_PLOT_STATEMENT, gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub(everything_down=True))
    assert res.gauge_to_plot_statement == GAUGE_TO_PLOT_STATEMENT
    assert "converted into a plot flood depth" in res.gauge_to_plot_statement
    assert res.to_dict()["gauge_to_plot_statement"] == GAUGE_TO_PLOT_STATEMENT


def test_flood_extent_records_carry_coverage_and_uncertainty():
    from geo.hydraulic.flood_evidence import gather_flood_evidence
    res = gather_flood_evidence(fetch_fn=_flood_stub())
    ext = next(r for r in res.records if r.title.startswith("September 1988 flood"))
    assert ext.status == "obtained"
    assert ext.spatial_coverage and ext.temporal_coverage and ext.uncertainty_note
    gfd = next(r for r in res.records if "Global Flood Database" in r.title)
    assert gfd.status == "obtained"
    assert "deferred" in gfd.uncertainty_note.lower()


# --- plot-level terrain evidence (terrain_evidence.py, offline logic) ---------


def make_terrain_dem(n=81, ps=0.002, center=(1.0, 1.0), pit_depth=12.0):
    """Grid DEM: gentle N->S slope + a smooth gaussian pit near the plot cell.

    ~0.002° (~220 m) cells, 81x81 -> ~18 km span, so a 3 km radius window is
    fully inside the grid for offline characterisation tests.
    """
    lat, lon = center
    span = ps * n
    t = AffineTransform(origin_lon=lon - span / 2, origin_lat=lat + span / 2,
                        pixel_size_lon=ps, pixel_size_lat=ps)
    yy = np.linspace(0, 1, n)[:, None] * np.ones((1, n))
    elev = 120.0 - 40.0 * yy
    cy, cx = n // 2, n // 2
    for r in range(n):
        for c in range(n):
            d2 = (r - cy) ** 2 + (c - cx) ** 2
            elev[r, c] -= (pit_depth * np.exp(-d2 / (2 * 3.0 ** 2)))
    return DEM(elevation=elev, transform=t, nodata=None,
               source_resolution_m=ps * 111_320.0, simulation_grid_m=ps * 111_320.0,
               horizontal_crs="EPSG:4326", vertical_datum="EGM2008",
               dataset="Copernicus DEM GLO-30", provenance="test")


def _river_way_points(osm_id, pts, name=None, waterway="river"):
    return {
        "osm_id": osm_id, "name": name, "tags": {"waterway": waterway},
        "nodes": [str(i) for i in range(len(pts) + 1)],
        "endpoints": [pts[0], pts[-1]], "points": pts,
        "distance_km": min(1.0, 0.1), "min_distance_km": 0.5, "length_km": 5.0,
    }


def _offset_provider(offset_m=7.0, base=100.0, dataset="SRTM GL1 (+GMTED2010 fill)",
                     vertical_datum="EGM96", res_m=30.0, raises=False):
    from geo.terrain.provider import ProviderResult

    class P:
        name = "offset-stub"

        def get_dem(self, lat, lon, radius_km):
            if raises:
                raise ConnectionError("simulated network outage")
            dem = DEM(elevation=base + offset_m + np.zeros((11, 11)),
                      transform=AffineTransform(lon - 0.011, lat + 0.011, 0.002, 0.002),
                      nodata=None, source_resolution_m=res_m,
                      horizontal_crs="EPSG:4326", vertical_datum=vertical_datum,
                      dataset=dataset, provenance="test-stub")
            return ProviderResult(dem=dem, source="stub", dataset=dataset,
                                  resolution_m=res_m, retrieved_at="t",
                                  license="test", note="stub cross-check",
                                  vertical_datum=vertical_datum,
                                  horizontal_crs="EPSG:4326")
    return P()


def test_terrain_elevations_are_dem_derived_never_surveyed():
    """Every numeric elevation is DEM-derived; the surveyed block is an honest
    'unavailable' and nothing is relabelled as surveyed."""
    from geo.hydraulic import TERRAIN_TO_CONNECTIVITY_STATEMENT, gather_terrain_evidence
    from geo.hydraulic.sources import ChannelReconciliation
    dem = make_terrain_dem()
    river = _river_way_points("r", [(1.0, 0.99), (1.0, 1.01)], name="Sutlej")
    g = _minimal_gather(channel_items=[river],
                        reconciliation=ChannelReconciliation(
                            resolved=True, main_stem_ids=["r"], min_plot_distance_km=0.1))
    r = gather_terrain_evidence(dem, g, plot_lat=1.0, plot_lon=1.0, radius_km=3.0)
    assert r.plot["elevation_kind"] == "dem"
    assert r.surveyed["status"] == "unavailable"
    assert all(s.elevation_kind == "dem" for s in r.samples)
    assert r.connectivity_statement == TERRAIN_TO_CONNECTIVITY_STATEMENT
    assert "characterisation only" in r.connectivity_statement


def test_terrain_transect_and_low_points_reported():
    """A transect to the main stem and a DEM depression (lower than the plot)
    must both be reported, with relative elevations, never as connectivity."""
    from geo.hydraulic import gather_terrain_evidence
    from geo.hydraulic.sources import ChannelReconciliation
    dem = make_terrain_dem()
    river = _river_way_points("r", [(1.0, 0.99), (1.0, 1.01)], name="Sutlej")
    g = _minimal_gather(channel_items=[river],
                        reconciliation=ChannelReconciliation(
                            resolved=True, main_stem_ids=["r"], min_plot_distance_km=0.1))
    r = gather_terrain_evidence(dem, g, plot_lat=1.0, plot_lon=1.0, radius_km=3.0)
    assert r.transect is not None
    assert len(r.transect.points) >= 2
    assert r.transect.plot_elevation_m is not None
    assert r.transect.channel_relative_to_plot_m is not None
    assert r.low_points, "pit should be a reported low point"
    low = r.low_points[0]
    assert low.dem_elevation_m < r.plot["dem_elevation_m"]
    assert low.relative_to_plot_m is not None and low.relative_to_plot_m < 0
    assert "NOT connectivity" in low.note


def test_terrain_finer_dem_crosscheck_keeps_datum_delta():
    """The finer-DEM cross-check reports the datum-separated delta explicitly
    (EGM96 vs EGM2008), calculates it, and never fuses the datums."""
    from geo.hydraulic import gather_terrain_evidence
    from geo.hydraulic.sources import ChannelReconciliation
    dem = make_terrain_dem()
    g = _minimal_gather(channel_items=[_river_way_points(
        "r", [(1.0, 0.99), (1.0, 1.01)], name="Sutlej")],
        reconciliation=ChannelReconciliation(resolved=True, main_stem_ids=["r"]))
    r = gather_terrain_evidence(dem, g, plot_lat=1.0, plot_lon=1.0, radius_km=3.0,
                                finer_provider=_offset_provider(
                                    offset_m=7.0,
                                    base=dem.value_at(1.0, 1.0)))
    assert r.finer_dem is not None
    assert r.finer_dem.status == "obtained"
    assert r.finer_dem.cross_check_delta_m == pytest.approx(7.0, abs=1e-6)
    assert r.finer_dem.vertical_datum == "EGM96"
    assert "datums explicitly differ" in r.finer_dem.note
    assert "sub-30 m DEM" in r.finer_dem.note  # cross-check != finer product


def test_terrain_finer_dem_fetch_failure_never_fabricated():
    """A failing finer-DEM attempt is recorded unavailable with the reason,
    never upgraded or filled in."""
    from geo.hydraulic import gather_terrain_evidence
    dem = make_terrain_dem()
    r = gather_terrain_evidence(dem, None, plot_lat=1.0, plot_lon=1.0,
                                radius_km=3.0,
                                finer_provider=_offset_provider(raises=True))
    assert r.finer_dem is not None
    assert r.finer_dem.status == "unavailable"
    assert "never fabricated" in r.finer_dem.note
    assert r.samples == [] and r.transect is None  # no fabricated features


def test_terrain_finer_dem_no_data_result_is_unavailable():
    """ProviderResult with dem=None (StubProvider semantics) -> unavailable,
    recorded as no data, not certified absence."""
    from geo.hydraulic import gather_terrain_evidence
    from geo.terrain.provider import StubProvider
    dem = make_terrain_dem()
    r = gather_terrain_evidence(dem, None, plot_lat=1.0, plot_lon=1.0,
                                radius_km=3.0, finer_provider=StubProvider())
    assert r.finer_dem.status == "unavailable"
    assert "no DEM" in r.finer_dem.note.lower() or "fetch" in r.finer_dem.note.lower()


def test_terrain_no_dem_is_honest_unavailable():
    from geo.hydraulic import gather_terrain_evidence
    r = gather_terrain_evidence(None, None, plot_lat=1.0, plot_lon=1.0, radius_km=3.0)
    assert r.dem_provenance["status"] == "unavailable"
    assert r.neighborhood == {}
    assert r.caveats  # reason exposed
    assert r.deferred_flood_extents["status"] == "deferred"


def test_terrain_missing_gather_still_characterises_plot():
    """No OSM gather (or empty gather) must not crash; the plot/neighbourhood
    measurements and gate remain, feature samples simply absent."""
    from geo.hydraulic import gather_terrain_evidence
    dem = make_terrain_dem()
    r = gather_terrain_evidence(dem, None, plot_lat=1.0, plot_lon=1.0, radius_km=3.0,
                                finer_provider=_offset_provider(offset_m=0.0))
    assert r.plot["dem_elevation_m"] is not None
    assert r.neighborhood["status"] == "obtained"
    assert r.samples == [] and r.transect is None and r.low_points
    assert r.connectivity_statement  # gate still present


# --- Phase 1f: local-survey spec + high-res DEM sources (survey_spec.py) -------


def test_survey_gate_verbatim_and_no_fabrication():
    """The gates are verbatim and every requested measurement ships as
    None/unverified — nothing may be assumed or invented."""
    from geo.hydraulic import (
        SURVEY_GATE_STATEMENT,
        HIGH_RES_DEM_GATE_STATEMENT,
        produce_survey_spec,
    )
    assert "may be assumed, guessed, or fabricated" in SURVEY_GATE_STATEMENT
    assert "UNRESOLVED" in SURVEY_GATE_STATEMENT
    assert "solver is NOT run" in SURVEY_GATE_STATEMENT
    assert "never fused" in HIGH_RES_DEM_GATE_STATEMENT
    r = produce_survey_spec(None, None, plot_lat=1.0, plot_lon=1.0)
    assert r.survey_points
    for s in r.survey_points:
        assert s.measured_value is None, "spec must never carry a fabricated value"
        assert s.status == "unverified"


def test_survey_spec_derived_from_reconciled_features_osm_ids_present():
    """Spec points for bridges, barrier, canal/drain must carry the real OSM ids
    ('254573869'/'254573867'/'680091133'/'377207446') when present in a gather."""
    from geo.hydraulic import produce_survey_spec
    from geo.hydraulic.sources import ChannelReconciliation, EvidenceGatherResult
    from geo.hydraulic.evidence import EvidenceContract

    def _way(osm_id, kind, name=None):
        return {"osm_id": osm_id, "name": name,
                "tags": {"waterway": "river"} if kind == "river" else {}}

    g = EvidenceGatherResult(
        records=[], contract=EvidenceContract(1.0, 1.0), fetched_at="t",
        prologue="",
        raw_items={
            "channel_centerline": [_way("r1", "river", "Sutlej")],
            "channels_drains": [_way("377207446", "drain", "canal/drain")],
            "bridges_culverts": [_way("254573869", "crossing", "MDR55 bridge"),
                                 _way("254573867", "crossing", "MDR55 crossing 2")],
            "embankments_road_rail": [_way("680091133", "barrier", "railway")],
            "flood_control": [],
        },
        channel_reconciliation=ChannelReconciliation(
            resolved=True, main_stem_ids=["r1"]),
    )
    r = produce_survey_spec(g, None, plot_lat=1.0, plot_lon=1.0)
    ids = {s.source_osm_id for s in r.survey_points}
    assert "254573869" in ids
    assert "254573867" in ids
    assert "680091133" in ids
    assert "377207446" in ids
    cats = {s.category for s in r.survey_points}
    assert cats >= {"culvert_crossing", "barrier_crown", "drainage_invert",
                    "channel_bank", "benchmark", "plot_grading",
                    "property_boundary"}


def test_record_survey_points_refuses_unverified_and_requires_metadata():
    """record_survey_points accepts ONLY verified, fully-provenanced claims;
    everything else is refused with a reason; accepted points never change
    connectivity."""
    from geo.hydraulic import (
        SurveyPointSubmission,
        record_survey_points,
    )
    unverified = SurveyPointSubmission(
        category="channel_bank", target="bank", value_m=266.0,
        provenance="surveyor log", vertical_datum="orthometric",
        horizontal_system="EPSG:4326", accuracy_m=0.02, verified=False)
    verified = SurveyPointSubmission(
        category="channel_bank", target="bank", value_m=266.42,
        provenance="GNSS-RTK field run 2026-09-02", vertical_datum="EGM2008",
        horizontal_system="EPSG:4326 ground", accuracy_m=0.02, verified=True)
    bogus = SurveyPointSubmission(
        category="benchmark", target="BM", value_m=270.0, provenance="",
        vertical_datum="", horizontal_system="", accuracy_m=0.02, verified=True)
    res = record_survey_points([unverified, verified, bogus],
                               connectivity_status="unresolved")
    assert [d["value_m"] for d in res.accepted] == [266.42]
    assert len(res.refused) == 2
    assert res.refused[0]["verified"] is False
    assert "incomplete" in res.refused[1]["reason"]
    assert res.connectivity_status == "unresolved"
    assert "do NOT by themselves change connectivity" in res.note


def test_high_res_dem_matrix_is_honest_and_recommends():
    """Source statuses must not over-claim availability: unprobed source stays
    unverified; only the probe result may upgrade (or downgrade) a status.
    Cartosat-1 is recommended as the practical sub-30 m public candidate while
    the drone/GNSS-RTK survey is not a 'source' claim to reliance."""
    from geo.hydraulic import recommend_high_res_dem_sources
    srcs = recommend_high_res_dem_sources()
    by_name = {s.name: s for s in srcs}
    assert by_name["Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m)"].recommended
    assert all(
        s.status in {"available", "unavailable", "commercial", "unverified"}
        for s in srcs)
    assert by_name["National / state LiDAR (India)"].status == "unverified"
    craft = by_name["Drone photogrammetry / GNSS-RTK survey"]
    assert "primary" in craft.suitability_for_plot.lower() or \
        "resolver" in craft.suitability_for_plot.lower()
    probed = recommend_high_res_dem_sources(
        probe_results={"Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m)": "available"})
    assert next(s for s in probed if "Cartosat-1" in s.name).status == "available"


def test_survey_spec_connectivity_stays_unresolved_no_solver():
    """produce_survey_spec never resolves connectivity and never runs a solver;
    plot-level credibility stays False and gate text is embedded."""
    from geo.hydraulic import produce_survey_spec, UNRESOLVED_MESSAGE
    r = produce_survey_spec(None, None, plot_lat=1.0, plot_lon=1.0)
    assert r.connectivity_status == UNRESOLVED_MESSAGE
    assert r.plot_level_credible is False
    assert r.surveyed_elevations_integrated == 0
    assert any("UNRESOLVED" in c for c in r.caveats)


# --- Phase 1g: acquisition + integration workflow (acquire.py) -----------------


def _ten_m_dem(ps_deg=0.0001):
    """A ~11 m DEM centred on (1.0, 1.0) covering the plot — the sub-30 m case."""
    n = 400
    span = ps_deg * n
    t = AffineTransform(origin_lon=1.0 - span / 2, origin_lat=1.0 + span / 2,
                        pixel_size_lon=ps_deg, pixel_size_lat=ps_deg)
    yy = np.linspace(0, 1, n)[:, None] * np.ones((1, n))
    return DEM(elevation=100.0 - 50.0 * yy, transform=t, nodata=None,
               source_resolution_m=ps_deg * 111_320.0,
               simulation_grid_m=ps_deg * 111_320.0,
               horizontal_crs="EPSG:4326", vertical_datum="EGM96",
               dataset="Cartosat-1 (test)", provenance="test")


def test_acquisition_gate_verbatim_and_no_solver():
    from geo.hydraulic import ACQUISITION_GATE_STATEMENT, DEM_FILE_REQUIREMENTS
    assert "verified-acquisition gate" in ACQUISITION_GATE_STATEMENT
    assert "refused" in ACQUISITION_GATE_STATEMENT
    assert "never runs the hydraulic solver" in ACQUISITION_GATE_STATEMENT
    assert any("resolution" in r for r in DEM_FILE_REQUIREMENTS)


def test_dem_sub30_covers_plot_is_available_never_partial():
    """A real 11 m DEM covering the plot registers HIGH_RES_DEM as AVAILABLE;
    nothing is fabricated — the verdict follows the passed DEM."""
    from geo.hydraulic import register_dem
    dem = _ten_m_dem()
    r = register_dem(dem, dataset="Cartosat-1 (test)", vertical_datum="EGM96",
                     provenance="live acquisition", plot_lat=1.0, plot_lon=1.0,
                     resolution_m=11.0)
    assert r.evidence_status == "available"
    assert r.covers_plot and r.sub_30m


def test_dem_30m_is_partial_never_upgraded_to_available():
    """The existing 222 m/30 m-class DEM covering the plot must register PARTIAL:
    a coarse DEM can never satisfy the plot-level HIGH_RES_DEM evidence."""
    from geo.hydraulic import register_dem
    dem = make_terrain_dem()
    r = register_dem(dem, dataset="Copernicus GLO-30 (test)",
                     vertical_datum="EGM2008", provenance="test",
                     plot_lat=1.0, plot_lon=1.0, resolution_m=30.0)
    assert r.evidence_status == "partial"
    assert r.sub_30m is False
    assert "NOT sub-30 m" in r.reason


def test_inspect_dem_file_missing_and_unreadable_never_fabricated():
    """A missing or unreadable raster file is recorded as 'missing' with the
    failure reason — never upgraded to a DEM or to available evidence."""
    from geo.hydraulic import inspect_dem_file
    r = inspect_dem_file("/nonexistent/definitely_missing.tif",
                         plot_lat=1.0, plot_lon=1.0, dataset="Cartosat-1",
                         provenance="acquisition", vertical_datum="EGM96")
    assert r.evidence_status == "missing"
    assert "file not found" in r.reason
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tif") as junk:
        junk.write(b"this is not a geotiff")
        junk.flush()
        r2 = inspect_dem_file(junk.name, plot_lat=1.0, plot_lon=1.0,
                              dataset="Cartosat-1", provenance="acquisition",
                              vertical_datum="EGM96")
    assert r2.evidence_status == "missing"
    assert "unreadable raster" in r2.reason


def test_ingest_survey_refuses_every_unverified_row():
    """Rows that are unverified or lack required metadata are refused; only a
    verified, fully-provenanced row is accepted (LOCAL_SURVEY -> available)."""
    from geo.hydraulic import ingest_survey_points
    rows = [
        {"category": "channel_bank", "target": "bank", "value_m": 266.4,
         "provenance": "rtk 2026-09-02", "vertical_datum": "EGM2008",
         "horizontal_system": "EPSG:4326", "accuracy_m": 0.02,
         "verified": True},
        {"category": "plot_grading", "target": "yard", "value_m": 267.1,
         "provenance": "field book 01", "vertical_datum": "EGM2008",
         "horizontal_system": "EPSG:4326", "accuracy_m": 0.02,
         "verified": False},
        {"category": "benchmark", "target": "BM", "value_m": 271.0,
         "provenance": "", "vertical_datum": "", "horizontal_system": "",
         "accuracy_m": 0.02, "verified": True},
    ]
    out = ingest_survey_points(rows)
    assert out.integrated_count == 1
    assert out.evidence_status == "available"
    assert len(out.refused) == 2
    assert all("refused" in str(x["reason"]) or "refused" in str(x["reason"])
               for x in out.refused)


def test_integrate_into_contract_upgrades_from_missing():
    """After integrating a verified survey + sub-30 m DEM the contract's
    HIGH_RES_DEM/LOCAL_SURVEY rows flip to available and plot_level_credible can
    pass; a 30 m DEM keeps HIGH_RES_DEM partial so credibility stays False."""
    from geo.hydraulic import (
        EvidenceCategory, EvidenceContract, ingest_survey_points,
        integrate_into_contract, register_dem,
    )
    c = EvidenceContract(1.0, 1.0)
    dem_r = register_dem(_ten_m_dem(), dataset="Cartosat-1 (test)",
                         vertical_datum="EGM96", provenance="p", plot_lat=1.0,
                         plot_lon=1.0, resolution_m=11.0)
    surv = ingest_survey_points([{"category": "benchmark", "target": "BM",
                                  "value_m": 100.0, "provenance": "rtk",
                                  "vertical_datum": "EGM96",
                                  "horizontal_system": "EPSG:4326",
                                  "accuracy_m": 0.02, "verified": True}])
    integrate_into_contract(c, dem_result=dem_r, survey_result=surv)
    assert c.row(EvidenceCategory.HIGH_RES_DEM).status.value == "available"
    assert c.row(EvidenceCategory.LOCAL_SURVEY).status.value == "available"
    assert c.plot_level_credible is True
    # 30 m a like-DEM must NOT satisfy HIGH_RES_DEM.
    c2 = EvidenceContract(1.0, 1.0)
    coarse = register_dem(make_terrain_dem(), dataset="GLO-30 (test)",
                          vertical_datum="EGM2008", provenance="p", plot_lat=1.0,
                          plot_lon=1.0, resolution_m=30.0)
    integrate_into_contract(c2, dem_result=coarse)
    assert c2.row(EvidenceCategory.HIGH_RES_DEM).status.value == "partial"
    assert c2.plot_level_credible is False


def test_reassess_refused_until_fine_data_integrated():
    """Without AVAILABLE HIGH_RES_DEM or verified LOCAL_SURVEY, re-assessment is
    refused (stays UNRESOLVED) and the solver is never run."""
    from geo.hydraulic import EvidenceCategory, EvidenceContract, EvidenceRow, \
        EvidenceStatus, reassess_connectivity_after_acquisition
    c = EvidenceContract(1.0, 1.0)
    c.rows = [EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE,
                          EvidenceStatus.AVAILABLE, source="osm")]
    r = reassess_connectivity_after_acquisition(c, dem=None, proc=None,
                                                plot_lat=1.0, plot_lon=1.0)
    assert r.connectivity_status == "unresolved"
    assert "Refused by acquisition gate" in r.reason
    assert r.solver_run is False
    assert r.gate_applied is True


def test_reassess_runs_after_integration_but_never_solver():
    """Once fine evidence is integrated the assessment actually runs, but it can
    still return UNRESOLVED (flat reach, no proc) and NEVER invokes the solver."""
    from geo.hydraulic import (
        EvidenceCategory, EvidenceContract, EvidenceRow, EvidenceStatus,
        ingest_survey_points, integrate_into_contract, register_dem,
        reassess_connectivity_after_acquisition,
    )
    c = EvidenceContract(1.0, 1.0)
    c.rows = [
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE,
                    source="osm"),
        EvidenceRow(EvidenceCategory.CHANNELS_DRAINS, EvidenceStatus.AVAILABLE,
                    source="osm"),
    ]
    dem_r = register_dem(_ten_m_dem(), dataset="Cartosat-1 (test)",
                         vertical_datum="EGM96", provenance="p", plot_lat=1.0,
                         plot_lon=1.0, resolution_m=11.0)
    surv = ingest_survey_points([{"category": "benchmark", "target": "BM",
                                  "value_m": 100.0, "provenance": "rtk",
                                  "vertical_datum": "EGM96",
                                  "horizontal_system": "EPSG:4326",
                                  "accuracy_m": 0.02, "verified": True}])
    integrate_into_contract(c, dem_result=dem_r, survey_result=surv)
    r = reassess_connectivity_after_acquisition(c, dem=None, proc=None,
                                                plot_lat=1.0, plot_lon=1.0)
    assert r.gate_applied is True
    assert r.solver_run is False
    assert r.connectivity_status in ("unresolved", "not_connected", "connected")
    # No proc grid supplied -> the flat-check cannot resolve a path; honest.
    assert r.connectivity_status == "unresolved"

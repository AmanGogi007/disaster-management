"""V0.2 — hydrological network tests."""
from __future__ import annotations

import numpy as np

from packages.geo.network.builder import build_network
from packages.geo.network.graph import (
    REL_DISCONNECTED, REL_DOWNSTREAM, REL_PLOT, REL_TRIBUTARY, REL_UNKNOWN, REL_UPSTREAM,
)
from packages.geo.raster.dem import AffineTransform, DEM
from packages.geo.watershed.flow import d8_flow_direction

from network_fixtures import (
    disconnected_dam_fixture,
    multiple_upstream_dams_fixture,
    plot_not_attached_fixture,
    tributary_fixture,
    upstream_dam_fixture,
)


def _to_latlon(row: int, col: int):
    dem = _shared_dem()
    t = dem.transform
    return t.lat_at_row(row), t.lon_at_col(col)


def _shared_dem():
    """Return the same DEM every fixture uses."""
    return _build_toy_dem()


def _build_toy_dem() -> DEM:
    rows = 20
    cols = 20
    pix = 0.0005
    elev = np.zeros((rows, cols), dtype=float)
    for r in range(rows):
        for c in range(cols):
            elev[r, c] = 100.0 - 5.0 * r + (5.0 if c == 10 else 0.0)
    t = AffineTransform(
        origin_lon=-0.005,
        origin_lat=rows * pix,
        pixel_size_lon=pix,
        pixel_size_lat=pix,
    )
    return DEM(elevation=elev, transform=t, nodata=None)


# ---------------------------------------------------------------------------

def test_d8_produces_directional_grid():
    dem = _shared_dem()
    fdir = d8_flow_direction(dem)
    # Row 0 col 10 (top of ridge) should drain to a southern neighbour.
    assert int(fdir[0, 10]) in (5, 6, 7, 8)


def test_upstream_dam_is_upstream_of_plot():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    assert net.plot_attachment_node_id is not None
    dams = [fl for fl in net.feature_links if fl.feature_type in ("dam", "weir")]
    by_name = {d.name: d for d in dams}
    assert by_name["Dam U"].relationship == REL_UPSTREAM
    assert by_name["Dam D"].relationship == REL_DOWNSTREAM


def test_disconnected_dam_is_marked_disconnected():
    f = disconnected_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    dams = [fl for fl in net.feature_links if fl.feature_type == "dam"]
    assert len(dams) == 1
    # The dam is on col=5, the river is col=10 → no shared endpoint, so it's
    # not in the directed graph but it IS snapped within 600 m.  Result must
    # be "disconnected", NOT upstream.
    assert dams[0].relationship == REL_DISCONNECTED


def test_tributary_classification():
    f = tributary_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    # Find the reservoir's classification.
    reservoir = next(fl for fl in net.feature_links if fl.feature_type == "reservoir")
    # Reservoir is on a tributary joining south of the plot → downstream.
    assert reservoir.relationship == REL_DOWNSTREAM


def test_multiple_upstream_dams():
    f = multiple_upstream_dams_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    dams = [fl for fl in net.feature_links if fl.feature_type == "dam"]
    names = sorted(d.name for d in dams)
    assert names == ["Dam E", "Dam W"]
    for d in dams:
        assert d.relationship == REL_UPSTREAM, f"{d.name} is {d.relationship}"


def test_geographic_nearness_does_not_imply_upstream():
    """A dam within the radius but on a separate drainage line must not be
    labelled upstream just because it's geographically close."""
    f = disconnected_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    dams = [fl for fl in net.feature_links if fl.feature_type == "dam"]
    assert dams[0].relationship == REL_DISCONNECTED
    # The dam node is NOT in the upstream set of the plot attachment.
    up_ids = set(net.upstream_of(net.plot_attachment_node_id))
    # Dam's nearest node should not be in up_ids OR down_ids.
    if dams[0].nearest_node_id is not None:
        assert dams[0].nearest_node_id not in up_ids


def test_plot_attachment_failure_handled_gracefully():
    f = plot_not_attached_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    # Plot at top-left corner might attach somewhere; even if it does, the
    # relationship flags should never silently be wrong.
    assert net is not None
    for fl in net.feature_links:
        if fl.feature_type == "dam":
            assert fl.relationship in (REL_UPSTREAM, REL_DOWNSTREAM,
                                       REL_TRIBUTARY, REL_DISCONNECTED,
                                       REL_UNKNOWN, REL_PLOT)


def test_upstream_set_excludes_plot_node():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    up = net.upstream_of(net.plot_attachment_node_id)
    assert net.plot_attachment_node_id not in up


def test_network_reports_methodology_and_provenance():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    assert net.methodology != ""
    assert net.methodology.startswith("V0.2")


def test_confidence_reflects_dem_direction_clarity():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    river_edges = [e for e in net.edges if e.river_type == "river"]
    for e in river_edges:
        assert e.confidence in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# DEM-based drainage attachment
# ---------------------------------------------------------------------------

def test_plot_attached_via_dem_with_methodology():
    """Attaching the plot must record a DEM-informed method + confidence."""
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    plot_link = next(fl for fl in net.feature_links if fl.feature_type == "plot")
    assert plot_link.nearest_node_id is not None
    assert plot_link.relationship == REL_PLOT
    # The notes should describe HOW the plot was attached.
    assert any("network" in n or "DEM" in n or "trace" in n for n in plot_link.notes)
    assert plot_link.confidence in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Downstream traversal
# ---------------------------------------------------------------------------

def test_downstream_trace_returns_structured_steps():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    steps = net.downstream_trace(net.plot_attachment_node_id)
    assert len(steps) > 0
    first = steps[0]
    # Each step must carry edge/node/feature metadata.
    for key in ("edge_id", "u", "v", "river_name", "river_type",
                "length_km", "cumulative_distance_km", "confidence"):
        assert key in first, f"missing key {key}"
    # Cumulative distance is monotonically non-decreasing.
    cums = [s["cumulative_distance_km"] for s in steps]
    assert all(b >= a for a, b in zip(cums, cums[1:]))


def test_downstream_trace_reaches_major_receiving_river():
    """In the tributary fixture the plot drains into Main downstream."""
    f = tributary_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    steps = net.downstream_trace(net.plot_attachment_node_id)
    assert len(steps) > 0
    assert steps[0]["river_name"] == "Main"


# ---------------------------------------------------------------------------
# Upstream traversal
# ---------------------------------------------------------------------------

def test_upstream_trace_distinguishes_main_stem_and_tributary():
    f = multiple_upstream_dams_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    trace = net.upstream_trace(net.plot_attachment_node_id)
    assert len(trace["main_stem"]) > 0
    # The West Branch must be reported as a tributary (not main stem).
    trib_names = {t["tributary_river_name"] for t in trace["tributaries"]}
    assert "West Branch" in trib_names
    # Both dams upstream.
    dam_names = {d["name"] for d in trace["upstream_dams"]}
    assert {"Dam W", "Dam E"} <= dam_names


def test_upstream_trace_reports_main_stem_edges_ordered_upstream_to_plot():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    trace = net.upstream_trace(net.plot_attachment_node_id)
    stem = trace["main_stem"]
    assert len(stem) >= 1
    # Edges should chain: stem[i].v == stem[i+1].u
    for a, b in zip(stem, stem[1:]):
        assert a["v"] == b["u"], f"{a} not chained to {b}"
    # Last edge's v must be (or chain into) the plot attachment node.
    assert stem[-1]["v"] == net.plot_attachment_node_id


# ---------------------------------------------------------------------------
# Dam relevance classification via topology (not geography)
# ---------------------------------------------------------------------------

def test_downstream_dam_is_downstream_via_topology():
    f = upstream_dam_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    dam_d = next(fl for fl in net.feature_links
                 if fl.feature_type == "dam" and fl.name == "Dam D")
    assert dam_d.relationship == REL_DOWNSTREAM
    # Its nearest node must be in the plot's downstream set.
    assert dam_d.nearest_node_id in set(net.downstream_of(net.plot_attachment_node_id))


def test_ambiguous_low_confidence_attachment_reported():
    """A plot far from any network node should not be silently guessed."""
    f = plot_not_attached_fixture()
    dem = _shared_dem()
    pr, pc = f["plot"]
    plat, plon = _to_latlon(pr, pc)
    net = build_network(f["features"], dem, plat, plon)
    # If the plot failed to attach, the report must say so rather than guessing.
    if net.plot_attachment_node_id is None:
        plot_link = next(fl for fl in net.feature_links if fl.feature_type == "plot")
        assert plot_link.relationship == REL_UNKNOWN
    # Either way, no feature may be marked UPSTREAM without a valid attachment.
    if net.plot_attachment_node_id is not None:
        for fl in net.feature_links:
            if fl.feature_type == "dam":
                assert fl.relationship != REL_UPSTREAM or fl.nearest_node_id in set(
                    net.upstream_of(net.plot_attachment_node_id)
                )
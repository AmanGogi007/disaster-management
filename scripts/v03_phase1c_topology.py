"""V0.3 Phase 1c — channel reconciliation + local hydraulic topology.

Builds on the Phase 1b evidence layer:

1. Reconciles which OSM river way(s) form the Sutlej main stem — via OSM's own
   network topology (shared junction nodes + coincident endpoints), never by
   guesswork.  Remaining unconnected ways are reported, not dropped.
2. Assembles the descriptive local topology (channel, local drains, potential
   barriers, crossings, flood-control structures, DEM-derived reach direction).
3. Re-runs connectivity so the verdict stays evidence-gated (UNRESOLVED on the
   flat 30 m reach).

NO flood solver.  OSM presence is NOT treated as proof of hydraulic
connectivity.  Missing/weak evidence is never converted into an assumption.

Writes:
    simulations/outputs/local_topology.json
    simulations/outputs/local_topology.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from geo.hydraulic import (  # noqa: E402
    assess_connectivity,
    build_local_topology,
    gather_plot_evidence,
)
from geo.terrain.preprocess import preprocess_dem  # noqa: E402
from geo.terrain.providers.copernicus import CopernicusGLO30Provider  # noqa: E402

PLOT = {"lat": 31.05, "lon": 76.53}
CORRIDOR = {"south": 30.98, "west": 76.30, "north": 31.47, "east": 76.68}
RADIUS_KM = 3.0
JOIN_TOLERANCE_M = 75.0

STATUS_MD = {
    "obtained": "obtained",
    "unavailable": "unavailable",
    "insufficient": "insufficient resolution",
    "conflicting": "conflicting",
}


def load_corridor():
    prov = CopernicusGLO30Provider()
    return prov.get_dem_bbox(
        CORRIDOR["south"], CORRIDOR["west"], CORRIDOR["north"], CORRIDOR["east"]
    ).dem


def build_markdown(g, topo, conn) -> str:
    L = []
    L.append("# V0.3 Phase 1c — Channel Reconciliation + Local Hydraulic Topology")
    L.append("")
    L.append(f"_Status: reconciliation + topology complete — awaiting review, no solver._")
    L.append("")
    L.append(f"- Plot: `{PLOT['lat']}, {PLOT['lon']}` (Ropar)")
    L.append(f"- Evidence radius: `{RADIUS_KM} km`; endpoint join tolerance: `{JOIN_TOLERANCE_M} m`")

    # ---- 1. Channel reconciliation ----
    L.append("")
    L.append("## 1. Sutlej main-stem reconciliation")
    L.append("")
    c = g.channel_reconciliation
    L.append(f"**Resolved:** `{c.resolved}` — confidence `{c.confidence}`")
    L.append("")
    L.append("| role | OSM id | name | min distance to plot (km) | length (km) |")
    L.append("|------|--------|------|--------------------------|-------------|")
    for w in c.ways:
        L.append(f"| {w['role']} | `{w['osm_id']}` | {w['name'] or '—'} | "
                 f"{w['distance_km'] or '—'} | {w['length_km'] or '—'} |")
    L.append("")
    L.append(f"**Min distance from the main stem to the plot:** `{c.min_plot_distance_km} km`")
    if c.conflicts:
        L.append("")
        L.append("**Conflicts / caveats (kept visible, not silently fixed):**")
        for x in c.conflicts:
            L.append(f"- {x}")
    L.append("")
    L.append(f"Reconciliation method: connected-component analysis over shared "
             f"junction node ids and near-coincident endpoints "
             f"(≤ {JOIN_TOLERANCE_M} m). Unconnected ways are reported above as "
             f"`unconnected`, never dropped.")

    # ---- 2. Local topology ----
    L.append("")
    L.append("## 2. Local hydraulic topology (descriptive)")
    L.append("")

    if topo.local_channels:
        L.append("### Local channels / drains")
        L.append("")
        L.append("| OSM id | kind | name | min dist (km) | length (km) |")
        L.append("|--------|------|------|---------------|-------------|")
        for ch in topo.local_channels:
            L.append(f"| `{ch['osm_id']}` | {ch['kind']} | {ch['name'] or '—'} | "
                     f"{ch['min_distance_km'] or '—'} | {ch['length_km'] or '—'} |")
        L.append("")

    if topo.barriers:
        L.append("### Potential barriers (roads/railways/embankments)")
        L.append("")
        L.append("| OSM id | kind | name | min dist (km) | note |")
        L.append("|--------|------|------|---------------|------|")
        for b in topo.barriers:
            L.append(f"| `{b['osm_id']}` | {b['kind']} | {b['name'] or '—'} | "
                     f"{b['min_distance_km'] or '—'} | {b['note']} |")
        L.append("")
    else:
        L.append("### Potential barriers — none found.")
        L.append("")

    if topo.crossings:
        L.append("### Crossings (bridges / culverts)")
        L.append("")
        L.append("| OSM id | kind | name | on waterway? | min dist (km) |")
        L.append("|--------|------|------|--------------|---------------|")
        for cr in topo.crossings:
            L.append(f"| `{cr['osm_id']}` | {cr['kind']} | {cr['name'] or '—'} | "
                     f"{'yes' if cr['on_waterway'] else 'no'} | {cr['min_distance_km'] or '—'} |")
        L.append("")
    else:
        L.append("### Crossings — none found.")
        L.append("")

    if topo.flood_structures:
        L.append("### Flood-control structures")
        L.append("")
        L.append("| OSM id | kind | name | min dist (km) |")
        L.append("|--------|------|------|---------------|")
        for f in topo.flood_structures:
            L.append(f"| `{f['osm_id']}` | {f['kind']} | {f['name'] or '—'} | "
                     f"{f['min_distance_km'] or '—'} |")
        L.append("")
    else:
        L.append("### Flood-control structures — none found.")
        L.append("")

    # ---- 3. Reach direction ----
    L.append("## 3. Flow direction at the plot reach")
    L.append("")
    L.append(f"- **Reach direction status:** `{topo.reach_direction_status}`")
    L.append(f"- **Plot cell:** `{topo.plot_cell}`")
    L.append(f"- **Note:** {topo.flow_direction_note}")

    # ---- 4. Connectivity verdict ----
    L.append("")
    L.append("## 4. Connectivity verdict (remains evidence-gated)")
    L.append("")
    L.append(f"- **Assessed result:** `{conn.status}`")
    L.append(f"- **Reason:** `{conn.reason}`")
    L.append("")
    L.append("| check | passed |")
    L.append("|-------|--------|")
    for ch in conn.checks:
        L.append(f"| {ch['check']} | `{ch['passed']}` |")
    L.append("")
    L.append("> Because `terrain_reach_resolvable` is false, connectivity is "
             "**UNRESOLVED** — the flat 30 m reach cannot be routed, so no path "
             "is fabricated and no flood depth is computed (design §J.1). The "
             "topology above is descriptive only.")
    L.append("")
    L.append("## Caveats (explicit, never papered over)")
    L.append("")
    for x in topo.caveats:
        L.append(f"- {x}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("=== V0.3 Phase 1c: reconcile + topology ===")
    g = gather_plot_evidence(PLOT["lat"], PLOT["lon"], radius_km=RADIUS_KM)
    rec = g.channel_reconciliation
    print(f"  channel reconciled: resolved={rec.resolved}, "
          f"main_stem={rec.main_stem_ids}, min={rec.min_plot_distance_km} km")

    dem = load_corridor()
    proc = preprocess_dem(dem, pour_lat=PLOT["lat"], pour_lon=PLOT["lon"])
    topo = build_local_topology(g, dem, proc,
                                plot_lat=PLOT["lat"], plot_lon=PLOT["lon"])
    print(f"  topology: {len(topo.local_channels)} drains, "
          f"{len(topo.barriers)} barriers, {len(topo.crossings)} crossings, "
          f"reach={topo.reach_direction_status}")

    conn = assess_connectivity(dem, proc, g.contract,
                               plot_lat=PLOT["lat"], plot_lon=PLOT["lon"])
    print(f"  connectivity: {conn.status}")

    out_dir = ROOT / "simulations" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "local_topology.md"
    md_path.write_text(build_markdown(g, topo, conn), encoding="utf-8")

    payload = {
        "phase": "V0.3 Phase 1c",
        "fetched_at_utc": g.fetched_at,
        "plot": PLOT,
        "corridor_bbox": CORRIDOR,
        "radius_km": RADIUS_KM,
        "join_tolerance_m": JOIN_TOLERANCE_M,
        "evidence": {
            "records": [r.to_dict() for r in g.records],
        },
        "channel_reconciliation": rec.to_dict(),
        "topology": topo.to_dict(),
        "reconciliation": {
            "plot_level_credible": g.contract.plot_level_credible,
            "missing_plot_level_evidence": [
                e.value for e in g.contract.missing_plot_level_evidence()
            ],
            "connectivity": {
                "status": conn.status,
                "reason": conn.reason,
                "checks": conn.checks,
            },
        },
    }
    json_path = out_dir / "local_topology.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"\nWrote:\n  {md_path}\n  {json_path}")


if __name__ == "__main__":
    main()
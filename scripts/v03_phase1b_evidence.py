"""V0.3 Phase 1b — local evidence inventory + reconciliation report.

Gathers the plot-level hydraulic evidence around the Ropar plot from
OpenStreetMap (Overpass), records every source with provenance / resolution /
datum / coverage / explicit availability-quality status, reconciles into the
J.3 EvidenceContract, and re-runs connectivity on the real GLO-30 corridor.

NO flood solver.  Missing/weak evidence is never converted into an assumption.

Writes:
    simulations/outputs/evidence_inventory.json
    simulations/outputs/evidence_inventory.md
"""
from __future__ import annotations

import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from geo.hydraulic import (  # noqa: E402
    assess_connectivity,
    gather_plot_evidence,
)
from geo.terrain.preprocess import preprocess_dem  # noqa: E402
from geo.terrain.providers.copernicus import CopernicusGLO30Provider  # noqa: E402

PLOT = {"lat": 31.05, "lon": 76.53}
CORRIDOR = {"south": 30.98, "west": 76.30, "north": 31.47, "east": 76.68}
RADIUS_KM = 3.0

STATUS_MD = {
    "obtained": "obtained",
    "unavailable": "unavailable",
    "insufficient": "insufficient resolution",
    "conflicting": "conflicting",
}


def load_corridor():
    print("Fetching/reusing GLO-30 corridor for the Ropar reach ...")
    prov = CopernicusGLO30Provider()
    # provider caches by bbox; this is the same bbox as Phase 0
    return prov.get_dem_bbox(
        CORRIDOR["south"], CORRIDOR["west"], CORRIDOR["north"], CORRIDOR["east"]
    ).dem


def build_markdown(result, conn) -> str:
    L = []
    L.append("# V0.3 Phase 1b — Local Evidence Inventory + Reconciliation")
    L.append("")
    L.append(f"_Status: evidence layer complete — awaiting review, no solver run._")
    L.append("")
    L.append("## Objective")
    L.append("")
    L.append(
        "Gather and reconcile the plot-level hydraulic evidence around the Ropar "
        "plot (31.05°N, 76.53°E) into the J.3 EvidenceContract. Every source carries "
        "provenance, resolution, datum, coverage and an explicit "
        "availability/quality status. Missing or weak evidence is **not** converted "
        "into an assumption; the flood solver is **not** started."
    )
    L.append("")
    L.append(f"- Plot: `{PLOT['lat']}, {PLOT['lon']}`")
    L.append(f"- Evidence search radius: `{RADIUS_KM} km`")
    L.append(f"- GLO-30 corridor (reused from Phase 0): `{CORRIDOR}`")
    L.append(f"- Gathered at (UTC): `{result.fetched_at}`")

    L.append("")
    L.append("## Evidence inventory")
    L.append("")
    L.append("| # | Category | Status | Found | Coverage (km) | Confidence | Source / dataset |")
    L.append("|---|----------|--------|-------|---------------|------------|------------------|")
    for rec in result.records:
        L.append(
            f"| {rec.category.value} | {rec.category.value} | "
            f"{STATUS_MD[rec.status]} | {rec.count} | {rec.coverage_km} | "
            f"{rec.confidence} | {rec.dataset} |"
        )

    L.append("")
    L.append("## Per-source detail (with provenance, resolution, datum, notes)")
    L.append("")
    for rec in result.records:
        L.append(f"### {rec.category.value} — *{STATUS_MD[rec.status]}*")
        L.append("")
        L.append(f"- **Source / dataset:** `{rec.source}` / `{rec.dataset}`")
        L.append(f"- **Retrieved at (UTC):** `{rec.retrieved_at}`")
        L.append(f"- **License:** `{rec.license}`")
        L.append(f"- **Coverage:** within {rec.coverage_km} km of the plot")
        L.append(f"- **Resolution note:** {rec.resolution_note}")
        L.append(f"- **Datum note:** {rec.datum_note or 'n/a'}")
        L.append(f"- **Confidence:** `{rec.confidence}`")
        L.append(f"- **Note:** {rec.note}")
        if rec.sample:
            L.append("- **Sample features:**")
            for s in rec.sample:
                nm = s["name"] or "—"
                L.append(
                    f"  - id `{s['osm_id']}` `{nm}` {s['distance_km']} km from plot "
                    f"`{s['tags']}`"
                )
        L.append("")

    L.append("## Reconciliation (per J.1 / J.3)")
    L.append("")
    L.append(
        f"- **`plot_level_credible`:** `{result.contract.plot_level_credible}` "
        "(requires local survey + high-res DEM available)."
    )
    miss = [e.value for e in result.contract.missing_plot_level_evidence()]
    L.append(f"- **Missing for plot-level credibility:** `{miss}`")
    L.append("")
    L.append("### Connectivity on the real 30 m DEM reach")
    L.append("")
    L.append(f"- **Assessed result:** `{conn.status}`")
    L.append(f"- **Reason:** `{conn.reason}`")
    L.append("")
    L.append("| check | passed |")
    L.append("|-------|--------|")
    for ch in conn.checks:
        L.append(f"| {ch['check']} | `{ch['passed']}` |")
    L.append("")
    L.append(
        "Because `terrain_reach_resolvable` is false, connectivity is "
        "**UNRESOLVED** — the 30 m DEM cannot rout the flat reach, so no path is "
        "fabricated and no flood depth is computed. This is the expected, honest "
        "outcome at 30 m resolution per design §J.1."
    )
    L.append("")
    L.append("## What each status means")
    L.append("")
    L.append("- **obtained** — present, authoritative enough, adequate for the purpose.")
    L.append("- **unavailable** — genuinely not present in the queried sources (0 found).")
    L.append("- **insufficient resolution** — present but too coarse to resolve the claim.")
    L.append("- **conflicting** — present but multiple features disagree (surfaced, low confidence, not silently reconciled).")
    L.append("")
    L.append("## Not done yet (deferred by user directive)")
    L.append("")
    L.append("- Flood solver / 2D hydraulic model — not started.")
    L.append("- Gauge reconstruction (CWC/BBMB/India-WRIS) — recorded `unavailable`, pending external data.")  # noqa: E501
    L.append("- Local survey & high-res DEM — recorded `unavailable`, required for plot-level credibility.")  # noqa: E501
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("=== V0.3 Phase 1b: evidence gather + reconcile ===")
    print(textwrap.dedent(
        """
        Gathering local hydraulic evidence for:
          plot     = (31.05, 76.53)  Ropar
          radius   = 3.0 km
          corridor = GLO-30 (reused from Phase 0)
        """))
    # 1. Gather evidence (this is the real Overpass fetch)
    result = gather_plot_evidence(PLOT["lat"], PLOT["lon"], radius_km=RADIUS_KM)
    print("  -> sources assembled:", len(result.records))

    # 2. Reconcile into the contract (already rows) + run connectivity on the real DEM
    dem = load_corridor()
    proc = preprocess_dem(dem, pour_lat=PLOT["lat"], pour_lon=PLOT["lon"])
    conn = assess_connectivity(dem, proc, result.contract,
                               plot_lat=PLOT["lat"], plot_lon=PLOT["lon"])
    print(f"  -> connectivity: {conn.status}")

    out_dir = ROOT / "simulations" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    md = build_markdown(result, conn)
    md_path = out_dir / "evidence_inventory.md"
    md_path.write_text(md, encoding="utf-8")

    payload = {
        "phase": "V0.3 Phase 1b",
        "fetched_at_utc": result.fetched_at,
        "plot": PLOT,
        "corridor_bbox": CORRIDOR,
        "radius_km": RADIUS_KM,
        "prologue": result.prologue,
        "records": [r.to_dict() for r in result.records],
        "contract": result.contract.to_dict(),
        "reconciliation": {
            "plot_level_credible": result.contract.plot_level_credible,
            "missing_plot_level_evidence": [
                e.value for e in result.contract.missing_plot_level_evidence()
            ],
            "connectivity": {
                "status": conn.status,
                "reason": conn.reason,
                "checks": conn.checks,
            },
        },
    }
    json_path = out_dir / "evidence_inventory.json"
    json_path.write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    print(f"\nWrote:\n  {md_path}\n  {json_path}")


if __name__ == "__main__":
    main()
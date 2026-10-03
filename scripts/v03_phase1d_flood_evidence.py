"""V0.3 Phase 1d — authoritative flood evidence report.

Gathers gauge observations + documented historical flood extents relevant to
the reconciled Sutlej corridor (CWC / India-WRIS / BBMB / NIH / NASA via NWDP
and official publications), preserving provenance, datum, timestamps, spatial
& temporal coverage, uncertainty and explicit availability status.

NO gauge reading or historical extent is converted into a plot flood depth.
NO 2D flood solver is run.

Writes:
    simulations/outputs/flood_evidence.json
    simulations/outputs/flood_evidence.md
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from geo.hydraulic import (  # noqa: E402
    FloodEvidenceKind,
    GAUGE_TO_PLOT_STATEMENT,
    gather_flood_evidence,
)

PLOT = {"lat": 31.05, "lon": 76.53}
RADIUS_KM = 3.0

STATUS_MD = {
    "obtained": "obtained",
    "unavailable": "unavailable",
    "insufficient": "insufficient resolution",
    "conflicting": "conflicting",
}


def build_markdown(res) -> str:
    kinds = {
        FloodEvidenceKind.GAUGE_SERIES.value: "Gauge series",
        FloodEvidenceKind.RESERVOIR_LEVEL.value: "Reservoir level (upstream control)",
        FloodEvidenceKind.PEAK_FLOW_RECORD.value: "Historical peak flow",
        FloodEvidenceKind.FLOOD_EXTENT.value: "Documented flood extent",
        FloodEvidenceKind.NETWORK_STATUS.value: "Coverage/network status",
    }
    L = []
    L.append("# V0.3 Phase 1d — Authoritative Flood Evidence (Sutlej / Ropar corridor)")
    L.append("")
    L.append("_Status: evidence layer complete — no solver run; gauge values are "
             "never converted into plot depths._")
    L.append("")
    L.append(f"- Plot: `{PLOT['lat']}, {PLOT['lon']}` (Ropar)")
    L.append(f"- Local search radius: `{RADIUS_KM} km`")
    L.append(f"- Gathered at (UTC): `{res.fetched_at}`")
    L.append("")
    L.append("## The gate that governs these numbers")
    L.append("")
    L.append(f"> {GAUGE_TO_PLOT_STATEMENT}")
    L.append("")
    L.append("## Availability summary")
    L.append("")
    L.append("| Kind | Records by status |")
    L.append("|------|-------------------|")
    by_kind: dict[str, dict[str, int]] = {}
    for r in res.records:
        b = by_kind.setdefault(kinds.get(r.kind.value, r.kind.value), {})
        b[r.status] = b.get(r.status, 0) + 1
    for k, b in by_kind.items():
        statuses = ", ".join(f"{s}: {n}" for s, n in sorted(b.items()))
        L.append(f"| {k} | {statuses} |")
    L.append("")
    L.append("## Per-record detail (provenance · datum · coverage · uncertainty)")
    L.append("")
    for r in res.records:
        L.append(f"### {r.title} — *{STATUS_MD.get(r.status, r.status)}*")
        L.append("")
        L.append(f"- **Kind:** `{r.kind.value}`")
        L.append(f"- **Source org / dataset:** `{r.source_org}` / `{r.dataset}`")
        L.append(f"- **Source URL:** `{r.source_url or 'n/a'}`")
        L.append(f"- **Retrieved at (UTC):** `{r.retrieved_at or 'n/a (cited)'}`")
        L.append(f"- **License:** `{r.license or 'n/a'}`")
        L.append(f"- **Spatial coverage:** {r.spatial_coverage}")
        L.append(f"- **Temporal coverage:** {r.temporal_coverage}")
        L.append(f"- **Units:** `{r.units or 'n/a'}`")
        L.append(f"- **Datum note:** {r.datum_note or 'n/a'}")
        L.append(f"- **Resolution note:** {r.resolution_note or 'n/a'}")
        L.append(f"- **Confidence:** `{r.confidence}`")
        if r.uncertainty_note:
            L.append(f"- **Uncertainty:** {r.uncertainty_note}")
        L.append(f"- **Note:** {r.note or 'n/a'}")
        if r.sample:
            L.append("- **Sample values:**")
            for s in r.sample:
                L.append(f"  - `{s}`")
        L.append("")
    L.append("## Why the Ropar-reach gauge stays UNAVAILABLE (stated, not silent)")
    L.append("")
    L.append(
        "- CWC flood-forecasting network has **no station in Punjab**; the single "
        "site added in 2019 is inactive; no level-forecast station exists anywhere "
        "in the Sutlej basin (CWC sites are monitoring-only, far upstream in HP)."
    )
    L.append(
        "- The NWDP machine-readable **CWC river-level package has no "
        "Indus/Sutlej resource** (peninsular basins only); the discharge package "
        "has no Indus-system state resource. The **BBMB manual-daily Bhakra "
        "resource contains placeholder-valued rows** (1,2,3,4,5 m −999) — "
        "recorded `insufficient`, never treated as observations."
    )
    L.append(
        "- The live BBMB daily bulletin is **unreachable from this environment** "
        "(fetch failure, retried); indexed snapshots (2025-09-04, 2026-08-21) are "
        "recorded with FRL/MWL constants. The only genuine in-catchment controller "
        "is Bhakra Reservoir — upstream-boundary evidence, not a Ropar plot depth."
    )
    L.append("")
    L.append("## Deferred (next steps, not run here)")
    L.append("")
    L.append("- GFD/DFO corridor-intersection extraction for 2000–2018 events.")
    L.append("- Download + station-filter NWDP CWC/BBMB CSVs when a Sutlej resource "
             "exists; re-verify BBMB Bhakra telemetry file (1970–2025, 12 MB).")
    L.append("- Establish the hydraulic relationship (solver phase): Bhakra release → "
             "Ropar reach flow → terrain → barriers → plot.")
    L.append("- Local survey + high-res DEM (still required for plot-level credibility).")
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("=== V0.3 Phase 1d: authoritative flood evidence ===")
    print(textwrap.dedent(
        f"""
        Gathering gauge + documented flood-extent evidence for:
          plot   = ({PLOT['lat']}, {PLOT['lon']})  Ropar
          radius = {RADIUS_KM} km
        Sources: CWC / India-WRIS / BBMB / NIH / NASA via NWDP + official docs.
        """))
    res = gather_flood_evidence(PLOT["lat"], PLOT["lon"], radius_km=RADIUS_KM)
    for r in res.records:
        print(f"  [{r.status:>13}] {r.title}")

    out_dir = ROOT / "simulations" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "flood_evidence.md"
    md_path.write_text(build_markdown(res), encoding="utf-8")
    json_path = out_dir / "flood_evidence.json"
    payload = {
        "phase": "V0.3 Phase 1d",
        "fetched_at_utc": res.fetched_at,
        "plot": PLOT,
        "radius_km": RADIUS_KM,
        "gauge_to_plot_statement": res.gauge_to_plot_statement,
        "portal_probe": res.portal_probe,
        "records": [r.to_dict() for r in res.records],
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote:\n  {md_path}\n  {json_path}")


if __name__ == "__main__":
    main()
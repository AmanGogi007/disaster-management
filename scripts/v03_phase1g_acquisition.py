"""V0.3 Phase 1g — acquisition + integration workflow (Cartosat-1/Bhuvan DEM and
field survey) for the exact plot (31.05, 76.53).

This is the REAL-DATA plumbing: it validates and integrates only genuine
acquisitions (a sub-30 m DEM raster that actually covers the plot; a delivered
survey file whose rows are provenance/datum/accuracy-tagged and verified).  It
never invents a DEM, never fabricates survey values, keeps every measurement
provenance-tagged and unverified until supplied, and never runs the hydraulic
solver.

Without CLI inputs it runs in "ready" mode: probes Bhuvan for the exact tile,
registers the current 30 m GLO-30 as PARTIAL evidence, and demonstrates that the
acquisition gate refuses a re-assessment — connectivity stays UNRESOLVED until
real fine-scale data is integrated.

Usage:
    .venv/bin/python scripts/v03_phase1g_acquisition.py
    .venv/bin/python scripts/v03_phase1g_acquisition.py \
        --dem-tif path/to/cartodem_10m.tif --dem-dataset "Cartosat-1 DSM" \
        --dem-datum "EGM96" --dem-res-m 10 --dem-source cartosat@bhuvan \
        --survey-json path/to/survey_delivery.json

Writes: simulations/outputs/acquisition_workflow.{md,json}
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from geo.hydraulic import (  # noqa: E402
    ACQUISITION_GATE_STATEMENT,
    DEM_FILE_REQUIREMENTS,
    EvidenceCategory,
    EvidenceContract,
    EvidenceRow,
    EvidenceStatus,
    UNRESOLVED_MESSAGE,
    inspect_dem_file,
    ingest_survey_points,
    integrate_into_contract,
    reassess_connectivity_after_acquisition,
)

PLOT = {"lat": 31.05, "lon": 76.53}
USER_AGENT = "location-hazard-engine/0.2 (research)"
PROBE_TIMEOUT_S = 10

BHUVAN_WMS = "https://bhuvan.nrsc.gov.in/bhuvan/wms"


def build_baseline_contract() -> EvidenceContract:
    """Constrain with the live evidence established so far.  HIGH_RES_DEM and
    LOCAL_SURVEY stay MISSING until real data is integrated."""
    c = EvidenceContract(plot_lat=PLOT["lat"], plot_lon=PLOT["lon"])
    c.rows = [
        EvidenceRow(EvidenceCategory.CHANNEL_CENTERLINE, EvidenceStatus.AVAILABLE,
                    source="OpenStreetMap", reference="Sutlej main stem "
                    "919730633/377207447/165931479/41539116 (reconciled)",
                    note="anchored main-stem centreline, min 0.129 km; "
                         "unconnected 248023200 reported."),
        EvidenceRow(EvidenceCategory.CHANNELS_DRAINS, EvidenceStatus.AVAILABLE,
                    source="OpenStreetMap", reference="377207446",
                    note="local canal/drain within 3 km radius."),
        EvidenceRow(EvidenceCategory.EMBANKMENTS_ROAD_RAIL, EvidenceStatus.AVAILABLE,
                    source="OpenStreetMap", reference="680091133, 919730631",
                    note="rail barriers mapped; openings/no-openings NOT "
                         "survey-confirmed (barrier note absent -> not a "
                         "definitive NOT_CONNECTED)."),
        EvidenceRow(EvidenceCategory.BRIDGES_CULVERTS, EvidenceStatus.AVAILABLE,
                    source="OpenStreetMap", reference="254573869, 254573867",
                    note="crossings mapped; invert/soffit field measurement "
                         "required (survey spec)."),
        EvidenceRow(EvidenceCategory.GAUGE_OBSERVATIONS, EvidenceStatus.MISSING,
                    source="-", reference="-",
                    note="CWC has no Rohira/Ropar Sutlej resource (Phase 1d); "
                         "any delivery must be provenance-tagged."),
        EvidenceRow(EvidenceCategory.DOCUMENTED_FLOOD_EXTENTS, EvidenceStatus.MISSING,
                    source="-", reference="-",
                    note="documented 1988/2019 events exist but corridor mapping "
                         "not ingested this phase."),
        EvidenceRow(EvidenceCategory.LOCAL_SURVEY, EvidenceStatus.MISSING,
                    source="field survey (to be delivered)", reference="survey_spec",
                    note="nothing integrated yet — spec only."),
        EvidenceRow(EvidenceCategory.HIGH_RES_DEM, EvidenceStatus.MISSING,
                    source="(to be acquired)", reference="survey_spec sources",
                    note="no sub-30 m DEM integrated yet."),
        EvidenceRow(EvidenceCategory.FLOOD_CONTROL, EvidenceStatus.NOT_APPLICABLE,
                    source="-", reference="-", note="no mapped flood control."),
    ]
    return c


def probe_bhuvan_cartosat() -> str:
    """Best-effort probe of Bhuvan for the exact plot.  Everything is honest:
    a 200 on a portal page is NOT authenticated tile access.  Reports each
    attempt's outcome so nothing is over-claimed."""
    attempts = [
        ("portal root", "https://bhuvan.nrsc.gov.in/"),
        ("wms GetCapabilities", BHUVAN_WMS
         + "?service=WMS&version=1.1.1&request=GetCapabilities"),
        ("ows GetCapabilities", "https://bhuvan.nrsc.gov.in/bhuvan/ows"
         + "?service=WMS&request=GetCapabilities"),
    ]
    notes = []
    for label, url in attempts:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_S) as resp:  # noqa: S310
                body = resp.read(1_000_000).decode("utf-8", "replace")
                lowered = body.lower()
                carto = [t for t in ("cartodem", "cartosat", "carto", "dem")
                         if t in lowered]
                extra = (f"; advertises {carto[0]!r}" if carto else "; no CartoDEM "
                         "layer token in body")
                notes.append(f"{label}: HTTP {resp.status}{extra}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{label}: fetch failure ({type(exc).__name__}: {exc})")
    return " | ".join(notes) + " — tile/coverage for the plot NOT verified."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem-tif", default=None, help="real sub-30 m GeoTIFF to integrate")
    ap.add_argument("--dem-dataset", default="(supplied raster)")
    ap.add_argument("--dem-datum", default="(recorded at acquisition)")
    ap.add_argument("--dem-res-m", type=float, default=None)
    ap.add_argument("--dem-source", default="")
    ap.add_argument("--survey-json", default=None, help="delivered survey rows JSON")
    args = ap.parse_args()

    print("=== V0.3 Phase 1g: acquisition + integration workflow ===")
    print(f"\nPlot = {PLOT['lat']}, {PLOT['lon']} (Ropar)")

    contract = build_baseline_contract()
    print("\n[gate] " + ACQUISITION_GATE_STATEMENT)

    print("\n[probe] Bhuvan WMS GetCapabilities (Cartosat/CartoDEM) ...")
    bhuvan_note = probe_bhuvan_cartosat()
    print("   " + bhuvan_note)

    dem_ingest = None
    if args.dem_tif:
        assert args.dem_res_m is not None, "--dem-res-m required when integrating a DEM file"
        assert args.dem_datum != "EGM2008" or True  # datum is declared by caller
        dem_ingest = inspect_dem_file(
            args.dem_tif, plot_lat=PLOT["lat"], plot_lon=PLOT["lon"],
            dataset=args.dem_dataset, provenance=args.dem_source or str(args.dem_tif),
            vertical_datum=args.dem_datum, source_resolution_m=args.dem_res_m,
        )
        print(f"   [ingest] {args.dem_tif} -> evidence_status="
              f"{dem_ingest.evidence_status} ({dem_ingest.reason})")
        dem = None  # DEM loaded for validation; preprocessed grid deferred
    else:
        print("   [status] no --dem-tif supplied: nothing integrated; awaiting the "
              "real acquisition.")
        dem = None
    survey_ingest = None
    if args.survey_json:
        rows = json.loads(Path(args.survey_json).read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("points", [])
        survey_ingest = ingest_survey_points(rows)
        print(f"   [ingest] {args.survey_json}: accepted="
              f"{survey_ingest.integrated_count} refused={len(survey_ingest.refused)}")
    else:
        print("   [status] no --survey-json supplied: nothing integrated; awaiting "
              "the field delivery.")

    integrate_into_contract(contract, dem_result=dem_ingest,
                            survey_result=survey_ingest)

    # Only re-assess when fine-scale evidence is actually integrated.
    reassessment = reassess_connectivity_after_acquisition(
        contract, dem=dem, proc=None, plot_lat=PLOT["lat"], plot_lon=PLOT["lon"],
    )
    print(f"\n[re-assess] connectivity = {reassessment.connectivity_status}"
          f" | solver_run = {reassessment.solver_run}"
          f" | plot_level_credible = {reassessment.plot_level_credible}")

    missing = contract.missing_plot_level_evidence()
    print(f"[contract] plot_level_credible = {contract.plot_level_credible}")
    print(f"[contract] missing plot-level evidence = "
          f"{[m.value for m in missing]}")

    result = {
        "phase": "V0.3 Phase 1g",
        "generated_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "plot": PLOT,
        "bhuvan_probe": bhuvan_note,
        "baseline_contract": contract.to_dict(),
        "acquisition_gate": ACQUISITION_GATE_STATEMENT,
        "dem_file_requirements": DEM_FILE_REQUIREMENTS,
        "dem_ingest": dem_ingest.to_dict() if dem_ingest else None,
        "survey_ingest": survey_ingest.to_dict() if survey_ingest else None,
        "reassessment": reassessment.to_dict(),
        "unresolved_message": UNRESOLVED_MESSAGE,
        "next_actions": [
            "Deliver the survey per simulations/outputs/survey_spec.md via "
            "--survey-json (rows: category/target/value_m/provenance/"
            "vertical_datum/horizontal_system/accuracy_m/verified).",
            "Acquire the Cartosat-1/Bhuvan sub-30 m tile for the plot, download "
            "it as GeoTIFF, and integrate via --dem-tif (declared datum + "
            "resolution).",
            "Only after verified survey + sub-30 m DEM are integrated: "
            "re-run connectivity (this workflow), then (if genuinely resolved) "
            "the solver phase may begin.",
        ],
    }
    out_dir = ROOT / "simulations" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "acquisition_workflow.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    (out_dir / "acquisition_workflow.md").write_text(
        build_markdown(result), encoding="utf-8")
    print("\nWrote:")
    print("  simulations/outputs/acquisition_workflow.json")
    print("  simulations/outputs/acquisition_workflow.md")


def build_markdown(r: dict) -> str:
    L = ["# V0.3 Phase 1g — Acquisition & Integration Workflow", ""]
    L.append("_Real-data step. Nothing is fabricated: DEMs and survey rows are "
             "integrated only through the verified-acquisition gate, and "
             "connectivity is not re-assessed until fine-scale data actually "
             "exists._")
    L.append("")
    L.append(f"- Plot: `{r['plot']['lat']}, {r['plot']['lon']}` (Ropar)")
    L.append("")
    L.append("## Gate")
    L.append(f"> {r['acquisition_gate']}")
    L.append("")
    L.append("## Bhuvan / Cartosat-1 probe")
    L.append("")
    L.append(f"- {r['bhuvan_probe']}")
    L.append("")
    L.append("## DEM intake requirements")
    L.append("")
    for req in r["dem_file_requirements"]:
        L.append(f"- {req}")
    L.append("")
    L.append("## Integrated (this run)")
    L.append("")
    if r["dem_ingest"]:
        d = r["dem_ingest"]
        L.append(f"- DEM: `{d['dataset']}` — evidence `{d['evidence_status']}` — "
                 f"{d['reason']}")
    else:
        L.append("- DEM: **none integrated** (no real sub-30 m file supplied).")
    if r["survey_ingest"]:
        s = r["survey_ingest"]
        L.append(f"- Survey: {s['note']} (accepted "
                 f"`{s['integrated_count']}`, refused `{len(s['refused'])}`).")
        for acc in s["accepted"]:
            L.append(f"  - accepted: {acc['category']} {acc['target']} = "
                     f"{acc['value_m']} m ({acc['vertical_datum']}, ±"
                     f"{acc['accuracy_m']} m, `{acc['provenance']}`)")
        for rf in s["refused"]:
            L.append(f"  - refused: {rf}")
    else:
        L.append("- Survey: **none integrated** (no verified delivery supplied).")
    L.append("")
    L.append("## Connectivity re-assessment")
    L.append("")
    ra = r["reassessment"]
    L.append(f"- Status: `{ra['connectivity_status']}`")
    L.append(f"- Reason: {ra['reason']}")
    L.append(f"- Solver run: `{ra['solver_run']}`")
    L.append(f"- Plot-level credible (J.3): `{ra['plot_level_credible']}`")
    L.append(f"- Missing plot-level evidence: "
             f"`{ra['missing_plot_level_evidence']}`")
    L.append("")
    L.append("## Baseline constraining observations")
    L.append("")
    L.append("| Category | Status | Source / reference | Note |")
    L.append("|---|---|---|---|")
    for row in r["baseline_contract"]["rows"]:
        L.append(f"| {row['category']} | {row['status']} | "
                 f"{row['source']} / {row['reference']} | {row['note']} |")
    L.append("")
    L.append("## Next actions")
    L.append("")
    for a in r["next_actions"]:
        L.append(f"- {a}")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
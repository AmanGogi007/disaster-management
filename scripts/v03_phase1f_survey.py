"""V0.3 Phase 1f — local-survey acquisition specification + high-res DEM source
determination for the exact plot (31.05, 76.53).

Produces a field-ready measurement spec (points, spacing, elevations,
datum/benchmark requirements, plot boundary, drainage/road/channel/culvert
crossings) derived entirely from the reconciled local features, plus a
high-resolution DEM candidate matrix whose availability is either live-probed or
honestly labelled unverified.

NO measurement is assumed or fabricated: every requested value ships as
``None``/``unverified``.  Connectivity stays UNRESOLVED until the fine-scale
evidence actually resolves it.  NO flood solver is run.

Writes:
    simulations/outputs/survey_spec.json
    simulations/outputs/survey_spec.md
"""
from __future__ import annotations

import json
import sys
import urllib.request
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from geo.hydraulic import (  # noqa: E402
    SURVEY_GATE_STATEMENT,
    HIGH_RES_DEM_GATE_STATEMENT,
    UNRESOLVED_MESSAGE,
    gather_plot_evidence,
    gather_terrain_evidence,
    produce_survey_spec,
)
from geo.terrain.providers.copernicus import CopernicusGLO30Provider  # noqa: E402

PLOT = {"lat": 31.05, "lon": 76.53}
RADIUS_KM = 3.0
CORRIDOR = {"south": 30.98, "west": 76.30, "north": 31.47, "east": 76.68}

USER_AGENT = "location-hazard-engine/0.2 (research)"
PROBE_TIMEOUT_S = 8

PROBES = {
    "Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m)": "https://bhuvan.nrsc.gov.in/",
    "ALOS PALSAR RTC (12.5 m)": "https://search.asf.alaska.edu/",
    "ALOS World 3D 30m (AW3D30)": "https://www.eorc.jaxa.jp/ALOS/en/aw3d30/",
    "TanDEM-X WorldDEM (12 m)": "https://geoservice.dlr.de/web/datasets/tdem/",
}


def _probe(url: str) -> str:
    """Best-effort reachability probe.  Reachable ≠ data verified; the result is
    used only to annotate the source matrix."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_S) as resp:  # noqa: S310
            return f"reachable (HTTP {resp.status}); tile/coverage NOT requested"
    except Exception as exc:  # noqa: BLE001
        return f"unreachable from this environment ({type(exc).__name__})"


def build_markdown(r) -> str:
    L = []
    L.append("# V0.3 Phase 1f — Local-Survey Specification & High-Resolution DEM Sources")
    L.append("")
    L.append("_Status: specification complete — nothing measured or fabricated. "
             "Values stay None/unverified until real, provenance-carrying field "
             "data arrives. Connectivity remains UNRESOLVED; solver NOT run._")
    L.append("")
    L.append(f"- Plot: `{r.plot_lat}, {r.plot_lon}` (Ropar)")
    L.append(f"- Generated at (UTC): `{r.generated_at}`")
    L.append(f"- Connectivity status: `{r.connectivity_status}`")
    L.append(f"- Plot-level credibility (J.3): `{r.plot_level_credible}` "
             "(still False — survey + high-res DEM required)")
    L.append(f"- Surveyed elevations integrated: `{r.surveyed_elevations_integrated}`")
    L.append("")
    L.append("## Gate statements")
    L.append("")
    L.append(f"> {SURVEY_GATE_STATEMENT}")
    L.append("")
    L.append(f"> {HIGH_RES_DEM_GATE_STATEMENT}")
    L.append("")
    L.append("## High-resolution DEM source determination")
    L.append("")
    L.append("Statuses: `available` only when genuinely verified; everything else "
             "is `commercial` or `unverified` (never silently assumed).")
    L.append("")
    L.append("| Source | Res (m) | Vertical datum | Licence | Suitability | Status | Recommended |")
    L.append("|---|---|---|---|---|---|---|")
    for s in r.high_res_dem_sources:
        L.append(f"| {s.name.replace('|', '/')} | {s.resolution_m or '-'} | "
                 f"{s.vertical_datum.replace('|', '/')} | "
                 f"{s.license.replace('|', '/')} | "
                 f"{s.suitability_for_plot.replace('|', '/')} | {s.status} | "
                 f"{'yes' if s.recommended else '-'} |")
    L.append("")
    L.append("### Live reachability probes (this environment)")
    L.append("")
    L.append("Reachable portal ≠ verified tile: coverage/approval is still "
             "required at acquisition time.")
    L.append("")
    for name, note in PROBE_NOTES.items():
        L.append(f"- **{name}:** {note}")
    L.append("")
    L.append("## Local-survey acquisition specification")
    L.append("")
    L.append(f"**{len(r.survey_points)} measurement classes.** Every "
             "`measured_value` is `None` until delivered and verified.")
    L.append("")
    by_cat: dict[str, list] = {}
    for s in r.survey_points:
        by_cat.setdefault(s.category, []).append(s)
    for cat, items in by_cat.items():
        first = items[0]
        L.append(f"### {first.category_label} — `{cat}`")
        L.append("")
        L.append(f"- **Derived from:** `{first.derived_from}`")
        L.append(f"- **Points required:** {first.points_required}")
        L.append(f"- **Spacing:** {first.spacing_m}")
        L.append(f"- **Fields to measure:** " +
                 "; ".join(first.fields_to_measure))
        L.append(f"- **Vertical datum requirement:** {first.vertical_datum_req}")
        L.append(f"- **Horizontal system:** {first.horizontal_system}")
        L.append(f"- **Accuracy required:** {first.accuracy_req}")
        L.append("- **Feature references:**")
        if not items:
            L.append("  - (none)")
        for s in items:
            L.append(f"  - `{s.target}` — OSM `{s.source_osm_id or 'n/a'}` "
                     f"(`{s.source_name or 'unnamed'}`); {s.location_note}")
        L.append("")
    L.append("## Caveats")
    L.append("")
    for c in r.caveats:
        L.append(f"- {c}")
    L.append("")
    L.append("## Required before the solver phase")
    L.append("")
    L.append("- Commission the survey per this spec and integrate ONLY verified "
             "points (`record_survey_points` gate).")
    L.append("- Acquire a sub-30 m DEM for the plot (recommended: Cartosat-1/"
             "Bhuvan, then field-verify); keep its datum explicit.")
    L.append("- Re-run connectivity with the verified fine-scale evidence; only "
             "then is the solver allowed to estimate flood depth.")
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("=== V0.3 Phase 1f: survey spec + high-res DEM sources ===")
    print(textwrap.dedent(
        f"""
        Plot      = ({PLOT['lat']}, {PLOT['lon']})  Ropar
        Radius    = {RADIUS_KM} km
        Scope     = survey acquisition spec (no measurements) + sub-30 m DEM
                    source determination for the exact plot.
        """))
    provider = CopernicusGLO30Provider()
    res_d = provider.get_dem_bbox(
        CORRIDOR["south"], CORRIDOR["west"], CORRIDOR["north"], CORRIDOR["east"])
    dem = res_d.dem

    print("  [context] OSM feature geometry (Overpass) ...")
    gather = gather_plot_evidence(PLOT["lat"], PLOT["lon"], radius_km=RADIUS_KM)
    for rec in gather.records[:4]:
        print(f"    [{rec.status:>13}] {rec.category.value} ({rec.count})")

    print("  [context] terrain low points ...")
    terrain = None
    if dem is not None:
        terrain = gather_terrain_evidence(
            dem, gather, plot_lat=PLOT["lat"], plot_lon=PLOT["lon"],
            radius_km=RADIUS_KM)
        print(f"    (transect={'yes' if terrain.transect else 'no'}, "
              f"lows={len(terrain.low_points)})")

    print("  [probe] high-res DEM source reachability ...")
    global PROBE_NOTES
    PROBE_NOTES = {}
    probe_results: dict[str, str] = {}
    for name, url in PROBES.items():
        state = _probe(url)
        PROBE_NOTES[name] = state
        print(f"    {name}: {state}")

    print("  [spec] building survey specification ...")
    r = produce_survey_spec(
        gather, terrain, plot_lat=PLOT["lat"], plot_lon=PLOT["lon"],
        probe_results=probe_results)
    print(f"    survey_point_classes = {len(r.survey_points)}")
    print(f"    dem_sources = {len(r.high_res_dem_sources)}")
    print(f"    connectivity = {r.connectivity_status[:48]}...")

    out_dir = ROOT / "simulations" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "survey_spec.md"
    md_path.write_text(build_markdown(r), encoding="utf-8")
    json_path = out_dir / "survey_spec.json"
    payload = {
        "phase": "V0.3 Phase 1f",
        "fetched_at_utc": r.generated_at,
        "plot": PLOT,
        "radius_km": RADIUS_KM,
        "survey_gate": SURVEY_GATE_STATEMENT,
        "high_res_gate": HIGH_RES_DEM_GATE_STATEMENT,
        "unresolved_message": UNRESOLVED_MESSAGE,
        "probe_notes": PROBE_NOTES,
        "survey": r.to_dict(),
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote:\n  {md_path}\n  {json_path}")


if __name__ == "__main__":
    main()
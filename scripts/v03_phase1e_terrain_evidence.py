"""V0.3 Phase 1e — plot-level terrain evidence report.

Acquires + characterises local terrain evidence around the exact plot from the
primary DEM (Copernicus GLO-30, 1 arc-second ~30 m, EGM2008), overlaid on the
reconciled OSM channel/drain/barrier geometry, and records an SRTM GL1
cross-check attempt (same ~30 m, EGM96).

Every elevation below is DEM-derived (DSM) — there is no surveyed elevation
anywhere in this phase, recorded explicitly.  Gauge values and historical
extents are NOT converted here; proximity/low-points do NOT imply hydraulic
connectivity; NO 2D flood solver is run.

Writes:
    simulations/outputs/terrain_evidence.json
    simulations/outputs/terrain_evidence.md
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from geo.hydraulic import (  # noqa: E402
    TERRAIN_TO_CONNECTIVITY_STATEMENT,
    gather_plot_evidence,
    gather_terrain_evidence,
)
from geo.terrain.providers.copernicus import CopernicusGLO30Provider  # noqa: E402

PLOT = {"lat": 31.05, "lon": 76.53}
RADIUS_KM = 3.0
CORRIDOR = {"south": 30.98, "west": 76.30, "north": 31.47, "east": 76.68}

STATUS_MD = {
    "obtained": "obtained",
    "unavailable": "unavailable",
    "insufficient": "insufficient resolution",
}


def _fmt(deg: float | None, suffix: str = "°") -> str:
    return "-" if deg is None else f"{deg:.4f}{suffix}"


def build_markdown(r) -> str:
    L = []
    L.append("# V0.3 Phase 1e — Plot-level Terrain Evidence (Sutlej / Ropar)")
    L.append("")
    L.append("_Status: terrain evidence layer complete — characterisation only. "
             "No gauge value converted, no connectivity inferred from terrain, "
             "no flood solver run._")
    L.append("")
    L.append(f"- Plot: `{PLOT['lat']}, {PLOT['lon']}` (Ropar)")
    L.append(f"- Terrain radius: `{r.radius_km} km`")
    L.append(f"- Gathered at (UTC): `{r.fetched_at}`")
    L.append("")
    L.append("> " + TERRAIN_TO_CONNECTIVITY_STATEMENT)
    L.append("")
    L.append("## DEM provenance (primary)")
    L.append("")
    p = r.dem_provenance
    for k, v in p.items():
        L.append(f"- **{k}:** `{v}`")
    L.append("")
    L.append("## Plot measurement")
    L.append("")
    pm = r.plot
    L.append(f"- **DEM elevation at plot:** `{pm.get('dem_elevation_m')} m` "
             f"({pm.get('elevation_kind')}; source `{pm.get('dem_source')}`; "
             f"vertical datum `{pm.get('dem_vertical_datum')}`)")
    L.append(f"- **Slope / aspect:** `{pm.get('slope_deg')}` / "
             f"`{pm.get('aspect_deg')}` ({pm.get('aspect_cardinal')})")
    L.append(f"- **Note:** {pm.get('note')}")
    L.append("")
    L.append("## Neighbourhood statistics (radius window)")
    L.append("")
    nh = r.neighborhood
    for k, v in nh.items():
        L.append(f"- **{k}:** `{v}`")
    L.append("")
    L.append("## Plot boundary record")
    L.append("")
    for k, v in r.plot_boundary.items():
        L.append(f"- **{k}:** `{v}`")
    L.append("")
    L.append("## Sampled feature elevations (DEM at OSM geometry)")
    L.append("")
    L.append("| Feature | Type | min_dist (km) | DEM min (m) | DEM mean (m) | DEM max (m) | Δ vs plot (m) | kind |")
    L.append("|---|---|---|---|---|---|---|---|")
    for s in r.samples:
        L.append(f"| {s.label.replace('|', '/')} | {s.feature_type} | "
                 f"{s.min_distance_km or '-'} | {s.dem_min_m or '-'} | "
                 f"{s.dem_mean_m or '-'} | {s.dem_max_m or '-'} | "
                 f"{s.relative_to_plot_m if s.relative_to_plot_m is not None else '-'} | "
                 f"{s.elevation_kind} |")
    L.append("")
    L.append("## Transect: plot → nearest main-stem Sutlej point")
    L.append("")
    tr = r.transect
    if tr is None:
        L.append("_No main-stem way available to define the transect._")
    else:
        tgt = tr.target
        L.append(f"- **Target** `{_fmt(tgt['lat'])}N, {_fmt(tgt['lon'])}E` "
                 f"at `{tgt['distance_km_from_plot']} km` from plot")
        L.append(f"- **Target (channel) DEM elevation:** `{tr.target_elevation_m} m`")
        L.append(f"- **Plot DEM elevation:** `{tr.plot_elevation_m} m`")
        L.append(f"- **Channel relative to plot:** `{tr.channel_relative_to_plot_m} m` "
                 f"(characterisation only)")
        L.append(f"- **Transect min / max elevation:** `{tr.min_elevation_m}` / "
                 f"`{tr.max_elevation_m}` m; **max drop below plot:** "
                 f"`{tr.drop_below_plot_m} m`")
        L.append(f"- **Note:** {tr.note}")
        L.append("")
        L.append("| # | lat | lon | dist (km) | DEM (m) |")
        L.append("|---|---|---|---|---|")
        for i, pt in enumerate(tr.points):
            L.append(f"| {i} | {pt.lat} | {pt.lon} | {pt.distance_km} | "
                     f"{pt.dem_elevation_m if pt.dem_elevation_m is not None else '-'} |")
    L.append("")
    L.append("## Low points / depressions within radius")
    L.append("")
    if not r.low_points:
        L.append("_No distinct low points found (flat window or all equal)._")
    else:
        L.append("| lat | lon | DEM (m) | dist from plot (m) | Δ vs plot (m) | local min |")
        L.append("|---|---|---|---|---|---|")
        for lo in r.low_points:
            L.append(f"| {lo.lat} | {lo.lon} | {lo.dem_elevation_m} | "
                     f"{lo.distance_from_plot_m} | "
                     f"{lo.relative_to_plot_m if lo.relative_to_plot_m is not None else '-'} | "
                     f"{lo.is_local_min} |")
    L.append("")
    L.append("## Surveyed elevation record")
    L.append("")
    for k, v in r.surveyed.items():
        L.append(f"- **{k}:** `{v}`")
    L.append("")
    L.append("## Finer-DEM cross-check attempt")
    L.append("")
    fd = r.finer_dem
    if fd is None:
        L.append("_No finer-DEM attempt was made._")
    else:
        for k, v in fd.__dict__.items():
            L.append(f"- **{k}:** `{v}`")
    L.append("")
    L.append("## Deferred historical-flood-extent work (non-blocking)")
    L.append("")
    for k, v in r.deferred_flood_extents.items():
        if isinstance(v, list):
            L.append(f"- **{k}:**")
            for item in v:
                L.append(f"  - {item}")
        else:
            L.append(f"- **{k}:** {v}")
    L.append("")
    L.append("## Caveats")
    L.append("")
    for c in r.caveats:
        L.append(f"- {c}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    print("=== V0.3 Phase 1e: plot-level terrain evidence ===")
    print(textwrap.dedent(
        f"""
        Plot      = ({PLOT['lat']}, {PLOT['lon']})  Ropar
        Radius    = {RADIUS_KM} km
        Corridor  = {CORRIDOR}
        Primary DEM = Copernicus GLO-30 (EGM2008); cross-check SRTM GL1 (EGM96).
        """))
    provider = CopernicusGLO30Provider()
    res_d = provider.get_dem_bbox(
        CORRIDOR["south"], CORRIDOR["west"], CORRIDOR["north"], CORRIDOR["east"])
    dem = res_d.dem
    print(f"  [primary] DEM: {res_d.note}")
    if dem is None:
        print(f"  [fatal] no primary DEM: {res_d.note}")

    print("  [context] OSM feature geometry (Overpass) ...")
    gather = gather_plot_evidence(PLOT["lat"], PLOT["lon"], radius_km=RADIUS_KM)
    for rec in gather.records[:4]:
        print(f"    [{rec.status:>13}] {rec.category.value} ({rec.count})")

    print("  [evidence] terrain characterisation ...")
    r = gather_terrain_evidence(
        dem, gather, plot_lat=PLOT["lat"], plot_lon=PLOT["lon"],
        radius_km=RADIUS_KM)
    print(f"    plot DEM = {r.plot.get('dem_elevation_m')} m "
          f"(slope {r.plot.get('slope_deg')}°)")
    print(f"    neighbourhood cells = {r.neighborhood.get('cell_count')}")
    print(f"    feature samples = {len(r.samples)}")
    print(f"    transect = "
          f"{'yes' if r.transect else 'no'}; "
          f"low points = {len(r.low_points)}")
    print(f"    finer DEM: {r.finer_dem.status} ({r.finer_dem.dataset}, "
          f"Δ {r.finer_dem.cross_check_delta_m} m)" if r.finer_dem else "    finer DEM: none")

    out_dir = ROOT / "simulations" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "terrain_evidence.md"
    md_path.write_text(build_markdown(r), encoding="utf-8")
    json_path = out_dir / "terrain_evidence.json"
    payload = {
        "phase": "V0.3 Phase 1e",
        "fetched_at_utc": r.fetched_at,
        "plot": PLOT,
        "radius_km": r.radius_km,
        "dem_provenance": r.dem_provenance,
        "terrain": r.to_dict(),
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote:\n  {md_path}\n  {json_path}")


if __name__ == "__main__":
    main()
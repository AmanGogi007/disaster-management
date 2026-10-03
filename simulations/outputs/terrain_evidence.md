# V0.3 Phase 1e — Plot-level Terrain Evidence (Sutlej / Ropar)

_Status: terrain evidence layer complete — characterisation only. No gauge value converted, no connectivity inferred from terrain, no flood solver run._

- Plot: `31.05, 76.53` (Ropar)
- Terrain radius: `3.0 km`
- Gathered at (UTC): `2026-09-01T20:43:59.748253+00:00`

> Plot-level terrain evidence is characterisation only. A lower DEM value, a low point, or terrain proximity to the channel does NOT by itself establish hydraulic connectivity or flood depth at the plot. Connectivity remains gated by assess_connectivity (UNRESOLVED at 30 m DEM resolution); flood depth requires the flood solver, which is NOT run in this phase.

## DEM provenance (primary)

- **dataset:** `Copernicus DEM GLO-30`
- **source_resolution_m:** `30.92222222222222`
- **simulation_grid_m:** `30.92222222222222`
- **horizontal_crs:** `EPSG:4326`
- **vertical_datum:** `EGM2008`
- **vertical_offset_m:** `0.0`
- **nodata:** `None`
- **bounds_deg:** `[31.0, 76.29972222222223, 31.470000000000002, 76.68027777777779]`
- **provenance:** `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N31_00_E076_00_DEM/Copernicus_DSM_COG_10_N31_00_E076_00_DEM.tif`

## Plot measurement

- **DEM elevation at plot:** `267.5 m` (dem; source `Copernicus DEM GLO-30`; vertical datum `EGM2008`)
- **Slope / aspect:** `0.0` / `None` (None)
- **Note:** DEM-derived (DSM) elevation at the plot cell; NOT a surveyed ground elevation.

## Neighbourhood statistics (radius window)

- **status:** `obtained`
- **cell_count:** `44688`
- **min_m:** `266.5`
- **max_m:** `391.62`
- **mean_m:** `287.33`
- **relief_m:** `125.12`
- **coverage_deg:** `[31.023, 76.4985, 31.077, 76.5615]`
- **note:** `DEM-derived (DSM) statistics over the radius window; characterisation only.`

## Plot boundary record

- **status:** `unavailable`
- **geometry:** `point only`
- **note:** `No surveyed/parcel plot boundary is available. 'The plot' is the coordinate (lat, lon) used throughout; boundary-dependent conclusions (e.g. which DEM cells fall inside the plot) are NOT asserted.`

## Sampled feature elevations (DEM at OSM geometry)

| Feature | Type | min_dist (km) | DEM min (m) | DEM mean (m) | DEM max (m) | Δ vs plot (m) | kind |
|---|---|---|---|---|---|---|---|
| channel (main stem):919730633 | channel | 0.129 | 267.0 | 267.3 | 267.5 | -0.2 | dem |
| channel (main stem):377207447 | channel | 0.301 | 267.0 | 267.72 | 270.52 | 0.22 | dem |
| channel:377207446 | channel | 0.555 | 267.5 | 277.98 | 284.12 | 10.48 | dem |
| local_canal_drain:377207446 | local_canal_drain | 0.555 | 267.5 | 277.98 | 284.12 | 10.48 | dem |
| channel (main stem):165931479 | channel | 1.152 | 266.0 | 266.55 | 267.0 | -0.95 | dem |
| channel (main stem):41539116 | channel | 1.237 | 267.5 | 271.88 | 275.5 | 4.38 | dem |
| crossing:254573869 | crossing | 1.611 | 272.39 | 274.87 | 277.34 | 7.37 | dem |
| crossing:254573867 | crossing | 2.494 | 279.41 | 280.06 | 280.71 | 12.56 | dem |
| barrier:680091133 | barrier | 2.674 | 274.89 | 277.77 | 279.28 | 10.27 | dem |
| channel:248023200 | channel | 2.966 | 268.0 | 272.96 | 289.89 | 5.46 | dem |
| barrier:919730631 | barrier | 3.17 | 273.5 | 279.27 | 283.22 | 11.77 | dem |

## Transect: plot → nearest main-stem Sutlej point

- **Target** `31.0495°N, 76.5288°E` at `0.1288 km` from plot
- **Target (channel) DEM elevation:** `267.5 m`
- **Plot DEM elevation:** `267.5 m`
- **Channel relative to plot:** `0.0 m` (characterisation only)
- **Transect min / max elevation:** `267.5` / `267.5` m; **max drop below plot:** `0.0 m`
- **Note:** Linear transect plot → nearest Sutlej main-stem OSM point, DEM sampled at each stop. Pure elevation contrast characterisation; NOT a hydraulic path, no connectivity or depth inference.

| # | lat | lon | dist (km) | DEM (m) |
|---|---|---|---|---|
| 0 | 31.05 | 76.53 | 0.0 | 267.5 |
| 1 | 31.049949 | 76.529878 | 0.0129 | 267.5 |
| 2 | 31.049899 | 76.529757 | 0.0258 | 267.5 |
| 3 | 31.049848 | 76.529635 | 0.0386 | 267.5 |
| 4 | 31.049797 | 76.529514 | 0.0515 | 267.5 |
| 5 | 31.049746 | 76.529392 | 0.0644 | 267.5 |
| 6 | 31.049696 | 76.529271 | 0.0773 | 267.5 |
| 7 | 31.049645 | 76.529149 | 0.0902 | 267.5 |
| 8 | 31.049594 | 76.529027 | 0.1031 | 267.5 |
| 9 | 31.049543 | 76.528906 | 0.1159 | 267.5 |
| 10 | 31.049493 | 76.528784 | 0.1288 | 267.5 |

## Low points / depressions within radius

| lat | lon | DEM (m) | dist from plot (m) | Δ vs plot (m) | local min |
|---|---|---|---|---|---|
| 31.070556 | 76.548056 | 266.85 | 2860.4 | -0.65 | True |
| 31.024167 | 76.530278 | 267.69 | 2872.7 | 0.19 | True |
| 31.031667 | 76.5275 | 267.76 | 2052.4 | 0.26 | True |
| 31.033611 | 76.525278 | 267.78 | 1877.1 | 0.28 | True |
| 31.035278 | 76.528333 | 267.81 | 1644.7 | 0.31 | True |
| 31.037222 | 76.526667 | 267.85 | 1455.9 | 0.35 | True |
| 31.034722 | 76.525556 | 267.95 | 1750.8 | 0.45 | True |
| 31.0325 | 76.526944 | 267.98 | 1967.6 | 0.48 | True |

## Surveyed elevation record

- **status:** `unavailable`
- **confidence:** `low`
- **note:** `No local ground survey acquired. A survey must supply, on a common datum with horizontal control: ground elevation at building plinths, road crown heights, rail/embankment top elevations, canal bed/berm elevations, culvert/bridge invert and soffit elevations, and plot grading. Until then plot-level answers stay NOT credible (J.3).`

## Finer-DEM cross-check attempt

- **status:** `obtained`
- **dataset:** `SRTM GL1 (+GMTED2010 fill)`
- **resolution_m:** `38.2`
- **vertical_datum:** `EGM96`
- **plot_elevation_m:** `269.62`
- **cross_check_delta_m:** `2.12`
- **note:** `Acquired 'SRTM GL1 (+GMTED2010 fill)' (resolution 38.2 m, vertical datum EGM96) as a CROSS-CHECK of the primary DEM, NOT a sub-30 m product. Delta vs primary 2.12109375 m — datums explicitly differ (EGM96 vs primary EGM2008), so the delta is reported, never fused. A sub-30 m DEM (ALOS/TanDEM/CartoSAT/drone) is still required for plot-level credibility (J.3).`

## Deferred historical-flood-extent work (non-blocking)

- **status:** deferred
- **why_not_blocking:** Terrain acquisition is independent of historical flood-extent intersection; terrain is complete without it.
- **remaining:**
  - GFD/DFO v1 (2000–2018, 913 events): per-event raster intersection with the Ropar corridor bbox; read duration + JRC-permanent-water bands per event.
  - Events AFTER 2018 (e.g. 2019, 2023) are NOT in GFD v1 — require CWC/NASA/state flood-extent products instead.
  - Reconcile any intersected event with the reconciled main stem + BBMB Bhakra release record (upstream boundary) before use as validation data.
  - Record each event's spatial/temporal coverage + uncertainty; never convert an extent polygon into a plot depth without the solver phase.

## Caveats

- All numeric elevations are DEM-derived (DSM, Copernicus GLO-30 unless stated) and are characterisation only — none is a surveyed ground elevation, and none is converted into flood depth.
- GLO-30 is a surface model (DSM): vegetation/embankment/roof tops can contribute to the cell value; a 30 m cell cannot resolve microtopography (ditches, bunds, plot grading, culvert inverts).
- Vertical datum is EGM2008 for GLO-30 (EGM96 for the SRTM cross-check); surveyed elevations on a local/orthometric datum would need explicit transformation before any comparison.
- OSM feature geometry is horizontal-only (WGS84; no vertical datum) — feature elevations here are purely the DEM sampled at the mapped geometry, never OSM tag heights.
- Terrain proximity / a low point does NOT imply hydraulic connectivity or flood depth; see the gate statement.
- No flood solver has been run (this phase is evidence-only).
- Plot-level credibility (J.3) still requires local survey + sub-30 m DEM.

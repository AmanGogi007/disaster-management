# V0.3 Phase 1g — Acquisition & Integration Workflow

_Real-data step. Nothing is fabricated: DEMs and survey rows are integrated only through the verified-acquisition gate, and connectivity is not re-assessed until fine-scale data actually exists._

- Plot: `31.05, 76.53` (Ropar)

## Gate
> Newly acquired data is integrated ONLY through the verified-acquisition gate: a DEM raster only after it really exists, reads successfully, covers the plot, and carries an explicit native resolution + vertical datum; survey points only after each claim is provenance-tagged, datum-tagged, accuracy-tagged and marked verified. Unverified or fabricated claims are refused. Integrating fine-scale data allows connectivity to be RE-ASSESSED — it never by itself resolves connectivity and never runs the hydraulic solver.

## Bhuvan / Cartosat-1 probe

- portal root: HTTP 200; no CartoDEM layer token in body | wms GetCapabilities: fetch failure (HTTPError: HTTP Error 404: Not Found) | ows GetCapabilities: fetch failure (HTTPError: HTTP Error 404: Not Found) — tile/coverage for the plot NOT verified.

## DEM intake requirements

- GeoTIFF (or raster readable by rasterio) in EPSG:4326.
- Must cover the plot cell, ideally with a ≥0.005° (~0.5 km) margin.
- Must carry an explicit native resolution and a named vertical datum ('vertical_datum' on intake; else the provider/product datum must be recorded by the caller).
- Native resolution < 30 m is required for the HIGH_RES_DEM category to be plot-level usable; a ≥30 m product integrating would be PARTIAL, not available.
- Datums (EGM96 / EGM2008 / MSL) must be declared on intake; they are never fused silently.

## Integrated (this run)

- DEM: **none integrated** (no real sub-30 m file supplied).
- Survey: **none integrated** (no verified delivery supplied).

## Connectivity re-assessment

- Status: `unresolved`
- Reason: Refused by acquisition gate: no verified fine-scale data (HIGH_RES_DEM available / verified LOCAL_SURVEY) integrated yet.
- Solver run: `False`
- Plot-level credible (J.3): `False`
- Missing plot-level evidence: `['local_survey', 'high_res_dem']`

## Baseline constraining observations

| Category | Status | Source / reference | Note |
|---|---|---|---|
| channel_centerline | available | OpenStreetMap / Sutlej main stem 919730633/377207447/165931479/41539116 (reconciled) | anchored main-stem centreline, min 0.129 km; unconnected 248023200 reported. |
| channels_drains | available | OpenStreetMap / 377207446 | local canal/drain within 3 km radius. |
| embankments_road_rail | available | OpenStreetMap / 680091133, 919730631 | rail barriers mapped; openings/no-openings NOT survey-confirmed (barrier note absent -> not a definitive NOT_CONNECTED). |
| bridges_culverts | available | OpenStreetMap / 254573869, 254573867 | crossings mapped; invert/soffit field measurement required (survey spec). |
| gauge_observations | missing | - / - | CWC has no Rohira/Ropar Sutlej resource (Phase 1d); any delivery must be provenance-tagged. |
| documented_flood_extents | missing | - / - | documented 1988/2019 events exist but corridor mapping not ingested this phase. |
| local_survey | missing | field survey (to be delivered) / survey_spec | nothing integrated yet — spec only. |
| high_res_dem | missing | (to be acquired) / survey_spec sources | no sub-30 m DEM integrated yet. |
| flood_control | not_applicable | - / - | no mapped flood control. |

## Next actions

- Deliver the survey per simulations/outputs/survey_spec.md via --survey-json (rows: category/target/value_m/provenance/vertical_datum/horizontal_system/accuracy_m/verified).
- Acquire the Cartosat-1/Bhuvan sub-30 m tile for the plot, download it as GeoTIFF, and integrate via --dem-tif (declared datum + resolution).
- Only after verified survey + sub-30 m DEM are integrated: re-run connectivity (this workflow), then (if genuinely resolved) the solver phase may begin.

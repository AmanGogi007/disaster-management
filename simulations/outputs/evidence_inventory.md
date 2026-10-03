# V0.3 Phase 1b — Local Evidence Inventory + Reconciliation

_Status: evidence layer complete — awaiting review, no solver run._

## Objective

Gather and reconcile the plot-level hydraulic evidence around the Ropar plot (31.05°N, 76.53°E) into the J.3 EvidenceContract. Every source carries provenance, resolution, datum, coverage and an explicit availability/quality status. Missing or weak evidence is **not** converted into an assumption; the flood solver is **not** started.

- Plot: `31.05, 76.53`
- Evidence search radius: `3.0 km`
- GLO-30 corridor (reused from Phase 0): `{'south': 30.98, 'west': 76.3, 'north': 31.47, 'east': 76.68}`
- Gathered at (UTC): `2026-09-01T18:38:04.201049+00:00`

## Evidence inventory

| # | Category | Status | Found | Coverage (km) | Confidence | Source / dataset |
|---|----------|--------|-------|---------------|------------|------------------|
| channel_centerline | channel_centerline | conflicting | 5 | 3.0 | low | osm-overpass |
| channels_drains | channels_drains | obtained | 1 | 3.0 | medium | osm-overpass |
| embankments_road_rail | embankments_road_rail | obtained | 2 | 3.0 | medium | osm-overpass |
| bridges_culverts | bridges_culverts | obtained | 2 | 3.0 | medium | osm-overpass |
| flood_control | flood_control | unavailable | 0 | 3.0 | low | osm-overpass |
| gauge_observations | gauge_observations | unavailable | 0 | 3.0 | low | osm-overpass |
| documented_flood_extents | documented_flood_extents | unavailable | 0 | 3.0 | low | osm-overpass |
| local_survey | local_survey | unavailable | 0 | 3.0 | low | osm-overpass |
| high_res_dem | high_res_dem | unavailable | 0 | 3.0 | low | osm-overpass |

## Per-source detail (with provenance, resolution, datum, notes)

### channel_centerline — *conflicting*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:37:53.616192+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** OSM centreline; horizontal accuracy ~meters; no width/depth.
- **Datum note:** OSM geometry is WGS84 (EPSG:4326); no vertical datum — relates to DEM only via horizontal CRS; do NOT use for absolute elevation.
- **Confidence:** `low`
- **Note:** Found 5 river ways within 3.0 km; reconcile which is the Sutlej main stem.
- **Sample features:**
  - id `41539116` `Sutlej` 6.762 km from plot `{'name': 'Sutlej', 'waterway': 'river'}`
  - id `165931479` `Sutlej` 4.078 km from plot `{'name': 'Sutlej', 'waterway': 'river'}`
  - id `248023200` `—` 5.109 km from plot `{'waterway': 'river'}`
  - id `377207447` `—` 0.444 km from plot `{'waterway': 'river'}`
  - id `919730633` `Sutlej` 0.279 km from plot `{'name': 'Sutlej', 'waterway': 'river'}`

### channels_drains — *obtained*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:37:53.616334+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** OSM drain/canal/stream; no bathymetry; ~meter x-y.
- **Datum note:** OSM geometry is WGS84 (EPSG:4326); no vertical datum — relates to DEM only via horizontal CRS; do NOT use for absolute elevation.
- **Confidence:** `medium`
- **Note:** Local channels/drains/streams — found 1.
- **Sample features:**
  - id `377207446` `—` 4.192 km from plot `{'waterway': 'canal'}`

### embankments_road_rail — *obtained*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:37:59.672767+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** Identifies embankments/roads/railways that may act as barriers; not a hydraulic analysis — gaps/culverts not assessed here.
- **Datum note:** OSM geometry is WGS84 (EPSG:4326); no vertical datum — relates to DEM only via horizontal CRS; do NOT use for absolute elevation.
- **Confidence:** `medium`
- **Note:** Roads/railways/embankments (potential barriers) — found 2.
- **Sample features:**
  - id `680091133` `—` 4.288 km from plot `{'railway': 'rail'}`
  - id `919730631` `—` 5.431 km from plot `{'railway': 'rail'}`

### bridges_culverts — *obtained*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:38:02.634975+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** OSM point/way locations; effective opening size NOT available — treat as locations only.
- **Datum note:** OSM geometry is WGS84 (EPSG:4326); no vertical datum — relates to DEM only via horizontal CRS; do NOT use for absolute elevation.
- **Confidence:** `medium`
- **Note:** Bridges/culverts/tunnels — found 2.
- **Sample features:**
  - id `254573867` `MDR55` 2.572 km from plot `{'bridge': 'yes', 'highway': 'secondary', 'ref': 'MDR55'}`
  - id `254573869` `MDR55` 1.611 km from plot `{'bridge': 'yes', 'highway': 'secondary', 'ref': 'MDR55'}`

### flood_control — *unavailable*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:38:04.200957+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** OSM point/way locations; operational data NOT in OSM.
- **Datum note:** n/a
- **Confidence:** `low`
- **Note:** Flood-control structures (dams/weirs/gates) — none found within 3.0 km.

### gauge_observations — *unavailable*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:38:04.201005+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** Gauge stage/discharge from CWC / India-WRIS / BBMB — not available via OSM. Requires external reconciliation (datum vs EGM2008).
- **Datum note:** n/a
- **Confidence:** `low`
- **Note:** CWC/India-WRIS/BBMB gauge data not yet ingested; recorded as unavailable pending external data step.

### documented_flood_extents — *unavailable*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:38:04.201018+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** Historical flood extents event-based (build validation dataset later); not available via OSM.
- **Datum note:** n/a
- **Confidence:** `low`
- **Note:** No documented flood extents ingested yet.

### local_survey — *unavailable*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:38:04.201029+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** Requires surveyed ground points / <30 m elevation (drone/LiDAR/survey) — not in OSM.
- **Datum note:** n/a
- **Confidence:** `low`
- **Note:** local survey not yet obtained; required for plot-level credibility.

### high_res_dem — *unavailable*

- **Source / dataset:** `OpenStreetMap` / `osm-overpass`
- **Retrieved at (UTC):** `2026-09-01T18:38:04.201039+00:00`
- **License:** `ODbL 1.0 — © OpenStreetMap contributors`
- **Coverage:** within 3.0 km of the plot
- **Resolution note:** Requires surveyed ground points / <30 m elevation (drone/LiDAR/survey) — not in OSM.
- **Datum note:** n/a
- **Confidence:** `low`
- **Note:** high-res DEM not yet obtained; required for plot-level credibility.

## Reconciliation (per J.1 / J.3)

- **`plot_level_credible`:** `False` (requires local survey + high-res DEM available).
- **Missing for plot-level credibility:** `['local_survey', 'high_res_dem']`

### Connectivity on the real 30 m DEM reach

- **Assessed result:** `unresolved`
- **Reason:** `Hydraulic connectivity unresolved at 30 m DEM resolution.`

| check | passed |
|-------|--------|
| channel_centerline_present | `True` |
| documented_local_drainage | `True` |
| terrain_reach_resolvable | `False` |
| definitive_barrier | `False` |

Because `terrain_reach_resolvable` is false, connectivity is **UNRESOLVED** — the 30 m DEM cannot rout the flat reach, so no path is fabricated and no flood depth is computed. This is the expected, honest outcome at 30 m resolution per design §J.1.

## What each status means

- **obtained** — present, authoritative enough, adequate for the purpose.
- **unavailable** — genuinely not present in the queried sources (0 found).
- **insufficient resolution** — present but too coarse to resolve the claim.
- **conflicting** — present but multiple features disagree (surfaced, low confidence, not silently reconciled).

## Not done yet (deferred by user directive)

- Flood solver / 2D hydraulic model — not started.
- Gauge reconstruction (CWC/BBMB/India-WRIS) — recorded `unavailable`, pending external data.
- Local survey & high-res DEM — recorded `unavailable`, required for plot-level credibility.

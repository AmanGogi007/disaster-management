# V0.3 Phase 1f — Local-Survey Specification & High-Resolution DEM Sources

_Status: specification complete — nothing measured or fabricated. Values stay None/unverified until real, provenance-carrying field data arrives. Connectivity remains UNRESOLVED; solver NOT run._

- Plot: `31.05, 76.53` (Ropar)
- Generated at (UTC): `2026-09-01T20:58:53.416673+00:00`
- Connectivity status: `Hydraulic connectivity unresolved at 30 m DEM resolution.`
- Plot-level credibility (J.3): `False` (still False — survey + high-res DEM required)
- Surveyed elevations integrated: `0`

## Gate statements

> No survey or elevation measurement may be assumed, guessed, or fabricated. Only verified observations (with provenance, horizontal/vertical datum, and reported accuracy) may be integrated. Until such data resolves the reach, hydraulic connectivity stays UNRESOLVED and no flood depth is produced. The flood solver is NOT run in this phase.

> A satellite-based sub-30 m DEM may reduce, never remove, the need for field verification of microtopography, culvert inverts and crossing openings. Datum differences (EGM96 / EGM2008 / MSL) are never fused; each acquisition keeps its own datum and uncertainty. No DEM source is treated as surveyed ground.

## High-resolution DEM source determination

Statuses: `available` only when genuinely verified; everything else is `commercial` or `unverified` (never silently assumed).

| Source | Res (m) | Vertical datum | Licence | Suitability | Status | Recommended |
|---|---|---|---|---|---|---|
| ALOS World 3D 30m (AW3D30) | 30.0 | EGM96 | JAXA free with terms | cross-check only (similar res, different datum). | unverified | - |
| ALOS PALSAR RTC (12.5 m) | 12.5 | radar backscatter — NOT an elevation DEM | open (NASA/ASF) | surface/texture/change detection only. | unverified | - |
| Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m) | 10.0 | EGM96 / regional MSL hybrid | NRSC Data Policy, registration + approval | closest public sub-30 m satellite DEM; still a DSM (roofs/vegetation), still needs field check. | unverified | yes |
| TanDEM-X WorldDEM (12 m) | 12.0 | WGS84 ellipsoid → EGM2008 product | commercial (DLR proposal/data grant) | good resolution but DSM + licensing cost; not needed if Cartosat-1 + survey proceed. | unverified | - |
| Drone photogrammetry / GNSS-RTK survey | 0.1 | orthometric via GNSS-RTK + BM tie | paid survey | PRIMARY resolver of the plot-level elevation blocker (pair with the survey spec). | unverified | - |
| National / state LiDAR (India) | - | varies (orthometric expected) | policy-dependent | would be ideal if available; verify before use. | unverified | - |

### Live reachability probes (this environment)

Reachable portal ≠ verified tile: coverage/approval is still required at acquisition time.

- **Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m):** reachable (HTTP 200); tile/coverage NOT requested
- **ALOS PALSAR RTC (12.5 m):** reachable (HTTP 200); tile/coverage NOT requested
- **ALOS World 3D 30m (AW3D30):** unreachable from this environment (HTTPError)
- **TanDEM-X WorldDEM (12 m):** reachable (HTTP 200); tile/coverage NOT requested

## Local-survey acquisition specification

**21 measurement classes.** Every `measured_value` is `None` until delivered and verified.

### Plot / building grading — `plot_grading`

- **Derived from:** `plot_context`
- **Points required:** minimum 5x5 grid at ≤5 m over the developable area; finer (≤2 m) along any drainage fall
- **Spacing:** ≤5 m (≤2 m at grading transitions)
- **Fields to measure:** ground elevation; yard fall direction; top of any internal bund/wall; building corner plinths if buildings exist
- **Vertical datum requirement:** orthometric via GNSS-RTK (NTRIP or CORS), tied to a temporary benchmark
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.02 m; horizontal ±0.05 m (RTK)
- **Feature references:**
  - `Ground elevation grid around plot (31.05, 76.53)` — OSM `n/a` (`unnamed`); 30 m GLO-30 shows 0.0° slope here; micro-grading (ditches, bunds, yard fall) is unresolved and must be field-measured.

### Plot boundary cadastre — `property_boundary`

- **Derived from:** `plot_context`
- **Points required:** all boundary vertices + corners
- **Spacing:** vertices
- **Fields to measure:** boundary coordinates; boundary length; offset of building to boundary
- **Vertical datum requirement:** n/a (horizontal cadastre)
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** horizontal ±0.05 m
- **Feature references:**
  - `Property boundary around (31.05, 76.53)` — OSM `n/a` (`unnamed`); Current working geometry is a point only; survey must supply the parcel polygon so 'inside the plot' DEM cells become well-defined.

### Sutlej bank (near plot) — `channel_bank`

- **Derived from:** `reconciled_osm`
- **Points required:** cross-sections at ≥3 stations within radius including the nearest approach
- **Spacing:** profile points ≤10 m along each cross-section
- **Fields to measure:** bank crest elevation; toe/berm elevation; bed elevation near bank; water surface elevation on survey day; bank height
- **Vertical datum requirement:** orthometric (BM-tied); record EGM2008 contribution via GNSS geoid model
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.02 m at crest; ±0.05 m bed
- **Feature references:**
  - `Bank crest + bed near the mapped main-stem way` — OSM `41539116` (`Sutlej`); Mapped main stem (OSM); the river here runs along the bank line ~0.13 km from the plot — measure bank crest, berm, bed, and water line during the survey.
  - `Bank crest + bed near the mapped main-stem way` — OSM `165931479` (`Sutlej`); Mapped main stem (OSM); the river here runs along the bank line ~0.13 km from the plot — measure bank crest, berm, bed, and water line during the survey.
  - `Bank crest + bed near the mapped main-stem way` — OSM `377207447` (`unnamed`); Mapped main stem (OSM); the river here runs along the bank line ~0.13 km from the plot — measure bank crest, berm, bed, and water line during the survey.
  - `Bank crest + bed near the mapped main-stem way` — OSM `919730633` (`Sutlej`); Mapped main stem (OSM); the river here runs along the bank line ~0.13 km from the plot — measure bank crest, berm, bed, and water line during the survey.

### Local canal/drain invert — `drainage_invert`

- **Derived from:** `reconciled_osm`
- **Points required:** invert at ≤50 m intervals across the radius; crest at least at ends
- **Spacing:** ≤50 m along invert
- **Fields to measure:** invert elevation; crest/berm elevation; bed slope between stations; wetted/perched water level; blockages
- **Vertical datum requirement:** orthometric (BM-tied)
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.02 m invert, ±0.05 m berm
- **Feature references:**
  - `Invert + berm of the local canal/drain` — OSM `377207446` (`unnamed`); Local channel carries/removes local drainage. Measure invert (bottom of flow) elevation, berm/crest, bed slope, and any blockage.

### Culvert/bridge crossing — `culvert_crossing`

- **Derived from:** `reconciled_osm`
- **Points required:** each opening: invert(L) + invert(R) + soffit + approaches + any second barrel
- **Spacing:** per opening
- **Fields to measure:** culvert invert elevation (up/down); soffit elevation; opening width × height; road/rail crown above; debris/silt level
- **Vertical datum requirement:** orthometric; culvert invert is the critical hydraulic control — highest precision
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.01 m at inverts
- **Feature references:**
  - `Opening geometry + inverts of the crossing` — OSM `254573867` (`MDR55`); Crossing is on the mapped network; its actual opening size and invert/soffit control local conveyance and must be field-measured — never inferred from OSM.
  - `Opening geometry + inverts of the crossing` — OSM `254573869` (`MDR55`); Crossing is on the mapped network; its actual opening size and invert/soffit control local conveyance and must be field-measured — never inferred from OSM.

### Rail/road barrier crown — `barrier_crown`

- **Derived from:** `reconciled_osm`
- **Points required:** crown profile at ≥2 stations each, incl. at any crossing
- **Spacing:** ≤10 m along profile
- **Fields to measure:** top-of-rail/crown elevation; adjoining ground on each side; any gap/culvert through the barrier
- **Vertical datum requirement:** orthometric (BM-tied)
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.02 m
- **Feature references:**
  - `Top-of-rail / carriageway crown of the barrier` — OSM `680091133` (`unnamed`); Barrier profile perpendicular to the feature, at the crossing points and at the lowest approach so the barrier's blocking/overtopping behaviour is known.
  - `Top-of-rail / carriageway crown of the barrier` — OSM `919730631` (`unnamed`); Barrier profile perpendicular to the feature, at the crossing points and at the lowest approach so the barrier's blocking/overtopping behaviour is known.

### DEM low-point field check — `low_point_check`

- **Derived from:** `dem_low_point`
- **Points required:** bottom of depression + rim + any outlet
- **Spacing:** profile across the low
- **Fields to measure:** bottom elevation; rim elevation; seasonal water/vegetation; outlet/drain connection
- **Vertical datum requirement:** orthometric (BM-tied)
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.02 m
- **Feature references:**
  - `Depression check at (31.070556, 76.548056)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.024167, 76.530278)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.031667, 76.527500)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.033611, 76.525278)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.035278, 76.528333)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.037222, 76.526667)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.034722, 76.525556)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.
  - `Depression check at (31.032500, 76.526944)` — OSM `n/a` (`unnamed`); GLO-30 indicates a local low here (a DEM depression, NOT connectivity). Field-check whether it is a genuine basin/pond, and its bottom elevation and drainage outlet.

### Benchmark & datum control — `benchmark`

- **Derived from:** `plot_context`
- **Points required:** ≥2 TBMs + ≥1 datum tie
- **Spacing:** n/a
- **Fields to measure:** TBM coordinates; TBM elevation; datum name & reference epoch; offsets to EGM2008
- **Vertical datum requirement:** name the official datum + geoid model + epoch
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** level loop closing ≤±0.01 m
- **Feature references:**
  - `Temporary BM(s) + tie to authoritative vertical datum` — OSM `n/a` (`unnamed`); Establish ≥2 stable temporary benchmarks (curb/monument) and connect them to a Survey of India benchmark / CWC or BBMB datum. Record the EGM96/EGM2008/MSL offsets so every downstream comparison shares one datum.

### Water level (baseline) — `water_level`

- **Derived from:** `plot_context`
- **Points required:** 1 per waterbody near plot
- **Spacing:** n/a
- **Fields to measure:** water surface elevation; date/time (UTC); flow state (dry/low/bankfull)
- **Vertical datum requirement:** orthometric (BM-tied)
- **Horizontal system:** WGS84 (EPSG:4326) + UTM 43N grid
- **Accuracy required:** vertical ±0.02 m
- **Feature references:**
  - `Surface water level in channel/canal (31.05, 76.53)` — OSM `n/a` (`unnamed`); One observation of the water surface on survey day in the nearby channel (identifies freeboard/headwater for the future solver; NOT a flood depth).

## Caveats

- This document specifies WHAT and HOW to measure; every measured_value is None until real field data is delivered and verified.
- No satellite DEM (any resolution) is a substitute for the invert/soffit/crown/benchmark field measurements at a house-scale problem.
- Cartosat-1/Bhuvan is the leading public sub-30 m candidate; its approval, coverage and licences for the exact tile must be confirmed before acquisition. Drone/GNSS-RTK survey is the authoritative resolver of plot-level grading and crossing inverts.
- Datum discipline: GLO-30 is EGM2008, SRTM/AW3D30 are EGM96, Cartosat-1 is EGM96/regional MSL hybrid, survey will be orthometric via GNSS-RTK — never fuse; always carry the datum + offset per observation.
- Hydraulic connectivity remains UNRESOLVED at 30 m and stays so until the fine-scale evidence actually resolves it; the flood solver is NOT run in this phase.

## Required before the solver phase

- Commission the survey per this spec and integrate ONLY verified points (`record_survey_points` gate).
- Acquire a sub-30 m DEM for the plot (recommended: Cartosat-1/Bhuvan, then field-verify); keep its datum explicit.
- Re-run connectivity with the verified fine-scale evidence; only then is the solver allowed to estimate flood depth.

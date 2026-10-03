# V0.3 Phase 1d — Authoritative Flood Evidence (Sutlej / Ropar corridor)

_Status: evidence layer complete — no solver run; gauge values are never converted into plot depths._

- Plot: `31.05, 76.53` (Ropar)
- Local search radius: `3.0 km`
- Gathered at (UTC): `2026-09-01T20:01:22.497085+00:00`

## The gate that governs these numbers

> Gauge readings and historical flood extents are calibration/validation evidence only; no reading or extent is converted into a plot flood depth. The hydraulic relationship between the gauge/event, the river hydraulics, the mapped terrain, the barriers and the Ropar plot is a downstream solver problem and remains unassessed.

## Availability summary

| Kind | Records by status |
|------|-------------------|
| Gauge series | obtained: 2, unavailable: 1 |
| Reservoir level (upstream control) | insufficient: 2, obtained: 1, unavailable: 1 |
| Historical peak flow | obtained: 1 |
| Documented flood extent | obtained: 4 |
| Coverage/network status | unavailable: 2 |

## Per-record detail (provenance · datum · coverage · uncertainty)

### CWC river water level (telemetry, hourly) — national NWDP dataset — *obtained*

- **Kind:** `gauge_series`
- **Source org / dataset:** `CWC / NWDP` / `River Water Level (Telemetry - Hourly), Central Water Commission (CWC)`
- **Source URL:** `https://nwdp.nwic.gov.in/dataset/river-water-level-telemetry-hourly-central-water-commission-cwc`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `National Water Data Portal (open government data)`
- **Spatial coverage:** All-india dataset; resource-level basin coverage (peninsular only)
- **Temporal coverage:** 1961–2025 per resource (hourly)
- **Units:** `m (water level)`
- **Datum note:** Per-station gauge zero vs MSL must hold per resource headers
- **Resolution note:** Hourly telemetry; station-level records
- **Confidence:** `medium`
- **Uncertainty:** Dataset reachable via NWDP CKAN API. The package covers ONLY peninsular river basins (Subernarekha, Brahmani, Mahanadi, Godavari, Krishna, Pennar, Cauvery, Tapi, Narmada, Mahi, Sabarmati, west/east-flowing groups) — it contains NO Indus/Sutlej-basin resource. Verified 2026-09-02 from the package resource list.
- **Note:** Dataset reachable via NWDP CKAN API. The package covers ONLY peninsular river basins (Subernarekha, Brahmani, Mahanadi, Godavari, Krishna, Pennar, Cauvery, Tapi, Narmada, Mahi, Sabarmati, west/east-flowing groups) — it contains NO Indus/Sutlej-basin resource. Verified 2026-09-02 from the package resource list.

### CWC gauge series for the Sutlej / Ropar reach — *unavailable*

- **Kind:** `gauge_series`
- **Source org / dataset:** `CWC / NWDP` / `Sutlej-basin level series (none published in NWDP RWL package)`
- **Source URL:** `https://sandrp.in/2019/09/25/overview-of-cwc-flood-forecasting-sites-2019-north-india/`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `n/a`
- **Spatial coverage:** Sutlej reach near Ropar (31.05N, 76.53E, r=3 km)
- **Temporal coverage:** n/a
- **Units:** `n/a`
- **Datum note:** n/a
- **Resolution note:** n/a
- **Confidence:** `low`
- **Uncertainty:** CWC flood-forecasting network has NO site in Punjab: the single site added in 2019 is inactive, and no level-forecast station exists in the Sutlej basin (only monitoring stations in Himachal Pradesh, far upstream: Rampur, Pandoa, Titang...). The NWDP RWL telemetry package lists no Indus/Sutlej resource. Both verified on 2026-09-02.
- **Note:** Authoritative absence with stated reasons — NOT a silent gap. The Ropar reach has no CWC telemetry level series in the machine-readable portal.

### CWC river discharge (manual, daily) — national NWDP dataset — *obtained*

- **Kind:** `gauge_series`
- **Source org / dataset:** `CWC / NWDP` / `River Discharge (Manual - Daily), Central Water Commission (CWC)`
- **Source URL:** `https://nwdp.nwic.gov.in/dataset/river-discharge-manual-dailly-central-water-commission-cwc`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `National Water Data Portal (open government data)`
- **Spatial coverage:** All-india dataset; state-grouped resources (no Indus-system states)
- **Temporal coverage:** 1950–2025 per resource (daily)
- **Units:** `m³/s (discharge)`
- **Datum note:** n/a
- **Resolution note:** Daily manual observations; station-level records
- **Confidence:** `medium`
- **Uncertainty:** Dataset reachable via NWDP CKAN API. The package is state-grouped and contains NO Punjab / Himachal J&K resource (no Indus-system state). Verified 2026-09-02 from the package resource list.
- **Note:** Dataset reachable via NWDP CKAN API. The package is state-grouped and contains NO Punjab / Himachal J&K resource (no Indus-system state). Verified 2026-09-02 from the package resource list.

### BBMB Bhakra reservoir level — NWDP manual-daily resource — *insufficient resolution*

- **Kind:** `reservoir_level`
- **Source org / dataset:** `BBMB / NWDP` / `Reservoir Water Level (Manual - Daily) BBMB (1970–2025)`
- **Source URL:** `https://nwdp.nwic.gov.in/dataset/reservoir-water-level-manual-daily-bhakra-beas-management-board-chandigarh`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `National Water Data Portal (open government data)`
- **Spatial coverage:** Bhakra Dam, Bilaspur HP (31.4156N, 76.4347E) ~45 km upstream of plot
- **Temporal coverage:** 1970–2025 (daily)
- **Units:** `m (per CSV header)`
- **Datum note:** Levels in metres in CSV; BBMB bulletin publishes feet (FRL 1680 ft ≈ 512.06 m)
- **Resolution note:** Daily reservoir level
- **Confidence:** `low`
- **Uncertainty:** Resource 'Reservoir Water Level ... (1970 - 2025) Manual Daily' contains a row for station 'Bhakra Dam RL1700_BBMB' (Satluj, Indus, 31.4156N, 76.4347E) BUT the published values are placeholder-quality (sequence 1,2,3,4,5 m and -999 fillers) — recorded insufficient, NOT credible as observations. Verified 2026-09-02 by direct download + inspection.
- **Note:** Resource 'Reservoir Water Level ... (1970 - 2025) Manual Daily' contains a row for station 'Bhakra Dam RL1700_BBMB' (Satluj, Indus, 31.4156N, 76.4347E) BUT the published values are placeholder-quality (sequence 1,2,3,4,5 m and -999 fillers) — recorded insufficient, NOT credible as observations. Verified 2026-09-02 by direct download + inspection.
- **Sample values:**
  - `{'station': 'Bhakra Dam RL1700_BBMB', 'lat': 31.41555556, 'lon': 76.43472222, 'value_m': 1.0, 'quality': 'placeholder — not credible'}`

### BBMB reservoir level — NWDP telemetry-hourly resources — *insufficient resolution*

- **Kind:** `reservoir_level`
- **Source org / dataset:** `BBMB / NWDP` / `Reservoir Water Level (Telemetry - Hourly) BBMB`
- **Source URL:** `https://nwdp.nwic.gov.in/dataset/reservoir-water-level-telemetry-hourly-bhakra-beas-management-board-chandigarh`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `National Water Data Portal (open government data)`
- **Spatial coverage:** BBMB reservoirs/powerhouses (Bhakra, Pong, Baspa, Karcham Wangtu)
- **Temporal coverage:** 1970–2030 (hourly)
- **Units:** `m (per CSV header)`
- **Datum note:** Levels in metres in CSV; BBMB bulletin publishes feet (FRL 1680 ft ≈ 512.06 m)
- **Resolution note:** Hourly reservoir level
- **Confidence:** `low`
- **Uncertainty:** The hourly BBMB telemetry resources (1970–2030) exist; the 2026–2030 resource inspected 2026-09-02 contains only station rows for 'Baspa PH' and 'Karcham Wangtu PH' (Satluj catchment powerhouses) — NO Bhakra reservoir rows in that file. Bhakra telemetry may reside in the 1970–2025 file (not inspected, 12 MB) — recorded uncertain, not assumed.
- **Note:** The hourly BBMB telemetry resources (1970–2030) exist; the 2026–2030 resource inspected 2026-09-02 contains only station rows for 'Baspa PH' and 'Karcham Wangtu PH' (Satluj catchment powerhouses) — NO Bhakra reservoir rows in that file. Bhakra telemetry may reside in the 1970–2025 file (not inspected, 12 MB) — recorded uncertain, not assumed.
- **Sample values:**
  - `{'station': 'Baspa PH_BBMB', 'river': 'Beas', 'level_m': 2530.981, 'note': 'upstream powerhouse, not Bhakra'}`

### BBMB Bhakra reservoir bulletin — daily live value — *unavailable*

- **Kind:** `reservoir_level`
- **Source org / dataset:** `BBMB` / `Reservoir Data bulletin (daily reservoir level / inflow / outflow)`
- **Source URL:** `https://bbmb.gov.in/data-reservoir.htm`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `BBMB public bulletin (© BBMB)`
- **Spatial coverage:** Bhakra Dam (31.4156N, 76.4347E) ~45 km upstream of plot
- **Temporal coverage:** snapshot (not captured)
- **Units:** `level ft; inflow/outflow cusecs`
- **Datum note:** BBMB gauge datum in feet; FRL 1680 ft, MWL 1690 ft, top of dam 1700 ft
- **Resolution note:** Daily (06:00) bulletin values
- **Confidence:** `low`
- **Uncertainty:** bbmb.gov.in bulletin pages unreachable from the research environment on 2026-09-01 (fetch failure after 2 attempts). This is a FETCH FAILURE, not certified absence; the bulletin is published daily and indexed snapshots exist (see documented records).
- **Note:** Fetch failure recorded honestly; no fabricated level value.

### Sutlej peak flow at Ropar — 9 Sep 1988 flood (worst on record) — *obtained*

- **Kind:** `peak_flow_record`
- **Source org / dataset:** `BBMB / Punjab Drainage records (via press)` / `Historical peak discharge record at Ropar headworks`
- **Source URL:** `https://indianexpress.com/article/cities/chandigarh/punjab-first-time-after-1988-floods-sutlej-carrying-more-than-its-capacity/`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `n/a (cited reporting)`
- **Spatial coverage:** Ropar headworks on the Sutlej (31.05N, 76.53E reach)
- **Temporal coverage:** 9 Sep 1988 (event)
- **Units:** `cusecs`
- **Datum note:** Flow (not stage); cusec ≈ 0.02832 m³/s
- **Resolution note:** Single peak value from official/BBMB records as reported
- **Confidence:** `medium`
- **Uncertainty:** Reported 4,55,411 cusecs on 9 Sep 1988, described as the worst-ever Sutlej flood in Punjab; sources are press quoting BBMB/Punjab drainage records — medium confidence, not a primary gauge chart.
- **Note:** Canonical documented peak for the Ropar reach; used later as a calibration/design event, never as a plot depth.
- **Sample values:**
  - `{'date': '1988-09-09', 'peak_cusecs': 455411, 'location': 'Ropar'}`

### September 1988 flood inundation mapping (Sutlej, upstream of Ropar) — *obtained*

- **Kind:** `flood_extent`
- **Source org / dataset:** `National Institute of Hydrology (NIH)` / `Flood inundation + flood-plain mapping of the 1988 flood, IRS LISS-II`
- **Source URL:** `https://www.indiawaterportal.org/climate-change/disasters/flood-studies-satluj-basin-research-report-national-institute-hydrology`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `NIH research report (via India Water Portal)`
- **Spatial coverage:** ~50 km Sutlej reach upstream of Roopnagar (Ropar) + 181 km planform reach downstream
- **Temporal coverage:** Sep 1988 event
- **Units:** `satellite-derived inundation classes`
- **Datum note:** IRS LISS-II (23.5 m) + FCC 1:250,000 rectified mapping
- **Resolution note:** Satellite flood-inundation mapping with damage classes
- **Confidence:** `medium`
- **Uncertainty:** Mapped with 1980s satellite data (LISS-II); right-flank areas reported more inundated than left; includes Ropar headworks conveyance-capacity assessment. Use as extent/calibration evidence, not plot depth.
- **Note:** Documented spatial extent of the design flood for the Ropar reach.
- **Sample values:**
  - `{'event': 'Sep 1988', 'mapper': 'NIH (IRS LISS-II)', 'reach_km_upstream_of_ropar': 50}`

### Sutlej flood Aug 2019 at Ropar/Phillaur — village-level inundation — *obtained*

- **Kind:** `flood_extent`
- **Source org / dataset:** `Punjab govt / Punjab Drainage Dept (via press + surveys)` / `District/village-level inundation + crop-damage survey (2019)`
- **Source URL:** `https://indianexpress.com/article/india/initial-crop-damage-survey-over-one-lakh-acres-submerged-crops-in-13-districts-hit-5926796/`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `n/a (cited reporting + govt survey)`
- **Spatial coverage:** Ropar (~95 villages, ~13,800 acres), Jalandhar, Ferozepur, Kapurthala districts
- **Temporal coverage:** 17–20 Aug 2019 (event)
- **Units:** `villages / acres / cusecs`
- **Datum note:** Flow at Phillaur; no Ropar-reach stage gauge
- **Resolution note:** Village/acre level official survey granularity
- **Confidence:** `medium`
- **Uncertainty:** Phillaur peak ~2.65–2.75 lakh cusecs (highest since 1988; carrying capacity Ropar–Harike ~2.0 lakh cusecs). Ropar district ~95 villages inundated; ~300 villages across Ropar/Jalandhar/Ferozepur; natural calamity declared; Dhussi bandh breach reported. Press + govt survey reporting, medium confidence.
- **Note:** Nearest-to-plot documented inundation event (Ropar district).
- **Sample values:**
  - `{'year': 2019, 'district': 'Ropar', 'villages_inundated': 95, 'acres_damaged': 13800}`
  - `{'year': 2019, 'peak_phillaur_cusecs': 265000}`

### Aug 2023 satellite-observed flood water on the Sutlej — *obtained*

- **Kind:** `flood_extent`
- **Source org / dataset:** `NASA EO / USGS Landsat` / `Landsat 9 OLI-2 flood imagery of the Sutlej (Aug 2023)`
- **Source URL:** `https://landsat.visibleearth.nasa.gov/view.php?id=151754`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `NASA/USGS Landsat — public domain`
- **Spatial coverage:** Sutlej downstream of Ropar — Firozpur reach (India/Pakistan border), NOT the Ropar corridor
- **Temporal coverage:** 2023-08-19 (with 2023-06-16 pre-flood)
- **Units:** `imagery (water surface)`
- **Datum note:** Satellite surface-water extent; no stage
- **Resolution note:** 30 m OLI-2 imagery
- **Confidence:** `high`
- **Uncertainty:** Documents the 2023 Sutlej flood extent ~150 km downstream of the plot. It does NOT establish inundation at the Ropar plot; recorded for the Sutlej flood library only.
- **Note:** Documented extent, correctly NOT extrapolated to the Ropar plot.
- **Sample values:**
  - `{'acquisition': '2023-08-19', 'sensor': 'Landsat 9 OLI-2', 'reach': 'Firozpur (downstream of Ropar)'}`

### Global Flood Database v1 (DFO/MODIS) — *obtained*

- **Kind:** `flood_extent`
- **Source org / dataset:** `DFO / Floodbase / Tellman et al. 2021` / `Global Flood Database v1 — 913 events, 2000–2018, MODIS 250 m`
- **Source URL:** `https://global-flood-database.cloudtostreet.info/`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `CC-BY (GFD)`
- **Spatial coverage:** Global; includes India events (316 recorded by DFO)
- **Temporal coverage:** 2000-02-17 to 2018-12-10
- **Units:** `flooded/duration/jrc_perm_water bands`
- **Datum note:** WGS84 raster at 30 arc-sec; hydroSHEDS-based event regions
- **Resolution note:** 250 m (MODIS) flood extent + duration
- **Confidence:** `medium`
- **Uncertainty:** Per-event extraction intersecting the Ropar corridor bbox has NOT been performed at this checkpoint (deferred step). Station/event catalog is reachable (verified 2026-09-02).
- **Note:** Dataset catalogued; corridor intersection extraction deferred.

### CWC flood-forecasting network coverage near Ropar — *unavailable*

- **Kind:** `network_status`
- **Source org / dataset:** `CWC / SANDRP compilations of the CWC FF network` / `CWC flood-forecasting site network (2018/2019/2025)`
- **Source URL:** `https://sandrp.in/2025/07/09/himachal-pradesh-why-cwcs-forecasting-is-unavailable-amidst-flood-disaster/`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `n/a (compilations)`
- **Spatial coverage:** Punjab (none) / Himachal Sutlej sites (Rampur, Pandoa, Titang, Powari, Nathpa — monitoring only)
- **Temporal coverage:** 2018–2025 network status
- **Units:** `sites`
- **Datum note:** n/a
- **Resolution note:** Network-level (site presence)
- **Confidence:** `high`
- **Uncertainty:** CWC has no flood-forecasting or level-forecast station in the Sutlej basin; the single Punjab site added in 2019 is inactive; Sutlej monitoring sites are far upstream in Himachal Pradesh (HFLs recorded 2005-08-03 at Rampur/Titang/etc.). No station at Ropar.
- **Note:** Explains WHY no CWC Ropar gauge series is expected: authoritative network coverage statement.

### India-WRIS hydro-meteorological station registry — *unavailable*

- **Kind:** `network_status`
- **Source org / dataset:** `India-WRIS (CWC/MoJS + NRSC-ISRO)` / `CWC Hydro-Meteorological Sites registry (901 HMS)`
- **Source URL:** `https://indiawris.gov.in/wiki/doku.php?id=cwc_hydro-meteorological_sites`
- **Retrieved at (UTC):** `2026-09-01T20:01:22.497085+00:00`
- **License:** `India-WRIS (government open access)`
- **Spatial coverage:** India-wide HMS registry
- **Temporal coverage:** registry as published
- **Units:** `stations`
- **Datum note:** n/a
- **Resolution note:** Registry-level
- **Confidence:** `low`
- **Uncertainty:** indiawris.gov.in was unreachable from the research environment on 2026-09-01 (fetch failure after 2 attempts) — recorded as a FETCH FAILURE, not certified absence. Registry documented via India-WRIS/NGI wiki + CWC sources.
- **Note:** Registry endpoint not live-verifiable at this checkpoint.

### BBMB Bhakra reservoir bulletin — indexed snapshots (FRL/MWL + recent) — *obtained*

- **Kind:** `reservoir_level`
- **Source org / dataset:** `BBMB` / `BBMB Reservoir Data (indexed bulletin snapshots)`
- **Source URL:** `https://www.bbmb.gov.in/index.htm`
- **Retrieved at (UTC):** `n/a (cited)`
- **License:** `BBMB public bulletin (© BBMB)`
- **Spatial coverage:** Bhakra Dam (31.4156N, 76.4347E) ~45 km upstream of plot
- **Temporal coverage:** snapshots: 2025-09-04 and 2026-08-21
- **Units:** `level ft; inflow/outflow cusecs`
- **Datum note:** BBMB gauge datum in feet; FRL 1680 ft, MWL 1690 ft, top of dam 1700 ft
- **Resolution note:** Daily (06:00) bulletin values
- **Confidence:** `medium`
- **Uncertainty:** Two independent indexed snapshots: 4 Sep 2025 — Bhakra 1678.97 ft, inflow 95435, outflow 73459 cusecs; 21 Aug 2026 —Bhakra 1629.32 ft, inflow 48309, outflow 24112 cusecs. FRL constant 1680 ft (≈512.06 m). Confidence medium (indexed copies, consistent).
- **Note:** Bhakra level is the headwater control for any dam-break / release scenario at Ropar; it is upstream-boundary evidence, NOT a plot depth.
- **Sample values:**
  - `{'date': '2025-09-04', 'level_ft': 1678.97, 'inflow_cusecs': 95435, 'outflow_cusecs': 73459}`
  - `{'date': '2026-08-21', 'level_ft': 1629.32, 'inflow_cusecs': 48309, 'outflow_cusecs': 24112}`

## Why the Ropar-reach gauge stays UNAVAILABLE (stated, not silent)

- CWC flood-forecasting network has **no station in Punjab**; the single site added in 2019 is inactive; no level-forecast station exists anywhere in the Sutlej basin (CWC sites are monitoring-only, far upstream in HP).
- The NWDP machine-readable **CWC river-level package has no Indus/Sutlej resource** (peninsular basins only); the discharge package has no Indus-system state resource. The **BBMB manual-daily Bhakra resource contains placeholder-valued rows** (1,2,3,4,5 m −999) — recorded `insufficient`, never treated as observations.
- The live BBMB daily bulletin is **unreachable from this environment** (fetch failure, retried); indexed snapshots (2025-09-04, 2026-08-21) are recorded with FRL/MWL constants. The only genuine in-catchment controller is Bhakra Reservoir — upstream-boundary evidence, not a Ropar plot depth.

## Deferred (next steps, not run here)

- GFD/DFO corridor-intersection extraction for 2000–2018 events.
- Download + station-filter NWDP CWC/BBMB CSVs when a Sutlej resource exists; re-verify BBMB Bhakra telemetry file (1970–2025, 12 MB).
- Establish the hydraulic relationship (solver phase): Bhakra release → Ropar reach flow → terrain → barriers → plot.
- Local survey + high-res DEM (still required for plot-level credibility).

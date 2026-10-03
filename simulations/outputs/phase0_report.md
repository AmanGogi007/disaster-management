# V0.3 Phase 0 — Real Terrain (Bhakra→Ropar) Validation

**REAL DEM: SUCCESS**

## DEM metadata
- **source_resolution_m**: 30.92
- **simulation_grid_m**: 30.92
- **horizontal_crs**: EPSG:4326
- **vertical_datum**: EGM2008
- **vertical_offset_m**: 0.0
- **dataset**: Copernicus DEM GLO-30
- **provenance**: https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N31_00_E076_00_DEM/Copernicus_DSM_COG_10_N31_00_E076_00_DEM.tif

## Preprocessing
- **cell_count**: 2318040
- **shape**: [1692, 1370]
- **source_resolution_m**: 30.92
- **simulation_grid_m**: 30.92
- **vertical_datum**: EGM2008
- **preproc_s**: 0.4
- **hand_computed**: True
- **catchment_cells**: 1076
- **pour_cell**: (1173, 1119)
- **pour_elevation_m**: 295.37
- **note**: real terrain processed with pysheds; HAND held as prior only

## Plot terrain
- **lat**: 31.05
- **lon**: 76.53
- **demo_elevation_m**: 267.5
- **hand_prior_m**: None
- **dem_extent**: [31.0, 76.2997, 31.47, 76.6803]
- **flat_reach_note**: Plot cell and 8 neighbours are exactly flat (267.5 m): D8 direction undefined, HAND unset, accumulation=1. 30 m DSM cannot resolve channel micro-topography near Ropar.

## Dynamic domain / compute footprint
- **bbox_deg**: [30.98, 76.3, 31.47, 76.68]
- **cell_count**: 2318040
- **grid_rows**: 1692
- **grid_cols**: 1370
- **approx_extent_sqkm**: 1961.83
- compute_footprint:
- **  preproc_s**: 0.4
- **  memory_elev_mb**: 9.27
- **  arrays**: ['pit_filled', 'flow_direction', 'accumulation', 'hand', 'catchment']

## Network↔terrain reconciliation
- **method**: compare DEM flow-direction at plot with OSM downstream_trace
- **status**: OK
- **network_available**: True
- **network_reason**: None
- **downstream_available**: True
- **downstream_reason**: None
- **downstream_trace_km**: None
- **downstream_direction_field**: None
- **main_stem**: None
- **upstream_node_count**: 743
- **nearest_river**: {'name': 'Sutlej', 'osm_id': '919730633', 'type': 'river', 'distance_km': 0.279}
- **dem_drainage_termination_km**: 0.0
- **dem_direction_field**: None

## Channel / DEM adequacy
- **plot_in_dem**: True
- **local_40x40_window**: {'rows_range': [1492, 1532], 'cols_range': [808, 848]}
- **window_min_m**: 267.0
- **window_max_m**: 299.5
- **window_relief_m**: 32.5
- **note**: 30 m DSM: channel incision/embankments/bridges/culverts generally NOT resolvable; OSM recalibration for depth, not bathymetry.

## Plots
- simulations/outputs/phase0_plot_dem.png
- simulations/outputs/phase0_plot_hand.png
- simulations/outputs/phase0_plot_cross_section.png

## Caveats
- DEM datum is EGM2008 (GLO-30). Dam/gauge absolute elevations (Bhakra crest/FSL, Ropar) come from separate sources; offset vs EGM2008 is NOT resolved here -> confidence=low on any absolute-elevation comparison until the dam/gauge datum is reconciled.
- Ropar plot is on a flat floodplain cell (267.5 m, all 8 neighbours equal): D8 flow direction, HAND and flow accumulation are degenerate there. HAND is treated as prior only; the solver (water surface + momentum + roughness) decides reachability, NOT D8/HAND.
- OSM downstream reach unavailable at the plot point (None); upstream reach available (743 nodes). Sutlej centreline recognised {'name': 'Sutlej', 'osm_id': '919730633', 'type': 'river', 'distance_km': 0.279}.
- 30 m DSM: channel incision, embankments, bridges, culverts generally NOT resolvable on this reach; OSM used for network/channel geometry, not bathymetry.

## Total runtime (s)
- **total**: 40.41

> Synthetic DEM never counted as success. GLO-30 EGM2008 primary; SRTM EGM96 documented fallback.

# Data Sources

Every external dataset used by the engine must be listed here.
Datasets MUST NOT be silently mixed.

## V0.1 providers

| Provider | Module | What it provides | Default | License | Notes |
|---|---|---|---|---|---|
| `sample` | `packages/geo/terrain/provider.py` | Synthetic DEM | yes (DEM) | CC0 (synthetic — **NOT survey data**) | Offline dev only. Explicitly labelled as synthetic in every response. |
| `stub` | `packages/geo/terrain/provider.py` | Nothing | — | n/a | Used to verify missing-DEM handling. |
| `osm` (Overpass) | `packages/geo/hydrology/provider.py` | Water features (river/stream/canal/lake/reservoir/pond/wetland/drain/dam/weir) | yes (hydrology) | ODbL 1.0 — © OpenStreetMap contributors | Uses `https://overpass-api.de/api/interpreter` by default. Subject to Overpass rate limits. |
| `stub` | `packages/geo/hydrology/provider.py` | Nothing | — | n/a | Used for fully-offline mode. |

## Real providers (planned, not yet implemented)

| Dataset | Region | Use | License | Notes |
|---|---|---|---|---|
| Copernicus DEM GLO-30 | Global | High-res terrain | Copernicus licence | 30 m; obtain via Copernicus DEM downloader. |
| SRTM GL1 (NASA / OpenTopography) | 60°N–56°S | Terrain fallback | Public domain | API key required for OpenTopography. |
| ASTER GDEM v3 | Global | Terrain fallback | NASA / METI | 30 m. |
| Bhuvan DEM / CartoDEM | India | India terrain | NRSC terms | Per-tile download or WMS/WFS. |
| NRSC Flood Hazard Layers | India | Historical inundation | NRSC terms | Available via Bhuvan / NRSC OGC services. |
| CWC / India-WRIS | India | Reservoirs, dams, river network | Government open data | Manual + scripted download. |
| HydroSHEDS | Global | River network, watersheds | WWF | 15"/30"/60" products. |
| OpenStreetMap | Global | Hydrology, land use | ODbL 1.0 | Already integrated. |

## Attribution

Map tiles (frontend default): © OpenStreetMap contributors.
Hydrology data: © OpenStreetMap contributors (ODbL 1.0).
DEM (default): synthetic sample surface — **NOT survey data**.

## Engineering rules for data sources

1. Every result must include `data_provenance` describing the dataset
   and licence.
2. If a real provider is unavailable, the engine MUST fall back to a
   clearly-labelled sample/stub — never invent values.
3. Mixed licences (e.g. ODbL + NRSC terms) must be shown separately
   in the report.
4. Provider selection is configurable via environment variables
   (`ELEVATION_PROVIDER`, `HYDROLOGY_PROVIDER`).
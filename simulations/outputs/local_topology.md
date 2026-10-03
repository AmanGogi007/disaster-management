# V0.3 Phase 1c — Channel Reconciliation + Local Hydraulic Topology

_Status: reconciliation + topology complete — awaiting review, no solver._

- Plot: `31.05, 76.53` (Ropar)
- Evidence radius: `3.0 km`; endpoint join tolerance: `75.0 m`

## 1. Sutlej main-stem reconciliation

**Resolved:** `True` — confidence `medium`

| role | OSM id | name | min distance to plot (km) | length (km) |
|------|--------|------|--------------------------|-------------|
| main_stem | `919730633` | Sutlej | 0.129 | 2.451 |
| main_stem | `377207447` | — | 0.301 | 1.562 |
| main_stem | `165931479` | Sutlej | 1.152 | 7.009 |
| main_stem | `41539116` | Sutlej | 1.237 | 13.067 |
| unconnected | `248023200` | — | 2.966 | 11.811 |

**Min distance from the main stem to the plot:** `0.129 km`

Reconciliation method: connected-component analysis over shared junction node ids and near-coincident endpoints (≤ 75.0 m). Unconnected ways are reported above as `unconnected`, never dropped.

## 2. Local hydraulic topology (descriptive)

### Local channels / drains

| OSM id | kind | name | min dist (km) | length (km) |
|--------|------|------|---------------|-------------|
| `377207446` | canal | — | 0.555 | 6.23 |

### Potential barriers (roads/railways/embankments)

| OSM id | kind | name | min dist (km) | note |
|--------|------|------|---------------|------|
| `680091133` | railway:rail | — | 2.674 | May act as a barrier only where no hydraulic opening (culvert/bridge) exists; opening data not in OSM. |
| `919730631` | railway:rail | — | 3.17 | May act as a barrier only where no hydraulic opening (culvert/bridge) exists; opening data not in OSM. |

### Crossings (bridges / culverts)

| OSM id | kind | name | on waterway? | min dist (km) |
|--------|------|------|--------------|---------------|
| `254573867` | bridge | MDR55 | no | 2.494 |
| `254573869` | bridge | MDR55 | no | 1.611 |

### Flood-control structures — none found.

## 3. Flow direction at the plot reach

- **Reach direction status:** `unresolved`
- **Plot cell:** `{'row': 1512, 'col': 828, 'elevation_m': 267.5, 'fdir': -1, 'is_flat': True}`
- **Note:** D8 at the plot cell is flat/sink (sentinel) — no resolvable downhill direction at 30 m DEM resolution.

## 4. Connectivity verdict (remains evidence-gated)

- **Assessed result:** `unresolved`
- **Reason:** `Hydraulic connectivity unresolved at 30 m DEM resolution.`

| check | passed |
|-------|--------|
| channel_centerline_present | `True` |
| documented_local_drainage | `True` |
| terrain_reach_resolvable | `False` |
| definitive_barrier | `False` |

> Because `terrain_reach_resolvable` is false, connectivity is **UNRESOLVED** — the flat 30 m reach cannot be routed, so no path is fabricated and no flood depth is computed (design §J.1). The topology above is descriptive only.

## Caveats (explicit, never papered over)

- OSM feature presence does NOT prove hydraulic connectivity.
- No culvert/bridge opening sizes: crossings are locations only, not conveyance estimates.
- A crossing marked on_waterway means it shares a waterway node id or lies within 100 m of a waterway geometry (OSM maps them with separate node ids) — it is a location flag, not an opening-size estimate.
- No vertical (elevation) relationship between OSM objects and the DEM; absolute heights are not comparable across datums.
- Reach direction at the plot: unresolved — D8 at the plot cell is flat/sink (sentinel) — no resolvable downhill direction at 30 m DEM resolution.

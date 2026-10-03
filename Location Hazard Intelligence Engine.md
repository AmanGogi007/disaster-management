# Location Hazard Intelligence Engine
## Project Specification — V0.1

## 1. Project Goal

Build a local-first geospatial application that analyzes a given geographic coordinate and determines its potential exposure to **flooding and water-related hazards**.

The long-term goal is to answer questions such as:

> "If a major upstream dam or reservoir experiences a catastrophic release, what could potentially happen at this exact location?"

The application must eventually support:

- terrain/elevation analysis
- rivers and streams
- reservoirs and dams
- canals and water bodies
- watersheds/catchments
- drainage direction
- historical flooding
- rainfall
- flood propagation
- dam-break scenarios
- flood depth
- flood velocity
- flood arrival time
- inundation duration
- additional natural hazards later

### IMPORTANT

This project is a **decision-support/research tool**, not an emergency warning system and not a replacement for government flood models, engineers, hydrologists, or disaster-management authorities.

The application must never present an estimated/modelled number as an exact real-world prediction.

---

# 2. Development Philosophy

Build this incrementally.

DO NOT attempt to implement the entire vision in V0.1.

V0.1 must establish a reliable geospatial foundation.

The architecture should support progressively adding:

```text
V0.1
Terrain + Hydrology + Basic Flood Exposure
        ↓
V0.2
Watershed + Upstream Infrastructure
        ↓
V0.3
Hydraulic Simulation
        ↓
V0.4
Dam-Breach Scenarios
        ↓
V0.5
Advanced Natural Hazards
```

---

# 3. Recommended Technology Stack

Use:

### Backend

Python 3.12+

FastAPI

Pydantic

GeoPandas

Shapely

Rasterio

PyProj

NumPy

SciPy where useful

xarray where useful

NetworkX for hydrological graph analysis

### GIS / Spatial Database

PostgreSQL + PostGIS

However:

The application MUST also have a local development mode that can operate without PostgreSQL initially.

For V0.1, SQLite/GeoPackage or local files may be used where appropriate.

Do not make cloud infrastructure mandatory.

### Frontend

Next.js + TypeScript

React

MapLibre GL JS preferred for map rendering.

Use OpenStreetMap-compatible basemaps or another legally usable map provider.

### Visualization

Interactive map.

Elevation profile.

Flood-risk overlays.

Terrain raster overlays.

Nearby water infrastructure.

Cross sections where available.

Charts for elevation/depth/distance.

---

# 4. Project Structure

Use a structure approximately like:

```text
location-hazard-engine/
│
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models/
│   │   └── schemas/
│   │
│   └── web/
│       ├── app/
│       ├── components/
│       ├── lib/
│       └── types/
│
├── packages/
│   └── geo/
│       ├── terrain/
│       ├── hydrology/
│       ├── raster/
│       ├── vector/
│       ├── watershed/
│       └── analysis/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── cache/
│   └── samples/
│
├── simulations/
│   ├── scenarios/
│   └── outputs/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── scripts/
│
├── docs/
│
├── docker/
│
├── .env.example
├── docker-compose.yml
├── README.md
└── PROJECT_SPEC.md
```

Keep geospatial algorithms separate from API routes and frontend code.

---

# 5. Core User Workflow

The user should be able to open the application and see:

```text
Location Hazard Intelligence

Enter coordinates

Latitude:
[ 30.xxxxx ]

Longitude:
[ 75.xxxxx ]

Analysis radius:
[ 50 km ]

[ Analyze Location ]
```

After analysis:

```text
Location
30.xxxxx, 75.xxxxx

Elevation
247.4 m

Nearest River
8.7 km

Nearest Major Water Body
12.2 km

Nearest Dam
XX km

Watershed
XXXX

Flood Exposure
MODERATE
```

The map should then show:

- analysis point
- terrain
- rivers
- streams
- reservoirs
- dams
- water bodies
- watershed boundaries
- flood hazard layers where available

---

# 6. Coordinate Input

Accept:

### Required

Latitude

Longitude

### Optional

Analysis radius.

Default:

50 km

Maximum initially:

200 km

Validate:

Latitude:

```text
-90 <= latitude <= 90
```

Longitude:

```text
-180 <= longitude <= 180
```

Support decimal degrees.

Future versions may support:

- Google Maps URL
- address search
- GeoJSON
- KML
- uploaded plot boundary
- polygon coordinates

---

# 7. Terrain / Elevation Engine

This is a critical component.

Do NOT rely exclusively on a single elevation API.

The system should have an abstraction:

```python
class ElevationProvider:
    def get_elevation(...)
    def get_dem(...)
```

Possible providers:

- Copernicus DEM
- SRTM
- ASTER
- national datasets
- Google Elevation API where appropriate

Provider selection must be configurable.

Example:

```text
ELEVATION_PROVIDER=copernicus
```

The system should cache downloaded data.

---

# 8. DEM Analysis

For the analysis area, calculate:

### Point elevation

Elevation at the user's coordinate.

### Minimum elevation

### Maximum elevation

### Mean elevation

### Elevation percentile

### Local relief

Difference between local high and low terrain.

### Slope

Calculate terrain slope from DEM.

### Aspect

Determine slope direction.

### Terrain gradient

Calculate magnitude and direction.

---

# 9. Terrain Profile

Generate terrain profiles between:

```text
Plot
  ↓
nearest river
```

and between:

```text
Plot
  ↓
nearest upstream/downstream hydraulic feature
```

Example:

```text
Elevation
300m |        /\
     |       /  \
250m |------/----\------ Plot
     |              \
200m |               \____ River
     |
     +-------------------------
              Distance
```

The backend should expose profile data as JSON.

---

# 10. Hydrology Dataset

The system must identify water features within the analysis radius.

Categories:

```text
river
stream
canal
lake
reservoir
pond
wetland
drain
dam
```

Do not simply use straight-line distance.

Store geometry.

For each feature calculate:

```text
feature_id
name
type
geometry
distance_to_plot
elevation if available
source
source_date
confidence
```

---

# 11. Water Feature Discovery

For the user's location:

Find:

### Nearest river

### Nearest major river

### Nearest stream

### Nearest reservoir

### Nearest lake

### Nearest dam

### All water bodies

within configured radius.

The UI should allow filtering.

---

# 12. Hydrological Network

Treat rivers and streams as a graph.

Example:

```text
Reservoir A
     |
     v
River A
     |
     +------ Tributary B
     |
     v
River C
     |
     +------ Tributary D
     |
     v
Downstream region
```

The system should eventually determine whether the plot is:

- upstream
- downstream
- laterally adjacent
- outside the drainage system

This is MUCH more important than simple distance.

---

# 13. Watershed / Catchment

Determine the watershed/catchment containing the plot.

Return:

```text
basin
sub-basin
watershed
sub-watershed
```

where data is available.

Display the watershed polygon on the map.

Also determine:

```text
Does water draining from the surrounding terrain naturally move toward the plot?
```

This is an important exposure factor.

---

# 14. Flow Direction

Use DEM-derived flow direction.

Possible algorithms:

- D8
- D-Infinity
- MFD

Start with D8 for V0.1.

Calculate:

```text
flow_direction
flow_accumulation
drainage_network
```

The system should identify local drainage paths.

---

# 15. Relative River Elevation

For nearby rivers calculate:

```text
plot_elevation
river_elevation
relative_elevation
```

Example:

```text
Plot elevation: 245 m
River elevation: 230 m

Difference: +15 m
```

Do NOT interpret this alone as flood safety.

Terrain barriers and hydraulic conditions must also be considered.

---

# 16. Historical Flood Data

Where available, integrate historical flood datasets.

For India, investigate:

- ISRO / NRSC
- Bhuvan
- CWC
- India-WRIS
- state water-resource departments
- disaster-management datasets

Potential information:

```text
historical inundation
flood frequency
flood hazard zones
maximum observed inundation
```

Store source metadata.

Every dataset must retain:

```text
source
dataset_name
dataset_version
date
resolution
license
```

---

# 17. Flood Exposure Model V0.1

V0.1 should NOT perform a full hydraulic simulation.

Instead calculate a transparent exposure score.

Possible factors:

```text
terrain
relative elevation
distance to water
hydrological connectivity
watershed position
historical flood exposure
flow accumulation
local slope
```

Example conceptual score:

```text
Flood Exposure Score: 0-100
```

But DO NOT arbitrarily invent weights.

Put all weights in configuration:

```yaml
flood_exposure:
  distance_weight: ...
  elevation_weight: ...
  connectivity_weight: ...
  historical_flood_weight: ...
  flow_accumulation_weight: ...
```

Document why each factor exists.

---

# 18. Confidence

Every major result should include confidence.

Example:

```json
{
  "flood_exposure": {
    "score": 67,
    "category": "moderate",
    "confidence": "medium"
  }
}
```

Confidence should depend on:

- DEM resolution
- hydrological dataset quality
- dataset age
- missing information
- model limitations

---

# 19. Dam / Reservoir Analysis

Find upstream dams and reservoirs.

For every candidate:

```text
name
location
distance
reservoir
river
upstream/downstream relationship
elevation
source
```

The critical distinction:

### Nearby dam

is NOT necessarily:

### hydraulically relevant dam.

The engine should attempt to determine whether the dam is upstream within the relevant drainage network.

---

# 20. Scenario Engine

Create a generic scenario architecture.

Example:

```python
Scenario(
    name="Dam Breach",
    type="dam_breach",
    source_id="...",
    parameters={}
)
```

Future scenarios:

```text
normal river flood
extreme rainfall
dam release
dam breach
reservoir overtopping
combined rainfall + dam breach
```

---

# 21. Bhakra Dam Example

The system must eventually support:

```text
Scenario:

Bhakra Dam catastrophic breach
```

But V0.1 should NOT claim exact results.

The UI can show:

```text
Bhakra Dam

Hydraulic relevance:
UNKNOWN / POSSIBLE / LIKELY / UNLIKELY

Reason:
The dam is connected to the downstream river network,
but a physical breach simulation has not yet been performed.
```

Later V0.3/V0.4 will perform the actual simulation.

---

# 22. Hydraulic Simulation — FUTURE

For V0.3+ investigate established hydraulic models rather than inventing one.

Potential technologies:

- HEC-RAS
- LISFLOOD-FP
- TELEMAC
- Iber
- other validated 1D/2D hydraulic models

The system should eventually support:

### Input

```text
DEM
river geometry
cross sections
roughness
reservoir characteristics
dam geometry
breach parameters
initial water level
initial river discharge
boundary conditions
```

### Output

```text
water depth
water surface elevation
velocity
flow direction
arrival time
duration
inundation extent
```

---

# 23. Dam Breach Parameters

A catastrophic dam breach is not a single deterministic event.

Model parameters such as:

```text
breach width
breach depth
breach formation time
reservoir elevation
reservoir volume
initial downstream flow
```

must be configurable.

Run multiple scenarios.

Example:

```text
Scenario A
Small breach

Scenario B
Medium breach

Scenario C
Large breach

Scenario D
Extreme breach
```

This is preferable to pretending there is one exact answer.

---

# 24. Monte Carlo / Uncertainty Analysis — FUTURE

Eventually run many simulations with uncertain parameters.

Example:

```text
breach width:
50m - 200m

breach formation:
10min - 60min

reservoir level:
range

downstream flow:
range
```

Then output:

```text
5th percentile
50th percentile
95th percentile
```

This is much more scientifically useful than:

> "The flood will definitely be 2.3m."

---

# 25. Flood Arrival Time

Eventually calculate:

```text
time_to_first_inundation
time_to_0.5m
time_to_1m
time_to_max_depth
```

Example:

```text
First water:
2h 14m

1m depth:
2h 52m

Maximum simulated depth:
3h 37m
```

Always label these as model outputs.

---

# 26. Flood Velocity

Eventually calculate velocity fields.

Example:

```text
Maximum simulated velocity:
3.2 m/s

Median velocity:
0.8 m/s
```

Do not estimate velocity simply from:

```text
distance / time
```

unless explicitly labelled as a crude approximation.

Use hydraulic model output for authoritative simulation.

---

# 27. Building-Specific Analysis

Future feature.

Allow user to specify:

```text
Plot elevation
Proposed plinth height
Ground-floor elevation
Basement
Number of floors
```

Example:

```text
Ground elevation:
245.2m

Plinth:
+1.0m

Ground floor:
246.2m
```

Then compare simulated water surface elevation.

Example output:

```text
Simulated flood water surface:
247.1m

Ground floor:
246.2m

Difference:
+0.9m
```

Again:

MODEL RESULT — NOT GUARANTEE.

---

# 28. Map UI

The main map should support layers:

```text
☑ Analysis location
☑ Terrain
☑ Rivers
☑ Streams
☑ Lakes
☑ Reservoirs
☑ Dams
☑ Watershed
☑ Historical floods
☐ Flow direction
☐ Flow accumulation
☐ Simulated inundation
```

Clicking a feature should show:

```text
Name
Type
Distance
Elevation
Source
Dataset
```

---

# 29. Risk Report

Generate a report with:

## Location

```text
Latitude
Longitude
Elevation
```

## Terrain

```text
Slope
Aspect
Relief
Drainage direction
```

## Hydrology

```text
Nearest river
Nearest reservoir
Nearest dam
Watershed
Catchment
```

## Historical Flooding

```text
Historical flood exposure
Available datasets
Observed inundation
```

## Potential Sources

```text
Upstream rivers
Reservoirs
Dams
```

## Risk

```text
Flood exposure
Confidence
Primary contributing factors
```

## Limitations

Always include limitations.

---

# 30. API Design

Example endpoints:

```text
GET /health

POST /api/analyze

GET /api/location/{id}

GET /api/location/{id}/terrain

GET /api/location/{id}/hydrology

GET /api/location/{id}/watershed

GET /api/location/{id}/flood-risk

GET /api/location/{id}/historical-floods

GET /api/location/{id}/dams

POST /api/scenarios

GET /api/scenarios/{id}

GET /api/scenarios/{id}/results
```

---

# 31. Analysis Response

Example:

```json
{
  "location": {
    "latitude": 30.000,
    "longitude": 75.000
  },
  "terrain": {
    "elevation_m": 245.3,
    "slope_deg": 1.8,
    "aspect_deg": 132
  },
  "hydrology": {
    "nearest_river_km": 8.7,
    "nearest_reservoir_km": 21.3,
    "nearest_dam_km": 52.1
  },
  "watershed": {
    "basin": "...",
    "sub_basin": "...",
    "watershed": "..."
  },
  "risk": {
    "flood_exposure_score": 61,
    "category": "moderate",
    "confidence": "medium"
  }
}
```

---

# 32. Data Provenance

This is mandatory.

Every external dataset must have metadata.

Never silently mix datasets.

Example:

```json
{
  "source": "NRSC/Bhuvan",
  "dataset": "Flood Hazard",
  "resolution": "...",
  "retrieved_at": "...",
  "license": "...",
  "version": "..."
}
```

The frontend should expose a "Data Sources" section.

---

# 33. Caching

Geospatial data can be large.

Implement caching.

Cache:

```text
DEM tiles
river datasets
water bodies
dam datasets
historical flood layers
geocoding
API responses
```

Do not repeatedly download the same dataset.

---

# 34. Local-First Requirement

The developer must be able to run:

```bash
git clone ...
cd location-hazard-engine
```

then install dependencies and run locally.

Do not require:

- Vercel
- Neon
- Railway
- Render
- cloud Kubernetes
- paid infrastructure

for V0.1.

External APIs may require API keys, but the architecture should support local datasets wherever possible.

---

# 35. Environment Variables

Create:

```text
.env.example
```

Potential values:

```text
GOOGLE_MAPS_API_KEY=
ELEVATION_PROVIDER=
DATABASE_URL=
DEM_DATA_PATH=
HYDROLOGY_DATA_PATH=
FLOOD_DATA_PATH=
```

Never commit secrets.

---

# 36. Testing

Tests are mandatory.

Test:

### Coordinates

Valid/invalid latitude/longitude.

### Distance

Known coordinates.

### Projection

Correct CRS conversion.

### Elevation

Known DEM fixture.

### River distance

Known geometry fixture.

### Watershed

Known test polygon.

### Flow direction

Small synthetic DEM.

### Risk scoring

Known inputs produce deterministic outputs.

---

# 37. Synthetic Test Dataset

Create a tiny synthetic terrain:

```text
100 100 100 100 100
 90  90  90  90 100
 80  80  80  80 100
 70  70  70  70 100
 60  60  60  60 100
```

Use this to test whether flow generally moves downhill.

Do not rely exclusively on real-world APIs for tests.

---

# 38. Engineering Rules

### Rule 1

Never hardcode geographic conclusions.

### Rule 2

Never fabricate missing elevation.

### Rule 3

Never fabricate river geometry.

### Rule 4

Never claim a dam is hydraulically connected merely because it is geographically close.

### Rule 5

Never call an exposure score a probability of disaster.

### Rule 6

Never present hypothetical dam-break results as predictions of an actual future event.

### Rule 7

Every result must identify its data/model source.

### Rule 8

Keep raw data separate from processed data.

### Rule 9

Keep analysis algorithms deterministic where possible.

### Rule 10

Make providers replaceable.

---

# 39. LLM Integration

An LLM may eventually be used to explain results.

For example:

```text
"The analysis indicates moderate flood exposure primarily because
the location lies within the same downstream drainage system as
the identified river network and has relatively low local relief."
```

But the LLM must receive structured calculated data.

It must NOT calculate:

- elevation
- flood depth
- velocity
- probability
- arrival time

from its own reasoning.

Those values must originate from geospatial/hydraulic calculations.

---

# 40. V0.1 Definition of Done

V0.1 is complete when:

### Input

User enters:

```text
latitude
longitude
radius
```

### System

Successfully:

1. validates coordinates
2. obtains terrain/DEM
3. calculates point elevation
4. calculates slope
5. calculates aspect
6. finds nearby rivers
7. finds nearby water bodies
8. finds nearby dams/reservoirs
9. identifies watershed where data exists
10. calculates basic drainage characteristics
11. checks historical flood datasets where available
12. generates a transparent preliminary flood-exposure score
13. reports confidence
14. displays everything on an interactive map
15. displays data sources
16. works locally
17. has automated tests

---

# 41. V0.1 MUST NOT CLAIM

The following are explicitly OUT OF SCOPE for V0.1:

```text
Exact dam-break water depth
Exact dam-break velocity
Exact dam-break arrival time
Exact flood probability
Exact future disaster prediction
Emergency evacuation instructions
```

Those require substantially more physical modelling and validation.

---

# 42. V0.2

After V0.1 works:

Add:

```text
hydrological graph
upstream/downstream tracing
reservoir relationships
better catchment analysis
river elevation profiles
historical flood frequency
rainfall datasets
```

---

# 43. V0.3

Add real hydraulic modelling.

Investigate:

```text
HEC-RAS
LISFLOOD-FP
TELEMAC
Iber
```

Select based on:

- licensing
- automation support
- Python integration
- 1D/2D capability
- DEM support
- computational requirements

Do not implement a home-grown hydraulic solver unless there is a compelling scientific reason.

---

# 44. V0.4

Implement:

```text
dam breach scenarios
```

Example:

```text
Bhakra Dam
     ↓
Scenario configuration
     ↓
Reservoir conditions
     ↓
Breach parameters
     ↓
Hydraulic simulation
     ↓
Inundation raster
     ↓
Depth
Velocity
Arrival time
Duration
```

Support multiple scenarios and uncertainty ranges.

---

# 45. V0.5

Add:

```text
extreme rainfall
flash flooding
landslide susceptibility
erosion
earthquake exposure
storm hazards
```

Each hazard must have its own scientifically appropriate model/data source.

Do NOT create one arbitrary "natural disaster score" by simply adding unrelated numbers together.

---

# 46. Future House-Planning Mode

Eventually the application should allow the user to upload/enter a house plan.

Inputs:

```text
plot boundary
house footprint
plinth height
basement
ground-floor level
```

Then overlay:

```text
terrain
flood extent
water depth
flow velocity
```

The final output could answer:

```text
How high should the finished floor level be
relative to the modelled flood surface?
```

This should be presented as engineering decision-support and should recommend professional validation.

---

# 47. First Implementation Task

DO NOT immediately implement everything in this document.

Start with:

## STEP 1

Create the repository structure.

## STEP 2

Create FastAPI backend.

## STEP 3

Create Next.js frontend.

## STEP 4

Create coordinate input UI.

## STEP 5

Create `/api/analyze`.

## STEP 6

Implement a DEM/elevation provider abstraction.

## STEP 7

Use a small real or sample DEM dataset.

## STEP 8

Calculate:

```text
elevation
slope
aspect
```

## STEP 9

Add OpenStreetMap-compatible hydrological data.

## STEP 10

Find nearby:

```text
rivers
streams
lakes
reservoirs
dams
```

## STEP 11

Display them on the map.

## STEP 12

Add basic watershed/flow-direction analysis.

## STEP 13

Add historical flood data where accessible.

## STEP 14

Create transparent flood-exposure scoring.

## STEP 15

Write tests.

Only after this works should hydraulic simulation begin.

---

# 48. Developer Instruction

Before writing substantial code:

1. Inspect the repository.
2. Identify what already exists.
3. Do not overwrite existing working code unnecessarily.
4. Create a `docs/DATA_SOURCES.md`.
5. Document every external data provider.
6. Prefer open/free datasets for the prototype.
7. Keep external providers behind interfaces.
8. Build V0.1 first.
9. Run tests.
10. Run the application locally.
11. Verify the map and analysis workflow end-to-end.
12. Report what works and what remains.

When a dataset/API is unavailable, DO NOT fabricate data.

Use a clearly marked mock/sample provider so development can continue.

---

# 49. Success Criteria

The first successful demo should look like this:

```text
                 LOCATION HAZARD INTELLIGENCE

Latitude       [ 30.xxxxx ]
Longitude      [ 75.xxxxx ]
Radius         [ 50 km ]

                 [ ANALYZE ]

------------------------------------------------

                    MAP

        Rivers / terrain / dams / watershed

                         ●
                       PLOT

------------------------------------------------

TERRAIN

Elevation                  245.3 m
Slope                        1.8°
Aspect                     132°

HYDROLOGY

Nearest river                8.7 km
Nearest reservoir            XX km
Nearest dam                  XX km

WATERSHED

Basin                        XXXXX
Sub-basin                    XXXXX

HISTORICAL FLOOD EXPOSURE

Available data               YES
Observed exposure            XXXXX

PRELIMINARY FLOOD EXPOSURE

                    MODERATE

Confidence                   MEDIUM

Main factors:
• relative terrain elevation
• drainage connectivity
• historical flood exposure
• proximity to river system

------------------------------------------------

IMPORTANT

This is a preliminary geospatial assessment.
It is not a hydraulic dam-break simulation or
an emergency warning system.
```

---

# 50. Final Principle

The ultimate objective is not to create a pretty map.

The objective is to build a **geospatial reasoning engine backed by real physical data**.

The architecture should eventually allow:

```text
LOCATION
   ↓
TERRAIN
   ↓
HYDROLOGY
   ↓
WATER INFRASTRUCTURE
   ↓
CATCHMENT
   ↓
SCENARIO
   ↓
PHYSICAL MODEL
   ↓
SIMULATION
   ↓
INUNDATION
   ↓
DEPTH + VELOCITY + ARRIVAL TIME
   ↓
PROPERTY IMPACT
   ↓
EXPLAINABLE REPORT
```

Build the foundation correctly now so that adding the actual dam-break simulation later does not require rewriting the entire application.
# V0.1 Spec Notes

This is the local copy / implementation mapping of the full
`Location Hazard Intelligence Engine.md` specification.
For the canonical spec see that file.

## What is implemented (V0.1)

- [x] Project structure (`apps/api`, `apps/web`, `packages/geo`, etc.)
- [x] FastAPI backend with `/api/health` and `/api/analyze`
- [x] Pydantic request validation (`-90..90`, `-180..180`, `0 < r ≤ 200`)
- [x] Coordinate utilities: Haversine distance, bbox construction
- [x] DEM provider abstraction (`sample`, `stub`)
- [x] Sample DEM synthesis (Punjab, deterministic, labelled synthetic)
- [x] Terrain analysis: point elevation, min/max/mean, relief, slope, aspect
- [x] Hydrology provider abstraction (`osm` Overpass, `stub`)
- [x] OpenStreetMap Overpass fetch for rivers/streams/canals/lakes/reservoirs/ponds/wetlands/drains/dams/weirs
- [x] Nearest-feature lookup (river / reservoir / dam) with DEM-sampled elevation
- [x] D8 flow direction + flow accumulation + downhill trace
- [x] Watershed metadata: trace length, direction, accumulation at plot
- [x] Transparent weighted flood-exposure score (5 factors, weights sum to 1.0)
- [x] Confidence level (low / medium / high) derived from data availability
- [x] Limitations list embedded in every response
- [x] Next.js + MapLibre GL JS frontend with coordinate input + sidebar report + interactive map
- [x] Synthetic DEM fixture (per spec §37) for tests
- [x] Unit + integration tests (31 tests, all passing)

## What is NOT implemented (out of V0.1 scope)

- [ ] Real hydraulic simulation (HEC-RAS, LISFLOOD, TELEMAC)
- [ ] Exact dam-break depth / velocity / arrival time
- [ ] Probability of disaster
- [ ] Reservoir volume, breach parameters, dam geometry
- [ ] Historical-flood raster overlays (NRSC/Bhuvan — planned V0.2)
- [ ] Watershed polygon generation (V0.2)
- [ ] Upstream/downstream graph analysis (V0.2)
- [ ] Rainfall, landslide, earthquake, storm (V0.5)
- [ ] Building/plinth analysis (future)
- [ ] LLM-generated explanations (only the LLM layer is intentionally absent;
      the structured report is the V0.1 deliverable)

## API contracts

### `POST /api/analyze`

```json
{
  "latitude": 30.7,
  "longitude": 76.0,
  "radius_km": 50,
  "historical_flood_count": 0,
  "historical_flood_source": "none"
}
```

Response shape mirrors the spec §31 (`AnalysisReport`).

### `GET /api/health`

```json
{"status":"ok","version":"0.1.0"}
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd apps/web && npm install && npm run dev
```

Open http://localhost:3000.
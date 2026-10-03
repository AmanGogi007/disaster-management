"""HTTP routes — V0.3 evidence-first architecture.

Wraps the existing `packages/geo/hydraulic/` backend and exposes a clean API
for the frontend.  Every response carries evidence states, never fabricated
flood-depth numbers.  The solver is only accessible when the evidence gates
permit it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory assessment store (MVP; replace with DB later)
# ---------------------------------------------------------------------------
_store: dict[str, dict[str, Any]] = {}

# Cache the most recent plot-evidence gather per (lat, lon, radius) so
# read-only derivation endpoints (e.g. acquisition-spec) reuse live results
# instead of re-triggering slow external gathers.
_gather_cache: dict[tuple, Any] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Helpers — bridge to the existing backend
# ---------------------------------------------------------------------------
def _build_contract_from_evidence(evidence_rows: list[dict]) -> Any:
    """Reconstruct an EvidenceContract from stored evidence rows."""
    from packages.geo.hydraulic.evidence import (
        EvidenceContract, EvidenceCategory, EvidenceRow, EvidenceStatus,
    )
    contract = EvidenceContract(plot_lat=0, plot_lon=0)
    for row in evidence_rows:
        try:
            cat = EvidenceCategory(row["category"])
            status = EvidenceStatus(row["status"])
            contract.rows.append(EvidenceRow(
                category=cat, status=status,
                source=row.get("source"), reference=row.get("reference"),
                note=row.get("note", ""), confidence=row.get("confidence", "medium"),
            ))
        except Exception:
            continue
    return contract


def _run_evidence_gather(lat: float, lon: float, radius_km: float) -> list[dict]:
    """Run the full evidence gather pipeline and return evidence rows."""
    rows: list[dict] = []

    # 1. OSM evidence (channel, drains, barriers, bridges)
    try:
        from packages.geo.hydraulic import gather_plot_evidence
        gather = gather_plot_evidence(lat, lon, radius_km=radius_km)
        _gather_cache[(round(lat, 6), round(lon, 6), round(radius_km, 3))] = gather
        for rec in gather.records:
            status = "available" if rec.status == "obtained" else "missing"
            samples = list(rec.sample or [])[:20]
            rows.append({
                "category": rec.category.value,
                "status": status,
                "source": "OpenStreetMap (Overpass)",
                "reference": f"{rec.count} features",
                "note": rec.note or f"OSM evidence: {rec.status}",
                "confidence": "high" if status == "available" else "low",
                "count": rec.count,
                "features": samples,
            })
    except Exception as exc:
        rows.append({
            "category": "channel_centerline",
            "status": "missing",
            "source": "OpenStreetMap",
            "reference": "-",
            "note": f"OSM fetch failed: {exc}",
            "confidence": "low",
        })

    # 2. Terrain evidence
    try:
        from packages.geo.hydraulic import gather_terrain_evidence
        from packages.geo.terrain.providers.copernicus import CopernicusGLO30Provider
        provider = CopernicusGLO30Provider()
        res = provider.get_dem_bbox(lat - 0.5, lon - 0.5, lat + 0.5, lon + 0.5)
        if res.dem is not None:
            terrain = gather_terrain_evidence(res.dem, None, plot_lat=lat, plot_lon=lon,
                                             radius_km=radius_km)
            rows.append({
                "category": "terrain_elevation",
                "status": "available",
                "source": "Copernicus DEM GLO-30",
                "reference": res.dataset or "GLO-30",
                "note": f"Plot elevation {terrain.plot.get('dem_elevation_m', 'n/a')} m; "
                        f"resolution ~{res.resolution_m or 30} m; datum {res.dem.vertical_datum}",
                "confidence": "high",
                "plot_elevation_m": terrain.plot.get("dem_elevation_m"),
                "slope_deg": terrain.plot.get("slope_deg"),
                "aspect_deg": terrain.plot.get("aspect_deg"),
                "neighborhood": terrain.neighborhood,
                "low_points_count": len(terrain.low_points),
                "transect": terrain.transect.to_dict() if terrain.transect else None,
            })
        else:
            rows.append({
                "category": "terrain_elevation",
                "status": "missing",
                "source": "Copernicus DEM GLO-30",
                "reference": "-",
                "note": "DEM fetch failed",
                "confidence": "low",
            })
    except Exception as exc:
        rows.append({
            "category": "terrain_elevation",
            "status": "missing",
            "source": "Copernicus DEM GLO-30",
            "reference": "-",
            "note": f"Terrain gather failed: {exc}",
            "confidence": "low",
        })

    # 3. Flood evidence
    try:
        from packages.geo.hydraulic import gather_flood_evidence
        flood = gather_flood_evidence(lat, lon, radius_km=radius_km)
        for rec in flood.records:
            status = "available" if rec.status == "obtained" else "missing"
            rows.append({
                "category": rec.kind.value,
                "status": status,
                "source": rec.source_org or "authoritative",
                "reference": rec.dataset or "-",
                "note": rec.note or rec.title or "",
                "confidence": "high" if status == "available" else "low",
                "count": rec.count,
            })
    except Exception as exc:
        rows.append({
            "category": "documented_flood_extents",
            "status": "missing",
            "source": "authoritative",
            "reference": "-",
            "note": f"Flood evidence fetch failed: {exc}",
            "confidence": "low",
        })

    # 4. Connectivity (always unresolved until verified data)
    from packages.geo.hydraulic.connectivity import UNRESOLVED_MESSAGE
    rows.append({
        "category": "connectivity",
        "status": "unresolved",
        "source": "assess_connectivity",
        "reference": "UNRESOLVED at 30 m DEM",
        "note": UNRESOLVED_MESSAGE,
        "confidence": "low",
    })

    # Guarantee exactly one row per SDG-required category.  gather_plot_evidence
    # already emits local_survey + high_res_dem; drop any stray duplicates so the
    # evidence inventory has a single authoritative row per category.
    seen = set()
    deduped: list[dict] = []
    for row in rows:
        cat = row["category"]
        if cat in seen and cat in ("local_survey", "high_res_dem"):
            continue
        seen.add(cat)
        deduped.append(row)
    return deduped


def _compute_evidence_summary(evidence_rows: list[dict]) -> dict:
    """Compute a summary of evidence states for the dashboard."""
    categories = {}
    for row in evidence_rows:
        cat = row["category"]
        categories[cat] = {
            "status": row["status"],
            "source": row.get("source", ""),
            "confidence": row.get("confidence", "low"),
        }

    # Overall status
    statuses = [r["status"] for r in evidence_rows]
    if all(s == "available" for s in statuses if s not in ("not_applicable",)):
        overall = "complete"
    elif any(s == "missing" for s in statuses):
        overall = "incomplete"
    else:
        overall = "partial"

    # Plot-level credibility
    high_res = categories.get("high_res_dem", {}).get("status") == "available"
    survey = categories.get("local_survey", {}).get("status") == "available"
    plot_level_credible = high_res and survey

    # Connectivity
    connectivity = categories.get("connectivity", {}).get("status", "unresolved")

    # Solver readiness
    solver_ready = plot_level_credible and connectivity in ("connected",)

    return {
        "categories": categories,
        "overall": overall,
        "plot_level_credible": plot_level_credible,
        "connectivity": connectivity,
        "solver_ready": solver_ready,
        "missing_plot_level": [
            c for c in ("high_res_dem", "local_survey")
            if categories.get(c, {}).get("status") != "available"
        ],
    }


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.post("/assessments")
def create_assessment(
    latitude: float = Form(...),
    longitude: float = Form(...),
    radius_km: float = Form(3.0),
    input_type: str = Form("coordinates"),
    place_name: str = Form(""),
) -> dict:
    """Create a new assessment for a location.  Does NOT run analysis — only
    registers the location and returns an assessment ID."""
    aid = _aid()
    _store[aid] = {
        "id": aid,
        "created_at": _now(),
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "input_type": input_type,
        "place_name": place_name,
        "status": "created",
        "evidence_rows": [],
        "evidence_summary": None,
        "connectivity": {"status": "unresolved", "reason": "not yet assessed"},
        "solver": {"status": "blocked", "reason": "evidence gates not satisfied"},
    }
    return {"assessment_id": aid, "location": {"lat": latitude, "lon": longitude}}


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str) -> dict:
    """Get assessment status + evidence summary for the dashboard."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")
    return {
        "id": a["id"],
        "created_at": a["created_at"],
        "location": {"lat": a["latitude"], "lon": a["longitude"],
                     "radius_km": a["radius_km"], "place_name": a["place_name"]},
        "status": a["status"],
        "evidence_summary": a["evidence_summary"],
        "connectivity": a["connectivity"],
        "solver": a["solver"],
    }


@router.get("/assessments/{assessment_id}/evidence")
def get_evidence(assessment_id: str) -> dict:
    """Full evidence inventory — the heart of the evidence panel."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")
    return {
        "id": a["id"],
        "location": {"lat": a["latitude"], "lon": a["longitude"]},
        "evidence_rows": a["evidence_rows"],
        "evidence_summary": a["evidence_summary"],
    }


@router.get("/assessments/{assessment_id}/map-layers")
def get_map_layers(assessment_id: str) -> dict:
    """Map layer data for the frontend — plot marker, radius, and vector
    evidence (Sutlej channel, local drains, embankments/roads/rail, bridges and
    culverts) reconstructed from the OSM way geometry.  Emits real polylines
    where available and falls back to point markers otherwise."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")

    lat, lon = a["latitude"], a["longitude"]
    radius_km = a.get("radius_km", 3.0)

    layers: list[dict] = []

    layers.append({
        "id": "plot",
        "type": "point",
        "label": "Plot location",
        "visible": True,
        "coordinates": [lon, lat],
        "properties": {"radius_km": radius_km},
    })

    layers.append({
        "id": "radius",
        "type": "circle",
        "label": "Search radius",
        "visible": True,
        "center": [lon, lat],
        "radius_km": radius_km,
    })

    # category -> visual grouping for the map legend
    group = {
        "channel_centerline": "waterways",
        "channels_drains": "waterways",
        "embankments_road_rail": "barriers",
        "bridges_culverts": "crossings",
        "flood_control": "flood_control",
    }

    for row in a["evidence_rows"]:
        cat = row["category"]
        if cat not in group:
            continue
        for feat in (row.get("features") or [])[:60]:
            points = feat.get("points") or []
            coords = [[round(p[1], 6), round(p[0], 6)] for p in points if len(p) >= 2]
            if len(coords) >= 2:
                layers.append({
                    "id": f"{cat}_{feat.get('osm_id', 'x')}",
                    "type": "line",
                    "label": feat.get("name") or cat,
                    "group": group[cat],
                    "visible": True,
                    "coordinates": coords,
                    "name": feat.get("name"),
                    "tags": feat.get("tags", {}),
                    "length_km": feat.get("length_km"),
                    "osm_id": feat.get("osm_id"),
                })
            elif feat.get("mid"):
                layers.append({
                    "id": f"{cat}_{feat.get('osm_id', 'x')}",
                    "type": "point",
                    "label": feat.get("name") or cat,
                    "group": group[cat],
                    "visible": True,
                    "coordinates": [round(feat["mid"][1], 6), round(feat["mid"][0], 6)],
                    "name": feat.get("name"),
                    "tags": feat.get("tags", {}),
                })

    return {"id": a["id"], "layers": layers}


@router.get("/assessments/{assessment_id}/acquisition-spec")
def get_acquisition_spec(assessment_id: str) -> dict:
    """Field survey spec + high-res DEM source matrix for this plot.

    Produces requirements, never measurements: the spec tells the user WHAT to
    collect (survey points) and WHERE to get finer elevation, but integrates
    nothing.  Plot-level credibility stays False until verified survey/DEM is
    actually delivered via /survey-points."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")

    from packages.geo.hydraulic.survey_spec import produce_survey_spec

    # Reuse a prior live gather if available (fast); only gather live as a
    # fallback when no evidence has been collected for this location yet.
    gather = _gather_cache.get(
        (round(a["latitude"], 6), round(a["longitude"], 6),
         round(a["radius_km"], 3)))
    if gather is None:
        try:
            from packages.geo.hydraulic import gather_plot_evidence
            gather = gather_plot_evidence(a["latitude"], a["longitude"],
                                          radius_km=a["radius_km"])
        except Exception:
            gather = None

    spec = produce_survey_spec(
        gather=gather,
        plot_lat=a["latitude"],
        plot_lon=a["longitude"],
    )
    return {"id": a["id"], "spec": spec.to_dict()}


@router.post("/assessments/{assessment_id}/survey-points")
def submit_survey_points(assessment_id: str, payload: dict) -> dict:
    """Accept verified field-survey points for the plot.

    Hard rule: only points that carry verified provenance/datum/accuracy are
    integrated (via ``record_survey_points``).  A bare file upload or
    unverified claims are REFUSED, and never upgrade LOCAL_SURVEY to available.
    Integrity of the 'no fabricated evidence' discipline is preserved."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")

    from packages.geo.hydraulic.survey_spec import (
        SurveyPointSubmission, record_survey_points,
    )

    points = []
    for p in payload.get("points", []):
        try:
            points.append(SurveyPointSubmission(
                category=p.get("category", "flood_elevation"),
                target=p.get("target", ""),
                value_m=p.get("value_m"),
                provenance=p.get("provenance", ""),
                vertical_datum=p.get("vertical_datum", "EGM2008"),
                horizontal_system=p.get("horizontal_system", "WGS84"),
                accuracy_m=p.get("accuracy_m"),
                verified=bool(p.get("verified", False)),
                source_osm_id=p.get("source_osm_id"),
            ))
        except Exception:
            continue

    conn_status = a.get("connectivity", {}).get("status", "unresolved")
    result = record_survey_points(points, connectivity_status=conn_status)

    # If any verified, integrable points were accepted, promote LOCAL_SURVEY to
    # available (real, delivered, provenance-carrying evidence) and recompute.
    if result.accepted:
        for row in a.get("evidence_rows", []):
            if row["category"] == "local_survey":
                row["status"] = "available"
                row["source"] = "field survey (verified)"
                row["reference"] = f"{len(result.accepted)} points"
                row["confidence"] = "medium"
        a["evidence_summary"] = _compute_evidence_summary(a["evidence_rows"])
        a["status"] = "evidence_complete"

    return {
        "id": a["id"],
        "accepted": result.accepted,
        "refused": result.refused,
        "connectivity": a.get("connectivity"),
        "evidence_summary": a.get("evidence_summary"),
    }


@router.post("/assessments/{assessment_id}/gather")
def run_gather(assessment_id: str) -> dict:
    """Run the full evidence gather pipeline for this assessment."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")

    a["status"] = "gathering"
    a["evidence_rows"] = _run_evidence_gather(
        a["latitude"], a["longitude"], a["radius_km"])
    a["evidence_summary"] = _compute_evidence_summary(a["evidence_rows"])

    # Update connectivity from evidence
    conn_row = next((r for r in a["evidence_rows"] if r["category"] == "connectivity"), None)
    if conn_row:
        a["connectivity"] = {"status": conn_row["status"], "reason": conn_row["note"]}

    # Update solver status
    if a["evidence_summary"]["solver_ready"]:
        a["solver"] = {"status": "ready", "reason": "all evidence gates satisfied"}
    else:
        missing = a["evidence_summary"]["missing_plot_level"]
        a["solver"] = {
            "status": "blocked",
            "reason": f"Missing plot-level evidence: {', '.join(missing)}",
        }

    a["status"] = "evidence_complete"
    return {"status": "ok", "assessment_id": a["id"],
            "evidence_summary": a["evidence_summary"]}


@router.post("/assessments/{assessment_id}/reassess")
def reassess(assessment_id: str) -> dict:
    """Re-assess connectivity after new evidence is integrated.  Only runs
    when fine-scale data (high-res DEM or verified survey) is available."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")

    # Rebuild contract from stored evidence
    contract = _build_contract_from_evidence(a["evidence_rows"])

    # Check if fine-scale evidence exists
    from packages.geo.hydraulic.evidence import EvidenceCategory, EvidenceStatus
    dem_ok = (contract.row(EvidenceCategory.HIGH_RES_DEM) is not None
              and contract.row(EvidenceCategory.HIGH_RES_DEM).status == EvidenceStatus.AVAILABLE)
    survey_ok = (contract.row(EvidenceCategory.LOCAL_SURVEY) is not None
                 and contract.row(EvidenceCategory.LOCAL_SURVEY).status == EvidenceStatus.AVAILABLE)

    if not (dem_ok or survey_ok):
        return {
            "status": "refused",
            "reason": "No verified fine-scale data (HIGH_RES_DEM or LOCAL_SURVEY) integrated.",
            "connectivity": a["connectivity"],
            "solver": a["solver"],
        }

    # Run connectivity re-assessment
    from packages.geo.hydraulic.acquire import reassess_connectivity_after_acquisition
    reassess = reassess_connectivity_after_acquisition(
        contract, dem=None, proc=None,
        plot_lat=a["latitude"], plot_lon=a["longitude"])

    a["connectivity"] = {
        "status": reassess.connectivity_status,
        "reason": reassess.reason,
    }

    # Update solver
    if reassess.connectivity_status == "connected" and a["evidence_summary"]["plot_level_credible"]:
        a["solver"] = {"status": "ready", "reason": "connectivity resolved + plot-level credible"}
    else:
        a["solver"] = {"status": "blocked",
                       "reason": f"connectivity={reassess.connectivity_status}, "
                                 f"credible={a['evidence_summary']['plot_level_credible']}"}

    return {"status": "ok", "connectivity": a["connectivity"], "solver": a["solver"]}


@router.post("/assessments/{assessment_id}/solver")
def run_solver(assessment_id: str) -> dict:
    """Run the hydraulic solver — ONLY when the evidence gates permit it.

    This is currently a placeholder.  The solver will be implemented in
    a later phase.  For now, it returns the gate status."""
    a = _store.get(assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown assessment_id")

    if a["solver"]["status"] != "ready":
        raise HTTPException(
            status_code=403,
            detail=f"Solver blocked: {a['solver']['reason']}. "
                   "Integrate verified survey + sub-30 m DEM + resolve connectivity first.")

    return {
        "status": "not_implemented",
        "reason": "Solver not yet implemented.  Awaiting verified fine-scale evidence "
                  "integration + connectivity resolution.",
        "connectivity": a["connectivity"],
        "solver": a["solver"],
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.3.0", "architecture": "evidence-first"}

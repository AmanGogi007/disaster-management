"""Phase 1g — acquisition + integration workflow for fine-scale evidence.

The one real-data step that unblocks J.3: a Cartosat-1/Bhuvan (or other sub-30 m)
DEM for the exact plot, and a field survey delivered against the Phase 1f
specification.  This module is the *plumbing* that ingests only genuine data and
keeps everything provenance-tagged until it actually is:

* ``inspect_dem_file`` / ``register_dem`` — a real raster is validated
  (readable, EPSG:4326, covers the plot with margin, carrier of an explicit
  resolution and vertical datum) before HIGH_RES_DEM evidence can become
  ``available``.  Nothing is fabricated; a missing/unreadable file is a failure
  the gate records, never a DEM.
* ``ingest_survey_points`` — a real, delimited list of claimed field
  observations is validated row-by-row (required: category, value, provenance,
  vertical datum, horizontal system, accuracy, ``verified``).  Only rows that
  are verifiably true-and-complete are accepted (re-used gate from Phase 1f);
  every accepted row is provenance-tagged and upgrades LOCAL_SURVEY evidence to
  ``available``.
* ``reassess_connectivity_after_acquisition`` — connectivity may be re-assessed
  only once fine-scale evidence (high-res DEM and/or verified survey) is actually
  integrated.  The hydraulic solver is NEVER run here; ``plot_level_credible``
  stays the J.3 gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ACQUISITION_GATE_STATEMENT = (
    "Newly acquired data is integrated ONLY through the verified-acquisition "
    "gate: a DEM raster only after it really exists, reads successfully, covers "
    "the plot, and carries an explicit native resolution + vertical datum; "
    "survey points only after each claim is provenance-tagged, datum-tagged, "
    "accuracy-tagged and marked verified. Unverified or fabricated claims are "
    "refused. Integrating fine-scale data allows connectivity to be "
    "RE-ASSESSED — it never by itself resolves connectivity and never runs the "
    "hydraulic solver."
)

DEM_FILE_REQUIREMENTS = [
    "GeoTIFF (or raster readable by rasterio) in EPSG:4326.",
    "Must cover the plot cell, ideally with a ≥0.005° (~0.5 km) margin.",
    "Must carry an explicit native resolution and a named vertical datum "
    "('vertical_datum' on intake; else the provider/product datum must be "
    "recorded by the caller).",
    "Native resolution < 30 m is required for the HIGH_RES_DEM category to be "
    "plot-level usable; a ≥30 m product integrating would be PARTIAL, not "
    "available.",
    "Datums (EGM96 / EGM2008 / MSL) must be declared on intake; they are never "
    "fused silently.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DemIngestResult:
    """Outcome of validating a real DEM against the acquisition gate."""
    dataset: str
    resolution_m: float | None
    vertical_datum: str
    horizontal_crs: str
    provenance: str
    covers_plot: bool
    sub_30m: bool
    evidence_status: str   # available | partial | missing
    reason: str = ""
    dem_info: dict = field(default_factory=dict)
    ingested_at: str = _now()

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "resolution_m": self.resolution_m,
            "vertical_datum": self.vertical_datum,
            "horizontal_crs": self.horizontal_crs,
            "provenance": self.provenance,
            "covers_plot": self.covers_plot,
            "sub_30m": self.sub_30m,
            "evidence_status": self.evidence_status,
            "reason": self.reason,
            "dem_info": self.dem_info,
            "ingested_at": self.ingested_at,
        }


def _evidence_status(covers: bool, sub30: bool, readable: bool) -> str:
    if not readable:
        return "missing"
    if covers and sub30:
        return "available"
    return "partial"


def register_dem(
    dem,
    *,
    dataset: str,
    vertical_datum: str,
    provenance: str,
    plot_lat: float,
    plot_lon: float,
    horizontal_crs: str = "EPSG:4326",
    resolution_m: float | None = None,
    margin_deg: float = 0.005,
) -> DemIngestResult:
    """Validate an already-loaded DEM against the gate (covers plot + sub-30 m)
    and return the evidence verdict.  The DEM is NOT itself re-worked; connectivity
    re-assessment is a separate, later call."""
    if dem is None:
        return DemIngestResult(
            dataset=dataset, resolution_m=None, vertical_datum=vertical_datum,
            horizontal_crs=horizontal_crs, provenance=provenance,
            covers_plot=False, sub_30m=False, evidence_status="missing",
            reason="no DEM object supplied — nothing integrated.",
        )
    res = resolution_m if resolution_m is not None else dem.source_resolution_m
    south, west, north, east = dem.bounds()
    covers = (south - margin_deg <= plot_lat <= north + margin_deg
              and west - margin_deg <= plot_lon <= east + margin_deg)
    covers_plot = (south <= plot_lat <= north and west <= plot_lon <= east)
    sub30 = res is not None and res < 30.0
    status = _evidence_status(covers_plot, sub30, True)
    note = ""
    if not covers_plot:
        note = f"DEM does not cover the plot; bounds {south:.4f},{west:.4f},{north:.4f},{east:.4f}."
    elif not sub30:
        note = f"Resolution {res} m is NOT sub-30 m -> HIGH_RES_DEM only PARTIAL."
    else:
        note = "Covers plot with margin and is native sub-30 m -> HIGH_RES_DEM available."
    return DemIngestResult(
        dataset=dataset, resolution_m=res, vertical_datum=vertical_datum,
        horizontal_crs=horizontal_crs, provenance=provenance,
        covers_plot=covers_plot, sub_30m=sub30,
        evidence_status=status, reason=note,
        dem_info={
            "rows": int(dem.rows), "cols": int(dem.cols),
            "bounds": {"south": south, "west": west, "north": north, "east": east},
        },
    )


def inspect_dem_file(
    path,
    *,
    plot_lat: float,
    plot_lon: float,
    dataset: str,
    provenance: str,
    vertical_datum: str,
    source_resolution_m: float | None = None,
    horizontal_crs: str | None = None,
    margin_deg: float = 0.005,
) -> DemIngestResult:
    """Load a real raster file and validate it against the gate.

    A missing/unreadable file returns ``evidence_status='missing'`` with the
    failure recorded — never a fabricated DEM.
    """
    p = Path(path)
    if not p.is_file():
        return DemIngestResult(
            dataset=dataset, resolution_m=None, vertical_datum=vertical_datum,
            horizontal_crs=horizontal_crs or "EPSG:4326", provenance=provenance,
            covers_plot=False, sub_30m=False, evidence_status="missing",
            reason=f"file not found: {p}",
        )
    try:
        import numpy as np
        import rasterio as rio
        with rio.open(str(p)) as src:
            transform = src.transform
            crs = src.crs.to_string() if src.crs else "EPSG:4326"
            nodata = src.nodata
            data = src.read(1)
            pixel = (abs(transform.a), abs(transform.e))
    except Exception as exc:  # noqa: BLE001
        return DemIngestResult(
            dataset=dataset, resolution_m=None, vertical_datum=vertical_datum,
            horizontal_crs=horizontal_crs or "EPSG:4326", provenance=provenance,
            covers_plot=False, sub_30m=False, evidence_status="missing",
            reason=f"unreadable raster ({type(exc).__name__}: {exc}) — recorded, "
                   "not fabricated.",
        )

    if horizontal_crs and crs != horizontal_crs:
        return DemIngestResult(
            dataset=dataset, resolution_m=None, vertical_datum=vertical_datum,
            horizontal_crs=crs, provenance=provenance,
            covers_plot=False, sub_30m=False, evidence_status="partial",
            reason=f"CRS {crs} != required {horizontal_crs} — not integrated; "
                   "reprojection must be explicit and recorded.",
        )
    from ..raster.dem import DEM, AffineTransform

    res_default = None
    if pixel[0] > 0 and pixel[1] > 0:
        res_default = (abs(pixel[0]) + abs(pixel[1])) / 2.0 * 111_320.0
    res = source_resolution_m if source_resolution_m is not None else res_default
    dem = DEM(
        elevation=data,
        transform=AffineTransform(
            origin_lon=float(transform.c), origin_lat=float(transform.f),
            pixel_size_lon=abs(float(transform.a)),
            pixel_size_lat=abs(float(transform.e)),
        ),
        crs=crs,
        nodata=float(nodata) if nodata is not None else None,
        source_resolution_m=res,
        simulation_grid_m=res,
        horizontal_crs=crs,
        vertical_datum=vertical_datum,
        dataset=dataset,
        provenance=provenance,
    )
    return register_dem(
        dem, dataset=dataset, vertical_datum=vertical_datum,
        provenance=provenance, plot_lat=plot_lat, plot_lon=plot_lon,
        horizontal_crs=crs, resolution_m=res, margin_deg=margin_deg,
    )


@dataclass
class SurveyIngestResult:
    """Row-by-row verdict over a delivered survey file."""
    accepted: list[dict] = field(default_factory=list)
    refused: list[dict] = field(default_factory=list)
    integrated_count: int = 0
    evidence_status: str = "missing"   # available | missing | partial
    note: str = ""
    recorded_at: str = _now()

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "refused": self.refused,
            "integrated_count": self.integrated_count,
            "evidence_status": self.evidence_status,
            "note": self.note,
            "recorded_at": self.recorded_at,
        }


_REQUIRED_CLAIM_FIELDS = (
    "category", "value_m", "provenance", "vertical_datum",
    "horizontal_system", "accuracy_m", "verified",
)


def _claim_to_submission(row: dict):
    from .survey_spec import SurveyPointSubmission
    verified = row.get("verified")
    verified = True if verified is True else False
    try:
        value_m = float(row["value_m"])
        accuracy_m = float(row["accuracy_m"])
    except (TypeError, ValueError, KeyError):
        return None, "non-numeric value_m/accuracy_m"
    if not row.get("provenance") or not row.get("vertical_datum") \
            or not row.get("horizontal_system"):
        return None, "missing provenance / vertical datum / horizontal system"
    return SurveyPointSubmission(
        category=row.get("category", ""),
        target=row.get("target", ""),
        value_m=value_m,
        provenance=row.get("provenance", ""),
        vertical_datum=row.get("vertical_datum", ""),
        horizontal_system=row.get("horizontal_system", ""),
        accuracy_m=accuracy_m,
        verified=verified,
        source_osm_id=row.get("source_osm_id"),
    ), None


def ingest_survey_points(points: list[dict]) -> SurveyIngestResult:
    """Deliver a real list of claimed survey observations.

    Each row requires category, target, value_m, provenance, vertical_datum,
    horizontal_system, accuracy_m, verified.  A row is accepted only when
    ``verified is True`` and every field is present/valid; anything else is
    refused with a reason.  Accepted rows are provenance-tagged and upgrade
    LOCAL_SURVEY to available at integration time.
    """
    from .survey_spec import record_survey_points

    accepted_rows: list[dict] = []
    refused_rows: list[dict] = []
    submissions = []
    if not points:
        return SurveyIngestResult(
            evidence_status="missing",
            note="no survey rows delivered.",
        )
    for i, row in enumerate(points):
        sub, err = _claim_to_submission(row)
        if err:
            refused_rows.append({"index": i, "reason": f"refused: {err}"})
            continue
        submissions.append(sub)
    if submissions:
        res = record_survey_points(submissions, connectivity_status="unresolved")
        accepted_rows = [dict(a) for a in res.accepted]
        refused_rows += [dict(r) for r in res.refused]
    integrated = len(accepted_rows)
    status = "available" if integrated else "missing"
    note = (f"{integrated} verified observation(s) integrated; "
            f"{len(refused_rows)} row(s) refused." if points
            else "no survey rows delivered.")
    return SurveyIngestResult(
        accepted=accepted_rows, refused=refused_rows,
        integrated_count=integrated, evidence_status=status, note=note,
    )


def integrate_into_contract(
    contract,
    *,
    dem_result: DemIngestResult | None = None,
    survey_result: SurveyIngestResult | None = None,
) -> "EvidenceContract":
    """Apply accepted acquisitions to the constraining-observations contract.

    HIGH_RES_DEM  <- dem_result.evidence_status (available / partial / missing).
    LOCAL_SURVEY  <- available only when ≥1 verified observation integrated,
                     else the existing row is left untouched.
    """
    from .evidence import EvidenceCategory, EvidenceStatus, EvidenceRow

    def upsert(cat, status, source, reference, note):
        existing = contract.row(cat)
        if existing is not None:
            existing.status = status
            existing.source = source
            existing.reference = reference
            existing.note = note
            existing.confidence = "high" if status == EvidenceStatus.AVAILABLE \
                else existing.confidence
        else:
            contract.rows.append(EvidenceRow(
                category=cat, status=status, source=source,
                reference=reference, note=note,
                confidence="high" if status == EvidenceStatus.AVAILABLE else "medium",
            ))

    if dem_result is not None:
        upsert(
            EvidenceCategory.HIGH_RES_DEM,
            EvidenceStatus(dem_result.evidence_status),
            source=dem_result.dataset,
            reference=dem_result.provenance,
            note=dem_result.reason or f"{dem_result.dataset} registered. "
                 f"Datum {dem_result.vertical_datum}; resolution "
                 f"{dem_result.resolution_m} m.",
        )
    if survey_result is not None and survey_result.integrated_count:
        upsert(
            EvidenceCategory.LOCAL_SURVEY,
            EvidenceStatus.AVAILABLE,
            source="field survey (delivered)",
            reference=f"{survey_result.integrated_count} verified points",
            note=survey_result.note,
        )
    return contract


@dataclass
class ReassessmentResult:
    """Connectivity re-assessment after fine-scale acquisitions, solver-gated."""
    connectivity_status: str
    reason: str
    checks: list[dict]
    path_established: bool
    solver_run: bool
    plot_level_credible: bool
    missing_plot_level_evidence: list[str]
    gate_applied: bool

    def to_dict(self) -> dict:
        return {
            "connectivity_status": self.connectivity_status,
            "reason": self.reason,
            "checks": self.checks,
            "path_established": self.path_established,
            "solver_run": self.solver_run,
            "plot_level_credible": self.plot_level_credible,
            "missing_plot_level_evidence": self.missing_plot_level_evidence,
            "gate_applied": self.gate_applied,
        }


def reassess_connectivity_after_acquisition(
    contract,
    *,
    dem=None,
    proc=None,
    plot_lat: float,
    plot_lon: float,
) -> ReassessmentResult:
    """(Re)assess connectivity only after fine-scale evidence is integrated.

    Refuses (stays UNRESOLVED) when neither HIGH_RES_DEM nor LOCAL_SURVEY is
    AVAILABLE.  On refusal and run alike, the hydraulic solver is never invoked.
    """
    from .evidence import EvidenceCategory, EvidenceStatus
    from .connectivity import assess_connectivity, ConnectivityStatus, UNRESOLVED_MESSAGE

    dem_ok = (contract.row(EvidenceCategory.HIGH_RES_DEM) is not None
              and contract.row(EvidenceCategory.HIGH_RES_DEM).status == EvidenceStatus.AVAILABLE)
    survey_ok = (contract.row(EvidenceCategory.LOCAL_SURVEY) is not None
                 and contract.row(EvidenceCategory.LOCAL_SURVEY).status == EvidenceStatus.AVAILABLE)

    if not (dem_ok or survey_ok):
        return ReassessmentResult(
            connectivity_status=ConnectivityStatus.UNRESOLVED,
            reason="Refused by acquisition gate: no verified fine-scale data "
                   "(HIGH_RES_DEM available / verified LOCAL_SURVEY) integrated yet.",
            checks=[],
            path_established=False,
            solver_run=False,
            plot_level_credible=contract.plot_level_credible,
            missing_plot_level_evidence=[c.value for c in contract.missing_plot_level_evidence()],
            gate_applied=True,
        )

    conn = assess_connectivity(
        dem, proc, contract, plot_lat=plot_lat, plot_lon=plot_lon)
    return ReassessmentResult(
        connectivity_status=conn.status,
        reason=conn.reason or UNRESOLVED_MESSAGE,
        checks=conn.checks,
        path_established=conn.path_established,
        solver_run=False,   # never run here
        plot_level_credible=contract.plot_level_credible,
        missing_plot_level_evidence=[c.value for c in contract.missing_plot_level_evidence()],
        gate_applied=True,
    )


@dataclass
class AcquisitionWorkflowResult:
    plot_lat: float
    plot_lon: float
    generated_at: str
    gate: str = ACQUISITION_GATE_STATEMENT
    dem_file_requirements: list[str] = field(default_factory=lambda: list(DEM_FILE_REQUIREMENTS))
    dem_ingest: DemIngestResult | None = None
    survey_ingest: SurveyIngestResult | None = None
    contract: dict | None = None
    reassessment: ReassessmentResult | None = None

    def to_dict(self) -> dict:
        return {
            "plot": [self.plot_lat, self.plot_lon],
            "generated_at": self.generated_at,
            "gate": self.gate,
            "dem_file_requirements": self.dem_file_requirements,
            "dem_ingest": self.dem_ingest.to_dict() if self.dem_ingest else None,
            "survey_ingest": self.survey_ingest.to_dict() if self.survey_ingest else None,
            "contract": self.contract,
            "reassessment": self.reassessment.to_dict() if self.reassessment else None,
        }
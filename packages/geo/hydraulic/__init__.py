"""V0.3 Phase 1 — hydraulic domain & evidence modules (design-first).

Implements the design's constraining-observations contract (J.3),
evidence-based connectivity (J.1/J.4) and gated connected-domain extraction.
The 2D flood propagation / solver is intentionally NOT here (deferred, §J.7).
"""
from .evidence import (
    EvidenceCategory,
    EvidenceContract,
    EvidenceRow,
    EvidenceStatus,
)
from .connectivity import (
    ConnectivityResult,
    ConnectivityStatus,
    UNRESOLVED_MESSAGE,
    assess_connectivity,
)
from .domain import ConnectedDomainResult, extract_connected_domain
from .sources import SourceRecord, EvidenceGatherResult, gather_plot_evidence
from .topology import LocalHydraulicTopology, build_local_topology
from .flood_evidence import (
    FloodEvidenceKind,
    FloodEvidenceRecord,
    FloodEvidenceResult,
    GAUGE_TO_PLOT_STATEMENT,
    gather_flood_evidence,
)
from .terrain_evidence import (
    TerrainEvidenceResult,
    TERRAIN_TO_CONNECTIVITY_STATEMENT,
    gather_terrain_evidence,
)
from .survey_spec import (
    SurveySpecResult,
    SurveyPointSpec,
    SurveyPointSubmission,
    SurveyVerificationResult,
    HighResDemSource,
    SURVEY_GATE_STATEMENT,
    HIGH_RES_DEM_GATE_STATEMENT,
    recommend_high_res_dem_sources,
    produce_survey_spec,
    record_survey_points,
)
from .acquire import (
    ACQUISITION_GATE_STATEMENT,
    DEM_FILE_REQUIREMENTS,
    DemIngestResult,
    SurveyIngestResult,
    ReassessmentResult,
    AcquisitionWorkflowResult,
    register_dem,
    inspect_dem_file,
    ingest_survey_points,
    integrate_into_contract,
    reassess_connectivity_after_acquisition,
)

__all__ = [
    "EvidenceCategory",
    "EvidenceContract",
    "EvidenceRow",
    "EvidenceStatus",
    "ConnectivityResult",
    "ConnectivityStatus",
    "UNRESOLVED_MESSAGE",
    "assess_connectivity",
    "ConnectedDomainResult",
    "extract_connected_domain",
    "SourceRecord",
    "EvidenceGatherResult",
    "gather_plot_evidence",
    "LocalHydraulicTopology",
    "build_local_topology",
    "FloodEvidenceKind",
    "FloodEvidenceRecord",
    "FloodEvidenceResult",
    "GAUGE_TO_PLOT_STATEMENT",
    "gather_flood_evidence",
    "TerrainEvidenceResult",
    "TERRAIN_TO_CONNECTIVITY_STATEMENT",
    "gather_terrain_evidence",
    "SurveySpecResult",
    "SurveyPointSpec",
    "SurveyPointSubmission",
    "SurveyVerificationResult",
    "HighResDemSource",
    "SURVEY_GATE_STATEMENT",
    "HIGH_RES_DEM_GATE_STATEMENT",
    "recommend_high_res_dem_sources",
    "produce_survey_spec",
    "record_survey_points",
    "ACQUISITION_GATE_STATEMENT",
    "DEM_FILE_REQUIREMENTS",
    "DemIngestResult",
    "SurveyIngestResult",
    "ReassessmentResult",
    "AcquisitionWorkflowResult",
    "register_dem",
    "inspect_dem_file",
    "ingest_survey_points",
    "integrate_into_contract",
    "reassess_connectivity_after_acquisition",
]

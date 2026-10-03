"""Phase 1 — constraining-observations contract (design §J.3).

Encodes *what evidence is allowed* to establish hydraulic connectivity and a
credible plot-level flood conclusion, and — critically — asserts when the
available evidence is NOT enough.  This is the guard that keeps the system from
producing a precise-looking answer that the data cannot support.

The keys rule encoded here:

* A plot/building answer is NOT credible on GLO-30 alone.
* A conclusion is only as strong as its weakest allowed evidence.
* Missing required evidence -> the caller must emit an "unresolved" outcome
  rather than a fabricated number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EvidenceStatus(str, Enum):
    AVAILABLE = "available"          # present, authoritative, fit-for-purpose
    PARTIAL = "partial"              # present but lower resolution / indirect
    MISSING = "missing"              # not obtained yet
    NOT_APPLICABLE = "not_applicable"


class EvidenceCategory(str, Enum):
    # Ordered roughly by resolution / how definitive each is for connectivity.
    CHANNEL_CENTERLINE = "channel_centerline"
    CHANNELS_DRAINS = "channels_drains"
    EMBANKMENTS_ROAD_RAIL = "embankments_road_rail"
    BRIDGES_CULVERTS = "bridges_culverts"
    GAUGE_OBSERVATIONS = "gauge_observations"
    DOCUMENTED_FLOOD_EXTENTS = "documented_flood_extents"
    LOCAL_SURVEY = "local_survey"
    HIGH_RES_DEM = "high_res_dem"
    FLOOD_CONTROL = "flood_control"


# Resolution / fit-for-purpose ordering used for the weakest-evidence rule.
# Higher index = finer / more definitive for a property-level conclusion.
_CATEGORY_ORDER = [
    EvidenceCategory.CHANNEL_CENTERLINE,
    EvidenceCategory.CHANNELS_DRAINS,
    EvidenceCategory.EMBANKMENTS_ROAD_RAIL,
    EvidenceCategory.BRIDGES_CULVERTS,
    EvidenceCategory.GAUGE_OBSERVATIONS,
    EvidenceCategory.DOCUMENTED_FLOOD_EXTENTS,
    EvidenceCategory.LOCAL_SURVEY,
    EvidenceCategory.HIGH_RES_DEM,
]

# Categories whose absence alone prevents a *property/building-level* verdict.
# (GLO-30 can bound a corridor-scale flood; it cannot place water at a building.)
_PLOT_LEVEL_REQUIRED = {
    EvidenceCategory.LOCAL_SURVEY,
    EvidenceCategory.HIGH_RES_DEM,
}


@dataclass
class EvidenceRow:
    """One row of the constraining-observations contract."""
    category: EvidenceCategory
    status: EvidenceStatus
    source: str | None = None       # who provides it (e.g. "OpenStreetMap", "CWC")
    reference: str | None = None    # specific id / URL / tag
    note: str = ""
    confidence: str = "medium"      # high | medium | low | unset

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "status": self.status.value,
            "source": self.source,
            "reference": self.reference,
            "note": self.note,
            "confidence": self.confidence,
        }


@dataclass
class EvidenceContract:
    """The declared evidence contract for one assessment point (the plot).

    ``plot_level_credible`` is the single gate the rest of the pipeline consults
    before it is allowed to produce a building/plot-level flood-depth or risk
    number.  When ``False`` the correct output is the "unresolved" statement
    (design §J.1), never a fabricated value.
    """
    plot_lat: float
    plot_lon: float
    rows: list[EvidenceRow] = field(default_factory=list)

    def row(self, category: EvidenceCategory) -> EvidenceRow | None:
        for r in self.rows:
            if r.category == category:
                return r
        return None

    def _status(self, category: EvidenceCategory) -> EvidenceStatus:
        row = self.row(category)
        return row.status if row else EvidenceStatus.MISSING

    def weakest_status(self) -> EvidenceStatus:
        """Status of the weakest (coarsest, most definitive-gap) category.

        Categories earlier in ``_CATEGORY_ORDER`` are coarser; a MISSING coarse
        category is the dominant limitation.
        """
        worst = 0
        result = EvidenceStatus.AVAILABLE
        for i, cat in enumerate(_CATEGORY_ORDER):
            st = self._status(cat)
            if st == EvidenceStatus.NOT_APPLICABLE:
                continue
            # A MISSING/PARTIAL coarse category dominates: it is the biggest gap.
            if i > worst and st.value in ("missing", "partial"):
                worst = i
                result = st
        return result

    @property
    def plot_level_credible(self) -> bool:
        """True only if every plot-level-required category is available.

        This enforces the design rule: *a plot/building answer is NOT credible
        on GLO-30 alone* (J.3 last row + J.8).
        """
        for cat in _PLOT_LEVEL_REQUIRED:
            if self._status(cat) != EvidenceStatus.AVAILABLE:
                return False
        return True

    def missing_plot_level_evidence(self) -> list[EvidenceCategory]:
        return [c for c in _PLOT_LEVEL_REQUIRED if self._status(c) != EvidenceStatus.AVAILABLE]

    def to_dict(self) -> dict:
        return {
            "plot": [self.plot_lat, self.plot_lon],
            "plot_level_credible": self.plot_level_credible,
            "weakest_status": self.weakest_status().value,
            "missing_plot_level_evidence": [c.value for c in self.missing_plot_level_evidence()],
            "rows": [r.to_dict() for r in self.rows],
        }

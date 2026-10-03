"""Transparent flood-exposure scoring (V0.1).

This is **NOT** a hydraulic model and **NOT** a probability of disaster.
It is a deterministic, configurable score derived from
geographic/topographic proxies so that downstream UI can give users a
first-pass assessment and identify the dominant contributing factors.

All weights live in :class:`ScoreWeights` so the formula is auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoreWeights:
    distance: float = 0.25
    elevation: float = 0.25
    connectivity: float = 0.20
    historical: float = 0.15
    flow_accumulation: float = 0.15

    def __post_init__(self) -> None:
        total = self.distance + self.elevation + self.connectivity + self.historical + self.flow_accumulation
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0, got {total:.4f}")

    def to_dict(self) -> dict:
        return {
            "distance": self.distance,
            "elevation": self.elevation,
            "connectivity": self.connectivity,
            "historical": self.historical,
            "flow_accumulation": self.flow_accumulation,
        }


@dataclass
class ExposureInputs:
    nearest_river_km: float | None
    nearest_reservoir_km: float | None
    nearest_dam_km: float | None
    plot_elevation_m: float | None
    nearest_water_elevation_m: float | None  # approx; from nearest river/sample DEM
    slope_deg: float | None
    flow_accumulation_at_plot: int | None
    historical_flood_events: int  # count within radius
    hydraulic_connection: str  # unknown | possible | likely | unlikely | none


@dataclass
class ExposureResult:
    score: float  # 0..100
    category: str  # low | moderate | high | very_high
    confidence: str  # low | medium | high
    contributing_factors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    weights: dict | None = None
    sub_scores: dict | None = None

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "category": self.category,
            "confidence": self.confidence,
            "contributing_factors": self.contributing_factors,
            "limitations": self.limitations,
            "weights": self.weights,
            "sub_scores": {k: round(v, 2) if isinstance(v, float) else v for k, v in (self.sub_scores or {}).items()},
        }


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _score_distance(km: float | None) -> tuple[float, str]:
    """Closer to a major water feature = higher exposure contribution."""
    if km is None:
        return 50.0, "no nearby river detected"
    if km < 0.5:
        return 95.0, f"river within {km:.1f} km"
    if km < 2:
        return 80.0, f"river within {km:.1f} km"
    if km < 5:
        return 60.0, f"river within {km:.1f} km"
    if km < 15:
        return 35.0, f"river {km:.1f} km away"
    return 15.0, f"river {km:.1f} km away"


def _score_elevation(plot_m: float | None, water_m: float | None) -> tuple[float, str]:
    if plot_m is None:
        return 50.0, "plot elevation unknown"
    if water_m is None:
        return 40.0, "nearest water elevation unknown"
    diff = plot_m - water_m
    if diff < 0:
        return 95.0, "plot sits BELOW nearby water surface"
    if diff < 2:
        return 80.0, f"plot only +{diff:.1f} m above water"
    if diff < 10:
        return 55.0, f"plot +{diff:.1f} m above water"
    if diff < 30:
        return 25.0, f"plot +{diff:.1f} m above water"
    return 10.0, f"plot +{diff:.1f} m above water"


def _score_connectivity(conn: str) -> tuple[float, str]:
    return {
        "likely": (85.0, "hydraulically connected to upstream infrastructure (likely)"),
        "possible": (55.0, "hydraulic connection possible but not confirmed"),
        "unknown": (40.0, "hydraulic connection unknown"),
        "unlikely": (15.0, "no confirmed hydraulic connection"),
        "none": (5.0, "no water infrastructure detected"),
    }.get(conn, (40.0, "connection unknown"))


def _score_historical(n: int) -> tuple[float, str]:
    if n <= 0:
        return 10.0, "no historical flood events in this area"
    if n == 1:
        return 35.0, "1 historical flood event observed"
    if n <= 3:
        return 60.0, f"{n} historical flood events observed"
    return 85.0, f"{n} historical flood events observed"


def _score_flow_accumulation(flow_cells: int | None) -> tuple[float, str]:
    if flow_cells is None or flow_cells <= 1:
        return 10.0, "plot is on a local high (low flow accumulation)"
    if flow_cells < 10:
        return 35.0, f"flow accumulation {flow_cells} cells"
    if flow_cells < 100:
        return 60.0, f"flow accumulation {flow_cells} cells"
    return 85.0, f"flow accumulation {flow_cells} cells"


def _category(score: float) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "moderate"
    if score < 75:
        return "high"
    return "very_high"


def _confidence(inputs: ExposureInputs) -> str:
    flags = 0
    if inputs.nearest_river_km is not None:
        flags += 1
    if inputs.plot_elevation_m is not None and inputs.nearest_water_elevation_m is not None:
        flags += 1
    if inputs.flow_accumulation_at_plot is not None:
        flags += 1
    if inputs.historical_flood_events >= 0 and inputs.hydraulic_connection != "unknown":
        flags += 1
    return {0: "low", 1: "low", 2: "medium", 3: "high", 4: "high"}[flags]


def compute_exposure(inputs: ExposureInputs, weights: ScoreWeights | None = None) -> ExposureResult:
    weights = weights or ScoreWeights()
    d_score, d_note = _score_distance(inputs.nearest_river_km)
    e_score, e_note = _score_elevation(inputs.plot_elevation_m, inputs.nearest_water_elevation_m)
    c_score, c_note = _score_connectivity(inputs.hydraulic_connection)
    h_score, h_note = _score_historical(inputs.historical_flood_events)
    f_score, f_note = _score_flow_accumulation(inputs.flow_accumulation_at_plot)

    score = (
        d_score * weights.distance
        + e_score * weights.elevation
        + c_score * weights.connectivity
        + h_score * weights.historical
        + f_score * weights.flow_accumulation
    )
    score = _clamp(score)

    contributing = []
    for n, s in (
        (d_note, d_score), (e_note, e_score), (c_note, c_score),
        (h_note, h_score), (f_note, f_score),
    ):
        if s >= 55:
            contributing.append(n)

    return ExposureResult(
        score=score,
        category=_category(score),
        confidence=_confidence(inputs),
        contributing_factors=contributing,
        limitations=[
            "Score is a transparent weighted index, not a hydraulic model.",
            "Nearest-water elevation uses sampled DEM cells, not surveyed water levels.",
            "Dam-break, breach hydraulics, and arrival times are NOT modelled in V0.1.",
            "Historical flood count uses available OSM-tagged overlays; absence ≠ safety.",
        ],
        weights=weights.to_dict(),
        sub_scores={
            "distance": d_score, "elevation": e_score, "connectivity": c_score,
            "historical": h_score, "flow_accumulation": f_score,
        },
    )
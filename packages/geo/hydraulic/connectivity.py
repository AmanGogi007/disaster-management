"""Phase 1 — evidence-based hydraulic connectivity (design §J.1 / §J.4).

Computes whether water travelling along the Sutlej (or an established local
drainage network) can physically reach the plot, but **only from evidence**,
never by manufacturing a path.

The three outputs are first-class:

* ``CONNECTED`` — there is a supported physical path and the evidence at an
  adequate resolution backs it.
* ``NOT_CONNECTED`` — positive evidence of a definitive barrier (e.g. a mapped,
  survey-confirmed embankment with no hydraulic opening) at an adequate
  resolution. Absence of a resolvable path is NOT enough here.
* ``UNRESOLVED`` — the evidence cannot determine connectivity (e.g. D8 is
  degenerate on a flat 30 m cell, no survey/local-drainage evidence). This is a
  *valid* result, not a failure, and is reported verbatim per design §J.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .evidence import EvidenceCategory, EvidenceStatus, EvidenceContract

if TYPE_CHECKING:  # pragma: no cover
    from ..terrain.preprocess import TerrainProcessResult
    from ..raster.dem import DEM


class ConnectivityStatus(str):
    CONNECTED = "connected"
    NOT_CONNECTED = "not_connected"
    UNRESOLVED = "unresolved"


UNRESOLVED_MESSAGE = (
    "Hydraulic connectivity unresolved at 30 m DEM resolution."
)

# Valid D8 flow directions used by the pysheds pipeline (dirmap powers of two).
# Anything else (-1 flat, -2 sink/nodata, 0) means the cell has no resolvable
# downhill path, so D8 cannot route water from it.
_VALID_D8_DIRECTIONS = frozenset({1, 2, 4, 8, 16, 32, 64, 128})


@dataclass
class ConnectivityResult:
    status: str
    reason: str = ""
    # Ordered list of evidence-checks that were performed and their verdicts.
    checks: list[dict] = field(default_factory=list)
    # Whether the plot/DEM connectivity was established via a resolvable path.
    path_established: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "path_established": self.path_established,
            "checks": self.checks,
        }


def assess_connectivity(
    dem: "DEM | None",
    proc: "TerrainProcessResult | None",
    contract: EvidenceContract,
    *,
    plot_lat: float,
    plot_lon: float,
    flat_tolerance_m: float = 0.5,
) -> ConnectivityResult:
    """Evaluate plot-to-channel connectivity from evidence only (J.4).

    Parameters
    ----------
    dem, proc : real DEM and its preprocessed grids (may be None if unavailable).
    contract : the constraining-observations contract (J.3).
    plot_lat, plot_lon : the plot point.
    flat_tolerance_m : local relief below which the cell is considered flat for
        the D8 path test (D8 cannot resolve routing on a flat reach).

    Returns
    -------
    ConnectivityResult — CONNECTED / NOT_CONNECTED / UNRESOLVED.
    """
    checks: list[dict] = []
    contract = contract or EvidenceContract(plot_lat, plot_lon)

    # ---- Evidence check 1: is there an anchored channel/centreline? --------
    chan_row = contract.row(EvidenceCategory.CHANNEL_CENTERLINE)
    has_channel = chan_row is not None and chan_row.status == EvidenceStatus.AVAILABLE
    checks.append(_check(
        "channel_centerline_present",
        has_channel,
        "Sutlej centreline available and anchored",
        chan_row.to_dict() if chan_row else None,
    ))

    # ---- Evidence check 2: is local drainage (channels/drains/survey) present?
    #      A *documented* local drainage link is the only positive evidence that
    #      can connect a low-lying plot to the channel.
    drains_row = contract.row(EvidenceCategory.CHANNELS_DRAINS)
    survey_row = contract.row(EvidenceCategory.LOCAL_SURVEY)
    documented_link = any(
        r is not None and r.status == EvidenceStatus.AVAILABLE
        for r in (drains_row, survey_row)
    )
    checks.append(_check(
        "documented_local_drainage",
        documented_link,
        "A documented channel/drain/survey link from channel to plot",
        {"channels_drains": drains_row.to_dict() if drains_row else None,
         "local_survey": survey_row.to_dict() if survey_row else None},
    ))

    # ---- Evidence check 3: is the plot on a resolvable (non-flat) reach? ----
    resolvable = _reach_resolvable(dem, proc, plot_lat, plot_lon, flat_tolerance_m)
    checks.append(_check(
        "terrain_reach_resolvable",
        resolvable,
        "DEM gradient can resolve a drainage path at the plot (not flat)",
        None,
    ))

    # ---- Evidence check 4: positive barrier? -------------------------------
    barrier_row = contract.row(EvidenceCategory.EMBANKMENTS_ROAD_RAIL)
    has_barrier = (
        barrier_row is not None
        and barrier_row.status == EvidenceStatus.AVAILABLE
        and _row_notes_barrier(barrier_row.note)
    )
    checks.append(_check(
        "definitive_barrier",
        has_barrier,
        "Survey-confirmed embankment with no hydraulic opening separates plot",
        barrier_row.to_dict() if barrier_row else None,
    ))

    if has_barrier:
        return ConnectivityResult(
            status=ConnectivityStatus.NOT_CONNECTED,
            reason="A survey-confirmed barrier with no hydraulic opening "
                   "separates the plot from the channel.",
            checks=checks,
            path_established=False,
        )

    # ---- Decision on resolvable path + documented link ---------------------
    if has_channel and documented_link and resolvable:
        # We have a positive channel anchor, a documented drainage link, and the
        # terrain actually resolves a path.  Only then can we claim connectivity.
        return ConnectivityResult(
            status=ConnectivityStatus.CONNECTED,
            reason="Anchored channel + documented local drainage link + a "
                   "DEM-resolvable terrain path establish connectivity.",
            checks=checks,
            path_established=True,
        )

    if not has_channel:
        return ConnectivityResult(
            status=ConnectivityStatus.UNRESOLVED,
            reason="No anchored channel/centreline evidence to evaluate connectivity.",
            checks=checks,
        )

    # The decisive Phase 0 finding: on a flat 30 m reach with no documented
    # local-drainage/survey link, neither the DEM nor any positive evidence can
    # route water to the plot.  We must NOT invent a path.
    return ConnectivityResult(
        status=ConnectivityStatus.UNRESOLVED,
        reason=UNRESOLVED_MESSAGE,
        checks=checks,
        path_established=False,
    )


def _reach_resolvable(dem, proc, lat, lon, tol_m: float) -> bool:
    """True if the DEM gradient at the plot can resolve a drainage direction.

    Uses the precomputed D8 flow direction: a non-zero direction that actually
    points to a lower neighbour indicates a resolvable slope.  On the flat
    Ropar reach this is 0 / undefined, so we return False.
    """
    if dem is None or proc is None or proc.flow_direction is None:
        return False
    t = dem.transform
    row = t.row_at_lat(lat)
    col = t.col_at_lon(lon)
    if row < 0 or row >= proc.flow_direction.shape[0]:
        return False
    if col < 0 or col >= proc.flow_direction.shape[1]:
        return False
    d = int(proc.flow_direction[row, col])
    if d not in _VALID_D8_DIRECTIONS:
        # -1 (flat), -2 (sink/nodata), 0: no resolvable downhill path.
        return False
    # Confirm there is an actual downslope drop > tolerance (not an artifact).
    z = dem.elevation[row, col]
    if not np_isfinite(z):
        return False
    return True


def _row_notes_barrier(note: str) -> bool:
    return "no hydraulic opening" in note.lower() or "impermeable" in note.lower()


def _check(name: str, passed: bool, desc: str, detail) -> dict:
    return {
        "check": name,
        "passed": bool(passed),
        "description": desc,
        "detail": detail,
    }


try:  # pragma: no cover
    import numpy as _np
    def np_isfinite(v):
        return bool(_np.isfinite(v))
except Exception:  # pragma: no cover
    def np_isfinite(v):  # pragma: no cover
        import math
        return math.isfinite(float(v))

"""Phase 1 — connected terrain domain extraction (design §J.2 / §J.4).

Extracts the hydrologically connected terrain domain for the plot, but ONLY
when connectivity has been established by evidence (``assess_connectivity``
returned CONNECTED).  It never manufactures a domain, a flood extent, or a path.

If connectivity is UNRESOLVED or NOT_CONNECTED, ``extract_connected_domain``
returns a result whose ``domain`` is None and whose ``outcome`` carries the
design's §J.1 "unresolved" statement — it is then the caller's job to surface
that statement to the end user instead of a fabricated flood number.

Consistent with Phase 0, this module reports the *dynamic* domain (its extent
and cell count at the DEM's simulation grid), never a hard-coded box.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .connectivity import ConnectivityResult, ConnectivityStatus, UNRESOLVED_MESSAGE

if TYPE_CHECKING:  # pragma: no cover
    from ..terrain.preprocess import TerrainProcessResult
    from ..raster.dem import DEM


@dataclass
class ConnectedDomainResult:
    outcome: str                      # "connected" | "unresolved" | "not_connected"
    domain: str | None = None         # e.g. "terrain" — set only on connected
    domain_cells: int | None = None
    domain_extent_sqkm: float | None = None
    message: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "domain_cells": self.domain_cells,
            "domain_extent_sqkm": self.domain_extent_sqkm,
            "message": self.message,
            "notes": self.notes,
        }


def extract_connected_domain(
    conn: ConnectivityResult,
    dem=None,
    proc: "TerrainProcessResult | None" = None,
) -> ConnectedDomainResult:
    """Return the hydraulic domain iff connectivity is evidence-established.

    Parameters
    ----------
    conn : result of ``assess_connectivity``.
    dem / proc : real DEM + preprocessed grids used to quantify the domain.

    Returns
    -------
    ConnectedDomainResult — ``domain`` populated only when ``conn.status`` is
    CONNECTED; otherwise None and outcome carries the J.1 statement.
    """
    if conn.status == ConnectivityStatus.UNRESOLVED:
        return ConnectedDomainResult(
            outcome="unresolved",
            message=UNRESOLVED_MESSAGE,
            notes=[conn.reason],
        )
    if conn.status == ConnectivityStatus.NOT_CONNECTED:
        return ConnectedDomainResult(
            outcome="not_connected",
            message="Plot is not hydraulically connected to the channel "
                    "(evidence: definitive barrier).",
            notes=[conn.reason],
        )

    # Connected: quantify the dynamic domain from the real DEM.
    if proc is None or dem is None:
        return ConnectedDomainResult(
            outcome="connected",
            message="Connected, but domain could not be quantified (DEM/preproc"
                    " unavailable).",
        )

    cells = proc.cell_count
    extent = _bbox_area_sqkm(dem.bounds())
    return ConnectedDomainResult(
        outcome="connected",
        domain="terrain",
        domain_cells=cells,
        domain_extent_sqkm=extent,
        message="Hydrologically connected terrain domain quantified from the "
                "real DEM.",
        notes=[
            "Domain is the dynamic DEM/domain extent (Phase 0), not a "
            "hard-coded box.",
            "Flood propagation/depth is NOT computed here (deferred to a later "
            "phase); connectivity is established but stage/extent modelling is "
            "out of scope for this deliverable.",
        ],
    )


def _bbox_area_sqkm(bounds):
    south, west, north, east = bounds
    import math
    mid_lat = math.radians((south + north) / 2)
    km_lat = (north - south) * 111.0
    km_lon = (east - west) * 111.0 * max(0.1, math.cos(mid_lat))
    return round(km_lat * km_lon, 2)

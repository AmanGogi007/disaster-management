"""Phase 1e — plot-level terrain evidence (design §J.3 plot-level blockers).

Characterises the elevation relationship between the plot, the surrounding
ground, the roads/railway/embankment barriers, the local canal/drain, the low
points/depressions and the reconciled Sutlej corridor — from the acquired DEM
(primary Copernicus GLO-30, 1 arc-second) and the OSM feature geometry.

Discipline enforced here (mirrors the J-series rules):

* **DEM-derived vs surveyed.** Every numeric elevation below is DEM-derived and
  labelled as such.  There is no surveyed elevation anywhere in this module; the
  ``surveyed`` block records the *absence* of a survey and what one must supply.
  Nothing is ever relabelled as surveyed.
* **Characterisation only, not connectivity.** A lower DEM value, a low point or
  terrain proximity to the channel does NOT by itself establish hydraulic
  connectivity or plot flood depth.  Connectivity stays gated by
  ``assess_connectivity`` (UNRESOLVED at 30 m); flood depth requires the flood
  solver, which is NOT run here.
* **Provenance preserved.** Source DEM, resolution, horizontal + vertical datum,
  coverage, retrieval time, licence, uncertainty and confidence on every item.
* **Fetch failure = fetch failure.** A finer-DEM acquisition attempt that fails
  is recorded unavailable (with reason), never silently upgraded, never
  fabricated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from ..coordinates import haversine_m
from ..raster.dem import DEM
from .evidence import EvidenceCategory

OBTAINED = "obtained"
UNAVAILABLE = "unavailable"
INSUFFICIENT = "insufficient"

# Literal gate statement for this phase (never downgraded).
TERRAIN_TO_CONNECTIVITY_STATEMENT = (
    "Plot-level terrain evidence is characterisation only. A lower DEM value, "
    "a low point, or terrain proximity to the channel does NOT by itself "
    "establish hydraulic connectivity or flood depth at the plot. Connectivity "
    "remains gated by assess_connectivity (UNRESOLVED at 30 m DEM resolution); "
    "flood depth requires the flood solver, which is NOT run in this phase."
)

DEFAULT_RADIUS_KM = 3.0


@dataclass
class PlotMeasurement:
    """Profile measurement for one feature or location on the ground."""
    label: str
    feature_type: str                        # plot | channel | local_canal_drain | barrier | crossing
    osm_id: str | None
    name: str | None
    min_distance_km: float | None
    dem_min_m: float | None
    dem_mean_m: float | None
    dem_max_m: float | None
    relative_to_plot_m: float | None          # DEM mean at feature minus DEM at plot (characterisation only)
    elevation_kind: str = "dem"               # dem | surveyed (surveyed never produced here)
    n_points: int = 0
    datum_note: str = ""
    note: str = ""


@dataclass
class TransectPoint:
    lat: float
    lon: float
    distance_km: float
    dem_elevation_m: float | None


@dataclass
class TransectResult:
    target: dict                     # nearest main-stem OSM point that defined the transect
    target_elevation_m: float | None
    plot_elevation_m: float | None
    min_elevation_m: float | None
    max_elevation_m: float | None
    drop_below_plot_m: float | None     # max positive (plot - point) along transect
    channel_relative_to_plot_m: float | None  # target DEM - plot DEM (characterisation only)
    points: list[TransectPoint]
    note: str = ""


@dataclass
class LowPoint:
    lat: float
    lon: float
    dem_elevation_m: float
    distance_from_plot_m: float
    relative_to_plot_m: float | None
    is_local_min: bool
    note: str = ""


@dataclass
class FinerDemAttempt:
    status: str
    dataset: str
    resolution_m: float | None
    vertical_datum: str | None
    plot_elevation_m: float | None
    cross_check_delta_m: float | None    # finer - primary (datum difference explicitly kept)
    note: str


@dataclass
class TerrainEvidenceResult:
    plot_lat: float
    plot_lon: float
    radius_km: float
    fetched_at: str
    dem_provenance: dict = field(default_factory=dict)
    plot: dict = field(default_factory=dict)
    neighborhood: dict = field(default_factory=dict)
    plot_boundary: dict = field(default_factory=dict)
    samples: list[PlotMeasurement] = field(default_factory=list)
    transect: TransectResult | None = None
    low_points: list[LowPoint] = field(default_factory=list)
    surveyed: dict = field(default_factory=dict)
    finer_dem: FinerDemAttempt | None = None
    connectivity_statement: str = TERRAIN_TO_CONNECTIVITY_STATEMENT
    deferred_flood_extents: dict = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plot": [self.plot_lat, self.plot_lon],
            "radius_km": self.radius_km,
            "fetched_at": self.fetched_at,
            "dem_provenance": self.dem_provenance,
            "plot_measurement": self.plot,
            "neighborhood": self.neighborhood,
            "plot_boundary": self.plot_boundary,
            "samples": [s.__dict__ for s in self.samples],
            "transect": {
                **{k: v for k, v in self.transect.__dict__.items()
                   if k != "points"},
                "points": [p.__dict__ for p in self.transect.points],
            } if self.transect else None,
            "low_points": [l.__dict__ for l in self.low_points],
            "surveyed": self.surveyed,
            "finer_dem": self.finer_dem.__dict__ if self.finer_dem else None,
            "connectivity_statement": self.connectivity_statement,
            "deferred_flood_extents": self.deferred_flood_extents,
            "caveats": self.caveats,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _r3(v, nd: int = 2):
    if v is None:
        return None
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


def _dem_provenance(dem: DEM) -> dict:
    return {
        "dataset": getattr(dem, "dataset", None),
        "source_resolution_m": getattr(dem, "source_resolution_m", None),
        "simulation_grid_m": getattr(dem, "simulation_grid_m", None),
        "horizontal_crs": getattr(dem, "horizontal_crs", dem.crs),
        "vertical_datum": getattr(dem, "vertical_datum", None),
        "vertical_offset_m": getattr(dem, "vertical_offset_m", None),
        "nodata": getattr(dem, "nodata", None),
        "bounds_deg": list(dem.bounds()),
        "provenance": getattr(dem, "provenance", None),
    }


def _plot_measurement(dem: DEM, lat: float, lon: float) -> dict:
    t = dem.transform
    row = t.row_at_lat(lat)
    col = t.col_at_lon(lon)
    slope, aspect = _slope_aspect(dem, lat, lon)
    return {
        "row": int(row) if 0 <= row < dem.rows else None,
        "col": int(col) if 0 <= col < dem.cols else None,
        "dem_elevation_m": _r3(dem.value_at(lat, lon)),
        "elevation_kind": "dem",
        "dem_source": getattr(dem, "dataset", None),
        "dem_vertical_datum": getattr(dem, "vertical_datum", None),
        "slope_deg": _r3(slope, 2),
        "aspect_deg": _r3(aspect, 1),
        "aspect_cardinal": _cardinal(aspect),
        "note": "DEM-derived (DSM) elevation at the plot cell; NOT a surveyed "
                "ground elevation.",
    }


def _cardinal(deg: float | None) -> str | None:
    if deg is None:
        return None
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((deg + 22.5) // 45) % 8]


def _slope_aspect(dem: DEM, lat: float, lon: float) -> tuple[float | None, float | None]:
    """3x3 Horn-based slope/aspect at a point (pure numpy, no external deps)."""
    t = dem.transform
    col = t.col_at_lon(lon)
    row = t.row_at_lat(lat)
    if col <= 0 or col >= dem.cols - 1 or row <= 0 or row >= dem.rows - 1:
        return None, None
    e = dem.elevation
    a = e[row - 1, col - 1]; b = e[row - 1, col]; c = e[row - 1, col + 1]
    d = e[row, col - 1]; f = e[row, col + 1]
    g = e[row + 1, col - 1]; h = e[row + 1, col]; i = e[row + 1, col + 1]
    center_lat = (t.origin_lat - (row + 0.5) * t.pixel_size_lat)
    pix_m = t.pixel_size_lon * 111_320.0 * max(0.1, math.cos(math.radians(center_lat)))
    if pix_m <= 0:
        return None, None
    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pix_m)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * pix_m)
    rise = math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy)
    slope = math.degrees(math.atan(rise))
    if dz_dx == 0 and dz_dy == 0:
        aspect = None
    else:
        aspect = (math.degrees(math.atan2(dz_dx, dz_dy)) + 360.0) % 360.0
    return slope, aspect


def _neighborhood_stats(dem: DEM, lat: float, lon: float, radius_km: float) -> dict:
    t = dem.transform
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.1, abs(math.cos(math.radians(lat)))))
    west, east = lon - dlon, lon + dlon
    north, south = lat + dlat, lat - dlat
    col0 = max(0, t.col_at_lon(west))
    col1 = min(dem.cols, t.col_at_lon(east) + 1)
    row0 = max(0, t.row_at_lat(north))
    row1 = min(dem.rows, t.row_at_lat(south) + 1)
    win = dem.elevation[row0:row1, col0:col1]
    mask = np.isfinite(win)
    if getattr(dem, "nodata", None) is not None:
        mask &= ~np.isclose(win, float(dem.nodata))
    cells = win[mask]
    if cells.size == 0:
        return {
            "status": UNAVAILABLE, "cell_count": 0,
            "coverage_deg": [south, west, north, east],
            "note": "No valid DEM cells in the neighbourhood window.",
        }
    return {
        "status": OBTAINED,
        "cell_count": int(cells.size),
        "min_m": _r3(float(cells.min())),
        "max_m": _r3(float(cells.max())),
        "mean_m": _r3(float(cells.mean())),
        "relief_m": _r3(float(cells.max() - cells.min())),
        "coverage_deg": [_r3(south, 4), _r3(west, 4), _r3(north, 4), _r3(east, 4)],
        "note": "DEM-derived (DSM) statistics over the radius window; "
                "characterisation only.",
    }


def _sample_way(dem: DEM, item: dict, label: str, feature_type: str,
                plot_elev: float | None) -> PlotMeasurement | None:
    pts = item.get("points") or []
    if not pts:
        return None
    vals = [dem.value_at(la, lo) for la, lo in pts]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    dmin = min(vals)
    dmean = float(np.mean(vals))
    dmax = max(vals)
    rel = (dmean - plot_elev) if plot_elev is not None else None
    tags = item.get("tags") or {}
    kind_tag = tags.get("waterway") or tags.get("railway") or \
        tags.get("highway") or tags.get("barrier") or ""
    return PlotMeasurement(
        label=label,
        feature_type=feature_type,
        osm_id=item.get("osm_id"),
        name=item.get("name"),
        min_distance_km=item.get("min_distance_km") or item.get("distance_km"),
        dem_min_m=_r3(dmin),
        dem_mean_m=_r3(dmean),
        dem_max_m=_r3(dmax),
        relative_to_plot_m=_r3(rel),
        elevation_kind="dem",
        n_points=len(vals),
        datum_note="DEM-derived (DSM) at 1 arc-second; vertical datum per "
                   "DEM provenance; no surveyed elevation.",
        note=f"OSM feature ({feature_type}; tag: {kind_tag or 'n/a'}). DEM mean "
             "across mapped points. Characterisation only — no connectivity or "
             "depth inference.",
    )


def _nearest_point_on_ways(ways: list[dict], lat: float, lon: float) -> tuple[dict, tuple[float, float]] | None:
    best: tuple[dict, tuple[float, float]] | None = None
    best_d = math.inf
    for w in ways:
        for p in (w.get("points") or []) + (w.get("endpoints") or []):
            d = haversine_m(lat, lon, p[0], p[1])
            if d < best_d:
                best_d = d
                best = (w, (p[0], p[1]))
    return best


def _build_transect(dem: DEM, plot_lat: float, plot_lon: float,
                    target: tuple[float, float], channel_elev: float | None,
                    n: int = 11) -> TransectResult:
    pts: list[TransectPoint] = []
    for k in range(n):
        t = k / (n - 1)
        la = plot_lat + (target[0] - plot_lat) * t
        lo = plot_lon + (target[1] - plot_lon) * t
        d = haversine_m(plot_lat, plot_lon, la, lo)
        pts.append(TransectPoint(
            lat=round(la, 6), lon=round(lo, 6),
            distance_km=_r3(d / 1000.0, 4),
            dem_elevation_m=_r3(dem.value_at(la, lo), 2),
        ))
    vals = [p.dem_elevation_m for p in pts if p.dem_elevation_m is not None]
    plot_elev = dem.value_at(plot_lat, plot_lon)
    note = ("Linear transect plot → nearest Sutlej main-stem OSM point, DEM "
            "sampled at each stop. Pure elevation contrast characterisation; "
            "NOT a hydraulic path, no connectivity or depth inference.")
    return TransectResult(
        target={"lat": round(target[0], 6), "lon": round(target[1], 6),
                "distance_km_from_plot": _r3(
                    haversine_m(plot_lat, plot_lon, target[0], target[1]) / 1000.0, 4)},
        target_elevation_m=_r3(channel_elev, 2),
        plot_elevation_m=_r3(plot_elev, 2),
        min_elevation_m=_r3(min(vals), 2) if vals else None,
        max_elevation_m=_r3(max(vals), 2) if vals else None,
        drop_below_plot_m=(
            _r3(max(0.0, (plot_elev - min(vals)))) if vals and plot_elev is not None else None),
        channel_relative_to_plot_m=(
            _r3(channel_elev - plot_elev) if channel_elev is not None and plot_elev is not None else None),
        points=pts,
        note=note,
    )


def _find_low_points(dem: DEM, lat: float, lon: float, radius_km: float,
                     plot_elev: float | None, max_n: int = 8) -> list[LowPoint]:
    t = dem.transform
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.1, abs(math.cos(math.radians(lat)))))
    col0 = max(0, t.col_at_lon(lon - dlon))
    col1 = min(dem.cols, t.col_at_lon(lon + dlon) + 1)
    row0 = max(0, t.row_at_lat(lat + dlat))
    row1 = min(dem.rows, t.row_at_lat(lat - dlat) + 1)
    if col1 <= col0 or row1 <= row0:
        return []
    win = dem.elevation[row0:row1, col0:col1]
    mask = np.isfinite(win)
    if not np.any(mask):
        return []
    # 3x3 local-minimum test (strict < all neighbours -> flats are not minima).
    padded = np.full((win.shape[0] + 2, win.shape[1] + 2), np.inf)
    padded[1:-1, 1:-1] = np.where(mask, win, np.inf)
    nbr = np.minimum.reduce(
        [padded[r:r + win.shape[0], c:c + win.shape[1]]
         for r in (0, 1, 2) for c in (0, 1, 2) if (r, c) != (1, 1)])
    is_min = mask & (win < nbr)
    rows, cols = np.nonzero(is_min)
    used_local_min = rows.size > 0
    if not used_local_min:
        rows, cols = np.nonzero(mask)
    order = np.argsort(win[rows, cols], kind="stable")
    out: list[LowPoint] = []
    for r, c in zip(rows[order], cols[order]):
        la = t.lat_at_row(row0 + int(r))
        lo = t.lon_at_col(col0 + int(c))
        if any(haversine_m(la, lo, q.lat, q.lon) < 90.0 for q in out):
            continue
        v = float(win[int(r), int(c)])
        out.append(LowPoint(
            lat=round(la, 6), lon=round(lo, 6),
            dem_elevation_m=_r3(v, 2),
            distance_from_plot_m=_r3(haversine_m(lat, lon, la, lo), 1),
            relative_to_plot_m=_r3(v - plot_elev) if plot_elev is not None else None,
            is_local_min=used_local_min,
            note="DEM-derived depression (GLO-30 DSM). Distinguishes a local "
                 "surface low, NOT a surveyed pond/basin and NOT connectivity.",
        ))
        if len(out) >= max_n:
            break
    return out


def _plot_boundary_record() -> dict:
    return {
        "status": UNAVAILABLE,
        "geometry": "point only",
        "note": "No surveyed/parcel plot boundary is available. 'The plot' is "
                "the coordinate (lat, lon) used throughout; boundary-dependent "
                "conclusions (e.g. which DEM cells fall inside the plot) are "
                "NOT asserted.",
    }


def _surveyed_record() -> dict:
    return {
        "status": UNAVAILABLE,
        "confidence": "low",
        "note": "No local ground survey acquired. A survey must supply, on a "
                "common datum with horizontal control: ground elevation at "
                "building plinths, road crown heights, rail/embankment top "
                "elevations, canal bed/berm elevations, culvert/bridge invert "
                "and soffit elevations, and plot grading. Until then plot-level "
                "answers stay NOT credible (J.3).",
    }


def _default_finer_provider():
    from ..terrain.providers.srtm import SRTMProvider
    return SRTMProvider()


def _attempt_finer_dem(provider, plot_lat: float, plot_lon: float,
                       prim_elev: float | None, prim_datum: str | None) -> FinerDemAttempt:
    if provider is None:
        return FinerDemAttempt(
            status=UNAVAILABLE, dataset="none", resolution_m=None,
            vertical_datum=None, plot_elevation_m=None,
            cross_check_delta_m=None,
            note="No finer-DEM provider attempted.")
    try:
        res = provider.get_dem(plot_lat, plot_lon, DEFAULT_RADIUS_KM)
    except Exception as exc:  # noqa: BLE001 — any provider failure is honest
        return FinerDemAttempt(
            status=UNAVAILABLE, dataset=getattr(provider, "name", "unknown"),
            resolution_m=None, vertical_datum=None, plot_elevation_m=None,
            cross_check_delta_m=None,
            note=f"Finer-DEM attempt failed ({exc}) — recorded unavailable, "
                 "never fabricated.")
    if res is None or getattr(res, "dem", None) is None:
        return FinerDemAttempt(
            status=UNAVAILABLE,
            dataset=getattr(res, "dataset", "unknown"),
            resolution_m=getattr(res, "resolution_m", None),
            vertical_datum=getattr(res, "vertical_datum", None),
            plot_elevation_m=None, cross_check_delta_m=None,
            note=(f"{getattr(res, 'note', 'Provider returned no DEM.')} "
                  "Recorded as fetch failure / no data, not certified absence."))
    dem_f = res.dem
    elev = dem_f.value_at(plot_lat, plot_lon)
    delta = (elev - prim_elev) if elev is not None and prim_elev is not None else None
    note = (
        f"Acquired '{res.dataset}' (resolution {_r3(res.resolution_m, 1)} m, "
        f"vertical datum {res.vertical_datum}) as a CROSS-CHECK of the primary "
        f"DEM, NOT a sub-30 m product. Delta vs primary "
        f"{delta if delta is not None else 'n/a'} m — datums explicitly differ "
        f"({res.vertical_datum} vs primary {prim_datum}), so the delta is "
        "reported, never fused. A sub-30 m DEM (ALOS/TanDEM/CartoSAT/drone) is "
        "still required for plot-level credibility (J.3)."
    )
    return FinerDemAttempt(
        status=OBTAINED, dataset=res.dataset,
        resolution_m=_r3(res.resolution_m, 1),
        vertical_datum=res.vertical_datum,
        plot_elevation_m=_r3(elev, 2),
        cross_check_delta_m=_r3(delta, 2),
        note=note,
    )


_DEFERRED_FLOOD_EXTENTS = {
    "status": "deferred",
    "why_not_blocking": "Terrain acquisition is independent of historical "
                        "flood-extent intersection; terrain is complete without it.",
    "remaining": [
        "GFD/DFO v1 (2000–2018, 913 events): per-event raster intersection with "
        "the Ropar corridor bbox; read duration + JRC-permanent-water bands per event.",
        "Events AFTER 2018 (e.g. 2019, 2023) are NOT in GFD v1 — require CWC/NASA/"
        "state flood-extent products instead.",
        "Reconcile any intersected event with the reconciled main stem + BBMB "
        "Bhakra release record (upstream boundary) before use as validation data.",
        "Record each event's spatial/temporal coverage + uncertainty; never "
        "convert an extent polygon into a plot depth without the solver phase.",
    ],
}


def gather_terrain_evidence(
    dem: DEM | None,
    gather_result=None,
    *,
    plot_lat: float,
    plot_lon: float,
    radius_km: float = DEFAULT_RADIUS_KM,
    finer_provider=None,
) -> TerrainEvidenceResult:
    """Characterise plot-level terrain elevation relationships (evidence only).

    Parameters
    ----------
    dem : the DEM carrying the plot (primary GLO-30 corridor extraction).
    gather_result : EvidenceGatherResult with OSM feature geometry (channel/
        drains/barriers); provides the reconciled context, never connectivity.
    finer_provider : optional ElevationProvider for the finer-DEM cross-check
        attempt; defaults to SRTM GL1 (same ~30 m, EGM96) when None.
    """
    fetched_at = _now()
    result = TerrainEvidenceResult(
        plot_lat=plot_lat, plot_lon=plot_lon, radius_km=radius_km,
        fetched_at=fetched_at,
    )
    if dem is None:
        result.dem_provenance = {"status": UNAVAILABLE,
                                 "note": "No DEM supplied — terrain evidence unavailable."}
        result.plot_boundary = _plot_boundary_record()
        result.surveyed = _surveyed_record()
        result.caveats = ["No DEM available; no terrain measurements made."]
        result.deferred_flood_extents = _DEFERRED_FLOOD_EXTENTS
        return result

    result.dem_provenance = _dem_provenance(dem)
    plot_elev = dem.value_at(plot_lat, plot_lon)
    result.plot = _plot_measurement(dem, plot_lat, plot_lon)
    result.neighborhood = _neighborhood_stats(dem, plot_lat, plot_lon, radius_km)
    result.plot_boundary = _plot_boundary_record()
    result.surveyed = _surveyed_record()

    raw = (gather_result.raw_items if gather_result else {}) or {}
    rec = getattr(gather_result, "channel_reconciliation", None) if gather_result else None
    main_ids = set(rec.main_stem_ids) if rec else set()

    # ---- 1. Feature elevation samples (OSM geometry overlaid on the DEM) ----
    for cat, ftype in ((EvidenceCategory.CHANNEL_CENTERLINE, "channel"),
                       (EvidenceCategory.CHANNELS_DRAINS, "local_canal_drain"),
                       (EvidenceCategory.EMBANKMENTS_ROAD_RAIL, "barrier"),
                       (EvidenceCategory.BRIDGES_CULVERTS, "crossing")):
        for item in raw.get(cat.value, []):
            role = ""
            if cat is EvidenceCategory.CHANNEL_CENTERLINE:
                role = " (main stem)" if item.get("osm_id") in main_ids else ""
            label = f"{ftype}{role}:{item.get('osm_id') or ''}"
            m = _sample_way(dem, item, label.strip(":"), ftype, plot_elev)
            if m is not None:
                result.samples.append(m)
    result.samples.sort(key=lambda s: (s.min_distance_km is None, s.min_distance_km or 0.0))

    # ---- 2. Transect plot → nearest main-stem channel point ----
    main_items = [it for it in raw.get(EvidenceCategory.CHANNEL_CENTERLINE.value, [])
                  if it.get("osm_id") in main_ids] or \
        raw.get(EvidenceCategory.CHANNEL_CENTERLINE.value, [])
    hit = _nearest_point_on_ways(main_items, plot_lat, plot_lon)
    if hit is not None:
        w, target = hit
        channel_elev = dem.value_at(target[0], target[1])
        result.transect = _build_transect(
            dem, plot_lat, plot_lon, target, channel_elev)

    # ---- 3. Low points / depressions ----
    result.low_points = _find_low_points(dem, plot_lat, plot_lon, radius_km, plot_elev)

    # ---- 4. Finer-DEM cross-check attempt ----
    if finer_provider is None:
        try:
            finer_provider = _default_finer_provider()
        except Exception as exc:  # noqa: BLE001
            finer_provider = None
    prim_datum = getattr(dem, "vertical_datum", None)
    result.finer_dem = _attempt_finer_dem(finer_provider, plot_lat, plot_lon,
                                          plot_elev, prim_datum)

    result.deferred_flood_extents = _DEFERRED_FLOOD_EXTENTS
    result.caveats = [
        "All numeric elevations are DEM-derived (DSM, Copernicus GLO-30 unless "
        "stated) and are characterisation only — none is a surveyed ground "
        "elevation, and none is converted into flood depth.",
        "GLO-30 is a surface model (DSM): vegetation/embankment/roof tops can "
        "contribute to the cell value; a 30 m cell cannot resolve microtopography "
        "(ditches, bunds, plot grading, culvert inverts).",
        "Vertical datum is EGM2008 for GLO-30 (EGM96 for the SRTM cross-check); "
        "surveyed elevations on a local/orthometric datum would need explicit "
        "transformation before any comparison.",
        "OSM feature geometry is horizontal-only (WGS84; no vertical datum) — "
        "feature elevations here are purely the DEM sampled at the mapped "
        "geometry, never OSM tag heights.",
        "Terrain proximity / a low point does NOT imply hydraulic connectivity "
        "or flood depth; see the gate statement.",
        "No flood solver has been run (this phase is evidence-only).",
        "Plot-level credibility (J.3) still requires local survey + sub-30 m DEM.",
    ]
    return result
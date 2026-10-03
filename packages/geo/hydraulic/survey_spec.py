"""Phase 1f — local-survey acquisition specification + high-res DEM sources.

Producing a field-ready survey specification is a *measurement contract* for a
land surveyor, NOT a set of measurements.  Nothing in this module invents a
value; every requested measurement ships as ``measured_value: None`` with
status ``unverified`` until real, provenance-carrying observations arrive.

Two things are established here:

1. **Local-survey acquisition specification** — the precise points, spacing,
   elevations, datum/benchmark requirements, plot boundary, drainage/road/
   channel/culvert crossings to capture, derived from the *actual reconciled
   local features* (main-stem Sutlej 919730633 ~0.129 km, canal/drain
   377207446, barriers/railways 680091133 & 919730631, crossings 254573869 /
   254573867, the DEM low points, the plot cell itself).

2. **High-resolution DEM source determination** for the exact plot — a
   candidate matrix with resolution / vertical datum / licence / access /
   suitability, where every availability claim is either live-probed or
   honestly labelled ``documented``/``unverified``.  A satellite sub-30 m DEM
   reduces — never removes — the need for field verification of
   microtopography and crossing inverts.

Discipline (enforced in module + tests):

* No measurement may be assumed or fabricated.  ``record_survey_points``
  refuses every point lacking verified provenance + datum + accuracy.
* Datums (EGM96 / EGM2008 / MSL orthometric) are recorded per point, never
  fused.  ``vertical_offset_m``-style fusing of DEM deltas stays reported-only.
* Connectivity stays UNRESOLVED until the fine-scale evidence actually resolves
  it; the flood solver is NOT run in this phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

SURVEY_GATE_STATEMENT = (
    "No survey or elevation measurement may be assumed, guessed, or fabricated. "
    "Only verified observations (with provenance, horizontal/vertical datum, "
    "and reported accuracy) may be integrated. Until such data resolves the "
    "reach, hydraulic connectivity stays UNRESOLVED and no flood depth is "
    "produced. The flood solver is NOT run in this phase."
)

HIGH_RES_DEM_GATE_STATEMENT = (
    "A satellite-based sub-30 m DEM may reduce, never remove, the need for "
    "field verification of microtopography, culvert inverts and crossing "
    "openings. Datum differences (EGM96 / EGM2008 / MSL) are never fused; each "
    "acquisition keeps its own datum and uncertainty. No DEM source is treated "
    "as surveyed ground."
)

PLOT_GRADING = "plot_grading"
BUILDING_PLINTH = "building_plinth"
BENCHMARK = "benchmark"
CHANNEL_BANK = "channel_bank"
CULVERT_CROSSING = "culvert_crossing"
DRAINAGE_INVERT = "drainage_invert"
BARRIER_CROWN = "barrier_crown"
LOW_POINT_CHECK = "low_point_check"
PROPERTY_BOUNDARY = "property_boundary"
WATER_LEVEL = "water_level"

_SURVEY_STATUS = "unverified"  # every spec'd point starts unverified

# DEM candidate statuses — availability is only "available" when live-probed.
DEM_AVAILABLE = "available"
DEM_UNAVAILABLE = "unavailable"
DEM_UNVERIFIED = "unverified"
DEM_COMMERCIAL = "commercial"


@dataclass
class SurveyPointSpec:
    """One field-measurement requirement (a spec, never a measured value)."""
    category: str
    category_label: str
    target: str
    source_osm_id: str | None = None
    source_name: str | None = None
    derived_from: str = "plot_context"    # plot_context | reconciled_osm | dem_low_point
    location_note: str = ""
    points_required: str = ""
    spacing_m: str = ""
    fields_to_measure: list[str] = field(default_factory=list)
    vertical_datum_req: str = ""
    horizontal_system: str = "WGS84 (EPSG:4326) + UTM 43N grid"
    accuracy_req: str = ""
    measured_value: float | None = None   # ALWAYS None until verified data arrives
    status: str = _SURVEY_STATUS

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "category_label": self.category_label,
            "target": self.target,
            "source_osm_id": self.source_osm_id,
            "source_name": self.source_name,
            "derived_from": self.derived_from,
            "location_note": self.location_note,
            "points_required": self.points_required,
            "spacing_m": self.spacing_m,
            "fields_to_measure": self.fields_to_measure,
            "vertical_datum_req": self.vertical_datum_req,
            "horizontal_system": self.horizontal_system,
            "accuracy_req": self.accuracy_req,
            "measured_value": self.measured_value,
            "status": self.status,
        }


@dataclass
class SurveyPointSubmission:
    """A claimed survey observation submitted for integration (refused unless
    verified)."""
    category: str
    target: str
    value_m: float
    provenance: str
    vertical_datum: str
    horizontal_system: str
    accuracy_m: float
    verified: bool
    source_osm_id: str | None = None

    def is_integrable(self) -> bool:
        return (
            self.verified is True
            and self.value_m is not None
            and bool(self.provenance)
            and bool(self.vertical_datum)
            and bool(self.horizontal_system)
            and self.accuracy_m is not None
            and self.accuracy_m >= 0.0
        )


@dataclass
class SurveyVerificationResult:
    """Outcome of trying to integrate claimed survey points."""
    accepted: list[dict] = field(default_factory=list)
    refused: list[dict] = field(default_factory=list)
    connectivity_status: str = ""
    note: str = (
        "Accepted points are stored as verified observations for a future "
        "solver; they do NOT by themselves change connectivity or produce a "
        "flood depth."
    )

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "refused": self.refused,
            "connectivity_status": self.connectivity_status,
            "note": self.note,
        }


@dataclass
class HighResDemSource:
    """A candidate source for finer elevation around the exact plot."""
    name: str
    provider_org: str
    resolution_m: float | None
    vertical_datum: str
    coverage: str
    license: str
    access_note: str
    suitability_for_plot: str
    status: str = DEM_UNVERIFIED    # available | unavailable | commercial | unverified
    recommended: bool = False
    url_or_api: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider_org": self.provider_org,
            "resolution_m": self.resolution_m,
            "vertical_datum": self.vertical_datum,
            "coverage": self.coverage,
            "license": self.license,
            "access_note": self.access_note,
            "suitability_for_plot": self.suitability_for_plot,
            "status": self.status,
            "recommended": self.recommended,
            "url_or_api": self.url_or_api,
            "note": self.note,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def recommend_high_res_dem_sources(probe_results: dict[str, str] | None = None) -> list[HighResDemSource]:
    """Documented candidate matrix for sub-30 m / higher-res elevation around
    (31.05, 76.53).  Statuses: a probe result overrides; anything not probed
    stays ``unverified`` (never silently "available")."""
    probe = probe_results or {}
    srcs = [
        HighResDemSource(
            name="ALOS World 3D 30m (AW3D30)",
            provider_org="JAXA", resolution_m=30.0,
            vertical_datum="EGM96",
            coverage="global (30m)", license="JAXA free with terms",
            access_note="Public download; same class as GLO-30, NOT sub-30 m.",
            suitability_for_plot="cross-check only (similar res, different datum).",
            url_or_api="https://www.eorc.jaxa.jp/ALOS/en/aw3d30/",
            note="Documented characteristics; availability not live-probed.",
        ),
        HighResDemSource(
            name="ALOS PALSAR RTC (12.5 m)",
            provider_org="NASA Alaska Satellite Facility", resolution_m=12.5,
            vertical_datum="radar backscatter — NOT an elevation DEM",
            coverage="path-based, India covered", license="open (NASA/ASF)",
            access_note="Open via ASF Vertex; radar slope-corrected amplitude, "
                        "NOT a substitute for surveyed elevation.",
            suitability_for_plot="surface/texture/change detection only.",
            url_or_api="https://search.asf.alaska.edu/",
            note="Documented; availability + coverage for the plot to be "
                 "live-verified at acquisition time.",
        ),
        HighResDemSource(
            name="Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m)",
            provider_org="ISRO / NRSC Bhuvan", resolution_m=10.0,
            vertical_datum="EGM96 / regional MSL hybrid",
            coverage="India, sub-30 m", license="NRSC Data Policy, registration + approval",
            access_note="Via Bhuvan WMS / NRSC; the practical national sub-30 m "
                        "candidate. Approval/coverage for the exact plot must be "
                        "confirmed before use.",
            suitability_for_plot="closest public sub-30 m satellite DEM; still a "
                                 "DSM (roofs/vegetation), still needs field check.",
            url_or_api="https://bhuvan.nrsc.gov.in/",
            note="Documented; live probe of Bhuvan availability below.",
        ),
        HighResDemSource(
            name="TanDEM-X WorldDEM (12 m)",
            provider_org="DLR / Airbus", resolution_m=12.0,
            vertical_datum="WGS84 ellipsoid → EGM2008 product",
            coverage="global, 12 m", license="commercial (DLR proposal/data grant)",
            access_note="Submitted science proposals can get DLR DEM access; "
                        "commercial otherwise.",
            suitability_for_plot="good resolution but DSM + licensing cost; not "
                                 "needed if Cartosat-1 + survey proceed.",
            url_or_api="https://geoservice.dlr.de/web/datasets/tdem/",
            note="Status commercial unless a DLR grant is obtained.",
        ),
        HighResDemSource(
            name="Drone photogrammetry / GNSS-RTK survey",
            provider_org="local survey (to be commissioned)", resolution_m=0.1,
            vertical_datum="orthometric via GNSS-RTK + BM tie",
            coverage="plot + crossings + reach", license="paid survey",
            access_note="The authoritative resolution of plot grading, culvert "
                        "inverts, road/rail crowns, bank crest — what no "
                        "satellite DEM can produce.",
            suitability_for_plot="PRIMARY resolver of the plot-level elevation "
                                 "blocker (pair with the survey spec).",
            url_or_api="spec in this report",
            note="To be commissioned against this specification; measures come "
                 "only from the field.",
        ),
        HighResDemSource(
            name="National / state LiDAR (India)",
            provider_org="Govt programmes (e.g. National Geospatial Policy)",
            resolution_m=None,
            vertical_datum="varies (orthometric expected)",
            coverage="programme-dependent; Punjab availability unconfirmed",
            license="policy-dependent",
            access_note="No confirmed Punjab LiDAR tile for the plot — recorded "
                        "unverified, not assumed.",
            suitability_for_plot="would be ideal if available; verify before use.",
            url_or_api="",
            note="Explicitly unverified; do not assume coverage.",
        ),
    ]
    for s in srcs:
        if s.name in probe:
            s.status = probe[s.name]
        s.recommended = s.name == "Cartosat-1 (2.5 m) / Cartosat-1 DSM (~10 m)"
    return srcs


def _spec_from_ways(category: str, category_label: str, items: list[dict],
                    target: str, *, spacing_m: str, fields: list[str],
                    datum: str, acc: str, pts: str = "as mapped points") -> list[SurveyPointSpec]:
    out = []
    for item in items:
        out.append(SurveyPointSpec(
            category=category, category_label=category_label,
            target=target,
            source_osm_id=item.get("osm_id"), source_name=item.get("name"),
            derived_from="reconciled_osm",
            location_note=(f"At OSM feature geometry; {pts}."),
            points_required=pts, spacing_m=spacing_m,
            fields_to_measure=list(fields),
            vertical_datum_req=datum, accuracy_req=acc,
        ))
    return out


def _build_survey_point_specs(gather=None, terrain=None,
                              *, plot_lat: float, plot_lon: float) -> list[SurveyPointSpec]:
    raw = (gather.raw_items if gather else {}) or {}
    rec = getattr(gather, "channel_reconciliation", None) if gather else None
    main_ids = set(rec.main_stem_ids) if rec else set()
    spec: list[SurveyPointSpec] = []

    # 1. Plot grading — around the exact plot cell (flat at 30 m: grade must be
    #    resolved at sub-decimetric level to judge ponding at the building).
    spec.append(SurveyPointSpec(
        category=PLOT_GRADING, category_label="Plot / building grading",
        target=f"Ground elevation grid around plot ({plot_lat}, {plot_lon})",
        derived_from="plot_context",
        location_note="30 m GLO-30 shows 0.0° slope here; micro-grading "
                      "(ditches, bunds, yard fall) is unresolved and must be "
                      "field-measured.",
        points_required="minimum 5x5 grid at ≤5 m over the developable area; "
                        "finer (≤2 m) along any drainage fall",
        spacing_m="≤5 m (≤2 m at grading transitions)",
        fields_to_measure=["ground elevation", "yard fall direction",
                           "top of any internal bund/wall", "building corner "
                           "plinths if buildings exist"],
        vertical_datum_req="orthometric via GNSS-RTK (NTRIP or CORS), tied to a "
                           "temporary benchmark",
        accuracy_req="vertical ±0.02 m; horizontal ±0.05 m (RTK)",
    ))

    # 2. Plot boundary / parcel geometry.
    spec.append(SurveyPointSpec(
        category=PROPERTY_BOUNDARY, category_label="Plot boundary cadastre",
        target=f"Property boundary around ({plot_lat}, {plot_lon})",
        derived_from="plot_context",
        location_note="Current working geometry is a point only; survey must "
                      "supply the parcel polygon so 'inside the plot' DEM cells "
                      "become well-defined.",
        points_required="all boundary vertices + corners",
        spacing_m="vertices",
        fields_to_measure=["boundary coordinates", "boundary length",
                           "offset of building to boundary"],
        vertical_datum_req="n/a (horizontal cadastre)",
        accuracy_req="horizontal ±0.05 m",
    ))

    # 3. Main-stem channel bank — the nearest Sutlej bank (~0.129 km).
    main_ways = [i for i in raw.get("channel_centerline", [])
                 if i.get("osm_id") in main_ids] or \
        raw.get("channel_centerline", [])
    if main_ways:
        for w in main_ways:
            spec.append(SurveyPointSpec(
                category=CHANNEL_BANK, category_label="Sutlej bank (near plot)",
                target="Bank crest + bed near the mapped main-stem way",
                source_osm_id=w.get("osm_id"), source_name=w.get("name"),
                derived_from="reconciled_osm",
                location_note="Mapped main stem (OSM); the river here runs along "
                              "the bank line ~0.13 km from the plot — measure "
                              "bank crest, berm, bed, and water line during "
                              "the survey.",
                points_required="cross-sections at ≥3 stations within radius "
                                "including the nearest approach",
                spacing_m="profile points ≤10 m along each cross-section",
                fields_to_measure=["bank crest elevation", "toe/berm elevation",
                                   "bed elevation near bank", "water surface "
                                   "elevation on survey day", "bank height"],
                vertical_datum_req="orthometric (BM-tied); record EGM2008 "
                                   "contribution via GNSS geoid model",
                accuracy_req="vertical ±0.02 m at crest; ±0.05 m bed",
            ))
    else:
        spec.append(SurveyPointSpec(
            category=CHANNEL_BANK, category_label="Sutlej bank (near plot)",
            target="Nearest main-stem bank",
            derived_from="plot_context",
            location_note="No reconciled main-stem geometry available in this "
                          "run; still required — confirm bank line on site.",
            points_required="cross-sections at ≥3 stations near the plot",
            spacing_m="profile points ≤10 m",
            fields_to_measure=["bank crest", "bed", "water surface elevation"],
            vertical_datum_req="orthometric (BM-tied)",
            accuracy_req="vertical ±0.02 m",
        ))

    # 4. Canal / drain invert — 377207446 is the local canal (~0.56 km).
    drains = raw.get("channels_drains", []) or []
    for d in drains:
        spec.append(SurveyPointSpec(
            category=DRAINAGE_INVERT, category_label="Local canal/drain invert",
            target="Invert + berm of the local canal/drain",
            source_osm_id=d.get("osm_id"), source_name=d.get("name"),
            derived_from="reconciled_osm",
            location_note="Local channel carries/removes local drainage. Measure "
                          "invert (bottom of flow) elevation, berm/crest, bed "
                          "slope, and any blockage.",
            points_required="invert at ≤50 m intervals across the radius; "
                            "crest at least at ends",
            spacing_m="≤50 m along invert",
            fields_to_measure=["invert elevation", "crest/berm elevation",
                               "bed slope between stations", "wetted/perched "
                               "water level", "blockages"],
            vertical_datum_req="orthometric (BM-tied)",
            accuracy_req="vertical ±0.02 m invert, ±0.05 m berm",
        ))

    # 5. Culvert / bridge crossings — 254573869, 254573867.
    crossings = raw.get("bridges_culverts", []) or []
    for c in crossings:
        spec.append(SurveyPointSpec(
            category=CULVERT_CROSSING, category_label="Culvert/bridge crossing",
            target="Opening geometry + inverts of the crossing",
            source_osm_id=c.get("osm_id"), source_name=c.get("name"),
            derived_from="reconciled_osm",
            location_note="Crossing is on the mapped network; its actual opening "
                          "size and invert/soffit control local conveyance and "
                          "must be field-measured — never inferred from OSM.",
            points_required="each opening: invert(L) + invert(R) + soffit + "
                            "approaches + any second barrel",
            spacing_m="per opening",
            fields_to_measure=["culvert invert elevation (up/down)", "soffit "
                               "elevation", "opening width × height", "road/rail "
                               "crown above", "debris/silt level"],
            vertical_datum_req="orthometric; culvert invert is the critical "
                               "hydraulic control — highest precision",
            accuracy_req="vertical ±0.01 m at inverts",
        ))

    # 6. Rail / road barriers — 680091133, 919730631.
    barriers = raw.get("embankments_road_rail", []) or []
    for b in barriers:
        spec.append(SurveyPointSpec(
            category=BARRIER_CROWN, category_label="Rail/road barrier crown",
            target="Top-of-rail / carriageway crown of the barrier",
            source_osm_id=b.get("osm_id"), source_name=b.get("name"),
            derived_from="reconciled_osm",
            location_note="Barrier profile perpendicular to the feature, at the "
                          "crossing points and at the lowest approach so the "
                          "barrier's blocking/overtopping behaviour is known.",
            points_required="crown profile at ≥2 stations each, incl. at any "
                            "crossing",
            spacing_m="≤10 m along profile",
            fields_to_measure=["top-of-rail/crown elevation", "adjoining ground "
                               "on each side", "any gap/culvert through the "
                               "barrier"],
            vertical_datum_req="orthometric (BM-tied)",
            accuracy_req="vertical ±0.02 m",
        ))

    # 7. DEM low-point field checks — from terrain phase (8 points, e.g.
    #    31.070556,76.548056 at −0.65 m).
    lows = (terrain.low_points if terrain else []) or []
    for lp in lows[:8]:
        spec.append(SurveyPointSpec(
            category=LOW_POINT_CHECK, category_label="DEM low-point field check",
            target=f"Depression check at ({lp.lat:.6f}, {lp.lon:.6f})",
            derived_from="dem_low_point",
            location_note="GLO-30 indicates a local low here (a DEM depression, "
                          "NOT connectivity). Field-check whether it is a "
                          "genuine basin/pond, and its bottom elevation and "
                          "drainage outlet.",
            points_required="bottom of depression + rim + any outlet",
            spacing_m="profile across the low",
            fields_to_measure=["bottom elevation", "rim elevation", "seasonal "
                               "water/vegetation", "outlet/drain connection"],
            vertical_datum_req="orthometric (BM-tied)",
            accuracy_req="vertical ±0.02 m",
        ))

    # 8. Benchmarks / datum control.
    spec.append(SurveyPointSpec(
        category=BENCHMARK, category_label="Benchmark & datum control",
        target="Temporary BM(s) + tie to authoritative vertical datum",
        derived_from="plot_context",
        location_note="Establish ≥2 stable temporary benchmarks (curb/monument) "
                      "and connect them to a Survey of India benchmark / CWC or "
                      "BBMB datum. Record the EGM96/EGM2008/MSL offsets so every "
                      "downstream comparison shares one datum.",
        points_required="≥2 TBMs + ≥1 datum tie",
        spacing_m="n/a",
        fields_to_measure=["TBM coordinates", "TBM elevation", "datum name & "
                           "reference epoch", "offsets to EGM2008"],
        vertical_datum_req="name the official datum + geoid model + epoch",
        accuracy_req="level loop closing ≤±0.01 m",
    ))

    # 9. Water level at survey time (baseline state).
    spec.append(SurveyPointSpec(
        category=WATER_LEVEL, category_label="Water level (baseline)",
        target=f"Surface water level in channel/canal ({plot_lat}, {plot_lon})",
        derived_from="plot_context",
        location_note="One observation of the water surface on survey day in "
                      "the nearby channel (identifies freeboard/headwater for "
                      "the future solver; NOT a flood depth).",
        points_required="1 per waterbody near plot",
        spacing_m="n/a",
        fields_to_measure=["water surface elevation", "date/time (UTC)",
                           "flow state (dry/low/bankfull)"],
        vertical_datum_req="orthometric (BM-tied)",
        accuracy_req="vertical ±0.02 m",
    ))

    return spec


def record_survey_points(points: list[SurveyPointSubmission],
                         *, connectivity_status: str) -> SurveyVerificationResult:
    """Integrate claims ONLY when verified; refuse everything else.  Accepted
    points never change connectivity by themselves."""
    res = SurveyVerificationResult(connectivity_status=connectivity_status)
    for p in points:
        d = {
            "category": p.category, "target": p.target,
            "value_m": p.value_m,
            "provenance": p.provenance, "vertical_datum": p.vertical_datum,
            "horizontal_system": p.horizontal_system, "accuracy_m": p.accuracy_m,
            "verified": p.verified, "source_osm_id": p.source_osm_id,
        }
        if p.is_integrable():
            res.accepted.append(d)
        else:
            d["reason"] = (
                "refused: missing verified provenance/datum/accuracy or "
                "unverified claim" if not p.verified
                else "refused: incomplete required metadata")
            res.refused.append(d)
    return res


@dataclass
class SurveySpecResult:
    plot_lat: float
    plot_lon: float
    generated_at: str
    high_res_dem_sources: list[HighResDemSource] = field(default_factory=list)
    survey_points: list[SurveyPointSpec] = field(default_factory=list)
    connectivity_status: str = ""
    plot_level_credible: bool = False
    surveyed_elevations_integrated: int = 0
    survey_gate: str = SURVEY_GATE_STATEMENT
    high_res_gate: str = HIGH_RES_DEM_GATE_STATEMENT
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plot": [self.plot_lat, self.plot_lon],
            "generated_at": self.generated_at,
            "connectivity_status": self.connectivity_status,
            "plot_level_credible": self.plot_level_credible,
            "surveyed_elevations_integrated": self.surveyed_elevations_integrated,
            "survey_gate": self.survey_gate,
            "high_res_gate": self.high_res_gate,
            "high_res_dem_sources": [s.to_dict() for s in self.high_res_dem_sources],
            "survey_points": [s.to_dict() for s in self.survey_points],
            "caveats": self.caveats,
        }


def produce_survey_spec(
    gather=None,
    terrain=None,
    *,
    plot_lat: float,
    plot_lon: float,
    probe_results: dict[str, str] | None = None,
) -> SurveySpecResult:
    """Build the field-ready survey spec + high-res DEM source matrix for the
    exact plot, from the reconciled local features and DEM low points only.

    Produces requirements — never measurements.  ``surveyed_elevations_integrated``
    is 0 here (integration is a later, verification-gated step).
    """
    from .connectivity import UNRESOLVED_MESSAGE

    sources = recommend_high_res_dem_sources(probe_results)
    points = _build_survey_point_specs(
        gather, terrain, plot_lat=plot_lat, plot_lon=plot_lon)
    result = SurveySpecResult(
        plot_lat=plot_lat, plot_lon=plot_lon, generated_at=_now(),
        high_res_dem_sources=sources, survey_points=points,
        connectivity_status=UNRESOLVED_MESSAGE,
        plot_level_credible=False,
        surveyed_elevations_integrated=0,
        caveats=[
            "This document specifies WHAT and HOW to measure; every "
            "measured_value is None until real field data is delivered and "
            "verified.",
            "No satellite DEM (any resolution) is a substitute for the "
            "invert/soffit/crown/benchmark field measurements at a house-scale "
            "problem.",
            "Cartosat-1/Bhuvan is the leading public sub-30 m candidate; its "
            "approval, coverage and licences for the exact tile must be "
            "confirmed before acquisition. Drone/GNSS-RTK survey is the "
            "authoritative resolver of plot-level grading and crossing inverts.",
            "Datum discipline: GLO-30 is EGM2008, SRTM/AW3D30 are EGM96, "
            "Cartosat-1 is EGM96/regional MSL hybrid, survey will be orthometric "
            "via GNSS-RTK — never fuse; always carry the datum + offset per "
            "observation.",
            "Hydraulic connectivity remains UNRESOLVED at 30 m and stays so "
            "until the fine-scale evidence actually resolves it; the flood "
            "solver is NOT run in this phase.",
        ],
    )
    return result
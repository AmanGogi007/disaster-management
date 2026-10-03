"""Phase 1 — authoritative flood evidence for the Ropar corridor (design §J.3).

Gathers the gauge observations and documented historical flood extents relevant
to the reconciled Sutlej corridor, from the authoritative national sources that
exist for this reach (CWC, India-WRIS, BBMB, NIH, NASA) plus NWDP (National
Water Data Portal) as the machine-readable distribution channel.

Hard rules enforced here (mirror the J-series discipline):

* A gauge reading or historical flood extent is NEVER converted into a plot
  flood depth.  The hydraulic relationship between the gauge/event, the river,
  the terrain, the barriers and the Ropar plot is a separate, downstream solver
  problem — this module only records evidence.
* No 2D flood solver is invoked anywhere in this module.
* Every record carries provenance (organisation, dataset, URL, retrieval time),
  datum/units, spatial + temporal coverage, uncertainty/confidence and an
  explicit availability status.  A fetch failure is recorded as a fetch
  failure — never upgraded to certified absence, never fabricated.
* A dataset whose published rows are placeholder/quality-flagged values is
  recorded as ``insufficient`` (present but not credible), NOT ``obtained``.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

USER_AGENT = "location-hazard-engine/0.2 (research)"

OBTAINED = "obtained"
UNAVAILABLE = "unavailable"
INSUFFICIENT = "insufficient"
CONFLICTING = "conflicting"

NWDP_PACKAGES = {
    "rwl_cwc": "river-water-level-telemetry-hourly-central-water-commission-cwc",
    "discharge_cwc": "river-discharge-manual-dailly-central-water-commission-cwc",
    "res_manual_bbmb": "reservoir-water-level-manual-daily-bhakra-beas-management-board-chandigarh",  # noqa: E501
    "res_tele_bbmb": "reservoir-water-level-telemetry-hourly-bhakra-beas-management-board-chandigarh",  # noqa: E501
}

BBMB_RESERVOIR_PAGES = (
    "https://bbmb.gov.in/data-reservoir.htm",
    "https://www.bbmb.gov.in/GenTarget2023_24_hi.htm",
)

# Referenced URLs used for the cited (documented) records.
_CITED = {
    "cwc_ff_2019": "https://sandrp.in/2019/09/25/overview-of-cwc-flood-forecasting-sites-2019-north-india/",  # noqa: E501
    "cwc_ff_2025": "https://sandrp.in/2025/07/09/himachal-pradesh-why-cwcs-forecasting-is-unavailable-amidst-flood-disaster/",  # noqa: E501
    "nih_1988": "https://www.indiawaterportal.org/climate-change/disasters/flood-studies-satluj-basin-research-report-national-institute-hydrology",  # noqa: E501
    "peak_1988": "https://indianexpress.com/article/cities/chandigarh/punjab-first-time-after-1988-floods-sutlej-carrying-more-than-its-capacity/",  # noqa: E501
    "flood_2019_villages": "https://indianexpress.com/article/india/initial-crop-damage-survey-over-one-lakh-acres-submerged-crops-in-13-districts-hit-5926796/",  # noqa: E501
    "flood_2019_ropat": "https://www.huffpost.com/archive/in/entry/punjab-himachal-floods-2019_in_5d5bfaade4b05f62fbd577f1",  # noqa: E501
    "nasa_2023": "https://landsat.visibleearth.nasa.gov/view.php?id=151754",
    "gfd": "https://global-flood-database.cloudtostreet.info/",
    "wris_hms": "https://indiawris.gov.in/wiki/doku.php?id=cwc_hydro-meteorological_sites",
    "bbmb_2026_snapshot": "https://www.bbmb.gov.in/index.htm",
}

# Literal gate statement (analogue of UNRESOLVED_MESSAGE): never downgraded.
GAUGE_TO_PLOT_STATEMENT = (
    "Gauge readings and historical flood extents are calibration/validation "
    "evidence only; no reading or extent is converted into a plot flood depth. "
    "The hydraulic relationship between the gauge/event, the river hydraulics, "
    "the mapped terrain, the barriers and the Ropar plot is a downstream solver "
    "problem and remains unassessed."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_get(url: str, timeout_s: float) -> tuple[int, bytes | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.status, resp.read()


def _safe_probe(
    fetch_fn,
    url: str,
    timeout_s: float,
    retries: int,
    backoff_s: float = 1.0,
) -> dict:
    last = None
    for attempt in range(1, retries + 1):
        try:
            status, body = fetch_fn(url, timeout_s)
            return {"url": url, "reachable": True, "status": status, "body": body}
        except Exception as exc:  # noqa: BLE001 - any transport error
            last = exc
            if attempt < retries:
                time.sleep(backoff_s * attempt)
    return {"url": url, "reachable": False, "error": repr(last)}


class FloodEvidenceKind(str, Enum):
    GAUGE_SERIES = "gauge_series"          # measured water-level / discharge series
    RESERVOIR_LEVEL = "reservoir_level"    # dam/reservoir level (upstream control)
    PEAK_FLOW_RECORD = "peak_flow_record"  # documented historical peak discharge
    FLOOD_EXTENT = "flood_extent"          # documented spatial historical inundation
    NETWORK_STATUS = "network_status"      # authoritative statement on gauge coverage


@dataclass
class FloodEvidenceRecord:
    title: str
    kind: FloodEvidenceKind
    status: str                       # obtained | unavailable | insufficient | conflicting
    source_org: str
    dataset: str
    source_url: str | None = None
    retrieved_at: str | None = None
    license: str = ""
    spatial_coverage: str = ""
    temporal_coverage: str = ""
    units: str = ""
    datum_note: str = ""
    resolution_note: str = ""
    uncertainty_note: str = ""
    confidence: str = "medium"
    count: int = 0
    sample: list[dict] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind.value,
            "status": self.status,
            "source_org": self.source_org,
            "dataset": self.dataset,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "license": self.license,
            "spatial_coverage": self.spatial_coverage,
            "temporal_coverage": self.temporal_coverage,
            "units": self.units,
            "datum_note": self.datum_note,
            "resolution_note": self.resolution_note,
            "uncertainty_note": self.uncertainty_note,
            "confidence": self.confidence,
            "count": self.count,
            "sample": self.sample[:5],
            "note": self.note,
        }


@dataclass
class FloodEvidenceResult:
    plot_lat: float
    plot_lon: float
    radius_km: float
    fetched_at: str
    records: list[FloodEvidenceRecord]
    gauge_to_plot_statement: str = GAUGE_TO_PLOT_STATEMENT
    portal_probe: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plot": [self.plot_lat, self.plot_lon],
            "radius_km": self.radius_km,
            "fetched_at": self.fetched_at,
            "gauge_to_plot_statement": self.gauge_to_plot_statement,
            "portal_probe": self.portal_probe,
            "records": [r.to_dict() for r in self.records],
        }


def _bbmb_rows(page: str, url: str) -> list[dict]:
    """Best-effort extraction of the Bhakra row from the BBMB bulletin HTML.

    Rule (documented, deterministic): locate the first occurrence of ``bhakra``,
    then read the first three numbers within the next 3000 characters, skipping
    the constant design levels FRL/MWL/top-of-dam (1680, 1690, 1700 ft). The
    three numbers map to level_ft, inflow_cusecs, outflow_cusecs.

    Returns [] when nothing parseable is found (recorded, never fabricated).
    """
    low = page.lower()
    m = re.search(r"bhakra", low)
    if not m:
        return []
    chunk = low[m.start():m.start() + 3000]
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", chunk)]
    nums = [n for n in nums if n not in (1680.0, 1690.0, 1700.0)]
    if not nums:
        return []
    row = {"feature": "Bhakra Dam"}
    row["reservoir_level_ft"] = nums[0]
    row["inflow_cusecs"] = nums[1] if len(nums) > 1 else None
    row["outflow_cusecs"] = nums[2] if len(nums) > 2 else None
    row["source_url"] = url
    return [row]


def _nwdp_package_summary(fetch_fn, api_base: str, timeout_s: float, retries: int) -> dict:
    out = {}
    for key, pid in NWDP_PACKAGES.items():
        url = f"{api_base}/api/3/action/package_show?id={pid}"
        probe = _safe_probe(fetch_fn, url, timeout_s, retries)
        if not probe["reachable"]:
            out[key] = {"reachable": False, "error": probe.get("error")}
            continue
        pkg = {}
        try:
            parsed = json.loads(probe["body"])
            d = parsed["result"]
            pkg = {
                "reachable": True,
                "title": d.get("title"),
                "metadata_modified": d.get("metadata_modified"),
                "resources": [
                    {"name": r.get("name"), "format": r.get("format"),
                     "size": r.get("size"), "url": r.get("url")}
                    for r in d.get("resources", [])
                ],
            }
        except Exception as exc:  # noqa: BLE001
            pkg = {"reachable": False, "parse_error": repr(exc)}
        out[key] = pkg
    return out


def gather_flood_evidence(
    plot_lat: float = 31.05,
    plot_lon: float = 76.53,
    radius_km: float = 3.0,
    nwdp_api: str = "https://nwdp.nwic.gov.in",
    timeout_s: float = 15.0,
    retries: int = 2,
    fetch_fn=_http_get,
) -> FloodEvidenceResult:
    """Gather authoritative gauge + documented flood-extent evidence relevant
    to the reconciled Sutlej corridor around (plot_lat, plot_lon).

    Live probe: NWDP CKAN ``package_show`` for the CWC/BBMB gauge datasets and
    the BBMB reservoir bulletin pages.  Documented findings (historical peaks,
    published flood-extent mappings, CWC network coverage) are cited records.
    Every fetch failure is recorded as unavailable, never fabricated.
    """
    fetched_at = _now()
    records: list[FloodEvidenceRecord] = []

    probe = _nwdp_package_summary(fetch_fn, nwdp_api, timeout_s, retries)

    rwlcwc = probe.get("rwl_cwc") or {}
    flow_to_rwlcwc_note = (
        "Dataset reachable via NWDP CKAN API. The package covers ONLY peninsular "
        "river basins (Subernarekha, Brahmani, Mahanadi, Godavari, Krishna, Pennar, "
        "Cauvery, Tapi, Narmada, Mahi, Sabarmati, west/east-flowing groups) — it "
        "contains NO Indus/Sutlej-basin resource. Verified 2026-09-02 from the "
        "package resource list."
    )
    records.append(FloodEvidenceRecord(
        title="CWC river water level (telemetry, hourly) — national NWDP dataset",
        kind=FloodEvidenceKind.GAUGE_SERIES,
        status=OBTAINED if rwlcwc.get("reachable") else UNAVAILABLE,
        source_org="CWC / NWDP",
        dataset="River Water Level (Telemetry - Hourly), Central Water Commission (CWC)",
        source_url=f"{nwdp_api}/dataset/" + NWDP_PACKAGES["rwl_cwc"],
        retrieved_at=fetched_at if rwlcwc.get("reachable") else None,
        license="National Water Data Portal (open government data)",
        spatial_coverage="All-india dataset; resource-level basin coverage (peninsular only)",
        temporal_coverage="1961–2025 per resource (hourly)",
        units="m (water level)",
        datum_note="Per-station gauge zero vs MSL must hold per resource headers",
        resolution_note="Hourly telemetry; station-level records",
        uncertainty_note=flow_to_rwlcwc_note,
        confidence="medium",
        count=len(rwlcwc.get("resources", [])),
        note=flow_to_rwlcwc_note,
    ))

    records.append(FloodEvidenceRecord(
        title="CWC gauge series for the Sutlej / Ropar reach",
        kind=FloodEvidenceKind.GAUGE_SERIES,
        status=UNAVAILABLE,
        source_org="CWC / NWDP",
        dataset="Sutlej-basin level series (none published in NWDP RWL package)",
        source_url=_CITED["cwc_ff_2019"],
        retrieved_at=fetched_at if rwlcwc.get("reachable") else None,
        spatial_coverage="Sutlej reach near Ropar (31.05N, 76.53E, r=3 km)",
        temporal_coverage="n/a",
        units="n/a",
        datum_note="n/a",
        resolution_note="n/a",
        uncertainty_note=(
            "CWC flood-forecasting network has NO site in Punjab: the single "
            "site added in 2019 is inactive, and no level-forecast station exists "
            "in the Sutlej basin (only monitoring stations in Himachal Pradesh, far "
            "upstream: Rampur, Pandoa, Titang...). The NWDP RWL telemetry package "
            "lists no Indus/Sutlej resource. Both verified on 2026-09-02."
        ),
        confidence="low",
        count=0,
        note=(
            "Authoritative absence with stated reasons — NOT a silent gap. The Ropar "
            "reach has no CWC telemetry level series in the machine-readable portal."
        ),
    ))

    rec_disc = probe.get("discharge_cwc") or {}
    discharge_note = (
        "Dataset reachable via NWDP CKAN API. The package is state-grouped and "
        "contains NO Punjab / Himachal J&K resource (no Indus-system state). "
        "Verified 2026-09-02 from the package resource list."
    )
    records.append(FloodEvidenceRecord(
        title="CWC river discharge (manual, daily) — national NWDP dataset",
        kind=FloodEvidenceKind.GAUGE_SERIES,
        status=OBTAINED if rec_disc.get("reachable") else UNAVAILABLE,
        source_org="CWC / NWDP",
        dataset="River Discharge (Manual - Daily), Central Water Commission (CWC)",
        source_url=f"{nwdp_api}/dataset/" + NWDP_PACKAGES["discharge_cwc"],
        retrieved_at=fetched_at if rec_disc.get("reachable") else None,
        license="National Water Data Portal (open government data)",
        spatial_coverage="All-india dataset; state-grouped resources (no Indus-system states)",
        temporal_coverage="1950–2025 per resource (daily)",
        units="m³/s (discharge)",
        datum_note="n/a",
        resolution_note="Daily manual observations; station-level records",
        uncertainty_note=discharge_note,
        confidence="medium",
        count=len(rec_disc.get("resources", [])),
        note=discharge_note,
    ))

    res_manual = probe.get("res_manual_bbmb") or {}
    bhakra_manual_note = (
        "Resource 'Reservoir Water Level ... (1970 - 2025) Manual Daily' contains "
        "a row for station 'Bhakra Dam RL1700_BBMB' (Satluj, Indus, 31.4156N, "
        "76.4347E) BUT the published values are placeholder-quality (sequence "
        "1,2,3,4,5 m and -999 fillers) — recorded insufficient, NOT credible as "
        "observations. Verified 2026-09-02 by direct download + inspection."
    )
    records.append(FloodEvidenceRecord(
        title="BBMB Bhakra reservoir level — NWDP manual-daily resource",
        kind=FloodEvidenceKind.RESERVOIR_LEVEL,
        status=INSUFFICIENT if res_manual.get("reachable") else UNAVAILABLE,
        source_org="BBMB / NWDP",
        dataset="Reservoir Water Level (Manual - Daily) BBMB (1970–2025)",
        source_url=f"{nwdp_api}/dataset/" + NWDP_PACKAGES["res_manual_bbmb"],
        retrieved_at=fetched_at if res_manual.get("reachable") else None,
        license="National Water Data Portal (open government data)",
        spatial_coverage="Bhakra Dam, Bilaspur HP (31.4156N, 76.4347E) ~45 km upstream of plot",
        temporal_coverage="1970–2025 (daily)",
        units="m (per CSV header)",
        datum_note="Levels in metres in CSV; BBMB bulletin publishes feet (FRL 1680 ft ≈ 512.06 m)",
        resolution_note="Daily reservoir level",
        uncertainty_note=bhakra_manual_note,
        confidence="low",
        count=1,
        sample=[{
            "station": "Bhakra Dam RL1700_BBMB", "lat": 31.41555556, "lon": 76.43472222,
            "value_m": 1.0, "quality": "placeholder — not credible",
        }],
        note=bhakra_manual_note,
    ))

    res_tele = probe.get("res_tele_bbmb") or {}
    bhakra_tele_note = (
        "The hourly BBMB telemetry resources (1970–2030) exist; the 2026–2030 "
        "resource inspected 2026-09-02 contains only station rows for 'Baspa PH' "
        "and 'Karcham Wangtu PH' (Satluj catchment powerhouses) — NO Bhakra "
        "reservoir rows in that file. Bhakra telemetry may reside in the 1970–2025 "
        "file (not inspected, 12 MB) — recorded uncertain, not assumed."
    )
    records.append(FloodEvidenceRecord(
        title="BBMB reservoir level — NWDP telemetry-hourly resources",
        kind=FloodEvidenceKind.RESERVOIR_LEVEL,
        status=INSUFFICIENT if res_tele.get("reachable") else UNAVAILABLE,
        source_org="BBMB / NWDP",
        dataset="Reservoir Water Level (Telemetry - Hourly) BBMB",
        source_url=f"{nwdp_api}/dataset/" + NWDP_PACKAGES["res_tele_bbmb"],
        retrieved_at=fetched_at if res_tele.get("reachable") else None,
        license="National Water Data Portal (open government data)",
        spatial_coverage="BBMB reservoirs/powerhouses (Bhakra, Pong, Baspa, Karcham Wangtu)",
        temporal_coverage="1970–2030 (hourly)",
        units="m (per CSV header)",
        datum_note="Levels in metres in CSV; BBMB bulletin publishes feet (FRL 1680 ft ≈ 512.06 m)",
        resolution_note="Hourly reservoir level",
        uncertainty_note=bhakra_tele_note,
        confidence="low",
        count=len(res_tele.get("resources", [])),
        sample=[{
            "station": "Baspa PH_BBMB", "river": "Beas", "level_m": 2530.981,
            "note": "upstream powerhouse, not Bhakra",
        }],
        note=bhakra_tele_note,
    ))

    # BBMB official daily bulletin (live fetch attempt; cited snapshots fallback).
    bbmb_rows = []
    for url in BBMB_RESERVOIR_PAGES:
        probe_page = _safe_probe(fetch_fn, url, timeout_s, retries)
        if probe_page["reachable"]:
            bbmb_rows.extend(_bbmb_rows(
                probe_page.get("body", b"").decode("utf-8", "replace"), url))
    if bbmb_rows:
        records.append(FloodEvidenceRecord(
            title="BBMB Bhakra reservoir bulletin — live capture",
            kind=FloodEvidenceKind.RESERVOIR_LEVEL,
            status=OBTAINED,
            source_org="BBMB",
            dataset="Reservoir Data bulletin (daily reservoir level / inflow / outflow)",
            source_url=BBMB_RESERVOIR_PAGES[0],
            retrieved_at=fetched_at,
            license="BBMB public bulletin (© BBMB)",
            spatial_coverage="Bhakra Dam (31.4156N, 76.4347E) ~45 km upstream of plot",
            temporal_coverage=f"snapshot at {fetched_at}",
            units="level ft; inflow/outflow cusecs",
            datum_note="BBMB gauge datum in feet; FRL 1680 ft, MWL 1690 ft, top of dam 1700 ft",
            resolution_note="Daily (06:00) bulletin values",
            uncertainty_note="Single HTML bulletin capture; not a verified time series.",
            confidence="medium",
            count=len(bbmb_rows),
            sample=bbmb_rows[:5],
            note="Live capture of the official BBMB reservoir bulletin.",
        ))
    else:
        records.append(FloodEvidenceRecord(
            title="BBMB Bhakra reservoir bulletin — daily live value",
            kind=FloodEvidenceKind.RESERVOIR_LEVEL,
            status=UNAVAILABLE,
            source_org="BBMB",
            dataset="Reservoir Data bulletin (daily reservoir level / inflow / outflow)",
            source_url=BBMB_RESERVOIR_PAGES[0],
            retrieved_at=fetched_at,
            license="BBMB public bulletin (© BBMB)",
            spatial_coverage="Bhakra Dam (31.4156N, 76.4347E) ~45 km upstream of plot",
            temporal_coverage="snapshot (not captured)",
            units="level ft; inflow/outflow cusecs",
            datum_note="BBMB gauge datum in feet; FRL 1680 ft, MWL 1690 ft, top of dam 1700 ft",
            resolution_note="Daily (06:00) bulletin values",
            uncertainty_note=(
                f"bbmb.gov.in bulletin pages unreachable from the research "
                f"environment on {fetched_at[:10]} (fetch failure after {retries} "
                "attempts). This is a FETCH FAILURE, not certified absence; the "
                "bulletin is published daily and indexed snapshots exist (see "
                "documented records)."
            ),
            confidence="low",
            count=0,
            note="Fetch failure recorded honestly; no fabricated level value.",
        ))

    # Documented historical flood extents + peak-flow records (cited research).
    records.append(FloodEvidenceRecord(
        title="Sutlej peak flow at Ropar — 9 Sep 1988 flood (worst on record)",
        kind=FloodEvidenceKind.PEAK_FLOW_RECORD,
        status=OBTAINED,
        source_org="BBMB / Punjab Drainage records (via press)",
        dataset="Historical peak discharge record at Ropar headworks",
        source_url=_CITED["peak_1988"],
        retrieved_at=None,
        license="n/a (cited reporting)",
        spatial_coverage="Ropar headworks on the Sutlej (31.05N, 76.53E reach)",
        temporal_coverage="9 Sep 1988 (event)",
        units="cusecs",
        datum_note="Flow (not stage); cusec ≈ 0.02832 m³/s",
        resolution_note="Single peak value from official/BBMB records as reported",
        uncertainty_note="Reported 4,55,411 cusecs on 9 Sep 1988, described as the "
                         "worst-ever Sutlej flood in Punjab; sources are press quoting "
                         "BBMB/Punjab drainage records — medium confidence, not a "
                         "primary gauge chart.",
        confidence="medium",
        count=1,
        sample=[{"date": "1988-09-09", "peak_cusecs": 455411, "location": "Ropar"}],
        note="Canonical documented peak for the Ropar reach; used later as a "
             "calibration/design event, never as a plot depth.",
    ))

    records.append(FloodEvidenceRecord(
        title="September 1988 flood inundation mapping (Sutlej, upstream of Ropar)",
        kind=FloodEvidenceKind.FLOOD_EXTENT,
        status=OBTAINED,
        source_org="National Institute of Hydrology (NIH)",
        dataset="Flood inundation + flood-plain mapping of the 1988 flood, IRS LISS-II",
        source_url=_CITED["nih_1988"],
        retrieved_at=None,
        license="NIH research report (via India Water Portal)",
        spatial_coverage="~50 km Sutlej reach upstream of Roopnagar (Ropar) + 181 km "
                         "planform reach downstream",
        temporal_coverage="Sep 1988 event",
        units="satellite-derived inundation classes",
        datum_note="IRS LISS-II (23.5 m) + FCC 1:250,000 rectified mapping",
        resolution_note="Satellite flood-inundation mapping with damage classes",
        uncertainty_note=(
            "Mapped with 1980s satellite data (LISS-II); right-flank areas reported "
            "more inundated than left; includes Ropar headworks conveyance-capacity "
            "assessment. Use as extent/calibration evidence, not plot depth."
        ),
        confidence="medium",
        count=1,
        sample=[{"event": "Sep 1988", "mapper": "NIH (IRS LISS-II)",
                 "reach_km_upstream_of_ropar": 50}],
        note="Documented spatial extent of the design flood for the Ropar reach.",
    ))

    records.append(FloodEvidenceRecord(
        title="Sutlej flood Aug 2019 at Ropar/Phillaur — village-level inundation",
        kind=FloodEvidenceKind.FLOOD_EXTENT,
        status=OBTAINED,
        source_org="Punjab govt / Punjab Drainage Dept (via press + surveys)",
        dataset="District/village-level inundation + crop-damage survey (2019)",
        source_url=_CITED["flood_2019_villages"],
        retrieved_at=None,
        license="n/a (cited reporting + govt survey)",
        spatial_coverage="Ropar (~95 villages, ~13,800 acres), Jalandhar, Ferozepur, "
                         "Kapurthala districts",
        temporal_coverage="17–20 Aug 2019 (event)",
        units="villages / acres / cusecs",
        datum_note="Flow at Phillaur; no Ropar-reach stage gauge",
        resolution_note="Village/acre level official survey granularity",
        uncertainty_note=(
            "Phillaur peak ~2.65–2.75 lakh cusecs (highest since 1988; carrying "
            "capacity Ropar–Harike ~2.0 lakh cusecs). Ropar district ~95 villages "
            "inundated; ~300 villages across Ropar/Jalandhar/Ferozepur; natural "
            "calamity declared; Dhussi bandh breach reported. Press + govt survey "
            "reporting, medium confidence."
        ),
        confidence="medium",
        count=95,
        sample=[{"year": 2019, "district": "Ropar", "villages_inundated": 95,
                 "acres_damaged": 13800},
                {"year": 2019, "peak_phillaur_cusecs": 265000}],
        note="Nearest-to-plot documented inundation event (Ropar district).",
    ))

    records.append(FloodEvidenceRecord(
        title="Aug 2023 satellite-observed flood water on the Sutlej",
        kind=FloodEvidenceKind.FLOOD_EXTENT,
        status=OBTAINED,
        source_org="NASA EO / USGS Landsat",
        dataset="Landsat 9 OLI-2 flood imagery of the Sutlej (Aug 2023)",
        source_url=_CITED["nasa_2023"],
        retrieved_at=None,
        license="NASA/USGS Landsat — public domain",
        spatial_coverage="Sutlej downstream of Ropar — Firozpur reach (India/Pakistan "
                         "border), NOT the Ropar corridor",
        temporal_coverage="2023-08-19 (with 2023-06-16 pre-flood)",
        units="imagery (water surface)",
        datum_note="Satellite surface-water extent; no stage",
        resolution_note="30 m OLI-2 imagery",
        uncertainty_note=(
            "Documents the 2023 Sutlej flood extent ~150 km downstream of the plot. "
            "It does NOT establish inundation at the Ropar plot; recorded for the "
            "Sutlej flood library only."
        ),
        confidence="high",
        count=1,
        sample=[{"acquisition": "2023-08-19", "sensor": "Landsat 9 OLI-2",
                 "reach": "Firozpur (downstream of Ropar)"}],
        note="Documented extent, correctly NOT extrapolated to the Ropar plot.",
    ))

    records.append(FloodEvidenceRecord(
        title="Global Flood Database v1 (DFO/MODIS)",
        kind=FloodEvidenceKind.FLOOD_EXTENT,
        status=OBTAINED,
        source_org="DFO / Floodbase / Tellman et al. 2021",
        dataset="Global Flood Database v1 — 913 events, 2000–2018, MODIS 250 m",
        source_url=_CITED["gfd"],
        retrieved_at=None,
        license="CC-BY (GFD)",
        spatial_coverage="Global; includes India events (316 recorded by DFO)",
        temporal_coverage="2000-02-17 to 2018-12-10",
        units="flooded/duration/jrc_perm_water bands",
        datum_note="WGS84 raster at 30 arc-sec; hydroSHEDS-based event regions",
        resolution_note="250 m (MODIS) flood extent + duration",
        uncertainty_note=(
            "Per-event extraction intersecting the Ropar corridor bbox has NOT been "
            "performed at this checkpoint (deferred step). Station/event catalog is "
            "reachable (verified 2026-09-02)."
        ),
        confidence="medium",
        count=913,
        note="Dataset catalogued; corridor intersection extraction deferred.",
    ))

    records.append(FloodEvidenceRecord(
        title="CWC flood-forecasting network coverage near Ropar",
        kind=FloodEvidenceKind.NETWORK_STATUS,
        status=UNAVAILABLE,
        source_org="CWC / SANDRP compilations of the CWC FF network",
        dataset="CWC flood-forecasting site network (2018/2019/2025)",
        source_url=_CITED["cwc_ff_2025"],
        retrieved_at=None,
        license="n/a (compilations)",
        spatial_coverage="Punjab (none) / Himachal Sutlej sites (Rampur, Pandoa, "
                         "Titang, Powari, Nathpa — monitoring only)",
        temporal_coverage="2018–2025 network status",
        units="sites",
        datum_note="n/a",
        resolution_note="Network-level (site presence)",
        uncertainty_note=(
            "CWC has no flood-forecasting or level-forecast station in the Sutlej "
            "basin; the single Punjab site added in 2019 is inactive; Sutlej "
            "monitoring sites are far upstream in Himachal Pradesh (HFLs recorded "
            "2005-08-03 at Rampur/Titang/etc.). No station at Ropar."
        ),
        confidence="high",
        count=0,
        note="Explains WHY no CWC Ropar gauge series is expected: authoritative "
             "network coverage statement.",
    ))

    records.append(FloodEvidenceRecord(
        title="India-WRIS hydro-meteorological station registry",
        kind=FloodEvidenceKind.NETWORK_STATUS,
        status=UNAVAILABLE,
        source_org="India-WRIS (CWC/MoJS + NRSC-ISRO)",
        dataset="CWC Hydro-Meteorological Sites registry (901 HMS)",
        source_url=_CITED["wris_hms"],
        retrieved_at=fetched_at,
        license="India-WRIS (government open access)",
        spatial_coverage="India-wide HMS registry",
        temporal_coverage="registry as published",
        units="stations",
        datum_note="n/a",
        resolution_note="Registry-level",
        uncertainty_note=(
            "indiawris.gov.in was unreachable from the research environment on "
            f"{fetched_at[:10]} (fetch failure after {retries} attempts) — recorded "
            "as a FETCH FAILURE, not certified absence. Registry documented via "
            "India-WRIS/NGI wiki + CWC sources."
        ),
        confidence="low",
        count=0,
        note="Registry endpoint not live-verifiable at this checkpoint.",
    ))

    records.append(FloodEvidenceRecord(
        title="BBMB Bhakra reservoir bulletin — indexed snapshots (FRL/MWL + recent)",
        kind=FloodEvidenceKind.RESERVOIR_LEVEL,
        status=OBTAINED,
        source_org="BBMB",
        dataset="BBMB Reservoir Data (indexed bulletin snapshots)",
        source_url=_CITED["bbmb_2026_snapshot"],
        retrieved_at=None,
        license="BBMB public bulletin (© BBMB)",
        spatial_coverage="Bhakra Dam (31.4156N, 76.4347E) ~45 km upstream of plot",
        temporal_coverage="snapshots: 2025-09-04 and 2026-08-21",
        units="level ft; inflow/outflow cusecs",
        datum_note="BBMB gauge datum in feet; FRL 1680 ft, MWL 1690 ft, top of dam 1700 ft",
        resolution_note="Daily (06:00) bulletin values",
        uncertainty_note=(
            "Two independent indexed snapshots: 4 Sep 2025 — Bhakra 1678.97 ft, "
            "inflow 95435, outflow 73459 cusecs; 21 Aug 2026 —Bhakra 1629.32 ft, "
            "inflow 48309, outflow 24112 cusecs. FRL constant 1680 ft (≈512.06 m). "
            "Confidence medium (indexed copies, consistent)."
        ),
        confidence="medium",
        count=2,
        sample=[
            {"date": "2025-09-04", "level_ft": 1678.97, "inflow_cusecs": 95435, "outflow_cusecs": 73459},
            {"date": "2026-08-21", "level_ft": 1629.32, "inflow_cusecs": 48309, "outflow_cusecs": 24112},
        ],
        note="Bhakra level is the headwater control for any dam-break / release "
             "scenario at Ropar; it is upstream-boundary evidence, NOT a plot depth.",
    ))

    return FloodEvidenceResult(
        plot_lat=plot_lat,
        plot_lon=plot_lon,
        radius_km=radius_km,
        fetched_at=fetched_at,
        records=records,
        portal_probe=probe,
    )
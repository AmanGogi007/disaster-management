"use client";

import type { Assessment, EvidenceCategory } from "@/types/api";

interface Props {
  assessment: Assessment;
  evidence_rows?: EvidenceCategory[];
}

type StageState = "verified" | "incomplete" | "blocked";

interface Stage {
  key: string;
  label: string;
  state: StageState;
  detail: string;
}

const VERIFIED = ["available"];
const INCOMPLETE = ["partial"];

function stateOf(status: string | undefined): StageState {
  if (!status) return "blocked";
  if (VERIFIED.includes(status)) return "verified";
  if (INCOMPLETE.includes(status)) return "incomplete";
  return "blocked";
}

function catState(summary: Assessment["evidence_summary"], key: string): StageState {
  return stateOf(summary?.categories?.[key]?.status);
}

const EMOJI: Record<StageState, string> = {
  verified: "🟢",
  incomplete: "🟡",
  blocked: "🔴",
};

export default function StagePipeline({ assessment, evidence_rows = [] }: Props) {
  const s = assessment.evidence_summary;

  const stages: Stage[] = [
    {
      key: "location",
      label: "Location",
      state: "verified",
      detail: `${assessment.location.lat}, ${assessment.location.lon} · ${assessment.location.radius_km} km`,
    },
    {
      key: "terrain",
      label: "Terrain",
      state: catState(s, "terrain_elevation"),
      detail: terrainDetail(evidence_rows),
    },
    {
      key: "connectivity",
      label: "Connectivity",
      state: assessment.connectivity.status === "connected"
        ? "verified"
        : assessment.connectivity.status === "unresolved"
          ? "blocked"
          : "incomplete",
      detail: assessment.connectivity.reason,
    },
    {
      key: "flood",
      label: "Flood Evidence",
      state: catState(s, "flood_extent"),
      detail: floodDetail(s, evidence_rows),
    },
    {
      key: "assessment",
      label: "Assessment",
      state: s?.solver_ready ? "verified" : "blocked",
      detail: s?.solver_ready
        ? "Solver eligible"
        : "Solver blocked — needs verified survey + sub-30 m DEM + resolved connectivity",
    },
  ];

  return (
    <div className="pipeline">
      {stages.map((st, i) => (
        <div key={st.key} className={`pipe-stage ${st.state}`}>
          <div className="pipe-dot">
            <span>{EMOJI[st.state]}</span>
          </div>
          <div className="pipe-body">
            <div className="pipe-label">{st.label}</div>
            <div className="pipe-detail">{st.detail}</div>
          </div>
          {i < stages.length - 1 && <div className="pipe-link" />}
        </div>
      ))}
    </div>
  );
}

function terrainDetail(rows: EvidenceCategory[]): string {
  const t = rows.find((r) => r.category === "terrain_elevation");
  if (t?.status === "available" && t.plot?.dem_elevation_m != null) {
    const dem = t.dem_provenance;
    const res = getattr(dem, "source_resolution_m", 30);
    const elev = t.plot.dem_elevation_m;
    return `${elev.toFixed(1)} m (${res} m res, ${getattr(dem, "vertical_datum", "EGM2008")})`;
  }
  return "terrain data not yet gathered";
}

function getattr(obj: any, key: string, default_val: any = null) {
  if (obj == null) return default_val;
  return obj[key] ?? default_val;
}

function floodDetail(
  summary: Assessment["evidence_summary"],
  rows: EvidenceCategory[]
): string {
  const rowsAvail = rows.filter(
    (r) => r.category === "flood_extent" && r.status === "available"
  );
  if (rowsAvail.length === 0) return "no documented flood extent yet";
  return `${rowsAvail.length} documented source(s) — not extrapolated to plot`;
}

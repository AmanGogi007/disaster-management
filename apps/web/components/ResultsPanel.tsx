"use client";

import type { Assessment, EvidenceCategory } from "@/types/api";

interface Props {
  assessment: Assessment;
  evidence_rows?: EvidenceCategory[];
}

const ELEVATION_SOURCE = "Copernicus GLO-30 (DSM)";
const ELEVATION_RESOLUTION_M = 30;

function formatElevationNote(elevation_m: number | null | undefined, dem: any) {
  if (elevation_m === null || elevation_m === undefined) return "-";
  const res = getattr(dem, "source_resolution_m", ELEVATION_RESOLUTION_M);
  const datum = getattr(dem, "vertical_datum", "EGM2008");
  return ` (~${res} m resolution, ${datum})`;
}

function getattr(obj: any, key: string, default_val: any = null) {
  if (obj == null) return default_val;
  return obj[key] ?? default_val;
}

function cardinalLabel(deg: number | null | undefined): string {
  if (deg == null || deg !== deg) return "-";
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][(Math.floor((deg + 22.5) % 360) / 45) % 8];
}

export default function ResultsPanel({ assessment, evidence_rows = [] }: Props) {
  const s = assessment.evidence_summary;
  const terrain = evidence_rows.find((r) => r.category === "terrain_elevation");
  const sutlej = evidence_rows.find((r) => r.category === "channel_centerline");
  const drains = evidence_rows.find(
    (r) => r.category === "channels_drains" && r.status === "available"
  );

  const highRes = s?.categories?.["high_res_dem"]?.status;
  const survey = s?.categories?.["local_survey"]?.status;
  const conn = assessment.connectivity.status;
  const solverLocked = !s?.solver_ready;

  const shortest: number | null | undefined =
    evidence_rows
      .filter((r) => r.category === "channel_centerline")
      .flatMap((r) => (r.features ?? []).map((f) => f.min_distance_km))
      .find((d) => d != null);
  const sutlejDist =
    shortest != null ? `${Math.round(shortest * 1000)} m from plot` : null;

  // Terrain elevation details
  const plotElev = terrain?.plot?.dem_elevation_m;
  const elevNote =
    plotElev != null && terrain != null
      ? formatElevationNote(plotElev, terrain.dem_provenance)
      : "";
  const slopeDeg = terrain?.plot?.slope_deg;
  const aspectDeg = terrain?.plot?.aspect_deg;
  const aspectCardinal = cardinalLabel(aspectDeg);

  // Neighborhood stats
  const hood = terrain?.neighborhood;
  const hoodMin = hood?.min_m ?? null;
  const hoodMax = hood?.max_m ?? null;
  const hoodMean = hood?.mean_m ?? null;
  const hoodRelief = hood?.relief_m ?? null;

  // Low points
  const lowPoints = terrain?.low_points ?? [];

  // Flow direction calculation from slope aspect
  const flowDirectionLabel = aspectCardinal; // Downhill direction is roughly aspect

  return (
    <div className="results">
      <h2>Risk Assessment</h2>
      <div className={`result-status ${solverLocked ? "incomplete" : "ok"}`}>
        {solverLocked ? "INCOMPLETE - more field evidence required" : "Assessment complete"}
      </div>

      <div className="result-grid">
        {/* Terrain elevation card */}
        <div className="result-item terrain-card">
          <span className="rk">Terrain elevation</span>
          <span className="rv">
            {plotElev != null ? `${plotElev.toFixed(1)} m` : "-"} {elevNote}
          </span>
        </div>

        {/* Slope card */}
        {slopeDeg !== null && (
          <div className="result-item">
            <span className="rk">Slope</span>
            <span className="rv">{slopeDeg?.toFixed(1)}°</span>
          </div>
        )}

        {/* Aspect card */}
        {aspectDeg !== null && (
          <div className="result-item">
            <span className="rk">Aspect</span>
            <span className="rv">
              {aspectDeg?.toFixed(0)}° {aspectCardinal}
            </span>
          </div>
        )}

        {/* Neighborhood stats card */}
        {hood !== null && (
          <div className="result-item">
            <span className="rk">Terrain range</span>
            <span className="rv">
              {hoodMin != null ? `${hoodMin.toFixed(1)} m` : "-"} to {hoodMax != null ? `${hoodMax.toFixed(1)} m` : "-"}
              {hoodRelief != null ? ` (relief ${hoodRelief.toFixed(1)} m)` : ""}
            </span>
          </div>
        )}

        {/* Low points card */}
        {lowPoints.length > 0 && (
          <div className="result-item">
            <span className="rk">Low areas</span>
            <span className="rv">
              {lowPoints.length} depression{"s "}
              {lowPoints
                .slice(0, 3)
                .map(
                  (p) => {
                    const d = p.distance_from_plot_m ? `${p.distance_from_plot_m.toFixed(0)} m` : "? m";
                    const e = p.dem_elevation_m ? `${p.dem_elevation_m.toFixed(1)} m` : "? m";
                    return `${d} away (${e})`;
                  }
                )
                .join(", ")}{lowPoints.length > 3 ? ` +${lowPoints.length - 3} more` : ""}
            </span>
          </div>
        )}

        {/* Sutlej distance */}
        <div className="result-item">
          <span className="rk">Sutlej</span>
          <span className="rv">{sutlejDist ?? "not identified"}</span>
        </div>

        {/* Local drainage */}
        <div className="result-item">
          <span className="rk">Local drainage</span>
          <span className="rv">{drains ? "detected" : "none detected"}</span>
        </div>

        {/* Hydraulic connectivity */}
        <div className="result-item">
          <span className="rk">Hydraulic connectivity</span>
          <span className={`rv ${conn === "connected" ? "ok" : "warn"}`}>
            {conn === "connected" ? conn : `⚠ UNRESOLVED`}
          </span>
        </div>

        {/* High-res DEM */}
        <div className="result-item">
          <span className="rk">High-resolution DEM</span>
          <span className={`rv ${highRes === "available" ? "ok" : "req"}`}>
            {highRes === "available" ? "✓ Available" : "❌ Required"}
          </span>
        </div>

        {/* Local survey */}
        <div className="result-item">
          <span className="rk">Local survey</span>
          <span className={`rv ${survey === "available" ? "ok" : "req"}`}>
            {survey === "available" ? "✓ Available" : "❌ Required"}
          </span>
        </div>

        {/* Solver */}
        <div className="result-item">
          <span className="rk">Solver</span>
          <span className={`rv ${solverLocked ? "req" : "ok"}`}>
            {solverLocked ? "🔒 BLOCKED" : "🔓 READY"}
          </span>
        </div>
      </div>

      <div className="why-banner">
        <strong>Why can&apos;t I get a flood depth yet?</strong>
        <p>
          The available terrain data is not sufficiently detailed to establish
          plot-level hydraulic connectivity. A sub-30&nbsp;m DEM and a verified
          local survey are required before flood depth can be calculated.
        </p>
        <p className="why-sub">
          Current terrain: {plotElev != null ? `${plotElev.toFixed(1)} m from ${ELEVATION_SOURCE}` : "not yet gathered"} at ~{ELEVATION_RESOLUTION_M} m resolution ·
          connectivity {conn.toUpperCase()} at ~30 m DEM resolution ·
          high-res DEM {highRes === "available" ? "available" : "required"} ·
          local survey {survey === "available" ? "available" : "required"}. The engine
          reports evidence states, never invented flood depths.
        </p>
      </div>
    </div>
  );
}

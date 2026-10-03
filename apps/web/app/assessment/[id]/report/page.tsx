"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import type { AssessmentEvidence } from "@/types/api";
import { getEvidence } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  terrain_elevation: "Terrain Elevation",
  channel_centerline: "Channel Centerline",
  channels_drains: "Local Channels & Drains",
  embankments_road_rail: "Embankments / Roads / Rail",
  bridges_culverts: "Bridges & Culverts",
  flood_control: "Flood-Control Structures",
  documented_flood_extents: "Historical Flood Extents",
  gauge_series: "Gauge Series",
  reservoir_level: "Reservoir Level",
  peak_flow_record: "Peak Flow Record",
  network_status: "Telemetry Network",
  local_survey: "Local Survey",
  high_res_dem: "High-Res DEM",
  connectivity: "Hydraulic Connectivity",
};

export default function ReportPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<AssessmentEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await getEvidence(id);
      setData(d);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refresh(); }, [refresh]);

  if (loading) return <div className="loading">Loading report…</div>;
  if (error) return <div className="loading">{error}</div>;
  if (!data) return <div className="loading">No report data.</div>;

  const rows = data.evidence_rows || [];
  const summary = data.evidence_summary;

  const verified = rows.filter((r) => r.status === "available");
  const partial = rows.filter((r) => r.status === "partial");
  const unresolved = rows.filter((r) => r.status === "unresolved");
  const missing = rows.filter((r) => r.status === "missing");

  return (
    <div className="report-page">
      <h2>Assessment Report</h2>
      <p className="report-sub">
        Location: {data.location.lat}, {data.location.lon} ·
        Evidence sources: {rows.length} ·
        Verified: {verified.length} ·
        Missing: {missing.length}
      </p>

      {/* Overall status */}
      {summary && (
        <div className="note-box" style={{ marginBottom: 16 }}>
          <strong>Overall evidence:</strong>{" "}
          <span className={`badge ${summary.overall}`}>{summary.overall}</span>
          {" · "}Plot-level credible:{" "}
          <span style={{ color: summary.plot_level_credible ? "var(--green)" : "var(--red)" }}>
            {summary.plot_level_credible ? "yes" : "no"}
          </span>
          {" · "}Connectivity:{" "}
          <span className={`badge ${summary.connectivity}`}>{summary.connectivity}</span>
          {" · "}Solver:{" "}
          <span className={`badge ${summary.solver_ready ? "ready" : "blocked"}`}>
            {summary.solver_ready ? "ready" : "blocked"}
          </span>
        </div>
      )}

      {/* Verified evidence */}
      {verified.length > 0 && (
        <div className="report-section verified">
          <h3>Verified Evidence ({verified.length})</h3>
          <p>These sources were successfully fetched and validated.</p>
          <ul>
            {verified.map((r, i) => (
              <li key={i}>
                <strong>{CATEGORY_LABELS[r.category] || r.category}</strong>
                {" — "}{r.note}
                {r.plot_elevation_m != null && (
                  <> · Elevation: {r.plot_elevation_m} m</>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Unresolved */}
      {unresolved.length > 0 && (
        <div className="report-section unresolved">
          <h3>Unresolved ({unresolved.length})</h3>
          <p>These items exist but are not yet resolved at the available data resolution.</p>
          <ul>
            {unresolved.map((r, i) => (
              <li key={i}>
                <strong>{CATEGORY_LABELS[r.category] || r.category}</strong>
                {" — "}{r.note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing */}
      {missing.length > 0 && (
        <div className="report-section unavailable">
          <h3>Missing ({missing.length})</h3>
          <p>These evidence sources could not be fetched or are not yet integrated.</p>
          <ul>
            {missing.map((r, i) => (
              <li key={i}>
                <strong>{CATEGORY_LABELS[r.category] || r.category}</strong>
                {" — "}{r.source}: {r.note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Assumptions */}
      <div className="report-section assumptions">
        <h3>Assumptions &amp; Constraints</h3>
        <ul>
          <li>Plot elevation from Copernicus GLO-30 (30 m resolution, EGM2008 datum).</li>
          <li>Channel geometry from OpenStreetMap — may be incomplete or imprecise.</li>
          <li>Connectivity is <strong>unresolved</strong> at 30 m DEM resolution. The plot may or may not sit on a connected floodplain.</li>
          <li>No hydraulic solver has been run. No flood depth or probability is presented.</li>
          <li>Historical flood extents are characterization-only — not a prediction.</li>
        </ul>
      </div>

      {/* Actions */}
      <div className="report-section actions">
        <h3>Recommended Actions</h3>
        <ul>
          <li>Download the survey specification and conduct a field survey of the plot.</li>
          <li>Acquire a sub-30 m DEM (Cartosat-1 / Bhuvan / ALOS) for the plot area.</li>
          <li>Upload verified survey data and DEM to resolve connectivity.</li>
          <li>After connectivity is resolved, the solver can be run.</li>
        </ul>
      </div>
    </div>
  );
}

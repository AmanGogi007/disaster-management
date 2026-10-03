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

const STATUS_ORDER = ["available", "partial", "unresolved", "missing", "not_applicable"];

const STATUS_LABELS: Record<string, string> = {
  available: "VERIFIED",
  partial: "PARTIAL",
  unresolved: "UNRESOLVED",
  missing: "UNAVAILABLE",
  not_applicable: "N/A",
};

const STATUS_ICONS: Record<string, string> = {
  available: "✓",
  partial: "~",
  unresolved: "?",
  missing: "✗",
  not_applicable: "—",
};

export default function EvidencePage() {
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

  if (loading) return <div className="loading">Loading evidence…</div>;
  if (error) return <div className="loading">{error}</div>;
  if (!data) return <div className="loading">No evidence data.</div>;

  const rows = data.evidence_rows || [];

  // Sort: available first, then partial, then unresolved, then missing
  const sorted = [...rows].sort((a, b) => {
    const ai = STATUS_ORDER.indexOf(a.status);
    const bi = STATUS_ORDER.indexOf(b.status);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <div className="evidence-page">
      <h2>Evidence Inventory</h2>
      <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 20 }}>
        Every row below is a real evidence source. Status reflects what was
        fetched and verified — never invented.
      </p>

      <div className="ev-detail-grid">
        {sorted.map((row, i) => (
          <div key={i} className="ev-detail-card">
            <div className="ev-detail-header">
              <div>
                <div className="ev-detail-category">
                  {CATEGORY_LABELS[row.category] || row.category}
                </div>
                <div className="ev-detail-source">{row.source}</div>
              </div>
              <span className={`badge ${row.status}`}>
                {STATUS_ICONS[row.status] || "?"} {STATUS_LABELS[row.status] || row.status}
              </span>
            </div>
            <div className="ev-detail-note">{row.note}</div>
            <div className="ev-detail-meta">
              <span>Confidence: {row.confidence}</span>
              {row.reference && <span> · {row.reference}</span>}
              {row.count !== undefined && <span> · {row.count} features</span>}
            </div>
            {row.plot_elevation_m !== undefined && row.plot_elevation_m !== null && (
              <div className="ev-detail-meta">
                Plot elevation: {row.plot_elevation_m} m · Slope: {row.slope_deg}°
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

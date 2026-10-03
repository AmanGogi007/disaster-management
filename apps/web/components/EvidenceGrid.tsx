"use client";

import type { EvidenceSummary } from "@/types/api";

const CATEGORY_LABELS: Record<string, string> = {
  terrain_elevation: "Terrain",
  channel_centerline: "Channel",
  channels_drains: "Drains",
  embankments_road_rail: "Barriers",
  bridges_culverts: "Bridges",
  flood_control: "Flood Control",
  documented_flood_extents: "Flood Hist.",
  gauge_series: "Gauge Series",
  reservoir_level: "Reservoir",
  peak_flow_record: "Peak Flow",
  network_status: "Network",
  connectivity: "Connectivity",
  local_survey: "Survey",
  high_res_dem: "Hi-Res DEM",
};

// Map the internal API status keys to the spec vocabulary for display.
const STATUS_LABELS: Record<string, string> = {
  available: "VERIFIED",
  partial: "PARTIAL",
  missing: "UNAVAILABLE",
  unresolved: "UNRESOLVED",
  not_applicable: "N/A",
};

const STATUS_ICONS: Record<string, string> = {
  available: "✓",
  partial: "~",
  unresolved: "?",
  missing: "✗",
  not_applicable: "—",
};

interface Props {
  summary: EvidenceSummary;
}

export default function EvidenceGrid({ summary }: Props) {
  const entries = Object.entries(summary.categories);

  return (
    <div className="ev-grid">
      {entries.map(([cat, info]) => (
        <div key={cat} className="ev-card">
          <div className="ev-top">
            <span className="ev-label">
              {CATEGORY_LABELS[cat] || cat}
            </span>
            <span className={`badge ${info.status}`}>
              {STATUS_ICONS[info.status] || "?"} {STATUS_LABELS[info.status] || info.status}
            </span>
          </div>
          <div className="ev-source">{info.source}</div>
        </div>
      ))}
    </div>
  );
}

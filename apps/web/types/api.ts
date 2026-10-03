/**
 * V0.3 evidence-first types.
 * Mirrors the API contracts.  Never invents a flood-depth or risk-score.
 */

export type EvidenceStatus = "available" | "partial" | "missing" | "not_applicable" | "unresolved";
export type OverallStatus = "complete" | "incomplete" | "partial";
export type SolverStatus = "ready" | "blocked" | "not_implemented";
export type Confidence = "high" | "medium" | "low";

export interface EvidenceCategory {
  category: string;
  status: EvidenceStatus;
  source: string;
  reference: string;
  note: string;
  confidence: Confidence;
  count?: number;
  features?: EvidenceFeature[];
  plot_elevation_m?: number | null;
  plot?: {
    dem_elevation_m?: number | null;
    slope_deg?: number | null;
    aspect_deg?: number | null;
  };
  dem_provenance?: {
    source_resolution_m?: number | null;
    vertical_datum?: string;
    horizontal_crs?: string;
  };
  neighborhood?: {
    min_m?: number | null;
    max_m?: number | null;
    mean_m?: number | null;
    relief_m?: number | null;
  };
  slope_deg?: number | null;
  aspect_deg?: number | null;
  low_points_count?: number;
  low_points?: Array<{
    distance_from_plot_m?: number | null;
    dem_elevation_m?: number | null;
  }>;
  transect?: Record<string, unknown> | null;
}

export interface EvidenceFeature {
  osm_id: string;
  name: string | null;
  tags?: Record<string, string>;
  mid?: [number, number];
  points?: [number, number][];
  endpoints?: [number, number][];
  distance_km?: number | null;
  min_distance_km?: number | null;
  length_km?: number | null;
  elevation_m?: number | null;
  source?: string;
  confidence?: string;
}

export interface EvidenceSummary {
  categories: Record<string, {
    status: EvidenceStatus;
    source: string;
    confidence: Confidence;
  }>;
  overall: OverallStatus;
  plot_level_credible: boolean;
  connectivity: string;
  solver_ready: boolean;
  missing_plot_level: string[];
}

export interface Assessment {
  id: string;
  created_at: string;
  location: {
    lat: number;
    lon: number;
    radius_km: number;
    place_name: string;
  };
  status: string;
  evidence_summary: EvidenceSummary | null;
  connectivity: {
    status: string;
    reason: string;
  };
  solver: {
    status: SolverStatus;
    reason: string;
  };
}

export interface AssessmentEvidence {
  id: string;
  location: { lat: number; lon: number };
  evidence_rows: EvidenceCategory[];
  evidence_summary: EvidenceSummary | null;
}

export type MapLayerType = "point" | "line" | "circle";

export interface MapLayer {
  id: string;
  type: MapLayerType;
  label: string;
  visible: boolean;
  group?: string;
  category?: string;
  name?: string;
  tags?: Record<string, string>;
  length_km?: number;
  osm_id?: string;
  center?: [number, number];
  radius_km?: number;
  coordinates?: [number, number] | [number, number][];
  properties?: Record<string, unknown>;
}

export interface MapLayersResponse {
  id: string;
  layers: MapLayer[];
}

export interface GatherResponse {
  status: string;
  assessment_id: string;
  evidence_summary: EvidenceSummary;
}

export interface ReassessResponse {
  status: string;
  reason?: string;
  connectivity: { status: string; reason: string };
  solver: { status: SolverStatus; reason: string };
}

export interface CreateAssessmentResponse {
  assessment_id: string;
  location: { lat: number; lon: number };
}

export interface AcquisitionSpecSource {
  name: string;
  provider_org: string;
  resolution_m: number | null;
  vertical_datum: string;
  coverage: string;
  license: string;
  access_note: string;
  suitability_for_plot: string;
  status: string;
  recommended: boolean;
  url_or_api: string;
  note: string;
}

export interface AcquisitionSpecPoint {
  category: string;
  target: string;
  value_spec: string;
  method: string;
  accuracy_requirement_m?: number | null;
  vertical_datum: string;
  why: string;
}

export interface AcquisitionSpec {
  plot: [number, number];
  generated_at: string;
  connectivity_status: string;
  plot_level_credible: boolean;
  surveyed_elevations_integrated: number;
  survey_gate: string;
  high_res_gate: string;
  high_res_dem_sources: AcquisitionSpecSource[];
  survey_points: AcquisitionSpecPoint[];
  caveats: string[];
}

export interface AcquisitionSpecResponse {
  id: string;
  spec: AcquisitionSpec;
}

export interface SurveyPointClaim {
  category: string;
  target: string;
  value_m: number;
  provenance: string;
  vertical_datum: string;
  horizontal_system: string;
  accuracy_m: number;
  verified: boolean;
  source_osm_id?: string | null;
}

export interface SurveyPointsResponse {
  id: string;
  accepted: Record<string, unknown>[];
  refused: Record<string, unknown>[];
  connectivity: { status: string; reason: string };
  evidence_summary: EvidenceSummary | null;
}

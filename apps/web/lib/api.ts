import type { Assessment, AssessmentEvidence, MapLayersResponse, GatherResponse, ReassessResponse, CreateAssessmentResponse, AcquisitionSpecResponse, SurveyPointClaim, SurveyPointsResponse } from "@/types/api";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(text || `HTTP ${r.status}`);
  }
  return r.json();
}

export async function createAssessment(
  lat: number, lon: number, radiusKm: number, placeName: string = ""
): Promise<CreateAssessmentResponse> {
  const fd = new FormData();
  fd.append("latitude", String(lat));
  fd.append("longitude", String(lon));
  fd.append("radius_km", String(radiusKm));
  fd.append("input_type", "coordinates");
  fd.append("place_name", placeName);
  return api("/api/assessments", { method: "POST", body: fd });
}

export async function getAssessment(id: string): Promise<Assessment> {
  return api(`/api/assessments/${id}`);
}

export async function getEvidence(id: string): Promise<AssessmentEvidence> {
  return api(`/api/assessments/${id}/evidence`);
}

export async function getMapLayers(id: string): Promise<MapLayersResponse> {
  return api(`/api/assessments/${id}/map-layers`);
}

export async function runGather(id: string): Promise<GatherResponse> {
  return api(`/api/assessments/${id}/gather`, { method: "POST" });
}

export async function reassess(id: string): Promise<ReassessResponse> {
  return api(`/api/assessments/${id}/reassess`, { method: "POST" });
}

export async function getAcquisitionSpec(id: string): Promise<AcquisitionSpecResponse> {
  return api(`/api/assessments/${id}/acquisition-spec`);
}

export async function submitSurveyPoints(id: string, points: SurveyPointClaim[]): Promise<SurveyPointsResponse> {
  return api(`/api/assessments/${id}/survey-points`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ points }),
  });
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import type { Assessment, EvidenceCategory } from "@/types/api";
import { getAssessment, getEvidence, runGather } from "@/lib/api";
import MapView from "@/components/MapView";
import EvidenceGrid from "@/components/EvidenceGrid";
import SolverPanel from "@/components/SolverPanel";
import AcquisitionPanel from "@/components/AcquisitionPanel";
import StagePipeline from "@/components/StagePipeline";
import ResultsPanel from "@/components/ResultsPanel";

export default function AssessmentPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<Assessment | null>(null);
  const [rows, setRows] = useState<EvidenceCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [gathering, setGathering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await getAssessment(id);
      setData(d);
      const ev = await getEvidence(id).catch(() => null);
      if (ev) setRows(ev.evidence_rows);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleGather() {
    setGathering(true);
    setError(null);
    try {
      await runGather(id);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGathering(false);
    }
  }

  async function handleSurveyAccepted() {
    await refresh();
  }

  if (loading) return <div className="loading">Loading assessment…</div>;
  if (error && !data) return <div className="loading">{error}</div>;
  if (!data) return <div className="loading">Assessment not found.</div>;

  const needsGather = data.status === "created" || !data.evidence_summary;

  return (
    <div className="dash-body">
      <aside className="dash-sidebar">
        {/* Location info */}
        <div className="section">
          <h3>Location</h3>
          <div className="kv">
            <span className="k">Latitude</span>
            <span className="v">{data.location.lat}</span>
            <span className="k">Longitude</span>
            <span className="v">{data.location.lon}</span>
            <span className="k">Radius</span>
            <span className="v">{data.location.radius_km} km</span>
            {data.location.place_name && (
              <>
                <span className="k">Place</span>
                <span className="v">{data.location.place_name}</span>
              </>
            )}
          </div>
        </div>

        {/* Error */}
        {error && <div className="section"><div className="error-banner">{error}</div></div>}

        {/* Gather button */}
        {needsGather && (
          <div className="section">
            <button className="btn" onClick={handleGather} disabled={gathering}>
              {gathering ? "Gathering evidence…" : "Gather Evidence"}
            </button>
            <p style={{ fontSize: 11, color: "var(--muted)", marginTop: 8 }}>
              Runs OSM, terrain, and flood evidence gatherers. Does NOT run the solver.
            </p>
          </div>
        )}

        {/* Evidence summary */}
        {data.evidence_summary && (
          <div className="section">
            <h3>Evidence Status</h3>
            <div style={{ marginBottom: 8 }}>
              <span className={`badge ${data.evidence_summary.overall}`}>
                {data.evidence_summary.overall}
              </span>
            </div>
            <EvidenceGrid summary={data.evidence_summary} />
          </div>
        )}

        {/* Connectivity */}
        <div className="section">
          <h3>Connectivity</h3>
          <div style={{ marginBottom: 6 }}>
            <span className={`badge ${data.connectivity.status}`}>
              {data.connectivity.status}
            </span>
          </div>
          <p style={{ fontSize: 12, color: "var(--muted)" }}>{data.connectivity.reason}</p>
        </div>

        {/* Solver */}
        <div className="section">
          <h3>Solver</h3>
          <SolverPanel solver={data.solver} evidenceSummary={data.evidence_summary} />
        </div>

        {/* Acquisition workflow */}
        <AcquisitionPanel assessmentId={id} onSurveyAccepted={handleSurveyAccepted} />
      </aside>

      <div className="map-area">
        {data.evidence_summary && (
          <div className="pipeline-wrap">
            <StagePipeline assessment={data} evidence_rows={rows} />
          </div>
        )}
        <div className="map-view">
          <MapView assessment={data} />
          <div className="map-legend">
            <span className="lg"><i className="sw" style={{ background: "#3ba7ff" }} />Waterways</span>
            <span className="lg"><i className="sw" style={{ background: "#ffb84d" }} />Barriers</span>
            <span className="lg"><i className="sw" style={{ background: "#7dff8a" }} />Crossings</span>
            <span className="lg"><i className="sw" style={{ background: "#ff7a7a" }} />Flood control</span>
          </div>
        </div>
        {data.evidence_summary && (
          <div className="results-wrap">
            <ResultsPanel assessment={data} evidence_rows={rows} />
          </div>
        )}
      </div>
    </div>
  );
}

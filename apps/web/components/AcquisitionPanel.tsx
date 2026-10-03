"use client";

import { useEffect, useState } from "react";
import type { AcquisitionSpec, SurveyPointClaim } from "@/types/api";
import { getAcquisitionSpec, submitSurveyPoints } from "@/lib/api";

interface Props {
  assessmentId: string;
  onSurveyAccepted: () => void;
}

export default function AcquisitionPanel({ assessmentId, onSurveyAccepted }: Props) {
  const [spec, setSpec] = useState<AcquisitionSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Survey point submission form
  const [valueM, setValueM] = useState("");
  const [target, setTarget] = useState("");
  const [provenance, setProvenance] = useState("");
  const [accuracyM, setAccuracyM] = useState("");
  const [verified, setVerified] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ accepted: number; refused: Record<string, unknown>[] } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAcquisitionSpec(assessmentId)
      .then((r) => { if (!cancelled) setSpec(r.spec); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [assessmentId]);

  function downloadSpec() {
    if (!spec) return;
    const lines = [
      "LOCATION HAZARD INTELLIGENCE ENGINE — FIELD SURVEY SPEC",
      `Plot: ${spec.plot[0]}, ${spec.plot[1]}`,
      `Generated: ${spec.generated_at}`,
      `Connectivity status: ${spec.connectivity_status}`,
      `Plot-level credible: ${spec.plot_level_credible}`,
      "",
      "= SURVEY GATE =",
      spec.survey_gate,
      "",
      "= HIGH-RES DEM GATE =",
      spec.high_res_gate,
      "",
      "= HIGH-RES DEM SOURCES =",
      ...spec.high_res_dem_sources.map((s) =>
        `  - ${s.name} (${s.provider_org}) | ${s.resolution_m ?? "?"} m | ${s.status}${s.recommended ? " [RECOMMENDED]" : ""}\n      ${s.access_note}`
      ),
      "",
      "= SURVEY POINTS REQUIRED =",
      ...spec.survey_points.map((p) =>
        `  - ${p.target}: ${p.value_spec} (${p.method}) — ${p.why}`
      ),
      "",
      "= CAVEATS =",
      ...spec.caveats.map((c) => `  - ${c}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `survey-spec-${assessmentId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function submitPoint() {
    setSending(true);
    setError(null);
    setResult(null);
    const claimed = (v: string): v is string => v.trim().length > 0;
    try {
      const claim: SurveyPointClaim = {
        category: "flood_elevation",
        target: target.trim() || "plot_ground",
        value_m: Number(valueM),
        provenance: provenance.trim(),
        vertical_datum: "EGM2008",
        horizontal_system: "WGS84",
        accuracy_m: Number(accuracyM),
        verified,
      };
      if (!claimed(provenance)) throw new Error("Provenance is required (who measured, instrument, date).");
      if (!(claim.accuracy_m >= 0)) throw new Error("Accuracy must be >= 0.");
      if (!Number.isFinite(claim.value_m)) throw new Error("Value is required.");
      const res = await submitSurveyPoints(assessmentId, [claim]);
      setResult({ accepted: res.accepted.length, refused: res.refused });
      if (res.accepted.length > 0) onSurveyAccepted();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  if (loading) return <div className="section"><h3>Acquisition Workflow</h3><p className="muted">Loading spec…</p></div>;

  return (
    <div className="section">
      <h3>Acquisition Workflow</h3>
      <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
        Collect the missing plot-level evidence (verified survey + sub-30 m DEM).
        The solver stays locked until both are delivered.
      </p>

      {error && <div className="error-banner">{error}</div>}

      {spec && (
        <>
          <div className="kv" style={{ marginBottom: 10 }}>
            <span className="k">Connectivity</span>
            <span className="v">{spec.connectivity_status}</span>
            <span className="k">Plot credible</span>
            <span className="v">{spec.plot_level_credible ? "yes" : "no"}</span>
          </div>

          <button className="btn btn-secondary btn-sm" onClick={downloadSpec} style={{ marginBottom: 12 }}>
            Download Survey Spec (.md)
          </button>

          {spec.high_res_dem_sources.length > 0 && (
            <>
              <h4 style={{ margin: "12px 0 6px" }}>High-res DEM sources</h4>
              {spec.high_res_dem_sources.map((s) => (
                <div key={s.name} className="dem-src" style={{ marginBottom: 8, fontSize: 12 }}>
                  <div>
                    <strong>{s.name}</strong>{" "}
                    <span className={`badge ${s.status}`}>{s.status}</span>
                    {s.recommended && <span className="badge available" style={{ marginLeft: 4 }}>rec</span>}
                  </div>
                  <div style={{ color: "var(--muted)" }}>
                    {s.provider_org} · {s.resolution_m ?? "?"} m · {s.vertical_datum}
                  </div>
                  <div style={{ color: "var(--muted)" }}>{s.access_note}</div>
                </div>
              ))}
            </>
          )}

          {spec.survey_points.length > 0 && (
            <>
              <h4 style={{ margin: "12px 0 6px" }}>Survey points required</h4>
              {spec.survey_points.map((p, i) => (
                <div key={i} style={{ fontSize: 12, marginBottom: 6 }}>
                  <div><strong>{p.target}</strong> — {p.value_spec}</div>
                  <div style={{ color: "var(--muted)" }}>{p.why}</div>
                </div>
              ))}
            </>
          )}
        </>
      )}

      <h4 style={{ margin: "14px 0 6px" }}>Submit a verified survey point</h4>
      <p style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8 }}>
        Only points with verified provenance, datum and accuracy are integrated. Unverified claims are refused.
      </p>
      <div className="survey-form" style={{ display: "grid", gap: 8, maxWidth: 320 }}>
        <input placeholder="Target (e.g. plot_ground)" value={target} onChange={(e) => setTarget(e.target.value)} className="input" />
        <input placeholder="Elevation value (m)" type="number" step="0.01" value={valueM} onChange={(e) => setValueM(e.target.value)} className="input" />
        <input placeholder="Provenance (who/instrument/date)" value={provenance} onChange={(e) => setProvenance(e.target.value)} className="input" />
        <input placeholder="Accuracy (m)" type="number" step="0.01" value={accuracyM} onChange={(e) => setAccuracyM(e.target.value)} className="input" />
        <label style={{ fontSize: 12, display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} />
          Verified (carries documented provenance)
        </label>
        <button className="btn btn-sm" onClick={submitPoint} disabled={sending}>
          {sending ? "Submitting…" : "Submit survey point"}
        </button>
      </div>

      {result && (
        <div style={{ marginTop: 10, fontSize: 12 }}>
          <div>Accepted: <span className="badge available">{result.accepted}</span></div>
          {result.refused.length > 0 && (
            <div className="error-banner" style={{ marginTop: 6 }}>
              {result.refused.length} refused: {result.refused.map((r) => r.reason ?? JSON.stringify(r)).join("; ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

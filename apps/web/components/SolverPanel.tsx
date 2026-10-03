"use client";

import type { SolverStatus, EvidenceSummary } from "@/types/api";

interface Props {
  solver: { status: SolverStatus; reason: string };
  evidenceSummary: EvidenceSummary | null;
}

const PREREQS = [
  { key: "high_res_dem", label: "High-res DEM (< 30 m) integrated" },
  { key: "local_survey", label: "Verified survey data integrated" },
  { key: "connectivity", label: "Hydraulic connectivity resolved" },
];

export default function SolverPanel({ solver, evidenceSummary }: Props) {
  const summary = evidenceSummary;

  return (
    <div className={`solver-panel ${solver.status}`}>
      <h3>
        {solver.status === "ready" ? "Solver Ready" : solver.status === "blocked" ? "Solver Locked" : "Solver"}
      </h3>
      <p className="reason">{solver.reason}</p>

      {summary && (
        <ul className="checklist">
          {PREREQS.map((p) => {
            let done = false;
            if (p.key === "connectivity") {
              done = summary.connectivity === "connected";
            } else {
              done = !summary.missing_plot_level.includes(p.key);
            }
            return (
              <li key={p.key}>
                <span className={`check ${done ? "done" : "wait"}`}>
                  {done ? "✓" : "✗"}
                </span>
                {p.label}
              </li>
            );
          })}
        </ul>
      )}

      {solver.status === "blocked" && (
        <div className="note-box" style={{ marginTop: 12 }}>
          The solver is locked. Complete all prerequisites above — upload a verified
          DEM and survey data, then resolve connectivity — before the solver can run.
        </div>
      )}
    </div>
  );
}

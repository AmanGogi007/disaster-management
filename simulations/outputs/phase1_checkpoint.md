# V0.3 Phase 1 — Checkpoint (design-first, no solver)

**REAL DEM: SUCCESS**

Evidence contract + evidence-based connectivity + gated connected-domain only. No propagation/solver (J.7).

## scenario_A_current_evidence
- connectivity.status: **unresolved**
- reason: Hydraulic connectivity unresolved at 30 m DEM resolution.
- domain.outcome: **unresolved**
- interpretation: With only the Sutlej centreline available and no local survey/channels-drains/high-res DEM, on the flat 30 m reach the correct output is the J.1 'unresolved' statement — NOT a fabricated low risk or flood depth.

## scenario_B_illustrative_full_evidence
- connectivity.status: **unresolved**
- reason: Hydraulic connectivity unresolved at 30 m DEM resolution.
- domain.outcome: **unresolved**
- interpretation: On the flat real reach, even with full plot-level evidence the terrain itself cannot resolve a routing direction (D8=flat), so connectivity stays UNRESOLVED from the DEM alone. This proves the no-fabricated-path rule: availability of evidence does not auto-manufacture a path — the solver (with water surface + momentum, later phase) plus the high-res DEM is what may resolve it.

## Design contracts demonstrated
- J.1 no-fabricated-path: UNRESOLVED emitted verbatim when evidence/terrain inadequate
- J.3 constraining-observations: plot_level_credible False without survey+high-res
- J.4 evidence-based connectivity: requires channel + documented link + resolvable reach
- J.2 gated domain: domain extracted only on CONNECTED; None otherwise

Total runtime: 6.62 s

> No solver, no hydrograph, no propagation. 48/48 V0.2 + 12 new Phase 1 tests pass (60 total). Waiting for review.

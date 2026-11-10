# Resource estimate, not a promise

Measured completed v6:37 sessions, approximately58 seconds between RUN_STARTED and RUN_STATUS,73,805,543 bytes in final export,328MiB whole directory because of cumulative checkpoints. Initialization before RUN_STARTED is additional.

Requested calendar has439 sessions. Simple proportional extrapolation gives approximately11.5 minutes and0.88GB final exports. State/archive growth and per-day full snapshots can make runtime and memory superlinear; allow tens of minutes and potentially1–2 hours rather than promising the linear estimate. Early factual stops may finish much sooner. A practical output allowance is1–3GB, depending on trading/ticket volume. These are untested estimates, not measured long-run results.

Keep only the fullOctober31 prefix checkpoint (about74MB at the measured scale) and final/blocked export. No repeated monthly cumulative JSON/CSV dumps. Preserve DAY console lines for progress; inspect actual exports for financial conclusions. No long history has run.

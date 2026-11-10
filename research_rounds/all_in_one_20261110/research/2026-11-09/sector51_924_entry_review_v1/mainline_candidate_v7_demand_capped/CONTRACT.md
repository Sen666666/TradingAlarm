# M7: cap expansion targets at current legal demand

Research-only single-factor comparison to frozen M6 (engine SHA256 5cdfa190071396559f1dbb97c9dd7fc4f89ec501766f2d63bbe3d2b3f24064e8). No live trades. Hypothesis fixed before inspecting M6 outcomes; no outcome-driven tuning. Same 2024-09-02 to 2024-10-08 independent 1.2 million account and data. Do not run history until independent admission and explicit hash-bound contract approval.

## Only allocation-cap change

V is marked actual sector holdings. F retains M6 fixed/INITIAL core/UNKNOWN/locked/T1 and event-receiver freeze. K=V-F. EVENT reservations R are unchanged and computed first. G=NAV-10%NAV-receivable-sum(F)-stress-sum(R). Eligible set J remains M TRUE and E>0. W=E+max(known daily E increase,0), unchanged.

D is the sum of current raw MATURE request legal all-in costs before reference and cash caps, after current EVENT reservations have consumed shared stock budget. Use actual inherited noncash CLOSE gates and frozen request quantities: structural legality, valid unconsumed CP, positive current CLOSE round net profit, I/CP protection, 10% stock budget, per-CP 2% original round NAV, capacity and legal quantities. M6's removed 4% round cap is not reintroduced. Mature SEED uses unchanged economic minimum quantity, representative-known gate and existing attempt budget, not an invented larger seed. ADD uses inherited maximum legal quantity. Original CLOSE construction remains responsible for upstream eligibility; D does not invent requests.

Deduplicate by stock/kind/current CP (SEED by stock). Deterministic within-sector order remains ADD first by CP date/stock, then known SEED representative order; decrement a shared stock's budget exactly once per unique legal request. EVENT/RESIDUAL never enter D. D does not use target lambda, hypothetical donor sales, cash or future CP/OPEN facts. No cross-sector contention exists in stock budgets.

For s in J: U=K+D, X=min(U,lambda W), sum(X)=min(max(0,G),sum(U)). K is not a floor. For sectors outside J, X=0. T=F+R+X. Mature buy envelope=max(0,X-K). Industry with no new request cannot gain a target above its existing mobile holdings. Excess G stays unallocated. Negative G and no-positive-E-M status handling are inherited. Continuous Decimal capped waterfill is deterministic; no second discrete slack redistribution occurs.

## Unchanged execution and safety boundaries

All inherited source files remain byte-identical. All signals, sizing, information confirmation, CP consumption only on real fill, protections, fees, initial/expansion roles and event/non-M handling remain M6. Existing ranking/rounding after reference construction is unchanged. CLOSE freezes quantities and receivers; OPEN only shrinks/cancels, never recomputes lambda or invents receivers. Targets are not spendable cash; real net donor proceeds must arrive before purchases and 10% cash reserve remains. Old INITIAL core never financially donates. No shared trial-risk pool or retrospective winner list.

Atomic loop is inherited unchanged. New diagnostics live only in snapshotted reference and existing reference logs. Temporary raw-request context is removed by try/finally on success or failure. Record daily D/K/U/X, unallocated G and independent demand gates/quantities/costs for audit. Do not claim robustness, causality by sector attribution, or live readiness from this short non-PIT-mapping sample and conditional OPEN cost model.

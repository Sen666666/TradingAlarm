# Frozen CE account handoff

READY: full original fixed-pool input and CORE-fixed stock-slot ranking. No account run has been performed here.

## Runtime interfaces

Directory: this account_adapter folder. Load it on sys.path, import CELookup from ce_adapter and rank_stock_slots from account_rank. Instantiate lookup = CELookup(directory=adapter_directory, verify_hashes=True) once.

- lookup.query(sid, signal_day) -> dictionary with CE, CE_known, reason, formation_n, variance_budget, source D/K/r/m and related diagnostics for original fresh CP only.
- lookup.score_candidates(frame) -> all input rows plus CE/status fields; only sid/day determine score. Original account/held fields do not influence CE. Never inner join and never drop a missing lookup.
- rank_stock_slots(frame, signal_day, lookup) -> (ranked_frame, audit_dict). Required columns: sid, rank, was_empty, has_mobile_intent, has_core_intent, PVR_score, PVR_ready. One row per stock from ACTUAL current counterfactual pending AFTER unchanged native planning. Original rank must be unique finite native stock values; gaps are allowed. Boolean fields must be explicit. Empty typed queue is supported.

Output adds ce_stock_rank and CE audit columns. Original rank and priority_rank fields, if present, remain unchanged, as do all original fields. The caller applies only ce_stock_rank to pending execution rank for that stock, retaining original priority_rank for comparison. It must keep original CORE-before-MOBILE ordering within stock and original done-per-stock handling. Do not change order sizing, budget, cash, exposure, admission, protection, exit or account state logic.

## Account scope and tie contract

Only current empty + actual pending MOBILE + NO actual pending CORE + PVR_ready/finite + CE known whole-stock slots can exchange. CORE+MOBILE groups are entirely fixed. All held groups, non-MOBILE groups, unknown CE, unknown/not-ready PVR stay in their original stock rank slot. Use actual pending role, NOT core_Q qualification. A CORE rejected by original planning/size checks and absent from pending is not an actual pending CORE.

All native stock rank keys are preserved without compressing to 1..N. Finite movable rows sort by CE rounded12 desc, original PVR rounded12 desc, original native stock rank then sid. Assign to the original movable rank keys. No K=20 and no truncation: every original stock group returns. The original account alone determines how many orders its actual cash/position/lot-size rules can accept.

`CELookup.rank_frame` is ONLY the old signal-diagnostic reproduction interface. It can reproduce all old 103766 candidate scores and 1568 queues, but it does not freeze CORE groups. Do NOT use rank_frame directly for the account intervention.

Fixed CORE ordering cannot guarantee identical CORE fills or cash: different preceding MOBILE purchases can change available cash indirectly. That is an account path consequence, not a direct CORE sorting change. Audit and report it.

## Formula and state/restart

The formula is exactly the frozen prepare_ce.py implementation whose hash is in ADAPTER_MANIFEST. r/m/D/K are original native cache values. v_j^2=max(mean(last 21 finite same-source r strictly BEFORE j squared), log(1.001)^2). V sums v_j^2 from the observation AFTER the true native anchor through current receipt. CE=min(original D,original K)/sqrt(V). No score threshold, n cap, receipt revival or delay.

Original start/E0_down_reset/lower_anchor establish an anchor with V=n=0; E0_invalid/unprepared/source change reset. Ordinary pullbacks accumulate. Current receipt is scored before consumption, then resets. Source change also resets r history; ordinary CP/E0 reset does not. The whole CP lineage is independent of account holdings.

The runtime lookup has no mutable incremental/account state. Restart requires only loading the exact same immutable files and querying the same original signal date. There is no warm-up state to serialize or recover in the account engine. All score preparation used source-only full-prefix histories and passed physical truncated-input checks. Scores must never be recomputed from account entry dates or truncated at the account start.

The serialized table covers every original cached fresh CP for all complete-source fixed-pool stocks, including dates not in the original candidate domain. It does not load original account history at runtime. Historical account files are read only by the separate scope audit, not by ce_adapter/account_rank.

## Coverage and explicit fallback

1709 fixed-pool names: 1687 complete native sources; 22 original manifest entries explicitly have no local observation by the original endpoint. All 232520 cached native receipts have finite CE. 177668 receipt keys are outside the previous 54852 candidate-stock-day domain. This avoids silently restricting a counterfactual account to original held/empty history.

query outside the fixed pool, on one of the 22 unavailable stocks, outside native source dates, or on a day without original cached fresh CP returns UNKNOWN with reason. Insufficient formation-variance/warm history would also be UNKNOWN. On any UNKNOWN the exact original slot stays unchanged; no interpolation, old receipt carry, score filling, inner join deletion, or replacement by a guessed CE. A future dataset extension requires a newly authorized adapter version; this adapter does not silently fetch/recompute data.

## Proven checks and scope difference

- 4081068 original source observations; native credit/D/anchor/frozen-scale lineage audit.
- 5061 whole-prefix checks over 1687 stocks × 2022-03-31/2024-09-24/2026-01-15.
- All original 103766 candidate rows / 54852 stock-days exactly identical in all saved CE state columns.
- All 1568 old complete diagnostic queues and 91 PVR-unknown exact slots reproduced.
- All 1579 original actual pending stock queues tested under CORE-fixed account scope; original fields and CORE rank slots preserved.
- Original legal MOBILE candidates include 83165 actual CORE+MOBILE groups (80.15%). Only 20601 are MOBILE-only, 20591 finite-score movable. These counts come from actual decisions/intents, never core_Q.
- Unknown CE/PVR, PVR not-ready, CORE overlap, held MOBILE, zero/one movable group, nonconsecutive rank values, exact tie ordering, typed empty queue, restart and input immutability tests pass.

Thus the account intervention is deliberately narrower than the original same-K20 diagnostic. Its original path win-rate/coverage changes do not establish an equivalent account improvement. No complete 0→0 round win-rate improvement, 30% target attainment, or account return has been shown by this adapter.

## Inputs, hashes, audit files

ADAPTER_MANIFEST.json includes runtime source/data hashes and audit identities. ALL_NATIVE_CP_RECEIPT_CE.parquet is the immutable score table. STOCK_COVERAGE.csv retains every fixed-pool name; EXPLICIT_UNAVAILABLE_STOCKS.csv lists the 22. CACHE_SOURCE_HASHES.csv records each native CP/facts hash and original manifest match. ADAPTER_AUDIT.json is full-input verification. ACCOUNT_SCOPE_AUDIT.json / ACTUAL_CORE_INTERSECTION_BY_YEAR.csv / ORIGINAL_CANDIDATE_ACTUAL_ROLE_SCOPE.parquet record actual CORE overlap. BOUNDARY_TESTS.json covers final runtime edge cases. FINAL_HANDOFF_HASHES.json covers all final files. Original candidate_test sealed artifacts remain byte-identical.

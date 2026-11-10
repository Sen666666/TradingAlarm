# FINAL account interface: all current empty first-entry stock slots

This is the latest authorized scope. Use empty_first_rank.py and EMPTY_FIRST_MANIFEST.json, not the historical narrow account_rank.py interface. The narrow artifacts and original same-K20 diagnostic remain byte-identical. There has been no account execution here.

## Exact API

Add this directory to sys.path, then:

from empty_first_rank import load_empty_first_inputs, rank_empty_first_stock_slots
lookup = load_empty_first_inputs(directory=adapter_directory)
ranked, audit = rank_empty_first_stock_slots(stock_frame, signal_close_day, lookup)
stock_rank_map = dict(zip(ranked.sid, ranked.ce_stock_rank))

Apply only stock_rank_map[sid] to the original pending execution rank after unchanged native planning. Retain original priority_rank in logs. Never replace or remove an original pending row by an inner join. Keep CORE-before-MOBILE and one-success-per-stock semantics.

stock_frame requires one row per actual current pending stock with sid, rank, was_empty, has_mobile_intent, has_core_intent, PVR_score, PVR_ready. was_empty must be the current counterfactual account quantity==0, never inferred from the old candidate table. Role flags describe actual pending intents, not core_Q. Original rank keys must be unique finite values and may be nonconsecutive. All original columns remain unchanged; output adds ce_stock_rank and CE/audit fields. Internally numeric PVR conversion handles None/NaN/object without modifying original columns. An untyped zero-row frame with required columns is supported.

## Final scope and ordering

Movable = was_empty AND original PVR_ready/finite AND current original fresh-CP CE known. CORE is NOT excluded; MOBILE is NOT required. A CORE-only stock with current fresh CE can move. A CORE-only stock without current fresh CE must stay in its exact original slot: no previous certificate, cached last score, interpolation or fabricated CE. Held positions and any unknown/not-ready PVR or unknown CE are fixed.

Sort movable whole-stock groups by CE.round12 descending, original PVR.round12 descending, original native stock rank then sid. Assign to the existing movable native rank keys; do not renumber the queue. This moves both CORE/MOBILE intents of the same stock together. Role priority, qualifications, risk, cash, sizing, positions, protection, exits and execution are unchanged. The original account determines acceptance; no K=20, threshold, filtering or truncation is applied by this module.

The old diagnostic CELookup.rank_frame reproduces the original full MOBILE-candidate K20 ordering only. It is NOT this account intervention. The old account_rank.rank_stock_slots freezes CORE groups and is now historical narrow-scope evidence, NOT the chosen interface.

## Full independent score coverage and UNKNOWN

CELookup query(sid, signal_day) and score_candidates(frame) use only sid/day and immutable original cache-derived scores, never account history. All 1709 original pool symbols are registered; 1687 have complete cache, 22 are explicit no-local-observation-by-original-end. 232520 original fresh receipts have finite CE, including 177668 keys outside the former 54852 candidate-stock-day set.

Unknown source/day, outside pool or no current cached fresh receipt returns CE=NaN/CE_known=False and a reason. Keep its original rank slot. No inner join or prior CE reuse. A future data extension needs a new authorized input version.

Scores use the same frozen D/K/r/m and CP reset/consumption clock, prior21 RMS budgets, and no formula change. 4081068 source observations and 5061 complete input-prefix comparisons passed. All old103766 candidate score rows, all1568 diagnostic queues, and91 PVR-unknown slots match exactly. See ADAPTER_AUDIT.json and original formula source/hash in ADAPTER_MANIFEST.

No mutable CE account state exists. Restart reloads the same verified data files and queries the exact original signal day, giving identical results. Do not warm from the account start or recompute CP.

## Final actual-queue and boundary audit

1579 original pending queues / 281983 stock-group observations were inspected read-only. Current empty state came from same-close original daily holdings; actual roles came from decisions/intents. Independent final-scope slot replay matched the function, every unknown/held slot stayed exact, all native rank keys and original fields were preserved. All-None/object and all-NaN/object PVR, untyped zero rows, zero/one movable group, CORE-only current fresh vs absent CE, held stocks, nonconsecutive keys, input immutability and restart checks passed. No future outcomes were used for this scope audit.

These are original-history interface coverage counts, not counterfactual account trade counts or returns. The upcoming driver must use its own actual held/pending state.

account  stock_groups  empty_groups  held_groups  empty_CORE_MOBILE  empty_CORE_only  empty_MOBILE_only  empty_CORE_only_with_current_CE  movable_stock_groups  empty_PVR_unknown  empty_CE_unknown  fixed_stock_groups  changed_stock_groups  CORE_groups_moved
    E31        137057        132118         4939              45949            73647              12522                              348                 58767                173             73299               78290                 57896              45600
    PVR        144926        139421         5505              49004            77990              12427                              271                 61647                178             77719               83279                 60769              48573

Signal dates: 2022-01-04 through 2026-05-15.

## Outcome boundaries

This broader account scope remains different from the earlier legal-MOBILE same-K20 diagnostic. It moves eligible CORE+MOBILE stocks together and includes CORE-only stocks only when they have current CE. Full0→0 round win rate, 30% target attainment, net account return, fees, execution and drawdown have not been tested here. Preserve old CE diagnostic and narrow scope facts rather than rebranding their results as this intervention.

## Frozen delivery files

Authoritative final manifest: EMPTY_FIRST_MANIFEST.json. Complete handoff list: EMPTY_FIRST_HANDOFF_HASHES.json. Runtime source: empty_first_rank.py, ce_adapter.py. Data: ALL_NATIVE_CP_RECEIPT_CE.parquet, STOCK_COVERAGE.csv. Final audits: EMPTY_FIRST_AUDIT.json, EMPTY_FIRST_SCOPE_OVERALL.csv, EMPTY_FIRST_SCOPE_BY_YEAR.csv, EMPTY_FIRST_QUEUE_SCOPE_AUDIT.csv, EMPTY_FIRST_ORIGINAL_PENDING_SCOPE.parquet, EMPTY_FIRST_SOURCE_HASHES.json. Formula/full-pool evidence: BUILD_FREEZE.json, ADAPTER_AUDIT.json, PREFIX_CHECKS.csv, CACHE_SOURCE_HASHES.csv. Existing ADAPTER_MANIFEST.json is kept as the immutable base data/narrow-scope lineage and is hash-checked by the final manifest.

No changes to delivered runtime code or inputs will be made after this handoff without a new explicit version.

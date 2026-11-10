# Original first profitable add: CORE / ADD cashflow decomposition

## Scope
Source: baseline/ALL_SHADOW_ROUNDS.csv under dual_budget_ablation_v1. M3, FALSE_TO_TRUE, with an actual buy_add action, restricted to birth windows 2022 and 2024_924. Counts are 479 and 251. These are overlapping independent stock-round shadow slots, not a capital account. Birth-window names are not add-execution years: adds extend into 2023 and 2025 respectively. No account replay or parameter scan was performed.

## Attribution
Each layer pays its own buy fee. A sell_add fee is wholly attributed to ADD. At sell_all, the actual single-order fee is allocated proportionally to remaining CORE and ADD share quantities. This is accounting attribution, not the fee that a standalone CORE order would pay. CORE-only cashflow keeps the original CORE entry, quantity, exit time and price, and recomputes its standalone dated sell fee using the original market rules. It is a same-path cashflow counterfactual, not a rerun with alternative cash deployment.

## Main results
All closed ADD layers: 2022 429 layers, 127 wins / 302 losses, net -51,129.31; 2024_924 237 layers, 92 wins / 145 losses, net +37,889.56. Win rates 29.60% / 38.82%; dollar average-win/average-loss ratios 1.899 / 2.086. Return-normalized payoff ratios are separately 1.680 / 1.822.

Only 419 / 221 whole rounds are closed. Another 10 / 16 ADD layers closed before the CORE path became UNKNOWN, contributing +39,947.62 / +12,752.43. Removing these layers because the entire round is UNKNOWN materially biases the add-layer sample. Remaining 50 / 14 ADD layers are UNKNOWN. No OPEN rows occur in these two windows. Corporate-action/factor unknown rounds are 56 / 28; missing-open unknown rounds are 4 / 2. No dividends or corporate-action continuation were imputed.

On the closed-round common denominator, actual-fee-allocated CORE net is 293,106.18 / 294,738.01, ADD net is -91,076.93 / +25,137.13, and whole-round net is 202,029.25 / 319,875.14. CORE winners become whole-round losers in 39 / 18 cases; CORE losers become whole-round winners in 6 / 8. Among CORE and whole-round joint winners, ADD helps 109 / 67 and hurts 71 / 38. Complete count and amount breakdowns for each category and both fee definitions are in CORE_ADD_KEY_RESULTS.txt.

## Fee-sensitive boundary
Combined sell orders save CORE allocated fees of 214.87 / 87.42 relative to standalone CORE fees. CORE-only nets are 292,891.31 / 294,650.59; actual whole-round minus CORE-only is -90,862.06 / +25,224.55.
2022 has two rounding-scale economic classification changes, not reconstruction errors:
- 002517.SZ birth 2022-08-15, add 2022-08-23: allocated CORE +0.83894 versus standalone CORE -0.41294. CORE-only winner-to-loser count therefore falls from 39 to 38.
- 002517.SZ birth 2022-08-09, add 2022-08-16: allocated ADD -0.77835, but combined-fee saving makes actual round versus standalone CORE +2.28617. Joint-winner incremental help/hurt counts become 110/70 rather than 109/71.
No analogous sign change occurs in 2024_924.

## Dependence and denominator
2022 / 2024_924 have 264 / 189 distinct stocks and 156 / 66 add dates. Original birth/entry-signal-date-by-stock has no duplicate rows; add-signal/open-date by stock does repeat. Add-open-date-by-stock has 72 / 26 repeated groups and 95 / 29 extra rows. In CORE_ADD_CASHFLOW_BY_EVENT.csv, signal_day means the original birth/entry signal date; in ALL_ACTUAL_ADD_FEATURES.csv, signal_day means the add signal close date. Maximum stock counts are 9 / 4; maximum same-stock same-add-date counts are 5 / 4. Largest add-date clusters are 22 / 25 rows (4.59% / 9.96%). These are distinct original birth events that reach the same later add, not data errors; do not silently deduplicate or treat them as independent trials. event_id is sector-event level, shared by up to two stocks, so use event_id plus sid for row identity. Windows share 84 stocks. Cluster by stock and relevant signal/add date when drawing uncertainty conclusions.

## QA and interpretation
Per-row one-add, sell_add share conservation and sell_all total-share conservation checked. Reconstructed total cashflow matches cashflow_to_date, closed CORE+ADD matches net_pnl, and recomputed full sell_all fees match recorded fees, each with maximum observed difference zero at reported floating precision. Conditional liquidation marks are not realized P&L. Unclosed ADD/CORE net fields remain missing rather than marking unknowns as losses or filling future outcomes.
Historical tradability remains UNKNOWN; figures use the source conditional-open execution proxy. Amount sums are overlapping shadow-slot sums, not NAV gains or deployable strategy returns. Outcomes here are labels for diagnosis only and must not become as-of predictors or selection criteria.

## Files
- reconstruct_core_add_cashflows.py: reconstruction and original complete printed statistics, with artifact writer.
- CORE_ADD_CASHFLOW_BY_EVENT.csv: 730 per-event CORE/ADD results, statuses, keys and QA columns.
- CORE_ADD_SUMMARY.json: layer summaries and whole-round reconciliation.
- CORE_ADD_KEY_RESULTS.txt: full category amounts for both actual allocation and standalone CORE comparison, cluster counts.
- CORE_ADD_QA.json: source hash, numeric QA and scope.
- CORE_ADD_OUTPUT_SHA256.json: hashes of this deliverable bundle.

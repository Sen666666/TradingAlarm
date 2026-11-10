# Single-difference ADD quantity-cap ablation v1
Research only, no production changes and no trading. Exactly two modes of one source engine; original capped replay then one uncapped research arm. Window is 2024-09-02 through 2024-09-23 inclusive, exactly 14 common trading days. No 9/24 or later account or payoff evaluation, no parameter sweep and no outcome-based selection.

## Sole difference
Starting from the exact approved mainline_candidate_v1/engine.py, remove only ADD quantity <= actual currently held round quantity. Three locations are switched by UNCAP_ADD, default False:
1. CLOSE planned quantity: min(int(capacity), current round quantity) -> int(capacity).
2. noncash sizing (shared by CLOSE demand, OPEN demand and OPEN first size): min(CLOSE planned_q, capacity, current round quantity) -> min(CLOSE planned_q, capacity).
3. alloc_open second sizing including cash: min(first q, CLOSE planned_q, current round quantity) -> min(first q, CLOSE planned_q).
False mode preserves the three original expression ASTs exactly. No new mode-specific function, economic method, ranking or facts. All other ASTs identical after stripping the one flag and selecting the false branch.

All M/Q/S/F/W evidence, A/B/SEED admission, minimum legal seed, independent information confirmation, original CP validity and consumption once on actual fill, close/open positive whole-round fee-net gate, I/CP exits, T+1, source/factor/action checks, Decimal fee/cash, cash floor10%, stock10%, original nav0 single2% and round4% capital slots, original capacity, queue ordering, transfer donor restrictions and retained ticket rules remain untouched. OPEN ADD never exceeds the frozen CLOSE quantity. No shared trial-risk pool, no fixed stock count or per-sector cap. Restoring 2% is explicitly principal at risk, not profit financing; positive prior net is only a direction gate.

## Admission and execution
Static AST seal and focused synthetic PASS must precede historical work. Parent and independent reviewer approval required. Replay false mode to September23 against all 17 original output families before one true-mode account execution. Load one Data(end=2024-09-23) for both modes and seal the same full source hash map; unchanged overlapping reference sources must match. Only account strategy/contract path substitutions are separated. No mutation of original output. A replay mismatch stops before new arm. New-arm RUN_STARTED is exclusive and never overwritten or retried without new documented authorization.

## Required output
Signal CLOSE September6/9 securities cohort is distinct from execution OPEN September6/9; enumerate all original sector_name=证券 A/B candidates, filled and unfilled, closed fee-net and unfinished mark separately. Original baseline35 signals/30 actual/closed net -237.9925290027000 is a required reconciliation, not an assumed uncapped result.
Show September13 full-account NAV,cash,exposure,fees,close drawdown; September18/19/20/23 all50 industry evidence, actual holdings, all seed/ADD fills and rejections; September23 total buy cost, net investment, securities names/shares and software/semiconductor even zero.
For every filled ADD report old-round pre-add fee-net profit, quantity, raw OPEN, buy price/slippage/explicit fees/all-in cost, known I and CP floor, incremental hypothetical loss on selling new layer at the known maximum I/CP floor with sell slippage/fee, and whole-round hypothetical net after ADD. Also report layer-specific old protections for interpretation, ratios to initial principal, frozen nav0 and actual pre-add NAV. All hypothetical floor figures use known same-day inputs, not future outcomes. They are not maximum risk under T+1, gaps, locks or liquidity and OPEN +/-5bp is only a conditional cost proxy, not matching.

Frozen current1692 members/50-sector classification and prices are non-PIT. Results separate capital risk from pre-event exposure improvement and do not establish that larger buying is worthwhile.

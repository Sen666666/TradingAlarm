# Two independent birth-cohort shared-account plan (NOT EXECUTED)

This is a planning document only. No cohort account run, additional dates, or parameter search was executed. Proceed only after the parent accepts independent review of execution_bridge_v1 and freezes the next run.

## Fixed cohorts, identical frozen contract
1. 2022 birth cohort: independent seed cash CNY1200000, flat start. Use original 2022 event window only, initialization at 2022-01-04; first legal signal is Jan5 and first conditional OPEN Jan6. Original legal event rows span Jan5 to Dec30, 2022. Follow admitted original rounds, original exits/claims and permitted one ADD through 2026-06-30. No new 2023–2026 birth universe is invented.
2. 2024 autumn birth cohort: independent seed cash CNY1200000, flat start. Exact original WINDOW=2024_924, START=2024-09-01, BIRTH_END=2024-12-31. First common initialization/signal date is Sep2; first conditional OPEN Sep3. Follow this cohort to 2026-06-30 with its original 2024 equity consumer and unadmitted-action boundary.
The two wallets never share cash or claims. Results are cohort-conditional historical experiments, not one continuous 2022–2026 all-market strategy.

Do not change M3 A+B eligibility, common-known denominator, I permit, PVR/top-two CLOSE selection, initial-only close_q ceiling, fee-inclusive round INIT/ADD2% / slot4% / risk0.25% of frozen first-signal Nd, cash reserve10% / stock10% of daily planning NAV, or effective-NAV probe10%/0.5%, industry probe ALL2% / confirmed ALL10%, industry ALL nominal-risk1%. Confirmed10% remains a research parameter, not user-selected or optimal. Keep same-phase proof snapshot, original held-state ADD order, global PVR/sid initial order, reserve ALL before conditional fills, one successful ADD, no third-name refill and no native E0/attempt gate.

## Before a cohort run
- Freeze exact source hashes, new run-specific engine/driver code, cohort, dates, seed, parameter contract, outputs and runtime/resource budget in an exclusive STARTED record before source load or account advancement.
- Confirm 2024 callback compatibility with its full original equity wrapper, beyond current exact unadmitted-function unit coverage. Reuse original functions and financial events, not a copied accounting implementation.
- Optimize only data structures and audit writing described below in a new version. Re-run the existing 13 synthetic groups, original held snapshot equality and fixed Jan6/7/10 path against the sealed prior outputs. No new economic sample or parameter variation is needed for that equivalence check.
- Full run writes a new isolated directory per cohort. Never overwrite original no_budget, reservation v3 or execution_v1 outputs. All failures/incomplete runs retain explicit status and last completed date.
- Checkpoints are deterministic end-of-day snapshots including archive/claims, layers, order state, consumed CP identities, pending intentions, frozen Nd and every source/code hash. Checkpointing cannot backfill failed opportunities or reassign order priority.

## UNKNOWN and valuation policy
Preserve every archived quantity, original cash flow, cost, protection, claimed entitlement and order responsibility. A liability-bearing UNKNOWN makes total NAV uncertified; never substitute zero, forward-fill the last price as a certified current price, or treat missing inventory as free capacity. New buys and promotions stop globally. Other known held stocks may continue original exits; already confirmed claims still accrue/pay on their source clocks and never migrate into a new round's profit.

Original UNKNOWN is not an automatic temporary strategy cooldown. Do not invent recovery/reentry for that round. An explicit later source repair would require a separate adjudicated version. Fresh unrelated legal signals cannot override uncertified whole-account NAV. A proven never-filled, current-round liability-free initial UNKNOWN retains that stock's original UNKNOWN lifecycle while other archived liabilities are accounted separately.

Output known cash, confirmed receivables, all known quantities and partial known inventory marks with a clear uncertified flag. Once a day is uncertified, an all-period certified return, drawdown or Sharpe must not bridge it by filling a number. Report the certified prefix and unresolved responsibility instead; do not choose a later endpoint to improve results.

## Required separate analyses
- First-probe layer: actual core fill quantity, own initial cash/fee, layer-held days, original core I exits, registered core dividend entitlement and allocated share of eventual whole-order fees.
- Full original stock round: core plus at most one ADD; cumulative actual buy/sell cash flows, recognized own-round receivables, inventory, all actual dated fees and original NET80 profit checks. Old-round claims never improve a new round.
- Pool migration is a classification event, not a cash trade or a new round. Separate qualification, original remaining-round risk zero, shared budget shrink, admission rejection and fills.
- A whole sell order incurs its minimum/dated fee once. For layer-attribution reporting only, propose allocating that one actual fee pro rata by shares (residual goes to a fixed named layer so allocations sum exactly). This reporting allocation must be frozen before computation; it cannot change routing, cash, profit gates or taxes.
- Register core/add quantities at their actual record CLOSE, attribute core amount from original core_record_q and ADD from the difference. Ex creates receivable, pay transfers cash at CLOSE, next OPEN can spend it. Unpaid recognized entitlements stay with their original closed/open round and the wallet.
- Terminal live stock quantities remain open/censored, not fabricated sales. Report gross-mark wallet NAV separately from original round hypothetical net-liquidation marks. Whole-order sell fees make those two valuations different.
- The old independent per-stock consumers can label source events, ownership and mechanism differences. They are NOT same-funded portfolio return benchmarks; do not import their win rate or PnL into this wallet.

## Static workload evidence and performance risk
Only existing source tables and finished bounded artifacts were read for this estimate:
- 2022: 12917 legal event rows, 1458 distinct stocks, 1084 common sessions from first legal Jan5 to terminal, plus Jan4 initialization.
- 2024 autumn: 6878 legal event rows, 1614 distinct stocks, 439 common sessions from Sep2 to terminal.
- Bounded three-OPEN author run: 17.74 seconds including source loading, hybrid source equivalence, two broad future-data pollution tests and exports; 6674 quantity-trial rows; roughly3.89MB output. This is not a full-period speed benchmark.
- Prior original no_budget full runs were about51s and41s, but lack shared bookkeeping and cannot establish new engine runtime.
- Current reconcile loops every archive and calls a full layers scan for each kind: O(R*L) per checkpoint and fill. R can be larger than the old consumer's round count because shared no-fills permit later fresh births. Static loose maximum R<=legal events and L<=2R makes naive repeated scanning unsuitable to promise a minute-scale run.
- Current full trial traces are retained in memory and duplicated in OPEN/AUDIT output. Large runs could become memory/output-bound even before compute.

## Proposed scaling work, without changing decisions
Use an indexed layers_by_round and active_round_by_stock structure, with immutable layer/action IDs. Keep slow recomputation as an independent daily audit option and compare indexed totals on the existing bounded tests. Index claim ownership and distinguish closed-but-unpaid archives. Do not discard archives to improve speed or globally patch source budgets/cache.

Stream complete quantity-trial and phase audit rows into append-only, exclusive run files with offsets/counts and hashes, instead of duplicating all rows in memory. Keep every tested quantity and rejection reason auditable. Preserve deterministic source order and Decimal arithmetic. Derived compact summaries must link to the full trace, not replace evidence.

## Estimated schedule, not a benchmark promise
- Indexing/audit-stream implementation and regression: approximately1–2 hours of engineering plus independent review, depending on source-wrapper findings.
- After bounded equivalence passes, provision a planning budget of about5–30 minutes per cohort for execution/exports, plus post-processing and review. This is a deliberately provisional resource estimate; no full shared runtime has been measured. The unoptimized version can be much slower, potentially hours, and should not be launched just to discover the quadratic cost.
- Freeze an explicit wall-time/memory/output budget with the parent before the full runs. If exceeded, mark INCOMPLETE at the deterministic checkpoint and report exact progress. Never silently change dates, sample, formulas, eligibility or trace completeness to finish faster.
- Execute one cohort at a time; report meaningful stage completion/failure, then independently audit source hashes, layer and round cash, all rights, UNKNOWN liabilities, queue order, caps and final certification before interpreting results.

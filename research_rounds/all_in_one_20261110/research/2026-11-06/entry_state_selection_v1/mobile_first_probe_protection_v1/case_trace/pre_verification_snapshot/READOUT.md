# Fixed-14 MOBILE first-layer source trace

This is a fixed historical-label mechanism development set, not an out-of-sample test. No account, E0/I/CP calculation, strategy, threshold search or alternative consumer was run.

## Main facts
- 6 of 7 fast failures already breached the immutable BUY floor at the actual trigger; Gree 1542 is the sole raised-floor-only fast failure. Jiangfeng 2897 also breached its unchanged initial floor.
- Gree last raise was a fresh CP receipt formed during its own holding period; verify exact receipt start in CASE_SUMMARY and FLOOR_RAISES.
- All 13 CP-protection exits had I still valid at their trigger. Ningbo 361 instead had I invalid and an I_structure_exit.
- All saved held-day floors reproduce exactly by old-floor test before same-day max(I, CP) updates. The calculation does not rerun account behavior.
- Jiangfeng had no observed stock bars between 2026-01-29 and 2026-02-06. Its immediate next common open is UNKNOWN; do not describe its 2/6 fill as the 1/30 next-open gap.

## Cash and timing
- LOSS_BRIDGE is a signed arithmetic loss decomposition using original per-layer net-cash allocation: entry gross to trigger-day effective raw floor; floor to trigger raw close; close to first observed next open; any first-open-to-actual-fill drift; sale slippage; buy/sell fees; minus dividend accrual. It sums to negative first-layer net P&L.
- Adjusted floor is divided by trigger-date factor, never compared directly to raw traded prices. These 14 selected first layers have no split and retain exact buy-to-sell share quantity. Corporate-action factor changes and dividends are explicit.
- The actual sell allocation for 2898 uses 2,200/2,800 of the combined fill fees; the additional 600-share layer is not treated as first-layer cash.
- No same-day sells occurred. A trigger on the buy day (2891) still executes no sooner than next OPEN.

## Follow-up evidence
- POST_EXIT_20_COMMON_CLOSES includes exit-day close separately as offset 0, then exactly min(20, remaining observation period) COMMON closes. Stock missing bars are explicit and fresh I requires a same-day observed fact.
- Fresh CP/I, original opportunity barriers, original OPEN funding and actual later BUY fills are reported. Their funding history cannot be reused as counterfactual feasibility after changing an exit. Exit-followed-by-rally is not labeled a mistaken sale.

## Boundaries
- The previously stated 577 was a typo; the parent-supplied saved group boundary is 578 CP-initial-layer exits among closed negative EXIT_BEFORE20 rounds. This report does not expand to new all-population simulation.
- SOURCE_PREFLIGHT and SOURCE_HASHES bind reused sources. CASE_DAILY has exact floor provenance; FLOOR_RAISES lists each raise with canonical receipt formation start.

## Cases
- 27 000877.SZ: CP1_add_protection; initial floor breached=True; I valid=True; last floor=CP1 2022-01-06; first-layer net=-1184.1527848937500.
- 17 000963.SZ: CP1_add_protection; initial floor breached=True; I valid=True; last floor=BUY_initial 2022-01-04; first-layer net=-2946.1280738932500.
- 28 002050.SZ: CP1_add_protection; initial floor breached=True; I valid=True; last floor=BUY_initial 2022-01-04; first-layer net=-2234.6184045943000.
- 1527 601918.SH: CP1_add_protection; initial floor breached=True; I valid=True; last floor=BUY_initial 2024-01-04; first-layer net=-56.9131828243000.
- 1542 000651.SZ: CP1_add_protection; initial floor breached=False; I valid=True; last floor=CP1 2024-01-16; first-layer net=-132.0450035447500.
- 2891 002195.SZ: CP1_add_protection; initial floor breached=True; I valid=True; last floor=BUY_initial 2026-01-14; first-layer net=-2544.7071691891000.
- 2893 600498.SH: CP1_add_protection; initial floor breached=True; I valid=True; last floor=BUY_initial 2026-01-14; first-layer net=-2032.9409055295000.
- 343 300034.SZ: CP1_add_protection; initial floor breached=False; I valid=True; last floor=CP1 2022-08-10; first-layer net=5514.9605698185000.
- 361 600366.SH: I_structure_exit; initial floor breached=False; I valid=False; last floor=I 2022-07-07; first-layer net=6541.3144114140000.
- 1942 300442.SZ: CP1_add_protection; initial floor breached=False; I valid=True; last floor=CP1 2024-10-08; first-layer net=5804.4663065440000.
- 1952 601881.SH: CP1_add_protection; initial floor breached=False; I valid=True; last floor=CP1 2024-10-08; first-layer net=5290.3351175624000.
- 2898 002716.SZ: CP1_add_protection; initial floor breached=False; I valid=True; last floor=CP1 2026-01-29; first-layer net=9906.1020265103000.
- 2905 600482.SH: CP1_add_protection; initial floor breached=False; I valid=True; last floor=CP1 2026-03-06; first-layer net=7989.4422899743000.
- 2897 300666.SZ: CP1_add_protection; initial floor breached=True; I valid=True; last floor=BUY_initial 2026-01-15; first-layer net=-1405.2665018008000.

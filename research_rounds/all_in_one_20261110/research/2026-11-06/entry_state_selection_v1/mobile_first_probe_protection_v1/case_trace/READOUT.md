# Fixed-14 MOBILE first-layer source trace

This is a fixed historical-label mechanism development set, not an out-of-sample test. No account, E0/I/CP calculation, strategy, threshold search or alternative consumer was run.

## Main facts
- 6 of 7 fast failures already breached the immutable BUY floor at the actual trigger; Gree 1542 is the sole raised-floor-only fast failure. Jiangfeng 2897 also breached its unchanged initial floor.
- Gree last raise was confirmed on 1/16 with anchor 1/9, before its 1/10 OPEN fill. Its new advances are 1/10, 1/15 and 1/16 CLOSE, all post-fill; previous receipt is the 1/9 entry signal, and the advance-ID overlap is zero. Anchor-before-fill is not evidence of pre-fill or reused credit.
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

## Verified source and exposure appendix
- All 7 fast failures had CP-dominant initial max(I,CP). The only I-dominant initial floor among 14 is Ningbo 361, whose actual first exit was I_structure_exit.
- Every CP floor-raising receipt in the 14 paths contains only post-fill new advance observations and zero reuse of entry-receipt advance IDs. CP_ADVANCE_DATES lists the observations. Do not use anchor-day comparison alone as a credit-contamination test.
- First I invalidation within entry through the fixed follow-up end: TianShan 2022-01-25, HuaDong 2022-02-22, SanHua 2022-01-24, NingBo 2022-07-11, China Galaxy 2024-10-15. For the other 9 cases, I stayed valid continuously from original trigger to follow-up end. A later return to I=true does not erase an earlier invalidation.
- RunZe 1942 and China Galaxy 1952 both raised CP on 2024-10-08, triggered on 10/09 and sold 10/10. RunZe I remains continuously valid through 11/07; Galaxy I first becomes invalid 10/15 then later valid again.
- In all 14 fixed windows, actual original-account rebuys are zero. Fresh evidence and some signal-side legal opportunities occur, but original industry/cash/risk/capital barriers often prevent entry. They are not counterfactual funding evidence.
- PENDING_EXIT_WINDOW_DAILY reads the actual native raw-bar manifest and original SHARED_WINDOW records. Jiangfeng is missing 1/30, 2/2, 2/3, 2/4 and 2/5 native bars. No same-day OPEN is available; original code returns no window, while prior close 113.48 is the mark, not an executable quote. On 2/6 the actual recorded sell window has raw OPEN 113.58, price 113.523210, capacity 158736 and prior-volume last observation 1/29. This does not establish official suspension.
- The final POST_EXIT file separates original OPEN funding from CLOSE sizing; the first draft mislabeled a day-level list as OPEN-only. This was a label correction, not a change to original outcomes.

## Verification history
- failure_01_uncropped_future_tail retains the initial source-preflight failure and exact script. It compared unequal future tails, corrected by applying the original consumer cutoff 2026-05-15.
- pre_verification_snapshot preserves primary text before correcting the distinction between CP anchor and new-credit observation dates, plus the OPEN/CLOSE funding label. Corrected main files and FINAL_VERIFICATION are authoritative.
- Original account, signal/fact and CP files are unchanged. Original account simulations=0; indicator recomputations=0; candidate consumer tests=0.

- failure_02_derived_output_hash_check preserves the verification-bookkeeping failure: its immutable-source loop accidentally included intentionally amended derived summaries. Finalizer rechecked all original inputs separately and verified all corrected tables without rerunning the analysis or an account.

- Final field clarification: entry_price_to_initial_effective_floor_per_share means distance to max(I,CP); entry_price_to_original_CP_floor_per_share now means distance to the actual CP candidate. They differ only for I-dominant Ningbo 361. This is a reporting-field correction, not a sizing or cash change.

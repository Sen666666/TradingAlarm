# January follow-through read-only analysis contract

## Sources and boundaries
- PVR_ORIGINAL is the original native full account; DMI_FROM_2022JAN and DMI_FROM_2026JAN are independent branches. Original internal PVR labels are not relabelled in source files.
- No strategy events, new indicator computation, economic rerun, training, tuning, forced liquidation, additional entry gate, or unknown-data state machine is part of analysis.
- New branches may only be read for results after DONE and output seals. Script writes and derived artifacts stay in analysis_preparation or analysis.
- 2026 inherited the original PVR 2025 state, not the 2022 DMI branch. Prior daily history may only be read from the exact inherited original prefix and must be explicitly identified. No returns or events from distinct accounts are combined.

## 1. Account and calendar attribution
Show full account and annual NAV, drawdown with initial/high water anchor, fees and embedded slippage, spendable cash versus accrued receivables, gross and net inventory, stocks/layers, actual BUY/SELL fills. For 2026 also show January, February-to-May-15 and year-to-date mark-to-mark NAV contribution from 2025 inherited live layers separately from new 2026 layers. Closed lifetime round PnL never substitutes for calendar-period contribution. Reconcile each daily NAV identity, inventory from original marks, layer/round PnL to final account NAV, and cumulative fees to trade fees.

## 2. Fixed January cohorts and first BUY layer
All separate actual 0-to-0 rounds with first BUY during each branch's January are frozen members, including those already closed in January. State both rounds and unique stocks. Report January closed, later closed, still open, independent closed first layer, and data unknown counts separately. Complete-round denominator is only completed rounds; first-layer denominator is only closed first layers, even if their rounds remain open. Provide wins/losses/flat, mean win, mean loss, payoff, net PnL, count and PnL of complete fee-net >=30% tails. Complete round return uses every BUY gross plus BUY fee including ADD; first layer uses only its own actual BUY cost. Open marks are not wins or complete tails.

## 3. Same-stock later normal reentry
Maintain sid + opened identity, round sequence, first BUY, actual subsequent BUY/SELL and closure. January rounds are never duplicated as post-January successors. Later profitable reentry cannot overwrite an earlier loss. A January stock-set successor summary is separate, with account-specific membership; cross-arm union and identical sid + opened matching are labelled explicitly.

## 4. Cross-arm identities and actual participation
Compare PVR versus each DMI branch only within the relevant January cohort using exact sid + opened. Added/lost closed winners and >=30% tails are accounting observations, not causal paired-trade estimates. Keep full-account 2024-09-24 actual holdings/transactions and early-window six-session participation separate from January cohort coverage. For 2026 show actual Jiangfeng (300666.SZ), Kema (301611.SZ), and observed additional technology paths. No MFE is treated as actual participation or a winner.

## 5. Valuation and unknowns
For every final held security publish mark, last valid observed bar date, common-session stale count, quantity/value, action adjustment if any, and source reference. Reconstruct original valuation exactly; do not replace old marks. January 2026 Jiangfeng last valid 01-29 and 002969 last valid 01-23 are disclosed again alongside final May-15 checks. Missing bar reason is UNKNOWN unless source independently establishes it; never call missing bars suspension. Closed-bookkeeping unknown, right censoring, stale-mark exposure, and external historical tradability/dividend-payment unknown are distinct. Do not add a new UNKNOWN lock or remove completed rounds for arbitrary missing bars.

## 6. Interpretation and exposure
Same 2026-05-15 cutoff gives roughly four years of follow-through to 2022 January versus months to 2026 January. Do not describe them as equal maturity or infer out-of-sample superiority. Frozen future 1709-stock/90-industry pool is NON-PIT, conditional daily OPEN plus/minus 5bp accounting proxy, not an executable live record. Native ACT, shared cash, all-pool later signals, protection, exits and ADD remain as in the frozen execution contract.

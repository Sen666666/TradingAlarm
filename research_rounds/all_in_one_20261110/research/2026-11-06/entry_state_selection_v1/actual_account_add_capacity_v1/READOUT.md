# Fixed add-capacity diagnostic

Status: FIXED SINGLE-DESIGN DECISION-POINT CHECK. NOT A STRATEGY BACKTEST. NOT A WIN-RATE OR RETURN CLAIM.

Source account: account_comparison_continuous_v1/no_loss_add_v1/run_1200000.
Population: the 12 actual held-position additions filled on 2024-09-24 and 2024-09-25, plus the unfilled silver-stock 2024-09-26 candidate. Every row uses the ORIGINAL account's contemporaneous holdings and cost. Rows are NOT chained into a counterfactual account.

## Fixed formula before calculation
U = whole-stock known-open net liquidation after 5bp sell slippage and date-specific sale fees minus remaining average cost (buy fees included, dividends excluded).
R0 = the current round's first actual fill's fee-inclusive loss to its entry-known protection price, using entry-date raw units and fees. Frozen, not updated by later signals.
Candidate D_add(q) = q * buy_proxy + buy_fee(q) - q * protection_raw * (1 - 0.0005) + sell_fee_at_protection(q), floored at zero.
D_add(q) <= min(R0, U + 0.25 * R0), U > 0.
q_add <= actual shares already held, rounded DOWN to legal buy units; never exceed original admissible/filled quantity.
0.25 is a research hypothesis, not an optimized or validated coefficient.
Original stock signals, ranking, cash reserve, sector/probe/confirmed routing, pending-order reservations, exits and date-specific units/fees remain binding. A formula pass cannot override a native rejection.

## Results
12 actual additions: original cash 129382.9140674625 CNY; static new cash 53768.2899421606 CNY; arithmetically unspent 75614.6241253019 CNY.
9/12 have a nonzero proposed lot; 3/12 are zero (000563, 000935, 600061). U/2 with the same quantity ceiling admits 6/12.
Proposed new-layer stop-loss proxies sum 2513.6640846918 CNY versus original 8911.4116090607 CNY. This is not total account risk and not an executable stop-loss guarantee.

If all other original 9/24-25 fills were mechanically held fixed and these unused amounts were NOT reassigned, cash after 9/25 would arithmetically be 152145.2481347247 CNY rather than 76530.6240094228 CNY.
This is NOT an alternative account cash balance: changed fills alter later holdings, NAV, cash reserve, budget routing, ranking eligibility and substitutions. No released funds may be used retroactively to claim an unfilled order.

Silver 300085 on 2024-09-26:
Original held q=100; 2024-09-25 CLOSE U=-13.0898491; 2024-09-26 OPEN U=24.8697258179; R0=1121.9090111755; candidate raw protection=16.61263173165938; buy proxy=19.36968.
100-share D_add=287.59626806615; new cap=305.346978611775, versus U/2=12.43486290895.
The new R formula allows 100 shares in isolation. Actual original-account cash admits ZERO: available=76530.6240094228, reserve=76980.2033369423. No trade improvement is claimed.

## Failure identified without retuning
A permanent R0 ceiling freezes growth for positions opened with close protection and hence small R0, even after substantial later profit.
Examples: 601066 has U=1723.4791 but R0=241.4283, reducing 600 added shares to 100. 600927 falls 1100->100. 600061 misses even 100 shares by about 0.66 CNY of modeled risk.
This formula is NOT recommended for promotion. No coefficients or minimum-lot exceptions were changed after seeing results.

## Not the old experiment
Earlier dual_plus_half_profit_v1 tested D_add <= U/2 on independent shadow rounds. This diagnostic adds a frozen seed-risk allowance and a quantity-growth ceiling, uses actual shared-account decision states, and still makes no counterfactual-account claim.
Earlier half-seed reserve diagnostic changed initial quantities. This fixed 12-row check does NOT change original initial quantities.
The old R17 broad risk-sharing test is not reproduced here; its adverse selection/crowding-out warning remains relevant.

## Data and uncertainty
Fixed future 1709-stock universe; not point-in-time universe certification.
Known positive opening-price +/-5bp with historical tradability UNKNOWN; gap/limit/stop slippage and actual fill probability UNKNOWN.
Protection-price risk is a planning proxy; stop orders do not guarantee this price.
No files from the original account were changed. No strategy, simulator, or trading order was run by this diagnostic.

## Independent checks
The 12 rows' seed positions, fee schedules, R0, candidate protection prices and maximum quantities were independently recalculated and passed. The 12 held additions were net-profitable at both signal CLOSE and execution OPEN. Silver was NOT profitable at signal CLOSE, only at the next OPEN; this matches the source account's OPEN-only profit admission.
The generic quantity expression was corrected from max(minimum, held floor) to buy_floor(min(original_quantity, actual_held_quantity)); otherwise a post-split odd holding below the buy minimum could incorrectly permit a larger add than its holding. All 12 checked holdings are at least one lot, so reported numbers did not change.
SOURCE_HASHES.json records direct inspected inputs and the reproduction script, not a claim that the entire transitive simulator dependency graph or universe is frozen.

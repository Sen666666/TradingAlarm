# M3 A+B source-grounded shared research contract
This is an engineering contract, not a shared-account economic result. All original sources remain unchanged. Original A_UNION_B 2022/2024 no_budget replay is a regression of sealed per-stock scenarios. 2026 remains signal/first-event diagnostic, not a third equivalent equity consumer.

## Authoritative source choice and preserved strategy
Use original relative_priority_equity_run_2022_v1/engine.py and cash_equity_baseline_2024_v1/engine.py for their respective windows. Both AST-extract the original relative_priority_v1/simulate.py functions, retaining original within-industry PVR/sid, common-known A/B births, I permission, UNKNOWN, one profitable fresh-CP ADD, exits and fresh-event reentry. Do not AND M3 with native E0/industry active/level, use freshUP, or substitute native remaining-average-cost profit.
no_budget calls original reset(FULL)/run_window(A_UNION_B) with exact original fixed budgets and original OPEN recomputation. It never changes module NAV/INIT/SLOT/RISK or closecache. Shared-mode quantities and cache keys must be separate and explicitly include round limits; no global-budget monkeypatch is permitted.

## Newly frozen research scale, not user-chosen optimal numbers
Single round Nd = certified NAV at first signal CLOSE, unchanged for that round:
INIT including buy fee <= .02 Nd; ADD including fee <= .02 Nd; combined marked slot <= .04 Nd; original whole-round fee-inclusive planned risk <= .0025 Nd. Retain original ADD budget min(.02 Nd,max(0,.04 Nd-held_qty*known_raw_OPEN)) and original initial-layer risk algorithm with remaining round risk.
Shared-mode OPEN may not exceed frozen close quantity. This is a labeled shared-contract addition. no_budget retains original OPEN size expansion on favorable gaps.
All applicable limits constrain the same quantity. Preserve original additional stock capital <= .10 * daily current NAV; do not replace the tighter round slot with that cap.

## Exact account bases and caps
At allocation, gross current wallet NAV is actual cash plus known inventory raw-price MTM plus confirmed receivables. It is distinct from round net-liquidation profit.
N_eff = certified budget NAV minus unbooked live/cancel_pending buy fees minus this candidate's buy fee.
- Global PROBE capital <= .10 N_eff.
- Global PROBE nominal protective-line risk <= .005 N_eff.
- New PROBE candidate: industry ALL capital <= .02 N_eff; its numerator includes existing confirmed inventory/orders.
- Confirmed candidate: industry ALL capital <= .10 N_eff, a newly chosen research baseline, not user-chosen or validated optimal.
- Industry ALL nominal protective-line risk <= .01 N_eff.
- Cash retention: candidate gross plus fee <= min(available cash minus .10 daily current NAV, budget cash minus order reservations). The reserve basis is the original daily planning NAV, not round Nd.
- Stock capital: held_qty * known_raw_OPEN plus candidate gross <= .10 daily current NAV.
Passive appreciation beyond caps does not itself sell holdings; it blocks new risk.
Nominal protection risk and fee-inclusive original AB sizing risk are separate. They are not guaranteed realized loss bounds. The dated fee engine and original one-whole-sell-order fee remain authoritative.

## Shared daily phases, distinct from no_budget original per-stock loop
1. Original known exits for all stocks and effective settlements first. Do not call each stock's full held_open in this phase because it embeds ADD.
2. One common post-sell/pre-buy snapshot for same-round CLOSE and OPEN NET80 promotion evidence. Prepare all grants before any pool mutation, then commit stock by stock with quantities/costs/lines/cash unchanged.
3. Original legal profitable AB ADDs in preserved held-state order.
4. Current-day original industry-top-two A/B first probes merged globally by original PVR descending then sid. No sector dictionary order is promoted into a new economic policy.
5. Reserve ALL feasible buy orders in that fixed sequence before executing any fills. Live and cancel_pending amounts/fees occupy budget. Do not allocate a later order using another stock's observed fill/HLCV result, and do not backfill an industry's third name after OPEN failure.
6. Execute the prepared fills and reconcile actual post-fill NAV/slippage separately. Actual fills do not make allocation caps guaranteed ex-post thresholds.
CLOSE SELECTED_PENDING remains an opportunity, not a cash lock or real broker order.

## Original AB financial and evidence clock
Original accrue_day occurs before OPEN. register happens at CLOSE after held-close management; pay_day is at CLOSE tail and funds only the next common OPEN. Only owned core/add at the original register date creates claims.
AB mark = this round's cumulative paid trade/dividend cash plus this round's recognized receivable plus remaining inventory net liquidation using one dated whole-order sell fee. Both original signal-CLOSE and next-OPEN marks must be strictly positive for ADD/promotion, with M3 TRUE and post-first-fill fresh CP. No previous round's claim/profit or another stock's result is usable.
UNKNOWN state simplification must not remove archives inventory or claims. A noncertifiable asset freezes new probe/ADD/promotion; known protective exits and confirmed equity transfers continue. This is an evidence failure boundary, not strategy cooling.
T+1 is tracked per executed fill; no same-day added layer sale is authorized by an earlier core fill date.
Canonical CP source identities and their post-fill ordering need the real receipt/source adapter, not invented IDs.

## Implemented now and remaining work
bridge.py is import-safe and loads original sources only by explicit load_original. It performs unchanged no_budget regression, not account allocation.
prepare.py pins 37 original source/baseline files and source definition hashes, and seals nonempty event fixtures. Jan4 has 344 OTHER_UNKNOWN_OR_LEFT observations, zero legal births. First legal signal/execution pairs: 2022 Jan5/Jan6, 2024 Sep2/Sep3, 2026 Jan7/Jan8.
The actual shared adapter, reserve-all-then-fill clock, verified cross-day obligations, live original NAV/CP/equity bridge, cap sizing and shared first-day/account execution remain unimplemented until separately validated. Cloud synthetic v3 is retained as a bounded reference, not silently used as a complete original-risk engine.
NON-PIT static pool/membership, limited NET80 scenarios and historical orderability UNKNOWN remain.

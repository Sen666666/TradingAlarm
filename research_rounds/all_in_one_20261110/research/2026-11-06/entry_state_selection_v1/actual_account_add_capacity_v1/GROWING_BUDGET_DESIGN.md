# Growing profit-budget structure: design only

Status: DESIGN NOTE ONLY. Not tested on new decision points, not a replacement result, and no new account run. The preceding fixed R0-ceiling diagnostic remains sealed with its original failures.

## Structural change, not a fitted threshold
Do not make R0 a permanent cap on each future layer. R0 is a one-time seed-risk allowance. Subsequent capacity grows with CURRENT, verified whole-stock net profit, while existing additions and pending orders occupy that capacity.
For a potential later single fixed experiment, retain alpha=1 and beta=0.25 as explicit research hypotheses. They have not been optimized. Removing the hard min(R0, ...) ceiling changes the structure; it does not validate these coefficients.

At decision close freeze the fresh stock/industry signal and the original protection reference.
At next OPEN, after original sells, settlement and corporate actions, calculate from the actual ledger:
- Q: actual stock shares, with same-stock pending/exit checks.
- U: whole-stock conditional net liquidation at the known open after sell slippage/dated fee minus remaining average cost including buy fees. Dividends do not reduce cost; previous realized profit does not conceal a losing remaining holding.
- R0: fee-inclusive protection loss of the first actual fill in this position round. Frozen through the round, never renewed by a fresh signal.
- H: cumulative negative realized PnL plus applicable fees of true added layers in this round. Positive realized gains do not erase this debt.
- L: sum of remaining true-added-layer principal-loss proxies to their currently decision-known ORIGINAL protection points, with remaining buy costs and estimated sale fees.
- P: reserved added-layer risk of unfilled and cancel-pending orders. Do not release until acknowledgment.
All classifications use actual inventory BEFORE the fill, not kind='add'. A mobile zero-inventory buy is a seed, not an economic add.

Pre-candidate budget B = beta * R0 + alpha * max(U, 0).
Indicative available budget A = max(0, B - H - L - P).
For actual sizing, recompute U_post(q) at the SAME known open using the combined Q+q liquidation and combined remaining cost after the candidate buy fee. This subtracts the candidate spread and marginal fee drag instead of spending the same pre-fill profit twice. Pending fees must also be charged/reserved once.
Require U > 0, U_post(q) > 0 and original eligibility. Choose maximum legal q satisfying:
H + L + P + D_new(q) <= beta * R0 + alpha * max(U_post(q), 0);
q <= Q (rounded DOWN to legal quantity);
all unchanged native cash, capital, risk, sector/pool/routing, capacity and order-uniqueness constraints.
Reserve D_new and its actual cash atomically before the next candidate. Confirmed routing only changes budget ownership; it cannot manufacture cash.

This ledger prevents issuing a fresh beta*R0 allowance for every CP signal. Prior adds consume L; realized add losses consume H; pending risk consumes P. A profitable protected add can release some L as its original line rises. Cash proceeds follow the real settlement clock.

## Legal units and growth
No automatic minimum-lot override. If the minimum lot needs D_min, it becomes financially possible only when:
U_post(minimum_lot) >= (D_min + H + L + P - beta*R0) / alpha,
with U > 0 and all native constraints still satisfied.
A rejected old signal is not replayed automatically; a later fresh eligible signal is needed.
Shares can at most double at one fill. This prevents 100->5000 on one marginally profitable observation while allowing 100->200->400 on successive valid confirmations. A fast trend with too few new signals may still be under-owned. That cost is real and must be measured, not hidden.
Fully flat inventory and acknowledged empty orders end the round. Later entry follows the original epoch/evidence rules; old receipts and old credit cannot be replayed. Repeated new-round losses remain a separate portfolio issue.

## Important mathematical and trading limits
1. U is verified MARKED profit, not guaranteed or locked profit and not spendable cash. It can disappear with the seed position. This rule must not be described as 'only risking profits'.
2. If seed protection still exposes about R0 principal loss, the combined stop-loss proxy can be as large as R0 + beta*R0 + alpha*U before the unchanged native caps intervene. Therefore this does NOT by itself preserve an invariant 'never risk more principal than the original seed'.
3. If strict principal-at-risk must stay at the old fixed amount, retain a separate hard whole-stock/sector principal-risk ledger including all live and pending layers. Then growing marked U cannot create principal capacity unless protection/realized capital actually improves. In silver's unchanged wide-I core example, that can leave no new capacity. There is no algebraic way to keep every old exit, guarantee fixed principal risk, and freely spend the same unrealized profit.
4. Current drawdown of U shrinks B. Under unchanged exits this only blocks new adds and cancels unfilled orders subject to acknowledgment; it does not force liquidation or guarantee continuous risk compliance. Requiring forced deleveraging would be a separate exit-policy change.
5. Gap risk, limit moves, T+1, stop execution, stale/invalid price sources and adjustments remain material. Protection prices are not guaranteed fills.
6. The native account already shares sector nominal mark-to-protection risk and keeps a 10% NAV cash reserve. This new overlay cannot cure a negative spendable-cash balance. Nor does smaller sizing guarantee saved cash stays unused: later candidates can consume it. A dedicated cash-pacing/reserve design would be another explicit intervention, not silently appended here.
7. First probes are not rejected by feedback. Their original admission and size remain unchanged in this design; the separate issue of oversized mobile zero-position starts is not silently changed.

## Relation to prior work
Old dual_plus_half_profit_v1: D_new <= U/2, one add maximum, independent shadow rounds, fixed principal/giveback limits; it reduced failures and winners and was not promoted. Its U was cumulative round cashflow plus liquidation, unlike the current remaining-cost holding gate.
Old half-seed reserve diagnostic: reduced initial size; not this design.
This proposal shares the old profit-funded-risk idea. Its distinct untested pieces are an outstanding-risk/debt/pending ledger, no permanent R0 ceiling, quantity-growth cap and integration with actual shared inventory/cash. It is not claimed to be an entirely new family.

## Smallest next verification, if pursued
Read-only reconstruct H/L/P and R0 from the actual current-round ledger for the same 12 points plus silver. Check units, fees, no repeated allowance, and minimum-lot thresholds without computing a new account return.
Only after that, reconstruct an exact unchanged baseline boundary and use one predeclared continuous window, with actual old inventory and pending orders. No isolated zero-old-stock account and no parameter scan.

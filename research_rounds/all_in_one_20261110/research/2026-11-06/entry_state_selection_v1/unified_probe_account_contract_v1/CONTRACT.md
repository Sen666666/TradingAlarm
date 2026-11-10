# Unified first-probe account contract v1

Status: implementation and engineering tests, no full-window economic run. Baseline is continuous no_loss_add PVR. No original file or account is edited. Daily inputs only. Fixed future 1709-stock pool remains NonPIT; historical tradability UNKNOWN, corporate-action terms assumed preknown, OPEN known-O/same-price fill is a proxy and is not live-execution certification.

## Admission and state machine

- Q=0: any original legal CORE or MOBILE intent can buy only from probe. MOBILE remains MOBILE/add and retains its stock CP receipt consumption and CP/I exit semantics. CORE retains original epoch lock and I/core protection. A completed stop resets real quantity/cost, not CP consumption or epoch identity; a later legal fresh CP can re-enter as a new probe.
- Frozen decision NAV Nd: each first order gross <= 0.02 Nd; modeled planned loss <= 0.0025 Nd. Planned loss is LR.protection_risk(q,p,f,schedule,par) = max(0, q[p-f(1-slip)] + buy_fee(q,p) + sell_fee(q,f(1-slip))); p=known OPEN*(1+.0005). Risk is an admission forecast, not a guaranteed loss in a gap.
- Original frozen intent caps and budget still bound the order. A native CORE target formerly allowed up to 10% but is additionally reduced to 2% while flat. No fixed stock-count cap. Legal minimum/step remains native.
- All outstanding/open/cancel-pending probe orders and probe lots share original pool capital <=10% adjusted NAV and nominal risk <=0.5% adjusted NAV. Nominal risk is marked/current buy price minus protection, floored at zero, distinct from the per-order 0.25% fee-inclusive loss contract. Existing mark moves may exceed admission limits; this does not add new forced liquidation.
- Original cash >=10% decision NAV, spendable cash, stock <=10%, sector risk <=1%, sector capital, fees, order reservations and T+1/exits/corporate-action callbacks remain. Confirmed60 and total-account3% remain removed as in baseline. Historical loss budget remains record_only.
- Q>0: every additional order requires the original legal fresh MOBILE CP plus strictly positive stock-wide remaining-cost net liquidation profit, using known OPEN, sell slippage and sell fee. Buy fees enter remaining cost; partial sales retire average cost pro rata; dividends/past realized gains do not subsidize remaining shares. No extra CLOSE-profit test is introduced.

## Explicit promotion phase

Native OPEN sells, settles and syncs first. Before allocating any new buys, evaluate independently all prior-CLOSE original qualifying held-stock opportunities (original mobile_Q true, fresh same-day CP, no original barrier). This phase includes evidence whose original buy quantity/budget would be insufficient. It creates no artificial buy intent, no PVR rank slot and no cash.

Promote only if real Q>0, no real pending buy or exit, sector active/level>0/expand, original current episode/attempt and canonical CP validity hold, current known positive OPEN is strictly above the new CP/I effective line in raw-price units, and remaining holding net liquidation profit is strictly positive. CP confirmation time must follow the actual probe fill; same date CLOSE after OPEN is legitimate. Only positive probe lots of this stock/current episode/current attempt migrate. Other stocks, stale attempt lots, costs, roles, floors, T+1 units and account cash/NAV/global resources cannot change. jmeta and budget lots are updated together. Promotion candidates commute and must give the same final state in reverse order.

Promotion is independent of later buy reservation/fill. A valid promotion remains when extra buying fails for cash, units or caps. It has an explicit event record, moved layer IDs and net-profit proof. (stock, canonical CP, attempt) is separately deduplicated. It does not consume the native buy CP: a real buy request consumes that once under unchanged rules; a failed no-quantity route does not. There is no delayed replay of yesterday's signal. If there are no eligible probe layers there is no fictitious migration.

All generic sector migrate calls are non-migrating, including industry, cancel acknowledgement and route. Industry evidence updates only its authorization stage and native pending-order cancellations. Native confirmed request's former implicit migrate check is replaced with explicit held-stock, profitable current-CP admission authorization. The old original PVR buy ordering is unchanged; moving promotion before funding is an explicit changed account clock phase, not claimed to reproduce old economics.

## Preserved conflict: industry total capital

The original probe sector-capital check is ALL same-industry lots and pending orders <=2% NAV, including already confirmed holdings. Thus a sector with e.g. 10% confirmed inventory blocks another stock's first probe even if the global probe pool is empty. Main contract deliberately preserves this gate. This must be reported as industry capital rejection, never as absence of a stock signal.

A separately labeled prospective comparison arm could split sector authorization from probe occupancy: ALL sector capital stays within current industry level's 2%/10%/20%, while sector probe subpool stays <=2%; global probe10%/0.5%, sector risk1%, stock10% and other rules remain. This is a proposed second contract, not a main-arm change, not an economically validated improvement and not implemented in the main route.

## Verification requirements

Synthetic: flat CORE/MOBILE size/pool/fee risk; strict positive profit; industry & cancel callbacks never sweep; same-industry winning A cannot promote losing B; only same attempt; fresh CP identity and reuse; independent promotion on insufficient funds; open <= line rejection; order and pool/jmeta bridge; promotion ordering commutes; original industry ALL conflict; fresh CP re-entry; buy fee/average remaining cost/splits/dividend exclusion. First-day: all actual first orders probe; no first-day promotion at OPEN or CLOSE; pools stay coherent; cash and quantity bridge; HLCV future perturbation at OPEN leaves complete results identical. Original-source hashes unchanged. Later full-window research requires the reviewed contract and separate execution command.

## Engineering corrections and current limitation

The first engineering attempt failed only during restored replay of Jan 5 OPEN. Legacy PreparedRunner.restore uses dict.update and did not remove `_ix`/`_ixn` layer caches created after an empty-account checkpoint. Normal OPEN had completed, but its detail was not persisted, so no first-day success or trade count is claimed from that failed attempt. Original failed directory remains intact. Isolated restore now validates source/policy/provenance and removes only the four proven lazy keys (_ix, _ixn, _buy_filling, _deferred_buy_cancels) when absent from the checkpoint; any other extra state is rejected, then calls original restore. Account fill, inventory and T+1 methods remain unchanged.

Each promotion-only candidate receives an outcome, including missing/invalid OPEN, invalid factor/price domain, post-sell zero quantity, pending real orders, invalid industry or CP, and no matching layers. Missing market data remains UNKNOWN, not a claim of exchange suspension.

New user clarification about sectors having many right-side stocks is NOT resolved by this funding contract. Existing industry E0/CP qualification must not be described as satisfying an explicit stock-breadth gate. No new breadth threshold is introduced here; full-window economic launch is paused pending that separate contract decision.

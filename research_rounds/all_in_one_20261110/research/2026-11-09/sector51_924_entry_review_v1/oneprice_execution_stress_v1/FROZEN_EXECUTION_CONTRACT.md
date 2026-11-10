# Frozen one-price execution stress scenario, version 1

Frozen before inspecting any scenario account outcomes. Standalone sibling experiment. No real orders. All pre-existing artifacts remain immutable.

## Unchanged economics
The source baseline is the reviewed 1692-member, 50-effective-sector shared-CNY1,200,000 account. Reuse its complete frozen economic contract, all M3/common-known/A/B/CP/I definitions, quantity/fee rules, 2%/4% capital slots, 10% stock/sector/cash limits, ADD-before-SEED timestamp/symbol ordering, T+1, actual-fill CP consumption, NET80 entitlement and certified-source checks. Do not tune any parameter or substitute an old focus list. Each fact version is pinned with hashes. Full raw O/H/L/C equality is never an alpha, rank, plan or OPEN-intent input.

## Scenario gate and limits
Only after the OPEN batch's ordinary intended orders and reservations have been constructed, apply an ex-post gate: if all finite positive raw OPEN/HIGH/LOW/CLOSE prices of that stock/day are exactly equal as Decimal strings, none of its attempted orders fills that day. Missing required gate prices is an explicit blocker, not a guessed fill. Volume is not used by this gate. Other fills retain baseline raw OPEN times 1.0005 for buys and .9995 for sells and all dated fees. These slipped prices are accounting cost proxies, even when outside the day's H/L, not executable-price evidence.

This is a conditional, ex-post daily execution-accessibility stress scenario. Historical ST status, venue limit prices, auction/queue order and available opposing liquidity have not been reconstructed. Do not label a near-10% bar a verified limit-up/down. A constant daily bar does not prove an order could never fill. This is neither a real-time queue model nor a return lower bound.

## Whole-OPEN intent freeze, reservations and failure semantics
At each actual-state OPEN, first clone the complete prior actual state and run the unchanged baseline exit and buy allocator on that clone using original OPEN-known data only. This freezes the original ordered sell intents, original buy allocations and their maximum quantities before evaluating any same-day price-range gate. A baseline-rejected buy cannot be revived. A baseline-approved quantity cannot grow.

Then apply attempted sells to actual holdings. A rejected sell supplies no cash, retains exactly the unsold lots, and locks each lot for subsequent common-OPEN retry. Existing full-exit locks survive. T+1 unsellable lots remain locked. Do not invent sale proceeds.

Recheck original approved buy intents against actual post-exit cash/exposure and original rules. Only reduction or rejection is allowed after failed sells. Reserve all accepted buy costs sequentially before applying any buy gate; rejected buy reservations cannot fund later orders within that same batch. Use actual post-exit NAV/caps but never exceed the previously frozen original quantity. Only after all intended reservations are complete apply buy no-fills, and release unused reservations at batch completion, for use at a later time point. Record both original intents and actual reservations.

A no-fill SEED expires with no holding/attempt; it cannot replay the old A/B ticket. A fresh later valid A/B may create a new attempt. A no-fill ADD does not consume CP and does not increment historical actual ADD count; later planning may reuse still-valid CP under the original contract. No-fill SELL lots persist and remain exit-locked until a valid eventual fill. New paths can change future candidates, entitlements and funding, so do not infer a small total effect from a small initial seed.

## Fact versions and certification
Run actual held/pending preflight, not a blanket all-inventory admission. Missing actual exposed equity or source bridge stops and atomically rolls back the entire uncertified day, including stress logs. Inform the parent and equity verifier of new exposed facts. Each facts update gets a new run directory. Before extending, replay the prior scenario certified prefix byte-for-byte at the row level for all nine baseline families plus intent/reservation/no-fill logs. Verify inherited economic methods are unchanged apart from existing fact-version run/checkpoint wrappers. Never skip a missing fact or overwrite a completed run.

## Outputs and interpretation
Export full daily shared cash, receivable, gross/net liquidation NAV, all 50 sector exposures, orders, CP events, candidates/capital rejects, holdings, attempts, equity, pending, frozen OPEN intents, reservations and no-fills. Report baseline differences at matching certified dates and track all future ADDs within baseline attempts whose seed was barred; distinguish direct path loss from wider funding/re-entry effects. Highlight the post-2024-09-24 rapid market-wide rise as an important situation whose future speed, breadth, sector persistence and order accessibility were unknowable in real time.

Synthetic tests precede historical outcomes. They include same-bar gate, non-constant bar allowance, missing gate blocker, SEED expiry, ADD CP preservation/retry, SELL lock/retry, T+1, frozen batch cash, no fictitious failed-sale cash, full-day rollback, unchanged-gate-off baseline equality, and prefix replay.

# Native fast-entry contract: source audit

This is an input/implementation audit, not a new economic result. The new small-entry consumer is deliberately different from the old shared-account router.

## Original trigger and eligibility

- `case-stage-ledger-20261031/v3/joint_v3.py:213–219`: `Facts.packet(at,'I')` supplies native I-state securities. `event.Q` calls original S0 eligibility. `continuing.Q` calls the identical eligibility after replacing only buy_allowed with native market_buyable.
- `actual-risk-recovery-20261027/code/engine.py:31–47`: the packet substitutes native I target for stock trend and turns original buy_allowed into original availability AND exact-day i_buy. It does not manufacture an event from an I state transition.
- `rs-h1-execution-20261025/code/sector_stock_admission.py:185–220`: S0 checks common stock/sector readiness, buy availability, fixed selected cap greater than CNY 10bn, stock I trend, known issuer and sector, readable same-day stock H1, same-day sector observation and readable sector H1, and sector E0 trend. Any unknown wins over any separate false condition. PVR is not substituted into this Q check.
- `current_pool_bridge.py:298–365`: state lookup is as-of, explicit source gaps remain unknown, industry observation must be current, and H1 uses the exact session row. `history_runner.py:144–179` provides original source-availability and dated-market-identity checks for buyability.
- Continuing Q has no additional G-grade, G-ready, PVR>50, M3 or age gate. Native i_buy already embodies its original entry event policy. Do not restore older pilot.py confirmation gates into joint_v3.

## Native epoch and consumption

`joint_v3.py:216–219` increments a stock counter whenever `(bool(i_target), segment_id)` changes, including I-off transitions, and clears the watch. A current event.Q True installs that epoch in the watch. `244` admits CORE only when empty and its epoch has not been used. Native actual fill consumption is in `probe-pyramid-pilot-20261029/code/pilot.py:59–73`: only a positive CORE FillReceipt writes core_epoch.

The new input has `i_epoch` as the stable stock/segment/counter identity. `epoch_lineage_known` separately audits exact-day facts and complete raw source_kind/source_path/segment continuity since a known adjacent I 0→1. A missing boundary never becomes a new reusable epoch. This strict reliability field is not the old raw counter itself. Empty CP does not require an unused CORE epoch or a nonempty global watch.

## CP receipt identity

The numeric CP cache contains receipt booleans and candidate floors but not canonical identity. `cp1-evidence-trace-20261031/trace.py:30–58` reconstructs identity without recomputing the numeric CP model. It advances over the entire warm history and only filters emitted output by BEGIN/END at line 56.

Receipt ID hashes canonical series, fixed model scale/hash, source segment, original E0 episode identity, anchor observation and confirmation observation. The decision-evidence key and evidence signature independently detect conflicting duplicates. The numeric stock CP input uses I as e0_valid; the canonical trace's original_E0_episode is explicitly based on original E0. These are distinct source conventions and must not be silently conflated.

The original universe receipts directory covers 2025-07 through 2026-06 only. The already frozen 2022 export is `2022-normal-reference-20261031/inputs/MANIFEST.json` and `stock-receipts/`, with 16,932 stock receipts across all 1,709 names. The new full-history trace checks every 2022 exported field against that original inventory before supplying 2022–2026 identities.

## Role protection, held state and fallback

- `joint_v3.py:243–258`: CORE requires empty; mobile requires fresh canonical CP plus continuing.Q. Mobile can begin from empty and is stored as kind=add with initial floor=max(I floor, current CP candidate). CORE is tried before CP for the same stock.
- `joint_v3.py:224–240`: I false or ACT pause exits all roles. CORE has native I exit. Each CP layer first tests CLOSE <= its old protection line; only a surviving layer ratchets to max(old line, today's I floor, today's fresh CP candidate). A new higher line does not retroactively trigger today's exit.
- `joint_v3.py:308–323`: failed CORE preview/route can fall back to CP. Successful reservation blocks another role for that stock even if the later execution-window check finds no fill. Do not use future H/L/volume or final execution outcome to reshuffle the opening queue.
- Because CORE requires empty, a CP initial holding never receives a CORE layer while HELD. Original joint mobile can add on successive fresh receipts without a one-add or profitability gate, subject to account budgets. The new consumer instead deliberately retains the existing one profitable CP add rule, with total 4% slot and the same .25% combined plan-risk budget.

## Deliberate new-consumer constraints

The old `resize_core` (`lot-risk-allocation-20261029/code/study.py:42–54`) can size CORE up to 10% gross, bounded by .25% floor risk. The new study uses <=2% NAV including entry fee and <=.25% plan risk for both initial roles, recalculated at the next common OPEN with dated fees and legal lot rules. It is not a scaled old account result.

The old budget model (`budget_v3/model.py:227–232`) consumes mobile CP at request/reservation before actual fill. The newly authorized consumer consumes canonical CP only on a positive conditional fill. No fill, failed sizing and unselected candidates do not consume identity. A receipt remains an exact-day market event and is not automatically replayed tomorrow merely because it was not consumed.

The merged daily per-sector top-two PVR queue, A/B union, finite per-stock NET80 path and fill-only CP consumption are new consumer rules, not the old ACT/industry-attempt/pool/shared-account router. Source Q remains original. No raw budget-controller/account gate is silently treated as a market signal.

## Input outputs

- `ALL_MARKET_INPUTS_2022.parquet`: all 1,709 stocks on all 2022 common days, original event_Q and continuing_Q as nullable booleans with complete reason strings.
- `ENTRY_CANDIDATES_2022.parquet`: one stock/day row where event_Q=True, fresh CP exists, or an A/B market event exists. Still contains false/unknown qualification candidates for audit.
- `CANONICAL_CP_2022_2026.parquet`: all 2022 through 2026-06-30 receipts; `sid, day, cp_id`, formation interval, canonical IDs, signatures and explicit trace-known status.
- `STARTUP_MARKET_INPUTS.parquet`: seven preselected startup windows, every common day.
- `CASE_PREFLIGHT.csv`: nine fixed 2022 dates plus the seven startup windows' fixed first A/B, i_buy and CP dates. Each row is a role-specific independent close/next-open quantity check, not a fill or new lifecycle. A CP sizing PASS without fresh CP and continuing.Q is not a trigger; combine the gate columns. A factor change is identified for NET80 bridge review rather than fabricated as a fill.

All input source hashes, extracted-definition hashes and output hashes are sealed separately. The first attempt was interrupted during heavyweight native execution-array setup, before exports or economic work; the preserved log documents this. The current Q-only context calls the original methods on their exact required fields without constructing accounts, raw execution arrays, signals or indicators.

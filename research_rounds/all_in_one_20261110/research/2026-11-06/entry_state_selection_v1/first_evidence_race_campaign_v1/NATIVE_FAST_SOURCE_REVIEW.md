# Native FAST source review and D boundary

This is a source/input audit, not D economics. The earlier 33-permit A/B/C run was a technical sample. D was requested afterward. No full economic run or D result is implied.

## Native source contract
- `fast_entry_equity_2022_v1/lifecycle.py:79–89,115–117`: every positive I_CORE fill consumes `(arm,sid,i_epoch)`, including AB-origin I. Never reset the credit on a trial exit. Native upstream `probe-pyramid-pilot-20261029/code/pilot.py:59–73` consumes CORE only after a positive fill.
- `case-stage-ledger-20261031/v3/joint_v3.py:213–219`: the stock epoch counter advances on changes of `(bool(i_target),segment_id)`, including I-off. Event Q uses the original I packet and S0 admission. Continuing Q replaces only buy_allowed with native market_buyable.
- `actual-risk-recovery-20261027/code/engine.py:31–47`: I packet uses original I trend and exact-day i_buy. Do not manufacture i_buy from a transition.
- `rs-h1-execution-20261025/code/sector_stock_admission.py:185–220`: original S0 readiness, availability, cap > CNY10bn, stock trend, issuer/sector identity, stock and sector H1 freshness, same-day sector observation and sector E0; unknown dominates false. No added M3, G, PVR>50 or age qualification. PVR is a separate original consumer queue condition, not S0.
- `prepare_inputs.py:112–130`: full warm native epoch plus separate lineage reliability. Missing boundaries cannot create new reusable epochs. Within an unchanged known I-root, the initial I fill has already consumed the same CORE epoch; fresh CP remains independent.
- `cp1-evidence-trace-20261031/trace.py:30–58`: canonical receipt identity hashes series, model scale, segment, original E0 episode, anchor and confirmation. Numeric CP validity uses I while canonical episode identity uses original E0. Those are not interchangeable.
- `CANONICAL_CP_2022_2026.parquet` has 99,031 identities, including 16,932 original-2022 exact matches. This input job reads it, never recreates it.

## Small consumer and D reuse
- `lifecycle.py:46–68,98–120`: I_CORE first, then MOBILE_CP only after known failure; unknown freezes. D recovery must exclude the `ab or fast` AB bypass and use native FAST eligibility only for CORE. No future outcome may select the role.
- Positive conditional fills consume identities; NOFILL, rejected sizing and unselected candidates do not. An unconsumed exact-day receipt is not replayable tomorrow.
- `lifecycle.py:159–186` and `joint_v3.py:224–240`: MOBILE_CP starts at max(I floor, CP candidate). Test the old line first; surviving holdings ratchet to max(old line, current I floor, current fresh CP candidate). Preserve the CP role after confirmation.
- `lifecycle.py:91–95`: initialfloor must bridge by old_factor/new_factor on a verified corporate-action coordinate change. The baseline engines only bridge addfloor/addpending, so the D wrapper must preserve this extra field.
- Use the existing small consumer <=2% NAV including entry fee and <=0.25% plan risk, dated fees/lot rules, next common OPEN recalculation, and campaign available cash. Do not import old shared-account CORE sizing up to 10%, ACT routing, account budgets, additions or cross-stock top-two allocation.
- Initial D entry remains the exact original I first fill. Recovery only adds native legal CORE/fresh CP, not C AB events. CP and CORE identity consumption persists across attempts in the campaign. No shared account or additional layer.
- Parent confirmed that each recovery restarts TRIAL; signal-day CP never counts as post-fill confirmation. Native role protection and trial exits retain the first pending exit, without erasing role protection.

## Input implementation boundary
`native_fast_inputs.py` copies the Q-only context and original method calls from the existing prepare_inputs.py, expands output dates to every 2022–2026-06-30 common day for all 1,709 original pool symbols, and preserves the full warm-history epoch calculation. It reads only market/source inputs and existing CP identities, not economic outcomes. It does not call the old main, rebuild indicators, execute accounts, or write old files. The full daily cache supplies signal-day epochs even on non-candidate days. Every comparable column and candidate membership for 2022 is checked against the frozen original market and candidate tables before output.

All file writes are restricted to first_evidence_race_campaign_v1. Source/output hashes and reconciliation are separate audit artifacts.

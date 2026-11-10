# Source inventory and proposed API mapping

Evidence type: parent-read source semantics, relayed in collaboration on 2026-11-09 UTC. This worker could not read the Mac source independently. Original-source SHA256 values are NOT VERIFIED; none are invented. Line references below are the parent's supplied references, not this worker's independent citations.

## Original sources to pin after reconnect

Root R: /Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1

- R/m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/engine.py: original per-stock/layer equity event register; ex creates receivable; pay CLOSE makes an equal cash/receivable transfer, available next OPEN. Register own core/add only.
- Same directory /run.py and /READOUT.md: 2022 A_UNION_B reference; preserve old fixed per-stock budgets and limited NET80 facts, not a shared account. Do not substitute freshUP.
- R/m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py: exact prefix/location to verify after reconnect. Parent read function semantics below.
- R/m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1: exact contained files to verify; use for 2024 rather than silently reusing 2022 accounting.
- R/unified_probe_account_contract_v1/: parent reports completed synthetic/Jan4–5 author tests and parent-supplied hash 755547e59cce871762523167bf21006033260291d6f0e613876d5c063aa5bc02. Not independently hashed or imported here. Useful as shared-account responsibilities, NOT a replacement strategy lifecycle.
- 2026 source: diagnostic only, exact file inventory pending.

## Function/responsibility map (names on the right are proposed adapters)

- simulate.py:45–59: PVR descending/sid within industry -> collect_original_ab_intentions() plus retain_original_industry_top2(). No synthesized breadth gate.
- simulate.py:100–107: size constrained by buy-fee-inclusive cash budget and risk -> original_size_at_open(). Wallet takes its final Decimal charges; it does not choose qty or line.
- simulate.py:109–123: initial-entry CLOSE sizing/check only -> collect_original_initial_close_size(). This is NOT the full-round CLOSE profit check; see 191–214 for that and 158–190 for OPEN profitability.
- simulate.py:143–157: OPEN INIT/RISK/priorcap recomputation, not min(close_q) -> original_size_at_open(no_budget=True) or separately labeled shared_close_q_ceiling mode. Wallet has no sizing method.
- simulate.py:158–190: sells before at-most-once ADD, mark > 0 and OP > line -> apply_original_exits_before_admission(), collect_original_add_intentions(). Wallet record_exit receives known verified deltas; queue follows.
- simulate.py:191–214: CLOSE I exit; CP ADD exit/line raising; sector == 1 + freshCP + net > 0 produces addpending -> apply_original_close_lifecycle(). No native multi-MOBILE substitution.
- engine.py equity registration/ex/pay (line numbers pending) -> emit_original_equity_events(). Wallet recognizes supplied claims and their effective-open settlement, without duplicating entitlement/rate calculations.
- Original archived UNKNOWN positions/claims -> export_all_obligations_including_archives(). Wallet keeps charge/claim entries and disables uncertified admission.
- Shared wallet current audited N -> freeze_open_snapshot(). Original single-cycle signal Nd stays attached to CycleLimits, never overwritten by later N.
- AB original close/open profitability plus executed-first-probe/freshCP/M3 -> emit_stock_promotion_grants(). Wallet promote_stock accepts one stock/cycle grant, preserving holdings except pool label.
- Parent-frozen merged all-market queue -> freeze_queue(queue, policy_ref). Wallet reserve_next(order_id) refuses out-of-order operations and never inserts a replacement.

## Compatibility requirements

The pure service budget_service_v3.py defines small accounting concepts, not an ABI claim about the unread original source. The source adapter and original integration tests do not yet exist. The fixed-budget no_budget branch must reproduce original old-consumer logs without shared close_q caps, cash scarcity or new NAV schedules. Only then should the separately labeled shared contract be wired. Do not equate those two results.

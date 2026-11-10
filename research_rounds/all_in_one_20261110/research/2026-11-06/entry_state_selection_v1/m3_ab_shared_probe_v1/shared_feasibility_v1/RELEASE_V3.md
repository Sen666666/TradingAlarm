# Bounded shared initial-OPEN feasibility, author release v3

Scope: source-derived proposal sizing and shared reservation arithmetic only. No shared fills, actual cash debits, PnL, return or complete account simulation. Independent review pending.

Authoritative files: limits_v3.py, test_limits_v3.py, run_first_open_v3.py, run_validation_v3.py, CODE_SEAL_V3.json and VALIDATION_EXECUTION_SEAL_V3.json. Older v1/v2 files/results are retained engineering drafts, not the current acceptance record. Original no_budget bridge seal and all original sources remain unchanged.

Results:
- Twelve mechanical tests pass, including input identity/status/quantity guards, holdings/order partition guards, gross NAV identity, UNKNOWN certification refusal, cash retention, industry risk, fee-adjusted pool risk, confirmed/probe capital separation, pending/cancel responsibility and old-round claim accounting.
- Original 2022 Jan5 selected 30 first probes are merged by PVR descending/sid and evaluated using Jan6 raw OPEN, original dated getmeta/fee/size and original quantity-rule buy_floor. Four reservations are fundable, 26 are rejected. All 30 stay in the ordered audit and no third-ranked industry replacement is inserted.
- The separate new CLOSE quantity ceiling reduces the single-stock quantity of eight proposals before shared gates. Each record separately exports old fixed-budget original_single_q, source_formula_q_at_round_nd, before_shared_caps_q and shared_q, plus minimum_buy_quantity and all tried quantity checks.
- Reserved gross capital is 33,452.718 CNY; planned buy fees 22.9672560866; reserved cash 33,475.6852560866. Nominal probe line risk is about 5,996.718 CNY, compared with fee-adjusted limit about 5,999.885 CNY. The bind here is nominal risk, not 10% capital. This is one deterministic engineering fixture, not a strategy result.
- All 26 final rejects include probe_risk; one also includes sector_capital at its original candidate quantity. Some accepted proposals are reduced by sector/probe risk. The output retains per-quantity details rather than assigning all shrinkage to a single rule.
- Cash remains 1,200,000 and actual shared fills remain zero. These are reservations, not actual or simulated executed positions.

Material unimplemented boundaries:
1. Generic original pending_bridge Q0 cash-coordinate entry logic and 2024 unadmitted_action_at ordering are not yet wired into reserve_initial. The frozen Jan6 fixture has zero admitted original corporate-action events on that date, zero selected event overlap and zero factor/source rejection, so it does not exercise or prove those paths. Do not use this initial planner as a general equity-admitted source adapter.
2. snapshot_from_ab assumes original known exits/accrual/settlements and coordinate bridges have already completed. It does not perform or certify them. All archives cash/receivable are retained, including old claims; UNKNOWN retains archived quantities and prevents certified NAV.
3. Source-factor acceptance uses original np.isclose rtol=1e-11, rather than the stricter abandoned v1 equality.
4. Actual original AB ADD/promotion proof and scheduling are not implemented here. Same-day entry OPEN followed by same-day CLOSE fresh CP may legally permit next-day OPEN ADD. Future adapter must use (day,phase) or known_at, not the invalid cp_day > entry_day simplification.
5. A naturally following held OPEN must still be tested. Perturb all same-day/future HLCV and same-day CLOSE-only I/CP/M3, retaining known OPEN and valid factor/equity metadata. OPEN actions/reservations/profit verdicts must remain unchanged. A synthetic raw_close-ignored snapshot check is NOT that real integration test.
6. Full unresolved cross-OPEN order persistence, original all-sells-first splitting, one common promotion snapshot, ADD-before-global-initial queue, reserve-all then fill-all commit and post-fill NAV reconciliation remain to be implemented and reviewed.
7. No shared full-period evaluation or economic conclusion is authorized by these checks. NON-PIT static membership, limited NET80 and historical orderability UNKNOWN remain.

Traceability:
validation_v3/ has exclusive STARTED, exact logs and RESULT. first_open_2022_v3/ has its own exclusive STARTED/log/RESULT and all plans/reservations/snapshot. The execution seal was written before execution. Nothing is backdated or overwritten.

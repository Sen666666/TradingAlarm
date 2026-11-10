# Structural maturity entry candidate: implementation reference

Status: research implementation and synthetic verification only. No historical replay, no new admission, no production or PIT certification. The inherited baseline is certified only through 2025-01-20. The unresolved 2025-01-21 000728 external-source 403 is outside this work and has not been accessed or supplemented.

The only strategy contract is ../mainline_structural_maturity_design_v1/DESIGN.md, SHA256 79ebeb73457914656eb70e4ecb59a58008e57d7cb92dd1296dd86d3577efbe12. This file does not amend it.

Baseline: ../mainline_m7_cash_batch_design_v6/engine.py, SHA256 ad0f77fb92d47af4046bf5ab7ef3b4f9b51451d4fe6a6b86a62163f35076a056. The loader is an exact class alias and was not instantiated. Model identity is the actual frozen CP model SHA256 85f21ad1622863645618f570b5f2e832558ebaca218ff2c71d0b4a0b545dd0bf. No model formula or reset rule is changed.

## Integration

- shadow.py is a standalone ENTRY_CP single-slot knowledge state machine. Receipt day includes the original signal CLOSE. It maintains persistent unknown gaps, permanent OPEN/CLOSE breaches, source identity, model identity, provenance, supersession and exact terminal identity. A new CLOSE receipt never sees that day's earlier OPEN.
- prepare_requests observes every original qualified A/B birth, preserves the original ticket/NAV/budget/event identity, and freezes phase, F and CP identity. Existing waiting tickets use the original daily refresh and actual phase recalculation. Structure tickets have their own constructor, without invented capital-cap failure.
- noncash enforces the same gate in M7 independent mature demand, CLOSE demand, OPEN receiver demand and the actual BUY reservation. A rejected MATURE request has q/cost/D=0 before capped allocation and cannot create donor demand. Original attempt/stock/dated-lot/I failures retain priority over the new gate.
- The current v6 allocator, including ST no-fill commit gates, has exactly one checked textual substitution: its retained-ticket outcome is dispatched to entry_open_outcome, which preserves STRUCTURE_WAIT/UNKNOWN instead of using the old non-capital cancellation for this new reason. All other quantity, cost, ranking and cash code remains unchanged.
- economic_preflight keeps all live waiting tickets in the original action/bridge/Q0 checks. Unknown text source sentinels follow the existing Q0 path; a localized copy of the unchanged gap loop uses the same known-source predicate. A known source change cancels, and matching terminal plans cannot reappear. For the existing single-day ST halt, an already-live same-identity ticket is captured through the original helper and removed from executable pending before Q0; the original new-request route is unchanged.
- Only preflight-verified or inherited CLOSE-bridge-verified current_factor is copied into the shadow. Its continuous-scale floor is not multiplied again. Waiting shares, dividend accrual and cash are zero.
- order writes only entry_evidence_id into the SEED order and ends the shadow. active.cp=None, confirmed_history=False and add_count=0 are asserted. Original post-SEED CLOSE CP, information confirmation, ADD and exits are unchanged.
- atomic_step snapshots every Engine attribute except the immutable input object, including logs, caches, identity maps and new state, as one deepcopy so active/archive aliases remain coherent. Any exception restores all of it and the caller's pending list. A retry from the same checkpoint is deterministic. This supplies a one-day primitive only; Engine.run explicitly refuses historical execution.

## Verification and limits

Run PYTHONDONTWRITEBYTECODE=1 python3 synthetic_tests.py in this directory for the 27 contract groups. Fixtures are artificial in-memory bars and fees. The only production model calculation is on artificial slow-rise, jump/flat and never-receipt series. No historical Data constructor, historical runner, account outcome comparison, network request, PDF/CNINFO lookup, approval file or RUN_STARTED marker was used.

STATIC_QA.json verifies the contract/model/baseline hashes and unchanged economic methods. SYNTHETIC_QA.json lists each assertion and group. SOURCE_HASHES.json binds this deliverable. The tests are technical admission evidence, not evidence of improved return, reduced drawdown or capture quality.

A separately authorized runner must explicitly choose the bounded certified calendar, call atomic_step with the original order of operations, preserve terminal pending when no future OPEN is available, and export into a separate approved run directory. This implementation does not approve or launch such a run. No M9/M10 overlay, shared risk pool, profit-coverage rule, principal guarantee, new timeout or return-based patch is present.

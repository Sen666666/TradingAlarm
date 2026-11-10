# Frozen synthetic release v3, 2026-11-09 UTC

Authoritative executable files:
- budget_service_v3.py
- test_budget_service_release.py

Authoritative reading order: this FROZEN_RELEASE.md, BOUNDARIES_AND_UNIMPLEMENTED.md, CONTRACT_DRAFT.md, then SOURCE_FUNCTION_MAP_V2.md. This release note corrects stale wording in the earlier drafts. budget_service.py is a retained non-importable first draft with a documented SyntaxError. test_budget_service.py and test_budget_service_v3.py are retained drafts, not the final suite. Nothing in those versions should be described as a passing source release.

## Corrections and exact boundaries

1. Parent-source function map correction: simulate.py:109–123 is the initial-entry close size/check, NOT the original full-round close profitability check. CLOSE full-round profitability is in 191–214; OPEN profitability in 158–190. All source line references are parent-supplied, not independently read by this worker.
2. Current wallet gross N uses certified actual cash, gross original-price inventory MTM and confirmed receivables. For a PROBE candidate the industry ALL capital ceiling uses current certified N, not the single-round frozen Nd. ALL means its numerator includes existing CORE and PROBE layers, not that confirmed ADD always stays below 2%. The single-round initial signal Nd alone is fixed for INIT/ADD/SLOT/fee-risk research budgets.
3. Every reserve_next now requires explicit allocation_limits. They contain n plus effective_nav_after_unbooked_buy_fees and absolute caps. The supplied global probe cap cannot exceed .10 times the supplied post-fee effective NAV; nominal line-risk cap cannot exceed .005 times it. probe_industry_all_capital_cap cannot exceed .02 current n. CORE/confirmed candidates use a separate explicit confirmed_industry_all_capital_cap. If that is None, confirmed admission fails closed; no particular real confirmed threshold is frozen here, and no native active/level eligibility is attached to M3. Smaller explicit caps may be used in mechanical stress tests, without changing the research contract. The source adapter, NOT this service, must reconstruct/reconcile current N and recompute paid/unbooked/pending/current-order buy fees before every allocation. That cash/gross-MTM/fee-to-N-to-cap chain is UNIMPLEMENTED and unverified. The code does not certify an injected Decimal just by calling it certified.
4. Final synthetic fee-boundary fixture supplies N=1,200,000, effective N=1,199,977.2 and nominal-risk cap=5,999.886. Exact supplied risk 5,999.08 is accepted. Supplied risk 5,999.90 is rejected although below 6,000. The incorrect cap 6,000 for that effective N is itself rejected. This validates arithmetic with supplied figures, not real fee calculation or original strategy replication.
5. ADD requires this frozen eligibility snapshot's same-stock/same-round positive CLOSE and OPEN NET80, post-first-fill fresh-CP flag and M3 TRUE, even if already CORE. A naked evidence_ref cannot authorize ADD. All such test proofs are SYNTHETIC external envelopes. Their source reconstruction is UNIMPLEMENTED.
6. Promotion requires an existing PROBE layer for that same stock/round and original proof. An all-CORE holding cannot be counted as a new promotion. A single stock transfer preserves supplied holdings except pool label. No sector mass migration and no peer-profit subsidy is implemented.
7. Passive price appreciation above a cap does not itself trigger a sale. New reservation checks reject additions that exceed any applicable cap. Known exits/settlements occur before the eligibility/NAV snapshot; that phase ordering is explicit.
8. The single-OPEN service does NOT restore live/cancel_pending obligations from a previous OPEN, persist state, or reconcile real asynchronous cancels/late fills/overfills. These are UNIMPLEMENTED; the synthetic single-OPEN cancel tests must not be called a complete account obligation system. Cross-OPEN transfer of add_used/round identities and inventory is caller-supplied, not a tested source adapter.
9. Ex claim registration and pay transfer retain original round_id. Old-round dividend cash affects total wallet cash but not new-round cashflow/claims. The test checks that accounting isolation plus rejection of a supplied negative new-round proof, not a reproduced AB NET80 calculation.
10. Per-fill T+1 is mechanically checked via external trading-session indexes. Quantity extraction, real trading calendar, original layer mapping and actual sell-order whole-fee allocation remain UNIMPLEMENTED.
11. Original input source versions, hashes, membership/PIT status and data availability remain unverified. Existing non-PIT/left-truncation limitations must not be cured by this synthetic scaffold. First-day real testing must locate a genuinely legal nonempty A/B event after reconnect; empty Jan4–5 output is not proof of integration.

## What passed and what did not run

The final twelve-test suite covers cash-not-frozen-at-CLOSE, known exits before admission, claim/pay clock and conservation, per-fill T+1, fee-inclusive buy budget versus separate risk dimensions, exact supplied post-fee cap arithmetic, partial-fill/live/cancel_pending obligations, probe/industry/round caps, one ADD and current proof, immutable external order and no third-slot refill, per-stock proof-gated promotion, old-round claim isolation, UNKNOWN freeze, Decimal validation and rejection atomicity.

Tests inject all evidence, including NET80 numbers, CP flags and certified NAV. Original lifecycle, real source adapter, no_budget parity, real first-day replay, original equity audit and economic results did not run. No market data or minute data is accessed. Original Mac files remain untouched. Files exist only in this cloud /tmp directory until an authorized transfer is performed and verified.

## Run final synthetic suite

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_budget_service_release

The final manifest hashes only the explicitly listed current code, final tests and evidence/contract notes. The parent may independently rerun this exact suite and review the recorded SHA256 values. This artifact is a scaffold awaiting source integration, not a production-ready account engine.

## Latest bounded fixes and remaining gates

- RoundLimits rejects any supplied initial/add/slot/fee-risk cap above (.02, .02, .04, .0025) times its immutable first-signal Nd. Smaller explicit caps are permitted for bounded mechanical tests. signal_close_ref and the limit object are frozen; the service has no mutation API for them.
- PROBE versus CORE industry limits are separate inputs. The existing-all-pools numerator is preserved. One synthetic CORE ADD above 2% industry usage is accepted under an explicitly supplied 10% mechanical fixture cap, while a new PROBE candidate in that same industry is rejected. This tests conditional accounting only: 10% is NOT adopted as the real M3 confirmed economic contract. Real confirmed thresholds remain to be frozen.
- Original shared model's 10% cash-retention gate is UNIMPLEMENTED. Nonnegative unreserved cash is not that gate.
- Original shared model's industry ALL nominal protective-risk 1% gate is UNIMPLEMENTED. Industry capital checks and the global probe 0.5% check do not reproduce it.
- The two omitted original gates must be preserved in actual integration unless separately and explicitly changed; this scaffold cannot be called complete reproduction of the original risk contract.

No more financial functionality is added in this release. The parent may independently check the frozen file manifest and twelve-test result. Current evidence proves only the bounded synthetic mechanics and explicitly declared rejections; it does not approve real execution or new economics.

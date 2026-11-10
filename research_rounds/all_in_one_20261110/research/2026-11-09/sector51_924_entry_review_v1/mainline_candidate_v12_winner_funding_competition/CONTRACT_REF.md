# M12 winner funding competition: implementation freeze

Authoritative contract: ../mainline_winner_funding_design_v1/EXECUTION_FREEZE_ADDENDUM.md, SHA256 3ffa6bd951e2377e65a83f9ee13bd3a2ed320970ed0f03fd277398e1b9856bd1, plus EXECUTION_FREEZE_FIELDS.json. This replaces the earlier active-donor-cap/joint-solver design. Baseline is unchanged mainline_m7_cash_batch_design_v6/engine.py, SHA256 ad0f77fb92d47af4046bf5ab7ef3b4f9b51451d4fe6a6b86a62163f35076a056.

## Executable interface

Engine.atomic_step(d, pending, prev) performs original preflight and accrue once; conditional OPEN prefix and complete-branch choice before any actual order; original actual exit and selected-branch allocation once; original CLOSE. All account, alias, log and new selector/wait state roll back on any exception. Engine.run is deliberately disabled. No historical launcher or approval exists here. A parent-approved runner must instantiate Data() with its original 2026-06-30 loaded horizon, then explicitly loop only 2024-09-02 through 2025-01-20 (93 days). No January 21 advance, new source, external network, production repo change, or financial transaction is authorized by this file.

## Unchanged native behavior

CLOSE sync/prepare runs once. Each nested new-MATURE-SEED subset independently reruns the original M5/M7 planner, including independent demand, capped_water, reference, exclusions, floor, donor ranking and sizing. It reuses the native allocator on a private scratch account. scratch has a shallow Data facade with private metadata cache; underlying price matrices are shared read-only. One joint deepcopy preserves active/archive aliases. The actual allocator, donor execution, exits, event roles, CP consumption, costs, quantities, Q0 and final no_fill methods remain inherited unchanged. No F/CP entry factor is added.

Only the lowest original full-ranked new MATURE SEED is successively removed. Common H is frozen at the true CLOSE anchor or OPEN-known predicted exit/info anchor. H requires native post-SEED confirmation proof, positive current net liquidation, unbroken current per-lot I/CP protection, and known original source/I/CP/donor fields; M=1 is not required. I target uses original integer/bool truth; CP receipt uses bool/np.bool_ handling. OPEN H uses prior CLOSE qualification and current OPEN quote/factor/lineage only, never current full-day bar eligibility or signals.

Branches freeze their own receiver bar_q_C, _ref_q/planned_q/econ_q/capacity, donor max_q/floor/rank and complete reference. q_hat_C is not an OPEN cap. Only CLOSE-pass suffix branches can execute; no cross-branch max/min or resurrection. Full-day no_fill only occurs after selection in the unchanged actual execution. Prediction/fill differences are diagnostics, never selection feedback.

Funding-withdrawn N retain the true original pending through preflight. Actual OPEN structurally and capital-legally valid N become explicit FUNDING_NONDISPLACEMENT_WAIT tickets preserving signal/identity/nav0/budget/source/I/event/phase. Original noncapital attempt/stock/structure failures cancel or reject normally, not a fabricated WAIT or REFERENCE_CAP. Original Q0 pause and future refresh/False cancellation remain unchanged. EVENT real attempts consume priority even without fills; scratch consumes no real state.

## Audit and limits

FUNDING_BRANCH_BOOKS, FUNDING_OPEN_DECISIONS, FUNDING_ACTUAL_DIAGNOSTICS, FUNDING_WAIT_LOG/STATE and FUNDING_PREFLIGHT export complete plans/projections and original execution evidence. clean() canonicalizes sets and numpy scalars for reproducible IDs. branch_id hashes retained/requests/plan/event_reserved/bar_q_C. book_id hashes all other book fields. CLOSE and OPEN scratch fingerprints assert no real state changes during projections. Actual prefix H is explicitly diagnostic only.

Synthetic PASS is not economic efficacy or PIT certification. The inherited OHLC no_fill model and net80/loader limits remain. The rule deliberately retains original phantom/integer funding residue. It cannot suppress unfunded MATURE seeds with no ADD/EVENT conflict; the December 5 robot case remains a necessary counterexample. Mainline winners among financing-day new seeds may be delayed. One frozen real-account experiment and independent cohort, ADD/tail, November 6 anchored PnL, winner giveback and cash-closure audit are still required.

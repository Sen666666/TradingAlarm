# Additional frozen boundaries and explicit implementation gaps

This supplements, rather than overwrites, the first contract. Latest parent guidance takes precedence where wording is less specific there.

## Frozen clarifications

- Original AB identity is round_id. No native industry attempt is introduced as an eligibility gate. Cycle/lifecycle wording in the first contract means this original round_id.
- Wallet NAV for budgets is certified cash + inventory at original unadjusted-price MTM + confirmed receivables. It does NOT deduct hypothetical sell fees. Full-round AB promotion/ADD profitability separately uses the audited original NET80 and actual dated whole-order sell fee. A wallet NAV is not an AB profit measure.
- Global actual cash = seed + actual paid cashflows of all rounds. The scaffold enforces that ledger identity. Claims are tagged to their own original round. Ex registration cannot increase available cash; settlement increases the old round's cash while removing its claim, preserving cash+claims and never adding the same income twice.
- In multi-layer sales, the original source must calculate one whole-order dated fee, not a separate minimum commission per layer. This wallet accepts already-allocated net cash and does not recalculate or certify that allocation.
- T+1 is per executed fill, not by the first fill date of the round. The synthetic asset service rejects same-session lot exits while allowing older lots from the same stock/round. It uses supplied consecutive trading-session integers, not calendar dates.
- Original cp[sid] evidence is receipt/candidate only in available parent context. Canonical original CP identifiers are unverified. All test proof references are explicitly SYNTHETIC; none claims a real CP id.
- CROSS-INDUSTRY QUEUE IS STILL AN EXPLICIT REQUIRED INPUT. The scaffold preserves the provided sequence and does not approve any particular real ordering.
- First real fixture must be nonempty. Parent inferred from freeze_events.py that a panel beginning Jan4 may label S=true as OTHER_UNKNOWN_OR_LEFT rather than a legal A/B birth. This has NOT been recomputed. Restore source access, inspect the first actual legal A/B event/execution day, and freeze that fixture, alongside explicit Jan4 initialization expectations. Do not fabricate a FALSE predecessor, issue a synthetic A/B ticket into real data, or call Jan4–5 empty output proof of integration.

## UNIMPLEMENTED or externally supplied, not tested as real AB integration

1. Original A/B/common-known calculations, source freeze_events, I/CP logic, three-window ticket generation, early signals, exit/re-entry and actual source loading.
2. Certification/reconstruction of N or Nd; gross MTM price sourcing, stale prices and UNKNOWN repair. nav_certified is an external evidence flag, NOT a proof produced by this module.
3. Canonical original round/stock matching across all source archives, actual CP identity/time and executed-first-probe proof. SYNTHETIC proof flags are plumbing fixtures, not adapter validation.
4. AB full-round NET80 reconstruction, actual close/open positivity, dated fee/slippage functions, fee allocation across layers, dividend entitlement registration and tax formulas. The module does not demonstrate them by accepting injected evidence.
5. Original size/round-lot rounding, priorcap/SLOT charge formula, current mark charge updates, share quantity, cost and line state. Explicit charge inputs are trusted synthetic values. Pool migration preserves these provided records; absent qty/cost/line fields are NOT verified.
6. Data-driven equity event clock and actual corporate-action records. Synthetic effective-session rejection and balanced claim transfer only validate wallet accounting, not the original engine's dates.
7. no_budget old-consumer parity and shared close_q ceiling implementation. Neither path is executable here.
8. Production persistence, broker reconciliation, externally overfilled orders, asynchronous events after an admission snapshot, and a complete multi-day account lifecycle. The scaffold models one OPEN and full-lot exits; partial fill obligations are supported, partial lot exits are not.
9. Real shared queue ranking and real initial two-slot selection. The module validates only provided slot identifiers and prevents replacing a frozen queue entry.
10. Original data integration, nonempty first-day replay, audited equity account results, economic returns, or a continuous 2022–2026 market history. No such results are produced.

The twelve synthetic tests validate mechanical boundaries only. In particular, the old-round-claim test checks accounting isolation and rejection of a supplied negative new-round proof, not whether a source adapter correctly reconstructed that proof. The T+1 test checks per-fill integer-clock enforcement, not original fill-date extraction. These limits must accompany any downstream use.

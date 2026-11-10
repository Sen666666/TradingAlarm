# Unified first-probe contract: engineering report

Implementation SHA256: 755547e59cce871762523167bf21006033260291d6f0e613876d5c063aa5bc02

## Scope and result

23 synthetic checks passed on this exact implementation. Original source files checked: 40; changes: 0. Only isolated research files are written. No full-window economic run, no trading orders.

Two-day first-entry check: PASS, see FIRST_DAY_COMPARISON.json and first_day_check_v2/SUMMARY.json.

Independent final review: **PASS within the limited first-day engineering scope**. This status is based on the completed independent read-only review report, now archived in INDEPENDENT_FINAL_AUDIT.md and INDEPENDENT_FINAL_AUDIT.json; this documentation update did not repeat the audit or run an account. The reviewer verified 421 candidate intents across 294 unique candidate stocks, both checkpoint binaries/metadata/provenance, equal normal/restored-future-perturbation payload hashes, all 44 run-freeze entries (40 original sources), and the four trades' fees/cash/NAV/admission limits. Separate dated-fee calculations without the LR risk function agreed within 2e−24.

The final PASS does not historically validate actual profitable-held-position promotion, corporate-action/equity events or T+1 sells because this first-day history has none. Those remain within applicable source/synthetic evidence only. It does not include M3/breadth gating or full-window economics. The original failure is preserved and the implementation remains unchanged.

## Retained failed attempt

The normal Jan 5 OPEN call completed, then restored/poisoned replay failed an inventory invariant. Its normal-event count was not separately saved, so this report does not attribute a count or success to it. first_day_check/FAILURE.json and checkpoint remain unchanged. Source diagnosis: native restore updates dictionaries but does not delete four lazy attributes created after a zero-inventory checkpoint. The isolated wrapper now permits cleanup only of `_ix`, `_ixn`, `_buy_filling`, `_deferred_buy_cancels` when absent from the checkpoint. Any unrecognized extra state fails; source/policy/provenance checks remain. The empty-checkpoint versus baseline-ending-checkpoint field difference independently equals those four keys. No native ledger method was replaced.

## Contract changes

All real Q=0 entries, including original MOBILE, use probe and frozen 2% decision-NAV gross plus 0.25% modeled fee-inclusive protection loss. Original roles, CP consumption, CORE epoch lock, original I versus CP protection, fees, dated units, T+1, corporate-action callbacks and PVR ranking stay.

Shared probe10% capital/0.5% nominal protection risk applies to lots plus unfilled/cancel-pending reservations. There is no fixed stock-count cap. Held additions require positive fee-inclusive remaining-holding liquidation profit and valid fresh original CP. Per-layer 0.25% is only the first-probe constraint; it is not quietly imposed on all later MOBILE adds.

Promotion happens in a separate snapshot phase after original OPEN sells/settlement and before unchanged PVR buy allocation. Every eligible stock is evaluated against one shared state before commits. Only matching profitable stock/current-attempt probe layers migrate, with pool/jmeta equality. Profit is not credited as spendable cash. A new stock CP must confirm after actual probe fill, and OP must remain above its CP/I line. Independent promotion does not demand an affordable new buy. Native CP buy consumption remains separate. Canonical evidence, missing OPEN, invalid factor, no position and pending-order reasons are auditable.

## Conflicts and limits not hidden

The inherited industry probe capital gate counts ALL same-industry holdings, including confirmed. Existing 10% confirmed exposure can therefore prevent another stock's new probe under the 2% gate. A distinct formula-only comparison arm is documented; the main route is not relaxed. Industry-upgrade cancellation of old outstanding probe orders remains native and does not release reserve until ACK or migrate another stock.

The user's new requirement that a sector contain many right-side stocks is a separate unresolved admission specification. Existing sector E0/CP is not claimed to satisfy it. No arbitrary breadth threshold was added, and full-window economic launch remains paused.

Fixed future 1709 pool is NonPIT; historical tradability is UNKNOWN. Daily OPEN-known/same-price execution is a research proxy, not a live executable claim. First-day mechanics and synthetic tests cannot establish profitability, drawdown, 35% win rate, or robust right-side identification.

## Artifacts

- CONTRACT.md: formulas, state machine, ordering, inherited conflicts.
- unified_probe.py: isolated adapter and exact minimal native opening/request derivations.
- SYNTHETIC_RESULTS.json, EDGE_CASE_RESULTS.json, REPAIR_RESULTS.json: test scopes and exact hashes.
- FIRST_DAY_COMPARISON.json: baseline versus new first-entry details when available.
- ORIGINAL_SOURCE_INTEGRITY.json: protected original file hashes.
- INDEPENDENT_FINAL_AUDIT.md / INDEPENDENT_FINAL_AUDIT.json: archived completed independent review and its exact limits.
- STATUS.json: limited first-day final-audit PASS; no economic completion claim.

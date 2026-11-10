# Conditional suspension integration, NOT installed or approved

Use only if the unchanged wrapper actually blocks on a held suspension. Do not replace M7 with joint v11, which predates mainline capital-reference decisions. No history run accompanied this draft.

## Verified boundaries and horizons

Joint v11 RUN_STATUS certifies 37 days through 2024-10-31 with no blockers. Its two officially sourced suspension rules cover only 300277.SZ on 2024-10-28..31 (last observed mark 2024-10-25, raw 12.02) and 002064.SZ on 2024-10-29..31 (last observed mark 2024-10-28, raw 8.11). Verified last mark includes exact source lineage and adjustment factor. Registry evidence hashes must be rechecked. Future notices or resumption dates are not decision inputs. v11 endpoint held 2,013 CNY stale assets and correctly left whole-account liquidation NAV undefined. That is v11 evidence, not evidence of M7 holdings.

All 1,709 manifest entries were inspected through their actual facts/CP index columns. Each family has 1,286 files ending 2026-06-30, 399 ending 2026-10-27, 22 empty files, one ending 2026-06-26 (601369.SH), one ending 2026-06-29 (603389.SH). Manifest cache_through is uniformly 2026-06-30, although actual files differ. KNOWN3, RIGHT3, PVR STOCK_DAILY each end 2026-06-30. Therefore 2026-06-30 is a shared-signal upper bound, not a certified execution horizon or a guarantee that all facts/tradability are available. Existing empty/incomplete facts must remain UNKNOWN; no future backfill. The first run should target 10/31 and discover actual blockers atomically. Later run endpoints must be admitted in a new wrapper, not overwrite this one.

## Minimal proposed rules

1. Keep observations missing. Never insert a stale pseudo-row into Data.z, copy a future quote, or turn stale price into a CP, stop-price, I-floor, capacity, winner or information-confirmation input.
2. Register only exact officially covered dates and anchored source/factor. Unexpected observed rows, missing registry coverage, source/factor mismatch, or corporate action during suspension without a separate verified bridge must block atomically. Accrue and pay already verified claims at original dates. Never invent dividends or use receivables as spendable cash.
3. A separate valuation-only mark supplies qvalue/NAV/holdings. Carry every held share in fixed F, zero mobile K contribution, zero donor quantity/stress, and frozen_lot_qty=full remaining quantity. Existing INITIAL/EXPANSION role and confirmed_history are preserved, but current winner/net is unknown. Do not call executable net() for the suspended stock. M7 D excludes suspended requests; E/W/waterfill/reserve rules remain unchanged.
4. Reuse v11 CLOSE suspension behavior: no price-derived CP invalidation, floor/stop breach, or ADD; preserve previously locked exits; known sector-false trial exit may lock exactly as in v11. No liquidation fill during suspension. Stops resume only under verified real tradable quotes, not synthetic backdated fills.
5. A donor planned yesterday that becomes suspended at OPEN is canceled for execution, emits a zero-fill diagnostic, contributes zero cash. Protection-exit cash estimates for currently suspended holdings are zero. Other donors in the same sector must use valuation-only fixed holdings in their OPEN floor, preserving every suspended share. Receivers remain CLOSE-frozen and OPEN can only shrink/cancel.
6. Order() hard-rejects any suspended trade. No CP consumption, lot mutation, fee, realized PnL or cash flow without actual fill. An unknown/nontradable holding must never be temporarily removed from active to dodge preflight, NAV, snapshots, or corporate-action checks.
7. Information confirmation needs explicit admission: proposed minimal rule is withdraw the provisional CLOSE proof when next OPEN is nontradable (matching existing next-OPEN validation lifetime), log OPEN_NONTRADABLE, preserve historical confirmed_history, and require fresh future valid CLOSE/OPEN confirmation. Do not defer an old proof indefinitely. This behavior is absent from v11 and must be independently reviewed before installation.
8. Whole-account executable liquidation NAV is null when any held asset is nontradable; separately label total marked NAV and stale value, plus tradable-subset liquidation. Marked returns/drawdowns are not realizable returns. Keep stale asset market value, dates, quantities and outstanding exits visible.
9. Add all new mutable suspension logs/state to atomic rollback inventory. Blocked-day partial activity cannot contaminate certified results. Preserve original M7 file hashes and all economic methods except narrowly audited accounting hooks.

## Required hook review

M3 classify_reference directly reads raw_close and calls net before UNKNOWN gating. M5 then recalculates mobile quantities from those rows. Both must honor nontradability without changing valid-quote paths. M4/M5 plan_transfers estimates protection-exit proceeds from raw_close; M3/M5 execute_transfers reads raw_open for both donor and same-sector fixed holdings. M1 info_open consumes pending proofs and requires real OPEN/net. Effective M6 close body, OPEN execution, ledger/holdings, economic_preflight and scan_restored_targets all need minimal branches. Use the effective inherited M7 methods, not textual replacement in a dead ancestor. Replacing only qvalue/exit_open with v11 methods is insufficient.

## Required tests before history

- No-suspension method/path identity and full original 10/8 prefix across economic output/state families.
- New-account suspension scenario: INITIAL plus EXPANSION holdings, M true and positive E; all shares fixed, no D, no donors, valid other-sector behavior unchanged.
- Suspended stock and tradable donor in same sector: OPEN floor includes stale frozen stock without dereferencing missing quote or selling it.
- Yesterday's donor becomes suspended: no expected proceeds credited; preplanned receivers shrink/cancel without reranking/new receivers.
- Existing locked stop/lot exit persists through suspension; no price-based new stop from stale mark; real resumption source/factor validation precedes any fill.
- Provisional information proof at suspension OPEN follows the approved expiry rule; no current winner/net inference from stale mark.
- Corporate action in covered suspension fails closed unless separately reviewed; unrelated already verified claim payments remain accurate.
- Registry wrong dates, lineage/factor mismatch, unexpected observed row, or unexplained missing held quote fails closed.
- Whole liquidation null; marked NAV reconciliation; nontradable subset cannot fund cash; suspension share/fee/PnL conservation.
- Forced late-day blocker restores every state/log and pending transfer exactly.
- Compare exact certified pre-stop prefix from this wrapper in addition to original10/8; then one frozen extension run to the admitted endpoint.

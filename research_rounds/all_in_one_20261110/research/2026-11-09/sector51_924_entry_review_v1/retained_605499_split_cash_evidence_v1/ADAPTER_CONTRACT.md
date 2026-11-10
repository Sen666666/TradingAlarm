# 605499 Q0 retained-ticket split plus cash fact bridge

Status: company facts and same-source factor identity verified; integration admission remains separate. No historical simulation, allocation optimization, held split implementation, or production trade performed.

Issuer announcement 2024-088 dated 2024-09-26 is retained as 605499_2024_088.pdf from CNINFO. Pages 1–2 give record date 2024-10-08, ex date 2024-10-09, cash payment date 2024-10-09, and newly unrestricted shares listing date 2024-10-09. Capital-reserve transfer is 0.3 shares per old share, plus CNY2.50 gross cash per old share. No differential distribution. This is not cash-only. Local actions retain null payment/listing dates; the reviewed fact adapter adds sourced dates without changing that source.

Factor bridge: new = old * 286.0 * 1.30 / (286.0 - 2.50). Source identity is unchanged across both observations: tushare_raw, daily_bars_history/daily_bars.parquet, segment0. Exact values and residual are saved in FACTOR_BRIDGE_QA.json. The adjustment series is research data, not proof of point-in-time availability or production admission.

## Integration boundary

Append this single event after existing cash-only Data loaders. Do not modify their split_ratio==1 assertions or call this a cash-only event. Hash-bind the fact adapter, PDF, signal and action files, match unique local action terms, adjacent calendar dates and lineage, and independently recalculate the split-plus-cash formula.

Before any ex-date economic mutation require: exact symbol/date; existing live never-seeded retained ticket; explicit recorded record-date snapshot with quantity0 (missing does not mean0); ex-date actual quantity0; no pending buy/request for this symbol; no claim/receivable or prior event accounting attributable to this event. Any changed scope raises the normal Blocked exception and triggers full day rollback. Do not continue after guard failure or silently fall back to ordinary cash-only accrual. Reject a held split even when post-ex shares would be sellable the same day.

M1 retained_ticket_preflight updates only current_factor and last_verified_day while preserving ticket identity, original signal day, original NAV, budget, original/current I-floor and source responsibilities. M2 quote-gap logic still owns unavailable-open pausing, same-source gap-chain verification, cancellation on source change, and no stale-open fill after recovery. The new bridge must not reset/replace ticket, seed a position, clear known-false signals, relax capital/lot constraints, or grant new priority. Unknown bridge still atomically blocks before any trade.

Base accrue iterates all admitted events and defaults absent snapshots to zero; this default is NOT sufficient evidence for the new exception. Base register_pay registers snapshots and settles claims. With explicitly proven Q0, both must produce no cash, receivable, entitlement or shares for this event. Require before/after assertions and zero record_qty factor-log entries. Add record-date guard at snapshot registration so unsupported holdings cannot pass simply because ex date is later. The wrapper worker owns complete integration and synthetic atomic-rollback tests.

## Are payment and tradability dates necessary at Q0?

For a proven never-seeded Q0 record/ex-date ticket, there is no entitlement, payment, new share inventory, or sellable tranche, so neither date is mathematically needed for factor-only bookkeeping. This does not authorize treating unknown dates as known, borrowing dates for held accounting, or weakening general admission rules. Here both dates are verified from the issuer, so no unknown-date exception is requested or implemented. The factor bridge still requires authoritative event identity/terms, record/ex timing and same-source factor continuity. Held or pending buys remain outside this adapter regardless of known dates.

## Required synthetic cases

1. Exact Q0 positive: only current_factor/last_verified_day change, no economic balance change.
2. Nonzero record snapshot: block before mutation.
3. Missing snapshot: block, never infer zero.
4. Nonzero ex quantity: block.
5. Pending request: block even if quantity currently zero.
6. ever_seeded or cancelled/consumed/missing ticket: block.
7. Existing claim or duplicated event: block.
8. Cash-only formula or altered split/cash factors: reject.
9. Changed source, mismatched old factor, missing/invalid current factor: no trade; preserve existing cancellation/block semantics.
10. Guard exception after prior unrelated day activity: full day rollback, not a partial continue.
11. M2 no-quote/recovery: no stale-open fill; full gap factor chain remains required.
12. Exact frozen prefix and frozen-file hashes remain unchanged. No historical continuation until separate admission.

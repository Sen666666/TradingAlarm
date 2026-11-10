# Bounded daily union diagnostic, version 1

## Scope and release

This is one new, historical conditional 2022 birth-cohort diagnostic, not the full 2022 strategy or continuous annual admission. It starts with the original 1,200,000 cash, the original 2022-01-01 to 2022-12-31 birth window, the original common calendar starting 2022-01-04, and the original follow limit 2026-06-30. It stops earlier at the first complete OPEN or CLOSE phase containing a new UNKNOWN with actual assets or outstanding responsibility. It must not start before an independent reviewer releases the exact PRE_RUN_STAGE_SEAL.json hash. Any byte change invalidates release. The permanent O_EXCL root lock and worker-start lock forbid retries, including after an error, interruption or hard resource stop.

Only daily data are used. No external collection, minute data, forced liquidation, source switching, parameter optimization, evidence shopping or automatic per-stock repair/replay is allowed. Original engines, evidence, accounts and seals are read-only. The complete original birth/event/source domain is preserved, without a fixed 1,406-name cutoff. No other halt or corporate action is admitted.

## Evidence and union

The original 436 event objects, evidence fields and permission restrictions are preserved. Their historical known-at limitations remain, and this union does not certify them anew. The 10 coordinate-only events retain no cash entitlement and no pay date. The only addition is 600403.SH|LOCAL_DISTRIBUTION_007, pure cash 0.35/source share, split 1, record 2022-05-11, ex/pay 2022-05-12. NET80 is the original research convention, not actual individual tax withholding.

The official May 5 publication date is conservatively bounded at Shanghai end of day. The new announcement is invisible through May 5 and may enter May 6's daily session. Its public object contains no future previous close or factor. The original time-local daily factor coordinate is read only at May 12 OPEN or later. EVENTS, EVENT_BY_ID, EVENT_AT, BY_RECORD, BY_EX, BY_PAY and ALLOWED_EVENT_IDS project the same old-preserving visible union. A visible announcement is in the catalog and record schedule before ex, but is not in executable coordinate/ex/pay maps until the ex observation is available. Duplicate IDs and same-symbol/ex-session conflicts are errors. Claims already owned by old rounds remain in the old maps and pay to those owners.

Only two full-day suspension sessions are licensed: 600595.SH on 2022-01-13 under the previously reviewed exact pre-open clock, and 600403.SH on 2022-04-15 under the verified April 14 19:28:57+08:00 news/fact pairing. Planned resumption is not actual price evidence. Validated same-day news must be strictly earlier than 09:30 Shanghai; equality and later are rejected. Official date-only publication must precede the session date. URL dates, effective dates and unverified date fields are not publication clocks.

The original source definitions provide registration at record CLOSE using actual CORE and ADD quantities, accrual and coordinate translation at ex OPEN, and transfer from receivable to cash at pay CLOSE for use from the next OPEN. The standalone conditional fixtures' 700 shares and 196 NET80 are never injected into the diagnostic account.

## Economic invariants

All original sizing, fees, calendar, daily qualifications, M3/AB permission, 2% initial/0.25% risk, probe 10%/0.5% limits and confirmed-sector 10% limits remain unchanged. Native OPEN completes exit processing, preflight, promotion, reservations and fills atomically at the phase level. Native CLOSE completes held CLOSE, record registration, selection, payout and reconciliation. No stop is inserted inside reserve/fill or before the remainder of the same original phase.

Known halt keeps inventory and sell obligations, expires pending ADD as before, permits no synthetic bar or global forward fill, and locks new risk through the first valid resumption CLOSE. Its temporary uncertified NAV does not by itself trigger the UNKNOWN stop. A never-filled initial UNKNOWN with no actual assets or outstanding responsibilities remains exempt.

## Precise stop predicate

After each complete original phase returns, inspect both live UNKNOWN states and asset/source unknowns in the phase snapshot. A blocking record must also have at least one of: nonzero CORE/ADD inventory, a positive active layer quantity, nonzero recognized receivable, an unsettled claim (including a not-yet-recognized registered claim), a live/cancel-pending order, or a retained whole/ADD sell obligation. Previous filled trades or settled claims alone do not create current responsibility. No later phase is executed after a blocking phase. All blocking records in that first phase are retained; native source termination log indexes preserve emission order where source records exist, with snapshot-only records afterward. The first phase and first source log record are reported separately.

## Checkpoint and reporting

At stopping phase, save a lossless pickle of the complete account runtime, including identity-sharing between archives and live state where applicable, source ledgers, claims, snapshots, pending CP and used CP identities, layers, full orders including dated fee/quantity schedules, caps, pools, sequence counters, day/phase and prior phase clocks, halt history, risk recovery flag, union old maps/permissions, projected catalog, candidate audit, CP cache, cached dated metadata, source hashes and loaded symbol list. Exact immutable market tables can be reloaded only from the same sealed manifest/source bytes; no resume is authorized by this package. Also save human-readable ledgers, blocker responsibilities and relevant original source evidence. Checkpoint creation itself must not change strategy state.

Closed first-probe, whole-round and ADD statistics use only execution-and-settlement-closed observations. Open inventory and unrecognized/unsettled claims are excluded from those denominators. Historical exact fees and research NET80 are retained. Stopping on OPEN must not read that session's future CLOSE for valuation or reports. Unknown NAV is not converted to a return or drawdown; no 35% claim or full-year performance claim is allowed.

## Resource and failure behavior

The entire execution, load, reports and exports share a 900-second hard supervisor deadline and 6 GiB child RSS budget on Darwin. A 780-second/5 GiB soft threshold requests a stop at the next complete original phase to preserve 120 seconds and 1 GiB for checkpoint/report export. The supervisor monitors throughout child initialization and reporting and kills the process group on hard limit, retaining the one-shot lock. A hard kill may lack a complete checkpoint; it is explicitly INCOMPLETE, never a successful UNKNOWN stop. Exceptions are failures, not normal diagnostic stops. There is no automatic restart.

## QA boundaries

The unchanged 20 halt and 26 candidate groups are rerun, with union catalog/permission/collision/clock/claim/identity/future-pollution, gate and resource tests. Two independent finite real-daily conditional slices remain labeled fixtures. The only real prefix QA ends at 2022-04-18, less than 75 common sessions. Its transactions equal the prior sealed recovery account through that date; reconciliation is identical before April 15, and April 15-18 changes are restricted to the authorized halt/valuation/recovery semantics, with unchanged cash, shares and trades. This is not a hidden full-window run.

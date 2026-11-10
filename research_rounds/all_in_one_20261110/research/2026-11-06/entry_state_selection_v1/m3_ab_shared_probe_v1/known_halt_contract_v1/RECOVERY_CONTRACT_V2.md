# Evidence-gated full-day suspension recovery contract v1

This is a new, explicitly different conditional research contract. It does not retroactively certify the old 2022 run or replace its sealed artifacts. No source prices, signals, thresholds, capital/risk fractions, selection rules, or old ledgers are edited. Daily data only. Observed OPEN ±5 bp remains a conditional proxy, not fill, auction, or price-limit executability evidence.

## Evidence and state

The generic consumer contains no security/date-specific branch. The input registry may name an individual security/session. Each admission must identify an exact FULL_DAY session and a timezone-aware known_at strictly before 09:30 Asia/Shanghai. Wrong security/session, missing/naive/late timestamps, and missing evidence cannot turn a missing price into a known halt. Real evidence is manually adjudicated from an issuer's official designated disclosure and an explicit publication clock, with local bytes and hashes pinned. The registry itself is hashed. Planned resume day is descriptive and never authorizes a trade or a missing later session.

The admitted Jan13 disclosure is issuer notice 临2022-003 in China Securities Journal. The independent clock is Sina's republication, not an official second-level issuer timestamp. Current HTML fields are 05:25:16/19/21+08:00; known_at takes the latest 05:25:21. These are reconstructed historical-publication evidence, not a contemporaneous capture, immutable PIT guarantee, or proof that the old run consumed the evidence.

HELD becomes KNOWN_FULL_DAY_SUSPENSION only when that session is supported and there is no conflicting positive OPEN or unresolved same-session corporate-action coordinate. Quantity, cost, pool, protective lines, layer dates, registered claims and outstanding sell responsibility remain. No bar, OPEN, I, CP, capacity or sector observation is synthesized. Existing UNKNOWN is absorbing and is never repaired by the halt adapter. Positive OPEN on a claimed full-day halt, or positive CLOSE subsequently observed, is a source/evidence conflict and remains UNKNOWN.

A later session without halt coverage uses the original raw OPEN, lineage/factor and dated metadata validation. It resumes existing-position management only if those original checks succeed. A missing/invalid resume OPEN or factor/source inconsistency remains UNKNOWN. Prior I-floor fallback is allowed only from the held round's last successful native CLOSE across an unbroken sequence of actually admitted halt sessions. Ordinary gaps are not forward-filled. At resume CLOSE, current original I/CP/raw data are required; old observations cannot substitute.

## Ticket, ownership and money clocks

A liability-free BUY_PENDING ticket expires without fill at its sole next common OPEN if that session is an admitted halt. It does not create a global asset lock; it cannot be replayed after resumption. A pending ticket with any fill/layer/claim/order liability is not discarded. A held stock's CP/ADD ticket expires on its next common OPEN during the halt. The unique-successful-ADD rule remains unchanged. Existing whole-position and ADD-layer sell responsibility remains until a valid raw OPEN, with original per-layer T+1 and one whole-order fee.

Known ownership is passed to original register using a temporary read-only HELD view, so a state label cannot turn owned shares into zero. Original recognized ex-date receivables and pay-CLOSE transfer continue, available only at the next OPEN. There is no general missing-bar corporate-action bridge: an admitted or local action effective on a missing-price halt session is still UNKNOWN if coordinates cannot be authenticated. The real admitted 600595 event has no such intersection; synthetic ownership/transfer tests do not expand real evidence.

## Account lock and NAV

A held asset's known halt sets a separate account recovery lock. Cash, receivables, quantity, costs and risk responsibility remain. Last valid CLOSE inventory/line/source_day are disclosed only as stale informational marks, not current liquidation prices. Certified NAV is null during the halt and all new risk/promotion is blocked. Stale information never becomes an allocation denominator.

At the resumption OPEN, known old-position exits and settlements may continue, but the global new-risk lock persists even if the resumed stock is sold completely. Pending new buys and ADD tickets from other stocks are consumed under their existing next-OPEN lifecycle, never deferred for replay after unlocking. Only a complete valid CLOSE snapshot releases the lock. That CLOSE may form genuinely new original A/B and fresh-CP tickets; the earliest execution is the next common OPEN. Jan14 CLOSE therefore cannot authorize Jan14 OPEN. Unrelated genuine UNKNOWN still blocks certification.

## Reports and execution gate

Report known-halt valuation gaps, resume-OPEN lock gaps, and genuine asset/source UNKNOWN separately. A restored final NAV does not imply a fully certified path; exact continuous drawdown through missing NAV is unavailable. An independently certified initial and terminal account can support endpoint return, with gap counts and proxy limits explicit. Any optional drawdown over observable days must be labeled that way.

Before independent approval only synthetic tests and the fixed Jan4–Jan17 prefix run are permitted. That prefix includes the original Jan12 purchase, Jan13 halt and Jan14 resume, not an outcome-selected exit. The unchanged-source Jan14 I is true and CP false; the stock is still held at Jan17. There is no claim that it sold or would fill a later order.

After independent release, one new 2022 birth-cohort account begins empty with CNY1,200,000, accepts births through Dec31, 2022 and follows to Jun30, 2026. The immutable runner checks all code/evidence hashes and an independently reviewed stage seal, uses a new exclusive-create output directory, and retains the prior 900-second/6-GiB resource guards. No new 2024 run is authorized. New additional UNKNOWN may still arise and are not preemptively repaired.

## Review amendment v2: report layers and admission gate

Only report_known_halt_v2.py and cohort_runner_known_halt_v2.py are authoritative for the proposed new run. The economic engine remains byte-identical. A halted whole round may contain a previously sold ADD layer. Only layers with q>0 receive KNOWN_HALT_UNCERTIFIED layer_status. A zero-quantity layer keeps its original cash, NET80 and individual execution/settlement status, including unsettled claims; round_status may still disclose the CORE halt.

release_gate_v2.py verifies the independent release's exact PRE_RUN_STAGE_SEAL_V2.json hash and every file listed by that seal, including RECOVERY_COHORT_CONTRACT_V2.json, before parsing the same verified contract bytes. It then verifies external code/source dependencies before output creation. Merely retaining an old seal file cannot mask changed contract bytes. Synthetic gate fixtures are isolated and are not actual approval. All v1 files and their original seal remain retained unchanged for audit.

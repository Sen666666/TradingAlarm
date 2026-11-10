# Independent post-run boundary review

## Certified result

Output-only audit: PASS, 6,175 checks, zero errors. Certified 41 sessions through 2024-11-06, 1,594 orders. Exact Decimal recomputation of every daily cash, receivable, paid fees, order notional/cash delta, per-security position, holding market value and marked NAV agrees. Final cash 148198.1264850922275; receivable 0; market value 1331357.18; NAV 1479555.3064850922275; fees 12704.3389249077725; 70 securities, 183021 shares. Fee amounts reconcile, but this audit does not independently certify fee tariffs or external market prices. Reported liquidation NAV was not independently recomputed.

All original final/checkpoint output hashes verify. All 33 fixed October31 baseline families compare exactly, with the established availability full-record multiset exception. Committed log day fields stop at November6; November7 appears only as failure/scan diagnostics or legitimate future planning dates. UNCERTIFIED_DAY reports no partial orders. This was an economic-preflight failure before accrual/fills. The audit supports restored exported state; it is not a fresh replay of all internal state.

## First actual boundary: 002602.SZ, 2024-11-07

Not held and never traded in this run. A new November6 SEED request is pending: planned/economic quantity 1400, reference allocation 0, reference rank 287. The older October18 ticket was already CANCELLED on October23 for RETRY_STOCK_M3_FALSE, never seeded. Do not label the new request an existing retained ticket or a held suspension.

Both admitted raw bars and facts skip November7: November6 exists and November8 exists. Raw November6 open/close 4.97/5.13; November8 4.87/4.87. These adjacent observations do not prove suspension and must not supply a fabricated November7 quote or factor. Scan issues are RAW_OPEN_MISSING_OR_INVALID, RAW_CLOSE_MISSING_OR_INVALID and ADJUSTMENT_FACTOR_MISSING_OR_INVALID.

Checked source paths:
- /Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/data-adjudicated-v2/bars/002602.SZ.parquet
- /Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/facts/002602.SZ.parquet
- /Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions/002602.SZ.json

No 002602-specific saved official evidence file was found within this research root. The action file contains no November7 2024 action and is not suspension evidence. Existing M2 economic_preflight pauses only existing live unheld tickets, not this new SEED request. Existing saved suspension adapters for other securities/dates do not authorize this case.

Required next factual question, before designing any repair: obtain official Shenzhen exchange/company evidence of 002602 trading status on November7 2024, effective suspension/resumption times and reason; distinguish a genuine no-session observation from a source omission. If it traded, obtain authoritative actual OHLCV/source/factor reconciliation. If suspended, separately review conservative new-request nonexecution/preservation and later revalidation; do not cancel the request or broaden existing pause behavior without review.

## Additional actual boundary in restored scan

300760.SZ, November7: held quantity 0, pending new November6 SEED 100 shares, no retained ticket. Issues UNADMITTED_EQUITY_EVENT and UNADMITTED_FACTOR_CHANGE. Local source action says ordinary cash 1.65/share, split ratio 1, effective November7; record/payment dates are unknown in that source. november_cash_evidence_v1 records an inventory, not an admitted official adapter. Need verified record/ex/payment dates, gross dividend, any differential reference decrement, and source-factor bridge before admission. No dividend entitlement may be manufactured for the zero holding.

## Decision

Do not rerun unchanged history: two actual fact/admission boundaries remain. Preserve completed prefix and current outputs. Parent decides whether to obtain official evidence; no external query, new facts, strategy modification, synthetic prices, request deletion, approval, or historical rerun was performed in this review.

## Supplemental official evidence and simulation risk stratification

Parent relayed the separate evidence branch's official 002602 announcement 2024-065:
https://disc.static.szse.cn/download/disc/disk03/finalpage/2024-11-07/816e0fce-2310-4cac-a566-81833c9a130a.PDF

It establishes one-day suspension on November7 and resumption November8 under ST华通 with a 5% price limit. This audit did not independently fetch that PDF. The earlier missing-evidence finding above describes the local files at initial review time; it is superseded by this official evidence report. Existing metadata lacks historical ST labels. Do not continue using a quote-gap proxy to bypass the dated ST/execution-rule boundary. No new boundary repair or run is performed.

This is a historical trading simulation, NOT live trading or actual account exposure. Independently grouped November6 CAPITAL_LOTS reconcile to total marked holdings. NAV exposure: total 89.9836%, current M1 25.4047%, current M0 64.5789%. M0 capital-role values are INITIAL 268868 CNY and EXPANSION 686612.18 CNY. These are current-day classifications, not proof that every M0 lot was originally acquired outside a mainline regime.

The substantial current non-mainline exposure, particularly expansion capital, remains a strategy-objective concern. Passing the accounting audit does not demonstrate compliance with the intended philosophy of concentrating on mainline trends and limiting other regimes to small trials and timely exits. This review records the concern without tuning or changing the strategy. This audit round is complete; leave factual/execution boundaries for a separately authorized review.

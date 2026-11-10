# Isolated native-pending E3.1 ranking contract v1

This is a NEW bounded hypothesis on the account's own pending domain, not the frozen 5517-pool daily20 experiment. Tests only: no Account/Runner instantiated or imported and no economics computed. Original code, frozen inputs and results are unmodified.

## API

`from pending_rank_adapter import rank_pending`

`new_intents, stock_audit, summary = rank_pending(intents, state_rows, day)`

- `intents`: original native PVR-ranked pending dicts, each with `sid`, `role`, numeric `rank`, and `PVR_score`. Input order is retained in output. Same-stock roles must share rank and PVR; duplicate roles and duplicate cross-stock rank keys fail closed.
- `state_rows`: iterable of dictionaries with `sid`, `day`, `state`, `first_break_day`. Only exact-day rows for pending stocks are read; no as-of fill. All other columns, including canonical PVR and price/support fields, are ignored. Duplicate same-day stock states fail closed.
- `day`: YYYY-MM-DD signal date.
- Returns deep copies changing ONLY `rank`. Original fields `priority_rank`, `priority_policy`, `original_H1_rank` and all other metadata stay historical, unmodified. Do not interpret old `priority_rank` as new rank; the native opening consumer sorts `(rank, role != 'core')`. Keep the returned audit externally.

## Full queue formula

1. Sort original intents by `(rank, role != 'core')`; collapse to unique-stock sequence Q and retain its numeric rank slots (including gaps).
2. Pin every stock whose original PVR_score is None/nonfinite at its original unique-stock position. Missing-score pinning takes precedence over the proposed prefix.
3. In the remaining movable Q order, F is the first 5 stocks with state FIRST_BREAK and first_break_day == day. C is the first 15 with state CONFIRMED. The state is only a ranking annotation, never an eligibility condition.
4. Concatenate F[0], C[0:3], F[1], C[3:6], ..., skipping unavailable reservations. Fill remaining places up to 20 movable stocks from unselected original movable Q order, including missing-state or continuing MOBILE/non-i_buy. Append every remaining stock in that same original order. This compress-then-backfill rule matches the frozen proposal's shortage convention; it does not insert fallback inside each missing bucket.
5. Merge the movable sequence around pinned original positions, and assign the unchanged sorted numeric slots to this final unique-stock sequence. Every intent for a stock receives the same rank; CORE-first behavior is unchanged.

For queues with a pinned missing score inside the first20 absolute positions, the first20 absolute stocks need not have the reserved5/15 composition. This is explicitly subordinate to native missing-score pinning. No stock or role is removed, and the consumer continues beyond20.

## Results

- 2024-09-24:988 unique stocks /1256 intents;949 same-day state rows,39 missing-state stocks retained;47 stocks moved. 600027.SH has missing native PVR and both roles, pinned at zero-based slot270 and numeric rank505. Top20:5 current-day FIRST_BREAK,15 CONFIRMED.
- 2026-01-15:257 unique stocks /344 intents;243 same-day state rows,14 missing-state stocks retained;55 stocks moved;no missing native PVR. Top20:5+15.
- Full nonrank intent equality, stock-role multiset equality, numeric-slot preservation, input immutability and same-stock rank sharing passed on both dates.
- Future/prior-row injection and future-row corruption passed. These establish exact-day lookup isolation, not upstream state-generation causality.
- Synthetic exact1+3 order, missing-score pinning, state absence, stale first-break day, shortage, duplicate roles, dual-role CORE-first, rank collisions and empty queues passed.

State availability derives from frozen canonical local I-buy rows, not a same-price-domain raw-account recomputation. Missing state does not prove absence of i_buy in the account; it only means no matched frozen source row. Do not use canonical support/price data as raw protection prices. These limitations remain relevant for any integration.

## Files and repeat command

- `pending_rank_adapter.py`: pure stdlib implementation.
- `test_rank_adapter.py`: isolated tests and frozen two-date exports.
- `TEST_RESULTS.json`: machine-readable counts, checks, limitations and input SHA256.
- `YYYY-MM-DD_NEW_QUEUE.csv`: full final unique-stock queue.
- `YYYY-MM-DD_RANK_CHANGES.csv`: moved unique-stock rows only.
- `YYYY-MM-DD_STATE_AVAILABILITY.csv`: all original-stock state match and movement records.
- `YYYY-MM-DD_TOP20.json`: first20 final unique-stock audit rows.
- `YYYY-MM-DD_RANK_ONLY_INTENTS.json`: all copied original intents, only rank changed.
- `OUTPUT_SHA256.json`: output seal excluding itself.

Run with PYTHONDONTWRITEBYTECODE=1 and `/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python test_rank_adapter.py`. It only reads frozen inputs and writes outputs within this directory.

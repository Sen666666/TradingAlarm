The immutable pure-market implementation is `engine.py` + `runner.py`; `FREEZE.md` is the economic contract. Importing these modules does not import an Account, execution or sizing engine. `CLAIM_SHA256.json` binds the exact code/manifest used in the five-stock smoke. Do not modify code during a batch.

Python: `/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python -B`

```sh
python -B entry_quality/channel_atr_fsm_v1/runner.py \
  --symbols-json PATH_TO_JSON_LIST_OF_SYMBOL_STRINGS \
  --period 2022-01-01 2023-12-31 \
  --period 2024-09-01 2024-12-31 \
  --out NEW_NONEXISTENT_OUTPUT_DIRECTORY
```

For semiconductor use one period, `2025-01-01 2026-06-30`, and the full fixed 126-symbol list. N/A rows are retained as coverage statuses. The output directory must not exist. There are no automatic retries; errors are preserved and the CLI exits nonzero after saving the batch receipt.

`runner.run_symbols(symbols, periods, outdir)` accepts `list[str]`, `list[[start,end]]`, and a Path/string. It parses the original STOCK_MANIFEST itself, verifies actual file SHA against the manifest, normalizes original daily index resolution to ns, and uniformly clips price/events/native/CP/input at 2026-06-30 before validating the original CP/input indexes. It computes full source-prefix state, then selects display periods and original CP anchors. Pair follow-up uses the full capped source until common original I invalid/source unknown/source end, independently of either protection exit. Do not prefilter to actual purchases or pass a display-only source prefix.

Engine functions:

- `features(price) -> DataFrame`: strict known Boolean flags, true OHLC TR/RMA14, prior ATR/U20; close validity is independent from H/L readiness.
- `market_fsm(sid, price, events, version, feature_frame=None) -> {daily, events, generations}`: no native-I argument. E0 starts shadow generations; hard/P old-line priority, CHANNEL_SEEN then first real frozen-ATR advance matures. Known close-frontier updates and consumes skipped grids while data unready, issuing no permission/backlog.
- `protection_pairs(sid, price, feature_frame, native, cp, anchor_mask, version) -> list[dict]`: all raw CP anchors, common P0/old-I context and anchor ATR denominator; loop uses arrays. Entry reference invalid/unknown, ATR-unprepared, early exits, unknown and insufficient-20 samples are explicit categories, not zero risk.

Each symbol writes `MARKET_DAILY.parquet`, `MARKET_EVENTS.json`, `MARKET_GENERATIONS.json`, `CP_ANCHOR_PAIRS.json`, `COVERAGE.json`, `SOURCE_FREEZE.json`. Batch writes `COVERAGE_ALL_SYMBOLS.json`, `ERRORS.json`, `RUN_RECEIPT.json`. Raw-anchor pair row count is asserted equal to the original CP mother-count; orphan raw CP dates are explicit unknown rows. Pair strong-excursion labels are raw common-horizon diagnostics; global window deciles are deliberately not assigned per symbol.

`MARKET_DAILY`/events are display-period outputs. `MARKET_GENERATIONS` retains origins of visible generations even when they began before a display period; the signal state was never initialized at the display boundary. All are market shadows, not actual holdings/intent grants, fills or returns. No real halt/limit/ST/orderbook/receive restoration or full missing-session calendar verification is claimed.

Five primary smoke cases are 000620/002583/300085/603061/300623; `smoke_v1` contains 4333 display rows and 291 original CP anchors with zero errors. `smoke_main_v1` preserves the earlier main-only snapshot, including the 605111 non-primary appendix. The unknown-frontier/pair guard correction preserved that source at `engine_pre_unknown_fixes.py`; `POST_FIX_STATE_COMPARISON.json` proves already reported four case trajectories retained their shared numerical fields. Actual 600345 unknown flags are in `smoke_v1/ACTUAL_600345_UNKNOWN_GUARD.json`. These traces are not an economic effectiveness pass.

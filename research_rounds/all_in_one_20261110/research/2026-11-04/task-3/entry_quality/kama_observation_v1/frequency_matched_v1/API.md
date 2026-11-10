Development phase is `run_dev.py`, pure signal/frequency counts only. It reads the original development raw-anchor mother (35713) from the two saved market shards and never accesses saved exit/outcome/strong labels to choose a period. Price/native/CP-input parquet reads use a `date <= 2023-12-31` predicate before indicators are calculated. Development follow-up is also administratively cut there.

`core.ema_matrix(price, existing_kama_indicators, periods=4..480)` produces one NumPy EMA matrix; all periods use the existing first-ten-close seed/reset and ordinary alpha=2/(N+1). Maximum residual is the largest-period EMA seed coefficient from clean_count. Original KAMA/s/seed coefficients come from `kama.calculate`, not a second implementation.

`core.common_anchor(pair, arrays)` assigns common eligibility before any arm exits are inspected: saved PAIRED/reference, source/native identity, anchor KAMA/all-EMA ready/s/seed residual<=.01; follow-up ends only at 20 known observations or an independent known I failure. Unknown/source/admin-end before a common end excludes the whole anchor for every arm. I hard exit is checked first and is a competing cause, not a protection event.

`core.evaluate(common, arrays)` uses KAMA+477EMA line states together, same P0, old-line first/next-close proposal only, no later CP candidates. It returns counts of protection/I-competing/no-exit20 plus P0/I-raised/band-raised protection origins. These are not fills, orders, price returns or capital outcomes.

After parent FREEZE and bounded static review, one run is:

```
/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python -B entry_quality/kama_observation_v1/frequency_matched_v1/run_dev.py --processes 3 --out entry_quality/kama_observation_v1/frequency_matched_v1/dev_run_v1
```

The directory must not exist. Source SHA is checked before use and after the batch. Errors preserve worker artifacts and stop without automatic retry. Locking minimizes integer protection-count difference on the common denominator; exact tie chooses the larger N. Error>1pp or zero common sample stops validation; it never extends the grid or turns exclusions into no-exit observations. Output is counts and `LOCK_EMA.json`, not validation outcomes. Validation is a later locked phase, not invoked by this development driver.

`SINGLE_CASE_API_GATE.json` is only the predeclared original盈新2022Jan7 compatibility check: vector EMA20 equals the existing scalar prefix exactly, KAMA protection1 versus EMA20 protection0/I1 within the common 16-observation I-ending span. No period was selected from this case. It does not replace the full frequency calibration or independent audit.

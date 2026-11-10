# Full5517 local source data-domain audit

Read-only audit complete; no numerical input-domain blocker was found for the frozen source. No model, signal, account or source rewrite was run in this task. This checks the existing local data domain, not historical tradability or a complete historical security universe.

Source: `/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet`  
SHA256: `11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`.

## Results

- Scanned all 15,739,264 rows in 121 batches. The 5517 IDs exactly match the frozen roster.
- Duplicate symbol/date extra rows: 0. Nonincreasing per-symbol physical date order: 0. All 5517 symbols have one nonnull known source value; multisource/unknown-source symbols: 0.
- Nonfinite/nonpositive OHLC: 0; invalid OHLC geometry: 0; original eligible-price mask rejections: 0.
- Nonpositive/nonfinite volume: 0; nonpositive/nonfinite amount: 0. PVR's own valid mask accepts all rows. Price and PVR clocks coincide on this file but retain their distinct definitions.
- CP first-bad-amount symbols: 0; CP domain-blocked rows: 0. The prospective adapter must still retain the valid prefix and mark CP UNKNOWN starting at the first bad amount on the original eligible-price clock, without amount filling, dropping/restarting CP, retroblocking earlier history, or altering E0/PVR clocks. This fault branch is not exercised by this source.

| Exact source day | Present | Missing | Original price valid | PVR own valid |
|---|---:|---:|---:|---:|
| 2022-01-24 | 4518 | 999 | 4518 | 4518 |
| 2024-09-24 | 5309 | 208 | 5309 | 5309 |
| 2026-01-15 | 5451 | 66 | 5451 | 5451 |

There are 5,424,843 actual source rows from 2022 onward, across an observed union of 1054 source dates from 2022-01-04 to 2026-05-15. This is not an official session calendar. The source does not cover the remainder of 2026 H1.

## Interpretation limits

The source lacks the optional original fields `observed_bar`, `synthetic_event_bar`, `source_invalid`, `source_anomaly`, `price_eligible` and `is_observed_bar`. The original mask's defaults were applied, including observed=True, synthetic/source_invalid=False and no excluded dates. Their absence does not authenticate actual observation, ST status, suspension, execution eligibility or historical publication time. Full historical listing identity remains UNKNOWN for all symbols in this audit. First/last source rows are observations, not listing/delisting dates; a missing target-date row does not establish why it is missing.

The price-mask implementation is bound to `data_utils.py` SHA256 `e5623d85b66ca575e9ba3066389d0a1119f757388ae68e2711e4a70852909668`; its absolute path and defaults are in `DATA_DOMAIN_SUMMARY.json`. Per-symbol domains and three-day missing-ID lists are saved beside this report. No current snapshot was reinterpreted as a historical PIT security master.

## Resources and evidence

One row-data pass plus a separate raw-byte hash pass completed in 3.427742 seconds. Peak process RSS was 1,185,677,312 bytes (about 1.10 GiB); retained date/mask arrays accounted for 141,653,376 raw bytes, not total process memory. The process exited and released memory. Source size/mtime remained unchanged. This audit's wall time is not a model-cache runtime estimate.

`SYMBOL_DATA_DOMAINS.*`, `THREE_DATE_COVERAGE.csv`, `THREE_DATE_MISSING_IDS.json`, `DUPLICATE_KEYS.json`, `STREAM_PASS_COMPLETE.json` and `DATA_DOMAIN_SUMMARY.json` contain the machine-readable evidence. `audit_data_domain.py` is the exact executed audit implementation. The model runner remains responsible for its own persisted anomaly isolation and causal-prefix validation.

# Independent one-price execution stress comparison

Facts: joint51_candidate_v8_facts. Certified scenario through 2024-10-24; baseline through 2024-10-24. All original baseline artifacts remain unchanged.

No-fills: 4. Baseline one-price orders over common horizon: 5. Baseline ADD descendants of barred seeds: 0. Aggregate trade path differences: 33.

## Matching-date NAV differences
- 2024-09-23: scenario NAV 1,192,497.15; baseline 1,192,289.44; difference +207.71; scenario stocks 102, weight 33.1011%.
- 2024-09-25: scenario NAV 1,214,784.78; baseline 1,214,631.22; difference +153.56; scenario stocks 267, weight 89.9559%.
- 2024-09-26: scenario NAV 1,270,156.95; baseline 1,270,037.36; difference +119.59; scenario stocks 266, weight 90.4554%.
- 2024-09-27: scenario NAV 1,330,429.95; baseline 1,330,163.36; difference +266.59; scenario stocks 266, weight 90.8878%.
- 2024-09-30: scenario NAV 1,441,144.35; baseline 1,440,845.76; difference +298.59; scenario stocks 266, weight 91.5832%.
- 2024-10-08: scenario NAV 1,514,552.35; baseline 1,514,195.76; difference +356.59; scenario stocks 266, weight 91.9911%.
- 2024-10-09: scenario NAV 1,428,312.04; baseline 1,428,117.44; difference +194.60; scenario stocks 266, weight 89.5777%.

## Limitations
- Conditional ex-post OHLC equality gate; not historical auction/queue reconstruction, verified limit-up/down status, or return lower bound.
- Original whole-OPEN intents and maximum quantities are frozen before gate. No-fill buy reservations remain unavailable throughout the batch; failed sales never supply cash.
- Raw OPEN +/- 5bp remains an accounting proxy, not evidence of a real executable price within H/L.
- 2024-09-24 onward rapid market-wide upside, future speed/breadth, persistent sectors and order access were unknowable at each decision time.
- Current roster and industry classifications are not PIT; 1692 selected members are not full historical A-shares.
- Small seed quantities do not bound downstream ADD, future reentry, shared-cash or return effects.
- Shared-cash path changes are not a clean causal attribution to individual original orders.

## Files
- full_20241031_once: full scenario account, holdings, orders, all 50 sectors, equity, CP, candidates, intents, reservations and no-fills.
- DAILY_BASELINE_DIFFERENCES and DAILY_SECTOR_DIFFERENCES: full daily comparisons.
- BARRED_SEED_PATH_LINEAGES and BASELINE_BARRED_SEED_DESCENDANT_ADDS: downstream paths, including alternative scenario entries.
- ALL_TRADE_PATH_DIFFERENCES: indirect funding/quantity changes.
- ALL_OPEN_REJECTIONS: all ordinary rejected OPEN requests.
- FREEZE and source/output hashes preserve provenance.

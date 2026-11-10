# M9 build readout

Research-only implementation and 102 synthetic/static checks PASS. No historical M9 run performed by this build. Engine and contract frozen before inspection of new actual-data examples; no economic changes afterward. Baseline M7 and M8 files preserved under dependency seal. Independent review and a separately approved runner remain necessary.

## Actual examples: M8 path, not M9 simulation

All 58 original M8 lot-marker observations fail at least one M9 two-close predicate on that M8 path. This is not evidence that M9 will never retire a lot: a later second day and divergent M9 positions, cashflows and round identities are not represented. No threshold was loosened to manufacture triggers.

The diagnostic reads saved M8 ADD_GATE close_net and CAPITAL_LOTS stock/M/sector state, verifies their round_net equality, and uses adjacent days of the completed no-blocker ledger. It does not load current quotes or reconstruct earlier net from later holdings. Saved completed CLOSE records imply inherited price validity; raw bars are not independently reloaded. Full daily records for requested names and PV retirement rounds are in ACTUAL_EXAMPLES.json with source hashes.

- 000158.SZ, 软件与IT服务, 2024-10-11: current net 11059.3788207266500, stock 1, sector 0, M 0; prior 2024-10-10 net 7826.1924967295500, stock 1, sector 1, M 1. M9 predicates on M8 path: False.
- 002049.SZ, 半导体, 2024-10-11: current net -2920.6062929567000, stock 0, sector 0, M 0; prior 2024-10-10 net 2034.1244022933500, stock 1, sector 1, M 1. M9 predicates on M8 path: False.
- 002261.SZ, 软件与IT服务, 2024-10-11: current net 6649.6105343298000, stock 1, sector 0, M 0; prior 2024-10-10 net 4478.9403495070000, stock 1, sector 1, M 1. M9 predicates on M8 path: False.
- 002056.SZ, 光伏风电设备, 2024-10-30: current net -916.3962558502000, stock 1, sector 0, M 0; prior 2024-10-29 net -640.7450420044000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 002129.SZ, 光伏风电设备, 2024-10-30: current net -534.9258882071000, stock 1, sector 0, M 0; prior 2024-10-29 net -814.5720471811000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 002459.SZ, 光伏风电设备, 2024-10-30: current net -184.6288315255000, stock 1, sector 0, M 0; prior 2024-10-29 net -723.9464238325000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 002487.SZ, 光伏风电设备, 2024-10-30: current net -914.4304008399500, stock 1, sector 0, M 0; prior 2024-10-29 net -1229.0323296857000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 002506.SZ, 光伏风电设备, 2024-10-30: current net -1738.9101675094000, stock 1, sector 0, M 0; prior 2024-10-29 net -1473.2463164841000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 002865.SZ, 光伏风电设备, 2024-10-30: current net 9191.7607532380500, stock 1, sector 0, M 0; prior 2024-10-29 net 4526.6635797825000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 300093.SZ, 光伏风电设备, 2024-10-30: current net -1578.5387853955000, stock 0, sector 0, M 0; prior 2024-10-29 net -1293.8989450112500, stock 0, sector -1, M -1. M9 predicates on M8 path: False.
- 300751.SZ, 光伏风电设备, 2024-10-30: current net -197.8787307203500, stock 0, sector 0, M 0; prior 2024-10-29 net -1989.6116207180500, stock 0, sector -1, M -1. M9 predicates on M8 path: False.
- 300850.SZ, 光伏风电设备, 2024-10-30: current net -1059.9396985974500, stock 1, sector 0, M 0; prior 2024-10-29 net -880.1671678284500, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 600438.SH, 光伏风电设备, 2024-10-30: current net 1118.1069034715500, stock 1, sector 0, M 0; prior 2024-10-29 net 1633.4548250093500, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 600732.SH, 光伏风电设备, 2024-10-30: current net 1084.4395573766500, stock 1, sector 0, M 0; prior 2024-10-29 net -1003.9180083899000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 601865.SH, 光伏风电设备, 2024-10-30: current net 353.8635678096500, stock 1, sector 0, M 0; prior 2024-10-29 net -443.1279852662500, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 603063.SH, 光伏风电设备, 2024-10-30: current net 1998.863609664000, stock 1, sector 0, M 0; prior 2024-10-29 net 2899.7237360731000, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 603806.SH, 光伏风电设备, 2024-10-30: current net -2040.0524446526000, stock 0, sector 0, M 0; prior 2024-10-29 net -2057.0309614474500, stock 0, sector -1, M -1. M9 predicates on M8 path: False.
- 688223.SH, 光伏风电设备, 2024-10-30: current net -2126.1735445918520, stock 0, sector 0, M 0; prior 2024-10-29 net -1387.2784810428005, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 688349.SH, 光伏风电设备, 2024-10-30: current net -2403.4584232769305, stock 0, sector 0, M 0; prior 2024-10-29 net -1782.3742915584970, stock 0, sector -1, M -1. M9 predicates on M8 path: False.
- 688472.SH, 光伏风电设备, 2024-10-30: current net -1433.4861908250230, stock 0, sector 0, M 0; prior 2024-10-29 net -923.9908639000360, stock 1, sector -1, M -1. M9 predicates on M8 path: False.
- 688503.SH, 光伏风电设备, 2024-10-30: current net 6656.5933987697965, stock 1, sector 0, M 0; prior 2024-10-29 net 3174.4793766768305, stock 1, sector -1, M -1. M9 predicates on M8 path: False.

## Interpretation limits

Whole-round net<=0 can permit large profit giveback; two-day confirmation can lag. Profitable rounds retain inherited hard protections, which need not protect all accumulated gains. This candidate is a narrow hypothesis, not a sufficient solution to holding major trends. Initial/trial behavior, I/CP precedence, M7 capital demand and funding remain unchanged. No shared risk pool, no fitted thresholds, no caps or new buy/reentry rules.

Synthetic checks cover state/unknown controls, profitable round retention, one-day retention, exact zero-net trigger, repeated dates, round replacement, noncontiguous market days, immutable prior actual holdings/net, absent/non-observed price data, hard-exit precedence, INITIAL preservation, mixed kinds, grouped fees/odd lots, legal partial remainders, T+1, stale donor plans, actual export and actual atomic rollback both after selling and after new CLOSE evidence.

## Files

- CONTRACT.md and CONTRACT_FREEZE.json: ex-ante hypothesis and timestamp/hash.
- engine.py: isolated M9 class inheriting M7; grouped execution adapted locally from M8, new explicit M9 order reason, no M8 global mutation.
- synthetic_retirement.py, STATIC_QA.json, SYNTHETIC_QA.json: 102 tests and method-identity results.
- DEPENDENCY_SEAL.json: immutable imported/frozen baseline files checked by QA.
- actual_examples.py and ACTUAL_EXAMPLES.json: post-freeze M8-path descriptive evidence only.
- OUTPUT_SEAL.json: final files hashed.

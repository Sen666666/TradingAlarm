# Frozen relative-UP priority experiment

One consumer, one economic run; no parameter scan. Original A_UNION_B baseline reproduced exactly by named columns for 3821 rounds, 8401 actions, 20445 decisions and 720 end states. First verifier stopped only on CSV column order; the named-column verifier is preserved separately. System-Python missing-pyarrow attempt produced no results and is archived.

3481 common selected events have exactly identical full round records and individual actions, maximum economic difference zero. Changes are entirely event admission/displacement and later re-entry identities.

2022 modestly improves but remains negative with core win rate 26.84%. 2024 win rate increases slightly but completed stock net sum falls and >=50% full tails fall 50 to 43. Original full >=50% tails retained 39/50; original return top10 retained 7/10. Losses include 银之杰, 富临精工 and 兆威机电. 2026 has only 14 completed, 19 UNKNOWN and 11 censored in new arm; no generalization.

All sums are independent conditional stock-round PnL, NOT shared-account returns. Core is fixed same-entry/exit independent-sell-fee counterfactual, NOT a new core-only strategy. Existing static-universe NON-PIT and historical orderability limitations remain.

Protocol revision 2 only corrects inherited explanatory attribution/audit statements and adds evidence; original freeze preserved as FREEZE_V1_SUPERSEDED.json with superseding hash. Consumer was unchanged. Supplemental postprocessing is independently sealed.

Artifacts: PERFORMANCE.csv, BASELINE_TAIL_RETENTION.csv, LOST_BASELINE_TAILS.csv, NEW_LOST_ATTRIBUTION.csv, SELECTION_FRESH_COUNTS.csv, DAILY_SECTOR_REPLACEMENTS.csv, CORE_AND_FULL_ROUNDS.csv, EVENT_OUTCOME_COMPARISON.csv. Exact original code diff: ORIGINAL_DIFF.patch. Baseline/economic directories retain all original engine ledgers and full candidate ranking audits.

Already completed commands (do not rerun into existing directories): python -B simulate.py --mode baseline; python -B verify_baseline_columns.py; python -B simulate.py --mode economic; python -B evaluate.py; python -B audit_increment.py. Interpreter: /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python.

# Daily gap inventory, authoritative v2

Strictly read-only source inventory. No economic replay.

Use RESULT_V2.json and the *_V2.csv files. The first diagnostic files are preserved, but their potential-domain label only means the original fixed-budget PASS reference subset. It must not be used to prune shared-account candidates.

V1 lineage transition text comparison was distorted by shift integer-to-float conversion. The V2 file compares numeric segment identity and removes false same-source transitions; missing-row counts are unchanged.

Main scope: every 2022 original A/B event security in the original NON-PIT fixed universe, beginning at its first candidate next common OPEN and ending 2026-06-30. This is not a historical whole-A-share universe and not an actual-holdings assertion.

OFFICIAL_SEARCH_QUEUE_V2.csv contains only security, name, dates, gap shape, adjacent public-price facts, and internal responsibility priority. Do not transmit private account sizes, PnL, strategy or local paths to public search services.

STOCK_UNIVERSE_V2.csv and CANDIDATE_EVENT_STATIC_CHECKS.csv define the complete reproducible stock-day domain. DAILY_ISSUES_V2.csv lists anomalous dates only; MISSING_ROW_RUNS_V2.csv groups contiguous missing common sessions. FACTOR_LINEAGE_TRANSITIONS_V2.csv separates admitted coordinate changes from other changes, not all changes are data failures.

ACTUAL_RESPONSIBILITY_ISSUES_V2.csv reconstructs pre-OPEN quantities from sealed executed transactions only. Unknown quantities remain held as recorded; it neither repairs missing data nor pretends later prices restore an UNKNOWN path. Original no-shared positions are reference only.

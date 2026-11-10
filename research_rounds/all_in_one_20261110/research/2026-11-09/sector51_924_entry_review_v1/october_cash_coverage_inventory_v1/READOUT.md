# October cash coverage inventory

Frozen baseline: mainline_m7_downturn_q0_split_v3/once_20241031, last completed day 2024-10-09.
Scope: all 1,692 eligible tickers from CLASSIFICATION_ALL1709.csv; ordinary cash distributions (split_ratio = 1, cash > 0), ex-date 2024-10-10 through 2024-10-31, absent from baseline EVENT_ADMISSION.json.

## Findings
60 events: 27 retained, 1 held, 32 neither held nor retained on 10/09.
2 have named reviewed adapters (600535 and 600750, under separate active work).
13 have existing official CNINFO raw records, but no reviewed adapter found.
45 have no exact-event official source found in searched evidence directories.

Immediate 10/11 retained gaps: 301087, 603588, 688029, 688563. The remaining 10/11 events are 600079 and 688248 (raw official records available), and 688200 (cancelled ticket; no official fact found).
10/14 retained gaps: 603678 and 605111.
10/15 held 688516 (cash/share 0.86) lacks existing official fact; this requires the held-entitlement path, not a q0-only shortcut.
10/15 retained gaps: 300741, 300919, 603077, 603881.

## Usage and limitations
MISSING_EVENT_INVENTORY.csv gives the compact inventory. JSON includes exact raw records, source paths, and found adapter records. SOURCE_HASHES.json seals the baseline files and evidence read. SUMMARY.json gives scope and counts.
State labels reflect 10/09 only, never a prediction of future holdings. “None” is not permission to ignore a future event or alter requests.
d_source here is the local action cash/share, not a newly adjudicated official amount.
Official raw records retain their original F-field dates. No pay date was inferred. Candidate facts, raw API responses, or filename-only notice matches are not reviewed engine admission.
Search covered the full current review ROOT and the 2026-11-06 entry_state_selection_v1 sibling, restricted to cash/equity/fact/notice evidence files (3,364 files). Missing means not found within these searched sources, not proof that no announcement exists.
No engine, run, classification, or original evidence was modified. Only this new inventory directory was written.

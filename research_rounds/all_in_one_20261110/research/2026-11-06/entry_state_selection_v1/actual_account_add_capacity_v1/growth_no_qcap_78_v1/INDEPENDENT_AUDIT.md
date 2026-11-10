# Independent pre-run audit: no quantity cap, fixed 78 sessions

Reviewer: /root/design_joint_capital_allocation/audit_no_qcap_experiment
Decision: PASS for one new no-qcap arm only. No economic execution was performed by this audit.

## Scope and source comparison
The complete growth_book.py is byte-for-byte the old source after replacing only 0<q<=current_qty with 0<q. The 0.25 coefficient, positive U_avg/U_layer/U_post conjunction and known-state requirement remain unchanged. Flat trials remain exempt from the extra growth gate. growth_adapter.py differs only in the sibling baseline path, experiment identity suffix and source-freeze path resolution. Its cost accounting, actual layer H/L/P/R0, native route, sizing enumeration, PVR priority, cash/sector/stock checks, fill, exit and observation code are unchanged.

A fresh -B interpreter imported the new growth_book and new growth_adapter. The adapter's growth_allowed object and GrowthRunner.growth_quantity_allowed globals refer to the new function. Shared resume_baseline is the sealed old sibling module. This clears the direct fresh-process CLI invocation, not arbitrary preloaded Python sessions.

## Restoration, provenance and frozen outputs
The checkpoint SHA256 is 848cc43a153aa609e67191504e8e835474ce46bb140d23733716f3aff759ef54. All 12 SOURCE_IDENTITY entries match. Every one of the checkpoint's 45 frozen source hashes was rechecked. All 20 old baseline and all 23 old growth manifest-listed outputs match their saved hashes. The existing baseline validation reports 13 successful exact comparison groups. These are checks of sealed evidence, NOT a new baseline reproduction or economic replay.
The runtime source-freeze reconstruction depends on bootstrapped score inputs; it was not reconstructed in this audit. The static restoration path still reconstructs all 45 hashes, verifies Python/engine identity, and restores under the original AtomicOutputs_ProfitRunner before installing GrowthRunner. No bootstrap, restore or event loop was called in this audit.

## Execution gate and discovered issue
The initial driver allowed alternate --out directories, which did not enforce a single run. This was reported and corrected before clearance. The reviewed driver accepts no output/date/parameter override, writes only growth/run, rejects an existing growth directory and exclusively creates EXECUTION_STARTED.json before bootstrap. The marker remains after failure, so changing/deleting only the output does not permit another run. --out growth/other was tested and rejected by argparse without creating a marker or output.
Missing AUDIT_GATE was independently tested and blocked. verify_gate binds the exact scope, baseline validation hash and reviewed-source hashes. The window code fixes 2023-01-03 through 2023-04-28 and asserts 78 opens and closes; the input horizon remains 2026-05-15. Output overwrite, automatic retry and economic parameter scanning are not permitted.

## Tests and reporting scope
All 24 pure ledger/predicate tests were independently rerun and passed; the existing unit-log hash matches UNIT_TESTS.json. They are not engine replay tests. The metrics contract uses the same inherited NAV, close-to-close window drawdown, split inherited/new closed cohorts, dividends, actual cash/fees, open cohorts and three sealed/new arms. The newly written metrics executable is outside this economic clearance and has not yet been numerically validated.
601019 must use the new continuous actual account path. Qingdao 601298 May losses remain an outside-window mechanism example and cannot enter this 78-day PnL or round statistics.

## Remaining limitations
One previously consumed development window, fixed future 1709-stock pool (not PIT), opening tradability unknown, and conditional protection not a guaranteed cash loss cap. Removing q<=Q is a controlled test, not evidence of improved returns. Future output and accounting bridges must still be verified before conclusions.

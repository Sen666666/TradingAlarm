# Strict original-account continuation baseline

Status: PASS. This is an engineering reproducibility check, not a performance claim or a new strategy test.

## Completed run

- Restored the original 2022-12-30 CLOSE checkpoint through the real `IO.atomic_runner_outputs` / `AtomicOutputs_ProfitRunner` guard and the unmodified original `ProfitRunner.restore` chain.
- Checkpoint SHA: `848cc43a153aa609e67191504e8e835474ce46bb140d23733716f3aff759ef54`.
- Exact Python 3.13.7 provenance, actual class/function identity and reconstructed original 45-file source freeze matched. No identity spoofing, guard bypass or original-source edits.
- Restored 69 holdings and 82 pending intents, available cash `84360.525699312823`, NAV `844956.557699312823`.
- Ran all 176 original events: 78 OPEN, 78 CLOSE and 20 ACTION. First OPEN `2023-01-03T09:30:00+08:00`; last CLOSE `2023-04-28T15:10:00+08:00`.
- Original `C.END=2026-05-15` was retained for inputs, factors and recovery. Only the event window was bounded. No account, annual or quarter reset. No live orders.
- Input loading: 107.147 seconds. Event loop: 55.617 seconds. Saved-output validation: 10.590 seconds. The first two are logged to millisecond precision; they do not include all import/export overhead.

## Exact validation

`run/BASELINE_VALIDATION.json` passes all 13 comparisons, with no first difference. Every field and row sequence matches the saved original full-run prefix. Monetary Decimal strings are not converted to floats or rounded; there is no tolerance gate.

| Stream | Full prefix rows | New continuation rows |
|---|---:|---:|
| Journal | 3,588 | 864 |
| Trades | 2,287 | 554 |
| Decisions | 320 | 78 |
| Account audit | 10,946 | 2,649 |
| Funding | 61,224 | 21,023 |
| Daily holdings and cash | 320 | 78 |
| Balance audit | 320 | 78 |
| Opportunities | 546,880 | 133,302 |
| Industry | 7,961 | 1,953 |
| Rank policy | 44,079 | 15,079 |
| Profit gates | 47,558 | 16,183 |
| OPEN cash checks | 320 | 78 |
| Execution windows | 554 | 554 |

The execution-window cache is not in the original checkpoint; its comparison covers new continuation events only. Other comparisons include the restored history and continuation. The daily comparison includes positions, layers, cash buckets, fees, pending counts and pool summaries, not just NAV. No claim is made that a nonexistent original 2023-04-28 internal-state checkpoint was compared.

New checkpoint: `run/latest_checkpoint/checkpoint.pkl`, SHA `d3c48d8d274e95e3baeb822a365a05dbbb5ed14049c52b2e6ad1007d9f3e3bce`. Its own generation-time provenance is in the adjacent `.provenance.json` and retains the real original engine identity.

## Preserved validation failures and correction

The original event loop and exports completed once. The first post-run comparison stopped because account audit fill dates are nested under `receipt.at`, while dividend accrual dates are under `receivable.ex_at`. The corrected comparison reader accepts those documented fields. A subsequent validation-only preflight identified the event-clock serializer's ISO `T` separator; its assertion was corrected to the actual saved format. Neither correction changed financial logic, saved account outputs or checkpoints, and no economic events were rerun.

The original executed script bytes are retained as `resume_baseline_execution_v1.py`, matching `run/PREDECLARED.json`'s driver SHA. `run/FAILURE.json`, `run.log`, `complete_validation_attempt1.py` and `validation_recovery.log` preserve the failures. Successful validation is in `validation_recovery2.log`. `run/DONE.json` records the comparison-only recovery explicitly. The current reusable driver contains only the nested audit timestamp fix relative to the executed version.

## Reusable API

Import `resume_baseline` from this directory.

```python
boot = resume_baseline.bootstrap_original()
with resume_baseline.restored_original(boot, output_directory) as (last, audit):
    last, run_info = resume_baseline.run_window(boot, last)
```

`boot` exposes `runner`, `market`, `factors`, `input_identity`, `restore_audit` and source/provenance records. `restored_original` yields only after successful strict original restore. `event_window(boot, last)` returns `(events, opens, closes)`. `run_window` uses the unchanged original `run_no_loss_add.event` and accepts an optional after-event observation callback.

For a separate growth adapter: first finish the original restore context, then install the new engine and its own source freeze/provenance. Do not change engine class or source freeze before restore. Do not change class inside this atomic context expecting it to survive exit: the original context restores its original class in `finally`. Do not naively attach two markets to one shared facts object; each boot owns a single market/facts binding. Market execution logs and caches are not checkpoint state.

## Commands

Run the eight lightweight exact-comparison tests:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python /Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/actual_account_add_capacity_v1/growth_continuous_78_v1/baseline/test_resume_baseline.py
```

The original single account run used `resume_baseline.py --out run`. Its exact executed bytes are retained in `resume_baseline_execution_v1.py`. To explicitly reproduce with the comparison-corrected driver, choose a new output directory; existing outputs are never overwritten:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python -u /Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/actual_account_add_capacity_v1/growth_continuous_78_v1/baseline/resume_baseline.py --out new_explicitly_authorized_run
```

Do not rerun economics merely to reread validation. `validate_exports(Path(...))` compares saved outputs without input bootstrap, restore or events. `complete_validation.py` was the one-time completion tool and refuses to overwrite `DONE.json`.

## Hashes

- Executed driver snapshot: `d83c03fe0aa1421d432975533f8a40de55cf052faba8b74dcd3c9a536b1eba1d`.
- Current reusable driver: `ecc890da3d57d201c76bcf785bca84fcdbc795d8c5b01432b346ac28b8e872c0`.
- Successful validation-only script: `669917046af552c7c4b129ba2827ba69013d8e57a5e41bb900687f7215926732`.
- Tests: `fa2b07f5ab4cae6d852569193a2ebba70c7c3ea237d4de4fd1cfa8f9fd5175cb`.
- Validation JSON: `94562d927bd13ad81453dcbc450429775fff081e966bc47096a20e5dd537ce2b`.
- DONE JSON: `d06bc02c4ffcbb5b93d7b1dfe06519082a2d69f92e26865e8edd3de0feab9446`.
- All output hashes: `run/OUTPUT_HASHES.json`. All current baseline source/readout hashes: `DELIVERABLE_HASHES.json`.

Research scope remains the original fixed future 1,709-stock pool and causal OPEN execution proxy with historical tradability unknown. These checks establish exact continuation reproducibility only.

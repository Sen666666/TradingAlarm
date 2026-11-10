# Original A+B bridge stage: author result

This stage replays unchanged original per-stock A_UNION_B consumers, not a new shared account. Independent review is pending.

- Original 2022 NET80 wrapper: 2,732 rounds, 6,536 actions, 12,917 decisions/ranking rows, 103 end states, 436 registrations, 842 claim-ledger rows and 108,901 profit-gate rows match original baseline columns. 431 bridges and 421 claims match normalized JSON exactly. All 2,732 original ledger QA rows pass.
- Original 2024 NET80 wrapper: 1,354 rounds, 3,387 actions, 6,878 decisions/ranking rows, 27 end states, 165 registrations, 300 claim-ledger rows and 57,660 profit-gate rows match original baseline columns. 154 bridges and 150 claims match normalized JSON exactly. All 1,354 original ledger QA rows pass.
- Numeric comparison uses the original compare_table tolerances (absolute 1e-7, relative 1e-12); this is column-level parity, not a claim that CSV byte serialization is identical.
- Import-safety audit: importing bridge.py read no original strategy/data file and executed no original consumer. Source loading/replay is explicit.
- 37 source/baseline files and source function definitions were independently hashed. Original consumers perform their own deeper source/equity seals, and consumed source hashes are verified again after each replay. No original file is written.
- Jan4 initialization is genuinely empty for legal A/B: 344 OTHER_UNKNOWN_OR_LEFT rows, all previous sector states unknown. Nonempty pairs are Jan5/Jan6 2022 (30 selected/30 first buys), Sep2/Sep3 2024 (42/42), Jan7/Jan8 2026 (2/2).
- Actual prefix replays through the first OPEN pass for 2022 and 2024. These earlier prefix runs have isolated RESULT files but were executed before the later requirement for exclusive STARTED, so no retrospective start proof is invented.
- Complete 2022/2024 replays have an execution code/fixture seal, exclusive STARTED, run log, explicit RESULT, and separately written outputs. 2026 is source/first-event diagnostic only, without equivalent complete equity replay.

Shared financial rules and ordering are frozen in SHARED_RESEARCH_CONTRACT.md, but the shared adapter is not executed here. No shared cash feasibility, new profit, shared return, new win rate, native-equity equivalence, PIT evidence or exchange tradability is inferred from this regression. All original NON-PIT/NET80/orderability limits remain.

Run artifacts:
- sealed_full_2022/{STARTED.json,RUN_LOG.txt,RESULT.json,LEDGER_QA.json,outputs/}
- sealed_full_2024_924/{STARTED.json,RUN_LOG.txt,RESULT.json,LEDGER_QA.json,outputs/}
- SOURCE_MANIFEST.json, NONEMPTY_FIXTURE_SEAL.json, EXECUTION_SEAL.json, IMPORT_SAFE_QA.json

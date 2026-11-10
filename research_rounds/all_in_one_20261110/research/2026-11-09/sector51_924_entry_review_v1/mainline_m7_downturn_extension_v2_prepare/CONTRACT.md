# Frozen M7 first downturn extension

Research only. Run the completed M7 strategy unchanged from 2024-09-02 through 2024-10-31 in an independent 1,200,000 account. No parameters, alpha, allocations, tickets, fees, market rules, event adapters, signal mappings or suspension rules change. The wrapper imports M7 Data and Engine and uses the exact M7 atomic run-loop source. Only export routing and mandatory prefix comparison are added.

Frozen M7 engine SHA256: 804d56f8b5a8e4b26d5a89caac5874c037911a38c339db9c6dfd5e99882aab6a.

At 2024-10-08, compare every existing M7 JSON output except full-horizon source/output hashes and event-admission inventory. Economic output/state families must match exactly in order and value. Only AVAILABILITY_EVENTS may use full-record multiset comparison, because the inherited diagnostic iterates a set. Any mismatch raises immediately before 10/09 trading. No tolerance, omitted economic fields, or end-only matching.

Existing atomic blockers remain authoritative. Do not synthesize rows, use stale valuation as executable quotes, or admit new events silently. A stop records the last certified day and exact restored-state blocker; it is not a completed extension. Registered v11 suspension policies are not installed speculatively. If actual M7 encounters a held suspension, prepare a separate minimal accounting extension, audit it, and replay this wrapper's full certified prefix before continuing.

Before history: static identity checks and independent exact-hash admission. The parent launches one run after admission. No history was run during wrapper preparation. Report comparable NAV return/drawdown, holdings and exits and any stale valuation separately. The original short-period parameter work is not out-of-sample validation. Later extension of shared signals is bounded above by 2026-06-30; actual tradability/equity/fact blockers determine the certified horizon.

## v2 export-only correction

Prefix comparison runs only for checkpoint_20241008, not final rolled-back exports. The previous wrapper passed the10/8 checkpoint then atomically blocked on10/9 605499.SH unadmitted split+cash event. Do not run this draft until the factual boundary is addressed and the final wrapper is admitted. No alpha or accounting change is installed here.

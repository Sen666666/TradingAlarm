# M8 build ready for independent review

- Historical strategy: NOT RUN. No approval record created. CLI permits only `--mode check`; Engine.run refuses history. The unchanged low-level run_loop is retained for synthetic rollback tests and future reviewed integration, not an authorization boundary.
- Static/synthetic QA: PASS, 68 assertions. No historical Data instance or historical strategy loop was used.
- Single change: surviving EXPANSION SEED/ADD lots receive a completed-CLOSE marker only when sector state=0 and M=0, and retire independently of receiver financing at the next eligible OPEN.
- INITIAL lots, account settings, I/CP protective execution, alpha, cash admission, sizing rules, fees and atomic loop remain inherited. Explicit retirement reason and pending per-lot export are included.
- Existing I/CP exits execute before retirement. Mixed rounds survive with INITIAL quantities intact. Unknown state/M never triggers. T+1, aggregate sell-floor partial quantities and odd remainders were exercised. Eligible lots are combined into one retirement order per stock/day, avoiding duplicated minimum commissions and stranded combinable odd lots.
- CLOSE cash estimation intentionally remains unchanged. This can leave excess planned donors; existing OPEN cash-gap logic cancels those sales, and stale retired-lot plans cannot double-sell. Both zero-gap and positive-gap stale-plan paths passed.
- Held missing-open/nontradable behavior remains the baseline atomic block. No new suspension valuation or quote invention was added. The test does not claim every external suspension encoding is covered.
- Atomic rollback was exercised after actual synthetic retirement orders, restoring cash, lots, markers, orders, candidates and active/archive aliasing; partial orders remain diagnostic only.
- Actual full synthetic export verified PENDING_RETIREMENTS.json and its output hash. Temporary synthetic export artifacts were cleaned up.
- DEPENDENCY_SEAL.json records imported local research code and all frozen baseline files; unchanged hashes were verified after testing. Candidate files are sealed by OUTPUT_SEAL.json.

Review should focus on the irrevocable per-lot marker, unchanged funding estimator, odd-lot remainder behavior, and protection-first execution. There are no concentration caps, profit filters, delay-day knobs or re-entry changes.

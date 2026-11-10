# M8: false-sector, non-mainline expansion retirement

Status: research-only candidate, frozen before synthetic QA; independent review required before any historical run. No live orders. No historical run is authorized by this build.

## Single changed hypothesis
At a completed CLOSE, if and only if sector state equals 0 AND M equals 0, mark every surviving EXPANSION acquisition lot for retirement at the next eligible OPEN. This includes SEED and ADD kinds. INITIAL acquisition lots retain exactly the baseline behavior. Unknown -1 is not false. The trigger has no cash, receiver-demand, profit, concentration, delay-days, or target-weight condition.

Baseline: mainline_m7_downturn_cash_batch_v6/engine.py, SHA256 b81f78fc04dec3709191258230c2e2fa7580f8658315c78e9b25bf3fea318c2e. All source facts, account constants, alpha, M calculation, sizing, fees, corporate-action admission, and existing protection rules are inherited without modification.

## Order and lot boundaries
Use a separate per-lot retirement_signal_day, never an account-level exit flag. Marking is called from plan_transfers, after inherited CLOSE protective decisions and before inherited transfer planning. It does not change the baseline protective flags, buy gate, target calculation, or transfer planning. The pending marker is irrevocable, like an existing locked exit; subsequent recovery does not cancel an already completed-CLOSE retirement instruction. Existing transfer execution sees actual post-exit cash and remaining lots.

At OPEN execute the exact baseline protective exits first. Existing I/CP exits retain their reasons and precedence. Only surviving, unprotected EXPANSION lots with a prior CLOSE marker are aggregated by stock, then sold as one retirement order per stock/day at inherited slippage and fee rules and the dated QuantityRule.sell_floor. The legal aggregate quantity is mapped back in stable lot-ID order. INITIAL quantities never contribute to the sellable retirement total; two eligible 50-share expansion remainders may combine into a legal 100-share order. Protective orders remain separate and execute first. No same-day sale is permitted. A mixed INITIAL/EXPANSION round is never closed merely because an expansion lot retires. Markers remain on unsellable remainders. All sale orders explicitly say FALSE_SECTOR_NON_MAINLINE_EXPANSION_RETIREMENT and carry lot quantities and signal day.

Retirement does not bypass economic_preflight. Inherited M7 held nontradable/missing-quote handling is a fail-closed atomic block, not a newly invented quote or a newly added suspension valuation model. Baseline behavior is preserved. Existing cash/corporate action accounting and all atomic snapshots and log inventories are unchanged; markers live inside snapshotted lots and diagnostics in snapshotted candidates.

## Evaluation boundary
No historical strategy execution in this build. Static and synthetic tests must cover mixed rounds, both expansion kinds, exact tri-state trigger, INITIAL preservation, I/CP precedence, T+1, legal partial quantities, nontradable preflight, atomic rollback, cash independence, and dependency seals. Candidate export uses unchanged economic export without baseline prefix-equality checks, because this is a strategy ablation. Historical entrypoint remains disabled until separately reviewed and authorized; no CONTRACT_APPROVAL is fabricated.

## Observable pending state and unchanged cash planner
Every export adds PENDING_RETIREMENTS.json with remaining lot quantity, signal date, reason, role, kind, round, sector and any superseding protective exit. CLOSE marking diagnostics remain in CANDIDATES. Export hashes cover this addition.

CLOSE estimated proceeds do not include the new separate marker. Therefore existing donor planning can over-plan cash release; this deliberately preserves the frozen funding algorithm. OPEN performs retirement before allocation and transfer execution, whose existing actual-cash gap shrinks or cancels those sales. A stale donor plan for a retired lot is rejected as DONOR_ALREADY_EXITED or RECEIVER_GAP_ZERO. No second sale or new funding algorithm is introduced.

"""Write the fixed implementation contract before any economics."""
from pathlib import Path
import json,datetime
from adapter import O,E,ENGINES,OLD_OUTPUTS,ARMS,sha,save
assert not (O/'CONTRACT.json').exists()
paths=[O.parent/'SPECIFICATION_FREEZE.json',O.parent/'compute_features.py',E/'relative_priority_v1/simulate.py',E/'relative_priority_v1/priority.py',E/'SEALED_ALL_BIRTH_EVENTS.csv']
for window,p in ENGINES.items():
    paths += [p,p.parent/'run.py',p.parent/'report.py',OLD_OUTPUTS[window]/'OUTPUT_HASHES.json',p.parent/'report/CORE_AND_FULL_ROUNDS.csv']
    seal=json.loads((OLD_OUTPUTS[window]/'OUTPUT_HASHES.json').read_text())
    for name,h in seal.items():assert sha(OLD_OUTPUTS[window]/name)==h
save(O/'CONTRACT.json',dict(version='FIXED_CH3_THREE_ARM_LIFECYCLE_V1',frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),arms=ARMS,windows={'2022':['2022-01-01','2022-12-31'],'2024_924':['2024-09-01','2024-12-31']},management_end='2026-06-30',market_events=19795,market_stock_months=14635,
formula='AST-exact frozen calc: 36m m-36..m-1 excess simple monthly return on intercept+CH3; epsilon including intercept; 11m m-12..m-2 mean/sample SD. RAW simple compounded same11m and exactly same known support. Machine epsilon degeneration only.',
queue='Per consumer live FLAT/I/PVR/close PASS first. Compress original PVR/sid feasible slots. Keep all UNKNOWN feasible positions. Permute only known positions by score DESC, PVR DESC, sid ASC. Preserve all infeasible emitted positions. K=min(2,live feasible count), not source queue_rank <=2. Negative scores eligible. Missing cache is fatal.',
reuse='Original repaired source engines loaded unchanged. 2022 functions unchanged. 2024 run_window AST changes only first assertion from A_UNION_B-only to fixed three approved arms. All clocks, prices, exits, fees, adds, sizing, UNKNOWN, entitlement registry and NET80 unchanged.',
isolation='Each consumer reset: independent states, rounds, archives, registrations, claims, snapshots. Arm embedded in round/claim identity. Market data and immutable close validation cache only may be reused. No cash shared or reallocated.',
execution_order='2022 baseline exact raw table/claims/bridges plus original core/financial report reproduction, then RAW then CH3; same for2024. One global exclusive RUN_ONCE marker. Economic run requires separate independent PASS and explicit parent START artifact.',
baseline_expected={'2022':{'legal':5728,'selected':2732,'evidence_usable_closed':2616},'2024_924':{'legal':3505,'selected':1354,'evidence_usable_closed':1312}},
report='Initial-lot core is actual FULL entry/exit with independently dated fees and own core NET80 claim, not separate CORE lifecycle. Report all permits/statuses and financial UNKNOWN, evidence usable closed separately; strict positive wins, zero separate, average net CNY and mean returns, winner/loser sums/means, payoff strict loss denominator, >=50% tails. Same-stock actual entries and own gross/net, unknowns never substituted with zero.',
accounting='Raw open gross - exact5bp slippage impact - dated fees + NET80 = net; actual fill gross is after slippage before fees. Independently summed stock amounts are not account return.',
limits=['No PIT claim: current revised factors and static pool/industry; historical release unknown; m-1 affects regression','Native adjusted close not certified total shareholder return','Same finite window-specific rights evidence as repaired originals; unknowns nonrandom','FAST independent unchanged absent','No new data sourcing, no installation, no external orders','No searches, no refits, no sign flips, no results-driven reruns'],source_hashes={str(p):sha(p) for p in paths}))
print('CONTRACT_FROZEN')

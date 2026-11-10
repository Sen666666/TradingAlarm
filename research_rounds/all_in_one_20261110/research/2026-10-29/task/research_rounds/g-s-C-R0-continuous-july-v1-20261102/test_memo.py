"""Pure immutable C projection memo checks on frozen real snapshots. No event."""
import copy,pickle,time
from pathlib import Path
import month_r0 as X
E=X.E;R=X.HERE
records=[]
for mode in ['C10','C_BATCH20']:
 p=X.M.HERE/'runs'/('2025_26-'+mode)/'2025-07-22-CLOSE.pkl';side=X.read(p.with_suffix('.provenance.json'));assert X.sha(p)==side['checkpoint_sha256']
 r=pickle.loads(p.read_bytes());assert r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity']
 cid=r.active['certificate_id'];c=r.authority.certificates[cid];v=r.trusted[c['trusted_id']];args=[v['snapshot'],v['demands'],v['evidence'],v['budget_before']]
 golden=next(z['projection'] for z in r.results if z['certificate']['certificate_id']==cid);fn=r._solve;start=time.perf_counter();before=E.digest(r.account.exported(r.last_completed_event))
 a=X.memo_solve(r,fn,*args);miss_secs=time.perf_counter()-start;assert E.digest(a)==E.digest(golden)
 t=time.perf_counter();b=X.memo_solve(r,fn,*args);hit_secs=time.perf_counter()-t;assert E.digest(b)==E.digest(golden)
 sid=next(iter(b['Q']));b['Q'][sid]+=1;again=X.memo_solve(r,fn,*args);assert E.digest(again)==E.digest(golden),'caller changed cached result'
 cache=copy.deepcopy(r._pure_projection_memo);r._pure_projection_memo['value']['Q'][sid]+=1
 try:X.memo_solve(r,fn,*args)
 except ValueError:tamper=True
 else:raise AssertionError('cache tamper accepted')
 r._pure_projection_memo=cache;changed=copy.deepcopy(args);changed[0]['available']+=1
 try:X.memo_solve(r,fn,*changed)
 except ValueError:input_miss_guard=True
 else:raise AssertionError('changed snapshot reused old budget/source binding')
 assert E.digest(r.account.exported(r.last_completed_event))==before
 records.append(dict(mode=mode,source_checkpoint_sha256=X.sha(p),golden_hash=E.digest(golden),memo_miss_same_numeric_body=True,memo_hit_same_numeric_body=True,miss_seconds=miss_secs,hit_seconds=hit_secs,caller_copy_isolated=True,cache_tamper_rejected=tamper,changed_actual_snapshot_rejected_by_original_guard=input_miss_guard,financial_events=0))
 print('MEMO_PROOF_PASS',mode,'miss',round(miss_secs,3),'hit',round(hit_secs,3),flush=True)
X.save(R/'MEMO_GATE.json',dict(passed=True,rows=records,financial_events=0,guards_not_skipped='All original verify_native checks still execute; only identical _solve pure projection repeated computation reused',not_cached=['live resources','_preview','order quantity','fees','fills','settlements']))

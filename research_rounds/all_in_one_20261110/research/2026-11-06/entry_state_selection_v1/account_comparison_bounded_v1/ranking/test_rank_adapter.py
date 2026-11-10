from pathlib import Path
import json, hashlib
from copy import deepcopy
from collections import Counter
import pandas as pd
from pending_rank_adapter import rank_pending
O=Path(__file__).resolve().parent
R=O.parent.parent

def queue(x):return list(dict.fromkeys(i['sid'] for i in sorted(x,key=lambda i:(i['rank'],i['role']!='core'))))
def invariants(before,after):
 assert Counter((i['sid'],i['role']) for i in before)==Counter((i['sid'],i['role']) for i in after)
 assert [{k:v for k,v in i.items() if k!='rank'} for i in before]==[{k:v for k,v in i.items() if k!='rank'} for i in after]
 assert sorted(set(i['rank'] for i in before))==sorted(set(i['rank'] for i in after))
 for s in queue(after):assert len({i['rank'] for i in after if i['sid']==s})==1
 for s in queue(after):
  roles=[i['role'] for i in sorted(after,key=lambda i:(i['rank'],i['role']!='core')) if i['sid']==s]
  if len(roles)==2:assert roles==['core','mobile']

def toy():
 day='2024-01-01'
 x=[dict(sid=str(i),role='mobile' if i==0 else 'core',rank=i*3+2,PVR_score=99-i,payload={'x':[1,2]}) for i in range(25)]
 x[1]['PVR_score']=None
 x.append(dict(x[10],role='mobile'))
 states=[dict(sid=str(i),day=day,state='FIRST_BREAK' if i>=20 else 'CONFIRMED',first_break_day=day) for i in range(5,25)]
 before=deepcopy(x);out,a,s=rank_pending(x,states,day);invariants(x,out);assert x==before
 expected=['20','1','5','6','7','21','8','9','10','22','11','12','13','23','14','15','16','24','17','18','19','0','2','3','4']
 assert queue(out)==expected,(queue(out),expected)
 assert next(i for i in out if i['sid']=='1')['rank']==5
 # Empty state source retains original queue and MOBILE without i_buy.
 out,_,_=rank_pending(x,[],day);assert queue(out)==queue(x);invariants(x,out)
 # Shortage compresses reservations then original-queue fallback.
 short=[dict(sid='24',day=day,state='FIRST_BREAK',first_break_day=day),dict(sid='23',day=day,state='CONFIRMED')]
 out,_,_=rank_pending(x,short,day);assert queue(out)[:5]==['24','1','23','0','2'];invariants(x,out)
 # Stale FIRST_BREAK never counts as current local first day.
 stale=[dict(sid='24',day=day,state='FIRST_BREAK',first_break_day='2023-12-31')]
 assert queue(rank_pending(x,stale,day)[0])==queue(x)
 # Missing score even on fresh state cannot move.
 pinned=[dict(sid='1',day=day,state='FIRST_BREAK',first_break_day=day)]
 assert queue(rank_pending(x,pinned,day)[0])==queue(x)
 for bad in [x+[deepcopy(x[0])],[dict(i,rank=2) for i in x]]:
  try:rank_pending(bad,[],day)
  except AssertionError:pass
  else:raise AssertionError('invalid roles/ranks accepted')
 empty=rank_pending([],[],day);assert empty[0]==[]
 return ['exact_1_plus_3_native_order','missing_score_pinned','missing_state_and_mobile_retained','shortage_fallback','dual_role_shared_rank_core_first','duplicate_role_rejected','duplicate_stock_rank_rejected','stale_first_break_excluded','empty_queue','nonrank_deep_equality','input_immutability']

def main():
 tests=toy()
 source=R/'equal_entry_validation_v1/ALL_ORIGINAL_I_BUY_WITH_STATES.parquet'
 cols=['sid','day','state','first_break_day']
 f=pd.read_parquet(source,columns=cols)
 summaries=[];hashes={str(source):hashlib.sha256(source.read_bytes()).hexdigest()}
 for day in ['2024-09-24','2026-01-15']:
  p=R/'account_integration_audit_v1'/f'{day}_FROZEN_NATIVE_INTENTS.json';hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  x=json.loads(p.read_text()); frozen=deepcopy(x)
  rows=f[f.day.eq(day)].where(pd.notnull(f),None).to_dict('records')
  out,a,s=rank_pending(x,rows,day);invariants(x,out);assert x==frozen
  # Add corrupted future rows (including same SID), and prior rows, no effects.
  future=[dict(r,day='2099-01-01',state='CONFIRMED',first_break_day='2099-01-01') for r in rows]
  prior=[dict(r,day='1900-01-01',state='FIRST_BREAK',first_break_day='1900-01-01') for r in rows]
  assert rank_pending(x,rows+future+prior,day)==(out,a,s)
  # Replacing future tail with entirely novel states is equally irrelevant.
  assert rank_pending(x,rows+[dict(sid='NOT_PENDING',day='2099-02-01',state='FIRST_BREAK')],day)==(out,a,s)
  q=sorted(a,key=lambda r:r['final_slot'])
  pd.DataFrame(q).to_csv(O/f'{day}_NEW_QUEUE.csv',index=False)
  pd.DataFrame([r for r in a if r['original_rank']!=r['new_rank']]).to_csv(O/f'{day}_RANK_CHANGES.csv',index=False)
  pd.DataFrame(a).to_csv(O/f'{day}_STATE_AVAILABILITY.csv',index=False)
  (O/f'{day}_TOP20.json').write_text(json.dumps(q[:20],indent=2,allow_nan=False))
  (O/f'{day}_RANK_ONLY_INTENTS.json').write_text(json.dumps(out,indent=2,allow_nan=False))
  s.update(nonrank_intents_equal=True,stock_role_multiset_equal=True,numeric_rank_slots_equal=True,future_row_perturbation_invariant=True,input_unchanged=True,top20_state_counts=dict(Counter(r['state'] or 'MISSING' for r in q[:20])))
  summaries.append(s)
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
 result=dict(status='PASS_PURE_RANK_TESTS_ONLY',account_runs=0,runner_imports=0,economics='NOT_RUN',toy_tests=tests,dates=summaries,input_sha256=hashes,limitations=['Frozen state source is canonical local I-buy states, not raw-account-price recomputation.','Future-row perturbation tests lookup isolation, not proof of upstream state causality.','Existing priority_rank and priority_policy fields are historical and preserved; consumer must sort literal rank.','Native pending 5/15 is a new bounded hypothesis, not original 5517 daily20.'])
 (O/'TEST_RESULTS.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()

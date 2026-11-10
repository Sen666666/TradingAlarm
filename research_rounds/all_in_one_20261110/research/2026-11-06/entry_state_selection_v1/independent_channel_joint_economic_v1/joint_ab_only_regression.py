"""G1 joint scheduler AB-only regression. Every PRICE entry point is poisoned.
No PRICE offers, market facts, sizes, books, orders or economics can run.
"""
from pathlib import Path
import argparse, hashlib, json
import baseline_regression as base
from joint_engine import JointConsumer
from gates import require_specification
ROOT=Path(__file__).resolve().parent
class PriceForbidden:
 def __getattr__(self,name):
  raise AssertionError('PRICE_DISABLED_FOR_JOINT_AB_REGRESSION:'+name)
def reject_price(*args,**kwargs):
 raise AssertionError('PRICE_DISABLED_FOR_JOINT_AB_REGRESSION')
def main():
 p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);p.add_argument('--revision',choices=['','v2'],default='');args=p.parse_args();w=args.window;tag=w+('_'+args.revision if args.revision else '')
 require_specification();dest=ROOT/('joint_ab_only_regression_'+tag);assert not dest.exists()
 names=['joint_ab_only_regression.py','joint_engine.py','joint_policy.py','execution_book.py','gates.py','baseline_regression.py']
 sealed={n:base.sha(ROOT/n) for n in names}
 expected=ROOT/('baseline_regression_'+w)
 legacy=base.BASE/base.CONFIG[w][0]
 before={str(p):base.sha(p) for folder in [expected,legacy/base.CONFIG[w][1]] for p in folder.rglob('*') if p.is_file()}
 base.save(ROOT/('JOINT_AB_ONLY_STARTED_'+tag+'.json'),dict(scope='G1_BASELINE_ONLY_NEW_JOINT_SCHEDULER',price_enabled=False,code_sha256=sealed,reference_hashes=before))
 s=base.load_engine(w);permits_hash=hashlib.sha256(s.ev.to_csv(index=False).encode()).hexdigest()
 c=JointConsumer(s,PriceForbidden(),w);c.arm='A_UNION_B';c.sizing=PriceForbidden()
 for name in ['price_entry_open','price_held_open','price_held_close','_proxy_buy','_view','_receipt','_candidate_frame','run_authorized']:setattr(c,name,reject_price)
 s.reset(True);groups={d:g.to_dict('records') for d,g in s.ev.groupby('day',sort=True)}
 old_dec=s.pd.read_csv(expected/'DECISIONS.csv',float_precision='round_trip',low_memory=False)
 old_selected={s.pd.Timestamp(d):g.event_id.tolist() for d,g in old_dec[old_dec.selected].groupby('day',sort=True)}
 days=0
 try:
  for k,day in enumerate(s.cal):
   if day<c.start or day>s.END:continue
   prev=s.cal[k-1] if k else None;n=len(s.decisions)
   c.process_day(day,prev,groups.get(day,[]),price_rows=[])
   actual=[r['event_id'] for r in s.decisions[n:] if r['selected']]
   assert actual==old_selected.get(day,[]),('FIRST_SELECTED_DIVERGENCE',str(day),actual,old_selected.get(day,[]))
   assert not c.books and not c.price_audit and not c.frozen_responsibilities
   assert all(r['owner_lane']=='AB' for r in c.offer_audit)
   days+=1
   if k%250==0:print('JOINT_AB_DAY',w,str(day.date()),len(s.rounds),flush=True)
  for sid,st in c.states.items():
   if st['state']=='HELD':s.record(st,'OPEN_CENSORED_AT_2026_06_30',s.END)
   elif st['state']=='BUY_PENDING':s.record(st,'BUY_PENDING_CENSORED_AT_DATA_END',s.END)
   s.blocks.append(dict(window=c.window,arm=c.arm,sid=sid,final_state=st['state'],round_id=st['round_id']))
  s.finalize();s.dump(dest)
  checks={name:base.compare_csv(dest/(name+'.csv'),expected/(name+'.csv'),selected=False) for name in ['ROUNDS','ACTIONS','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES']}
  for name in ['CLAIMS','BRIDGES','LEDGER_QA']:
   a=base.read(dest/(name+'.json'));b=base.read(expected/(name+'.json'));assert a==b,(name,'JSON_EXACT_MISMATCH')
   checks[name]=dict(rows=len(a),exact=True,sha256=base.sha(dest/(name+'.json')),reference_sha256=base.sha(expected/(name+'.json')))
  # DECISIONS/ranking are intentionally different audit schemas. Compare selected
  # sequence/PVR and every PASS candidate, not original queue_rank semantics.
  old_cols,old_rows=base.csv_rows(expected/'DECISIONS.csv');_,new_rows=base.csv_rows(dest/'DECISIONS.csv')
  old_pass=[r for r in old_rows if r['decision'] in ('SELECTED_PENDING','PASS_NOT_TOP2')]
  assert len(old_pass)==len(new_rows)
  common=[k for k in old_cols if k in new_rows[0] and k!='queue_rank']
  for i,(a,b) in enumerate(zip(new_rows,old_pass)):
   for key in common:assert base.exact_cell(a[key],b[key]),('PASS_CANDIDATE_DIFF',i,key,a[key],b[key])
  diagnostics=[]
  old_by={r['event_id']:r for r in old_rows};new_by={r['event_id']:r for r in new_rows}
  for r in old_rows:
   if r['queue_rank']!='':
    n=new_by.get(r['event_id']);closefail=r['decision'].startswith('CLOSE_')
    diagnostics.append(dict(event_id=r['event_id'],day=r['day'],sid=r['sid'],sector=r['sector'],PVR_score=r['PVR_score'],original_decision=r['decision'],original_queue_rank=r['queue_rank'],joint_feasible_rank=n.get('joint_feasible_rank',n['queue_rank']) if n else None,close_failed=closefail,selected=r['selected'],rank_differs=n is not None and not base.exact_cell(r['queue_rank'],n.get('joint_feasible_rank',n['queue_rank']))))
  s.pd.DataFrame(diagnostics).to_csv(dest/'RANK_SEMANTIC_DIFFERENCES.csv',index=False)
  s.pd.DataFrame(c.offer_audit).to_csv(dest/'AB_OFFER_AUDIT.csv',index=False)
  s.pd.DataFrame(c.ab_decision_audit).to_csv(dest/'AB_ORIGINAL_DECISION_AUDIT.csv',index=False)
  ineligible=[x for x in c.offer_audit if x['result']=='AB_ORIGINAL_CLOSE_INELIGIBLE' and x.get('close_check') is not None]
  failed_ids={x['event_id'] for x in diagnostics if x['close_failed']}
  assert failed_ids=={x['event_id'] for x in ineligible},'CLOSE_FAIL_OFFER_COVERAGE'
  assert hashlib.sha256(s.ev.to_csv(index=False).encode()).hexdigest()==permits_hash
  for path,h in before.items():assert base.sha(path)==h,('OLD_CHANGED',path)
  for n,h in sealed.items():assert base.sha(ROOT/n)==h,('CODE_CHANGED_DURING_RUN',n)
  qa=dict(result='PASS_JOINT_SCHEDULER_AB_ONLY_EXACT',window=w,days=days,checks=checks,original_permit_rows=len(s.ev),permit_hash_unchanged=permits_hash,all_selected_events_order_exact=True,all_pass_candidates_original_common_fields_except_queue_rank_exact=True,pass_candidates=len(new_rows),selected=len(s.rounds),old_decisions=len(old_rows),new_decisions=len(new_rows),close_fail_original_ranked=len(failed_ids),pass_rank_differences=sum(x['rank_differs'] for x in diagnostics),selected_rank_differences=sum(x['rank_differs'] and x['selected']=='True' for x in diagnostics),ranking_semantics='Original queue_rank counts I/PVR legal close failures and the new queue_rank preserves it; joint_feasible_rank counts only feasible PASS options. Full DECISIONS/RANKING_AUDIT exact is NOT claimed.',price_calls=0,price_books=0,price_offers=0,new_price_economic_runs=0,real_orders=0,source_files_unchanged=True,code_sha256=sealed)
  base.save(dest/'JOINT_AB_EXACT_QA.json',qa)
  base.save(dest/'JOINT_AB_OUTPUT_HASHES.json',{p.name:base.sha(p) for p in dest.iterdir() if p.is_file()})
  print('JOINT_AB_PASS',w,{k:v['rows'] for k,v in checks.items()},'rank differences',qa['pass_rank_differences'],flush=True)
 except Exception as exc:
  failure=ROOT/('JOINT_AB_ONLY_FAILURE_'+tag+'.json')
  if not failure.exists():base.save(failure,dict(error=repr(exc),day=str(locals().get('day')),completed_days=days,rounds=len(s.rounds),actions=len(s.actions),code_sha256=sealed,price_calls=0))
  raise
if __name__=='__main__':main()

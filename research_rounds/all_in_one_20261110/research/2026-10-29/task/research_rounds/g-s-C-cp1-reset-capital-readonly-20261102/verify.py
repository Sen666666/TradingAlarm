"""Causal lineage regressions and actual saved-trace prefix equality; no account step."""
import sys,pickle
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import analyze as A
def fixture(rows):
 cp=[];facts={}
 for day,phase,reason,receipt,valid in rows:
  cp.append(dict(sid='X',day=day,phase=phase,reset_reason=reason,receipt=receipt,e0_valid=valid))
  facts[('X',day)]=dict(segment_id=0,i_target=int(valid),e0_target=int(valid),close=10)
 return A.scan(pd.DataFrame(cp),facts)
def main():
 x=fixture([('1','UP','receipt_consumed',True,True),('2','UP',None,False,True),('3','UP','receipt_consumed',True,True),('4','SEEK','E0_down_reset',False,True),('5','SEEK','lower_anchor',False,True),('6','SEEK','receipt_consumed',True,True),('7','UP','receipt_consumed',True,True)])
 assert x[('X','3')]['kind']=='UP_CONTINUATION'
 assert x[('X','6')]['kind']=='RESET_SEEK_REPAIR' and x[('X','6')]['I_target']==1
 assert x[('X','6')]['negative_reset_observed'] and x[('X','6')]['lower_anchor_observed']
 assert x[('X','7')]['kind']=='UP_CONTINUATION' and x[('X','6')]['diagnostic_root_id']==x[('X','7')]['diagnostic_root_id']
 y=fixture([('1','SEEK',None,False,True),('2','SEEK','receipt_consumed',True,True)])
 assert y[('X','2')]['kind']=='SEEK_ORIGIN_UNKNOWN'
 z=fixture([('1','SEEK','E0_down_reset',False,True),('2',None,'E0_invalid',False,False),('3','SEEK','start',False,True),('4','SEEK','receipt_consumed',True,True)])
 assert z[('X','4')]['kind']=='START_SEEK_FIRST' and not z[('X','4')]['negative_reset_observed']
 A.M.guard();p=A.MONTH/'runs/2025_26-C10/2025-07-31-CLOSE.pkl';r=pickle.loads(p.read_bytes());cp=A.clean(r.inputs.table('cp').to_dict('records'));ff=A.clean(r.inputs.table('facts').to_dict('records'));fm={(v['sid'],v['day']):v for v in ff};full=A.scan(pd.DataFrame(cp),fm);checks=[]
 for day in ('2025-07-08','2025-07-22','2025-07-29'):
  cut=A.scan(pd.DataFrame([z for z in cp if z['day']<=day]),{k:v for k,v in fm.items() if k[1]<=day});gold={k:v for k,v in full.items()if k[1]<=day};assert A.J.digest(A.clean(cut))==A.J.digest(A.clean(gold));checks.append(dict(day=day,exact=True,receipt_records=len(cut)))
 checks0=A.read(HERE/'CHECKS.json');summary=A.read(HERE/'SUMMARY.json');events=A.read(HERE/'EVENTS.json')
 assert len({A.J.digest([(e['sid'],e['day'],e['canonical_id'],e['classification'])for e in es])for es in events.values()})==1
 for arm,groups in summary.items():
  assert sum(z['events']for z in groups.values())==3336 and sum(z['Q_unknown']for z in groups.values())==8 and sum(z['Q_false']for z in groups.values())==0
  assert sum(z['layers']for z in groups.values())+len(checks0[arm]['core_only_or_nonfresh_layers'])==checks0[arm]['actual_layer_total']
  all_l=A.read(A.MONTH/'july_end_analysis/ALL_LAYERS.json')[arm]
  assert sum((A.D(z['total_contribution'])for z in all_l),A.Z)==sum((A.D(z['actual_realized'])+A.D(z['unrealized'])+A.D(z['booked_dividend'])for z in groups.values()),A.Z)+sum((A.D(z['total_contribution'])for z in checks0[arm]['core_only_or_nonfresh_layers']),A.Z)
 A.save('VERIFICATION.json',dict(passed=True,lineage_fixture_assertions=6,actual_saved_trace_prefix_checks=checks,full_mother_same_across_accounts=True,unknown_Q_not_false=True,all_layer_contribution_bridge=True,account_events=0))
 print('VERIFY_PASS',flush=True)
if __name__=='__main__':main()

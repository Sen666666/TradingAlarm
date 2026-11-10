"""Compare complete saved economic/strategy views, retaining raw provenance."""
from pathlib import Path
import json,copy,sys
import c_horizon as C
E=C.E;HERE=C.HERE
def normalized(r):
 x=dict(observable=r.observable(r.last_completed_event),lifecycle=r.lifecycle,last_stock_state=r.last_stock_state,cursor=r.cursor,goal_intents=r.goal_intents,busy=r._busy_goals,active_intents=getattr(r,'active_intents',None),rank_bindings=r.rank_bindings,native_audit=r.account.audit_log,native_decisions=r.account.decisions)
 x=json.loads(json.dumps(x,default=E.encode));binding=r.source_binding();ids={cid:'CERT|'+r.mode+'|'+r.window+'|'+c['known_at'] for cid,c in r.authority.certificates.items()}
 def norm(z,key=None):
  if key=='source_binding' and isinstance(z,dict) and z==binding:return {'separately_verified_branch_source_binding':True}
  if isinstance(z,dict):return {norm(k):norm(v,k) for k,v in z.items() if k not in ('input_manifest','input_sha256')}
  if isinstance(z,list):return [norm(v) for v in z]
  if isinstance(z,str):
   for cid,logical in ids.items():z=z.replace(cid,logical)
  return z
 return norm(x)
def main():
 window,mode=sys.argv[1:3];root=HERE/'runs'/(window+'-'+mode);day=C.DATES[window];rows=[]
 phases=['IMPORT']+(['ACTION'] if window=='2025_26' else [])+['OPEN','CLOSE']
 for phase in phases:
  states=[]
  for branch in ('full','physical'):
   p=root/branch/('state/IMPORT.pkl' if phase=='IMPORT' else day+'-'+phase+'.pkl');r=C.HorizonRunner.restore(p);states.append(normalized(r))
  if states[0]!=states[1]:
   E.IO.write_json(root/('COMPARE-'+phase+'-FAIL.json'),dict(full=states[0],physical=states[1]),encoder=E.encode)
   raise AssertionError('full economic/strategy state differs at '+phase)
  rows.append(dict(phase=phase,full_economic_and_strategy_view_equal=True,hash=E.digest(states[0]),includes_native_audit_and_decisions=True))
 E.IO.write_json(root/'COMPARISON.json',dict(passed=True,window=window,mode=mode,rows=rows,provenance_exceptions=['only branch input_manifest/input_sha256','current source_binding dictionaries independently verified under each frozen branch','certificate ids mapped by exact mode/window/known_at; quantities/receipts/deadlines/projections/budgets preserved'],physical_branch_not_formal_path=True),encoder=E.encode)
 print('COMPARISON_PASS',window,mode,flush=True)
if __name__=='__main__':main()

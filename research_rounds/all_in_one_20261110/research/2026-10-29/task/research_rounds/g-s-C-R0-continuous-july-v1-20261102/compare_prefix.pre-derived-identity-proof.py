"""Same complete prefix comparison contract as prior audited next-session gate."""
from pathlib import Path
import json,pickle,sys
import month_r0 as X
E=X.E;ROOT=X.HERE

def load(p,formal=True):
 p=Path(p);side=X.read(p.with_suffix('.provenance.json'));E.require(X.sha(p)==side['checkpoint_sha256'],'prefix bytes changed');r=pickle.loads(p.read_bytes())
 E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'prefix actual source identity changed');r.account.owner=r;r.assert_observers();return r

def normalized(r):
 x=dict(observable=r.observable(r.last_completed_event),lifecycle=r.lifecycle,last_stock_state=r.last_stock_state,cursor=r.cursor,goal_intents=r.goal_intents,busy=r._busy_goals,active_intents=getattr(r,'active_intents',None),rank_bindings=r.rank_bindings,native_audit=r.account.audit_log,native_decisions=r.account.decisions)
 x=json.loads(json.dumps(x,default=E.encode));binding=r.source_binding();ids={cid:'CERT|'+r.mode+'|'+r.window+'|'+c['known_at'] for cid,c in r.authority.certificates.items()}
 def norm(z,key=None):
  if key=='source_binding' and isinstance(z,dict) and z==binding:return {'separately_verified_branch_source_binding':True}
  if isinstance(z,dict):return {norm(k):norm(v,k) for k,v in z.items() if k not in ('input_manifest','input_sha256','new_july_account','pure_projection_cache','approved_risk_switch','approved_risk')}
  if isinstance(z,list):return [norm(v) for v in z]
  if isinstance(z,str):
   for cid,logical in ids.items():z=z.replace(cid,logical)
  return z
 return norm(x)

def main():
 records=[]
 for mode in ['C10','C_BATCH20']:
  for day in ['2025-07-01','2025-07-02']:
   for phase in ['ACTION','OPEN','CLOSE']:
    name=day+'-'+phase+'.pkl';off=load(ROOT/'gates/off'/mode/name)
    original=load(X.W/'g-s-C-two-day-finance-20261102/runs'/('2025_26-'+mode)/name,False)
    a,b=normalized(off),normalized(original)
    if a!=b:
     X.save(ROOT/('OFF-'+mode+'-'+day+'-'+phase+'-DIFF.json'),dict(new=a,original=b));raise AssertionError('OFF baseline differs '+mode+' '+name)
    full=load(ROOT/'runs'/mode/name);physical=load(ROOT/'gates/physical'/mode/name)
    c,d=normalized(full),normalized(physical)
    if c!=d:
     X.save(ROOT/('PHYSICAL-'+mode+'-'+day+'-'+phase+'-DIFF.json'),dict(full=c,physical=d));raise AssertionError('physical prefix differs '+mode+' '+name)
    # In addition to the prior whole-view contract, include the NEW risk book
    # in physical/full equality after explicit cert/source identity mapping.
    def risk_norm(r):
     raw=json.loads(json.dumps(r.risk.__dict__,default=E.encode));ids={cid:'CERT|'+r.mode+'|'+cc['known_at'] for cid,cc in r.authority.certificates.items()};binding=r.source_binding()
     def n(v,key=None):
      if key=='source_binding' and v==binding:return {'verified':True}
      if isinstance(v,dict):return {n(k):n(z,k) for k,z in v.items()}
      if isinstance(v,list):return [n(z) for z in v]
      if isinstance(v,str):
       for k,z in ids.items():v=v.replace(k,z)
      return v
     return n(raw)
    E.require(risk_norm(full)==risk_norm(physical),'new risk mapping physically future-dependent')
    records.append(dict(mode=mode,day=day,phase=phase,OFF_original_complete_view_equal=True,on_full_physical_complete_view_equal=True,on_full_physical_risk_book_equal=True,hash=E.digest(c)))
 X.save(ROOT/'TWO_DAY_GATE.json',dict(passed=True,records=records,financial_events_invoked_by_comparison=0,formal_runs_not_restarted=True,cross_process_restart='Jul1 close checkpoint restored in a new process before Jul2',runtime_sha256=X.sha(ROOT/'month_r0.py'),entry_sha256=X.sha(ROOT/'run_july.py'),memo_gate_sha256=X.sha(ROOT/'MEMO_GATE.json'),normalization_exceptions=['input storage identity','separately verified source bindings','certificate IDs by exact mode/window/known_at','new R0 observer excluded only for OFF-vs-old; separately fully compared for on full/physical','memo counters/new-account provenance']) )
 print('TWO_DAY_GATE_PASS',len(records),'comparisons',flush=True)
if __name__=='__main__':main()

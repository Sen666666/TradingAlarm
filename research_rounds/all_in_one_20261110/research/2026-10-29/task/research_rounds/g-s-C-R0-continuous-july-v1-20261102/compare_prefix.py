"""Same complete prefix comparison contract as prior audited next-session gate."""
from pathlib import Path
import json,pickle,sys,copy,hashlib
import month_r0 as X
E=X.E;ROOT=X.HERE

def load(p,formal=True):
 p=Path(p);side=X.read(p.with_suffix('.provenance.json'));E.require(X.sha(p)==side['checkpoint_sha256'],'prefix bytes changed');r=pickle.loads(p.read_bytes())
 E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'prefix actual source identity changed');r.account.owner=r;r.assert_observers();return r

_contexts={}
def witness(root):
 """Prove every normalized derived hash from its full, guarded source body.
 No finance invoked. The necessary-stage body is reconstructed ONLY for
 these D-empty prefixes by restoring the pre-optional native goal registry;
 its exact stored digest is mandatory, not an assumed equivalence.
 """
 root=Path(root)
 if str(root) in _contexts:return _contexts[str(root)]
 last=load(root/'2025-07-02-CLOSE.pkl');ids={};proofs=[]
 for cid,c in last.authority.certificates.items():
  tag=last.mode+'|'+last.window+'|'+c['known_at'];ids[cid]='CERT|'+tag
  v=last.trusted[c['trusted_id']];s,ds,e,bb=v['snapshot'],v['demands'],v['evidence'],v['budget_before']
  E.require(c['certificate_id']==E.digest({k:z for k,z in c.items() if k!='certificate_id'}),'raw cert content hash')
  E.require(c['trusted_id']==E.digest(dict(s=s,ds=ds,e=e,bb=bb)) and c['snapshot_hash']==E.digest(s),'raw trusted content hash')
  result=next(z['projection'] for z in last.results if z['certificate']['certificate_id']==cid)
  E.require(last._solve(s,ds,e,bb)==result and E.digest(result)==c['projection_hash'],'raw original pure result must exactly recompute')
  ss,dd,audit=X.R.M.C.transform(s,ds,e)
  ids[c['trusted_id']]='TRUSTED|'+tag;ids[c['snapshot_hash']]='SNAPSHOT|'+tag
  ids[E.digest(ss)]='RANKED_SNAPSHOT|'+tag
  # Identical s/ss (no ranked lots) must share the same canonical identity.
  if E.digest(ss)==c['snapshot_hash']:ids[c['snapshot_hash']]='SNAPSHOT|'+tag
  for k in ('result_id','base_B_result_id','base_private_B_result_id'):
   if k in result:ids[result[k]]=k+'|'+tag
  ids[c['projection_hash']]='PROJECTION|'+tag
  if 'budget_after_sha256' in result:
   E.require(result['budget_after_sha256']==hashlib.sha256(result['budget_after'].encode()).hexdigest(),'budget bytes hash')
   ids[result['budget_after_sha256']]='BUDGET_BYTES|'+tag
  proofs.append(dict(at=c['known_at'],trusted=v,ranked_snapshot=ss,ranked_demands=dd,projection=result))
 necessary=[]
 for day in ('2025-07-01','2025-07-02'):
  close=last if day=='2025-07-02' else load(root/(day+'-CLOSE.pkl'));op=X.read(root/(day+'-OPEN.json'));at=close.last_completed_event
  E.require(not close.results[-1]['projection']['D'],'necessary-stage reconstruction only valid for D-empty gate')
  acc=close.account;old_goals=acc.funding.goals;acc.funding.goals=copy.deepcopy(op['account']['funding_coverage']['goals'])
  body=copy.deepcopy(dict(account=acc.exported(at),f1={k:X.asdict(v) for k,v in close.f1.items()},f1seq=close.f1seq,cursor=close.cursor));acc.funding.goals=old_goals
  raw=close.close_stages[at.isoformat()]['necessary_digest'];E.require(E.digest(body)==raw,'exact necessary-stage body not reconstructible; no opaque hash ignored')
  ids[raw]='NECESSARY|'+last.mode+'|'+day;necessary.append(dict(at=at,body=body))
 _contexts[str(root)]=dict(ids=ids,proofs=proofs,necessary=necessary);print('PROVED_SOURCE_BODIES',str(root),flush=True);return _contexts[str(root)]

def normalized(r,root):
 ctx=witness(root)
 x=dict(observable=r.observable(r.last_completed_event),lifecycle=r.lifecycle,last_stock_state=r.last_stock_state,cursor=r.cursor,goal_intents=r.goal_intents,busy=r._busy_goals,active_intents=getattr(r,'active_intents',None),rank_bindings=r.rank_bindings,native_audit=r.account.audit_log,native_decisions=r.account.decisions,derived_hash_source_bodies=ctx['proofs'],necessary_hash_source_bodies=ctx['necessary'])
 x=json.loads(json.dumps(x,default=E.encode));binding=r.source_binding();ids=ctx['ids']
 def norm(z,key=None):
  if key=='source_binding' and isinstance(z,dict) and z==binding:return {'separately_verified_branch_source_binding':True}
  if isinstance(z,dict):return {norm(k):norm(v,k) for k,v in z.items() if k not in ('input_manifest','input_sha256','new_july_account','pure_projection_cache','approved_risk_switch','approved_risk')}
  if isinstance(z,list):return [norm(v) for v in z]
  if isinstance(z,str):
   if z.startswith('{"body"'):
    b=json.loads(z);E.require(b['state_id']==E.digest(b['body']),'raw budget state hash');body=norm(b['body']);return dict(body=body,state_id=E.digest(body))
   for raw,logical in ids.items():z=z.replace(raw,logical)
  return z
 return norm(x)

def main():
 records=[]
 for mode in ['C10','C_BATCH20']:
  for day in ['2025-07-01','2025-07-02']:
   for phase in ['ACTION','OPEN','CLOSE']:
    name=day+'-'+phase+'.pkl';off=load(ROOT/'gates/off'/mode/name)
    original=load(X.W/'g-s-C-two-day-finance-20261102/runs'/('2025_26-'+mode)/name,False)
    a,b=normalized(off,ROOT/'gates/off'/mode),normalized(original,X.W/'g-s-C-two-day-finance-20261102/runs'/('2025_26-'+mode))
    if a!=b:
     X.save(ROOT/('OFF-'+mode+'-'+day+'-'+phase+'-DIFF.json'),dict(new=a,original=b));raise AssertionError('OFF baseline differs '+mode+' '+name)
    full=load(ROOT/'runs'/mode/name);physical=load(ROOT/'gates/physical'/mode/name)
    c,d=normalized(full,ROOT/'runs'/mode),normalized(physical,ROOT/'gates/physical'/mode)
    if c!=d:
     X.save(ROOT/('PHYSICAL-'+mode+'-'+day+'-'+phase+'-DIFF.json'),dict(full=c,physical=d));raise AssertionError('physical prefix differs '+mode+' '+name)
    # In addition to the prior whole-view contract, include the NEW risk book
    # in physical/full equality after explicit cert/source identity mapping.
    def risk_norm(r):
     raw=json.loads(json.dumps(r.risk.__dict__,default=E.encode));root=ROOT/'runs'/r.mode if r.branch=='full' else ROOT/'gates/physical'/r.mode;ids=witness(root)['ids'];binding=r.source_binding()
     def n(v,key=None):
      if key=='source_binding' and v==binding:return {'verified':True}
      if isinstance(v,dict):return {n(k):n(z,k) for k,z in v.items()}
      if isinstance(v,list):return [n(z) for z in v]
      if isinstance(v,str):
       for k,z in ids.items():v=v.replace(k,z)
      return v
     return n(raw)
    E.require(risk_norm(full)==risk_norm(physical),'new risk mapping physically future-dependent')
    print('VERIFIED_PREFIX',mode,day,phase,flush=True)
    records.append(dict(mode=mode,day=day,phase=phase,OFF_original_complete_view_equal=True,on_full_physical_complete_view_equal=True,on_full_physical_risk_book_equal=True,hash=E.digest(c)))
 X.save(ROOT/'TWO_DAY_GATE.json',dict(passed=True,records=records,financial_events_invoked_by_comparison=0,formal_runs_not_restarted=True,cross_process_restart='Jul1 close checkpoint restored in a new process before Jul2',runtime_sha256=X.sha(ROOT/'month_r0.py'),entry_sha256=X.sha(ROOT/'run_july.py'),memo_gate_sha256=X.sha(ROOT/'MEMO_GATE.json'),normalization_exceptions=['input storage identity','separately verified source bindings','certificate IDs by exact mode/window/known_at','new R0 observer excluded only for OFF-vs-old; separately fully compared for on full/physical','memo counters/new-account provenance','derived hashes ONLY with exact raw-body hashes, pure-projection recomputation, and full normalized underlying-body comparison; necessary-stage exact reconstruction for D-empty gates']) )
 print('TWO_DAY_GATE_PASS',len(records),'comparisons',flush=True)
if __name__=='__main__':main()

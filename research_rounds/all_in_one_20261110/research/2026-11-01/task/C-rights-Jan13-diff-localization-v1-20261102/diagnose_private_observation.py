"""Disposable C10 diagnostic clone; no formal run_one/checkpoint/registry."""
from pathlib import Path
import hashlib,json,pickle,sys,time,traceback
O=Path(__file__).resolve().parent;A=O.parent/'C-rights-Jan13-action-v1-20261102'
sys.path.insert(0,str(A));import action_runtime as AR
import state_snapshot as S;import serializer_fix as T
R=AR.R;U=AR.U
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def first(a,b,path='$'):
 if type(a) is not type(b):return dict(path=path,before_type=type(a).__name__,after_type=type(b).__name__,before=a,after=b)
 if isinstance(a,dict):
  if a.keys()!=b.keys():return dict(path=path,before_keys=list(a),after_keys=list(b))
  for k in a:
   z=first(a[k],b[k],path+'/'+str(k))
   if z:return z
 elif isinstance(a,list):
  if len(a)!=len(b):return dict(path=path,before_length=len(a),after_length=len(b))
  for i,(x,y) in enumerate(zip(a,b)):
   z=first(x,y,path+'/'+str(i))
   if z:return z
 elif a!=b:return dict(path=path,before=a,after=b)
 return None
def view(r):
 a=r.account
 account={k:v for k,v in a.__dict__.items() if k not in {'owner','market','facts','last_cursor','as_of','audit_log','native_callbacks'}}
 facts={k:v for k,v in a.facts.__dict__.items() if k not in {'market','inputs'}}
 names=('authority','budget','binding_id','active','trusted','coverage','goal_intents','local_wait_sids','_busy_goals','close_stages','f1','f1seq','last_stock_state','cursor','windows','event_ids','action_ids','results','lifecycle','rank_bindings','active_intents','transitions')
 return account,facts,{k:r.__dict__[k] for k in names if k in r.__dict__}
def capture(r,label):
 print('CAPTURE',label,flush=True)
 x=dict(original_fields=S.snapshot(r),diagnostic_fields=T.snapshot(r),original_conservation=json.loads(R.conservation_bytes(r)),diagnostic_conservation=T.norm(view(r)),prefix=U.prefix_hashes(r),cursor=str(r.last_completed_event),bank_shares=r.account.quantity('002948.SZ'))
 save(label+'.json',x);return x
def delta(a,b):
 return dict(original_changed=[k for k in sorted(set(a['original_fields'])|set(b['original_fields'])) if a['original_fields'].get(k)!=b['original_fields'].get(k)],diagnostic_changed=[k for k in sorted(set(a['diagnostic_fields'])|set(b['diagnostic_fields'])) if a['diagnostic_fields'].get(k)!=b['diagnostic_fields'].get(k)],first_original_conservation_difference=first(a['original_conservation'],b['original_conservation']),first_diagnostic_conservation_difference=first(a['diagnostic_conservation'],b['diagnostic_conservation']),prefix_equal=a['prefix']==b['prefix'])
begun=time.monotonic();r=AR.activate('2022-C10',AR.authority('2022-C10')['sha256'])
before=capture(r,'PRIVATE_BEFORE_RIGHTS');backup=pickle.dumps(r,pickle.HIGHEST_PROTOCOL)
print('PRIVATE_OBSERVATION_ONLY no run_one/checkpoint/registry',flush=True)
try:
 result=r.corporate_actions('2022-01-13')
 observed=capture(r,'PRIVATE_AFTER_RIGHTS')
 save('PRIVATE_RIGHTS_DIFF.json',dict(disposable_only=True,result=result,diff=delta(before,observed)))
 print('VERIFY_ONLY_AFTER_PRIVATE_OBSERVATION',flush=True)
 for c in r.authority.certificates.values():r.verify_native(c)
 verified=capture(r,'PRIVATE_AFTER_CERTIFICATES')
 d=delta(observed,verified)
 save('PRIVATE_POST_CERT_DIFF.json',dict(disposable_only=True,diff=d))
 print('FIRST_POST_CERT_DIFF',json.dumps({k:v for k,v in d.items() if k not in {'first_original_conservation_difference','first_diagnostic_conservation_difference'}}),flush=True)
except Exception as e:
 save('PRIVATE_EXCEPTION.json',dict(error=repr(e),traceback=traceback.format_exc(),disposable_only=True));print('PRIVATE_EXCEPTION',repr(e),flush=True)
 pre_restore=capture(r,'PRIVATE_AFTER_EXCEPTION')
# Always exercise the exact failed outer restore assignment on this disposable clone.
pre_restore=capture(r,'PRIVATE_BEFORE_RESTORE')
prior=pickle.loads(backup);r.__dict__.clear();r.__dict__.update(prior.__dict__);r.account.owner=r
restored=capture(r,'PRIVATE_AFTER_RESTORE')
save('PRIVATE_RESTORE_DIFF.json',dict(disposable_only=True,baseline_to_restored=delta(before,restored),pre_restore_to_restored=delta(pre_restore,restored)))
save('PRIVATE_COMPLETION.json',dict(disposable_only=True,no_formal_ACTION=True,no_checkpoint_or_registry=True,no_C20=True,no_OPEN_CLOSE=True,original_sources_unmodified=True,seconds=time.monotonic()-begun))
print('PRIVATE_DIAGNOSTIC_DONE',round(time.monotonic()-begun,2),flush=True)

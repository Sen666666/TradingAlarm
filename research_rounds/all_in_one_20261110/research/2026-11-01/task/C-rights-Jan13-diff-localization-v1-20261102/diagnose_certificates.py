"""Read-only Jan12 clone; original seven certificate replays, NO ACTION."""
from pathlib import Path
import hashlib,json,pickle,sys,time
O=Path(__file__).resolve().parent
A=O.parent/'C-rights-Jan13-action-v1-20261102'
Udir=O.parent/'C-rights-Jan12-upgrade-v1-20261102'
sys.path.insert(0,str(A));import state_snapshot as S;import diagnostic_stable as T
sys.path.insert(0,str(Udir));import upgrade_runtime as U
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def roots(r):return {'runner':r,'account':r.account,'market':r.account.market,'facts':r.account.facts,'inputs':r.inputs,'old_inputs':r.rights_legacy_inputs,'native':r.account.market.native}
def value(r,k):
 a,b=k.split('.',1);return roots(r)[a].__dict__[b]
def typed(r,k,serializer):
 rr=roots(r);refs={id(v):n for n,v in rr.items()}
 return serializer.norm(value(r,k),refs)
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
begun=time.monotonic();reg=U.read(Udir/'UPGRADED_CHECKPOINTS.json');rec=next(x for x in reg if x['arm']=='2022-C10')
print('RESTORE_ONLY',flush=True);r=U.UpgradedRunner.restore(rec['checkpoint'])
save('RESTORE.json',dict(checkpoint=rec['checkpoint'],checkpoint_sha256=sha(rec['checkpoint']),cursor=str(r.last_completed_event),seven_old_certificates_verified=True,no_ACTION=True))
baseline=pickle.dumps(r,pickle.HIGHEST_PROTOCOL)
print('BEFORE_SNAPSHOTS',flush=True);before_old=S.snapshot(r);before_stable=T.snapshot(r);before_cons=U.NoSubscriptionRunnerMixin.__module__
import rights_wiring as R
cons0=R.conservation_bytes(r);pfx0=U.prefix_hashes(r)
save('BEFORE_FIELDS.json',dict(original=before_old,diagnostic=before_stable))
certs=[]
for c in r.authority.certificates.values():
 print('VERIFY_ONLY',str(c['known_at']),flush=True)
 q=r.verify_native(c)
 certs.append(dict(id=c['certificate_id'],known_at=str(c['known_at']),projection_matches=U.E.digest(q)==c['projection_hash'],financial_prefix_equal=U.prefix_hashes(r)==pfx0,original_conservation_equal=R.conservation_bytes(r)==cons0))
print('AFTER_SNAPSHOTS',flush=True);after_old=S.snapshot(r);after_stable=T.snapshot(r)
changed_old=[k for k in before_old if before_old[k]!=after_old.get(k)]
changed_stable=[k for k in before_stable if before_stable[k]!=after_stable.get(k)]
save('AFTER_FIELDS.json',dict(original=after_old,diagnostic=after_stable))
save('CERTIFICATE_REPLAY.json',dict(no_ACTION=True,certificates=certs,original_changed=changed_old,diagnostic_changed=changed_stable,prefix_equal=U.prefix_hashes(r)==pfx0,original_conservation_equal=R.conservation_bytes(r)==cons0,seconds=time.monotonic()-begun))
print('DIFF',json.dumps(dict(original=changed_old,diagnostic=changed_stable)),flush=True)
base=pickle.loads(baseline);base.account.owner=base
samples=[]
for k in sorted(set(changed_old)|set(changed_stable)):
 samples.append(dict(field=k,before_type=type(value(base,k)).__module__+'.'+type(value(base,k)).__qualname__,after_type=type(value(r,k)).__module__+'.'+type(value(r,k)).__qualname__,first_diagnostic_difference=first(typed(base,k,T),typed(r,k,T)),first_original_encoding_difference=first(typed(base,k,S),typed(r,k,S))))
save('FIRST_DIFFERENCES.json',dict(no_ACTION=True,differences=samples))
print('DONE',round(time.monotonic()-begun,2),flush=True)

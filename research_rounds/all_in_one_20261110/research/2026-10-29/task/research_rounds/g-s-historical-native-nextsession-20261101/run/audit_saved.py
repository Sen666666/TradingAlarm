"""Read-only import/restore and append-only evidence; zero account events."""
from driver import *
import pickle
spec=importlib.util.spec_from_file_location('existing_full_mutable_audit',OLD/'export-recovery/audit_state.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)

def same(a,b):return V.typed(a)==V.typed(b)
def import_check(k):
 old=H.HistoricalRunner.restore(old_checkpoint(k))
 new=NextSessionRunner.restore(HERE/k/'IMPORT.pkl')
 oa,na=old.account,new.account
 added_account=set(vars(na))-set(vars(oa))
 assert added_account=={'canonical_generations','old_canonical_binding','new_canonical_binding','canonical_old_end'}
 for field in vars(oa):
  if field not in ('market','facts'):assert same(getattr(oa,field),getattr(na,field)),('account import',k,field)
 added_runner=set(vars(new))-set(vars(old))
 assert added_runner=={'authorized_next_session','finance_import_authorized','horizon_import'}
 for field in vars(old):
  if field not in ('account','inputs'):assert same(getattr(old,field),getattr(new,field)),('runner import',k,field)
 for field in vars(oa.market):
  if field not in ('inputs','native'):assert same(getattr(oa.market,field),getattr(na.market,field)),('market import',k,field)
 for field in vars(oa.market.native):
  if field not in ('raw','actions','bundle'):assert same(getattr(oa.market.native,field),getattr(na.market.native,field)),('native market import',k,field)
 for field in vars(oa.market.native.bundle):
  if field!='manifest_path':assert same(getattr(oa.market.native.bundle,field),getattr(na.market.native.bundle,field)),('bundle import',k,field)
 for field in vars(oa.facts):
  if field not in ('inputs','market'):assert same(getattr(oa.facts,field),getattr(na.facts,field)),('facts import',k,field)
 # All historical raw rows and old company events are an exact prefix.
 for sid,frame in oa.market.native.raw.items():
  candidate=na.market.native.raw[sid]
  import pandas as pd
  pd.testing.assert_frame_equal(frame,candidate.loc[frame.index])
 for sid,actions in oa.market.native.actions.items():assert same(actions,na.market.native.actions[sid][:len(actions)])
 return dict(window=k,all_old_fields_exact=True,added_account_fields=sorted(added_account),added_runner_fields=sorted(added_runner),
   changed_immutable_inputs=['raw future append','actions future append','manifest_path','input provider','future canonical generation'],
   old_pending=len(oa.pending),old_exit_locks=sum(bool(e.remaining) for e in oa.policy.locks.values()),old_checkpoint_sha256=sha(old_checkpoint(k)))

def prefix_check(k):
 old=H.HistoricalRunner.restore(old_checkpoint(k));day=SPECS[k]['next_day']
 new=NextSessionRunner.restore(HERE/k/'close'/(day+'-CLOSE.pkl'))
 streams=[]
 for name in ('events','mapping','lifecycle','action_log'):
  before=getattr(old,name);after=getattr(new,name);assert same(before,after[:len(before)]),('runner stream',k,name);streams.append('runner.'+name)
 for name in ('fills','trades','audit_log','native_callbacks','rejections','decisions'):
  before=getattr(old.account,name);after=getattr(new.account,name);assert same(before,after[:len(before)]),('account stream',k,name);streams.append('account.'+name)
 for event in new.events:
  assert str(event['at'])[:10]<=day
  b=event['bridge']
  for n in ('independent_nav_difference','cash_asset_difference','layer_cash_difference'):assert D(b[n])==0
 new.account.assert_lot_bridge()
 return dict(window=k,immutable_old_streams=streams,events=len(new.events),all_three_accounting_bridges_zero=True,stable_lot_bridge=True,last_event=new.last_completed_event)

def main():
 out=HERE/'saved-state-audit';out.mkdir(exist_ok=False)
 imports=[import_check(k) for k in SPECS];prefix=[prefix_check(k) for k in SPECS];records=[]
 cps=[]
 for k,s in SPECS.items():
  cps+=[HERE/k/'IMPORT.pkl']
  cps+=sorted((HERE/k).glob(s['next_day']+'-*.pkl'))
  cps+=[HERE/k/'close'/(s['next_day']+'-CLOSE.pkl')]
 for n,p in enumerate(cps):
  side=LD.read(p.with_suffix('.provenance.json'));assert sha(p)==side['checkpoint_sha256']
  direct=pickle.loads(p.read_bytes());expected=V.h(V.view(direct));dest=out/(str(n)+'.json')
  subprocess.run([sys.executable,'-B',str(Path(__file__)),'worker',str(p),str(dest)],check=True)
  actual=LD.read(dest);assert actual['complete_mutable_state_sha256']==expected
  records.append(dict(checkpoint=str(p),checkpoint_sha256=sha(p),all_mutable_state_sha256=expected,guarded_crossprocess_restore_exact=True))
 original_guard()
 original_sources=LD.read(O/'inputs/SOURCE_BINDINGS.json')
 for p,h in original_sources.items():assert sha(p)==h,('original source changed',p)
 auth=LD.read(O/'NEXT_SESSION_AUTHORIZATION.json')
 for p,h in auth['sources'].items():assert sha(p)==h,('frozen execution source changed',p)
 save(out/'VERIFICATION.json',dict(passed=True,imports=imports,historical_streams=prefix,checkpoint_restores=records,
   original_source_files_reverified=len(original_sources),execution_sources_reverified=True,old_package_hash_unchanged=OLD_INDEX_SHA,
   financial_events_executed=0,unsupported_new_sessions=False))
 print(json.dumps(dict(passed=True,checkpoints=len(records),original_sources=len(original_sources),financial_events=0)),flush=True)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='worker':
  r=NextSessionRunner.restore(sys.argv[2]);save(sys.argv[3],dict(complete_mutable_state_sha256=V.h(V.view(r))))
 else:main()

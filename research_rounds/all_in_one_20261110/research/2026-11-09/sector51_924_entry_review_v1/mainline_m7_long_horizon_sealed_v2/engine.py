"""Scope-only frozen M7 horizon extension. No new facts or alpha changes."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;BASE=O.parent/'mainline_m7_downturn_cash_batch_v6'
sp=importlib.util.spec_from_file_location('long_frozen_v6',BASE/'engine.py');v6=importlib.util.module_from_spec(sp);sys.modules[sp.name]=v6;sp.loader.exec_module(v6)
read=v6.read;save=v6.save;sha=v6.sha;day=v6.day;pd=v6.pd;Blocked=v6.Blocked
BASE_SHA='b81f78fc04dec3709191258230c2e2fa7580f8658315c78e9b25bf3fea318c2e'
END='2026-06-30'
assert sha(BASE/'engine.py')==BASE_SHA

MANIFEST_SHA='0aa3853882941c99caca57465f9283d6b1e5f30481c16cf2cf776e751aff70fe'
def require_exact(actual,expected,label):
 actual=set(actual);expected=set(expected)
 assert set(actual)==set(expected),(label,'missing',sorted(set(expected)-set(actual)),'unexpected',sorted(set(actual)-set(expected)))
def validate_baseline():
 assert sha(O/'BASELINE_MANIFEST.json')==MANIFEST_SHA,'BASELINE_MANIFEST_DRIFT'
 m=read(O/'BASELINE_MANIFEST.json');baseline=BASE/'once_20241031'
 assert m['base_engine_sha256']==BASE_SHA
 require_exact(m['required_json_families'],m['comparison_families']+m['inventory_families'],'MANIFEST_FAMILY_PARTITION')
 assert len(m['comparison_families'])==33 and len(m['inventory_families'])==3 and len(m['required_json_families'])==36
 require_exact((p.name for p in baseline.iterdir()),m['files'],'BASELINE_FILES')
 require_exact((p.stem for p in baseline.glob('*.json')),m['required_json_families'],'BASELINE_JSON_FAMILIES')
 for n,h in m['files'].items():assert sha(baseline/n)==h,('BASELINE_FILE_DRIFT',n)
 original=read(baseline/'OUTPUT_HASHES.json')
 require_exact(original,set(m['files'])-{'OUTPUT_HASHES.json'},'ORIGINAL_OUTPUT_HASH_INVENTORY')
 for n,h in original.items():assert h==m['files'][n] and sha(baseline/n)==h,('ORIGINAL_OUTPUT_HASH_DRIFT',n)
 for n,h in m['completion_files'].items():assert sha(BASE/n)==h,('BASELINE_COMPLETION_DRIFT',n)
 status=read(BASE/'RUN_STATUS.json');audit=read(BASE/'POST_RUN_INDEPENDENT_AUDIT.json')
 assert status['completed_horizon'] and status['days']==37 and status['last']['day']=='2024-10-31' and not status['blockers']
 assert audit['verdict']=='PASS' and audit['error_count']==0
 return m

class Data(v6.Data):
 def __init__(self,end=END):
  assert end==END
  validate_baseline()
  super().__init__(end)
  assert day(self.cal[-1])==END
  for p in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_scope.py',O/'BASELINE_MANIFEST.json']:self.hashes[str(p)]=sha(p)

def check_prefix(path):
 m=validate_baseline();excluded=set(m['inventory_families']);baseline=BASE/'once_20241031';checks={}
 require_exact((p.stem for p in Path(path).glob('*.json')),m['required_json_families'],'CHECKPOINT_JSON_FAMILIES')
 for n in m['comparison_families']:
  p=baseline/(n+'.json')
  a=read(path/p.name);b=read(p);mode='exact_ordered'
  if a!=b and n=='AVAILABILITY_EVENTS':
   assert collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in b),('OCTOBER_PREFIX_MISMATCH',n)
   mode='full_record_multiset_unordered_diagnostic'
  else:assert a==b,('OCTOBER_PREFIX_MISMATCH',n)
  checks[n]=dict(comparison=mode,count=len(a) if hasattr(a,'__len__') else None)
 save(O/'PREFIX_QA_20241031.json',dict(result='PASS',through='2024-10-31',base_engine_sha256=BASE_SHA,families=checks,exclusions=sorted(excluded)))

class Engine(v6.Engine):
 def next_day(self,d):
  # Fail through the existing atomic boundary, not a raw terminal IndexError.
  if self.d.cal.get_loc(d)+1>=len(self.d.cal):raise Blocked(f'{day(d)} NEXT_SESSION_CALENDAR_UNAVAILABLE')
  return super().next_day(d)
 def export(self,path):
  v6.v5.v4.v3.m7.Engine.export(self,path)
  if Path(path).name=='checkpoint_20241031':check_prefix(path)

old_source=v6.source
old_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-14']"
new_dates="['2024-10-31']"
assert old_source.count(old_dates)==1
source=old_source.replace(old_dates,new_dates)
exec(compile(source,'LONG_SAME_ATOMIC_LOOP_ONLY_OCTOBER_PREFIX_EXPORT','exec'),globals())
def self_check():
 methods={n:getattr(Engine,n) is getattr(v6.Engine,n) for n in dir(v6.Engine) if not n.startswith('__') and callable(getattr(v6.Engine,n)) and n not in ('export','next_day')}
 validate_baseline()
 assert all(methods.values()) and source.replace(new_dates,old_dates)==old_source
 return dict(result='PASS',economic_method_identity=methods,only_new_boundary='missing_next_calendar_day_raises_Blocked_instead_of_IndexError',only_loop_change='single_full_20241031_prefix_checkpoint',new_fact_admissions=0,history_run=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],required=True);args=ap.parse_args();save(O/'STATIC_QA.json',self_check())
 if args.mode=='run':
  ap=read(O/'CONTRACT_APPROVAL.json');assert ap['approved'] and ap['engine_sha256']==sha(O/'engine.py') and ap['contract_sha256']==sha(O/'CONTRACT.md')
  qa=read(O/'SYNTHETIC_QA.json');assert qa['result']=='PASS' and qa['engine_sha256']==sha(O/'engine.py') and qa['contract_sha256']==sha(O/'CONTRACT.md')
  prior=read(BASE/'RUN_STATUS.json');assert prior['completed_horizon'] and prior['days']==37 and prior['last']['day']=='2024-10-31' and not prior['blockers']
  assert not (O/'RUN_STARTED.json').exists()
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,base_engine_sha256=BASE_SHA,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md'),end=END,new_fact_admissions=0))
  save(O/'RUN_STARTED.json',dict(end=END,time=str(pd.Timestamp.now(tz='UTC'))))
  e=run_loop(Engine(data));e.export(O/'once_20260630')
  save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,prefix_1031_pass=(O/'PREFIX_QA_20241031.json').exists(),planned_end=END,completed_horizon=bool(e.ledger and e.ledger[-1]['day']==END and not e.blockers)))
  print(json.dumps(read(O/'RUN_STATUS.json')))

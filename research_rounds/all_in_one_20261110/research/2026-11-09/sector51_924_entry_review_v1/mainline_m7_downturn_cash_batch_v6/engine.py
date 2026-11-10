"""Frozen M7/v5 extension: exact manifest-bound ordinary cash batch only."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;BASE=ROOT/'mainline_m7_downturn_cash_batch_v5'
sp=importlib.util.spec_from_file_location('v6_frozen_v5',BASE/'engine.py');v5=importlib.util.module_from_spec(sp);sys.modules[sp.name]=v5;sp.loader.exec_module(v5)
read=v5.read;save=v5.save;sha=v5.sha;day=v5.day;pd=v5.pd;Blocked=v5.Blocked;D=v5.D;dec=v5.dec
BASE_SHA='6860981fd7dd9cf7228c594b72fc3777c5c3df46a2fb7087878d0219b168f6be'
assert sha(BASE/'engine.py')==BASE_SHA
MANIFEST_PATH=O/'REVIEWED_BATCH_MANIFEST.json'
MANIFEST_SHA='235d1b1dcc83fd7eebf8298ae3edbac08cef0ed7bdb73d79cd5564d46a0851e9'

# Reuse approved generic loader code without modification.
admit_cash=v5.admit_cash
manifest_records=v5.manifest_records

class Data(v5.v4.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  assert sha(MANIFEST_PATH)==MANIFEST_SHA
  self.hashes[str(MANIFEST_PATH)]=MANIFEST_SHA
  def checked(p,h):
   assert sha(Path(p))==h,('CASH_FACT_DRIFT',p);self.hashes[str(p)]=h
  assert sha(v5.MANIFEST_PATH)==v5.MANIFEST_SHA
  manifest=read(MANIFEST_PATH);prior_manifest=read(v5.MANIFEST_PATH)
  assert all(a in manifest['adapters'] for a in prior_manifest['adapters'])
  self.hashes[str(v5.MANIFEST_PATH)]=v5.MANIFEST_SHA
  self.hashes[str(BASE/'engine.py')]=BASE_SHA
  events,allowed=manifest_records(manifest,checked)
  for ev in events:admit_cash(self,ev,checked,allowed)
  for p in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_batch.py']:self.hashes[str(p)]=sha(p)

EXCLUDED_INVENTORY={'SOURCE_HASHES','OUTPUT_HASHES','EVENT_ADMISSION'}
FUTURE_BLOCKER_DIAGNOSTICS={'BLOCKERS','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY'}
def check_prefix(path,date):
 baseline={'2024-10-08':v5.v4.v3.BASE/'once_20241008','2024-10-09':v5.v4.BASE/'once_20241031','2024-10-10':v5.BASE/'once_20241031','2024-10-14':BASE/'once_20241031'}[date]
 excluded=EXCLUDED_INVENTORY|(FUTURE_BLOCKER_DIAGNOSTICS if date in ('2024-10-09','2024-10-10','2024-10-14') else set())
 names=sorted(p.stem for p in baseline.glob('*.json') if p.stem not in excluded);checks={}
 for n in names:
  a=read(path/(n+'.json'));b=read(baseline/(n+'.json'));mode='exact_ordered'
  if a!=b and n=='AVAILABILITY_EVENTS':
   assert collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in b),('PREFIX_MISMATCH',date,n)
   mode='full_record_multiset_unordered_diagnostic'
  else:assert a==b,('PREFIX_MISMATCH',date,n)
  checks[n]=dict(comparison=mode,count=len(a) if hasattr(a,'__len__') else None)
 save(O/('PREFIX_QA_'+date.replace('-','')+'.json'),dict(result='PASS',through=date,baseline=str(baseline),families=checks,exclusions=sorted(excluded)))

class Engine(v5.Engine):
 def export(self,path):
  # Bypass prior wrappers' export routing only; keep all frozen economic exports.
  v5.v4.v3.m7.Engine.export(self,path)
  for date in ['2024-10-08','2024-10-09','2024-10-10','2024-10-14']:
   if Path(path).name=='checkpoint_'+date.replace('-',''):check_prefix(path,date)

old_source=v5.source
old_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-10-09','2024-10-10']"
new_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-14']"
assert old_source.count(old_dates)==1
source=old_source.replace(old_dates,new_dates)
exec(compile(source,'CASH_V6_SAME_ATOMIC_LOOP_ADDED_1014_CHECKPOINT','exec'),globals())
def self_check():
 methods={n:getattr(Engine,n) is getattr(v5.Engine,n) for n in dir(v5.Engine) if not n.startswith('__') and callable(getattr(v5.Engine,n)) and n!='export'}
 assert all(methods.values()) and source.replace(new_dates,old_dates)==old_source
 return dict(result='PASS',method_identity=methods,only_loop_change='add_20241014_checkpoint',history_run=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],required=True);args=ap.parse_args();save(O/'STATIC_QA.json',self_check())
 if args.mode=='run':
  approval=read(O/'CONTRACT_APPROVAL.json');assert approval['approved'] and approval['engine_sha256']==sha(O/'engine.py') and approval['contract_sha256']==sha(O/'CONTRACT.md')
  qa=read(O/'SYNTHETIC_QA.json');assert qa['result']=='PASS' and qa['engine_sha256']==sha(O/'engine.py') and qa['contract_sha256']==sha(O/'CONTRACT.md')
  facts_qa=read(O/'FACTS_LOADER_QA.json');assert facts_qa['result']=='PASS' and facts_qa['manifest_sha256']==MANIFEST_SHA
  assert not (O/'RUN_STARTED.json').exists()
  prior=read(BASE/'RUN_STATUS.json');assert prior['days']==24 and prior['last']['day']=='2024-10-14'
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,base_engine_sha256=BASE_SHA,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')))
  save(O/'RUN_STARTED.json',dict(end='2024-10-31',time=str(pd.Timestamp.now(tz='UTC'))))
  e=run_loop(Engine(data));e.export(O/'once_20241031')
  save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,prefix_1008_pass=(O/'PREFIX_QA_20241008.json').exists(),prefix_1009_pass=(O/'PREFIX_QA_20241009.json').exists(),prefix_1010_pass=(O/'PREFIX_QA_20241010.json').exists(),prefix_1014_pass=(O/'PREFIX_QA_20241014.json').exists(),planned_end='2024-10-31',completed_horizon=bool(e.ledger and e.ledger[-1]['day']=='2024-10-31' and not e.blockers)))
  print(json.dumps(read(O/'RUN_STATUS.json')))

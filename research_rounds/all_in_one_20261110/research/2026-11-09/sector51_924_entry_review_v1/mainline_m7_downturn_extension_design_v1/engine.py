"""Unchanged frozen M7 endpoint extension. No suspension accounting installed."""
from pathlib import Path
import sys, importlib.util, inspect, json, copy, argparse, collections
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
BASE=O.parent/'mainline_candidate_v7_demand_capped'
sp=importlib.util.spec_from_file_location('extension_frozen_m7',BASE/'engine.py')
m7=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m7;sp.loader.exec_module(m7)
read=m7.read;save=m7.save;sha=m7.sha;day=m7.day;pd=m7.pd;Blocked=m7.Blocked
FROZEN_ENGINE='804d56f8b5a8e4b26d5a89caac5874c037911a38c339db9c6dfd5e99882aab6a'
assert sha(BASE/'engine.py')==FROZEN_ENGINE
# Admissions/source inventories describe the requested full horizon, not prefix state.
EXCLUDED={'SOURCE_HASHES','OUTPUT_HASHES','EVENT_ADMISSION'}
FAMILIES=sorted(p.stem for p in (BASE/'once_20241008').glob('*.json') if p.stem not in EXCLUDED)

def check_prefix(path):
 checks={}
 for n in FAMILIES:
  a=read(path/(n+'.json'));b=read(BASE/'once_20241008'/(n+'.json'))
  mode='exact_ordered'
  if a!=b and n=='AVAILABILITY_EVENTS':
   # Existing M2 emits only this diagnostic through unordered set iteration.
   assert collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in b),('PREFIX_MISMATCH',n)
   mode='full_record_multiset_unordered_diagnostic'
  else:assert a==b,('PREFIX_MISMATCH',n)
  checks[n]={'comparison':mode,'count':len(a) if hasattr(a,'__len__') else None}
 save(O/'M7_PREFIX_QA.json',dict(result='PASS',through='2024-10-08',m7_engine_sha256=FROZEN_ENGINE,families=checks,exclusions=sorted(EXCLUDED)))

class Engine(m7.Engine):
 def export(self,path):
  super().export(path)
  if self.ledger and self.ledger[-1]['day']=='2024-10-08':check_prefix(path)

# Run loop is byte-identical source, rebinding only output path and export subclass.
source=inspect.getsource(m7.m4.run_loop)
exec(compile(source,'UNCHANGED_M7_ATOMIC_LOOP','exec'),globals())

def self_check():
 methods={n:getattr(Engine,n) is getattr(m7.Engine,n) for n in dir(m7.Engine) if not n.startswith('__') and callable(getattr(m7.Engine,n)) and n!='export'}
 assert all(methods.values())
 assert len(FAMILIES)>=30 and 'REFERENCE_AT_END' in FAMILIES
 assert run_loop.__code__.co_code==m7.run_loop.__code__.co_code and run_loop.__code__.co_consts==m7.run_loop.__code__.co_consts
 return dict(result='PASS',economic_method_identity=methods,atomic_loop_source_identical=True,prefix_families=FAMILIES,suspension_changes_installed=False,history_run=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],required=True);args=ap.parse_args()
 save(O/'STATIC_QA.json',self_check())
 if args.mode=='run':
  approval=read(O/'CONTRACT_APPROVAL.json')
  assert approval['approved'] and approval['engine_sha256']==sha(O/'engine.py') and approval['contract_sha256']==sha(O/'CONTRACT.md')
  assert not (O/'RUN_STARTED.json').exists()
  assert read(BASE/'RUN_STATUS.json')['days']==20 and not read(BASE/'RUN_STATUS.json')['blockers']
  data=m7.Data(end='2024-10-31')
  save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,m7_engine_sha256=FROZEN_ENGINE,wrapper_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')))
  save(O/'RUN_STARTED.json',dict(end='2024-10-31',time=str(pd.Timestamp.now(tz='UTC'))))
  e=run_loop(Engine(data));e.export(O/'once_20241031')
  save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,prefix_pass=(O/'M7_PREFIX_QA.json').exists(),planned_end='2024-10-31',completed_horizon=bool(e.ledger and e.ledger[-1]['day']=='2024-10-31' and not e.blockers)))
  print(json.dumps(read(O/'RUN_STATUS.json')))

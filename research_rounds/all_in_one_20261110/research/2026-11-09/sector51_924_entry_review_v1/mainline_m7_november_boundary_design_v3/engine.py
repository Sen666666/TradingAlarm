"""Review-only boundary adapter. No historical launch entrypoint."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,inspect
from decimal import Decimal,ROUND_HALF_UP
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;BASE=O.parent/'mainline_m7_long_horizon_sealed_v2'
sp=importlib.util.spec_from_file_location('boundary_base',BASE/'engine.py');b=importlib.util.module_from_spec(sp);sys.modules[sp.name]=b;sp.loader.exec_module(b)
read=b.read;save=b.save;sha=b.sha;pd=b.pd;day=b.day;Blocked=b.Blocked;D=b.v6.D;dec=b.v6.dec
LOCKS={'BASELINE_MANIFEST.json': 'ea1977f0839e3d25042248368b53b61ad04250b7581baa3ba1368e687e9c9f63', 'EVIDENCE_MANIFEST.json': '84c2c10f3a2aa36fbbbdc072c59b9c67a3da1a8907926a447bc0fb9052872524', 'CASH_EVENT.json': '7d8c26763132392dc73f88c0fceaea7a10a7ad867c332068482b34931e4a3685'}
SID='002602.SZ';HALT='2024-11-07';RESUME='2024-11-08'
def validate_inputs():
 for n,h in LOCKS.items():assert sha(O/n)==h,('ADAPTER_DRIFT',n)
 m=read(O/'BASELINE_MANIFEST.json');assert sha(BASE/'engine.py')==m['engine_sha256'] and sha(BASE/'RUN_STATUS.json')==m['status_sha256']
 f=BASE/'once_20260630';b.require_exact((p.name for p in f.iterdir()),m['files'],'BASELINE_FILE_SET')
 for n,h in m['files'].items():assert sha(f/n)==h,('BASELINE_DRIFT',n)
 original=read(f/'OUTPUT_HASHES.json');assert original=={k:v for k,v in m['files'].items() if k!='OUTPUT_HASHES.json'}
 for p,h in read(O/'EVIDENCE_MANIFEST.json').items():assert sha(Path(p))==h,('EVIDENCE_DRIFT',p)
 return m
# Identical previously reviewed loader body; scope narrows to one November event.
loader_source=inspect.getsource(b.v6.admit_cash)
old="assert '2024-10-11'<=ev['ex_date']<='2024-10-31' and ev['event_type']=='PURE_CASH'"
new="assert s=='300760.SZ' and ev['ex_date']=='2024-11-07' and ev['event_type']=='PURE_CASH'"
assert loader_source.count(old)==1
v4=b.v6.v5.v4
exec(compile(loader_source.replace(old,new),'EXACT_300760_LOADER_SCOPE_ONLY','exec'),globals())
class Data(b.Data):
 def __init__(self,end=b.END):
  validate_inputs();super().__init__(end)
  ev=read(O/'CASH_EVENT.json')
  def checked(p,h):
   assert sha(Path(p))==h;self.hashes[str(p)]=h
  admit_cash(self,ev,checked,{(ev['sid'],ev['ex_date'],ev['economic_event_id_candidate'])})
  for n in ['engine.py','CONTRACT.md',*LOCKS]:self.hashes[str(O/n)]=sha(O/n)
def check_prefix(path):
 m=validate_inputs();b.require_exact((p.stem for p in Path(path).glob('*.json')),m['required_json_families'],'NOV6_PREFIX_FAMILY_SET');checks={}
 for n in m['comparison_families']:
  a=read(Path(path)/(n+'.json'));z=read(BASE/'once_20260630'/(n+'.json'));same=a==z
  if n=='AVAILABILITY_EVENTS':same=collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in z)
  assert same,('NOV6_PREFIX_MISMATCH',n);checks[n]='PASS'
 save(O/'PREFIX_QA_20241106.json',dict(result='PASS',families=checks,excluded_inventory=m['excluded_inventory'],sealed_future_failure_diagnostics=m['failure_diagnostics']))
class Engine(b.Engine):
 def __init__(self,data):super().__init__(data);self.paused_new_requests={}
 def economic_preflight(self,d,pending):
  # Bounded tier A: no resumed ST execution authorized by this prototype.
  if day(d)>=RESUME:raise Blocked(f'{day(d)} {SID} ST_EXECUTION_TIER_B_NOT_ADMITTED')
  if day(d)==HALT:
   matches=[r for r in pending if r['sid']==SID]
   if matches:
    assert len(matches)==1 and matches[0]['kind']=='SEED' and matches[0]['signal_day']=='2024-11-06'
    assert SID not in self.active or self.quantity(self.active[SID])==0
    assert SID not in self.live_tickets() and SID not in self.paused_new_requests
    self.paused_new_requests[SID]=dict(status='PAUSED_OFFICIAL_SUSPENSION',halt_date=HALT,request=copy.deepcopy(matches[0]))
    pending[:]=[r for r in pending if r['sid']!=SID]
  return super().economic_preflight(d,pending)
 def close(self,d,prev):
  requests=super().close(d,prev)
  if SID in self.paused_new_requests:
   # A missing halt-day observation is never a fresh signal/replacement.
   assert not any(r['sid']==SID for r in requests),'HALT_DAY_REQUEST_CONFLICT'
   requests.append(copy.deepcopy(self.paused_new_requests[SID]['request']))
  return requests
 def export(self,path):
  b.v6.v5.v4.v3.m7.Engine.export(self,path)
  if Path(path).name=='checkpoint_20241106':
   assert not self.paused_new_requests;check_prefix(path)
  if self.paused_new_requests:
   save(Path(path)/'PAUSED_NEW_REQUESTS.json',self.paused_new_requests)
   save(Path(path)/'OUTPUT_HASHES.json',{p.name:sha(p) for p in Path(path).iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
source=b.source.replace("['2024-10-31']","['2024-11-06']").replace("keys=['cash'","keys=['paused_new_requests','cash'")
assert source.replace("['2024-11-06']","['2024-10-31']").replace("keys=['paused_new_requests','cash'","keys=['cash'")==b.source
exec(compile(source,'BOUNDARY_LOOP_EXTRA_STATE_AND_NOV6_GATE','exec'),globals())
def st_oneprice_gate(side,ohlc,reference,known_st=True):
 """Tier B pure proposal, NOT connected to fills/alpha. Daily-bar ex-post gate."""
 if not known_st:return 'UNKNOWN_STOP'
 vals=[D(str(v)) for v in ohlc];ref=D(str(reference))
 if len(vals)!=4 or any(not v.is_finite() or v<=0 for v in vals) or not ref.is_finite() or ref<=0:return 'UNKNOWN_STOP'
 lo=(ref*D('.95')).quantize(D('.01'),rounding=ROUND_HALF_UP);hi=(ref*D('1.05')).quantize(D('.01'),rounding=ROUND_HALF_UP)
 if any(v<lo or v>hi for v in vals):return 'REFERENCE_OR_LIMIT_MISMATCH_STOP'
 if side not in ['buy','sell']:return 'UNKNOWN_STOP'
 if len(set(vals))==1 and ((side=='buy' and vals[0]==hi) or (side=='sell' and vals[0]==lo)):return 'DIRECTIONAL_LIMIT_NO_FILL'
 if len(set(vals))==1:return 'OPPOSITE_DIRECTION_ONEPRICE_CONDITIONAL_ONLY_NOT_PROVEN_FILL'
 return 'CONDITIONAL_OPEN_ONLY_NOT_PROVEN_FILL'
def self_check():
 validate_inputs();names=[n for n in dir(b.Engine) if not n.startswith('__') and callable(getattr(b.Engine,n)) and n not in ['economic_preflight','close','export']]
 assert all(getattr(Engine,n) is getattr(b.Engine,n) for n in names)
 return dict(result='PASS',history_run=False,unchanged_methods=names,changed_methods=['__init__','economic_preflight','close','export'],tier_A='reviewable bounded halt preservation; not launched',tier_B='pure gate proposal only; not integrated/admitted',historical_entrypoint=False)
if __name__=='__main__':raise SystemExit('REVIEW_ONLY: no historical launcher; parent must approve complete execution scope first')

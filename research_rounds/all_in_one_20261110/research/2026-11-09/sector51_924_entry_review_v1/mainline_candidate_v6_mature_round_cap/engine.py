"""M6 single-factor mature ADD round-cap ablation. Research only."""
from pathlib import Path
import sys,importlib.util,inspect,json,copy
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;BASE=ROOT/'mainline_candidate_v5_expansion_competition'
sp=importlib.util.spec_from_file_location('m6_frozen_m5',BASE/'engine.py');m5=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m5;sp.loader.exec_module(m5)
m4=m5.m4;m3=m5.m3;D=m5.D;ZERO=m5.ZERO;INITIAL=m5.INITIAL;SLIP=m5.SLIP;pd=m5.pd;dec=m5.dec;day=m5.day;finite=m5.finite;sha=m5.sha;save=m5.save;read=m5.read;Blocked=m5.Blocked
assert sha(BASE/'engine.py')=='54f3d42846c97e63bf79b886564e186df182c5b9a1d0b69c1a8797dec7de9fa9'
def replace_once(s,a,b):
 assert s.count(a)==1,('HOOK_NOT_UNIQUE',a);return s.replace(a,b)
original_close=inspect.getsource(m3.Engine.close);original_noncash=inspect.getsource(m3.Engine.noncash)
close_source=replace_once(original_close,' def close','def close')
close_source=replace_once(close_source,"budget=min(D('.02')*a['nav0'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,'raw_close')))","budget=D('.02')*a['nav0']")
noncash_source=replace_once(original_noncash,' def noncash','def noncash')
noncash_source=replace_once(noncash_source,"budget=min(r['budget'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,field))) if a else ZERO","budget=r['budget'] if a else ZERO")
ns=dict(m3.__dict__);exec(compile(close_source,'M6_mature_CLOSE_budget_only','exec'),ns);m3.Engine.close=ns['close'];exec(compile(noncash_source,'M6_mature_OPEN_budget_only','exec'),ns);m3.Engine.noncash=ns['noncash']
class Data(m5.Data):
 def __init__(self,end='2024-10-08'):
  super().__init__(end)
  for p in [O/'engine.py',O/'CONTRACT.md']:self.hashes[str(p)]=sha(p)
class Engine(m5.Engine):pass
# Same M5/M4 atomic state and log inventory, redirected output only.
source=inspect.getsource(m4.run_loop);exec(compile(source,'M6_atomic_loop','exec'),globals())
if __name__=='__main__':
 ap=read(O/'CONTRACT_APPROVAL.json');assert ap['approved'] and ap['engine_sha256']==sha(O/'engine.py') and ap['contract_sha256']==sha(O/'CONTRACT.md');assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert not (O/'RUN_STARTED.json').exists()
 save(O/'GENERATED_RUNTIME_METHODS.json',dict(close=close_source,noncash=noncash_source));data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')));save(O/'RUN_STARTED.json',dict(end='2024-10-08',time=str(pd.Timestamp.now(tz='UTC'))));e=run_loop(Engine(data));e.export(O/'once_20241008');save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))

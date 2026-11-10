"""Read saved own checkpoints only: all mutable state vs raw pickle reference."""
from pathlib import Path
import sys,json,pickle,subprocess,hashlib,collections,math
from datetime import datetime,date
from decimal import Decimal
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from historical_binding import *

def typed(v):
 if v is None or isinstance(v,(str,bool,int)):return [type(v).__name__,v]
 if isinstance(v,Decimal):return ['Decimal',str(v)]
 if isinstance(v,(datetime,date)):return [type(v).__name__,v.isoformat()]
 if isinstance(v,float):return ['float',repr(v)]
 if isinstance(v,dict):
  rows=[[typed(k),typed(x)] for k,x in v.items()];rows.sort(key=lambda r:json.dumps(r[0],sort_keys=True));return [type(v).__name__,rows]
 if isinstance(v,(list,tuple)):return [type(v).__name__,[typed(x) for x in v]]
 if isinstance(v,(set,frozenset)):return [type(v).__name__,sorted([typed(x) for x in v],key=lambda x:json.dumps(x,sort_keys=True))]
 if hasattr(v,'__dict__'):return [type(v).__module__+'.'+type(v).__qualname__,typed(vars(v))]
 raise TypeError('unsupported mutable state type '+type(v).__name__)
def view(r):
 a=r.account;mutable_account={k:v for k,v in vars(a).items() if k not in ('market','facts')}
 mutable_runner={k:v for k,v in vars(r).items() if k not in ('account','inputs')}
 market={k:getattr(a.market,k) for k in ('prices','known','factors','sectors','stars')}
 native={k:getattr(a.market.native,k) for k in ('notices','_notice_keys','fx','_fx_times','_fx_cache')}
 facts={k:v for k,v in vars(a.facts).items() if k not in ('inputs','market')}
 return dict(account=typed(mutable_account),runner=typed(mutable_runner),market=typed(market),native_market_runtime=typed(native),facts=typed(facts),input_binding=r.inputs.m)
def h(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 root=HERE/'state-audit';root.mkdir(exist_ok=False);records=[];checkpoints=[]
 for window,first,second in [('2022','2022-01-04','2022-01-05'),('2025_26','2025-07-01','2025-07-02')]:
  for d,sub in [(first,'primary'),(second,'primary-resume')]:
   for p in sorted((HERE.parent/'runs'/window/sub).glob(d+'-*.pkl')):
    if p.name in ('BEFORE_EVENT.pkl','FAILED_WORKING_STATE.pkl'):continue
    checkpoints.append(p)
 for n,p in enumerate(checkpoints):
  side=LD.read(p.with_suffix('.provenance.json'));assert sha(p)==side['checkpoint_sha256']
  direct=pickle.loads(p.read_bytes());v=view(direct);expected=h(v)
  out=root/(str(n)+'.json');subprocess.run([sys.executable,'-B',str(Path(__file__)),'worker',str(p),str(out)],check=True)
  actual=LD.read(out);assert actual['state_sha256']==expected
  records.append(dict(checkpoint=str(p),checkpoint_sha256=sha(p),all_mutable_state_exact=True,state_sha256=expected,account_fields=sorted(k for k in vars(direct.account) if k not in ('market','facts')),cursor=str(direct.last_completed_event)))
 IO.write_json(root/'VERIFICATION.json',dict(passed=True,checkpoints=len(records),records=records,financial_events_executed=0,method='raw owned pickle complete mutable view versus guarded cross-process restore; input files bound separately'))
 print(json.dumps(dict(passed=True,checkpoints=len(records),financial_events=0)),flush=True)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='worker':
  r=HistoricalRunner.restore(sys.argv[2]);IO.write_json(sys.argv[3],dict(state_sha256=h(view(r))))
 else:main()

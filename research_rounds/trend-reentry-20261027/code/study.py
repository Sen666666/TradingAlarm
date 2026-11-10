from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027'
sys.path.insert(0,str(PRIOR/'code'));import experiment as P
E=P.E;R=P.R;A=P.A;pd=P.pd;np=P.np
from dataclasses import replace
from decimal import Decimal as D
VERSION='ACT'
original_override=E.risk_policy.override

def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class Facts(E.Facts):
 def __init__(self,b,m,cutoff=None):
  super().__init__(b,m,cutoff);self.local={}
  if VERSION!='ACT':
   for line in b.lines:
    sid=line.security_id;z=pd.read_parquet(O/VERSION/'signals'/f'{sid}.parquet');self.local[sid]=z.loc[:cutoff] if cutoff else z
 def event(self,sid,at):
  day=pd.Timestamp(at.date());z=self.local.get(sid);r=self.row(sid,at)
  if z is None or day not in z.index or r is None or bool(r.i_buy):return None
  q=z.loc[day];return q if bool(q.event) else None
 def floor(self,sid,at,mode):
  q=self.event(sid,at) if mode=='I' else None
  return D(str(q.floor)) if q is not None else super().floor(sid,at,mode)
 def packet(self,at,mode):
  clock,stocks,sectors=super().packet(at,mode)
  if VERSION=='ACT' or mode!='I':return clock,stocks,sectors
  buyable=self.market.market_buyable(at)
  return clock,tuple(replace(s,buy_allowed=buyable[s.security_id]) if self.event(s.security_id,at) is not None else s for s in stocks),sectors

class Account(E.Account):
 def __init__(self,*args,**kw):super().__init__(*args,**kw);self.local_positions={}
 def reserve_budget(self,**kw):
  ok,reason=super().reserve_budget(**kw)
  if ok and VERSION!='ACT':
   sid=kw['quote'].security_id;at=kw['clock'].decision_at;q=self.facts.event(sid,at)
   if q is not None:
    z=dict(setup_kind=str(q.kind),anchor=str(q.anchor),signal_at=at,local_floor=D(str(q.floor)),entry_e0_floor=D(str(self.facts.row(sid,at).e0_floor)),handed=False)
    self.intents[reason]['local_entry']=z;self.log('local_entry_contract',at,sid=sid,order_id=reason,**z)
  return ok,reason
 def fill_buy(self,sid,w):
  o=self.buys.get(sid);z=self.intents[o.order_id].get('local_entry') if o else None;empty=not self.quantity(sid)
  fill=super().fill_buy(sid,w)
  if fill and z is not None and empty:
   self.local_positions[sid]=dict(z,stop=z['local_floor'],filled_at=w.at);self.log('local_position_started',w.at,sid=sid,order_id=o.order_id,**self.local_positions[sid])
  return fill

def override(a,stocks,clock,mode,Fact):
 at=clock.decision_at
 if VERSION!='ACT':
  changed=[]
  for s in stocks:
   sid=s.security_id;z=a.local_positions.get(sid)
   if z and not a.quantity(sid):del a.local_positions[sid];z=None
   if z:
    r=a.facts.row(sid,at)
    if bool(r.e0_target) and np.isfinite(r.e0_floor):z['stop']=max(z['stop'],D(str(r.e0_floor)))
    stop= D(str(r.close))<=z['stop']
    if not stop and not z['handed'] and bool(r.e0_target) and D(str(r.e0_floor))>z['entry_e0_floor'] and D(str(r.e0_floor))>=z['local_floor']:
     z['handed']=True;a.log('local_handoff',at,sid=sid,stop=z['stop'],e0_floor=D(str(r.e0_floor)),entry_e0_floor=z['entry_e0_floor'],local_floor=z['local_floor'])
    if stop:
     s=replace(s,trend_up=Fact(False,at,at,source_id='TRE1_local_close_stop'),buy_allowed=Fact(False,at,at,source_id='TRE1_no_same_close_retry'))
     if sid not in a.exits:a.log('local_stop_trigger',at,sid=sid,close=D(str(r.close)),stop=z['stop'],handed=z['handed'])
   changed.append(s)
  stocks=tuple(changed)
 return original_override(a,stocks,clock,mode,Fact)

def run(version,stage):
 global VERSION
 VERSION=version;assert version in ['ACT','PB','BOX','BOTH'];original=P.setup('RS');R.Facts=Facts;R.Account=Account;R.Runner=E.Runner;E.risk_policy.override=override
 root=O/version;root.mkdir(exist_ok=True)
 if not (root/'execution-rules-v2.json').exists():(root/'execution-rules-v2.json').symlink_to((O/'execution-rules-v2.json').resolve())
 if stage=='economic':assert read(O/'admission.json')['passed'] and read(O/'graph-review.json')['reviewed'] and (O/'freeze.json').exists()
 end='2024-06-28' if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27'
 out=root/('technical/short-v2' if stage=='short' else 'technical/prefix' if stage=='prefix' else 'accounts-v2')
 R.run(out,modes=['I'],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic');R.context=original

def freeze():
 assert read(O/'admission.json')['passed'];fs=[O/'protocol.json',O/'raw-review.json',O/'graph-review.json',O/'input.json',O/'signal-checks.json',O/'execution-rules-v2.json',PRIOR/'freeze.json',*sorted((O/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py'))]
 signals={str(p):sha(p) for v in ['PB','BOX','BOTH'] for p in (O/v/'signals').glob('*.parquet')}
 save(O/'freeze.json',{'before_economic':True,'sources':{str(p):sha(p) for p in fs},'signals':signals})
if __name__=='__main__':freeze() if sys.argv[1]=='freeze' else run(sys.argv[2],sys.argv[1])

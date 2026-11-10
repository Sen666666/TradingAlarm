from pathlib import Path
import sys,json,hashlib,math,inspect
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027'
sys.path.insert(0,str(PRIOR/'code'));import experiment as P
E=P.E;R=P.R;A=P.A;pd=P.pd;np=P.np
from dataclasses import replace
from decimal import Decimal as D
STARTS={'S0':'2023-12-29','S1':'2024-06-28','S2':'2024-12-31'};MODES=['ACT','SF'];FAST={};SESS=[];STRICT={}
FREF=ROOT/'research_rounds/intent-support-20261027';SREF=ROOT/'research_rounds/strict-entry-capacity-20261027'
RANK='RS'
SFREF=ROOT/'research_rounds/strict-entry-fast-support-20261027'
old_override=E.risk_policy.override

def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def control_override(a,stocks,clock,mode,Fact):
 if a.mode in ['S','SF']:
  day=pd.Timestamp(clock.decision_at.date())
  stocks=tuple(replace(s,buy_allowed=Fact(False,clock.decision_at,clock.decision_at,source_id='strict_e0_entry_only')) if day not in STRICT[s.security_id].index or not bool(STRICT[s.security_id].loc[day,'strict_target']) else s for s in stocks)
 if a.mode in ['ACT','S']:return old_override(a,stocks,clock,mode,Fact)
 at=clock.decision_at;day=pd.Timestamp(at.date());j=SESS.index(day);L=3 if a.mode=='W3' else 10 if a.mode in ['W10','W10F'] else 0;fast=a.mode in ['F','SF']
 if not hasattr(a,'watch'):a.watch={};a.previous_q={};a.fast_floor={}
 sector={s.sector_id:s for s in a.facts.packet(at,'I')[2]};market=a.market.market_buyable(at);result=[]
 for s in stocks:
  sid=s.security_id;r=a.facts.row(sid,at);held=bool(a.quantity(sid));today=r is not None and day in a.facts.f[sid].index;up=bool(r.i_target) if r is not None else False
  q=E.admission.eligibility(s,sector,clock,'S0').q is True;prev=a.previous_q.get(sid,False);a.previous_q[sid]=q
  if not held:a.fast_floor.pop(sid,None)
  stopped=False
  if fast and held and sid not in a.exits:
   f=FAST[sid];z=f.loc[day] if day in f.index else None;prior=a.fast_floor.get(sid);price=float(r.close) if r is not None and 'close' in r else None
   # Price is in the causal adjusted signal coordinate, not raw execution units.
   if today and z is not None:
    price=float(z.close)
    if prior is not None and price<=prior:
     s=replace(s,trend_up=Fact(False,at,at,source_id='fast_support_exit'));stopped=True;a.log('fast_support_exit',at,sid=sid,close=price,floor=prior);a.counts['fast_support_exits']+=1
    else:
     old=float(r.i_floor) if math.isfinite(float(r.i_floor)) else None;v=max(x for x in [prior,old] if x is not None) if prior is not None or old is not None else None
     buys=[x.at.date().isoformat() for x in a.fills if x.security_id==sid and x.side=='buy'];sales=[x.at.date().isoformat() for x in a.fills if x.security_id==sid and x.side=='sell'];last=max(sales) if sales else '';entry=min(x for x in buys if x>last)
     if z.event==1 and z.pivot_date>=entry:v=max(v,float(z.pivot)) if v is not None else float(z.pivot)
     if v is not None:
      if prior is None or v>prior:a.log('fast_support_raise',at,sid=sid,previous=prior,floor=v,event=float(z.event),pivot_date=None if pd.isna(z.pivot_date) else z.pivot_date,entry=entry)
      a.fast_floor[sid]=v
  if L:
   w=a.watch.get(sid);valid=today and up and bool(r.e0_ready) and math.isfinite(float(r.i_floor)) and float(r.close)>float(r.i_floor)
   if w:
    why='filled' if held else 'risk_pause' if not a.risk_state['on'] else 'structure_or_source' if not valid or str(r.segment_id)!=w['segment'] else 'expired' if j-w['j']>=L else None
    if why:a.log('intent_end',at,sid=sid,origin=w['day'],reason=why,age=j-w['j']);del a.watch[sid];w=None
   if not held and a.risk_state['on'] and valid and q and not prev and sid not in a.exits:
    if w is None:
     w={'j':j,'day':str(day.date()),'segment':str(r.segment_id)};a.watch[sid]=w;a.log('intent_create',at,sid=sid,**w)
   if stopped:a.watch.pop(sid,None);w=None
   if w and not held and valid and bool(r.g_ready and r.g_grade>=2) and sid not in a.exits:
    s=replace(s,buy_allowed=market[sid])
  result.append(s)
 return old_override(a,tuple(result),clock,mode,Fact)


def setup(cutoff=None):
 global FAST,SESS,STRICT
 old=P.setup(RANK);E.risk_policy.override=override;R.Account=Account;R.Runner=E.Runner;R.Facts=E.Facts
 FAST={p.stem:pd.read_parquet(p).loc[:cutoff] if cutoff else pd.read_parquet(p) for p in (FREF/'signals').glob('*.parquet')}
 STRICT={p.stem:pd.read_parquet(p).loc[:cutoff] if cutoff else pd.read_parquet(p) for p in (SREF/'signals').glob('*.parquet')}
 SESS=sorted({pd.Timestamp(x[:10]) for x in read(PRIOR/'execution-rules-v2.json')['decision_cutoffs']}|{pd.Timestamp(d) for d in ['2023-12-29','2026-10-23','2026-10-26','2026-10-27']})
 return old

def run(cohort,stage,rank):
 global RANK
 RANK=rank
 root=O/rank/cohort;root.mkdir(parents=True,exist_ok=True);link=root/'execution-rules-v2.json'
 if not link.exists():link.symlink_to((PRIOR/'execution-rules-v2.json').resolve())
 end=(pd.Timestamp(STARTS[cohort])+pd.Timedelta(days=75)).date().isoformat() if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27';old=setup(end if stage=='prefix' else None)
 if stage=='economic':assert read(O/'admission.json')['passed'] and (O/'freeze.json').exists()
 R.run(root/({'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'}[stage]),modes=['ACT','SF','SW3F','SW10F'] if rank=='RS' else ['SF','SW3F','SW10F'],stresses=['base','delay1','cost2'] if cohort=='S0' else ['base','delay1'],start=STARTS[cohort],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic');R.context=old

from waiting import advance

def strict(sid,day):return day in STRICT[sid].index and bool(STRICT[sid].loc[day,'strict_target'])
def override(a,stocks,clock,mode,Fact):
 if a.mode in ['ACT','SF']:return control_override(a,stocks,clock,mode,Fact)
 at=clock.decision_at;day=pd.Timestamp(at.date());j=SESS.index(day);L=3 if a.mode=='SW3F' else 10
 if not hasattr(a,'watch'):a.watch={};a.previous_q={};a.fast_floor={};a.fast_anchor={}
 sector={s.sector_id:s for s in a.facts.packet(at,'I')[2]};market=a.market.market_buyable(at);result=[]
 for s in stocks:
  sid=s.security_id;r=a.facts.row(sid,at);today=r is not None and day in a.facts.f[sid].index;held=bool(a.quantity(sid));ok=strict(sid,day)
  if not ok:s=replace(s,buy_allowed=Fact(False,at,at,source_id='strict_e0_entry_only'))
  q=E.admission.eligibility(s,sector,clock,'S0').q is True;prev=a.previous_q.get(sid,False);a.previous_q[sid]=q
  z=FAST[sid].loc[day] if day in FAST[sid].index else None;stopped=False
  if not held:a.fast_floor.pop(sid,None);a.fast_anchor.pop(sid,None)
  if held and sid not in a.exits and today and z is not None:
   prior=a.fast_floor.get(sid);price=float(z.close)
   if prior is not None and price<=prior:
    s=replace(s,trend_up=Fact(False,at,at,source_id='fast_support_exit'));stopped=True;a.log('fast_support_exit',at,sid=sid,close=price,floor=prior);a.counts['fast_support_exits']+=1
   else:
    old=float(r.i_floor) if math.isfinite(float(r.i_floor)) else None;v=max(x for x in [prior,old] if x is not None) if prior is not None or old is not None else None
    buys=[x.at.date().isoformat() for x in a.fills if x.security_id==sid and x.side=='buy'];sales=[x.at.date().isoformat() for x in a.fills if x.security_id==sid and x.side=='sell'];last=max(sales) if sales else '';entry=min(x for x in buys if x>last);anchor=a.fast_anchor.get(sid,entry)
    if z.event==1 and z.pivot_date>=anchor:v=max(v,float(z.pivot)) if v is not None else float(z.pivot)
    if v is not None:
     if prior is None or v>prior:a.log('fast_support_raise',at,sid=sid,previous=prior,floor=v,event=float(z.event),pivot_date=None if pd.isna(z.pivot_date) else z.pivot_date,entry=entry,anchor=anchor)
     a.fast_floor[sid]=v
  w=a.watch.get(sid);valid=today and ok and bool(r.i_target and r.e0_ready) and math.isfinite(float(r.i_floor)) and float(r.close)>float(r.i_floor) and z is not None
  cancelled=False
  if w:
   previous=w
   if held:w=None;reason='filled'
   else:w,reason=advance(w,day=str(day.date()),j=j,L=L,close=float(r.close) if r is not None else float('nan'),old_floor=float(r.i_floor) if r is not None else float('nan'),event=float(z.event) if z is not None else 0,pivot=float(z.pivot) if z is not None else float('nan'),pivot_date=str(z.pivot_date) if z is not None else '',valid=valid,segment=str(r.segment_id) if r is not None else '',on=a.risk_state['on'])
   if reason:
    a.log('intent_end',at,sid=sid,origin=previous['day'],reason=reason,age=j-previous['j'],floor=previous['floor']);a.watch.pop(sid,None);cancelled=reason in ['waiting_floor_breach','updated_floor_breach','structure_or_source','risk_pause']
   else:
    a.watch[sid]=w
    if w['floor']>previous['floor']:a.log('waiting_support_raise',at,sid=sid,origin=w['day'],previous=previous['floor'],floor=w['floor'],close=float(r.close),event=float(z.event),pivot=float(z.pivot),pivot_date=str(z.pivot_date))
  if not held and not cancelled and a.risk_state['on'] and valid and q and not prev and sid not in a.exits and w is None:
   w={'j':j,'day':str(day.date()),'segment':str(r.segment_id),'floor':float(r.i_floor)};a.watch[sid]=w;a.log('intent_create',at,sid=sid,**w)
  if stopped:a.watch.pop(sid,None);w=None
  if cancelled:s=replace(s,buy_allowed=Fact(False,at,at,source_id='waiting_support_cancel'))
  elif w and not held and valid and bool(r.g_ready and r.g_grade>=2) and sid not in a.exits:s=replace(s,buy_allowed=market[sid])
  result.append(s)
 return old_override(a,tuple(result),clock,mode,Fact)

class FloorView:
 def __init__(self,base,sid,floor):self.base,self.sid,self.v=base,sid,floor
 def __getattr__(self,name):return getattr(self.base,name)
 def floor(self,sid,at,mode):
  v=self.base.floor(sid,at,mode)
  return max(v,self.v) if sid==self.sid and v is not None else self.v if sid==self.sid else v
class Account(E.Account):
 def reserve_budget(self,**kw):
  sid=kw['quote'].security_id;at=kw['clock'].decision_at;w=getattr(self,'watch',{}).get(sid);base=self.facts
  if w:self.facts=FloorView(base,sid,D(str(w['floor'])))
  try:ok,oid=super().reserve_budget(**kw)
  finally:self.facts=base
  if ok:
   r=base.row(sid,at)
   if w:self.intents[oid]['watch_origin']=w['day'];self.intents[oid]['watch_floor']=w['floor']
   self.log('intent_entry_class',at,order_id=oid,sid=sid,original=bool(r.i_buy),origin=w['day'] if w else None,window=3 if self.mode=='SW3F' else 10 if self.mode=='SW10F' else 0,waiting_floor=w['floor'] if w else None)
  return ok,oid
 def fill_buy(self,sid,w):
  order=self.buys.get(sid);z=self.intents.get(order.order_id) if order else None;fill=super().fill_buy(sid,w)
  if fill and z and 'watch_origin' in z:
   if not hasattr(self,'fast_anchor'):self.fast_anchor={}
   self.fast_floor[sid]=max(self.fast_floor.get(sid,float('-inf')),float(z['floor_signal']));self.fast_anchor[sid]=z['watch_origin'];self.log('waiting_support_inherited',w.at,sid=sid,origin=z['watch_origin'],floor=self.fast_floor[sid],order_id=order.order_id)
  return fill
if __name__=='__main__':run(sys.argv[2],sys.argv[1],sys.argv[3])

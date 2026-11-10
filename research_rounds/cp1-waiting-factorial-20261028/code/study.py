from fw_common import *
from dataclasses import replace
from decimal import Decimal as D
import math

def setup(sector,root,cutoff=None):
 if sector=='TECH':
  sys.path.insert(0,str(COMBO/'code'));Q=load('integration_original_combo',COMBO/'code/study.py');Q.setup(cutoff);R,E=Q.R,Q.E;R.HERE=root
 else:
  sys.path.insert(0,str(LOCAL/'code'));prior=load('integration_original_drug',LOCAL/'code/study.py');prior.setup(root,cutoff);Q,R,E=prior.Q,prior.R,prior.E
 if cutoff:E.risk_policy.RECOVERY=E.risk_policy.RECOVERY.loc[:cutoff].copy()
 Parent=Q.Account;old_risk=Q.old_override
 cp={sid:pd.read_parquet(cpdir(sector)/f'{sid}.parquet').loc[:cutoff] for sid in pool(sector).symbol}
 class Account(Parent):
  def __init__(self,*args,**kw):
   super().__init__(*args,**kw);self.cp_states={};self.cp_seq=0
  def reserve_budget(self,**kw):
   mode=self.mode
   if mode in WINDOWS:self.mode='SW3F' if WINDOWS[mode]==3 else 'SW10F'
   try:return super().reserve_budget(**kw)
   finally:self.mode=mode
  def fill_buy(self,sid,w):
   order=self.buys.get(sid);z=self.intents.get(order.order_id) if order else None
   filled=super().fill_buy(sid,w)
   if filled and self.mode in CPS and sid not in self.cp_states:
    self.cp_seq+=1;state=dict(P=float(z['floor_signal']),entry_at=w.at.isoformat(),segment=str(self.facts.row(sid,w.at).segment_id),cycle_id=f'{sid}:{self.cp_seq}',order_id=order.order_id)
    self.cp_states[sid]=state;self.log('cp_start',w.at,sid=sid,**state)
   return filled
  def fill_exit(self,sid,w):
   filled=super().fill_exit(sid,w)
   if sid in self.cp_states and not self.quantity(sid):self.log('cp_end',w.at,sid=sid,**self.cp_states.pop(sid))
   return filled

 def waiting(a,stocks,clock,Fact):
  at=clock.decision_at;day=pd.Timestamp(at.date());j=Q.SESS.index(day);L=WINDOWS[a.mode];use_s=a.mode in STRICT_CP
  if not hasattr(a,'watch'):a.watch={};a.previous_q={};a.fast_floor={};a.fast_anchor={}
  sector_map={s.sector_id:s for s in a.facts.packet(at,'I')[2]};market=a.market.market_buyable(at);result=[]
  for s in stocks:
   sid=s.security_id;r=a.facts.row(sid,at);today=r is not None and day in a.facts.f[sid].index;held=bool(a.quantity(sid));ok=Q.strict(sid,day) if use_s else True
   if not ok:s=replace(s,buy_allowed=Fact(False,at,at,source_id='strict_e0_entry_only'))
   q=E.admission.eligibility(s,sector_map,clock,'S0').q is True;prev=a.previous_q.get(sid,False);a.previous_q[sid]=q
   z=Q.FAST[sid].loc[day] if day in Q.FAST[sid].index else None
   if not held:a.fast_floor.pop(sid,None);a.fast_anchor.pop(sid,None)
   w=a.watch.get(sid);valid=today and ok and bool(r.i_target and r.e0_ready) and math.isfinite(float(r.i_floor)) and float(r.close)>float(r.i_floor) and z is not None;cancelled=False
   if w:
    previous=w
    if held:w=None;reason='filled'
    else:w,reason=Q.advance(w,day=str(day.date()),j=j,L=L,close=float(r.close) if r is not None else float('nan'),old_floor=float(r.i_floor) if r is not None else float('nan'),event=float(z.event) if z is not None else 0,pivot=float(z.pivot) if z is not None else float('nan'),pivot_date=str(z.pivot_date) if z is not None else '',valid=valid,segment=str(r.segment_id) if r is not None else '',on=a.risk_state['on'])
    if reason:
     a.log('intent_end',at,sid=sid,origin=previous['day'],reason=reason,age=j-previous['j'],floor=previous['floor']);a.watch.pop(sid,None);cancelled=reason in ['waiting_floor_breach','updated_floor_breach','structure_or_source','risk_pause']
    else:
     a.watch[sid]=w
     if w['floor']>previous['floor']:a.log('waiting_support_raise',at,sid=sid,origin=w['day'],previous=previous['floor'],floor=w['floor'],close=float(r.close),event=float(z.event),pivot=float(z.pivot),pivot_date=str(z.pivot_date))
   if not held and not cancelled and a.risk_state['on'] and valid and q and not prev and sid not in a.exits and w is None:
    w={'j':j,'day':str(day.date()),'segment':str(r.segment_id),'floor':float(r.i_floor)};a.watch[sid]=w;a.log('intent_create',at,sid=sid,**w)
   if cancelled:s=replace(s,buy_allowed=Fact(False,at,at,source_id='waiting_support_cancel'))
   elif w and not held and valid and bool(r.g_ready and r.g_grade>=2) and sid not in a.exits:s=replace(s,buy_allowed=market[sid])
   result.append(s)
  return tuple(result)

 def override(a,stocks,clock,mode,Fact):
  if a.mode in ['ACT','S','SF']:return Q.control_override(a,stocks,clock,mode,Fact)
  if a.mode in ['SW3F','SW10F']:return Q.override(a,stocks,clock,mode,Fact)
  at=clock.decision_at;day=pd.Timestamp(at.date())
  if a.mode in WINDOWS:stocks=waiting(a,stocks,clock,Fact)
  elif a.mode=='SCP':
   strict=Q.STRICT
   stocks=tuple(replace(s,buy_allowed=Fact(False,at,at,source_id='strict_e0_entry_only')) if day not in strict[s.security_id].index or not bool(strict[s.security_id].loc[day,'strict_target']) else s for s in stocks)
  result=[]
  for s in stocks:
   sid=s.security_id
   if not a.quantity(sid):result.append(s);continue
   assert sid in a.cp_states,(sid,at,'missing CP state')
   state=a.cp_states[sid];r=a.facts.row(sid,at);today=day in a.facts.f[sid].index
   assert str(r.segment_id)==state['segment'],(sid,at,'source change while holding')
   old=float(state['P']);reason='ACT' if not a.risk_state['on'] else 'E0' if not bool(r.i_target) else 'locked' if sid in a.exits else 'CP' if today and float(r.close)<=old else None
   candidate=None;receipt=False;new=old
   if not reason and today:
    z=cp[sid].loc[day];receipt=bool(z.receipt)
    if receipt:candidate=float(z.candidate)
    if math.isfinite(float(r.i_floor)):new=max(new,float(r.i_floor))
    if candidate is not None:new=max(new,candidate)
   a.log('cp_checkpoint',at,sid=sid,cycle_id=state['cycle_id'],observed=today,close=float(r.close),E=float(r.i_floor),old_P=old,new_P=new,receipt=receipt,candidate=candidate,reason=reason,raised_by_cp=candidate is not None and candidate>max(old,float(r.i_floor)))
   state['P']=new
   if reason:s=replace(s,trend_up=Fact(False,at,at,source_id='cp1_'+reason))
   result.append(s)
  return old_risk(a,tuple(result),clock,mode,Fact)
 R.Account=Account;E.risk_policy.override=override
 return R

def main(sector,stage):
 root=O/sector;root.mkdir(parents=True,exist_ok=True);link=root/'execution-rules-v2.json'
 if not link.exists():link.symlink_to(PRIOR/'execution-rules-v2.json')
 if stage=='economic':
  assert read(O/'admission.json')['passed']
  for path,h in read(O/'freeze.json')['sha256'].items():assert sha(path)==h,path
 end='2024-03-13' if stage=='short' else '2026-06-30' if stage=='prefix' else END
 R=setup(sector,root,end if stage=='prefix' else None)
 R.run(root/({'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'}[stage]),modes=run_modes(sector,stage),stresses=['base','cost2','delay1'],start='2023-12-29',end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic')
if __name__=='__main__':main(*sys.argv[1:])

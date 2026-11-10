"""Account-bound local protection; unchanged cash/quantity/fee/settlement core."""
from ler_common import *
from dataclasses import replace
sys.path[:0]=[str(SEC/'code'),str(OLD/'code'),str(IX/'code'),str(ROOT/'research_rounds/universe-expansion-diagnosis-20261025/code')]
import run_accounts_v2 as old_context
import fixed_scope_v1 as fs
import sector_stock_admission as adm
import current_fixed_pool as pool
from sector_account import SectorAccount,dec
from current_pool_bridge import checked_ref

DATA={};FACTS={};FACTORS={};SCOPE=None;ACCOUNTS={};CACHE={};STATE={}

def configure(scope,data,facts,factors,accounts):
 global SCOPE,DATA,FACTS,FACTORS,ACCOUNTS
 SCOPE=scope;DATA=data;FACTS=facts;FACTORS=factors;ACCOUNTS=accounts;CACHE.clear();STATE.clear()

class LocalAccount(SectorAccount):
 def install(self,mode):self.local_mode=mode;self.bound={}
 def fill_buy(self,sid,window):
  order=self.buys.get(sid)
  if order is None:return None
  d=pd.Timestamp(order.created_at.date());f=DATA[sid];r=FACTS[sid]
  assert d in r.index and bool(r.loc[d,'receipt']),(sid,d,'order lacks a local receipt')
  local=float(r.loc[d,'local_floor']);known=max(float(f.loc[d,'e0_floor']),local)
  entry_day=pd.Timestamp(window.at.date());factor=float(FACTORS[sid].loc[entry_day])
  if not order.filled_shares and window.at>=order.earliest_at and window.buy_allowed is True and float(window.raw_open)*factor<=known:
   self._time(window.at);self.audit_log.append(dict(kind='local_open_cancel',at=window.at,sid=sid,order_id=order.order_id,decision_at=order.created_at,known_floor_signal=known,raw_open=window.raw_open,factor=factor));self.cancel_buy(sid);return None
  receipt=super().fill_buy(sid,window)
  if receipt is not None and sid not in self.bound:
   b=dict(local_floor=local,known_floor_at_decision=known,receipt_day=str(d.date()),segment=str(f.loc[d,'segment_id']),order_id=order.order_id,first_fill_at=window.at,handoff=False)
   self.bound[sid]=b
   self.audit_log.append(dict(kind='local_bound',at=window.at,sid=sid,**b,actual_entry_price=window.execution_price,shares=receipt.shares))
  return receipt

def market_views(clock,entry_mode,lines,historical,sectors):
 group,policy,stress=entry_mode.split('_');aid=entry_mode+'__S1_'+stress;account=ACCOUNTS[aid];key=(clock.decision_at,aid)
 if key in CACHE:return CACHE[key]
 if len(CACHE)>30:CACHE.clear()
 day=pd.Timestamp(clock.session_date);ss={x.sector_id:x for x in sectors};hh={x.security_id:x for x in historical};stocks={};elig={};states=[]
 for sid in tuple(account.bound):
  if not account.quantity(sid):del account.bound[sid]
 for line in lines:
  sid=line.security_id;h=hh[sid];f=DATA[sid];value=h.trend_up.read(clock);fresh=day in FACTS[sid].index and bool(FACTS[sid].loc[day,'receipt']);reason='';protection=None;handoff=False
  if value is not None:
   value=bool(f.loc[day,'e0_target']) if day in f.index else None
   if value is not None and account.quantity(sid):
    assert sid in account.bound,(aid,sid,'holding lacks executed local binding')
    b=account.bound[sid]
    if policy=='LER':
     if str(f.loc[day,'segment_id'])!=b['segment']:value=False;reason='source_segment_reset'
     else:
      eo_floor=float(f.loc[day,'e0_floor']);protection=max(eo_floor,b['local_floor']) if math.isfinite(eo_floor) else b['local_floor'];handoff=bool(math.isfinite(eo_floor) and eo_floor>=b['local_floor'])
      if not value:reason='E0_structure'
      elif float(f.loc[day,'close'])<=protection:value=False;reason='local_failure'
      if handoff and not b['handoff']:
       b['handoff']=True;account.audit_log.append(dict(kind='local_E0_handoff',at=clock.decision_at,sid=sid,local_floor=b['local_floor'],E0_floor=float(f.loc[day,'e0_floor']),receipt_day=b['receipt_day']))
    elif not value:reason='E0_structure'
   h=replace(h,trend_up=adm.Fact(value,clock.decision_at,clock.decision_at,observed_at=h.trend_up.observed_at,source_id='LER01:actual_participation_not_market_grade'))
  s=pool.build_security(line,h,pool_evidence)
  allowed=s.buy_allowed.read(clock,for_execution=True);allowed=None if allowed is None else bool(allowed and fresh)
  s=replace(s,buy_allowed=adm.Fact(allowed,clock.decision_at,clock.decision_at,source_id='LER01:new_local_OHLCV_receipt'))
  stocks[sid]=s;elig[sid]=adm.eligibility(s,ss,clock,'S1')
  if account.quantity(sid):
   states.append(dict(symbol=sid,trend_up=value,receipt=fresh,protection=protection,handoff=handoff,reason=reason))
   if reason:account.audit_log.append(dict(kind='local_exit_signal',at=clock.decision_at,sid=sid,reason=reason,protection=protection,receipt_day=account.bound[sid]['receipt_day']))
 CACHE[key]=(stocks,ss,elig);STATE[key]=states
 return CACHE[key]

pool_evidence=None
def decide(*,evidence,lines,historical,clock,variant,sectors,entry_mode,**kw):
 global pool_evidence
 group,policy,stress=entry_mode.split('_')
 if policy=='I':return fs.decide(evidence=evidence,lines=lines,historical=historical,clock=clock,variant=variant,sectors=sectors,entry_mode=group+'_I',**kw)
 pool_evidence=evidence;stocks,ss,elig=market_views(clock,entry_mode,lines,historical,sectors);ids=SCOPE['groups'][group];gid=GROUPS[group][1]
 fs.CURRENT={sid:replace(elig[sid],sector_id=gid) for sid in ids};selected=[replace(stocks[sid],sector_id=replace(stocks[sid].sector_id,value=gid)) for sid in ids]
 if group=='DRUG':
  template=next(iter(ss.values()));allocation=replace(template,sector_id=gid,trend_up=adm.Fact(True,clock.decision_at,clock.decision_at,source_id='external_fixed_scope_identity_only'),rank=adm.Rank(0.,clock.decision_at,clock.decision_at))
 else:allocation=ss[gid]
 decision=fs._decide(clock=clock,variant='S1',securities=tuple(selected),sectors=(allocation,),**kw)
 return pool.CurrentPoolDecision(evidence,decision)

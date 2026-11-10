"""Entry-only EMA gate; native market state and financial kernel stay unchanged."""
from gate_common import *
from dataclasses import replace
sys.path[:0]=[str(SEC/'code'),str(OLD/'code'),str(IX/'code'),str(ROOT/'research_rounds/universe-expansion-diagnosis-20261025/code')]
import run_accounts_v2 as native
import fixed_scope_v1 as fs
import sector_stock_admission as adm
import current_fixed_pool as pool
DATA={};GATES={};SCOPE=None;CACHE={};EXCLUSIONS={}

def configure(scope,data,gates):
 global SCOPE,DATA,GATES
 SCOPE=scope;DATA=data;GATES=gates;CACHE.clear();EXCLUSIONS.clear()

def decide(*,evidence,lines,historical,clock,variant,sectors,entry_mode,**kw):
 group,policy,stress=entry_mode.split('_')
 if policy=='I':return fs.decide(evidence=evidence,lines=lines,historical=historical,clock=clock,variant=variant,sectors=sectors,entry_mode=group+'_I',**kw)
 key=(clock.decision_at,policy)
 if len(CACHE)>12:CACHE.clear()
 if key not in CACHE:
  day=pd.Timestamp(clock.session_date);hh={h.security_id:h for h in historical};ss={s.sector_id:s for s in sectors};stocks={};elig={};blocked=[]
  for line in lines:
   sid=line.security_id;h=hh[sid];f=DATA[sid];loc=f.index.searchsorted(day,side='right')-1
   field='i_target' if policy=='IG' else 'e0_target'
   original=h.trend_up.read(clock)
   if original is not None:
    h=replace(h,trend_up=replace(h.trend_up,value=bool(f[field].iloc[loc])))
   s=pool.build_security(line,h,evidence);allowed=s.buy_allowed.read(clock,for_execution=True)
   if policy=='IG':allowed=None if allowed is None else bool(allowed and day in f.index and f.loc[day,'IX'])
   if allowed is not None:s=replace(s,buy_allowed=adm.Fact(allowed,clock.decision_at,clock.decision_at,source_id='original_'+('I_event' if policy=='IG' else 'E0_availability')))
   original_q=adm.eligibility(s,ss,clock,'S1')
   if policy.endswith('G'):
    aligned=day in GATES[sid].index and bool(GATES[sid].loc[day,'gate'])
    if original_q.q is True and not aligned:blocked.append(sid)
    value=None if allowed is None else bool(allowed and aligned)
    s=replace(s,buy_allowed=adm.Fact(value,clock.decision_at,clock.decision_at,source_id='original_entry_AND_EMA9_21_50_rising'))
   stocks[sid]=s;elig[sid]=adm.eligibility(s,ss,clock,'S1')
  CACHE[key]=(stocks,ss,elig);EXCLUSIONS[key]=blocked
 stocks,ss,elig=CACHE[key];ids=SCOPE['groups'][group];gid=GROUPS[group][1]
 fs.CURRENT={s:replace(elig[s],sector_id=gid) for s in ids};selected=[replace(stocks[s],sector_id=replace(stocks[s].sector_id,value=gid)) for s in ids]
 if group=='DRUG':
  template=next(iter(ss.values()));allocation=replace(template,sector_id=gid,trend_up=adm.Fact(True,clock.decision_at,clock.decision_at,source_id='external_fixed_scope_identity_only'),rank=adm.Rank(0.,clock.decision_at,clock.decision_at))
 else:allocation=ss[gid]
 d=fs._decide(clock=clock,variant='S1',securities=tuple(selected),sectors=(allocation,),**kw)
 return pool.CurrentPoolDecision(evidence,d)

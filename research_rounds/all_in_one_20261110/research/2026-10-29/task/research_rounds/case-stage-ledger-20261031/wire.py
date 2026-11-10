"""Thin existing-ledger harness. Budget-controller integration is separate."""
from pathlib import Path
import sys,importlib.util,collections,time,json,gzip,copy
from dataclasses import replace
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
M=load('case_stage_original_full_domain',W/'mainline-I-quarter-2025Q3-20261031/adapter.py');C=M.C;BP=M.BP;LR=C.LR;D=C.D;Z=D(0)
START='2025-07-01';END='2026-03-31';CACHE=W/'case-stock-cp1-warmup-20261031';M.O=W/'mainline-absolute-Q4-20261031';M.END=END
def save(n,x):M.save(O/(n+'.json'),x)
def context(end=END):
 manifest=M.read(CACHE/'MANIFEST.json');ids=[r['sid'] for r in manifest if r['status']=='complete'];assert len(ids)==77
 b,m,f=M.context(end,ids=ids)
 for sid in ids:
  q=pd.read_parquet(CACHE/'full-facts'/f'{sid}.parquet').loc[:end];f.f[sid]=q;b.series[sid].states=q[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 assert len(m.lines)==77 and len({x.sector_id for x in b.lines})==5
 return b,m,f
class CaseAccount(C.Account):
 def __init__(self,name,market,facts,enabled=False):
  super().__init__(name,market,facts,False,1,0);self.joint_enabled=enabled
  # These are external accounting maps, never replacements for original layers.
  self.pool_by_layer={};self.attempt_by_layer={};self.mobile_CP1_consumed=set();self.budget_events=[]
 def reserve_quantity(self,i,q,p,schedule,at):
  # No receipt may be consumed by a failed sizing/route preview. The actual
  # budget adapter must reserve once immediately before this real ledger call.
  if self.joint_enabled:raise RuntimeError('reviewed v2 budget source/interface not connected; no unbudgeted economic fill')
  return super().reserve_quantity(i,q,p,schedule,at)
class Harness(M.Pilot):
 def __init__(self,shared=None,wrapped=False):
  super().__init__(policies=('L0',),shared=shared or context());self.gate_enabled=False
  if wrapped:self.accounts['L0']=CaseAccount('L0',self.market,self.facts,False)
  self.cp={sid:pd.read_parquet(CACHE/'CP1'/f'{sid}.parquet').loc[:END] for sid in self.market.lines};self.pv={sid:pd.Series(dtype=float,index=pd.DatetimeIndex([])) for sid in self.market.lines}
 def planning(self,at):
  # Exact original L0 planning; no P, Top3, half-list or attention restriction.
  C.Pilot.planning(self,at)
def observable(r):
 a=r.accounts['L0'];return dict(daily=r.daily,trades=a.trades,audit=a.audit_log,decisions=a.decisions,layers=a.layers,counts=dict(a.counts),available=a.available,positions=a.positions,buys=a.buys,exits=a.exits,fees=a.fees_cny,settlements=a.settlements,dividends=a.dividends,ACT=a.risk_state)
def canon(x):return json.loads(json.dumps(M.N.encoded(x),ensure_ascii=False,default=C.encoded))
def physical(shared,end):
 b,m,f=shared;date=pd.Timestamp(end);b2=copy.copy(b);b2.series={k:copy.copy(v) for k,v in b.series.items()}
 for v in b2.series.values():v.states=v.states.loc[:end]
 d,col,score=b._h1_cache;mask=d<=date;b2._h1_cache=(d[mask],col,score[mask]);m2=copy.copy(m);m2.bundle=b2;m2.raw={k:v.loc[:end] for k,v in m.raw.items()};m2.arr={}
 for sid,a in m.arr.items():
  n=len(m2.raw[sid]);m2.arr[sid]={k:(v[v<n] if k in ['good','positive'] else v[:n] if isinstance(v,np.ndarray) else v) for k,v in a.items()}
 m2.actions={sid:[e for e in es if e['effective_date']<=end] for sid,es in m.actions.items()};m2.cache_at=None;m2.mark_verified=set();m2.window_verified=set();m2.notices=[];m2._notice_keys={};f2=M.E.Facts.__new__(M.E.Facts);f2.b=b2;f2.market=m2;f2.f={k:v.loc[:end] for k,v in f.f.items()};f2.cache={};f2.day=None;f2.structure_lookup={};return b2,m2,f2
def stock_opportunities(r,at):
 clock,stocks,sectors=r.facts.packet(at,'I');ss={s.sector_id:s for s in sectors};buyable=r.market.market_buyable(at);out=[];day=pd.Timestamp(at.date())
 for s in stocks:
  sid=s.security_id;q=BP.A.eligibility(s,ss,clock,'S0');continuing=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0');cp=r.cp[sid];newcp=bool(day in cp.index and cp.loc[day,'receipt']);out.append(dict(sid=sid,core_Q=q.q,core_reasons=q.reasons,mobile_Q=continuing.q,mobile_reasons=continuing.reasons,stock_CP1=newcp,mobile_candidate=bool(newcp and continuing.q is True),rank=s.rank.read(clock) if s.rank else None,sector=s.sector_id.read(clock)))
 return clock,out
def main():
 t=time.monotonic();shared=context();prepared=time.monotonic();end='2025-07-07';gold=Harness(shared,False);gold.run(end=end,begin=START);gold_s=canon(observable(gold));native_done=time.monotonic();off=Harness(shared,True);off.run(end=end,begin=START);assert gold_s==canon(observable(off));prefix=Harness(physical(shared,end),True);prefix.run(end=end,begin=START);assert gold_s==canon(observable(prefix));_,op=stock_opportunities(off,M.N.iso(end+'T15:10:00+08:00'));save('OPPORTUNITY_INTERFACE_SAMPLE',op)
 save('OFF_PREFIX_GATE',dict(passed=True,scope=[START,end],same77_inputs=True,no_new_economic_policy=True,off_full_event_exact=True,physical_prefix_exact=True,ACT_external_file=str(M.O/'recovery.csv'),ACT_external_sha256=M.sha(M.O/'recovery.csv'),ACT_external_domain='unchanged original1709stocks/90industries',control_fills=len(gold.accounts['L0'].trades),closes=len(gold.daily),preparation_seconds=prepared-t,one_arm_short_seconds=native_done-prepared,total_gate_seconds=time.monotonic()-t,needs_reviewed_budget_code=True));print('OFF_PREFIX_PASS',len(gold.accounts['L0'].trades),round(time.monotonic()-t,3),flush=True)
if __name__=='__main__':main()

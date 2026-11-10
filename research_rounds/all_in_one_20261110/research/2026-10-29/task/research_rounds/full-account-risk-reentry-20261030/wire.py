"""Small research-only hooks on the original ACT executor. No new runner or signal policy."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from dataclasses import replace
import sys,json,math,hashlib,importlib.util,gzip
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;W=O.parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';V=W/'rearm-risk-boundary-design-20261030'
sys.path.insert(0,str(V));from risk_boundary_v2 import RiskBoundary,NegativeReceipt
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n,p):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sys.modules[n]=m;sp.loader.exec_module(m);return m
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]

class Feed:
 def __init__(self,sector,prep,cutoff=None):
  pool=RR/('tech-compound-design-20261026/proposed-pool.csv' if sector=='TECH' else 'innovative-drug-local-recovery-20261028/pool.csv');self.ids=set(pd.read_csv(pool).symbol);self.frames={};self.ev={};self.signals={};self.valid={};self.epoch={};self.sigmas={};self.sigma_checks=[];self.sector=sector
  ar=load('full_rb_original_arithmetic',RR/'pv-strength-b5-20261025/code/arithmetic.py');self.log_ratio=ar.log_ratio;proof=read(RR/'ph1-cross-sector-20261028/event-validation.json');assert proof['passed'];records={x['symbol']:x for x in proof['records'] if x['sector']==sector}
  for sid in sorted(self.ids):
   fp=prep/'facts'/f'{sid}.parquet';sp=prep/'signals'/f'{sid}.parquet';ep=RR/f'ph1-cross-sector-20261028/events/{sector}/{sid}.parquet';rec=records[sid];assert sha(fp)==rec['inputs'][str(fp)] and sha(sp)==rec['inputs'][str(sp)] and sha(ep)==rec['output_sha256']
   f=pd.read_parquet(fp).loc[:cutoff];e=pd.read_parquet(ep).loc[:cutoff];sg=pd.read_parquet(sp,columns=['volume','observed_bar','source_invalid','synthetic_event_bar']).loc[:cutoff];assert f.index.equals(e.index) and f.close.equals(e.close) and f.segment_id.equals(e.segment_id);good=f[['raw_close','factor','close']].gt(0).all(axis=1)&np.isfinite(f[['raw_close','factor','close']]).all(axis=1);assert np.allclose((f.raw_close*f.factor)[good],f.close[good],rtol=64*np.finfo(float).eps,atol=0);assert all(pd.isna(p) or str(p)[:10]<=str(d.date()) for d,p in e.loc[e.event.ne(0),'pivot_date'].items());self.frames[sid]=f;self.ev[sid]=e;self.signals[sid]=sg
   v=f[['close','segment_id']].join(sg[['volume']]);v=v[v[['close','volume']].gt(0).all(axis=1)&np.isfinite(v[['close','volume']]).all(axis=1)];self.valid[sid]={int(seg):g for seg,g in v.groupby('segment_id',sort=False)}
   known=f.e0_ready.astype(bool)&f.e0_target.notna();on=f.e0_target.astype('boolean').where(known).groupby(f.segment_id).ffill().fillna(False).astype(bool);previous=on.groupby(f.segment_id).shift(fill_value=False);start=on&~previous
   labels=pd.Series(None,index=f.index,dtype=object)
   for day in f.index[start]:labels.loc[day]=f'{sid}|source={int(f.loc[day,"segment_id"])}|E0={day.date()}'
   labels=labels.groupby(f.segment_id).ffill().where(on,None);self.epoch[sid]=labels.to_dict()
 def context(self,sid,at):
  f=self.frames[sid];day=pd.Timestamp(at.date());j=f.index.searchsorted(day,side='right')-1;assert j>=0;r=f.iloc[j];seg=int(r.segment_id)
  return dict(source_id=f'{sid}|source={seg}',unit_id=f'{self.sector}|{sid}|source={seg}',structure_id=self.epoch[sid][f.index[j]],source_segment=seg,decision_at=at)
 def sigma(self,sid,day,seg):
  key=(sid,seg,str(day.date()))
  if key in self.sigmas:return self.sigmas[key]
  g=self.valid[sid][seg];past=g[g.index<day].close.tail(64).to_numpy(float)
  if len(past)<64:self.sigmas[key]=None;return None
  r=[self.log_ratio(past[i],past[i-1]) for i in range(1,64)];value=max(math.sqrt(math.fsum(x*x for x in r)/63),1e-8)
  prefix=g.loc[:day];p=prefix[prefix.index<day].close.tail(64).to_numpy(float);assert np.array_equal(p,past);self.sigmas[key]=value;self.sigma_checks.append(dict(symbol=sid,source=seg,date=str(day.date()),sigma=value,confirmation_return_excluded=True,physical_prefix_exact=True));return value
 def observation(self,sid,at,c):
  day=pd.Timestamp(at.date());f=self.frames[sid];e=self.ev[sid];sg=self.signals[sid];native=day in f.index;eknown=day in e.index;observed=bool(day in sg.index and sg.loc[day,'observed_bar'] and not sg.loc[day,'source_invalid'] and not sg.loc[day,'synthetic_event_bar']);bar=at.date().toordinal();context=self.context(sid,at);receipt=None;sigma=None;event=int(e.loc[day,'event']) if eknown else None
  if event==-1:
   receipt=NegativeReceipt(f'{sid}|source={context["source_segment"]}|confirmed={day.date()}|native_event=-1',sid,context['source_id'],bar)
   if not c.exit_locked and c.phase=='OBSERVING':sigma=self.sigma(sid,day,context['source_segment'])
  z=f.loc[day] if native else None;floor=float(z.i_floor) if native and np.isfinite(z.i_floor) else None
  return dict(bar=bar,raw_close=float(z.raw_close) if native and observed else None,factor=float(z.factor) if native and observed else None,unit_id=context['unit_id'],negative=receipt,sigma=sigma,updated_floor=floor,floor_known=native and floor is not None,event_feed_known=eknown),dict(native_event=event,native_day=native,raw_i_buy=bool(z.i_buy) if native else False,market_structure=context['structure_id'])

def account_class(Parent,feed,enabled):
 class Account(Parent):
  def __init__(self,*a,**kw):
   super().__init__(*a,**kw);self.rb_enabled=enabled;self.rb_states={};self.rb_context={};self.rb_meta={}
  def reserve_budget(self,**kw):
   result=super().reserve_budget(**kw)
   if self.rb_enabled and result[0]:
    sid=kw['quote'].security_id;self.rb_context[result[1]]=feed.context(sid,kw['clock'].decision_at)
    self.log('rb_order_context',kw['clock'].decision_at,sid=sid,order_id=result[1],context=self.rb_context[result[1]])
   return result
  def fill_buy(self,sid,w):
   order=self.buys.get(sid);z=self.intents.get(order.order_id) if order else None;oid=order.order_id if order else None;before=self.quantity(sid);filled=super().fill_buy(sid,w)
   if self.rb_enabled and filled:
    if not before:
     assert sid not in self.rb_states;ctx=self.rb_context[oid];cid=f'{sid}|buy={filled.receipt_id}';self.rb_states[sid]=RiskBoundary(cycle_id=cid,symbol=sid,source_id=ctx['source_id'],unit_id=ctx['unit_id'],shares=self.quantity(sid),e0_floor=float(z['floor_signal']),buy_pending=sid in self.buys);self.rb_meta[sid]=dict(context=ctx,entry_at=w.at,order_id=oid,cycle_id=cid)
     self.log('rb_start',w.at,sid=sid,cycle_id=cid,context=ctx,order_id=oid,shares=self.quantity(sid),initial_floor=z['floor_signal'])
    self.rb_states[sid].sync_execution(shares=self.quantity(sid),buy_pending=sid in self.buys,exit_order_pending=sid in self.exits)
   return filled
  def fill_exit(self,sid,w):
   filled=super().fill_exit(sid,w)
   if self.rb_enabled and sid in self.rb_states:
    c=self.rb_states[sid];c.sync_execution(shares=self.quantity(sid),buy_pending=sid in self.buys,exit_order_pending=sid in self.exits)
    if self.quantity(sid)==0 and sid not in self.buys and sid not in self.exits:
     self.log('rb_end',w.at,sid=sid,cycle_id=c.cycle_id,reason=c.exit_reason,episodes=c.episodes,context=self.rb_meta[sid]['context']);del self.rb_states[sid];del self.rb_meta[sid]
   return filled
 return Account

def process(a,stocks,clock,Fact,feed):
 if not a.rb_enabled:return stocks
 out=[]
 for s in stocks:
  sid=s.security_id
  if not a.quantity(sid):out.append(s);continue
  assert sid in a.rb_states,(sid,clock.decision_at,'missing controller');c=a.rb_states[sid];c.sync_execution(shares=a.quantity(sid),buy_pending=sid in a.buys,exit_order_pending=sid in a.exits);obs,diag=feed.observation(sid,clock.decision_at,c);orig=s.trend_up.read(clock) is False or sid in a.exits
  r=c.on_close(**obs,original_exit=orig);a.log('rb_checkpoint',clock.decision_at,sid=sid,**r,**diag)
  if c.exit_locked:s=replace(s,trend_up=Fact(False,clock.decision_at,clock.decision_at,source_id='rb2_'+str(c.exit_reason)))
  out.append(s)
 return tuple(out)

def setup(sector,root,enabled,cutoff=None):
 prior=RR/'pvr-act-comparison-20261027'
 if sector=='TECH':
  P=load('full_rb_original_tech',prior/'code/experiment.py');P.setup('RS',cutoff);R,E=P.R,P.E;Parent=R.Account;prep=Path(read(prior/'input.json')['snapshot']['path']);core=prior/'input';mode='I'
 else:
  loc=RR/'innovative-drug-local-recovery-20261028';sys.path.insert(0,str(loc/'code'));P=load('full_rb_original_drug',loc/'code/study.py');P.setup(root,cutoff);R,E=P.R,P.E;Parent=R.Account;prep=RR/'innovative-drug-sfw3-20261028/prepared';core=prep;mode='ACT'
 R.HERE=root
 if cutoff:E.risk_policy.RECOVERY=E.risk_policy.RECOVERY.loc[:cutoff].copy()
 feed=Feed(sector,prep,cutoff) if enabled else None;R.Account=account_class(Parent,feed,enabled);old_override=E.risk_policy.override
 def override(a,stocks,clock,riskmode,Fact):return process(a,old_override(a,stocks,clock,riskmode,Fact),clock,Fact,feed)
 E.risk_policy.override=override
 old_commit=E.ledger.commit_cutoff
 def commit(a,**kw):
  if not a.rb_enabled:return old_commit(a,**kw)
  factory=kw['decision_factory'];decisions=[]
  def logged(**kwargs):
   d=factory(**kwargs);interesting={e.security_id for e in d.eligibility if e.q is True}|set(a.positions)|set(a.exits)|set(a.buys)|{x.security_id for x in kw.get('completed_exits',())}
   decisions.append(dict(selected=d.selected,rejected=d.rejected,waiting=d.waiting,continue_buys=d.continue_buys,cancel_buys=d.cancel_buys,pause_buys=d.pause_buys,exit_requests=d.exit_requests,ranking_fallbacks=d.ranking_fallbacks,eligibility=[e for e in d.eligibility if e.security_id in interesting],memories=[m for m in d.memories if m.security_id in interesting]));return d
  kw=dict(kw);kw['decision_factory']=logged;before=a.balance(kw['clock'].decision_at,kw['marks']);ack=old_commit(a,**kw)
  a.log('rb_admission',kw['clock'].decision_at,before=before,decisions=decisions,accepted=ack.accepted,rejected=ack.rejected,occupancy=ack.occupancy);return ack
 E.ledger.commit_cutoff=commit
 return R,E,feed,core,prep,mode

"""Same frozen market/ledger, unlimited capacity, fixed 1m gross per issuer episode."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
from decimal import Decimal
import sys,json,gzip,time,hashlib,inspect,types,collections,math,argparse
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
IX=ROOT/'research_rounds/ix-a-share-entry-20261025'
SEC=ROOT/'research_rounds/sector-ix-i-20261026'
G1=ROOT/'research_rounds/b5-g1-20261025'
for p in [OLD/'code',IX/'code',G1/'code']:sys.path.append(str(p))
from current_pool_bridge import load_bundle,load_prepared_states,checked_ref
import current_fixed_pool as pool
import sector_stock_admission as adm
import sector_account as ledger
import multi_runner as native
from run_first10 import first10_specs as old_specs
from policies_g1 import project

CAP=Decimal('1000000');PAD=Decimal('1000000000000')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)

# Keep the original candidate memory, reentry, unknown and exit algorithm;
# only remove its three numerical capacity tests, in this new local module.
src=inspect.getsource(adm.decide)
for condition in ['len(occupied_issuers) >= 6','counts[e.sector_id] >= (6 if variant == \'S1\' else 2)','e.sector_id not in counts and len(counts) >= (1 if variant == \'S1\' else 3)']:
 assert src.count('elif '+condition+':')==1,condition
 src=src.replace('elif '+condition+':','elif False:')
space=dict(adm.decide.__globals__);exec(compile(src,'unlimited_capacity_admission','exec'),space);unlimited_decide=space['decide']

class Account(ledger.SectorAccount):
 @property
 def available(self):return self._available
 @available.setter
 def available(self,value):
  self._available=value
  if not hasattr(self,'minimum_available') or value<self.minimum_available:
   self.minimum_available=value;self.minimum_at=getattr(self,'as_of',None)
 def apply_decision(self,decision,*,clock,quotes,marks,currency_fx=None):
  assert decision.decision_at==clock.decision_at
  self._time(clock.decision_at)
  for sid in decision.exit_requests:self.request_exit(quotes[sid],clock)
  for sid in decision.cancel_buys:self.cancel_buy(sid)
  for sid in decision.pause_buys:
   if sid in self.buys:self.buys[sid].paused=True
  for sid in decision.continue_buys:
   if sid in self.buys:self.buys[sid].paused=False
  eligibility={e.security_id:e for e in decision.eligibility};memories={m.security_id:m for m in decision.memories}
  occupied={x.issuer_id for x in self.occupancy(clock.decision_at)};accepted=[];rejected=[]
  for sid in decision.selected:
   q=quotes.get(sid);e=eligibility[sid]
   if q is None:rejected.append((sid,'decision_quote_unknown'));continue
   assert e.q is True and (q.issuer_id,q.sector_id)==(e.issuer_id,e.sector_id)
   if q.issuer_id in occupied:rejected.append((sid,'issuer_already_committed'));continue
   assert self.available>CAP*2000,'Cash pad accidentally constraining orders'
   m=memories[sid];assert m.created_at is not None and m.origin
   ok,reason=self.reserve_budget(quote=q,clock=clock,gross_budget_cny=CAP,candidate_id=f'{sid}:{m.created_at.isoformat()}:{m.origin}')
   if ok:accepted.append(sid);occupied.add(q.issuer_id)
   else:rejected.append((sid,reason))
  return ledger.DecisionAck(tuple(accepted),tuple(rejected),self.occupancy(clock.decision_at))

SIGNALS={};CACHE={};Q_CACHE={};SINK=None
def decide(*,evidence,lines,historical,clock,variant,sectors,entry_mode,**kwargs):
 key=(clock.decision_at,entry_mode)
 if key not in CACHE:
  if len(CACHE)>4:CACHE.clear();Q_CACHE.clear()
  hs={h.security_id:h for h in historical};securities=[];day=pd.Timestamp(clock.session_date)
  for line in lines:
   h=hs[line.security_id]
   if entry_mode!='E0':
    f=SIGNALS[line.security_id];i=f.index.searchsorted(day,side='right')-1
    if h.trend_up.read(clock) is not None:
     value=bool(f[('i_' if entry_mode=='I' else 'ix_')+'target'].iloc[i]) if i>=0 else None
     h=replace(h,trend_up=replace(h.trend_up,value=value))
   s=pool.build_security(line,h,evidence)
   if entry_mode!='E0':
    allowed=s.buy_allowed.read(clock,for_execution=True)
    event=bool(f.IX.iloc[i]) if i>=0 and f.index[i]==day else False
    s=replace(s,buy_allowed=adm.Fact(None if allowed is None else bool(allowed and event),clock.decision_at,clock.decision_at,source_id='unchanged_G1_I_IX_buy_event'))
   securities.append(s)
  ss={s.sector_id:s for s in sectors};elig={s.security_id:adm.eligibility(s,ss,clock,'S0') for s in securities}
  CACHE[key]=(tuple(securities),elig)
 securities,elig=CACHE[key]
 space['eligibility']=lambda s,sectors,clock,variant:elig[s.security_id]
 d=unlimited_decide(clock=clock,variant='S0',securities=securities,sectors=sectors,**kwargs)
 return pool.CurrentPoolDecision(evidence,d)

def restore_i(f):
 # Exact array implementation already used and verified in the four-pool I study.
 n=len(f);target=np.zeros(n,int);buy=np.zeros(n,bool);active=False;floor=math.nan;segment=None
 seg=f.segment_id.to_numpy();close=f.close.to_numpy(float);shadow=f.e0_target.to_numpy(bool);bf=f.e0_floor.to_numpy(float);be=f.e0_entered.to_numpy(bool);ready=f.strength_ready.to_numpy(bool);grade=f.grade.to_numpy(float);fresh=f.fresh_up.to_numpy(bool)
 for j in range(n):
  exited=False
  if seg[j]!=segment:active=False;floor=math.nan;segment=seg[j]
  if active:
   if not shadow[j] or close[j]<=floor:active=False;exited=True
   elif np.isfinite(bf[j]):floor=max(floor,bf[j])
  opp=shadow[j] and ready[j] and grade[j]>=2 and (be[j] or fresh[j])
  if not active and not exited and opp:active=True;floor=bf[j]
  target[j]=active;buy[j]=active and opp
 return pd.DataFrame(dict(target=target,buy_event=buy),index=f.index)

def context(cutoff=None):
 t=time.time();print(json.dumps(dict(stage='loading_frozen_data',at=now())),flush=True)
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');assert b.signal_ready
 manifests=[];checked=0
 for sid,item in b.series.items():
  if item.record['kind']!='stock':continue
  p=IX/'signals'/f'{sid}.parquet';f=pd.read_parquet(p)
  assert f.index.equals(item.states.index)
  np.testing.assert_array_equal(f.e0_target.to_numpy(bool),item.states.target.to_numpy(bool))
  if cutoff:f=f.loc[:cutoff].copy()
  i=restore_i(f);np.testing.assert_array_equal(i.buy_event.to_numpy(bool),f.IX.to_numpy(bool))
  f=f[['ix_target','IX']].copy();f['i_target']=i.target
  prior=SEC/'signals'/f'{sid}.parquet'
  if prior.is_file():
   old=pd.read_parquet(prior);old=old.loc[f.index]
   np.testing.assert_array_equal(f.i_target.to_numpy(bool),old.i_target.to_numpy(bool));checked+=1
  SIGNALS[sid]=f;manifests.append(dict(sid=sid,source_sha256=sha(p),rows=len(f)))
 if cutoff:
  for item in b.series.values():
   if item.states is not None:item.states=item.states.loc[:cutoff].copy()
  z=np.load(OLD/'h1/matrix.npz');d=pd.DatetimeIndex(z['dates']);n=d.searchsorted(pd.Timestamp(cutoff),side='right')
  b._h1_cache=(d[:n],{s:j for j,s in enumerate(z['symbols'])},z['score'][:n])
 m=native.FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff].copy()
  m.actions={s:[e for e in es if e['effective_date']<=cutoff] for s,es in m.actions.items()}
 print(json.dumps(dict(stage='data_ready',seconds=time.time()-t,stocks=len(SIGNALS),old_I_exact=checked)),flush=True)
 return b,m,dict(signals=manifests,old_I_exact=checked)

class CachedMarket(native.FrozenMarket):
 def latest_mark(self,sid,at):
  if getattr(self,'_mark_time',None)!=at:self._mark_time=at;self._marks_cache={}
  if sid not in self._marks_cache:self._marks_cache[sid]=super().latest_mark(sid,at)
  return self._marks_cache[sid]
 def window(self,sid,at,side,cost_multiplier):
  if getattr(self,'_window_time',None)!=at:self._window_time=at;self._windows_cache={}
  key=(sid,side,cost_multiplier)
  if key not in self._windows_cache:self._windows_cache[key]=super().window(sid,at,side,cost_multiplier)
  return self._windows_cache[key]

class Sink:
 def __init__(self,p):
  self.p=p;p.mkdir(parents=True,exist_ok=False);self.stream={k:gzip.open(p/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions','fills','audit']};self.runner=None;self.rows=0
 def emit(self,name,r):
  aid=r['account'];a=self.runner.accounts[aid]
  if name=='decisions':
   ack=r['ack'];d=ack.decisions[0]
   r=dict(account=aid,at=r['at'],accepted=ack.accepted,rejected=ack.rejected,eligible=[e.security_id for e in d.eligibility if e.q is True],selected=d.selected,exits=ack.decisions[-1].exit_requests)
  else:
   r=dict(r,pnl=r['nav']-PAD,peak_funding=PAD-a.minimum_available,peak_funding_at=a.minimum_at,holding_count=len(a.positions))
   r.pop('mark_observed_at',None);r.pop('mark_source_id',None)
   for k,rows in [('fills',a.fills),('audit',a.audit_log)]:
    for item in rows:self.stream[k].write(json.dumps(native.encoded(dict(account=aid,**(item if isinstance(item,dict) else {f.name:getattr(item,f.name) for f in __import__('dataclasses').fields(item)}))),ensure_ascii=False)+'\n')
    rows.clear()
   self.rows+=1
   if self.rows%90==0:print(json.dumps(dict(stage='running',date=str(r['at'].date()),rows=self.rows)),flush=True)
  self.stream[name].write(json.dumps(native.encoded(r),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for f in self.stream.values():f.close()

class Runner(native.HistoryRunner):
 def write(self,out,summary,provenance):
  write(out/'summary.json',summary);write(out/'provenance.json',provenance)
  for aid,a in self.accounts.items():
   write(out/f'{aid}-final.json',dict(positions=a.positions,buys=a.buys,exits=a.exits,dividends=a.dividends,settlements=a.settlements,fees_cny=a.fees_cny,available=a.available,peak_funding=PAD-a.minimum_available,peak_funding_at=a.minimum_at))

def specs(stresses=('base','cost2','delay1')):
 return tuple(replace(s,account_id=mode+'__'+s.account_id,initial_capital_cny=PAD) for mode in ['E0','I','IX'] for s in old_specs() if s.variant=='S0' and s.stress.name in stresses)

def run(mode):
 cutoff='2015-01-30' if mode.startswith('short') else '2015-03-31' if mode=='prefix' else None
 native.FrozenMarket=CachedMarket
 b,m,receipt=context(cutoff)
 ss=specs(('base',) if mode=='prefix' else ('base','cost2','delay1'))
 native.first10_specs=lambda:ss;native.SectorAccount=Account
 def factory(**kw):
  # Preserve the upstream HistoryRunner, supplying only policy identity.
  raise AssertionError('set per spec through caller adapter')
 # Native runner already parses account mode into the entry_mode argument.
 native.decide_current_pool=decide
 path=HERE/('technical/'+mode if mode!='economic' else 'accounts-v1')
 if mode=='economic':
  assert read(HERE/'technical/short-validation.json')['passed']
  paths=list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',OLD/'inputs-v2/input-manifest.json',OLD/'prepared-v2/manifest.json',OLD/'h1/matrix.npz',OLD/'inputs-v2/economic-protocol.json',OLD/'inputs-v2/market-rules.json',OLD/'code/sector_account.py',OLD/'code/sector_stock_admission.py',IX/'code/multi_runner.py',G1/'code/policies_g1.py']
  write(HERE/'account-freeze-v1.json',dict(recorded_at=now(),before_results=True,paths=9,initial_cash_pad=str(PAD),per_episode_gross=str(CAP),source_receipt=receipt,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
 sink=Sink(path)
 start=native.iso('2015-01-01T00:00:00+08:00');end=native.iso((cutoff or '2026-10-22')+'T15:10:00+08:00')
 r=Runner(b,m,start=start,end=end,sink=sink,synthetic=mode!='economic');sink.runner=r;t=time.time()
 try:
  summary=r.run();summary.update(unlimited_capital=True,initial_capital_cny=None,per_episode_gross=CAP,profit_excludes_pad=True)
  r.write(path,summary,dict(recorded_at=now(),seconds=time.time()-t,mode=mode,source_receipt=receipt))
 except BaseException as exc:write(path/'failure.json',dict(recorded_at=now(),error=repr(exc)));raise
 finally:sink.close()
 print(json.dumps(dict(done=True,mode=mode,seconds=time.time()-t,final_pnl={s:str(x['nav']-PAD) for s,x in r.last_daily.items()})),flush=True)

if __name__=='__main__':run(sys.argv[1])

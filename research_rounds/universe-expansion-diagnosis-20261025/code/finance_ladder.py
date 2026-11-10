"""Four bounded basic accounts, frozen finance, on-demand identical quotes."""
from common import *
import collections,gzip,time
from dataclasses import replace
from types import SimpleNamespace as NS
sys.path.append(str(OLD/'code'));sys.path.append(str(IX/'code'));sys.path.append(str(ABCD/'code'))
from current_pool_bridge import load_bundle,load_prepared_states
import multi_runner as runner
import selection_abcd as base
from run_first10 import first10_specs as originals
import sector_stock_admission as adm
from sector_account import Mark
META=read(OLD/'inputs-v2/metadata.json');FILTERS={'SEMI':'URFI881121','COMM':'URFI881129'};SECTOR={};CACHE={};ORIGINAL_QUOTES=runner.FrozenMarket.quotes

class DummyBoard:
 def at(self,d):return NS(i=0)

class LazyQuotes(dict):
 def __init__(self,market,at):super().__init__();self.market=market;self.at=at;self.misses=set()
 def materialize(self,sid):
  if dict.__contains__(self,sid) or sid in self.misses:return
  line=self.market.lines.get(sid)
  if line is None or not(line.current_stock is True and line.company_cap_cny is not None and line.company_cap_cny>1e10 and (line.market=='A' or line.southbound_selected is True)):
   self.misses.add(sid);return
  r=ORIGINAL_QUOTES(self.market,self.at,[sid])
  if sid in r:dict.__setitem__(self,sid,r[sid])
  else:self.misses.add(sid)
 def get(self,sid,default=None):self.materialize(sid);return dict.get(self,sid,default)
 def __contains__(self,sid):self.materialize(sid);return dict.__contains__(self,sid)
 def __missing__(self,sid):self.materialize(sid);return dict.__getitem__(self,sid)

def quotes(self,at,ids=None):return LazyQuotes(self,at) if ids is None else ORIGINAL_QUOTES(self,at,ids)

def sector_value(s,clock):
 old=s.trend_up.read(clock)
 if old is None:return None
 f=SECTOR[s.sector_id];i=f.index.searchsorted(pd.Timestamp(clock.session_date),side='right')-1
 return bool(f.ix_target.iloc[i]) if i>=0 and bool(f.ready.iloc[i]) else None

def decide(*,evidence,lines,historical,clock,variant,sectors,entry_mode,**kwargs):
 key=(clock.decision_at,entry_mode)
 if key not in CACHE:
  if len(CACHE)>12:CACHE.clear()
  ll=lines;hs=historical;ss=sectors
  if entry_mode in FILTERS:
   sid=FILTERS[entry_mode];ll=tuple(l for l in lines if l.sector_id==sid);ids={l.security_id for l in ll};hs=tuple(h for h in historical if h.security_id in ids);ss=tuple(s for s in sectors if s.sector_id==sid)
  if entry_mode=='GATE':
   values={s.sector_id:sector_value(s,clock) for s in sectors};stocksector={l.security_id:l.sector_id for l in lines};new=[]
   for h in historical:
    a=h.trend_up.read(clock);b=values.get(stocksector[h.security_id]);up=False if a is False or b is False else True if a is True and b is True else None
    new.append(replace(h,trend_up=adm.Fact(up,clock.decision_at,clock.decision_at,observed_at=clock.decision_at,source_id='HIX1:stockIX_AND_sectorIX')))
   hs=tuple(new);ss=tuple(replace(s,trend_up=adm.Fact(values[s.sector_id],clock.decision_at,clock.decision_at,observed_at=s.trend_up.observed_at,source_id='HIX1:sector-IX-state')) for s in sectors)
  CACHE[key]=(ll,hs,ss)
 ll,hs,ss=CACHE[key]
 return base.decide_current_pool(evidence=evidence,lines=ll,historical=hs,clock=clock,variant=variant,sectors=ss,entry_mode='A',**kwargs)

class Sink:
 def __init__(self,p):
  self.p=p;p.mkdir(parents=True,exist_ok=False);self.fs={k:gzip.open(p/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,r):
  if name=='decisions':
   a=r['ack'];d=a.decisions[-1];r=dict(account=r['account'],at=r['at'],accepted=a.accepted,rejected=a.rejected,eligible=len(a.decisions[0].eligibility),selected=d.selected,exits=d.exit_requests,occupancy=a.occupancy)
  self.fs[name].write(json.dumps(runner.encoded(r),ensure_ascii=False)+'\n')
 def close(self):
  for f in self.fs.values():f.close()

def specs(modes):
 out=[]
 for m in modes:
  variant='S1' if m in FILTERS else 'S0';s=next(s for s in originals() if s.variant==variant and s.stress.name=='base');out.append(replace(s,account_id=m+'__'+s.account_id))
 return tuple(out)

def main():
 t=time.time();print(dict(stage='loading_same_frozen_inputs'),flush=True);b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');buy=collections.defaultdict(set)
 for sid,item in b.series.items():
  if item.record['kind']=='stock':
   f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['ix_target']);item.states=item.states.copy();item.states['target']=f.ix_target
 for sid,ds in read(ABCD/'prepared/buy-events.json').items():
  for d in ds:buy[d].add(sid)
 base.configure(buy,DummyBoard())
 for s in b.sector_series:SECTOR[s]=pd.read_parquet(HERE/'sector-states'/f'{s}.parquet')
 print(dict(stage='loading_raw_execution',seconds=time.time()-t),flush=True);m=runner.FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'));runner.decide_current_pool=decide
 start=runner.iso('2021-01-04T15:10:00+08:00');end=runner.iso(END+'T15:10:00+08:00')
 # Lazy access changes only when an already-defined immutable quote is created.
 # Two complete short financial replays check same NAV, fills, orders and cash.
 controls=[]
 for lazy in [False,True]:
  runner.FrozenMarket.quotes=quotes if lazy else ORIGINAL_QUOTES;runner.first10_specs=lambda:specs(['ALL']);p=HERE/'technical'/('lazy' if lazy else 'eager');sink=Sink(p);r=runner.HistoryRunner(b,m,start=start,end=runner.iso('2021-01-15T15:10:00+08:00'),sink=sink,synthetic=True)
  try:r.write(p,r.run(),dict(lazy_quotes=lazy,financial_engine_changed=False))
  finally:sink.close()
  controls.append(p)
 assert read(controls[0]/'ALL__S0_base.json')==read(controls[1]/'ALL__S0_base.json')
 with gzip.open(controls[0]/'daily.jsonl.gz','rt') as f:a=f.read()
 with gzip.open(controls[1]/'daily.jsonl.gz','rt') as f:c=f.read()
 assert a==c
 write(HERE/'technical/lazy-identity.json',dict(passed=True,financial_json_exact=True,day_rows=10,quote_values_unchanged=True))
 paths=list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',HERE/'sector-states/manifest.json',HERE/'technical/lazy-identity.json'];write(HERE/'ladder-freeze.json',dict(recorded_at=now(),new_accounts=4,modes=['ALL','SEMI','COMM','GATE'],start=START,end=END,initial_each=1000000,individual_IX_unchanged=True,HIX1='sector IX gates both new entries and ongoing stock eligibility; no change to RS/sizing/individual IX',missing_gap_guard_not_combined=True,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
 print(dict(stage='four_basic_accounts',seconds=time.time()-t),flush=True);runner.FrozenMarket.quotes=quotes;runner.first10_specs=lambda:specs(['ALL','SEMI','COMM','GATE']);sink=Sink(HERE/'accounts');r=runner.HistoryRunner(b,m,start=start,end=end,sink=sink,synthetic=False)
 try:r.write(HERE/'accounts',r.run(),dict(recorded_at=now(),same_inputs=True,lazy_quotes=True,code_sha256=sha(__file__)))
 finally:sink.close()
 print(dict(done=True,seconds=time.time()-t,final_nav={k:str(v['nav']) for k,v in r.last_daily.items()}),flush=True)
if __name__=='__main__':main()

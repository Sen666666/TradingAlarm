"""Four entry consumers over the unchanged A-share cash/share execution engine."""
import sys,json,gzip,time,subprocess,collections
from dataclasses import asdict
import pandas as pd
import numpy as np
from util_ix import *
sys.path.append(str(OLD/'code'))
from current_pool_bridge import load_bundle,load_prepared_states
from market_runner import FrozenMarket,HistoryRunner,iso,encoded
import selection_adapter

class CompactSink:
 def __init__(self,out):
  self.out=Path(out);self.out.mkdir(exist_ok=False,parents=True)
  self.streams={k:gzip.open(self.out/f'{k}.jsonl.gz','wt',encoding='utf-8',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,row):
  if name=='decisions':
   ack=row['ack'];first=ack.decisions[0];last=ack.decisions[-1]
   counts=collections.Counter(reason for x in first.eligibility for reason in x.reasons)
   dated_events=selection_adapter.BUY_BY_DAY.get(row['at'].date().isoformat(),set())
   row=dict(account=row['account'],at=row['at'],accepted=ack.accepted,rejected=ack.rejected,
    eligible=tuple(x.security_id for x in first.eligibility if x.q is True),unknown_eligibility=sum(x.q is None for x in first.eligibility),reason_counts=dict(counts),
    event_eligibility=[dict(symbol=x.security_id,sector=x.sector_id,q=x.q,reasons=x.reasons) for x in first.eligibility if x.security_id in dated_events],
    first_selected=first.selected,first_rejected=first.rejected,occupancy=ack.occupancy,
    selected=last.selected,waiting=last.waiting,continue_buys=last.continue_buys,paused_buys=last.pause_buys,cancel_buys=last.cancel_buys,exit_requests=last.exit_requests,rejected_new=last.rejected,ranking_fallbacks=last.ranking_fallbacks)
  self.streams[name].write(json.dumps(encoded(row),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for f in self.streams.values():f.close()

def context(mode,cutoff=None):
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');assert b.signal_ready
 buy=collections.defaultdict(set)
 if mode!='E0':
  for sid,item in b.series.items():
   if item.record['kind']!='stock':continue
   f=pd.read_parquet(HERE/'signals'/f'{sid}.parquet',columns=['ix_target',mode])
   assert item.states.index.equals(f.index)
   item.states=item.states.copy();item.states['target']=f.ix_target
   for dt in f.index[f[mode].astype(bool)]:
    if dt>=pd.Timestamp('2015-01-01') and (cutoff is None or dt<=pd.Timestamp(cutoff)):buy[str(dt.date())].add(sid)
 if cutoff:
  for item in b.series.values():
   if item.states is not None:item.states=item.states.loc[:cutoff]
  z=np.load(OLD/'h1/matrix.npz');d=pd.DatetimeIndex(z['dates']);n=d.searchsorted(pd.Timestamp(cutoff),side='right');b._h1_cache=(d[:n],{s:j for j,s in enumerate(z['symbols'])},z['score'][:n])
 m=FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff]
  for sid in m.actions:m.actions[sid]=[a for a in m.actions[sid] if a['effective_date']<=cutoff]
 selection_adapter.configure(mode,dict(buy));return b,m

def worker(mode,technical=False,cutoff=None):
 freeze=read(HERE/('technical-freeze.json' if mode=='E0' else 'freeze.json'));verify(freeze['sha256']);verify(read(HERE/'old-identity-before.json')['sha256'])
 b,m=context(mode,cutoff)
 package=read(OLD/'inputs-v2/package.json');start=iso(package['start']);end=iso(package['end']) if not cutoff else max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 out=HERE/('technical/E0-controls' if mode=='E0' else f'technical/prefix-{mode}-{cutoff}' if cutoff else f'accounts/{mode}')
 sink=CompactSink(out);r=HistoryRunner(b,m,start=start,end=end,sink=sink,synthetic=technical)
 if mode=='E0' or cutoff:
  r.specs=tuple(x for x in r.specs if x.stress.name=='base');r.accounts={x.account_id:r.accounts[x.account_id] for x in r.specs};r.memory={k:v for k,v in r.memory.items() if k in r.accounts}
 provenance=dict(recorded_at=now(),entry=mode,technical=technical,cutoff=cutoff,source='old frozen RS-H1 full market package',account_specs=[asdict(x) for x in r.specs],entry_changes_only=True,shared_IX_exit=True,cache='pure cutoff facts only; same admission bytecode',engine_financial_source_sha256=sha(OLD/'code/sector_account.py'))
 try:
  summary=r.run();r.write(out,summary,provenance)
 except BaseException as exc:
  r.write(out,dict(status='failed_partial_run',error=type(exc).__name__+':'+str(exc),completed_accounts=0),provenance);raise
 finally:sink.close()
 if mode=='E0' or cutoff:
  reference=OLD/'accounts-v2' if mode=='E0' else HERE/'accounts'/mode
  expected={}
  with gzip.open(reference/'daily.jsonl.gz','rt') as f:
   for line in f:
    z=json.loads(line)
    if z['account'] in r.accounts and iso(z['at'])<=end:expected[(z['account'],z['at'])]=z
  count=0
  with gzip.open(out/'daily.jsonl.gz','rt') as f:
   for line in f:
    z=json.loads(line);assert z==expected.pop((z['account'],z['at']));count+=1
  assert not expected
  if mode=='E0':
   for aid in r.accounts:
    actual=read(out/f'{aid}.json');old=read(reference/f'{aid}.json');assert actual==old,aid
  write(out/'comparison.json',dict(recorded_at=now(),passed=True,accounts=len(r.accounts),exact_daily_rows=count,old_full_account_payloads_exact=mode=='E0',future_raw_states_actions_removed=bool(cutoff)))
 print(dict(done=True,mode=mode,cutoff=cutoff,accounts=len(r.accounts),final_nav=summary['final_nav']),flush=True)

if __name__=='__main__':
 worker(sys.argv[1],technical=sys.argv[1]=='E0' or len(sys.argv)>2,cutoff=sys.argv[2] if len(sys.argv)>2 else None)

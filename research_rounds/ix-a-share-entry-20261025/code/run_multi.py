"""One chronological market pass for all48 independent one-million accounts."""
import sys,collections,gzip,json,os
from util_ix import *
sys.path.append(str(OLD/'code'))
import pandas as pd
from current_pool_bridge import load_bundle,load_prepared_states
from multi_runner import FrozenMarket,HistoryRunner,iso,encoded
import multi_selection

class Sink:
 def __init__(self,out):
  self.out=Path(out);self.out.mkdir(parents=True,exist_ok=False)
  self.streams={k:gzip.open(self.out/f'{k}.jsonl.gz','wt',encoding='utf-8',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,row):
  if name=='decisions':
   mode=row['account'].split('__',1)[0];ack=row['ack'];first=ack.decisions[0];last=ack.decisions[-1];ids=multi_selection.BUY.get(mode,{}).get(row['at'].date().isoformat(),set())
   row=dict(account=row['account'],at=row['at'],accepted=ack.accepted,rejected=ack.rejected,eligible=tuple(x.security_id for x in first.eligibility if x.q is True),unknown_eligibility=sum(x.q is None for x in first.eligibility),reason_counts=dict(collections.Counter(reason for x in first.eligibility for reason in x.reasons)),event_eligibility=[dict(symbol=x.security_id,sector=x.sector_id,q=x.q,reasons=x.reasons) for x in first.eligibility if x.security_id in ids],first_selected=first.selected,first_rejected=first.rejected,occupancy=ack.occupancy,waiting=last.waiting,continue_buys=last.continue_buys,paused_buys=last.pause_buys,cancel_buys=last.cancel_buys,exit_requests=last.exit_requests,rejected_new=last.rejected,ranking_fallbacks=last.ranking_fallbacks)
  self.streams[name].write(json.dumps(encoded(row),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for f in self.streams.values():f.close()

def context(cutoff=None):
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');assert b.signal_ready
 buy={mode:collections.defaultdict(set) for mode in ENTRY_TYPES}
 for sid,item in b.series.items():
  if item.record['kind']!='stock':continue
  f=pd.read_parquet(HERE/'signals'/f'{sid}.parquet',columns=['ix_target']+ENTRY_TYPES);assert f.index.equals(item.states.index)
  item.states=item.states.copy();item.states['target']=f.ix_target
  for mode in ENTRY_TYPES:
   for dt in f.index[f[mode].astype(bool)]:
    if dt>=pd.Timestamp('2015-01-01') and (cutoff is None or dt<=pd.Timestamp(cutoff)):buy[mode][str(dt.date())].add(sid)
 if cutoff:
  import numpy as np
  for item in b.series.values():
   if item.states is not None:item.states=item.states.loc[:cutoff]
  z=np.load(OLD/'h1/matrix.npz');d=pd.DatetimeIndex(z['dates']);n=d.searchsorted(pd.Timestamp(cutoff),side='right');b._h1_cache=(d[:n],{s:j for j,s in enumerate(z['symbols'])},z['score'][:n])
 m=FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff]
  for sid in m.actions:m.actions[sid]=[e for e in m.actions[sid] if e['effective_date']<=cutoff]
 multi_selection.configure(buy);return b,m

def main(cutoff=None):
 freeze=read(HERE/'freeze.json');verify(freeze['sha256']);verify(read(HERE/'old-identity-before.json')['sha256'])
 if not cutoff:
  assert read(HERE/'technical/E0-controls/comparison.json')['passed']
  assert read(HERE/'validation/multi-decision-identity.json')['passed']
 b,m=context(cutoff);package=read(OLD/'inputs-v2/package.json');end=iso(package['end']) if not cutoff else max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 if cutoff:os.environ['IX_ENTRY_STRESSES']='base'
 out=HERE/('accounts' if not cutoff else f'technical/multi-prefix-{cutoff}');sink=Sink(out);r=HistoryRunner(b,m,start=iso(package['start']),end=end,sink=sink,synthetic=bool(cutoff))
 provenance=dict(recorded_at=now(),entry_modes=ENTRY_TYPES,technical=bool(cutoff),cutoff=cutoff,account_specs=[s.account_id for s in r.specs],source='same frozen A-share engine, shared immutable facts, independent accounts',code=sha(__file__))
 try:
  summary=r.run();r.write(out,summary,provenance)
 except BaseException as e:
  r.write(out,dict(status='failed_partial_run',error=type(e).__name__+':'+str(e),completed_accounts=0),provenance);raise
 finally:sink.close()
 if cutoff:
  expected={}
  with gzip.open(HERE/'accounts/daily.jsonl.gz','rt') as f:
   for line in f:
    x=json.loads(line)
    if x['account'] in r.accounts and iso(x['at'])<=end:expected[(x['account'],x['at'])]=x
  n=0
  with gzip.open(out/'daily.jsonl.gz','rt') as f:
   for line in f:x=json.loads(line);assert x==expected.pop((x['account'],x['at']));n+=1
  assert not expected;write(out/'comparison.json',dict(recorded_at=now(),passed=True,technical_accounts=16,daily_rows_exact=n,future_prices_states_actions_removed=True))
 print(dict(done=True,cutoff=cutoff,accounts=len(r.accounts),final_nav=summary['final_nav']),flush=True)

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)

"""One finite entry-only correction after the causal timing diagnostic."""
from common import *
import collections,time
import finance_ladder as fl
import multi_runner as runner
from current_pool_bridge import load_bundle,load_prepared_states

def main():
 assert read(HERE/'first-opportunity/summary.json')['first_events']>0
 p=HERE/'first-account';p.mkdir(exist_ok=False);paths=[HERE/'code/run_first_account.py',HERE/'code/finance_ladder.py',HERE/'first-opportunity/events.json',HERE/'first-opportunity/summary.json',HERE/'entry-attribution/summary.json'];write(p/'freeze.json',dict(recorded_at=now(),mechanism='F1: only first full original S0 eligibility per IX participation episode; later price-only continuation cannot renew an old episode buy event',initial_capital=1000000,one_account_only=True,other_policy='original ALL S0, same stock IX exits and sector E0 gate, original RS-H1 and finance; no sectorIX extra exit',start=START,end=END,sha256={str(x.relative_to(ROOT)):sha(x) for x in paths}))
 t=time.time();b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');buy=collections.defaultdict(set)
 for sid,item in b.series.items():
  if item.record['kind']=='stock':
   f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['ix_target']);item.states=item.states.copy();item.states['target']=f.ix_target
 for sid,ds in read(HERE/'first-opportunity/events.json').items():
  for d in ds:buy[d].add(sid)
 fl.base.configure(buy,fl.DummyBoard());m=runner.FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'));runner.FrozenMarket.quotes=fl.quotes;runner.decide_current_pool=fl.decide;runner.first10_specs=lambda:fl.specs(['FIRST']);sink=fl.Sink(p/'accounts');r=runner.HistoryRunner(b,m,start=runner.iso('2021-01-04T15:10:00+08:00'),end=runner.iso(END+'T15:10:00+08:00'),sink=sink,synthetic=False)
 try:r.write(p/'accounts',r.run(),dict(recorded_at=now(),entry_only_correction=True,individual_exit_changed=False,seconds=time.time()-t))
 finally:sink.close()
 print(dict(done=True,seconds=time.time()-t,nav={k:str(v['nav']) for k,v in r.last_daily.items()}),flush=True)
if __name__=='__main__':main()

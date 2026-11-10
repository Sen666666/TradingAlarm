"""Bounded technical replays on truncated raw/state prefixes, base four only."""
from pathlib import Path
import json,sys,gzip
from history_runner import FrozenMarket,HistoryRunner,StreamingSink,iso
from current_pool_bridge import load_bundle,load_prepared_states
from build_inputs import HERE,read,write,now,sha256

def main(cutoff):
 package=read(HERE/'inputs-v1/package.json');protocol=read(HERE/'inputs-v1/economic-protocol.json')
 b=load_bundle(HERE/'inputs-v1/input-manifest.json');load_prepared_states(b,HERE/'prepared-v1')
 m=FrozenMarket(b,read(HERE/'inputs-v1/market-rules.json'),[],protocol)
 end=max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 # Remove future values rather than relying only on <= clocks in the provider.
 for item in b.series.values():
  if item.states is not None:item.states=item.states.loc[:cutoff]
 for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff]
 for sid in m.actions:m.actions[sid]=[e for e in m.actions[sid] if e['effective_date']<=cutoff]
 out=HERE/'technical-prefix'/cutoff;sink=StreamingSink(out)
 r=HistoryRunner(b,m,start=iso(package['start']),end=end,synthetic=True,sink=sink)
 r.specs=tuple(s for s in r.specs if s.variant!='B0' and s.stress.name=='base')
 r.accounts={s.account_id:r.accounts[s.account_id] for s in r.specs}
 try:summary=r.run();r.write(out,summary,{'technical_only':True,'future_source_values_removed_after':cutoff,'code':sha256(__file__)})
 finally:sink.close()
 # Compare complete daily components, positions and pending orders exactly.
 expected={}
 with gzip.open(HERE/'accounts-v1/daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account'] in r.accounts and iso(x['at'])<=end:expected[(x['account'],x['at'])]=x
 count=0
 with gzip.open(out/'daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);assert x==expected.pop((x['account'],x['at']));count+=1
 assert not expected
 write(out/'exact-comparison.json',dict(recorded_at=now(),cutoff=cutoff,accounts=4,technical_account_replays=4,
  daily_rows_exact=count,all_future_raw_states_actions_removed=True,economic_comparison_accounts_added=0,passed=True))
 print({'cutoff':cutoff,'daily_rows_exact':count,'passed':True},flush=True)

if __name__=='__main__':main(sys.argv[1])

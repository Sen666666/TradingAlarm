"""Same predeclared base4 prefix replay, with a bounded live-main-file reader.

The original frozen prefix verifier is untouched. This reader stops as soon as
the completed main stream passes the prefix end, so no future result is needed.
"""
import sys,gzip,json
from history_runner import FrozenMarket,HistoryRunner,StreamingSink,iso
from current_pool_bridge import load_bundle,load_prepared_states
from build_inputs import HERE,read,write,now,sha256

def main(cutoff):
 package=read(HERE/'inputs-v1/package.json');protocol=read(HERE/'inputs-v1/economic-protocol.json')
 b=load_bundle(HERE/'inputs-v1/input-manifest.json');load_prepared_states(b,HERE/'prepared-v1')
 m=FrozenMarket(b,read(HERE/'inputs-v1/market-rules.json'),[],protocol)
 end=max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 for item in b.series.values():
  if item.states is not None:item.states=item.states.loc[:cutoff]
 for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff]
 for sid in m.actions:m.actions[sid]=[e for e in m.actions[sid] if e['effective_date']<=cutoff]
 out=HERE/'technical-prefix'/cutoff;sink=StreamingSink(out)
 r=HistoryRunner(b,m,start=iso(package['start']),end=end,synthetic=True,sink=sink)
 r.specs=tuple(s for s in r.specs if s.variant!='B0' and s.stress.name=='base')
 r.accounts={s.account_id:r.accounts[s.account_id] for s in r.specs}
 try:summary=r.run();r.write(out,summary,dict(technical_only=True,future_source_values_removed_after=cutoff,code=sha256(__file__)))
 finally:sink.close()
 expected={};observed_later=False
 with gzip.open(HERE/'accounts-v1/daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if iso(x['at'])>end:observed_later=True;break
   if x['account'] in r.accounts:expected[(x['account'],x['at'])]=x
 assert observed_later,'Main must have advanced past the prefix before this check'
 count=0
 with gzip.open(out/'daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);assert x==expected.pop((x['account'],x['at']));count+=1
 assert not expected
 write(out/'exact-comparison.json',dict(recorded_at=now(),cutoff=cutoff,accounts=4,technical_account_replays=4,
  daily_rows_exact=count,all_future_raw_states_actions_removed=True,economic_comparison_accounts_added=0,passed=True,verifier_sha256=sha256(__file__)))
 print({'cutoff':cutoff,'daily_rows_exact':count,'passed':True},flush=True)

if __name__=='__main__':main(sys.argv[1])

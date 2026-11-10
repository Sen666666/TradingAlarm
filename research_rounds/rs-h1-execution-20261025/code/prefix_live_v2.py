"""Predeclared four-policy source truncation against two live main groups."""
import sys,gzip,json
import numpy as np,pandas as pd
from history_runner import FrozenMarket,HistoryRunner,StreamingSink,iso
from current_pool_bridge import load_bundle,load_prepared_states
from build_inputs import HERE,read,write,now,sha256

def main(cutoff):
 package=read(HERE/'inputs-v2/package.json');protocol=read(HERE/'inputs-v2/economic-protocol.json')
 b=load_bundle(HERE/'inputs-v2/input-manifest.json');load_prepared_states(b,HERE/'prepared-v2')
 z=np.load(HERE/'h1/matrix.npz');dates=pd.DatetimeIndex(z['dates']);n=dates.searchsorted(pd.Timestamp(cutoff),side='right')
 b._h1_cache=(dates[:n].copy(),{sid:j for j,sid in enumerate(z['symbols'])},z['score'][:n].copy())
 m=FrozenMarket(b,read(HERE/'inputs-v2/market-rules.json'),[],protocol)
 end=max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 for item in b.series.values():
  if item.states is not None:item.states=item.states.loc[:cutoff]
 for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff]
 for sid in m.actions:m.actions[sid]=[e for e in m.actions[sid] if e['effective_date']<=cutoff]
 out=HERE/'technical-prefix-v2'/cutoff;sink=StreamingSink(out)
 r=HistoryRunner(b,m,start=iso(package['start']),end=end,synthetic=True,sink=sink)
 r.specs=tuple(s for s in r.specs if s.variant!='B0' and s.stress.name=='base')
 r.accounts={s.account_id:r.accounts[s.account_id] for s in r.specs}
 try:summary=r.run();r.write(out,summary,dict(technical_only=True,future_source_values_removed_after=cutoff,code=sha256(__file__)))
 finally:sink.close()
 expected={}
 for group in ['G0','G1']:
  later=False
  with gzip.open(HERE/'accounts-v2/groups'/group/'daily.jsonl.gz','rt') as f:
   for line in f:
    x=json.loads(line)
    if iso(x['at'])>end:later=True;break
    if x['account'] in r.accounts:expected[(x['account'],x['at'])]=x
  assert later,'Main group must advance past prefix'
 count=0
 with gzip.open(out/'daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);assert x==expected.pop((x['account'],x['at']));count+=1
 assert not expected
 write(out/'exact-comparison.json',dict(recorded_at=now(),cutoff=cutoff,accounts=4,technical_account_replays=4,
  daily_rows_exact=count,all_future_raw_states_actions_removed=True,economic_comparison_accounts_added=0,passed=True,verifier_sha256=sha256(__file__)))
 print({'cutoff':cutoff,'daily_rows_exact':count,'passed':True},flush=True)

if __name__=='__main__':main(sys.argv[1])

"""All-stock static factor verification. No account or financial replay."""
from pathlib import Path
import json,hashlib,time,sys
import numpy as np,pandas as pd
from continuous_factors import OpenFactorTimeline
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
M=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
SRC=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_pool_bridge.py')
hashes={}
def sha(p):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();hashes[str(p)]=h;return h
def read(p):sha(p);return json.loads(Path(p).read_text())
def checked(ref):
 p=Path(ref['path']);p=p if p.is_absolute() else P/p
 assert sha(p)==ref['sha256'],str(p)
 return p
def write(n,v):
 p=O/n
 with p.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False,default=str)
start=time.monotonic();manifest=read(M);records={r['series_id']:r for r in read(P/'manifest.json')['series']}
sha(SRC);sha(__file__);sha(O/'continuous_factors.py')
rows=[];diff=[];actions=[];coverage=0;prefix_tests=0
for n,r in enumerate(manifest):
 sid=r['symbol'];rec=records[sid];rp=checked(rec['raw']);ap=checked(rec['adjustment']['actions'])
 obj=read(ap);assert obj['status'] in ('reviewed_terms','declared_research_proxy') and not obj.get('unresolved')
 assert obj['series_id']==sid
 raw=pd.read_parquet(rp);fp=Path(r['refs']['facts']);assert sha(fp)==r['output_sha256'][str(fp)]
 facts=pd.read_parquet(fp,columns=['factor'])
 timeline=OpenFactorTimeline(raw,obj['events'],method=rec['adjustment']['method'])
 idx=facts.index[(facts.index>=timeline.start)&(facts.index<=timeline.end)]
 got=timeline.at_dates(idx).to_numpy(dtype=float);want=facts.loc[idx,'factor'].to_numpy(dtype=float)
 same=(got==want)|(np.isnan(got)&np.isnan(want))
 missing=len(facts)-len(idx);coverage+=len(idx)
 for i in np.flatnonzero(~same):
  diff.append(dict(sid=sid,day=str(idx[i].date()),derived=float(got[i]),original=float(want[i]),absolute_gap=float(abs(got[i]-want[i]))))
 for a in timeline.action_audit:actions.append(dict(sid=sid,**a))
 # Perturb last observed close: factor on that date cannot change.
 raw2=raw.copy();raw2.loc[raw2.index[-1],'close']=123456789.0
 t2=OpenFactorTimeline(raw2,obj['events'],method=rec['adjustment']['method'])
 assert timeline.factor_float(timeline.end)==t2.factor_float(timeline.end)
 prefix_tests+=1
 rows.append(dict(sid=sid,facts_rows=len(facts),compared_rows=len(idx),outside_coverage=missing,
  exact=bool(same.all()) and not missing,mismatches=int((~same).sum()),
  action_count=len(timeline.action_audit),missing_bar_actions=sum(a['missing_raw_bar'] for a in timeline.action_audit)))
 if (n+1)%100==0:print('STATIC',n+1,'mismatches',len(diff),flush=True)
write('STOCK_CHECKS.json',rows);write('DIFFERENCES.json',diff);write('ACTION_REFERENCE_AUDIT.json',actions)
write('SOURCE_SHA256.json',hashes)
write('SUMMARY.json',dict(passed=all(r['exact'] for r in rows),stocks=len(rows),compared_rows=coverage,
 mismatching_rows=len(diff),stocks_with_difference=sum(not r['exact'] for r in rows),
 action_events=len(actions),missing_raw_bar_actions=sum(a['missing_raw_bar'] for a in actions),
 last_close_perturbation_tests=prefix_tests,seconds=time.monotonic()-start,
 account_runs=0,account_imports=0,scope='All available original fullfacts factor dates, strict-prior-close theoretical ex-price recurrence',
 limitations=['Action availability assumed preknown; not announcement PIT proof.',
 'Equality to saved factors is not proof of PIT universe/metadata.',
 'Factor queries outside frozen coverage fail; caller must build enough dated coverage.']))
print('DONE',len(rows),coverage,len(diff),round(time.monotonic()-start,2),flush=True)

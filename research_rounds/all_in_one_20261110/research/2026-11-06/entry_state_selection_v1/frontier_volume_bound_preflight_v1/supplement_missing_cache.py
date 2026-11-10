"""Complete the two preselected 2025 points outside overlap cache coverage. No changes to frozen formula."""
from pathlib import Path
import json,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O))
import preflight as p

if (O/'SUPPLEMENT_QA.json').exists():raise RuntimeError('Refuse duplicate supplement')
p.src(O/'CONTRACT.md');p.src(O/'FIXED_CASES.json');p.src(O/'preflight.py');p.src(Path(__file__))
base=json.loads((O/'FIXED_CASE_RESULTS.json').read_text())
cases=json.loads((O/'FIXED_CASES.json').read_text())
missing=[c for c in cases if c['sid']=='300666.SZ' and c['day'] in ['2025-12-15','2025-12-17']]
assert len(missing)==2
m={x['symbol']:x for x in json.loads(p.src(p.M).read_text())}['300666.SZ']
sp=next(x for x in m['source_sha256'] if x.endswith('/signal.parquet'))
raw=pd.read_parquet(p.src(sp,m['source_sha256'][sp]))
fp=O.parent/'independent_channel_probe_preflight_v1/FIXED_DAILY.csv'
existing=json.loads((O.parent/'independent_channel_probe_preflight_v1/SOURCE_HASHES.json').read_text())
# Native protocol/root engine are frozen original sources; daily fact file added as complete preselected receipt source.
p.src(O.parent/'independent_channel_probe_preflight_v1/core.py',existing[str(O.parent/'independent_channel_probe_preflight_v1/core.py')])
prior=pd.read_csv(p.src(fp),parse_dates=['day','root_day'])
with np.load(p.src(p.H),allow_pickle=False) as n:cal=pd.DatetimeIndex(n['dates'])
rows=[]
for case in missing:
 d=pd.Timestamp(case['day'])
 rr=prior[prior.sid.eq(case['sid'])&prior.day.eq(d)]
 assert len(rr)==1 and bool(rr.iloc[0].receipt)
 rec=rr.iloc[0].to_dict()
 z=p.evaluate(raw,rec,case,cal)
 assert z['status']=='KNOWN',z
 assert p.clean(z)==p.clean(p.evaluate(raw.loc[:d],rec,case,cal[cal<=d]))
 future=raw.copy();future.loc[future.index>d,['open','high','low','close','raw_open','raw_high','raw_low','raw_close','amount','raw_volume']]=1e100
 assert p.clean(z)==p.clean(p.evaluate(future,rec,case,cal))
 rows.append(z)
joined=[]
bykey={(r['sid'],r['day']):r for r in rows}
for r in base:
 key=(r['sid'],r['day'])
 joined.append(bykey.get(key,r))
assert len(joined)==19 and all(r['status']=='KNOWN' for r in joined)
p.save('SUPPLEMENT_RESULTS.json',rows)
p.save('FIXED_CASE_RESULTS_COMPLETE.json',joined)
df=pd.DataFrame(joined);df.to_csv(O/'FIXED_CASE_RESULTS_COMPLETE.csv',index=False)
# Compare strict frozen lower-bound permit to the exact-data midpoint expression without changing the gate.
mid=(df.raw_q>(df.boundary_raw+df.raw_H)/2)
bound=pd.Series([bool(r['candidate_permit']) for r in joined])
branch=df.raw_L.le(df.boundary_raw)&df.boundary_raw.lt(df.raw_H)
assert np.array_equal(mid[branch].to_numpy(),bound[branch].to_numpy())
assert all(p.sha(path)==digest for path,digest in p.S.items())
p.save('SUPPLEMENT_SOURCE_HASHES.json',p.S)
p.save('SUPPLEMENT_QA.json',dict(preselected_missing_cache_rows=2,known_completed=19,new_stock_dates=0,formula_changed=False,native_roots_replayed=False,economic_runs=0,filtered_returns=0,source_hashes_unchanged=True,midpoint_point_gate_equivalent_on_fixed_non_gap_rows=True,correction="First run NOT_RECEIPT for two 2025 points was an overlap-cache coverage error, not a conclusion about native receipts. Complete files supersede those two classifications only.",precision="Units shares/CNY and range consistency verified. 0.5 CNY rounding bound not independently sourced. The retained epsilon is an inherited numerical convention, not a certified bound on true source error. Empirical LB must be called a numerical-convention lower bound; the mathematical distribution theorem is conditional on faithful exact moments/support.",promotion="STOP_NOT_PROMOTED"))
print(df[df.sid.eq('300666.SZ')][['sid','day','boundary_raw','raw_q','raw_H','raw_L','LB','UB','candidate_permit']].to_string(index=False))
print('TOTAL',len(df),'PASS',int(df.candidate_permit.sum()),'BLOCK',int((~df.candidate_permit).sum()))

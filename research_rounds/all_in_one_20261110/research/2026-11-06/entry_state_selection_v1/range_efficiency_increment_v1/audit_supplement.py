"""Post-review descriptive exclusion only. No scores, ranking or parameters changed."""
from pathlib import Path
import runpy,pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
e=runpy.run_path(str(O/'experiment.py'))
sha=e['sha'];dump=e['dump'];period=e['period'];periods=e['periods'];blockstat=e['blockstat'];cal=e['calendar']()
seal=json.loads((O/'RANK_SEAL.json').read_text());assert all(sha(O/n)==h for n,h in seal['hashes'].items())
c=pd.read_parquet(O/'FEATURES.parquet');s=pd.read_parquet(O/'SELECTED_WITH_LABELS.parquet')
bad=c[c.common_known&~np.isfinite(c.original_PVR)];bad.to_csv(O/'AUDIT_PVR_UNKNOWN_REORDERABLE.csv',index=False);bad_days=set(bad.day)
res=[];deltas=[]
for h in [5,20,60]:
 good=s.groupby('day')['complete'+str(h)].all()
 whole=s[s.day.isin(good[good].index)&~s.day.isin(bad_days)]
 for per,start,end in periods():
  sub=period(whole,start,end)
  if not len(sub):continue
  means=sub.groupby(['day','method'])['ret'+str(h)].mean().unstack('method')
  for method,g in sub.groupby('method'):
   res.append(dict(period=per,H=h,method=method,N=len(g),dates=g.day.nunique(),mean_day=float(means[method].mean()),mean_event=float(g['ret'+str(h)].mean()),positive_40bp=float(g['ret'+str(h)].gt(.004).mean())))
  for a,b in [('Qrange','PVR'),('Qclose','PVR'),('Qrange','Qclose')]:
   deltas.append(dict(period=per,H=h,comparison=a+'-'+b,**blockstat(means[a]-means[b],cal)))
pd.DataFrame(res).to_csv(O/'AUDIT_EXCLUDE_AFFECTED_DATES_RESULTS.csv',index=False)
pd.DataFrame(deltas).to_csv(O/'AUDIT_EXCLUDE_AFFECTED_DATES_DELTAS.csv',index=False)
p=pd.read_csv(O/'MATCHED_PAIRS_WITH_LABELS.csv');out=[]
for per,start,end in periods():
 for scope,base in [('EXCLUDE_AFFECTED_DATES',p[~p.day.isin(bad_days)]),('PVR_KNOWN_BOTH_ONLY',p[np.isfinite(p.hi_original_PVR)&np.isfinite(p.lo_original_PVR)])]:
  g=period(base,start,end)
  for h in [5,20,60]:
   z=g[g['hi_complete'+str(h)]&g['lo_complete'+str(h)]]
   if not len(z):continue
   delta=z['hi_ret'+str(h)]-z['lo_ret'+str(h)]
   out.append(dict(period=per,scope=scope,H=h,pairs=len(z),PVR_delta_known=int(z.PVR_delta.notna().sum()),mean_event_delta=float(delta.mean()),**blockstat(delta.groupby(z.day).mean(),cal)))
pd.DataFrame(out).to_csv(O/'AUDIT_MATCHED_PAIR_SENSITIVITY.csv',index=False)
checks=dict(
 finding='COMMON_KNOWN_OMITTED_FINITE_ORIGINAL_PVR',
 original_PVR_unknown=int((~np.isfinite(c.original_PVR)).sum()),
 feature_known_PVR_unknown=len(bad),affected_dates=len(bad_days),
 all_pair_count=len(p),pair_PVR_delta_known=int(p.PVR_delta.notna().sum()),
 original_rankings_and_parameters_unchanged=all(sha(O/n)==h for n,h in seal['hashes'].items()),
 reranked=False,account_runs=0,
 interpretation='Original comparison did not fully implement all-arm common-known/unknown-slot contract. Exclusion sensitivity describes existing picks on unaffected dates; not corrected full-universe rerun, not OOS.'
)
dump('AUDIT_ADDENDUM.json',checks)
print(pd.DataFrame(res).query('period=="ALL"').to_string(index=False))
print(pd.DataFrame(deltas).query('period=="ALL"').to_string(index=False))
print(pd.DataFrame(out).query('period=="ALL" and H in [20,60]').to_string(index=False))

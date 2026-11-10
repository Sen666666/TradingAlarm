"""Independent arithmetic, boundary and causal checks. No accounts."""
from bisect import bisect_left,bisect_right
from pathlib import Path
import math,json
import numpy as np
import pandas as pd
from prepare import HERE,ROOT,EXAMPLES,sha,read,write,now
from calculate import Study
from model import raw_momentum,rank_known

def main():
 s=Study();a=s.arrays;cache={};checked=0
 # Independent scalar implementation and sorted/bisect percentile arithmetic.
 def manual(t,h):
  if (t,h) in cache:return cache[t,h]
  output=[]
  for j in range(len(s.symbols)):
   value=0.;ok=h>=5 and h<=252 and t>=h and a['obs_count'][t,j]>=6
   for k,w in enumerate([.4,.2,.2,.2]):
    near=min(63*k,h);far=min(63*(k+1),h)
    if near==far:continue
    if not ok:break
    p,q=a['close'][t-near,j],a['close'][t-far,j]
    ok=math.isfinite(p) and math.isfinite(q) and p>0 and q>0 and a['segment'][t-near,j]==a['segment'][t,j] and a['segment'][t-far,j]==a['segment'][t,j]
    if ok:value+=w*(p/q-1)
   output.append(float(np.round(value,12)) if ok else None)
  ref=sorted(x for x in output if x is not None)
  cache[t,h]=(output,ref);return output,ref
 rows=[]
 for name in ['latest-all','milestones','artificial-truncations']:rows+=read(HERE/'results'/f'{name}.json')
 for row in rows:
  if row['score'] is None:continue
  t=s.dates.get_loc(row['date']);j=s.symbols.index(row['symbol']);values,ref=manual(t,row['h']);m=values[j]
  expected=100*(bisect_left(ref,m)+.5*(bisect_right(ref,m)-bisect_left(ref,m)))/len(ref)
  assert abs(row['raw_momentum']-m)<1e-11
  assert abs(row['score']-expected)<1e-11
  assert row['reference_n']==len(ref);checked+=1
 t=len(s.dates)-1;full=s.at(t,252);continuous=np.isfinite(a['close'][t-252:t+1]).all(axis=0)&np.isfinite(a['old_rs'][t])
 errors=np.abs(full[continuous]-a['old_rs'][t,continuous]);assert np.max(errors)<1e-11
 # Global price denomination is irrelevant; missing symbols do not cause code sorting.
 scaled=raw_momentum(a['close']*.01,a['segment'],a['obs_count'],t,252)
 np.testing.assert_allclose(full,scaled,rtol=0,atol=1e-11,equal_nan=True)
 known=[{'symbol':'000001','score':20.},{'symbol':'300001','score':90.}]
 ranked,unknown=rank_known(known+[{'symbol':'000000','score':None}])
 assert [r['symbol'] for r in ranked]==['300001','000001'] and len(unknown)==1
 # Same horizon and same returns receive the same M, irrespective of price level.
 p=np.tile(np.exp(np.arange(254)*.001)[:,None],(1,25));p[:,1]*=37
 seg=np.zeros_like(p);obs=np.tile(np.arange(1,255)[:,None],(1,25))
 for h in [5,21,62,63,64,125,126,127,188,189,190,251,252]:
  v=raw_momentum(p,seg,obs,253,h);np.testing.assert_allclose(v,np.full(25,v[0]),atol=1e-11)
 assert np.isnan(raw_momentum(p,seg,obs,253,4)).all()
 obs2=obs.copy();obs2[253,0]=5;assert np.isnan(raw_momentum(p,seg,obs2,253,5)[0])
 # Real source/state truncations, not a no-op cutoff argument on full arrays.
 prefixes=[]
 for cutoff in ['2026-01-09','2026-06-02','2026-09-10']:
  prefix=Study(until=cutoff);n=0
  for sid in s.symbols[::19]+EXAMPLES:
   x=s.row(sid,cutoff);y=prefix.row(sid,cutoff)
   assert x==y,(sid,cutoff);n+=1
  prefixes.append({'cutoff':cutoff,'rows_exact':n,'future_price_state_arrays_physically_excluded':True})
 reg=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')
 for name,expected in reg['sha256'].items():assert sha(ROOT/name)==expected,name
 result={'recorded_at':now(),'independent_rows_checked':checked,'continuous_old_formula_identity_count':int(continuous.sum()),
  'old_formula_max_absolute_difference':float(np.max(errors)),'price_scale_invariance':True,'missing_candidate_isolation':True,
  'same_horizon_same_path_equality':True,'min_observation_and_quarter_boundaries':True,'real_prefixes':prefixes,
  'frozen_E0_R_R1_files_unchanged':len(reg['sha256']),'accounts_run':0,'all_passed':True}
 p=HERE/'audit/verification.json';assert not p.exists();write(p,result);print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()

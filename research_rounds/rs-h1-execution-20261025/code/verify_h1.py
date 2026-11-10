"""Independent four-block arithmetic and sorted-midrank, plus physical prefixes."""
from pathlib import Path
import json,bisect,hashlib
import numpy as np,pandas as pd
from prepare_h1 import HERE,read,write
from rs_h1_model import raw_momentum

def independent(z,t,h,l,r):
 c=z['close'];s=z['segment'];v=np.zeros(r-l);valid=np.isfinite(c[t,l:r])&(z['obs_count'][t,l:r]>=6)
 for near,far,w in zip([0,63,126,189],[63,126,189,252],[.4,.2,.2,.2]):
  near,far=min(near,h),min(far,h)
  if near==far:continue
  p,q=c[t-near,l:r],c[t-far,l:r]
  valid&=np.isfinite(p)&np.isfinite(q)&(p>0)&(q>0)&(s[t-near,l:r]==s[t,l:r])&(s[t-far,l:r]==s[t,l:r])
  with np.errstate(divide='ignore',invalid='ignore'):v+=w*(p/q-1)
 return np.where(valid,np.round(v,12),np.nan)
def main():
 z=dict(np.load(HERE/'h1/matrix.npz'));ds=pd.DatetimeIndex(z['dates']);symbols=list(z['symbols']);checks=0
 old=read(HERE.parent/'rs-history-matched-20261025/results/latest-all.json');t=ds.get_loc('2026-10-22')
 for row in old:
  j=symbols.index(row['symbol']);v=z['score'][t,j];assert (row['score'] is None and np.isnan(v)) or abs(v-row['score'])<1e-10,(row['symbol'],row['score'],v)
  checks+=1
 sample_dates=[str(ds[(ds.year==year)&(ds.month==month)][-1].date()) for year in range(2015,2027) for month in [3,9] if any((ds.year==year)&(ds.month==month))]+['2015-01-05','2026-10-22']
 rowchecks=prefixchecks=0
 for date in sample_dates:
  t=ds.get_loc(date)
  for l,r in [(0,1709),(1709,1799)]:
   for h in np.unique(z['h'][t,l:r]):
    h=int(h)
    if h<5:continue
    v=independent(z,t,h,l,r);ref=sorted(v[np.isfinite(v)]);target=np.flatnonzero((z['h'][t,l:r]==h)&np.isfinite(z['close'][t,l:r])&(z['obs_count'][t,l:r]>=6))
    for k in target:
     x=v[k];expected=100*(bisect.bisect_left(ref,x)+.5*(bisect.bisect_right(ref,x)-bisect.bisect_left(ref,x)))/len(ref) if np.isfinite(x) and len(ref)>=20 else np.nan
     actual=z['score'][t,k+l];assert np.isnan(expected) and np.isnan(actual) or abs(expected-actual)<1e-10,(date,k,expected,actual)
     rowchecks+=1
 for cut in ['2017-12-31','2020-12-31','2023-12-31']:
  end=ds.searchsorted(pd.Timestamp(cut),side='right');c=z['close'][:end].copy();s=z['segment'][:end].copy();o=z['obs_count'][:end].copy()
  for t in range(end-5,end):
   for l,r in [(0,1709),(1709,1799)]:
    for h in np.unique(z['h'][t,l:r]):
     if h<5:continue
     full=independent(z,t,int(h),l,r);tr=raw_momentum(c[:,l:r],s[:,l:r],o[:,l:r],t,int(h));assert np.allclose(full,tr,equal_nan=True,atol=1e-12,rtol=0)
     prefixchecks+=1
 registry=read(HERE.parent/'algorithm-baselines-20261024/registry.json');root=HERE.parents[1]
 for p,d in registry['sha256'].items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==d
 write(HERE/'audit/h1-verification.json',dict(passed=True,prototype_latest_identity_rows=checks,independent_row_checks=rowchecks,physical_prefix_vectors=prefixchecks,old_algorithm_registry_files=len(registry['sha256']),source_accounts_run=0,calendar_start=str(ds[0].date()),stock_pool=1709,industry_pool=90))
 print(read(HERE/'audit/h1-verification.json'),flush=True)
if __name__=='__main__':main()

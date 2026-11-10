from common import *
from run import context,benchmark
import csv

def main():
 assert read(HERE/'technical/old-control-identity.json')['passed'];assert read(HERE/'technical/synthetic.json')['passed'];short=read(HERE/'technical/short-analysis/accounting.json');assert short['passed'] and short['accounts']==21;assert read(HERE/'technical/short-analysis/funding.json')['passed']
 prepared=read(PREP/'manifest.json');assert prepared['complete_old_indexes_equal'] and len(prepared['series'])==418;assert all(r['old_prefix_rows']>0 for r in prepared['series'])
 z=dict(np.load(PREP/'h1.npz'));dates=pd.DatetimeIndex(z['dates']);columns={str(s):j for j,s in enumerate(z['symbols'])};original=dict(np.load(OLD/'h1/matrix.npz'));np.testing.assert_array_equal(z['score'][:len(original['dates'])],original['score']);price_checks=0;score_checks=0
 for r in prepared['series']:
  sid=r['symbol'];f=pd.read_parquet(PREP/'signals'/f'{sid}.parquet');j=columns[sid]
  for day in ['2026-10-23','2026-10-26']:
   t=dates.get_loc(pd.Timestamp(day))
   if pd.Timestamp(day) in f.index:
    row=f.loc[day]
    if row.raw_volume>0 and np.isfinite(row.raw_volume):assert np.isclose(float(row.close),z['close'][t,j],rtol=1e-12,atol=1e-10),(sid,day,'H1 new source coordinate');price_checks+=1
 # Independent scalar target return + vector reference distribution; do not
 # invoke rs_h1_model.raw_momentum for this check.
 chosen=list(range(0,1709,73))+list(range(1709,1799,7))
 for day in ['2026-10-23','2026-10-26']:
  t=dates.get_loc(pd.Timestamp(day))
  for j in chosen:
   left,right=(0,1709) if j<1709 else (1709,1799);h=int(z['h'][t,j]);lo=np.minimum(np.arange(5)*63,h);values=[]
   for k in range(left,right):
    valid=np.isfinite(z['close'][t,k]) and z['close'][t,k]>0 and z['obs_count'][t,k]>=6 and h>=5;value=0.
    for a,w in enumerate([.4,.2,.2,.2],1):
     near,far=int(lo[a-1]),int(lo[a])
     if near==far:continue
     p,q=z['close'][t-near,k],z['close'][t-far,k]
     valid=valid and np.isfinite(p) and np.isfinite(q) and p>0 and q>0 and z['segment'][t-near,k]==z['segment'][t,k] and z['segment'][t-far,k]==z['segment'][t,k]
     value+=w*(p/q-1) if np.isfinite(p) and np.isfinite(q) and q>0 else 0
    values.append(np.round(value,12) if valid else np.nan)
   v=values[j-left];ref=np.array(values);ref=ref[np.isfinite(ref)];expected=100*((ref<v).sum()+.5*(ref==v).sum())/len(ref) if len(ref)>=20 and np.isfinite(v) else np.nan;actual=z['score'][t,j]
   assert np.isclose(expected,actual,rtol=0,atol=1e-10,equal_nan=True),(day,j,expected,actual);score_checks+=1
 b,m=context();ids=benchmark(b);meta=read(OLD/'inputs-v2/metadata.json');write(HERE/'benchmark.json',dict(frozen_before_economic=True,selection_cutoff='2023-12-29',stocks=[dict(symbol=s,name=meta[s]['name'],industry=meta[s]['industry']) for s in ids],not_selected_from_future_returns=True))
 write(HERE/'economic-admission.json',dict(passed=True,recorded_at=now(),paths=21,original_complete_prefix_rows=sum(r['old_prefix_rows'] for r in prepared['series']),old_control_rows=sum(r['daily_rows'] for r in read(HERE/'technical/old-control-identity.json')['receipts']),short_daily_rows=short['daily_rows'],new_tail_price_checks=price_checks,independent_new_H1_score_checks=score_checks,original_graphs_viewed=True,overlays_viewed=True,formula_revisions=0,new_economic_so_far=0))
 print(dict(admitted=True,paths=21,new_prices=price_checks,H1_scores=score_checks),flush=True)
if __name__=='__main__':main()

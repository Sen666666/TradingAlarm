"""Signal diagnostic only: next-close intervals, not executable portfolio returns."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from volume_units import split_consistent_volume
OUT=Path('results/trend-coverage-audit')
def main():
 OUT.mkdir(exist_ok=True)
 protocol={'universe':'ETF17/HK7 selected development assets','period':'2022-01-01 to 2026-10-16','model':'Frozen pairwise_volume, original entry/zero exit','interval':'Signal at previous observed close paired with next observed close log-return; diagnostic, not tradable open execution','exit_labels':'Forward 5 and 21 observed closes; only complete horizons before cutoff, both reported without selection','limits':['Repeated development sample; no independent validation.','Positive-return mass is hindsight decomposition, not attainable profit.','Exit forward gains do not prove holding was superior after costs/risk or establish a real trend label.']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 etf,_=load_extended();hk,_=load_assets();daily=[];events=[];prefix=0
 for group,assets in [('etf17',etf),('hk7',hk)]:
  for symbol,a in assets.items():
   valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);valid=valid[valid<=pd.Timestamp('2026-10-16')]
   c=a['signal'].close.reindex(valid);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(valid);s=pairwise_frame(c,v).strength;e=strength_exposure(s)
   cut=int(len(c)*.8);pd.testing.assert_series_equal(strength_exposure(s.iloc[:cut]),e.iloc[:cut]);prefix+=1
   r=np.log(c).diff();prior=e.shift(1);ready=s.shift(1).notna()&r.notna()
   f=pd.DataFrame(dict(log_return=r,held=prior,positive=r.clip(lower=0),negative=-r.clip(upper=0)))
   f=f.loc[ready&(f.index>=pd.Timestamp('2022-01-01'))];f['group']=group;f['symbol']=symbol;f['year']=f.index.year;f['date']=f.index
   f['positive_held']=f.positive*f.held;f['negative_held']=f.negative*f.held;daily.append(f)
   for i in np.flatnonzero(e.diff().lt(0).to_numpy()):
    if c.index[i]<pd.Timestamp('2022-01-01'):continue
    for h in [5,21]:
     if i+h>=len(c):continue
     future=c.iloc[i+1:i+h+1]/c.iloc[i]-1
     events.append(dict(group=group,symbol=symbol,date=str(c.index[i].date()),year=int(c.index[i].year),horizon=h,forward_return=float(future.iloc[-1]),best_close=float(future.max()),worst_close=float(future.min())))
 d=pd.concat(daily,ignore_index=True);d.to_parquet(OUT/'daily.parquet',index=False);ev=pd.DataFrame(events);ev.to_csv(OUT/'exit-events.csv',index=False)
 rows=[]
 for (g,y),f in d.groupby(['group','year']):
  p=f.positive.sum();n=f.negative.sum();ph=f.positive_held.sum();nh=f.negative_held.sum()
  assert abs((p-n)-f.log_return.sum())<1e-9
  assert abs((ph-nh)-(f.log_return*f.held).sum())<1e-9
  rows.append(dict(group=g,year=int(y),asset_bars=len(f),signal_occupancy=float(f.held.mean()),positive_mass_capture=float(ph/p),negative_mass_exposure=float(nh/n),held_log_sum=float(ph-nh),flat_log_sum=float(p-n-ph+nh)))
 exits=[]
 for (g,y,h),f in ev.groupby(['group','year','horizon']):
  exits.append(dict(group=g,year=int(y),horizon=int(h),count=len(f),mean_forward_return=float(f.forward_return.mean()),median_forward_return=float(f.forward_return.median()),positive_fraction=float(f.forward_return.gt(0).mean())))
 pd.DataFrame(rows).to_csv(OUT/'coverage-summary.csv',index=False);pd.DataFrame(exits).to_csv(OUT/'exit-summary.csv',index=False)
 report={'status':'diagnostic_complete_not_strategy_validation','prefix_checks':prefix,'daily_rows':len(d),'exit_horizon_rows':len(ev),'coverage':rows,'exit_followthrough':exits,'interpretation':'Low positive capture alone is not failure: compare negative exposure and occupied time. Forward outcomes are hindsight diagnostic labels, never fed into current trading signals.'}
 (OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(exits).query('year==2026').to_string(index=False))
if __name__=='__main__':main()

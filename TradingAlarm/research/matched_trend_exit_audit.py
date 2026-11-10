"""Fixed pairwise entry events, paired original/multiscale first-exit diagnostic."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from multiscale_trend_strength import multiscale_frame
from volume_units import split_consistent_volume
from geometric_strength import strength_exposure
OUT=Path('results/matched-trend-exit-audit')
def first_exit(score,i,h):
    # Entry on i is fixed; first permissible exit is a later observed close.
    for j in range(i+1,i+h+1):
        if np.isfinite(score.iloc[j]) and score.iloc[j]<=5:return j,False
    return i+h,True

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'entries':'Full-history original pairwise-volume flat-to-long events','exits':['original score<=5','existing equal-weight5/21/63 score<=5'],'horizons':[21,63],'parameters':'Frozen existing models; no selection or optimization','comparison':'Same entry close, first subsequent exit close or horizon end; no reentry. All complete horizons only. Signal study, no execution costs or shared account.','limits':['Entry while alternate score already negative is retained; exit earliest next bar; report such cases.','Independent episode experiments may overlap and exceed available capital.','Same-close fills not executable evidence; successful candidate would require next-open ledger.','Selected survivor development data and repeated hypothesis testing.']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 etf,_=load_extended();hk,_=load_assets();rows=[];prefix_checks=0
 for group,assets in [('etf17',etf),('hk7',hk)]:
  for symbol,a in assets.items():
   ix=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);ix=ix[ix<=pd.Timestamp('2026-10-16')]
   c=a['signal'].close.reindex(ix);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(ix)
   old=pairwise_frame(c,v).strength;new=multiscale_frame(c,v).strength;e=strength_exposure(old)
   k=len(c)//2;pd.testing.assert_series_equal(multiscale_frame(c.iloc[:k],v.iloc[:k]).strength,new.iloc[:k]);prefix_checks+=1
   for i in np.flatnonzero(e.diff().gt(0).to_numpy()):
    if ix[i]<pd.Timestamp('2022-01-01') or not np.isfinite(new.iloc[i]):continue
    for h in [21,63]:
     if i+h>=len(c):continue
     row=dict(group=group,symbol=symbol,date=str(ix[i].date()),year=int(ix[i].year),horizon=h,alternate_negative_at_entry=bool(new.iloc[i]<=5))
     for name,s in [('original',old),('multiscale',new)]:
      j,censored=first_exit(s,i,h);ret=float(c.iloc[j]/c.iloc[i]-1);peak=float(c.iloc[i:j+1].max()/c.iloc[i]-1)
      row.update({name+'_return':ret,name+'_bars':j-i,name+'_censored':censored,name+'_giveback':peak-ret,name+'_exit':str(ix[j].date())})
     row['difference']=row['multiscale_return']-row['original_return'];rows.append(row)
 f=pd.DataFrame(rows);f.to_csv(OUT/'paired-episodes.csv',index=False)
 summary=f.groupby(['group','year','horizon']).agg(n=('date','size'),original=('original_return','mean'),multiscale=('multiscale_return','mean'),difference=('difference','mean'),original_bars=('original_bars','mean'),multiscale_bars=('multiscale_bars','mean'),original_giveback=('original_giveback','mean'),multiscale_giveback=('multiscale_giveback','mean'),original_tail30=('original_return',lambda x:float(x.ge(.3).mean())),multiscale_tail30=('multiscale_return',lambda x:float(x.ge(.3).mean())),alternate_negative=('alternate_negative_at_entry','sum')).reset_index()
 summary.to_csv(OUT/'summary.csv',index=False)
 report={'status':'diagnostic_not_live_strategy','prefix_checks':prefix_checks,'paired_rows':len(f),'summary':summary.to_dict('records'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(OUT/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(summary.to_string(index=False))
if __name__=='__main__':main()

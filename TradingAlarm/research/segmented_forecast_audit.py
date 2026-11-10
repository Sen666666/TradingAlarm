"""Forward diagnostic of fixed slope estimators, not return-trained forecasts or trade rules."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from volume_units import split_consistent_volume
from segmented_trend_strength import segmented_frame
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
ROOT=Path(__file__).resolve().parent

def forward_labels(close,horizon):
    return np.log(close.shift(-horizon)/close)

def main():
    out=ROOT/'results/segmented-forecast-audit';out.mkdir(exist_ok=True)
    etf,_=load_extended();hk,_=load_assets();frames=[];fitrows=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            c=sig.close.reindex(valid);v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            models={'uniform':pairwise_frame(c,v,recency=False),'segmented_price':segmented_frame(c,v,joint=False),'segmented_volume':segmented_frame(c,v)}
            for model,f in models.items():
                strength=f.strength;exposure=strength_exposure(strength);entry=exposure.diff().gt(0)
                if 'knot' in f:
                    development=f.loc['2022-01-01':'2026-10-16'].dropna()
                    fitrows.append(dict(group=group,symbol=symbol,model=model,rows=len(development),knot_fraction=float(development.knot.ge(0).mean()),latest_allowed_knot_fraction=float(development.knot.eq(16).mean())))
                for h in [1,5,21]:
                    actual=forward_labels(c,h);prediction=h*f.velocity
                    r=pd.DataFrame(dict(actual=actual,prediction=prediction,entry=entry))
                    r=r.loc['2022-01-01':'2026-10-16'].dropna()
                    r['model']=model;r['group']=group;r['symbol']=symbol;r['horizon']=h;r['date']=r.index;r['year']=r.index.year
                    r['squared_error']=(r.prediction-r.actual)**2;r['rw_error']=r.actual**2
                    r['direction_correct']=(np.sign(r.prediction)==np.sign(r.actual)).astype(float)
                    frames.append(r.reset_index(drop=True))
        print(group,'computed',flush=True)
    f=pd.concat(frames,ignore_index=True);f.to_parquet(out/'forecasts.parquet',index=False)
    # Verify paired all-date model populations, preventing missing rows from changing comparisons.
    for (group,h),g in f.groupby(['group','horizon']):
        counts=g.groupby(['symbol','date']).model.nunique();assert counts.eq(3).all()
    summaries=[]
    for label,sub in [('all',f),('own_entry',f[f.entry])]:
        s=sub.groupby(['group','model','horizon']).agg(n=('actual','size'),error=('squared_error','sum'),rw=('rw_error','sum'),direction_accuracy=('direction_correct','mean'),mean_actual_log=('actual','mean')).reset_index()
        s['mse_ratio_to_nochange']=s.error/s.rw;s['subset']=label;summaries.append(s)
        annual=sub.groupby(['group','year','model','horizon']).agg(n=('actual','size'),error=('squared_error','sum'),rw=('rw_error','sum'),direction_accuracy=('direction_correct','mean'),mean_actual_log=('actual','mean')).reset_index();annual['mse_ratio_to_nochange']=annual.error/annual.rw;annual.to_csv(out/f'{label}-annual.csv',index=False)
    s=pd.concat(summaries,ignore_index=True);s.to_csv(out/'summary.csv',index=False);pd.DataFrame(fitrows).to_csv(out/'fit-structure.csv',index=False)
    (out/'validation.json').write_text(json.dumps(dict(rows=len(f),paired_all_date_populations=True,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['segmented_forecast_audit.py','segmented_trend_strength.py','pairwise_trend_strength.py']},limits=[
      'Forecast anchors at observed current logclose plus horizon times current fitted slope; no future intercept or refitting.',
      '1/5/21 observed-bar forward labels use future prices solely for evaluation; incomplete horizon rows excluded.',
      'Overlapping horizons and correlated instruments are not independent observations; no p-values or statistical significance claim.',
      'Own-entry subsets differ by model and cannot isolate causal estimator advantage. All-date populations are paired.',
      'Prediction MSE and directional accuracy are diagnostics, not equivalent to asymmetric trading utility or account return.',
      'SelectedETF17/HK7 previously inspected2022-2026development, not an untouched holdout.'
    ]),indent=2));print(s.to_string(index=False))
if __name__=='__main__':main()

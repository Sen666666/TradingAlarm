"""Fit frozen 2024 model; later years never enter preprocessing or fitting."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from trajectory_strength import features,path_target,fit,predict
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/trend-strength-v3'

def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    data=ROOT/'data/ths-refresh-20261018'
    manifest=json.loads((data/'validated-input-balanced-all500.json').read_text())
    frames=[]
    for rec in manifest['records']:
        p=data/f"{rec['ths_symbol']}-signal.parquet"
        assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['signal_sha256']
        f=pd.read_parquet(p);f=f[f.observed_bar & f.volume.gt(0)]
        x=features(f.signal_close,f.close,f.volume)
        dates=pd.Series(f.index,index=f.index)
        x['target']=path_target(f.signal_close).where(dates.shift(-21).dt.year.eq(dates.dt.year))
        for h in (5,21):
            x[f'forward{h}']=(f.signal_close.shift(-h)/f.signal_open.shift(-1)-1).where(dates.shift(-h).dt.year.eq(dates.dt.year))
        x['symbol']=rec['symbol'];x['date']=x.index;x['year']=x.index.year
        frames.append(x.loc['2024-01-01':])
    table=pd.concat(frames,ignore_index=True)
    featurecols=[c for c in table if c.startswith(('price_','activity_'))]
    table=table.dropna(subset=featurecols)
    train=table[table.year.eq(2024)].dropna(subset=['target'])
    weights=1/train.groupby('date').date.transform('size').to_numpy()
    models={};reports=[];observations=[]
    for name,cols in [('price_only',[c for c in featurecols if c.startswith('price_')]),('price_volume',featurecols)]:
        m=fit(train[cols],train.target,weights);m['columns']=cols;models[name]=m
        t=table[['symbol','date','year','target','forward5','forward21']].copy()
        t['prediction']=np.clip(predict(m,table[cols]),-1,1);t['strength']=5+5*t.prediction;t['model']=name
        t['bin']=pd.cut(t.strength,[0,2,4,6,8,10],include_lowest=True).astype(str)
        observations.append(t)
        for year,g in t.groupby('year'):
            valid=g.dropna(subset=['target']).copy()
            valid['mse']=(valid.prediction-valid.target)**2
            valid['baseline_mse']=(m['intercept']-valid.target)**2
            daily=valid.groupby('date')[['mse','baseline_mse']].mean()
            # Rank within date, preserving market-date dependence.
            ranks=valid.groupby('date')[['prediction','target']].rank()
            ranks['date']=valid.date
            correlations=[d.prediction.corr(d.target) for _,d in ranks.groupby('date')]
            bins=[]
            for b,part in valid.groupby('bin'):
                bins.append({'bin':b,'rows':len(part),'dates':part.date.nunique(),'target':float(part.groupby('date').target.mean().mean()),'forward21':float(part.groupby('date').forward21.mean().mean())})
            reports.append({'model':name,'year':int(year),'rows':len(valid),'dates':len(daily),'mse':float(daily.mse.mean()),'baseline_mse':float(daily.baseline_mse.mean()),'relative_mse_gain':float(1-daily.mse.mean()/daily.baseline_mse.mean()),'mean_daily_rank_correlation':float(np.nanmean(correlations)),'score_quantiles':g.strength.quantile([0,.01,.1,.5,.9,.99,1]).to_dict(),'bins':bins})
    (OUT/'frozen-models.json').write_text(json.dumps({'training_year':2024,'training_rows':len(train),'last_training_date':str(train.date.max()),'protocol_sha256':hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest(),'models':models},indent=2)+'\n')
    pd.concat(observations).to_parquet(OUT/'strength-observations.parquet',index=False)
    (OUT/'validation-report.json').write_text(json.dumps({'symbols':len(manifest['records']),'reports':reports,'interpretation':'Date-balanced descriptive evaluation; correlated observations, no significance claim. Training year not out-of-sample.'},indent=2)+'\n')
    for r in reports:print({k:v for k,v in r.items() if k not in ('bins','score_quantiles')},flush=True)
if __name__=='__main__':main()

"""Past-known evidence at zero-exit versus symmetric-exit disagreements."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from volume_units import split_consistent_volume
OUT=Path('results/trend-exit-disagreement')

def features(close,volume):
    r=np.log(close).diff();scale=r.pow(2).rolling(21,min_periods=21).mean().pow(.5)
    down=volume.where(r.lt(0),0.).rolling(5,min_periods=5).sum();total=volume.rolling(5,min_periods=5).sum()
    return pd.DataFrame(dict(fast5=r.rolling(5,min_periods=5).sum()/(np.sqrt(5)*scale),drawdown21=close/close.rolling(21,min_periods=21).max()-1,down_volume_share5=down/total,volume_ratio5_21=volume.rolling(5,min_periods=5).mean()/volume.shift(5).rolling(21,min_periods=21).mean()))

def forward_label(close,i):
    # Complete 21 observed-bar horizon, no across-year selection distortion.
    if i+21>=len(close):return None
    current=float(close.iloc[i]);future=close.iloc[i+1:i+22]
    return dict(forward21=float(future.iloc[-1]/current-1),mfe21=float(future.max()/current-1),mae21=float(future.min()/current-1),label_end=str(future.index[-1].date()))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(scope='ETF17/HK7 2022-2026Oct16 development; positivevolume observed bars',events='Originalpairwisevolume changeslongtoflat while symmetricpairwisevolume remainslong, one row per originalexit',features='Past5logreturn /sqrt5/past21RMS; drawdownfrompast21closehigh; last5down-dayvolumeshare; last5meanvolume/prior21meanvolume excludinglast5',outcomes='Next21observedclose return, maximum/minimum relative to eventclose; complete horizon only, not tradableexitcounterfactual',comparison='Featuremedian splits fixedwithin each market/year, descriptive outcomecontrast not chosen threshold; report everyfeature/year; no learned tradingrule',limits='Repeated overlapping events and survivoruniverse; futurelabels hindsight only; no claim to identify true trendturn in realtime')
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2))
    etf,_=load_extended();hk,_=load_assets();rows=[];cases=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        for symbol,a in assets.items():
            valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);c=a['signal'].close.reindex(valid);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(valid);s=pairwise_frame(c,v).strength;normal=strength_exposure(s);wide=strength_exposure(s,5-5*np.tanh(1));f=features(c,v)
            event=normal.diff().lt(0)&wide.eq(1)
            for i in np.flatnonzero(event.to_numpy()):
                date=c.index[i]
                if date<pd.Timestamp('2022-01-01') or date>pd.Timestamp('2026-10-16'):continue
                row=dict(group=group,symbol=symbol,date=str(date.date()),year=date.year,strength=float(s.iloc[i]),**f.iloc[i].to_dict());label=forward_label(c,i)
                if label is not None:rows.append(dict(row,**label))
                if symbol=='USHJ512480' and date.year==2026:cases.append(dict(row,label=label))
    data=pd.DataFrame(rows);data.to_parquet(OUT/'events.parquet',index=False);report=[]
    for (group,year),g in data.groupby(['group','year']):
        for feature in ['fast5','drawdown21','down_volume_share5','volume_ratio5_21']:
            cutoff=g[feature].median();low=g.loc[g[feature].le(cutoff)];high=g.loc[g[feature].gt(cutoff)]
            report.append(dict(group=group,year=int(year),feature=feature,n=len(g),low_count=len(low),high_count=len(high),median_cutoff=float(cutoff),low_forward21=float(low.forward21.mean()),high_forward21=float(high.forward21.mean()) if len(high) else None,high_minus_low=float(high.forward21.mean()-low.forward21.mean()) if len(high) else None))
    pd.DataFrame(report).to_csv(OUT/'feature-contrasts.csv',index=False);(OUT/'2026-cases.json').write_text(json.dumps(cases,indent=2));(OUT/'validation.json').write_text(json.dumps(dict(complete_events=len(data),assets=24,year_counts=data.groupby(['group','year']).size().reset_index(name='count').to_dict('records')),indent=2));print(pd.DataFrame(report).to_string(index=False));print(json.dumps(cases,indent=2))
if __name__=='__main__':main()

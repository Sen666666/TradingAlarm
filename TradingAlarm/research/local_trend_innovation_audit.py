"""Diagnostic of frozen trend-forecast displacement; future labels never signals."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from local_trend_strength import local_trend_frame
from volume_units import split_consistent_volume

OUT=Path('results/local-trend-innovation-audit')


def response_labels(logprice, forecast, prior_slope, scale, horizon):
    """Extrapolate the pre-observation trajectory without refitting it later."""
    innovation=logprice-forecast
    future=logprice.shift(-horizon)
    future_residual=future-(forecast+horizon*prior_slope)
    result=pd.DataFrame(dict(z=innovation/scale,retention=future_residual/innovation,
        normalized_future_residual=future_residual/scale,
        future_return=future-logprice,departure_from_drift=(future-logprice-horizon*prior_slope)/scale))
    # Retention is ill-conditioned for tiny innovations, so only predeclared |z|>=1.
    result['retention']=result.retention.where(result.z.abs().ge(1))
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(
        status='Frozen before outcomes',model='local_trend_volume, unchanged',
        horizons=[1,5,21],sample='all observed dates 2022-2026; horizon must end within same year and <=2026-10-16',
        bins='negative z<=-1; positive z>=1; no search',
        retention='future residual relative to PRE-observation trajectory / current innovation; fixed extrapolated prior slope',
        interpretation='0 means return to old trajectory; 1 means initial displacement persists relative to that trajectory. Not a trading return or proof of predictability.',
        limitations='Overlapping labels and correlated securities, no significance claims; all data development.'),indent=2))
    etf,_=load_extended();hk,_=load_assets();frames=[];cases=[];serial=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        for symbol,a in assets.items():
            raw=a['raw'];p=a['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index)
            p=p.reindex(valid);y=np.log(p);v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            f=local_trend_frame(p,v,True);prior_slope=f.velocity.shift().fillna(0)
            z=f.innovation/f.scale
            for year in range(2022,2027):
                zz=z.loc[str(year)].dropna()
                serial.append(dict(group=group,symbol=symbol,year=year,n=len(zz),lag1=float(zz.autocorr())))
            for h in (1,5,21):
                labels=response_labels(y,f.forecast,prior_slope,f.scale,h)
                end=pd.Series(p.index,index=p.index).shift(-h)
                keep=(end.dt.year==p.index.year)&(p.index>=pd.Timestamp('2022-01-01'))&(end<=pd.Timestamp('2026-10-16'))
                labels=labels.loc[keep].dropna();labels=labels.loc[labels.z.abs().ge(1)].copy()
                labels['group']=group;labels['symbol']=symbol;labels['year']=labels.index.year
                labels['side']=np.where(labels.z>0,'positive','negative');labels['horizon']=h;labels['date']=labels.index.astype(str)
                frames.append(labels)
                if symbol=='USHJ512480':
                    for d in ['2026-06-01','2026-06-15','2026-07-02','2026-07-09']:
                        if pd.Timestamp(d) in labels.index:cases.append(labels.loc[d].to_dict())
    frame=pd.concat(frames,ignore_index=True);frame.to_parquet(OUT/'labels.parquet')
    summary=frame.groupby(['group','year','side','horizon']).agg(n=('retention','size'),median_retention=('retention','median'),mean_retention=('retention','mean'),fraction_same_side=('retention',lambda x:float((x>0).mean())),mean_future_log_return=('future_return','mean'))
    summary.to_csv(OUT/'summary.csv');pd.DataFrame(serial).to_csv(OUT/'innovation-autocorrelation.csv',index=False)
    (OUT/'cases.json').write_text(json.dumps(cases,indent=2))
    print(summary.to_string());print(json.dumps(cases,indent=2))


if __name__=='__main__':main()

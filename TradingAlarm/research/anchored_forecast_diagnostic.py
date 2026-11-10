import json
from pathlib import Path
import numpy as np
import pandas as pd
from geometric_strength import fit_endpoint
from volume_units import split_consistent_volume
from trajectory_break_diagnostic import forecast_frame
OUT=Path('results/anchored-forecast-diagnostic')
def anchored_frame(price,volume):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.price.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)];rows=np.full((len(f),3),np.nan)
    for i in range(22,len(f)):
        past=y[i-21:i];vol=v[i-21:i];returns=r[i-21:i];scale=np.sqrt(np.mean(returns**2))
        if scale<=1e-12:continue
        slope,_=fit_endpoint(past,vol,degree=1)
        velocity,acceleration=fit_endpoint(past,vol,degree=2)
        rows[i]=(r[i]-np.array([slope,velocity+.5*acceleration,returns.mean()]))/scale
    return pd.DataFrame(rows,index=f.index,columns=['anchored_linear_z','anchored_quadratic_z','mean_drift_z'])
def main():
    from hk_extension import load_extended
    from hk_in_kind_campaign import load_assets
    a,_=load_extended();b,_=load_assets();frames=[]
    for symbol,asset in {**a,**b}.items():
        raw=asset['raw'];p=asset['signal'].close;valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(p.index)
        p=p.reindex(valid);v=split_consistent_volume(raw.volume,asset.get('splits',[])).reindex(valid)
        f=forecast_frame(p,v).join(anchored_frame(p,v)).loc['2024-01-01':'2026-10-16'];f['symbol']=symbol;frames.append(f)
    f=pd.concat(frames).rename_axis('date').reset_index();f.to_parquet(OUT/'daily.parquet',index=False);rows=[]
    for year,g in f.groupby(f.date.dt.year):
        cols=[c for c in g if c.endswith('_z')];g=g.dropna(subset=cols)
        for col in cols:
            errors=g.assign(squared=g[col]**2).groupby('date').squared.mean()
            correlations=[s[col].autocorr() for _,s in g.sort_values('date').groupby('symbol')]
            rows.append(dict(year=int(year),model=col,mean_squared_standardized_error=float(errors.mean()),median_symbol_lag1=float(np.nanmedian(correlations))))
    (OUT/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    case=f.loc[f.symbol.eq('USHJ512480')&(f.date.between('2026-05-25','2026-06-05')|f.date.between('2026-07-01','2026-07-10'))];case.to_csv(OUT/'semiconductor-case.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False));print(case[['date','anchored_linear_z','anchored_quadratic_z','mean_drift_z']].to_string(index=False))
if __name__=='__main__':main()

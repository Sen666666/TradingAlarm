"""Causal forecasts and separate retrospective evaluation; no trade rule changes."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from adaptive_geometric_strength import fit_experts,adaptive_frame
from geometric_strength import strength_exposure
from volume_units import split_consistent_volume
OUT=Path('results/trajectory-break-diagnostic')

def forecast_frame(price,volume):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.price.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)]
    rows=np.full((len(f),4),np.nan)
    for i in range(22,len(f)):
        _,pred=fit_experts(y[i-21:i],v[i-21:i])
        scale=np.sqrt(np.mean(r[i-21:i]**2))
        if scale>1e-12:rows[i,:3]=(y[i]-np.r_[pred,y[i-1]])/scale
        rows[i,3]=v[i]/np.median(v[i-21:i])
    return pd.DataFrame(rows,index=f.index,columns=['linear_z','quadratic_z','random_walk_z','volume_ratio'])

def main():
    from hk_extension import load_extended
    from hk_in_kind_campaign import load_assets
    a,_=load_extended();b,_=load_assets();assets={**a,**b};frames=[]
    for symbol,asset in assets.items():
        raw=asset['raw'];price=asset['signal'].close
        valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(price.index)
        p=price.reindex(valid);v=split_consistent_volume(raw.volume,asset.get('splits',[])).reindex(valid)
        f=forecast_frame(p,v)
        f['prior_held']=strength_exposure(adaptive_frame(p,raw.close.reindex(valid),v).strength).shift().fillna(0).astype(bool)
        # Forward labels belong only to evaluation, never forecast_frame.
        future=pd.concat([p.shift(-k)/p-1 for k in range(1,22)],axis=1)
        f['next21_return']=p.shift(-21)/p-1
        f['next21_min']=future.min(axis=1).where(future.notna().all(axis=1))
        f['next21_max']=future.max(axis=1).where(future.notna().all(axis=1))
        f['symbol']=symbol;f['year']=f.index.year;frames.append(f.loc['2024-01-01':'2026-10-16'])
    allf=pd.concat(frames).rename_axis('date').reset_index();allf.to_parquet(OUT/'daily.parquet',index=False)
    summaries=[]
    for year,g in allf.groupby('year'):
        g=g.dropna(subset=['next21_return'])
        for held in (False,True):
            selected=g.loc[g.prior_held] if held else g
            for model in ('linear','quadratic','random_walk'):
                for surprise in (False,True):
                    q=selected.loc[selected[model+'_z'].lt(-2)] if surprise else selected
                    summaries.append(dict(year=int(year),prior_held_only=held,model=model,surprise_only=surprise,n=len(q),symbols=int(q.symbol.nunique()),mean_return=float(q.next21_return.mean()),median_return=float(q.next21_return.median()),positive_fraction=float(q.next21_return.gt(0).mean()),mean_min=float(q.next21_min.mean()),mean_max=float(q.next21_max.mean())))
    cases=allf.loc[allf.symbol.eq('USHJ512480') & (allf.date.between('2026-05-25','2026-06-05')|allf.date.between('2026-07-01','2026-07-10'))]
    cases.to_csv(OUT/'semiconductor-case.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps({'asset_count':len(assets),'rows':summaries,'limits':'Conditional descriptive results; overlapping dates/events and selected survivorship-biased universe. Dates are development evidence, not blind validation. Forward labels cannot be used to classify a live reversal.'},indent=2)+'\n')
    print(cases[['date','linear_z','quadratic_z','random_walk_z','volume_ratio','next21_return']].to_string(index=False))
    for s in summaries:
        if s['prior_held_only'] and s['surprise_only']:print(s)
if __name__=='__main__':main()

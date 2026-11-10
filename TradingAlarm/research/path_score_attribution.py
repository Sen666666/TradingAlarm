import json
from pathlib import Path
import numpy as np
import pandas as pd
from path_efficiency_strength import path_efficiency_frame
from geometric_strength import strength_exposure
from volume_units import split_consistent_volume
OUT=Path('results/path-score-attribution')

def decompose(price,baseline):
    y=np.log(price);r=y.diff();sigma=np.sqrt(r.pow(2).rolling(21).mean()).replace(0,np.nan);distance=y-baseline
    z=distance/sigma
    f=pd.DataFrame({'z':z,'delta_z':z.diff(),'price_component':r/sigma,'baseline_component':-baseline.diff()/sigma,'normalization_component':distance.shift()*(1/sigma-1/sigma.shift()),'old_scale_z':distance/sigma.shift(),'price_return':price.pct_change(fill_method=None),'baseline_delta':baseline.diff()})
    residual=f.delta_z-f[['price_component','baseline_component','normalization_component']].sum(axis=1,min_count=3)
    if len(residual.dropna()):assert residual.abs().max()<1e-9
    return f

def main():
    from hk_extension import load_extended
    from hk_in_kind_campaign import load_assets
    a,_=load_extended();b,_=load_assets();rows=[];cases=[]
    for symbol,asset in {**a,**b}.items():
        raw=asset['raw'];p=asset['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index);p=p.reindex(valid);v=split_consistent_volume(raw.volume,asset.get('splits',[])).reindex(valid)
        for name,joint,fixed in [('fixed',False,True),('price',False,False),('volume',True,False)]:
            f=path_efficiency_frame(p,v,joint,fixed);d=decompose(p,f.log_baseline);d['strength']=f.strength;d['alpha']=f.alpha;d['entry']=strength_exposure(f.strength).diff().eq(1);d['symbol']=symbol;d['model']=name
            e=d.loc['2022-01-01':'2026-10-16'];e=e.loc[e.entry].dropna(subset=['delta_z']);rows.append(e)
            if symbol=='USHJ512480':cases.append(d.loc['2026-07-01':'2026-07-10'])
    t=pd.concat(rows).rename_axis('date').reset_index();t.to_parquet(OUT/'entries.parquet',index=False);pd.concat(cases).rename_axis('date').reset_index().to_csv(OUT/'july-case.csv',index=False);reports=[]
    for name,g in t.groupby('model'):
        cols=['price_component','baseline_component','normalization_component'];r=dict(model=name,entries=len(g),positive_price=int(g.price_component.gt(0).sum()),positive_baseline=int(g.baseline_component.gt(0).sum()),positive_normalization=int(g.normalization_component.gt(0).sum()),normalization_sensitive_crossings=int(g.old_scale_z.lt(1).sum()),dominant_positive_component=g[cols].idxmax(axis=1).value_counts().to_dict(),median_components=g[cols].median().to_dict());reports.append(r);print(r)
    (OUT/'summary.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(t.loc[t.symbol.eq('USHJ512480')&t.date.between('2026-07-01','2026-07-10'),['date','model','z','price_component','baseline_component','normalization_component','old_scale_z']].to_string(index=False))
if __name__=='__main__':main()

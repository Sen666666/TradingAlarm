import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from adaptive_geometric_strength import adaptive_frame
from anchored_trend_strength import anchored_strength_frame
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/strength-path-discrimination')

def path_labels(f,h):
    entry=f.signal_open.shift(-1)
    highs=pd.concat([f.signal_high.shift(-k) for k in range(1,h+1)],axis=1)
    lows=pd.concat([f.signal_low.shift(-k) for k in range(1,h+1)],axis=1)
    dates=pd.Series(f.index,index=f.index)
    valid=highs.notna().all(axis=1)&lows.notna().all(axis=1)&dates.shift(-h).dt.year.eq(dates.dt.year)&entry.gt(0)
    up=(highs.max(axis=1)/entry-1).clip(lower=0);down=(1-lows.min(axis=1)/entry).clip(lower=0)
    asym=(up-down)/(up+down).replace(0,np.nan);asym=asym.mask((up+down).eq(0),0)
    return pd.DataFrame({f'asym{h}':asym.where(valid),f'return{h}':(f.signal_close.shift(-h)/entry-1).where(valid)})

def main():
    root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());frames=[]
    for n,r in enumerate(manifest['records']):
        p=root/(r['ths_symbol']+'-signal.parquet');rp=root/'rights'/(r['ths_symbol']+'.json')
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];assert hashlib.sha256(rp.read_bytes()).hexdigest()==r['rights_sha256']
        raw=pd.read_parquet(p);vol=ths_split_consistent_volume(raw.volume,json.loads(rp.read_text()));f=raw.loc[raw.observed_bar&raw.volume.gt(0)]
        v=vol.reindex(f.index);ret=np.log(f.signal_close).diff();rms=np.sqrt(ret.pow(2).rolling(21).mean())
        scores=pd.DataFrame({'adaptive':adaptive_frame(f.signal_close,f.close,v).strength,'anchored_neutral':anchored_strength_frame(f.signal_close,v,True).strength,'momentum21':5+5*np.tanh(np.sqrt(21)*ret.rolling(21).mean()/rms.replace(0,np.nan))})
        for h in (5,21,63):scores=scores.join(path_labels(f,h))
        scores['symbol']=r['symbol'];frames.append(scores.loc['2024-01-01':'2026-10-16'])
        if (n+1)%100==0:print('symbols',n+1,flush=True)
    t=pd.concat(frames).rename_axis('date').reset_index();t.to_parquet(OUT/'observations.parquet',index=False);daily=[]
    for h in (5,21,63):
        cols=['adaptive','anchored_neutral','momentum21'];valid=t.dropna(subset=[*cols,f'asym{h}',f'return{h}'])
        for date,g in valid.groupby('date'):
            if len(g)<20:continue
            for model in cols:
                rank=g[model].rank(pct=True);hi=g.loc[rank.gt(.8)];lo=g.loc[rank.le(.2)]
                if not len(hi) or not len(lo):continue
                ic=g[model].rank().corr(g[f'asym{h}'].rank())
                daily.append(dict(date=date,year=date.year,model=model,horizon=h,n=len(g),rank_ic=ic,asymmetry_spread=float(hi[f'asym{h}'].mean()-lo[f'asym{h}'].mean()),return_spread=float(hi[f'return{h}'].mean()-lo[f'return{h}'].mean())))
    d=pd.DataFrame(daily);d.to_parquet(OUT/'daily-comparisons.parquet',index=False)
    s=d.groupby(['year','model','horizon']).agg(dates=('date','size'),mean_rank_ic=('rank_ic','mean'),mean_asymmetry_spread=('asymmetry_spread','mean'),mean_return_spread=('return_spread','mean')).reset_index()
    (OUT/'summary.json').write_text(s.to_json(orient='records',indent=2)+'\n');print(s.to_string(index=False))
if __name__=='__main__':main()

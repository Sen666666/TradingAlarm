import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from anchored_trend_strength import anchored_strength_frame
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/anchored-score-decomposition')

def decompose(score,neutral_weight):
    if not np.isfinite(score) or not np.isfinite(neutral_weight) or not 0<=neutral_weight<1:raise ValueError('finite score and nondegenerate trend mass required')
    if not 0<score<10:raise ValueError('saturated score cannot be inverted exactly')
    weighted=np.arctanh((score-5)/5);conditional=weighted/(1-neutral_weight)
    reconstructed=5+5*np.tanh(conditional*(1-neutral_weight))
    assert abs(reconstructed-score)<1e-12
    category=('nonpositive_direction' if conditional<=0 else 'direction_below_entry' if conditional<1 else 'neutral_attenuation' if weighted<1 else 'actual_score_above_entry')
    return dict(weighted_velocity=weighted,conditional_velocity=conditional,conditional_strength=5+5*np.tanh(conditional),category=category)

def main():
    root=Path('data/ths-refresh-20261018');m=json.loads((root/'validated-input-balanced-second500.json').read_text());ref=pd.read_parquet('results/strength-anchored-transfer485/episodes.parquet');ref=ref.loc[ref.cutoff.eq('2026-10-16')&ref.delay.eq(0)&ref.strategy.eq('adaptive_geometry_price_volume_split_units')&ref.status.eq('closed')];rows=[]
    for n,r in enumerate(m['records']):
        path=root/(r['ths_symbol']+'-signal.parquet');rp=root/'rights'/(r['ths_symbol']+'.json')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==r['signal_sha256'];assert hashlib.sha256(rp.read_bytes()).hexdigest()==r['rights_sha256']
        f=pd.read_parquet(path);v=ths_split_consistent_volume(f.volume,json.loads(rp.read_text()));o=f.loc[f.observed_bar&f.volume.gt(0)]
        scores=anchored_strength_frame(o.signal_close,v.reindex(o.index),True)
        for e in ref.loc[ref.symbol.eq(r['symbol'])].itertuples():
            d=pd.Timestamp(e.signal_date);s=scores.loc[d];ret=e.return15
            rows.append(dict(symbol=e.symbol,date=e.signal_date,year=d.year,reference_return=ret,stratum='loss' if ret<=0 else 'tail' if ret>=.3 else 'ordinary_profit',neutral_weight=s.neutral_weight,actual_strength=s.strength,**decompose(s.strength,s.neutral_weight)))
        if (n+1)%100==0:print('symbols',n+1,flush=True)
    t=pd.DataFrame(rows);assert len(t)==len(ref)==7108;t.to_parquet(OUT/'entry-components.parquet',index=False);summary=[]
    for label,g in t.groupby('stratum'):
        z=dict(stratum=label,n=len(g),categories=g.category.value_counts().to_dict(),median_neutral_weight=float(g.neutral_weight.median()),median_actual_strength=float(g.actual_strength.median()),median_conditional_strength=float(g.conditional_strength.median()));summary.append(z);print(z)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    annual=[dict(year=int(y),stratum=s,n=len(g),categories=g.category.value_counts().to_dict()) for (y,s),g in t.groupby(['year','stratum'])];(OUT/'annual.json').write_text(json.dumps(annual,indent=2)+'\n')
if __name__=='__main__':main()

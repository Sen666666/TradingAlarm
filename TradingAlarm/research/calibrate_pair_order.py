"""Freeze one pooled order-balance threshold using pre2022 score occupancy only."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from pair_order_strength import order_frame
from volume_units import split_consistent_volume
OUT=Path('results/strength-calibrated-order')
def calibration(pair,order):
    f=pd.concat([pair.rename('pair'),order.rename('order')],axis=1).dropna()
    occupancy=float(f.pair.ge(5+5*np.tanh(1)).mean())
    q=float(f.order.quantile(1-occupancy,interpolation='higher'))
    if not 0<q<=1:raise ValueError('Invalid frozen threshold')
    return dict(threshold=q,baseline_occupancy=occupancy,order_occupancy=float(f.order.ge(q).mean()),observations=len(f))
def main():
    etf,_=load_extended();hk,_=load_assets();frames=[];coverage=[]
    for symbol,a in {**etf,**hk}.items():
        raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
        v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid);c=sig.close.reindex(valid)
        f=pd.DataFrame(dict(pair=pairwise_frame(c,v).strength,order=order_frame(c,v).balance)).loc['2020-01-01':'2021-12-31'].dropna()
        assert len(f)>100,(symbol,len(f))
        coverage.append(dict(symbol=symbol,n=len(f),first=str(f.index.min().date()),last=str(f.index.max().date())))
        f['symbol']=symbol;frames.append(f)
    f=pd.concat(frames);r=calibration(f.pair.reset_index(drop=True),f.order.reset_index(drop=True));r['coverage']=coverage
    f.to_parquet(OUT/'training-score-pairs.parquet');(OUT/'calibration.json').write_text(json.dumps(r,indent=2));print(r['threshold'],r['baseline_occupancy'],r['order_occupancy'])
if __name__=='__main__':main()

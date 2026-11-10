import json,argparse
from pathlib import Path
import numpy as np,pandas as pd
from run_pv_segment_round import assets,volume,manifest,write

def main(out):
    groups,_=assets();rows=[];bad=[]
    for group,items in groups.items():
        for s,a in items.items():
            r=a['raw'];f=a['signal'];v=volume(a);pos=r[['open','high','low','close']].gt(0).all(axis=1)&np.isfinite(r[['open','high','low','close']]).all(axis=1);geometry=(r.high+1e-8>=r[['open','close']].max(axis=1))&(r.low-1e-8<=r[['open','close']].min(axis=1))&(r.high+1e-8>=r.low);good=pos&geometry&v.gt(0)&np.isfinite(v);bad.extend(dict(symbol=s,date=str(t.date()),positive=bool(pos.loc[t]),geometry=bool(geometry.loc[t]),volume=float(v.loc[t])) for t in r.index[~good]);ratio=f[['open','high','low','close']]/r[['open','high','low','close']];spread=(ratio.max(axis=1)-ratio.min(axis=1)).abs()
            rows.append(dict(group=group,symbol=s,rows=len(r),eligible=int(good.sum()),ohlc_invalid=int((~pos|~geometry).sum()),zero_or_invalid_volume=int((~v.gt(0)|~np.isfinite(v)).sum()),range_zero=int(r.high.eq(r.low).sum()),signal_same_bar_factor_maxdiff=float(spread.max()),start=str(r.index[0].date()),end=str(r.index[-1].date())))
    write(out/'data-audit.json',dict(assets=rows,ohlc_source='Existing source OHLC parsed by loaders; signal columns share same daily price adjustment factor. Not independent market verification.',intraday_features='Use raw same-bar log(C/O),log(H/L),close location; invariant to common daily adjustment. Close-to-close background/outcomes from existing total-return signal. Invalid geometry excluded, no synthetic OHLC replacement.',bad_rows=bad));manifest(out,'audit');print(rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)

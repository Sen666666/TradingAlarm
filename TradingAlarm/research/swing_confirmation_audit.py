import json
from pathlib import Path
import numpy as np
import pandas as pd
from swing_structure_strength import swing_frame
from geometric_strength import strength_exposure
OUT=Path('results/swing-confirmation-audit')
def main():
    from hk_extension import load_extended
    from hk_in_kind_campaign import load_assets
    a,_=load_extended();b,_=load_assets();rows=[]
    for symbol,asset in {**a,**b}.items():
        raw=asset['raw'];sig=asset['signal'];valid=raw.index[raw.volume.gt(0)].intersection(sig.index);sig=sig.reindex(valid).loc[:'2026-10-16'];p=sig.close
        f,events=swing_frame(p);state=strength_exposure(f.strength);entries=state.diff().eq(1);lookup={pd.Timestamp(e['confirmation_date']):e for e in events}
        ret=p.pct_change(fill_method=None);future=p.shift(-21)/sig.open.shift(-1)-1
        for date in entries.loc['2022-01-01':].index[entries.loc['2022-01-01':]]:
            event=lookup.get(date);kind=event['kind'] if event else 'none';lag=valid.get_loc(date)-valid.get_loc(pd.Timestamp(event['pivot_date'])) if event else None
            rows.append(dict(symbol=symbol,date=str(date.date()),year=date.year,kind=kind,confirmation_lag=lag,current_return=float(ret.loc[date]),strength=float(f.strength.loc[date]),forward21=float(future.loc[date]) if pd.notna(future.loc[date]) else None))
    t=pd.DataFrame(rows);t.to_parquet(OUT/'entries.parquet',index=False);summary=[]
    for kind,g in t.groupby('kind'):
        h=g.dropna(subset=['forward21']);summary.append(dict(kind=kind,entries=len(g),negative_current=int(g.current_return.lt(0).sum()),median_current_return=float(g.current_return.median()),median_confirmation_lag=float(g.confirmation_lag.median()) if g.confirmation_lag.notna().any() else None,mature_outcomes=len(h),mean_forward21=float(h.forward21.mean()),median_forward21=float(h.forward21.median())))
    annual=[dict(year=int(y),kind=k,entries=len(g),negative_current=int(g.current_return.lt(0).sum())) for (y,k),g in t.groupby(['year','kind'])]
    (OUT/'summary.json').write_text(json.dumps({'categories':summary,'annual':annual},indent=2)+'\n');print(json.dumps(summary,indent=2));print('total',len(t),'negative',int(t.current_return.lt(0).sum()))
if __name__=='__main__':main()

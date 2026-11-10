import json
from pathlib import Path
import numpy as np
import pandas as pd
from swing_structure_strength import swing_frame
from geometric_strength import strength_exposure
OUT=Path('results/swing-reset-audit')
def prior_anchor_score(previous,current_logprice,scale):
    h,l=previous.high_change,previous.low_change;z=0.
    if np.isfinite(h+l):
        if h>0 and l>0:z=min(h,l,current_logprice-previous.view_low)/scale
        elif h<0 and l<0:z=max(h,l,current_logprice-previous.view_high)/scale
    return 5+5*np.tanh(z)

def main():
    from hk_extension import load_extended
    from hk_in_kind_campaign import load_assets
    a,_=load_extended();b,_=load_assets();rows=[]
    for symbol,asset in {**a,**b}.items():
        raw=asset['raw'];sig=asset['signal'];ix=raw.index[raw.volume.gt(0)].intersection(sig.index);sig=sig.reindex(ix).loc[:'2026-10-16'];p=sig.close
        f,events=swing_frame(p,True,True);plain,_=swing_frame(p,True);pd.testing.assert_frame_equal(plain,f[plain.columns],check_exact=True)
        lookup={pd.Timestamp(e['confirmation_date']):e['kind'] for e in events};exits=strength_exposure(f.strength).diff().eq(-1);future=p.shift(-21)/sig.open.shift(-1)-1
        for date in exits.loc['2022-01-01':].index[exits.loc['2022-01-01':]]:
            n=f.index.get_loc(date);prev=f.iloc[n-1];cur=f.iloc[n];counter=prior_anchor_score(prev,np.log(p.loc[date]),cur.scale)
            rows.append(dict(symbol=symbol,date=str(date.date()),event=lookup.get(date,'none'),price_return=float(p.iloc[n]/p.iloc[n-1]-1),actual_strength=float(cur.strength),prior_anchor_strength=float(counter),anchor_revision_needed=bool(counter>5),forward21=float(future.loc[date]) if pd.notna(future.loc[date]) else None))
    t=pd.DataFrame(rows);t.to_parquet(OUT/'exits.parquet',index=False);reports=[]
    for (event,needed),g in t.groupby(['event','anchor_revision_needed']):
        h=g.dropna(subset=['forward21']);r=dict(event=event,anchor_revision_needed=bool(needed),exits=len(g),positive_price_days=int(g.price_return.gt(0).sum()),mature=len(h),mean_forward21=float(h.forward21.mean()),median_forward21=float(h.forward21.median()));reports.append(r);print(r)
    (OUT/'summary.json').write_text(json.dumps(reports,indent=2)+'\n');print(t.loc[t.symbol.eq('USHJ512480')&t.date.between('2026-05-01','2026-07-31')].to_string(index=False))
if __name__=='__main__':main()

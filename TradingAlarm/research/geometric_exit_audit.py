"""Hindsight exit diagnosis, never used as a filter or counterfactual profit."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from geometric_strength import geometric_frame,strength_exposure
ROOT=Path(__file__).resolve().parent

def linear_velocity(y,v=None):
    y=np.asarray(y,float);x=np.arange(1-len(y),1,dtype=float);w=np.exp2(x/5)
    if v is not None:w*=np.clip(np.sqrt(np.asarray(v)/np.median(v)),.25,4)
    xbar=np.average(x,weights=w);ybar=np.average(y,weights=w)
    return float(np.sum(w*(x-xbar)*(y-ybar))/np.sum(w*(x-xbar)**2))

def future_window(frame,exit_date,h):
    # Exit at open; include that day's close as first future observation.
    i=frame.index.get_indexer([pd.Timestamp(exit_date)])[0]
    if i<0 or i+h>len(frame):return None
    window=frame.iloc[i:i+h]
    if window.index[-1].year!=pd.Timestamp(exit_date).year:return None
    return window

def main():
    out=ROOT/'results/trend-strength-v4-trades';data=ROOT/'data/ths-refresh-20261018'
    manifest=json.loads((data/'validated-input-balanced-all500.json').read_text())
    t=pd.read_parquet(out/'episodes.parquet');t=t[t.cutoff.eq('2026-10-16')&t.delay.eq(0)&t.status.eq('closed')]
    rows=[]
    for n,r in enumerate(manifest['records']):
        p=data/f"{r['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256']
        f=pd.read_parquet(p);f=f[f.observed_bar&f.volume.gt(0)]
        for strategy,joint in [('geometry_price',False),('geometry_price_volume',True)]:
            g=geometric_frame(f.signal_close,f.close,f.volume,joint)
            exposure=strength_exposure(g.strength)
            exits=exposure.index[exposure.diff().eq(-1)]
            for e in t[t.symbol.eq(r['symbol'])&t.strategy.eq(strategy)].itertuples():
                eligible=exits[(exits>=pd.Timestamp(e.entry_date))&(exits<pd.Timestamp(e.exit_date))]
                assert len(eligible), (e.symbol,e.entry_date,e.exit_date)
                trigger=eligible[-1];i=f.index.get_loc(trigger);past=f.iloc[i-20:i+1]
                slope=linear_velocity(np.log(past.signal_close),past.volume if joint else None)
                row={'symbol':e.symbol,'strategy':strategy,'exit_date':e.exit_date,'trigger_date':str(trigger.date()),'year':pd.Timestamp(e.exit_date).year,'trade_return':e.return15,'endpoint_velocity':float(g.loc[trigger,'velocity']),'linear_velocity':slope,'linear_still_positive':slope>0}
                assert row['endpoint_velocity']<=1e-12
                for h in (5,21):
                    w=future_window(f,e.exit_date,h)
                    row[f'forward{h}']=float(w.signal_close.iloc[-1]/e.exit_price-1) if w is not None else None
                    row[f'strong_again{h}']=bool(g.loc[w.index,'strength'].ge(5+5*np.tanh(1)).any()) if w is not None else None
                rows.append(row)
        if (n+1)%100==0:print('exit audit symbols',n+1,flush=True)
    a=pd.DataFrame(rows);a.to_parquet(out/'exit-path-audit.parquet',index=False);reports=[]
    for (strategy,year,positive),g in a.groupby(['strategy','year','linear_still_positive']):
        for h in (5,21):
            valid=g.dropna(subset=[f'forward{h}']);daily=valid.groupby('exit_date')[f'forward{h}'].mean()
            reports.append({'strategy':strategy,'year':int(year),'linear_still_positive':bool(positive),'horizon':h,'exits':len(g),'valid_labels':len(valid),'dates':len(daily),'date_balanced_forward_mean':float(daily.mean()),'date_balanced_positive_fraction':float(valid.assign(up=valid[f'forward{h}'].gt(0)).groupby('exit_date').up.mean().mean()),'strong_again_fraction':float(valid[f'strong_again{h}'].mean())})
    summary=[]
    for strategy,g in a.groupby('strategy'):
        summary.append({'strategy':strategy,'exits':len(g),'linear_still_positive':int(g.linear_still_positive.sum()),'fraction':float(g.linear_still_positive.mean())})
    (out/'exit-path-audit.json').write_text(json.dumps({'summary':summary,'reports':reports,'meaning':'Frozen exits audited; signal-date slopes use past data only. Future closes and recovered scores are hindsight diagnostics, no executable hold-through return or causal benefit claim. Exclude labels across year/end boundaries. Event-level recovery frequency, date-balanced forward returns; correlated observations, no significance assertion.'},indent=2)+'\n')
    print(summary)
if __name__=='__main__':main()

"""Fixed entry cohort attribution. No new strategy or hindsight trading signals."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from volume_units import split_consistent_volume
from geometric_strength import strength_exposure
OUT=Path('results/trend-entry-horizon-attribution')
def decompose(close,exposure,i,h):
    log_returns=np.diff(np.log(np.asarray(close.iloc[i:i+h+1],float)))
    state=np.asarray(exposure.iloc[i:i+h],float)
    assert len(log_returns)==h and len(state)==h
    held=float(log_returns@state);flat=float(log_returns@(1-state));total=float(np.log(close.iloc[i+h]/close.iloc[i]))
    assert abs(held+flat-total)<1e-12
    return dict(total_log=total,held_log=held,flat_log=flat,hold_return=float(np.expm1(total)),signal_return=float(np.expm1(held)),held_fraction=float(state.mean()))
def main():
 OUT.mkdir(exist_ok=True)
 protocol={'source':'Original pairwise volume strength; same 24 ETF/HK assets','entry':'Original strength_exposure full-history 0-to-1 transition; initial state is not inferred as an entry','horizons':[21,63],'execution':'Diagnostic signal-close to subsequent-close returns, no costs, no cash budget or open execution; not ledger backtest','decomposition':'Include any later reentry within horizon; held log+flat log=buy-hold log for exact same entry cohort','limits':['All data development; overlapping observations not independent.','All high-score dates overrepresent persistent episodes compared with entry events.','Cannot infer optimal horizon from these retrospective comparisons.','Score8-10 bin is not identical to actual entry threshold about8.808.']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 etf,_=load_extended();hk,_=load_assets();rows=[];bridge=0
 labels=pd.read_parquet('results/trend-tail-distribution/labeled.parquet')
 for group,assets in [('etf17',etf),('hk7',hk)]:
  for symbol,a in assets.items():
   ix=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);ix=ix[ix<=pd.Timestamp('2026-10-16')]
   c=a['signal'].close.reindex(ix);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(ix);s=pairwise_frame(c,v).strength;e=strength_exposure(s);entry=e.diff().gt(0)
   for h in [21,63]:
    old=labels.loc[labels.symbol.eq(symbol)&labels.horizon.eq(h)].set_index('date')
    np.testing.assert_allclose(old['return'],(c.shift(-h)/c-1).reindex(old.index),rtol=0,atol=0);bridge+=1
    for i in np.flatnonzero(entry.to_numpy()):
     if c.index[i]<pd.Timestamp('2022-01-01') or i+h>=len(c):continue
     rows.append(dict(group=group,symbol=symbol,date=str(c.index[i].date()),year=int(c.index[i].year),horizon=h,strength=float(s.iloc[i]),**decompose(c,e,i,h)))
 f=pd.DataFrame(rows);f.to_csv(OUT/'entry-cohorts.csv',index=False)
 summary=f.groupby(['group','year','horizon']).agg(entries=('date','size'),hold_mean=('hold_return','mean'),signal_mean=('signal_return','mean'),flat_mean_log=('flat_log','mean'),held_fraction=('held_fraction','mean'),hold_tail30=('hold_return',lambda x:float(x.ge(.3).mean())),signal_tail30=('signal_return',lambda x:float(x.ge(.3).mean()))).reset_index()
 summary['signal_minus_hold']=summary.signal_mean-summary.hold_mean;summary.to_csv(OUT/'summary.csv',index=False)
 report={'status':'diagnostic_only','exact_label_bridges':bridge,'entry_horizon_rows':len(f),'summary':summary.to_dict('records'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(OUT/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(summary.to_string(index=False))
if __name__=='__main__':main()

"""Fixed calendar snapshots of causal campaign records; future exits never price an open trade."""
import json
import math
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT,grouped

OUT=ROOT/'results/a-stock-cutoff-audit'


def snapshot(records,history,cutoff):
    cutoff=pd.Timestamp(cutoff);hist=history[history.date.le(cutoff)]
    valid=hist[hist.observed_bar & hist.positive_volume]
    rows=[]
    for r in records:
        if pd.Timestamp(r['entry_date'])>cutoff:continue
        exit_date=r.get('exit_date')
        closed=pd.notna(exit_date) and pd.Timestamp(exit_date)<=cutoff
        if closed:
            price=r['exit_price'];status='closed';mark_date=exit_date
        else:
            if valid.empty:raise ValueError('No observed mark for an entered campaign')
            last=valid.iloc[-1];price=last.signal_close;mark_date=str(pd.Timestamp(last.date).date())
            status='open_at_cutoff' if pd.Timestamp(last.date)==cutoff else 'stale_unknown'
        out=dict(symbol=r['symbol'],source=r['source'],cutoff=str(cutoff.date()),entry_date=r['entry_date'],status=status,mark_date=mark_date)
        for cost in [15,30]:
            fee=(r['entry_price']+(price if closed else 0))*cost/10000
            out[f'R_cost{cost}']=(price-r['entry_price']-fee)/r['risk_distance']
            out[f'R_zero_terminal_cost{cost}']=(-r['entry_price']*(1+cost/10000))/r['risk_distance']
        rows.append(out)
    return rows


def main(source=ROOT/'results/a-stock-campaign-signals',output=OUT):
    output.mkdir(exist_ok=True)
    records=pd.read_parquet(source/'campaigns.parquet')
    inputs=ROOT/'data/stock-features';file=pq.ParquetFile(inputs/'local-features.parquet')
    dates=set()
    for b in file.iter_batches(columns=['date']):dates.update(pd.to_datetime(b.column(0).to_pandas()))
    dates=pd.DatetimeIndex(sorted(dates));dates=dates[dates.year>=2022]
    cutoffs=[g.max() for _,g in pd.Series(dates,index=dates).groupby(dates.year)]
    protocol=dict(cutoffs=[str(x.date()) for x in cutoffs],start='2022-01-01',
        method='Replay stored causal campaign entry/exit intervals,mark open positions only using observed positive-volume close on/before cutoff. Futureexitprices ignored.',
        missing='Stale marks excluded from primary mean,reported separately with zero-terminal-value sensitivity. No assumed delisting proceeds.',
        limitations='Overlapping cumulative histories,not independent tests. Provider-revised syntheticadjustedprices,not raw cash/share account or certified PITuniverse. No cutoffselection.')
    f=output/'protocol.json'
    if f.exists():assert json.loads(f.read_text())==protocol
    f.write_text(json.dumps(protocol,indent=2));lookup={n:g.to_dict('records') for n,g in records.groupby('symbol')};rows=[]
    for name in ['local-features.parquet','ths-retired-features.parquet']:
        for symbol,h in grouped(pq.ParquetFile(inputs/name),['symbol','date','signal_close','observed_bar','positive_volume']):
            if symbol not in lookup:continue
            for cutoff in cutoffs:rows.extend(snapshot(lookup[symbol],h,cutoff))
    frame=pd.DataFrame(rows);frame.to_parquet(output/'snapshots.parquet',index=False);summary=[]
    for cutoff,g in frame.groupby('cutoff'):
        for cost in [15,30]:
            known=g[g.status.ne('stale_unknown')];v=known[f'R_cost{cost}'];tail=v.nlargest(max(1,math.ceil(len(v)*.1)));stale=g[g.status.eq('stale_unknown')]
            summary.append(dict(cutoff=cutoff,cost_bps=cost,closed=int(g.status.eq('closed').sum()),open=int(g.status.eq('open_at_cutoff').sum()),stale_unknown=len(stale),marked_mean_R=float(v.mean()),top10_R=float(tail.sum()),ordinary_R=float(v.drop(tail.index).sum()),zero_terminal_sensitivity_mean_R=float((v.sum()+stale[f'R_zero_terminal_cost{cost}'].sum())/len(g))))
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    # The final snapshot must reproduce the previous diagnostic, without future price use.
    for cost in [15,30]:
        expected=float(records.loc[records.status.ne('terminal_unknown'),f'R_cost{cost}'].mean())
        actual=next(x['marked_mean_R'] for x in summary if x['cutoff']==str(cutoffs[-1].date()) and x['cost_bps']==cost)
        assert np.isclose(expected,actual,atol=1e-12)
    for x in summary:print(x,flush=True)


if __name__=='__main__':main()

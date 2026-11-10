"""Frozen daily-exit comparator; exact controls checked for all symbols."""
from a_stock_monthly252 import analyze_symbol,COLS
import json,math
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT,SOURCE,grouped
from ths_signal_adjustment import signal_frame
OUT=ROOT/'results/a-stock-monthly252-daily-exit'

def main():
    old=ROOT/'results/a-stock-monthly252'
    controls={s:g for s,g in pd.read_parquet(old/'episodes.parquet').groupby('symbol')}
    checked=0
    def candidate(symbol,f,raw,opens,calendar,cutoffs,source):
        nonlocal checked
        baseline=pd.DataFrame([dict(r,source=source) for r in analyze_symbol(symbol,f,raw,opens,calendar,cutoffs)])
        expected=controls.get(symbol)
        if expected is None:assert baseline.empty
        else:
            keys=['cutoff','scenario','entry_date']
            baseline=baseline.astype(expected.dtypes.to_dict())
            pd.testing.assert_frame_equal(baseline.sort_values(keys).reset_index(drop=True),expected.sort_values(keys).reset_index(drop=True),check_exact=True)
        checked+=1
        return analyze_symbol(symbol,f,raw,opens,calendar,cutoffs,daily_exit=True)
    protocol=json.loads((OUT/'protocol.json').read_text());cutoffs=[pd.Timestamp(x) for x in protocol['cutoffs']]
    paths=ROOT/'data/stock-features';pf=pq.ParquetFile(paths/'local-features.parquet');dates=set()
    for b in pf.iter_batches(columns=['date']):dates.update(pd.to_datetime(b.column(0).to_pandas()))
    calendar=pd.DatetimeIndex(sorted(d for d in dates if d<=max(cutoffs)))
    assert all(c in calendar for c in cutoffs)
    it=iter(grouped(pq.ParquetFile(SOURCE),['symbol','trade_date','open','high','low','close','reference_adjustment_factor']))
    s,current=next(it);records=[];rows=[]
    for symbol,f in grouped(pf,COLS):
        while s<symbol:s,current=next(it)
        assert s==symbol;raw=current.set_index('trade_date')
        check=(raw.close*raw.reference_adjustment_factor).reindex(pd.DatetimeIndex(f.date));obs=f.observed_bar.to_numpy()
        assert np.allclose(check.to_numpy()[obs],f.signal_close.to_numpy()[obs],rtol=1e-10,atol=1e-8)
        rr=candidate(symbol,f,raw,raw.open*raw.reference_adjustment_factor,calendar,cutoffs,'local')
        rows.extend(dict(r,source='local') for r in rr);records.append(symbol)
        if len(records)%500==0:print('symbols',len(records),flush=True)
    local_count=len(records)
    for symbol,f in grouped(pq.ParquetFile(paths/'ths-retired-features.parquet'),COLS):
        code,market=symbol.split('.');name=('USHD' if market=='SH' else 'USZD')+code+'.json'
        raw=signal_frame(json.loads((ROOT/'data/ths-raw'/name).read_text()),json.loads((ROOT/'data/ths-rights'/name).read_text()))
        check=raw.signal_close.reindex(pd.DatetimeIndex(f.date));obs=f.observed_bar.to_numpy()
        assert np.allclose(check.to_numpy()[obs],f.signal_close.to_numpy()[obs],rtol=1e-10,atol=1e-8)
        rr=candidate(symbol,f,raw,raw.signal_open,calendar,cutoffs,'ths_retired')
        rows.extend(dict(r,source='ths_retired') for r in rr);records.append(symbol)
    assert len(records)==len(set(records))==5426 and local_count==5204
    assert checked==5426
    table=pd.DataFrame(rows);table.to_parquet(OUT/'episodes.parquet',index=False)
    (OUT/'coverage.json').write_text(json.dumps(dict(symbols=len(records),local=local_count,retired=len(records)-local_count,records=records),indent=2))
    summaries=[]
    for (cutoff,scenario),g in table.groupby(['cutoff','scenario']):
        for cost in (15,30):
            closed=g[g.status.eq('closed')];v=closed[f'return{cost}'].sort_values();n=math.ceil(len(v)*.1)
            known=g[~g.status.eq('terminal_unknown')][f'return{cost}'];terminal=g[g.status.eq('terminal_unknown')]
            summaries.append(dict(cutoff=cutoff,scenario=scenario,cost=cost,counts=g.status.value_counts().to_dict(),closed_win_rate=float(v.gt(0).mean()),closed_mean=float(v.mean()),closed_ordinary_bottom90_mean=float(v.iloc[:-n].mean()),closed_average_win=float(v[v>0].mean()),closed_average_loss=float(v[v<0].mean()),known_marked_mean=float(known.mean()),terminal_lastmark_mean=float(terminal[f'return{cost}'].mean()) if len(terminal) else None,all_mean_terminal_zero_stress=float((known.sum()-len(terminal))/len(g))))
    (OUT/'summary.json').write_text(json.dumps(summaries,indent=2));print(json.dumps(summaries[-6:],indent=2),flush=True)


if __name__=='__main__':main()

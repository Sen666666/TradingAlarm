"""Broad synthetic-price monthly trend episodes, no portfolio account claims."""
import json
import math
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT,SOURCE,grouped
from ths_signal_adjustment import signal_frame

OUT=ROOT/'results/a-stock-monthly252'
COLS=['symbol','date','signal_close','observed_bar','positive_volume']


def simulate(dates,opens,closes,scores,active,execute,cutoffs,symbol,delay=0,daily_exit=False,cadence='monthly',start='2022-01-01'):
    if cadence not in ('monthly','daily'):raise ValueError('unknown cadence')
    rows=[];snapshots={};state=None;pending=None;month=None;last_mark=None;last_price=None
    cutoffset=set(cutoffs)
    for i,day in enumerate(dates):
        if active[i] and np.isfinite(closes[i]):last_mark=day;last_price=float(closes[i])
        if day<pd.Timestamp(start):continue
        if cadence=='daily':
            target=bool(scores[i-1]) if i else False
            if pending is not None and pending['target']==target:pass
            else:pending=dict(target=target,wait=delay,signal_date=str(dates[i-1].date())) if target!=(state is not None) else None
        elif month!=day.to_period('M'):
            month=day.to_period('M');target=bool(scores[i-1]) if i else False
            if not (daily_exit and pending is not None and not pending['target']):
                pending=dict(target=target,wait=delay,signal_date=str(dates[i-1].date())) if target!=(state is not None) else None
        if daily_exit and state is not None and i and not scores[i-1] and (pending is None or pending['target']):
            pending=dict(target=False,wait=delay,signal_date=str(dates[i-1].date()))
        if pending is not None and active[i] and execute[i] and np.isfinite(opens[i]) and opens[i]>0:
            if pending['wait']:pending['wait']-=1
            else:
                if pending['target']:
                    state=dict(symbol=symbol,entry_date=str(day.date()),signal_date=pending['signal_date'],entry_price=float(opens[i]))
                else:
                    rows.append(dict(state,exit_date=str(day.date()),mark_date=str(day.date()),exit_price=float(opens[i]),status='closed'));state=None
                pending=None
        if day in cutoffset:
            snapshot=[dict(r) for r in rows]
            if state is not None:
                assert last_mark is not None
                snapshot.append(dict(state,exit_date=None,mark_date=str(last_mark.date()),exit_price=last_price,status='open_at_cutoff' if last_mark==day else 'terminal_unknown'))
            snapshots[str(day.date())]=snapshot
    return snapshots


def analyze_symbol(symbol,f,raw,opens,calendar,cutoffs,daily_exit=False):
    f=f.set_index('date').sort_index();observed=f.observed_bar & f.signal_close.notna()
    series=f.loc[observed,'signal_close'];score=series.pct_change(252,fill_method=None).gt(0)
    signals=score.reindex(calendar,method='ffill').fillna(False).to_numpy(dtype=bool)
    close=f.signal_close.reindex(calendar).to_numpy();op=opens.reindex(calendar).to_numpy()
    active=(f.observed_bar & f.positive_volume).reindex(calendar,fill_value=False).to_numpy(dtype=bool)
    zero=pd.Series(~np.isclose(raw.high,raw.low,rtol=1e-10,atol=1e-10),index=raw.index).reindex(calendar,fill_value=False).to_numpy(dtype=bool)
    allrows=[]
    for label,mask,delay in [('base',np.ones(len(calendar),dtype=bool),0),('zero_range',zero,0),('delay1',zero,1)]:
        snaps=simulate(calendar,op,close,signals,active,mask,cutoffs,symbol,delay,daily_exit=daily_exit)
        for cutoff,rows in snaps.items():
            for r in rows:
                for cost in (15,30):
                    r[f'return{cost}']=(r['exit_price']*(1-cost/10000) if r['status']=='closed' else r['exit_price'])/(r['entry_price']*(1+cost/10000))-1
                allrows.append(dict(r,cutoff=cutoff,scenario=label))
    return allrows


def main():
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
        rr=analyze_symbol(symbol,f,raw,raw.open*raw.reference_adjustment_factor,calendar,cutoffs)
        rows.extend(dict(r,source='local') for r in rr);records.append(symbol)
        if len(records)%500==0:print('symbols',len(records),flush=True)
    local_count=len(records)
    for symbol,f in grouped(pq.ParquetFile(paths/'ths-retired-features.parquet'),COLS):
        code,market=symbol.split('.');name=('USHD' if market=='SH' else 'USZD')+code+'.json'
        raw=signal_frame(json.loads((ROOT/'data/ths-raw'/name).read_text()),json.loads((ROOT/'data/ths-rights'/name).read_text()))
        check=raw.signal_close.reindex(pd.DatetimeIndex(f.date));obs=f.observed_bar.to_numpy()
        assert np.allclose(check.to_numpy()[obs],f.signal_close.to_numpy()[obs],rtol=1e-10,atol=1e-8)
        rr=analyze_symbol(symbol,f,raw,raw.signal_open,calendar,cutoffs)
        rows.extend(dict(r,source='ths_retired') for r in rr);records.append(symbol)
    assert len(records)==len(set(records))==5426 and local_count==5204
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

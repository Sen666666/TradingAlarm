"""Resumable bounded THS refresh; separate snapshots, never overwrite canonical input."""
import argparse,json,signal,sys,time,hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import fetch_history as history
import fetch_ths_rights as rights
from build_stock_features import ROOT
from ths_signal_adjustment import signal_frame
sys.path.insert(0,str(history.APP))
from search import SearchClient
from sessions import SessionManager,DEFAULT_PREFERENCES
OUT=ROOT/'data/ths-refresh-20261018';OUT.mkdir(exist_ok=True)
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
history.OUT=OUT;rights.OUT=OUT/'rights';rights.OUT.mkdir(exist_ok=True)


def board(symbol):
    if symbol.startswith(('688','689')):return 'SH_STAR'
    if symbol.endswith('.SH'):return 'SH_MAIN'
    if symbol.startswith(('300','301')):return 'SZ_CHINEXT'
    return 'SZ_MAIN'


def balanced_order(symbols):
    """Return-blind deterministic order, interleaved across code-based boards."""
    buckets=defaultdict(list)
    for s in symbols:buckets[board(s)].append(s)
    for values in buckets.values():values.sort(key=lambda s:hashlib.sha256(('ths-refresh-v1:'+s).encode()).hexdigest())
    return [buckets[k][i] for i in range(max(map(len,buckets.values()),default=0)) for k in sorted(buckets) if i<len(buckets[k])]


def main(limit,budget,selection='balanced'):
    target=OUT/'batch-checkpoint.json';saved=json.loads(target.read_text()) if target.exists() else {'records':{}}
    records=saved['records'];coverage=json.loads((ROOT/'results/a-stock-monthly252/coverage.json').read_text())
    universe=coverage['records'][:coverage['local']]
    remaining=[s for s in universe if s not in records]
    selected=(balanced_order(remaining) if selection=='balanced' else remaining)[:limit]
    source=pq.read_table(SOURCE,columns=['symbol','trade_date','open','high','low','close'],filters=[('symbol','in',selected),('trade_date','>=',pd.Timestamp('2026-01-01'))]).to_pandas()
    groups={s:g.set_index('trade_date') for s,g in source.groupby('symbol')}
    manager=SessionManager(history.APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
    client=SearchClient(manager);started=time.monotonic()
    def save():
        saved.update(records=records,universe_count=len(universe),elapsed_last_batch=round(time.monotonic()-started,3),selection_last_batch=selection,scope='Read-only THS snapshots;rawOHLCoverlap andinwindowactionparsing gate only,notcertifiedfull corporateactions/accountdata.')
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(saved,indent=2));temp.replace(target)
    def timeout(*_):raise TimeoutError('bounded batch finished')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(budget)
    try:
        for symbol in selected:
            if time.monotonic()-started>budget-5:break
            stage='identifier'
            try:
                code=symbol.split('.')[0];market='USHA' if symbol.endswith('.SH') else 'USZA'
                matches=[x for x in client.search(code) if x.get('code')==code and x.get('market')==market]
                if len(matches)!=1:raise ValueError('identifier')
                ths=matches[0]['symbol'];stage='history';h=history.fetch(ths,'20261016','2026-01-01',1,'raw')
                stage='actions';actions=rights.fetch_rights(ths)
                raw=pd.DataFrame(h['bars']);raw['date']=pd.to_datetime(raw.date);raw=raw.set_index('date')
                stage='overlap';old=groups.get(symbol,pd.DataFrame());common=old.index.intersection(raw.index)
                if len(common)<20:raise ValueError('insufficient_overlap')
                diff=(old.loc[common,['open','high','low','close']]-raw.loc[common,['open','high','low','close']]).abs()
                if diff.to_numpy().max()>1e-6:raise ValueError('OHLC_mismatch')
                if raw.index.duplicated().any() or not((raw.low>0)&(raw.low<=raw[['open','close']].min(axis=1))&(raw.high>=raw[['open','close']].max(axis=1))).all():raise ValueError('invalid_OHLC')
                stage='signal_actions';frame=signal_frame(h,actions,start='2023-01-01');frame.to_parquet(OUT/f'{ths}-signal.parquet')
                records[symbol]=dict(status='signal_window_checked',ths_symbol=ths,overlap=len(common),last=str(raw.index.max().date()),rows2026=int((raw.index>=pd.Timestamp('2026-01-01')).sum()),new_rows=int((raw.index>pd.Timestamp('2026-05-15')).sum()),actions_complete_certified=False)
            except Exception as exc:
                records[symbol]=dict(status='quarantined',stage=stage,error_type=type(exc).__name__)
                if isinstance(exc,TimeoutError):save();break
            save();print(symbol,records[symbol]['status'],flush=True);time.sleep(.2)
    finally:signal.alarm(0);save()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=50);parser.add_argument('--budget',type=int,default=120);parser.add_argument('--selection',choices=['balanced','original'],default='balanced');a=parser.parse_args();main(a.limit,a.budget,a.selection)

"""Bounded pure-market runner. Imports no account/trade/sizing engine."""
from pathlib import Path
import argparse,json,hashlib,time,traceback
from collections import Counter
import numpy as np
import pandas as pd
import engine

HERE=Path(__file__).resolve().parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CAP='2026-06-30'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def code_freeze():return {str(p):sha(p) for p in [HERE/'engine.py',HERE/'runner.py',HERE/'FREEZE.md',MANIFEST]}
def version_for(code):return 'CHANNEL_N3_V1:'+engine.key(code)[:24]
def frame(path):
    f=pd.read_parquet(path)
    ix=pd.DatetimeIndex(pd.to_datetime(f.index))
    if ix.tz is not None:ix=ix.tz_localize(None)
    f.index=ix.as_unit('ns').normalize()
    if not f.index.is_unique or not f.index.is_monotonic_increasing:raise ValueError('nonunique/unordered original daily index')
    return f.loc[:CAP]
def period_mask(index,periods):
    mask=np.zeros(len(index),dtype=bool)
    for start,end in periods:mask|=(index>=pd.Timestamp(start))&(index<=pd.Timestamp(end))
    return mask
def period_label(day,periods):return next((start+'__'+end for start,end in periods if start<=day<=end),None)
def read_symbol(meta):
    pp=Path(next(p for p in meta['source_sha256'] if p.endswith('/signal.parquet')))
    ep=Path(next(p for p in meta['source_sha256'] if p.endswith('/events.parquet')))
    paths={'price':pp,'events':ep,**{k:Path(meta['refs'][k]) for k in ['facts','CP1','CP1_input']}}
    sources={}
    for label,path in paths.items():
        expected=meta['source_sha256'].get(str(path),meta['output_sha256'].get(str(path)))
        if expected is None:raise ValueError('source binding absent: '+str(path))
        actual=sha(path)
        if actual!=expected:raise ValueError('source SHA mismatch: '+str(path))
        sources[str(path)]=actual
    data={label:frame(path) for label,path in paths.items()}
    if not data['CP1'].index.equals(data['CP1_input'].index):raise ValueError('original CP/input indexes differ after uniform June30 cut')
    q=data['CP1_input'];p=data['price'].reindex(q.index)
    if not np.array_equal(q.close.to_numpy(),p.close.to_numpy(),equal_nan=True):raise ValueError('CP/input price-domain mismatch')
    return data,sources


def run_symbol(meta,periods,outdir,version,code):
    sid=meta['symbol'];outdir.mkdir(exist_ok=False)
    if meta.get('status')!='complete':
        report=dict(sid=sid,status='NOT_APPLICABLE_OR_NO_SOURCE',original_manifest_status=meta.get('status'),
                    periods=[dict(start=a,end=b,observations=0,raw_CP_anchors=0) for a,b in periods])
        save(outdir/'COVERAGE.json',report);return report
    d,sources=read_symbol(meta);price=d['price'];events=d['events'];cp=d['CP1'];native=d['facts']
    features=engine.features(price)
    main=engine.market_fsm(sid,price,events,version,features)
    display=period_mask(price.index,periods);daily=main['daily'].iloc[np.flatnonzero(display)].copy()
    daily['window']=[period_label(day,periods) for day in daily.day]
    daily.to_parquet(outdir/'MARKET_DAILY.parquet')
    event_rows=[dict(e,window=period_label(e['day'],periods)) for e in main['events'] if period_label(e['day'],periods)]
    ids=set(daily.generation_id.dropna())
    generation_rows=[g for g in main['generations'] if g['generation_id'] in ids or period_label(g['start_day'],periods)]
    save(outdir/'MARKET_EVENTS.json',event_rows);save(outdir/'MARKET_GENERATIONS.json',generation_rows)
    c=cp.reindex(price.index);raw=np.array([engine.flag(x) is True for x in engine.col(c,'receipt')])
    anchor_mask=raw&display
    pairs=engine.protection_pairs(sid,price,features,native,cp,anchor_mask,version)
    for row in pairs:row['window']=period_label(row['anchor_day'],periods)
    # Keep a raw CP mother-row even if its original price observation is missing.
    cp_display=cp.iloc[np.flatnonzero(period_mask(cp.index,periods))]
    orphan=[str(t.date()) for t in cp_display.index if engine.flag(cp_display.at[t,'receipt']) is True and t not in price.index]
    for day in orphan:pairs.append(dict(sid=sid,anchor_day=day,status='RAW_CP_DATE_MISSING_SOURCE',window=period_label(day,periods),CP=None,ATR3=None))
    raw_count=sum(engine.flag(x) is True for x in cp_display.receipt)
    assert len(pairs)==raw_count
    save(outdir/'CP_ANCHOR_PAIRS.json',pairs)
    counts=[]
    for start,end in periods:
        pm=(daily.day>=start)&(daily.day<=end);cr=cp.loc[start:end]
        counts.append(dict(start=start,end=end,observations=int(pm.sum()),raw_CP_anchors=sum(engine.flag(x) is True for x in cr.receipt),
                           channel_seen=int(daily.loc[pm,'CHANNEL_seen'].sum()),channel_advance=int(daily.loc[pm,'CHANNEL_advance'].sum()),
                           main_exit_events=int(daily.loc[pm,'exit_event_count'].sum())))
    report=dict(sid=sid,status='COMPLETE',original_manifest_status=meta.get('status'),source_sha256=sources,
                original_price_rows=len(price),original_CP_rows=len(cp),original_native_rows=len(native),
                source_last_day=None if price.empty else str(price.index[-1].date()),
                original_CP_last_day=None if cp.empty else str(cp.index[-1].date()),
                source_rows_without_CP=len(price.index.difference(cp.index)),
                current_unknown_sideflag_rows=int((~features.sideflags_known).sum()),periods=counts,
                raw_CP_anchors=raw_count,pair_status_counts=dict(Counter(x['status'] for x in pairs)),
                full_calendar_missing_sessions='NOT_VERIFIED',historical_halt_limit_ST_orderbook_receive='UNKNOWN_NOT_RESTORED',
                native_I_used_by_main=False,native_I_used_by_pair=True,new_accounts=0,new_quantities=0,new_returns=0)
    save(outdir/'COVERAGE.json',report)
    save(outdir/'SOURCE_FREEZE.json',dict(version=version,code_sha256=code,source_sha256=sources,physical_tail_cut=CAP))
    return report


def run_symbols(symbols,periods,outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=False)
    code=code_freeze();version=version_for(code)
    metas={r['symbol']:r for r in json.loads(MANIFEST.read_text())};reports=[];errors=[];started=time.monotonic()
    for number,sid in enumerate(symbols):
        try:
            if sid not in metas:raise KeyError('symbol not in frozen manifest: '+sid)
            result=run_symbol(metas[sid],periods,outdir/sid.replace('.','_'),version,code);reports.append(result)
        except Exception as error:
            item=dict(sid=sid,status='ERROR',error=repr(error),traceback=traceback.format_exc());errors.append(item)
            save(outdir/(sid.replace('.','_')+'_ERROR.json'),item)
            print(json.dumps(dict(sid=sid,status='ERROR',error=repr(error))),flush=True)
        if (number+1)%25==0:print(json.dumps(dict(completed=number+1,total=len(symbols),errors=len(errors),elapsed=time.monotonic()-started)),flush=True)
    assert code==code_freeze(),'runtime code/freeze changed; preserve outputs and stop release'
    save(outdir/'COVERAGE_ALL_SYMBOLS.json',reports);save(outdir/'ERRORS.json',errors)
    save(outdir/'RUN_RECEIPT.json',dict(status='COMPLETE' if not errors else 'PARTIAL_ERROR',version=version,code_sha256=code,
        symbols_requested=len(symbols),symbols_completed=sum(r['status']=='COMPLETE' for r in reports),
        symbols_not_applicable=sum(r['status']!='COMPLETE' for r in reports),errors=len(errors),periods=periods,
        display_observations=sum(sum(p['observations'] for p in r['periods']) for r in reports),
        raw_CP_anchors=sum(r.get('raw_CP_anchors',0) for r in reports),new_accounts=0,new_quantities=0,new_returns=0,
        elapsed_seconds=time.monotonic()-started,full_calendar_gap_check='NOT_VERIFIED'))
    return dict(reports=reports,errors=errors,version=version)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--symbols-json',type=Path,required=True)
    p.add_argument('--period',nargs=2,action='append',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();symbols=json.loads(a.symbols_json.read_text())
    if not isinstance(symbols,list) or not all(isinstance(x,str) for x in symbols):raise SystemExit('symbols-json must be a list of symbol strings')
    result=run_symbols(symbols,a.period,a.out)
    raise SystemExit(bool(result['errors']))

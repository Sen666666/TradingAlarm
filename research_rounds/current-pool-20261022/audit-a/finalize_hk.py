"""Offline HK raw observation fusion; missing volume never deletes valid prices.

Reuses the A collector's evidence integrity checks, not its A volume assumptions
or distribution parser. No network or account code is imported.
"""
from __future__ import annotations
import argparse,collections,csv,datetime,hashlib,importlib.util,json,shutil
from pathlib import Path
import numpy as np
import pandas as pd
from finalize_a import digest,read_json,verify_attempt,verify_history,boundary_status,safe_child,discover_history_batches,history_source_order,source_dispositions
from prepare_a import FORMAL,FIELDS,write_csv,write_json

OLD=FORMAL/'TradingAlarm/research/data/ths-index-history-9603-20261018'
FROZEN_HELPER=FORMAL/'research_rounds/pv-participation-response-20261020/code/data_utils.py'


def backup_old(out):
    out.mkdir(parents=True,exist_ok=False);manifest=[]
    canonical=sorted((OLD/'canonical').glob('UHKM*.csv'))
    if len(canonical)!=7:raise ValueError('Expected exactly the seven prior HK equity canonical sources')
    files=[OLD/'protocol.json',OLD/'integrity.json']
    for p in canonical:
        files.extend([p,OLD/'checkpoints'/(p.stem+'.json')]);files.extend(sorted((OLD/'raw'/p.stem).glob('*')))
    for p in files:
        if not p.is_file():continue
        target=out/p.relative_to(OLD);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        manifest.append(dict(source=str(p),copy=str(target.resolve()),sha256=digest(p),bytes=p.stat().st_size))
    write_json(out/'manifest.json',dict(source=str(OLD),canonical_securities=7,files=manifest,network_requests=0,
                note='Exact prior source bytes; not a new quality certification. Raw price, original wire volume/amount; no adjustment conversion.'))
    return len(manifest)


def raw_observations(path):
    x,cp,item,seen=verify_history(path);batch=path.parent.parent;records={}
    for page in cp['pages']:
        attempt=safe_child(batch,page['attempt'])
        for row in read_json(attempt/'decoded.json'):records[str(row['1'])]=row
    rows=[]
    for day in sorted(records):
        r=records[day];rows.append(dict(trade_date=f'{day[:4]}-{day[4:6]}-{day[6:]}',**{k:r.get(f) for k,f in
            [('open','7'),('high','8'),('low','9'),('close','11'),('volume','13'),('amount','19')]}))
    return pd.DataFrame(rows,columns=['trade_date']+FIELDS),x,cp,item,seen


def legacy_source(backup,native):
    path=backup/'canonical'/(native+'.csv');cp=read_json(backup/'checkpoints'/(native+'.json'))
    if cp['symbol']!=native or cp['status']!='complete' or cp['overlap_conflicts']:
        raise ValueError('Legacy source status/identity conflict')
    if digest(path)!=cp['canonical_sha256']:raise ValueError('Legacy canonical hash mismatch')
    for page in cp['pages']:
        raw=safe_child(backup,page['file'])
        if digest(raw)!=page['body_sha256'] or raw.stat().st_size!=page['body_bytes']:
            raise ValueError('Legacy raw page hash mismatch')
    if cp['rows_dropped_by_parser']:
        raise ValueError('Legacy source has unrecovered parser drops')
    frame=pd.read_csv(path,float_precision='round_trip')
    if len(frame)!=cp['rows']:raise ValueError('Legacy canonical count mismatch')
    return frame,dict(path=str(path.resolve()),sha256=digest(path),legacy=True,accepted=True,
        history_status='complete',stop_reason='short_raw_page_source_boundary' if cp['stop_reason']=='short_page_history_start' else cp['stop_reason'],
        requested_end=cp['end_requested'],first=cp['first'],last=cp['last'],rows=cp['rows'],parser_dropped_recovered=0,
        observed_at=cp['completed_at'],reason='legacy_canonical_and_all_raw_page_hashes_verified')


def normalize_hk(frame,symbol,path,seen='',currency='HKD'):
    out=frame.copy().rename(columns={'date':'trade_date'})
    out['trade_date']=pd.to_datetime(out.trade_date,errors='raise')
    if out.trade_date.isna().any() or out.trade_date.duplicated().any():raise ValueError('Missing or duplicate source date')
    for k in FIELDS:out[k]=pd.to_numeric(out[k],errors='coerce')
    out['symbol']=symbol;out['source_kind']='ths_raw';out['source_path']=str(path)
    out['observed_at']=seen;out['observed_bar']=True;out['is_observed_bar']=True;out['synthetic_event_bar']=False
    finite=np.isfinite(out[FIELDS[:4]]).all(axis=1)&out[FIELDS[:4]].gt(0).all(axis=1)
    geom=out.high.ge(out.low)&out.high.ge(out[['open','close']].max(axis=1))&out.low.le(out[['open','close']].min(axis=1))
    out['price_eligible']=finite&geom
    out['volume_eligible']=np.isfinite(out.volume)&out.volume.gt(0)
    out['source_invalid']=~out.price_eligible
    out['quality_status']=np.select([~finite,~geom,~np.isfinite(out.volume),out.volume.lt(0),out.volume.eq(0)],
        ['missing_or_nonpositive_price','invalid_price_geometry','volume_missing_price_preserved','negative_volume_price_preserved','zero_volume_price_preserved'],default='valid_price_and_positive_volume')
    out['volume_unit']='source_wire_units_unscaled';out['amount_unit']=currency+'_source_wire_units_unscaled'
    out['currency']=currency;out['price_adjustment']='raw'
    return out[['symbol','trade_date']+FIELDS+[c for c in out if c not in ['symbol','trade_date']+FIELDS+['wire_extra']]].sort_values('trade_date').reset_index(drop=True)


def merge_hk(base,extra,symbol):
    if base is None:return extra.copy(),[],dict(accepted=True,reason='first_available_source',overlap=0)
    a=base.set_index('trade_date');b=extra.set_index('trade_date');common=a.index.intersection(b.index);conflicts=[]
    for k in FIELDS:
        av=a.loc[common,k].to_numpy();bv=b.loc[common,k].to_numpy()
        atol,rtol=(1e-6,0) if k in FIELDS[:4] else (1.,1e-6)
        mismatch=~np.isclose(av,bv,atol=atol,rtol=rtol,equal_nan=True)
        for d,v,w in zip(common[mismatch],av[mismatch],bv[mismatch]):
            conflicts.append(dict(symbol=symbol,date=str(d.date()),field=k,old=float(v),new=float(w),old_source=a.at[d,'source_path'],new_source=b.at[d,'source_path']))
    if conflicts:return base.copy(),conflicts,dict(accepted=False,reason='overlap_conflict',overlap=len(common))
    if not len(common):return base.copy(),[],dict(accepted=False,reason='no_overlap_requires_bridge',overlap=0)
    new=extra.loc[~extra.trade_date.isin(base.trade_date)]
    return pd.concat([base,new],ignore_index=True).sort_values('trade_date'),[],dict(accepted=True,reason='overlap_checked',overlap=len(common),new_rows=len(new))


def unit_crosscheck(frame):
    eligible=frame.price_eligible&frame.volume_eligible&np.isfinite(frame.amount)&frame.amount.gt(0)
    x=frame.loc[eligible]
    if x.empty:return dict(status='no_positive_turnover_crosscheck',days=0,conversion_applied=False)
    vwap=x.amount/x.volume;ratio=vwap/x.close
    in_range=(vwap>=x.low-1e-5)&(vwap<=x.high+1e-5)
    median=float(ratio.median())
    # This only detects gross 100x/1000x unit mismatch. It is not an official
    # share-lot definition, nor a filter on admissible price observations.
    consistent=0.8<=median<=1.2
    return dict(status='turnover_consistent_with_unscaled_shares_and_quote_currency' if consistent else 'unit_or_price_turnover_relation_requires_review',
                days=len(x),median_amount_per_volume_over_close=median,ratio_p05=float(ratio.quantile(.05)),ratio_p95=float(ratio.quantile(.95)),
                vwap_within_intraday_range_fraction=float(in_range.mean()),conversion_applied=False,official_unit_definition_certified=False,
                caveat='Per-security arithmetic evidence; no exchange-wide guessed multiplier. Missing-volume prices remain eligible.')


def hk_rights(native,batches):
    sources=[];issues=[]
    for batch in batches:
        path=batch/'checkpoints'/(native+'.json')
        if not path.exists():continue
        cp=read_json(path)
        if cp.get('rights_status')!='received':issues.append(dict(path=str(path),status=cp.get('rights_status')));continue
        try:
            protocol=read_json(batch/'protocol.json')
            if cp['protocol_sha256']!=digest(batch/'protocol.json'):raise ValueError('Rights protocol mismatch')
            items=[i for i in protocol['items'] if i['symbol']==native]
            if len(items)!=1 or not items[0].get('rights'):raise ValueError('Rights request not in protocol')
            records,seen,attempt=verify_attempt(batch,cp['rights'],211,native,cp['node'])
            sources.append(dict(path=str(attempt/'decoded.json'),sha256=digest(attempt/'decoded.json'),observed_at=seen or '',records=records))
        except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:issues.append(dict(path=str(path),status='integrity_error',reason=str(exc)))
    chosen=max(sources,key=lambda x:x['observed_at']) if sources else None
    return dict(native_symbol=native,status='received_current' if chosen else 'missing',records=chosen['records'] if chosen else [],
                source_path=chosen['path'] if chosen else '',source_sha256=chosen['sha256'] if chosen else '',
                observed_at=chosen['observed_at'] if chosen else '',source_evidence=[{k:v for k,v in r.items() if k!='records'} for r in sources],
                issues=issues,parsed_using_a_share_rules=False,complete_actions_certified=False,ledger_ready=False,
                empty_does_not_prove_no_events=True,note='HK id211 raw records preserved verbatim; A-share per-ten-share parser is not applied.')


def finalize(master_path,backup,downloads,out,symbols=None):
    master=list(csv.DictReader(master_path.open()));master_total=len(master);master=[r for r in master if not symbols or r['symbol'] in symbols]
    if not master or len({r['symbol'] for r in master})!=len(master):raise ValueError('Empty or duplicate HK master')
    if any(not r['symbol'].endswith('.HK') for r in master):raise ValueError('Non-HK master member')
    out.mkdir(parents=True,exist_ok=False)
    for sub in ['bars','signal-bars','rights']:(out/sub).mkdir()
    (out/'master-input.csv').write_bytes(master_path.read_bytes())
    batches=discover_history_batches(downloads)
    write_json(out/'protocol.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),master=str(master_path.resolve()),master_sha256=digest(master_path),
        start='2013-01-01',end='2026-10-22',symbols_subset=symbols,master_total=master_total,selected=len(master),network_requests=0,account_runs=0,
        mask_policy='Frozen eligible_prices: missing volume preserves valid positive OHLC; geometry/price failures remain raw but cannot enter price state.',
        rights_policy='Raw HK rights only, never A-share per-ten parsing',unit_policy='No conversion; per-security price/turnover arithmetic crosscheck; official unit definition not falsely certified.'))
    spec=importlib.util.spec_from_file_location('frozen_data_utils',FROZEN_HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    coverage=[];evidence=[];conflicts=[];unit_records=[];manifest=[]
    master_sha=digest(master_path)
    quality_file=(out/'row-quality.csv').open('x',newline='')
    quality_fields=['symbol','trade_date','open','high','low','close','volume','amount','quality_status','price_eligible','volume_eligible','source_path']
    quality_writer=csv.DictWriter(quality_file,fieldnames=quality_fields);quality_writer.writeheader()
    for row in master:
        symbol=row['symbol'];native=row.get('ths_symbol','');currency=row.get('currency') or 'HKD';merged=None;se=[]
        old=backup/'canonical'/(native+'.csv')
        if old.exists():
            try:
                legacy,le=legacy_source(backup,native)
                merged=normalize_hk(legacy,symbol,old.resolve(),le['observed_at'],currency)
                merged=merged.loc[merged.trade_date.between('2013-01-01','2026-10-22')]
                le.update(symbol=symbol,native_symbol=native)
            except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:
                le=dict(symbol=symbol,native_symbol=native,path=str(old.resolve()),legacy=True,accepted=False,reason=str(exc))
            se.append(le);evidence.append(le)
        history_paths=sorted((b/'history'/(native+'.json') for b in batches if native and (b/'history'/(native+'.json')).exists()),key=history_source_order)
        for path in history_paths:
            e=dict(symbol=symbol,native_symbol=native,path=str(path.resolve()),sha256=digest(path),accepted=False)
            try:
                frame,x,cp,item,seen=raw_observations(path)
                e.update(history_status=cp['history_status'],stop_reason=cp.get('stop_reason'),requested_end=x['requested_end'],requested_earliest=x['requested_earliest'],raw_unique_dates=x['raw_unique_dates'],
                         parser_dropped_recovered=x['rows_dropped_by_parser'],observed_at=seen)
                if cp['history_status']=='quarantined':raise ValueError('Collector quarantined source')
                if frame.empty:raise ValueError('Empty source records')
                frame=normalize_hk(frame,symbol,path.resolve(),seen,currency)
                frame=frame.loc[frame.trade_date.between('2013-01-01','2026-10-22')]
                if frame.empty:raise ValueError('No source date in target window')
                e.update(first=str(frame.trade_date.min().date()),last=str(frame.trade_date.max().date()),rows=len(frame))
                merged,cc,check=merge_hk(merged,frame,symbol);conflicts.extend(cc);e.update(check)
            except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:e.update(reason=str(exc),accepted=False)
            evidence.append(e);se.append(e)
        first=last='';n=0;bars_path=bars_hash=signal_path=signal_hash='';signal_count=0;last_price='';unit=dict(status='no_bars',days=0)
        missing_volume=bad_price=0
        if merged is not None and not merged.empty:
            merged=merged.sort_values('trade_date').reset_index(drop=True);first=str(merged.trade_date.min().date());last=str(merged.trade_date.max().date());n=len(merged)
            bars_path=str((out/'bars'/(symbol+'.parquet')).resolve());merged.to_parquet(bars_path,index=False);bars_hash=digest(bars_path)
            mask_input=merged.rename(columns={'trade_date':'date'})
            signal=helper.eligible_prices(mask_input,symbol).reset_index()
            if 'index' in signal:signal=signal.rename(columns={'index':'date'})
            signal=signal.rename(columns={'date':'trade_date'})
            expected=merged.loc[merged.price_eligible,'trade_date'].tolist()
            if signal.trade_date.tolist()!=expected:raise ValueError('HK mask differs from frozen eligible_prices')
            signal_count=len(signal);last_price=str(signal.trade_date.max().date()) if signal_count else ''
            signal_path=str((out/'signal-bars'/(symbol+'.parquet')).resolve());signal.to_parquet(signal_path,index=False);signal_hash=digest(signal_path)
            unit=unit_crosscheck(merged);unit_records.append(dict(symbol=symbol,**unit))
            missing_volume=int((~np.isfinite(merged.volume)).sum());bad_price=int((~merged.price_eligible).sum())
            for q in merged.loc[merged.quality_status!='valid_price_and_positive_volume'].to_dict('records'):
                quality_writer.writerow({k:q[k] for k in quality_fields})
        ss,ts=boundary_status(first,last,'2013-01-02','2013-01-01','2026-10-22',se)
        unresolved_source_failures=source_dispositions(se)
        rights=hk_rights(native,batches);rp=out/'rights'/(symbol+'.json');write_json(rp,rights)
        c=dict(symbol=symbol,name=row.get('name',''),ths_symbol=native,currency=currency,rows=n,first=first,last=last,start_status=ss,tail_status=ts,
               price_eligible_rows=signal_count,last_price_eligible=last_price,missing_volume_rows=missing_volume,invalid_price_rows=bad_price,
               new_sources=sum(not e.get('legacy') for e in se),accepted_new_sources=sum(e['accepted'] for e in se if not e.get('legacy')),rejected_new_sources=sum(not e['accepted'] for e in se),
               parser_dropped_recovered=sum(e.get('parser_dropped_recovered',0) for e in se if e['accepted']),
               unresolved_source_failures=unresolved_source_failures,resolved_source_failures=sum(e.get('disposition')=='resolved_by_independent_complete_source' for e in se),
               bars_path=bars_path,bars_sha256=bars_hash,signal_bars_path=signal_path,signal_bars_sha256=signal_hash,
               volume_unit='source_wire_units_unscaled',amount_unit=currency+'_source_wire_units_unscaled',currency_basis='current_HKEX_snapshot',historical_currency_certified=False,unit_crosscheck_status=unit['status'],
               rights_status=rights['status'],rights_records=len(rights['records']),rights_path=str(rp.resolve()),rights_sha256=digest(rp),
               complete_actions_certified=False,account_ready=False)
        coverage.append(c);manifest.append(dict(c,master_sha256=master_sha,master_record=row))
    quality_file.close()
    write_csv(out/'coverage.csv',coverage);write_csv(out/'source-evidence.csv',evidence);write_csv(out/'conflicts.csv',conflicts)
    write_csv(out/'unit-crosschecks.csv',unit_records);write_json(out/'security-manifest.json',manifest)
    unresolved=[r for r in coverage if r['start_status'] in ('no_bars','later_first_bar_unconfirmed') or r['tail_status'] in ('no_bars','tail_unresolved') or r['unresolved_source_failures'] or r['rights_status']!='received_current']
    write_csv(out/'unresolved.csv',unresolved)
    result=dict(selected=len(master),with_bars=sum(r['rows']>0 for r in coverage),raw_observation_rows=sum(r['rows'] for r in coverage),
        price_eligible_rows=sum(r['price_eligible_rows'] for r in coverage),missing_volume_rows=sum(r['missing_volume_rows'] for r in coverage),invalid_price_rows=sum(r['invalid_price_rows'] for r in coverage),
        parser_dropped_recovered=sum(r['parser_dropped_recovered'] for r in coverage),source_conflict_cells=len(conflicts),
        start_status_counts=dict(collections.Counter(r['start_status'] for r in coverage)),tail_status_counts=dict(collections.Counter(r['tail_status'] for r in coverage)),
        rights_status_counts=dict(collections.Counter(r['rights_status'] for r in coverage)),unresolved_securities=len(unresolved),
        network_requests=0,account_runs=0,data_collection_complete=not unresolved and not symbols,algorithm_usable_pool_complete=False,account_ready=False,
        caveat='Raw source collection and price/volume/action usability are separate; no silent security exclusion; no official unit certification from arithmetic alone.')
    write_json(out/'summary.json',result);write_json(out/'code-manifest.json',{str(p.resolve()):digest(p) for p in [Path(__file__),Path(__file__).with_name('finalize_a.py'),FROZEN_HELPER]})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backup-old-only',type=Path);p.add_argument('--master',type=Path);p.add_argument('--backup',type=Path)
    p.add_argument('--downloads',type=Path);p.add_argument('--out',type=Path);p.add_argument('--symbols',nargs='*');a=p.parse_args()
    if a.backup_old_only:print(backup_old(a.backup_old_only))
    else:
        if not all([a.master,a.backup,a.downloads,a.out]):p.error('--master --backup --downloads --out required')
        print(json.dumps(finalize(a.master,a.backup,a.downloads,a.out,a.symbols),ensure_ascii=False,indent=2))

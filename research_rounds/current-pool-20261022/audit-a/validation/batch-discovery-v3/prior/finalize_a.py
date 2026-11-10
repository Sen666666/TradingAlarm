"""Offline A-share cache/new-THS fusion and honest raw/rights coverage reporting.

No network imports or account engine. Every collector response is checked against
its frozen protocol, request, receipt and decoded hash before it can enter bars.
Empty responses, source starts, missing bars and suspension candidates stay visible.
"""
from __future__ import annotations
import argparse, collections, csv, datetime, hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from prepare_a import FIELDS, FORMAL, load_master, merge_frames, normalize, write_csv, write_json

LEGACY_RIGHTS=FORMAL/'TradingAlarm/research/data/ths-refresh-20261018/rights'


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path): return json.loads(Path(path).read_text())
def date8(x): return str(x).replace('-','')


def safe_child(root, relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()): raise ValueError('Evidence outside batch root')
    return path


def verify_attempt(batch, evidence, kind, native, node):
    attempt=safe_child(batch,evidence['attempt'])
    request=read_json(attempt/'request.json'); receipt=read_json(attempt/'receipt.json')
    if request['query']!=evidence['query'] or request['query']['id']!=kind:
        raise ValueError('Evidence request mismatch')
    q=request['query']
    if q['market']+q['code']!=native or str(request['node'])!=str(node):
        raise ValueError('Evidence security/node mismatch')
    endpoints={'9602':'119.3.43.91:9602','9603':'119.3.4.152:9603'}
    if request.get('endpoint')!=endpoints.get(str(node)):
        raise ValueError('Evidence endpoint mismatch')
    raw_hash=digest(attempt/'response.bin'); decoded_hash=digest(attempt/'decoded.json')
    if raw_hash!=evidence['raw_sha256'] or raw_hash!=receipt['sha256']:
        raise ValueError('Raw response hash mismatch')
    if (attempt/'response.bin').stat().st_size!=receipt['bytes'] or decoded_hash!=evidence['decoded_sha256']:
        raise ValueError('Decoded response hash/length mismatch')
    return read_json(attempt/'decoded.json'),receipt.get('received_at') or receipt.get('recovered_at'),attempt


def verify_history(path):
    batch=path.parent.parent; x=read_json(path); native=x['symbol']
    protocol=read_json(batch/'protocol.json'); protocol_hash=digest(batch/'protocol.json')
    cp=read_json(batch/'checkpoints'/(native+'.json'))
    if cp['protocol_sha256']!=protocol_hash or x['protocol_sha256']!=protocol_hash:
        raise ValueError('Protocol hash mismatch')
    items=[i for i in protocol['items'] if i['symbol']==native]
    if len(items)!=1:raise ValueError('Security missing/duplicated in protocol')
    item=items[0]
    if cp['symbol']!=native or str(cp['node'])!=str(item['node']) or str(x['node'])!=str(item['node']):
        raise ValueError('History security/node mismatch')
    if x['requested_end']!=date8(item['end']) or x['requested_earliest']!=date8(item['earliest']):
        raise ValueError('History date request mismatch')
    if cp['history_status']!=x['history_status'] or cp['pages']!=x['pages']:
        raise ValueError('History checkpoint mismatch or active batch snapshot')
    records={};observed_at=[];expected_end=date8(item['end'])
    for page in cp['pages']:
        rows,seen,_=verify_attempt(batch,page,210,native,item['node'])
        if str(page['query']['end'])!=expected_end:raise ValueError('Pagination chain mismatch')
        if 'fuquan' in page['query']:raise ValueError('Adjusted history not allowed')
        if page['query'].get('datatype')!='1,7,8,9,11,13,19,74' or page['query'].get('period')!=16384 or page['query'].get('start')!=-749:
            raise ValueError('History field/period/page-shape mismatch')
        if seen:observed_at.append(seen)
        for row in rows:
            day=str(row['1'])
            if day>expected_end:raise ValueError('Raw date after request end')
            if day in records and records[day]!=row:raise ValueError('Raw overlap conflict')
            records[day]=row
        if rows:expected_end=min(str(row['1']) for row in rows)
    # Reconstruct the parser output from raw evidence, rather than trusting export.
    bars=[]
    for day in sorted(records):
        row=records[day]
        if all(isinstance(row.get(k),(int,float)) for k in ('7','8','9','11')):
            bars.append(dict(date=f'{day[:4]}-{day[4:6]}-{day[6:]}',**{k:row.get(f) for k,f in
                [('open','7'),('high','8'),('low','9'),('close','11'),('volume','13'),('amount','19')]}))
    if bars!=x['bars'] or len(records)!=x['raw_unique_dates']:
        raise ValueError('History export differs from verified raw evidence')
    if len(records)-len(bars)!=x['rows_dropped_by_parser']:
        raise ValueError('Parser drop count differs')
    return x,cp,item,max(observed_at,default='')


def verified_raw_frame(path):
    """Retain every raw date, including dates omitted by the display parser."""
    x,cp,item,seen=verify_history(path);records={};batch=path.parent.parent
    for page in cp['pages']:
        for row in read_json(safe_child(batch,page['attempt'])/'decoded.json'):
            records[str(row['1'])]=row
    rows=[]
    for day in sorted(records):
        r=records[day]
        rows.append(dict(trade_date=f'{day[:4]}-{day[4:6]}-{day[6:]}',**{k:r.get(f) for k,f in
            [('open','7'),('high','8'),('low','9'),('close','11'),('volume','13'),('amount','19')]}))
    return pd.DataFrame(rows,columns=['trade_date']+FIELDS),x,cp,item,seen


def annotate_observations(frame,symbol=None,source_path=None,observed_at=None):
    """Frozen price-clock semantics; missing volume/amount does not erase price."""
    out=frame.copy().rename(columns={'date':'trade_date'})
    out['trade_date']=pd.to_datetime(out.trade_date,errors='raise')
    if out.trade_date.isna().any() or out.trade_date.duplicated().any():raise ValueError('Missing or duplicate source date')
    for k in FIELDS:out[k]=pd.to_numeric(out[k],errors='coerce')
    finite=np.isfinite(out[FIELDS[:4]]).all(axis=1)&out[FIELDS[:4]].gt(0).all(axis=1)
    geometry=out.high.ge(out.low)&out.high.ge(out[['open','close']].max(axis=1))&out.low.le(out[['open','close']].min(axis=1))
    out['price_eligible']=finite&geometry
    out['volume_eligible']=np.isfinite(out.volume)&out.volume.gt(0)
    out['source_invalid']=~out.price_eligible
    out['observed_bar']=True;out['is_observed_bar']=True;out['synthetic_event_bar']=False
    out['quality_status']=np.select([~finite,~geometry,~np.isfinite(out.volume),out.volume.lt(0),out.volume.eq(0),~np.isfinite(out.amount),out.amount.lt(0)],
        ['missing_or_nonpositive_price','invalid_price_geometry','volume_missing_price_preserved','negative_volume_price_preserved','zero_volume_price_preserved','amount_missing_price_preserved','negative_amount_price_preserved'],default='valid_price_and_positive_volume')
    if symbol is not None:out['symbol']=symbol
    if source_path is not None:out['source_path']=str(source_path);out['source_kind']='ths_raw'
    if observed_at is not None:out['observed_at']=observed_at
    elif 'observed_at' not in out:out['observed_at']=''
    out['volume_unit']='shares';out['amount_unit']='CNY';out['price_adjustment']='raw'
    return out.sort_values('trade_date').reset_index(drop=True)


def merge_observations(base,extra,symbol):
    """Compare usable like fields; missing/invalid new rows never erase old facts.

    The original source JSON/raw bytes preserve every source version. Canonical
    overlap keeps old values; new unique dates retain missing fields and masks.
    Actual finite/eligible disagreements remain an explicit source quarantine.
    """
    if base is None:return extra.copy(),[],dict(accepted=True,reason='first_available_source',overlap=0)
    a=base.set_index('trade_date');b=extra.set_index('trade_date');common=a.index.intersection(b.index)
    if not len(common):return base.copy(),[],dict(accepted=False,reason='no_overlap_requires_bridge',overlap=0)
    conflicts=[];skipped=0
    for k in FIELDS:
        av=a.loc[common,k].to_numpy();bv=b.loc[common,k].to_numpy()
        comparable=np.isfinite(av)&np.isfinite(bv)
        if k in FIELDS[:4]:comparable &= a.loc[common,'price_eligible'].to_numpy()&b.loc[common,'price_eligible'].to_numpy()
        else:comparable &= (av>=0)&(bv>=0)
        skipped+=int((~comparable).sum())
        atol,rtol=(1e-6,0) if k in FIELDS[:4] else (1.,1e-6)
        mismatch=comparable&~np.isclose(av,bv,atol=atol,rtol=rtol,equal_nan=True)
        for day,old,new in zip(common[mismatch],av[mismatch],bv[mismatch]):
            conflicts.append(dict(symbol=symbol,date=str(day.date()),field=k,old=float(old),new=float(new),old_source=a.at[day,'source_path'],new_source=b.at[day,'source_path']))
    detail=dict(overlap=len(common),overlap_noncomparable_cells_preserved_in_raw=skipped)
    if conflicts:return base.copy(),conflicts,dict(detail,accepted=False,reason='overlap_conflict')
    new=extra.loc[~extra.trade_date.isin(base.trade_date)]
    return pd.concat([base,new],ignore_index=True).sort_values('trade_date').reset_index(drop=True),[],dict(detail,accepted=True,reason='overlap_checked_with_explicit_missing_fields',new_rows=len(new))


def unit_evidence(prepared, paths, native_to_symbol):
    """Require observed cross-source unit agreement for each native A market."""
    result={}
    for path in paths:
        native=path.stem;market=native[:4]
        if market in result or native not in native_to_symbol:continue
        old=prepared/'bars'/(native_to_symbol[native]+'.parquet')
        if not old.exists():continue
        try:
            frame,x,cp,item,seen=verified_raw_frame(path)
            if cp['history_status']=='quarantined' or frame.empty:continue
            a=annotate_observations(pd.read_parquet(old)).set_index('trade_date');b=annotate_observations(frame,source_path=path).set_index('trade_date')
            common=a.index.intersection(b.index)
            eligible=a.loc[common,'price_eligible']&b.loc[common,'price_eligible']&np.isfinite(a.loc[common,FIELDS]).all(axis=1)&np.isfinite(b.loc[common,FIELDS]).all(axis=1)
            common=common[eligible]
            if len(common)<20:continue
            good=True;ratios={}
            for field in FIELDS:
                av=a.loc[common,field].to_numpy();bv=b.loc[common,field].to_numpy()
                atol,rtol=(1e-6,0) if field in FIELDS[:4] else (1.,1e-6)
                good &= bool(np.isclose(av,bv,atol=atol,rtol=rtol).all())
                if field in ('volume','amount'):
                    mask=(av>0)&(bv>0)
                    if mask.sum()<20:good=False
                    ratios[field]=float(np.median(bv[mask]/av[mask])) if mask.any() else None
            if good:result[market]=dict(native=native,path=str(path),sha256=digest(path),overlap_dates=len(common),
                                        ratios_to_shares_CNY=ratios,volume_unit='shares',amount_unit='CNY',observed_at=seen)
        except (ValueError,KeyError,FileNotFoundError,TypeError):continue
    return result


def rights_sources(symbol, native, batches, parser):
    sources=[];issues=[]
    old_native=('USZA' if symbol.endswith('.SZ') else 'USHA')+symbol.split('.')[0]
    old=LEGACY_RIGHTS/(old_native+'.json')
    if old.exists():
        x=read_json(old)
        if x.get('symbol')==old_native:
            sources.append(dict(path=str(old),sha256=digest(old),observed_at=x.get('fetched_at',''),records=x['records'],fresh=False))
    for batch in batches:
        path=batch/'checkpoints'/(native+'.json')
        if not path.exists():continue
        cp=read_json(path)
        if cp.get('rights_status')!='received':
            issues.append(dict(path=str(path),status=cp.get('rights_status'),error=cp.get('last_error')));continue
        try:
            protocol=read_json(batch/'protocol.json')
            if cp['protocol_sha256']!=digest(batch/'protocol.json'):raise ValueError('Rights protocol mismatch')
            items=[x for x in protocol['items'] if x['symbol']==native]
            if len(items)!=1 or not items[0].get('rights'):raise ValueError('Rights not in protocol')
            records,seen,attempt=verify_attempt(batch,cp['rights'],211,native,cp['node'])
            sources.append(dict(path=str(attempt/'decoded.json'),sha256=digest(attempt/'decoded.json'),
                                observed_at=seen or '',records=records,fresh=True))
        except (ValueError,KeyError,FileNotFoundError,TypeError) as exc:
            issues.append(dict(path=str(path),status='integrity_error',error=str(exc)))
    chosen=max(sources,key=lambda x:(x['fresh'],x['observed_at'])) if sources else None
    events=[];unparsed=[]
    if chosen:
        for row in chosen['records']:
            try:events.append(parser(native,row))
            except (ValueError,KeyError,TypeError) as exc:unparsed.append(dict(row=row,reason=str(exc)))
    return dict(symbol=symbol,native_symbol=native,status='received_current' if chosen and chosen['fresh'] else 'legacy_only' if chosen else 'missing',
                source_path=chosen['path'] if chosen else '',source_sha256=chosen['sha256'] if chosen else '',
                observed_at=chosen['observed_at'] if chosen else '',records=chosen['records'] if chosen else [],
                events=events,unparsed=unparsed,source_evidence=[{k:v for k,v in x.items() if k!='records'} for x in sources],
                issues=issues,complete_actions_certified=False,ledger_ready=False,
                caveat='Raw id211 received and parser coverage only; no invented pay dates; unparsed records preserved.')


def boundary_status(first,last,target_first,start,end,evidence):
    accepted=[e for e in evidence if e.get('accepted')]
    if not first:return 'no_bars','no_bars'
    start_status='reaches_start' if first<=target_first else 'later_first_bar_unconfirmed'
    for e in accepted:
        if e.get('history_status')=='complete' and e.get('stop_reason') in ('short_raw_page_source_boundary','empty_raw_page'):
            if e.get('first') and e['first']<=first:start_status='available_source_start_verified' if first>target_first else 'reaches_start'
    if last>=end:tail='end_reached'
    elif any(e.get('history_status')=='complete' and e.get('requested_end')==date8(end) for e in accepted):
        tail='latest_source_bar_before_end_suspension_or_source_limit'
    else:tail='tail_unresolved'
    return start_status,tail


def finalize(prepared,downloads,out,limit=None):
    master_path=prepared/'master-input.csv'; master=load_master(master_path)
    protocol=read_json(prepared/'prepare-protocol.json')
    if digest(master_path)!=protocol['master_sha256']:raise ValueError('Prepared master snapshot hash mismatch')
    if limit is not None:master=master[:limit]
    batches=sorted(p for p in downloads.iterdir() if p.is_dir() and (p/'protocol.json').exists())
    native_to_symbol={r['ths_symbol']:r['current_symbol'] for r in master}
    all_paths=[p for b in batches for p in sorted((b/'history').glob('*.json')) if p.stem in native_to_symbol]
    units=unit_evidence(prepared,all_paths,native_to_symbol)
    out.mkdir(parents=True,exist_ok=False);(out/'bars').mkdir();(out/'rights').mkdir();(out/'signal-bars').mkdir()
    write_json(out/'unit-evidence.json',units)
    write_json(out/'protocol.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        prepared=str(prepared.resolve()),master_sha256=digest(master_path),downloads=str(downloads.resolve()),
        batches=[str(b.resolve()) for b in batches],start=protocol['start'],end=protocol['end'],
        network_requests=0,account_runs=0,limit=limit,source_merge_policy='Canonical old overlap preserved; conflicting new source quarantined whole; no-overlap requires bridge.',
        source_boundary_policy='Short/empty terminal page proves available-source boundary, not an exchange listing date or suspension reason.',
        action_policy='Data collection closure distinct from precise pay-date accounting; raw id211 and unparsed records retained.'))
    source_code=FORMAL/'TradingAlarm/research/stock_actions.py'
    spec=importlib.util.spec_from_file_location('existing_stock_actions',source_code);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mask_code=FORMAL/'research_rounds/pv-participation-response-20261020/code/data_utils.py'
    spec_mask=importlib.util.spec_from_file_location('frozen_price_mask',mask_code);mask=importlib.util.module_from_spec(spec_mask);spec_mask.loader.exec_module(mask)
    old_cov={r['symbol']:r for r in csv.DictReader((prepared/'coverage.csv').open())}
    coverage=[];conflicts=[];evidence=[];gaps=[];manifest=[];prepared_inputs=[]
    quality_file=(out/'row-quality.csv').open('x',newline='')
    quality_fields=['symbol','trade_date','open','high','low','close','volume','amount','quality_status','price_eligible','volume_eligible','source_path']
    quality_writer=csv.DictWriter(quality_file,fieldnames=quality_fields);quality_writer.writeheader()
    grouped=collections.defaultdict(list)
    for path in all_paths:grouped[path.stem].append(path)
    for record in master:
        symbol=record['current_symbol'];native=record['ths_symbol'];old=prepared/'bars'/(symbol+'.parquet')
        old_hash=digest(old) if old.exists() else ''
        prepared_inputs.append(dict(symbol=symbol,path=str(old.resolve()),exists=old.exists(),sha256=old_hash))
        merged=annotate_observations(pd.read_parquet(old),symbol=symbol) if old.exists() else None
        if merged is not None:
            merged['is_observed_bar']=True
            merged['observed_at']=''
        se=[]
        for path in grouped[native]:
            e=dict(symbol=symbol,native_symbol=native,path=str(path.resolve()),sha256=digest(path),accepted=False)
            try:
                frame,x,cp,item,seen=verified_raw_frame(path)
                e.update(history_status=cp['history_status'],stop_reason=cp.get('stop_reason'),requested_end=x['requested_end'],
                         requested_earliest=x['requested_earliest'],raw_unique_dates=x['raw_unique_dates'],parser_drops=x['rows_dropped_by_parser'],observed_at=seen)
                if cp['history_status']=='quarantined':raise ValueError('Collector quarantined source')
                if native[:4] not in units:raise ValueError('Native market units lack overlap evidence')
                if frame.empty:raise ValueError('Empty history cannot synthesize a bar')
                frame=annotate_observations(frame,symbol,path.resolve(),seen)
                frame=frame.loc[frame.trade_date.between(protocol['start'],protocol['end'])]
                if frame.empty:raise ValueError('No bars in target window')
                e.update(first=str(frame.trade_date.min().date()),last=str(frame.trade_date.max().date()),rows=len(frame))
                merged,cc,check=merge_observations(merged,frame,symbol);conflicts.extend(cc);e.update(check)
            except (ValueError,KeyError,FileNotFoundError,TypeError) as exc:e.update(reason=str(exc),accepted=False)
            evidence.append(e);se.append(e)
        first=last='';bars_path='';bar_hash='';signal_path=signal_hash='';n=0;zero_volume=0;price_rows=missing_volume=missing_amount=invalid_price=0
        if merged is not None and not merged.empty:
            merged=merged.sort_values('trade_date').reset_index(drop=True)
            merged['symbol']=symbol;first=str(merged.trade_date.min().date());last=str(merged.trade_date.max().date());n=len(merged)
            zero_volume=int((merged.volume==0).sum());bars_path=str((out/'bars'/(symbol+'.parquet')).resolve())
            merged.to_parquet(bars_path,index=False);bar_hash=digest(bars_path)
            signal=mask.eligible_prices(merged.rename(columns={'trade_date':'date'}),symbol).reset_index().rename(columns={'date':'trade_date'})
            if signal.trade_date.tolist()!=merged.loc[merged.price_eligible,'trade_date'].tolist():raise ValueError('A mask differs from frozen eligible_prices')
            price_rows=len(signal);missing_volume=int((~np.isfinite(merged.volume)).sum());missing_amount=int((~np.isfinite(merged.amount)).sum());invalid_price=int((~merged.price_eligible).sum())
            signal_path=str((out/'signal-bars'/(symbol+'.parquet')).resolve());signal.to_parquet(signal_path,index=False);signal_hash=digest(signal_path)
            for q in merged.loc[merged.quality_status!='valid_price_and_positive_volume'].to_dict('records'):
                quality_writer.writerow({k:q[k] for k in quality_fields})
            dates=merged.trade_date
            for i in np.flatnonzero((dates.diff().dt.days>14).fillna(False).to_numpy()):
                gaps.append(dict(symbol=symbol,previous=str(dates.iloc[i-1].date()),next=str(dates.iloc[i].date()),
                                 calendar_days=int((dates.iloc[i]-dates.iloc[i-1]).days),classification='calendar_span_only_not_a_claim_of_missing_trading_days'))
        target_first=old_cov[symbol]['target_first_observed_session']
        ss,ts=boundary_status(first,last,target_first,protocol['start'],protocol['end'],se)
        rights=rights_sources(symbol,native,batches,mod.parse_ths_rights)
        rights_path=out/'rights'/(symbol+'.json');write_json(rights_path,rights)
        rejected=sum(not e['accepted'] for e in se)
        row=dict(symbol=symbol,name=record.get('name',''),ths_symbol=native,rows=n,first=first,last=last,
                 start_status=ss,tail_status=ts,new_sources=len(se),accepted_new_sources=sum(e['accepted'] for e in se),rejected_new_sources=rejected,
                 source_conflict_cells=sum(c['symbol']==symbol for c in conflicts),zero_volume_observed_bars=zero_volume,
                 bars_path=bars_path,bars_sha256=bar_hash,volume_unit='shares',amount_unit='CNY',price_adjustment='raw',
                 prepared_input_path=str(old.resolve()) if old_hash else '',prepared_input_sha256=old_hash,
                 signal_bars_path=signal_path,signal_bars_sha256=signal_hash,price_eligible_rows=price_rows,missing_volume_rows=missing_volume,
                 missing_amount_rows=missing_amount,invalid_price_rows=invalid_price,
                 parser_dropped_recovered=sum(e.get('parser_drops',0) for e in se if e['accepted']),
                 rights_status=rights['status'],rights_records=len(rights['records']),rights_parsed=len(rights['events']),rights_unparsed=len(rights['unparsed']),
                 rights_path=str(rights_path.resolve()),rights_sha256=digest(rights_path),complete_actions_certified=False,account_ready=False)
        coverage.append(row);manifest.append(dict(row,master_sha256=protocol['master_sha256']))
    quality_file.close();write_json(out/'prepared-input-evidence.json',prepared_inputs)
    write_csv(out/'coverage.csv',coverage);write_csv(out/'conflicts.csv',conflicts);write_csv(out/'source-evidence.csv',evidence);write_csv(out/'long-calendar-spans.csv',gaps)
    write_json(out/'security-manifest.json',manifest)
    unresolved=[r for r in coverage if r['start_status'] in ('no_bars','later_first_bar_unconfirmed') or
        r['tail_status'] in ('no_bars','tail_unresolved') or r['rejected_new_sources'] or r['rights_status']!='received_current']
    write_csv(out/'unresolved.csv',unresolved)
    result=dict(selected=len(master),with_bars=sum(r['rows']>0 for r in coverage),rows=sum(r['rows'] for r in coverage),
        start_status_counts=dict(collections.Counter(r['start_status'] for r in coverage)),tail_status_counts=dict(collections.Counter(r['tail_status'] for r in coverage)),
        rights_status_counts=dict(collections.Counter(r['rights_status'] for r in coverage)),unparsed_rights_records=sum(r['rights_unparsed'] for r in coverage),
        price_eligible_rows=sum(r['price_eligible_rows'] for r in coverage),missing_volume_rows=sum(r['missing_volume_rows'] for r in coverage),
        missing_amount_rows=sum(r['missing_amount_rows'] for r in coverage),invalid_price_rows=sum(r['invalid_price_rows'] for r in coverage),
        parser_dropped_recovered=sum(r['parser_dropped_recovered'] for r in coverage),
        conflict_cells=len(conflicts),rejected_new_sources=sum(r['rejected_new_sources'] for r in coverage),unresolved_securities=len(unresolved),
        network_requests=0,account_runs=0,data_collection_complete=not unresolved and limit is None,
        exact_pay_date_ledger_complete=False,account_ready=False,
        caveat='Current 2026-10-22 survivor pool historical data, not historical investability; terminal source boundaries are documented separately from observed bars.')
    write_json(out/'summary.json',result)
    write_json(out/'code-manifest.json',{str(p.resolve()):digest(p) for p in [Path(__file__),Path(__file__).with_name('prepare_a.py'),source_code,mask_code]})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--downloads',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--limit',type=int);a=p.parse_args()
    print(json.dumps(finalize(a.prepared,a.downloads,a.out,a.limit),ensure_ascii=False,indent=2))

"""Offline current-pool A-share cache preparation. Never imports a network client.

Today's supplied master fixes membership. Existing histories are sources, not a
historical eligibility universe. Raw Tushare hands/kCNY are normalized to shares/CNY.
"""
from __future__ import annotations
import argparse,csv,datetime,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

FORMAL=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
RAW=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
CACHE=FORMAL/'TradingAlarm/research/data/ths-refresh-20261018/ths-raw'
FIELDS=['open','high','low','close','volume','amount']


def load_master(path):
    if path.suffix.lower()=='.csv':
        with path.open() as f: records=list(csv.DictReader(f))
    else:
        obj=json.loads(path.read_text());records=obj if isinstance(obj,list) else obj.get('records',obj.get('stocks'))
    if not isinstance(records,list):raise ValueError('Master must be a list, records list or stocks list')
    result=[];seen=set()
    for row in records:
        symbol=row.get('current_symbol') or row.get('symbol')
        if not symbol or symbol.rsplit('.',1)[-1] not in ('SH','SZ','BJ'):
            continue
        if symbol in seen:raise ValueError('Duplicate current symbol: '+symbol)
        seen.add(symbol)
        aliases=row.get('cache_symbols') or [symbol]
        if isinstance(aliases,str):aliases=json.loads(aliases) if aliases.startswith('[') else [aliases]
        if not isinstance(aliases,list) or not all(isinstance(x,str) for x in aliases):raise ValueError('Invalid cache aliases')
        result.append(dict(row,current_symbol=symbol,cache_symbols=list(dict.fromkeys([symbol]+aliases))))
    if not result:raise ValueError('No explicit A-share current_symbol/symbol rows in master')
    return sorted(result,key=lambda r:r['current_symbol'])


def normalize(frame, kind, source_path):
    frame=frame.copy()
    if 'trade_date' not in frame and 'date' in frame:frame=frame.rename(columns={'date':'trade_date'})
    frame['trade_date']=pd.to_datetime(frame.trade_date)
    for k in FIELDS:frame[k]=pd.to_numeric(frame[k],errors='raise')
    if frame.trade_date.isna().any():raise ValueError('Missing date')
    if not np.isfinite(frame[FIELDS].to_numpy()).all():raise ValueError('Nonfinite OHLCV/amount')
    if ((frame[['open','high','low','close']]<=0).any(axis=1)|
        (frame.low>frame[['open','close']].min(axis=1)+1e-6)|
        (frame.high<frame[['open','close']].max(axis=1)-1e-6)|
        (frame.volume<0)|(frame.amount<0)).any():raise ValueError('Invalid raw OHLCV')
    if frame.trade_date.duplicated().any():raise ValueError('Duplicate date inside source')
    if kind=='tushare_raw':
        if 'source' not in frame or set(frame.source)!={'tushare'}:raise ValueError('Unverified source units')
        frame['volume']=frame.volume*100.0
        frame['amount']=frame.amount*1000.0
    elif kind!='ths_raw':raise ValueError('Unsupported source kind')
    frame['source_kind']=kind;frame['source_path']=str(source_path)
    frame['volume_unit']='shares';frame['amount_unit']='CNY';frame['price_adjustment']='raw'
    return frame[['trade_date']+FIELDS+['source_kind','source_path','volume_unit','amount_unit','price_adjustment']].sort_values('trade_date')


def merge_frames(base, extra, symbol):
    """Preserve canonical overlapping rows; reject a conflicting extra source.

    Numeric tolerance only accounts for wire rounding, not a trend threshold.
    """
    if base is None:return extra.copy(),[],{'overlap':0,'accepted':True,'reason':'first_available_source'}
    a=base.set_index('trade_date');b=extra.set_index('trade_date');common=a.index.intersection(b.index)
    conflicts=[]
    for k in FIELDS:
        x=a.loc[common,k].to_numpy();y=b.loc[common,k].to_numpy()
        atol,rtol=(1e-6,0) if k in ('open','high','low','close') else (1.0,1e-6)
        mismatch=~np.isclose(x,y,atol=atol,rtol=rtol)
        for d,old,new in zip(common[mismatch],x[mismatch],y[mismatch]):
            conflicts.append({'symbol':symbol,'date':str(d.date()),'field':k,'old':float(old),'new':float(new),
                              'old_source':a.at[d,'source_path'],'new_source':b.at[d,'source_path']})
    if conflicts:return base.copy(),conflicts,{'overlap':len(common),'accepted':False,'reason':'overlap_conflict'}
    if len(common)==0:
        return base.copy(),[],{'overlap':0,'accepted':False,'reason':'no_overlap_requires_bridge'}
    new=extra.loc[~extra.trade_date.isin(base.trade_date)]
    merged=pd.concat([base,new],ignore_index=True).sort_values('trade_date').reset_index(drop=True)
    return merged,[],{'overlap':len(common),'accepted':True,'reason':'overlap_checked','new_rows':len(new)}


def native_cache_path(symbol):
    code,market=symbol.rsplit('.',1)
    if market=='SH':return CACHE/('USHA'+code+'.json')
    if market=='SZ':return CACHE/('USZA'+code+'.json')
    return None


def write_json(p,obj):
    with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def write_csv(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r)) or ['symbol']
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def prepare(master_path,out,start='2013-01-01',end='2026-10-22',limit=None):
    master=load_master(master_path)
    if limit is not None:master=master[:limit]
    out.mkdir(parents=True,exist_ok=False);(out/'bars').mkdir()
    write_json(out/'prepare-protocol.json',{'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'offline_cache_preparation_only','master_path':str(master_path),'master_sha256':hashlib.sha256(master_path.read_bytes()).hexdigest(),
        'start':start,'end':end,'selected':len(master),'network_requests':0,'units':{'tushare_volume_multiplier':100,'tushare_amount_multiplier':1000},
        'history_membership_mode':'20261022_fixed_current_master_no_historical_eligibility_reconstruction',
        'missing_history_or_actions_are_not_certified_complete':True,'limit':limit})
    boundary_table=pq.read_table(RAW,columns=['trade_date'],filters=[('trade_date','>=',pd.Timestamp(start)),
        ('trade_date','<=',pd.Timestamp(start)+pd.Timedelta(days=7))])
    observed=boundary_table.to_pandas().trade_date.min() if boundary_table.num_rows else pd.NaT
    target_first_session=str((observed if pd.notna(observed) else pd.Timestamp(start)).date())
    summary=[];conflicts=[];requests=[];inputs=[]
    for offset in range(0,len(master),100):
        chunk=master[offset:offset+100]
        aliases=sorted({alias for item in chunk for alias in item['cache_symbols']})
        table=pq.read_table(RAW,columns=['symbol','trade_date']+FIELDS+['source'],
            filters=[('symbol','in',aliases),('trade_date','>=',pd.Timestamp(start)),('trade_date','<=',pd.Timestamp(end))])
        groups={symbol:frame for symbol,frame in table.to_pandas().groupby('symbol')}
        for record in chunk:
            symbol=record['current_symbol'];merged=None;checks=[];errors=[];all_sources=[]
            for alias in record['cache_symbols']:
                if alias in groups:
                    try:
                        frame=normalize(groups[alias],'tushare_raw',RAW)
                        merged,cc,check=merge_frames(merged,frame,symbol);conflicts.extend(cc)
                        checks.append(dict(check,source=str(RAW),cache_symbol=alias));all_sources.append(str(RAW)+'#'+alias)
                    except Exception as e:errors.append({'source':str(RAW),'cache_symbol':alias,'error':str(e)})
                path=native_cache_path(alias)
                if path is not None and path.exists():
                    x=json.loads(path.read_text())
                    try:
                        if not str(x.get('adjustment','')).startswith('fuquan omitted'):raise ValueError('Cache not marked raw')
                        frame=normalize(pd.DataFrame(x['bars']),'ths_raw',path)
                        frame=frame.loc[frame.trade_date.between(start,end)]
                        if not frame.empty:
                            merged,cc,check=merge_frames(merged,frame,symbol);conflicts.extend(cc)
                            checks.append(dict(check,source=str(path),cache_symbol=alias));all_sources.append(str(path))
                        inputs.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                    except Exception as e:errors.append({'source':str(path),'error':str(e)})
            first=last='';n=0;bar_path='';source_ranges=[]
            if merged is not None and not merged.empty:
                merged=merged.sort_values('trade_date');first=str(merged.trade_date.min().date());last=str(merged.trade_date.max().date());n=len(merged)
                merged.insert(0,'symbol',symbol);bar_path=str(out/'bars'/(symbol+'.parquet'));merged.to_parquet(bar_path,index=False)
                source_ranges=[{'source_kind':k[0],'source_path':k[1],'first':str(g.trade_date.min().date()),'last':str(g.trade_date.max().date()),'rows':len(g)}
                               for k,g in merged.groupby(['source_kind','source_path'])]
            rejected=any(not c['accepted'] for c in checks) or bool(errors)
            list_date=record.get('list_date') or ''
            if list_date:
                try:list_date=str(pd.Timestamp(list_date).date())
                except Exception:list_date=''
            # A current listing date is optional evidence, not a historical member gate.
            start_status='no_cache' if not first else ('reaches_start' if first<=target_first_session else
                         'post_listing_available_start' if list_date and list_date>=start and first==list_date else 'later_first_bar_needs_head_probe')
            row={'symbol':symbol,'name':record.get('name',''),'ths_symbol':record.get('ths_symbol',''),
                 'rows':n,'first':first,'last':last,'start_status':start_status,'target_first_observed_session':target_first_session,'last_before_end':not last or last<end,
                 'source_rejected_or_error':rejected,'bars_path':bar_path,'volume_unit':'shares','amount_unit':'CNY',
                 'sources':json.dumps(source_ranges,ensure_ascii=False),'merge_checks':json.dumps(checks,ensure_ascii=False),
                 'errors':json.dumps(errors,ensure_ascii=False),'corporate_actions_complete_certified':False}
            summary.append(row)
            native=record.get('ths_symbol','')
            # New master supplies native IDs, including BJ; do not guess a BJ market.
            if not native and symbol.endswith('.SH'):native='USHA'+symbol.split('.')[0]
            if not native and symbol.endswith('.SZ'):native='USZA'+symbol.split('.')[0]
            if not last or last<end or rejected:
                anchor=str(merged.trade_date.iloc[max(0,len(merged)-20)].date()) if n else start
                requests.append({'symbol':symbol,'ths_symbol':native,'kind':'tail_with_overlap' if n else 'bounded_full_history',
                                 'end':end.replace('-',''),'earliest':anchor,'max_pages':1 if n else 5,
                                 'adjustment':'raw','needs_native_resolution':not bool(native),'reason':'source_conflict_recheck' if rejected else 'tail_missing',
                                 'existing_last':last,'target_start':start})
            if start_status=='later_first_bar_needs_head_probe':
                requests.append({'symbol':symbol,'ths_symbol':native,'kind':'head_availability_probe','end':first.replace('-',''),
                                 'earliest':start,'max_pages':1,'adjustment':'raw','needs_native_resolution':not bool(native),
                                 'reason':'differentiate_available_history_start_from_truncation_not_historical_membership'})
    write_csv(out/'coverage.csv',summary);write_csv(out/'conflicts.csv',conflicts)
    write_csv(out/'start-coverage-insufficient.csv',[r for r in summary if r['start_status'] in ('no_cache','later_first_bar_needs_head_probe')])
    write_json(out/'history-request-plan.json',{'status':'proposed_for_shared_history_batch_not_executed','start':start,'end':end,
        'requests':requests,'requests_count':len(requests),'page_budget_sum':sum(r['max_pages'] for r in requests),
        'tail_first':True,'note':'Empty/short server history and suspension must be recorded, not zero-filled. A newer dataset does not certify corporate actions.'})
    write_json(out/'cache-inputs.json',inputs)
    write_json(out/'summary.json',{'selected':len(master),'with_bars':sum(r['rows']>0 for r in summary),'rows':sum(r['rows'] for r in summary),
        'source_errors_or_rejections':sum(r['source_rejected_or_error'] for r in summary),'conflict_cells':len(conflicts),
        'tail_requests':sum(r['kind']!='head_availability_probe' for r in requests),'head_requests':sum(r['kind']=='head_availability_probe' for r in requests),
        'network_requests':0,'current_pool_data_complete':False,'phase':'offline_preparation_not_collection_closeout'})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--master',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--start',default='2013-01-01');p.add_argument('--end',default='2026-10-22');p.add_argument('--limit',type=int)
    a=p.parse_args();print(prepare(a.master,a.out,a.start,a.end,a.limit))

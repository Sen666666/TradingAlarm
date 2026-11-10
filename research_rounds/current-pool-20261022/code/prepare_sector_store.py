"""Bounded offline sector raw merge/continuity audit, no model or account calls."""
from pathlib import Path
import csv, json, hashlib
import numpy as np
import pandas as pd
import current_pool_bridge as bridge

ROOT=Path(__file__).resolve().parents[1]
FORMAL=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
OLD=FORMAL/'TradingAlarm/research/data/ths-index-history-9603-20261018'
OUT=ROOT/'sector-data-v2'
FIELDS=['open','high','low','close','volume','amount']
WIRE={'open':'7','high':'8','low':'9','close':'11','volume':'13','amount':'19'}


def save(path,obj):
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def evidence(path):
    return {'path':str(path.resolve()),'sha256':bridge.sha256(path),'bytes':path.stat().st_size}


def checked_new(symbol,path):
    obj=json.loads(path.read_text());batch=path.parent.parent
    if obj['symbol']!=symbol or obj.get('source')!='THS id210 raw; fuquan omitted':
        raise ValueError('history identity/raw source marker mismatch '+symbol)
    sources=[evidence(path)];records={};overlap=0
    for page in obj['pages']:
        if 'fuquan' in page['query']:raise ValueError('Unexpected adjusted source query')
        loc=batch/page['attempt'];rp=loc/'response.bin';dp=loc/'decoded.json'
        if bridge.sha256(rp)!=page['raw_sha256'] or bridge.sha256(dp)!=page['decoded_sha256']:
            raise ValueError('Changed native page '+str(loc))
        receipt=json.loads((loc/'receipt.json').read_text())
        if receipt['sha256']!=bridge.sha256(rp):raise ValueError('Receipt mismatch')
        rows=json.loads(dp.read_text())
        for row in rows:
            key=str(row['1'])
            if key in records:
                if row!=records[key]:raise ValueError('Native raw overlap conflict')
                overlap+=1
            records[key]=row
        sources.extend(evidence(loc/name) for name in ('response.bin','decoded.json','request.json','receipt.json'))
    rows=[{'date':pd.to_datetime(k,format='%Y%m%d'),**{name:row.get(code) for name,code in WIRE.items()}}
          for k,row in sorted(records.items())]
    frame=pd.DataFrame(rows).set_index('date')
    frame['source_path']=str(path.resolve());frame['source_kind']='THS_id210_9603_current'
    return frame,sources,{'raw_unique_dates':len(records),'raw_page_overlap':overlap,
                         'legacy_parser_dropped':obj['rows_dropped_by_parser'],'history_status':obj['history_status'],
                         'stop_reason':obj['stop_reason']}


def checked_old(symbol):
    path=OLD/'canonical'/f'{symbol}.csv';cp=OLD/'checkpoints'/f'{symbol}.json'
    frame=pd.read_csv(path,index_col='date',parse_dates=True,float_precision='round_trip')
    checkpoint=json.loads(cp.read_text());sources=[evidence(path),evidence(cp)]
    if checkpoint['symbol']!=symbol or len(frame)!=checkpoint['rows']:raise ValueError('Old identity/count mismatch')
    for page in checkpoint['pages']:
        rp=OLD/page['file']
        if bridge.sha256(rp)!=page['body_sha256']:raise ValueError('Old raw page changed')
        sources.append(evidence(rp))
    frame=frame[FIELDS].copy();frame['source_path']=str(path);frame['source_kind']='THS_id210_9603_20261018_canonical'
    return frame,sources


def main():
    if (OUT/'manifest.json').exists():raise FileExistsError('Refuse to overwrite store')
    (OUT/'bars').mkdir(exist_ok=False)
    a=pd.read_csv(ROOT/'audit-snapshot/a-industry-index-bridge.csv',dtype=str).to_dict('records')
    h=pd.read_csv(ROOT/'audit-snapshot/hk-industry-index-bridge.resolved.csv',dtype=str).to_dict('records')
    masters=[dict(x,market='A') for x in a]+[dict(x,market='H') for x in h]
    frames={};summary=[];all_sources=[];conflicts=[]
    for row in masters:
        symbol=row['index_symbol']; old=None;checks={};sources=[]
        if row['market']=='A':old,sources=checked_old(symbol)
        paths=[p for p in [ROOT/'downloads/hk-industry-pilot-01/history'/f'{symbol}.json',
                          ROOT/'downloads/sector-history-remaining-01/history'/f'{symbol}.json'] if p.exists()]
        if len(paths)!=1:raise ValueError('Exactly one new history expected '+symbol)
        new,src,check=checked_new(symbol,paths[0]);sources+=src;checks['new_history']=check
        for col in FIELDS:new[col]=pd.to_numeric(new[col],errors='coerce')
        if old is not None:
            overlap=old.index.intersection(new.index);checks['old_new_overlap_rows']=len(overlap)
            if len(overlap)==0:raise ValueError('No old/new overlap for '+symbol)
            checks['overlap_fields']={}
            for col in FIELDS:
                x=old.loc[overlap,col].to_numpy();y=new.loc[overlap,col].to_numpy()
                same=np.isclose(x,y,rtol=1e-12,atol=1e-9,equal_nan=True)
                checks['overlap_fields'][col]={'mismatches':int((~same).sum()),
                    'median_new_old_ratio':float(np.nanmedian(y[x>0]/x[x>0])) if (x>0).any() else None}
                for d,v,w in zip(overlap[~same],x[~same],y[~same]):
                    conflicts.append({'symbol':symbol,'date':str(d.date()),'field':col,'old':v,'new':w})
            frame=pd.concat([old,new.loc[~new.index.isin(old.index)]]).sort_index()
        else:frame=new
        if frame.index.duplicated().any() or not frame.index.is_monotonic_increasing:raise ValueError('Duplicate clock')
        frame.index.name='date';frame['symbol']=symbol;frame['observed_bar']=True
        frame['volume_unit']='source_index_units';frame['amount_unit']='source_index_amount_units'
        frame['price_adjustment']='raw';frame['synthetic_event_bar']=False
        price=bridge.eligible_prices(frame).index
        frame['price_eligible']=frame.index.isin(price)
        frame['volume_eligible']=np.isfinite(frame.volume)&frame.volume.gt(0)
        frame['source_invalid']=~frame.price_eligible
        frames[symbol]=frame
        out=OUT/'bars'/f'{symbol}.parquet';frame.to_parquet(out)
        prices=frame[bridge.OHLC[0]]
        summary.append({'symbol':symbol,'market':row['market'],'name':row['industry_name'],
            'sector_id':row.get('block_code',row.get('industry_block_code')),
            'rows':len(frame),'first':str(frame.index[0].date()),'last':str(frame.index[-1].date()),
            'price_eligible_rows':int(frame.price_eligible.sum()),'positive_volume_rows':int(frame.volume_eligible.sum()),
            'price_rows_missing_or_nonpositive_volume':int((frame.price_eligible&~frame.volume_eligible).sum()),
            'invalid_price_rows':int((~frame.price_eligible).sum()),'end_reached':frame.index[-1]==pd.Timestamp('2026-10-22'),
            'source_start_before_target':frame.index[0]<=pd.Timestamp('2013-01-01'),
            'bars':evidence(out),'sources':sources,'checks':checks,
            'volume_unit':'source_index_units','price_adjustment':'raw','account_ready':False})
        all_sources+=sources
    calendars={market:pd.DatetimeIndex(sorted({d for r in summary if r['market']==market for d in frames[r['symbol']].index})) for market in ('A','H')}
    gaps=[];missing=[]
    for item in summary:
        symbol=item['symbol'];frame=frames[symbol];calendar=calendars[item['market']]
        gaps_here=[]
        for left,right in zip(frame.index[:-1],frame.index[1:]):
            days=(right-left).days
            omitted=calendar[(calendar>left)&(calendar<right)]
            if days>10 or len(omitted):
                gap={'symbol':symbol,'left':str(left.date()),'right':str(right.date()),'calendar_days':days,
                     'missing_other_same_market_dates':len(omitted),'candidate_source_break':days>20}
                gaps.append(gap);gaps_here.append(gap)
            if len(omitted):missing.append({'symbol':symbol,'left':str(left.date()),'right':str(right.date()),
                'dates':[str(x.date()) for x in omitted]})
        cuts=[x for x in gaps_here if x['candidate_source_break']]
        start=item['first'];segments=[]
        for gap in cuts:
            segments.append({'start':start,'end':gap['left'],'reason':'source break candidate; pending cross-node/continuity adjudication'})
            start=gap['right']
        segments.append({'start':start,'end':item['last'],'reason':'observed interval, not certified gap-free historical market calendar'})
        item['gaps_over_20_days']=cuts;item['proposed_segments']=segments
        item['missing_same_market_dates']=sum(x['missing_other_same_market_dates'] for x in gaps_here)
        item['continuity_status']='candidate_source_break' if cuts else 'no_long_gap_detected_not_exchange_certification'
        item['source_overlap_conflict_cells']=sum(x['symbol']==symbol for x in conflicts)
    uniq={x['path']:x for x in all_sources}
    save(OUT/'source-manifest.json',list(uniq.values()))
    save(OUT/'gaps.json',gaps);save(OUT/'missing-same-market-dates.json',missing);save(OUT/'overlap-conflicts.json',conflicts)
    save(OUT/'manifest.json',{'schema_version':1,'scope_date':'2026-10-22','series':summary,'account_runs':0,
        'algorithm_changes':0,'full_pool_closed':False,'sector_series_count':len(summary),
        'code_sha256':bridge.sha256(__file__),'protocol_sha256':bridge.sha256(OUT/'PROTOCOL.json'),
        'unit_limitation':'Unscaled THS index turnover units: within-series ratios only; no stock VWAP inference, share-count assertion or cross-industry volume ranking',
        'continuity_limitation':'Source coverage and actual listed/index existence differ; marked breaks require source decision before state use'})
    pd.DataFrame([{k:v for k,v in x.items() if k not in ('sources','checks','bars','proposed_segments','gaps_over_20_days')} for x in summary]).to_csv(OUT/'coverage.csv',index=False)
    print(json.dumps({'series':len(summary),'rows':sum(x['rows'] for x in summary),'conflict_cells':len(conflicts),
        'long_gap_series':sum(bool(x['gaps_over_20_days']) for x in summary),'invalid_prices':sum(x['invalid_price_rows'] for x in summary)}))

if __name__=='__main__':main()

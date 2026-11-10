"""Read original source inventory only; no FSM/account/price-path calculation."""
from pathlib import Path
from collections import Counter
import hashlib,json,time
import pandas as pd
import pyarrow.parquet as pq

O=Path(__file__).resolve().parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
PERIODS={'2022_2023':('2022-01-01','2023-12-31'),'2024_924':('2024-09-01','2024-12-31')}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,x):
    (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
allrows=sorted(json.loads(MANIFEST.read_text()),key=lambda r:r['symbol'])
selected=allrows[1::2]
records=[];sources={str(MANIFEST):sha(MANIFEST)}
started=time.monotonic()
for i,m in enumerate(selected):
    row={'symbol':m['symbol'],'manifest_sorted_index':2*i+1,'manifest_status':m['status'],
         'manifest_warm_from':m.get('warm_from'),'manifest_cache_through':m.get('cache_through')}
    if m['status']!='complete':
        row['status']='NOT_APPLICABLE_ORIGINAL_NO_LOCAL_OBSERVATION'
        records.append(row);continue
    refs=m['refs'];cp_path=Path(refs['CP1']);input_path=Path(refs['CP1_input'])
    price_path=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')))
    events_path=Path(next(p for p in m['source_sha256'] if p.endswith('/events.parquet')))
    required=[price_path,events_path,cp_path,input_path]
    missing=[str(p) for p in required if not p.is_file()]
    if missing:
        row.update(status='MISSING_ORIGINAL_SOURCE_FILE',missing_paths=missing);records.append(row);continue
    ps=pq.read_schema(price_path);cs=pq.read_schema(cp_path);ins=pq.read_schema(input_path)
    pcols=['observed_bar','price_eligible','source_invalid','synthetic_event_bar']
    absent=[c for c in ['open','high','low','close','segment_id']+pcols if c not in ps.names]
    if absent:
        row.update(status='MISSING_ORIGINAL_PRICE_FIELDS',missing_fields=absent);records.append(row);continue
    p=pd.read_parquet(price_path,columns=pcols)
    c=pd.read_parquet(cp_path,columns=['ready','receipt','e0_valid'])
    ev=pd.read_parquet(events_path,columns=['event'])
    row.update(status='ORIGINAL_INVENTORY_COMPLETE',source_paths={
        'price':str(price_path),'events':str(events_path),'CP1':str(cp_path),'CP1_input':str(input_path)},
        source_full_rows={'price':len(p),'events':len(ev),'CP1':len(c),'CP1_input':pq.ParquetFile(input_path).metadata.num_rows},
        source_date_bounds={'price':[str(p.index.min().date()),str(p.index.max().date())],
                            'events':[str(ev.index.min().date()),str(ev.index.max().date())],
                            'CP1':[str(c.index.min().date()),str(c.index.max().date())]},
        price_flag_nulls={k:int(p[k].isna().sum()) for k in pcols},
        price_flag_types={k:str(p[k].dtype) for k in pcols},
        input_fields_present=all(k in ins.names for k in ['close','amount','segment_id','e0_valid','i_floor']),periods={})
    for name,(a,b) in PERIODS.items():
        pp=p.loc[a:b];cc=c.loc[a:b];ee=ev.loc[a:b]
        known=pcols and pp[pcols].notna().all(axis=1)
        valid=known & pp.observed_bar.eq(True) & pp.price_eligible.eq(True) & pp.source_invalid.eq(False) & pp.synthetic_event_bar.eq(False)
        row['periods'][name]={'original_price_observations':len(pp),'explicit_known_price_flag_valid':int(valid.sum()),
            'explicit_unknown_price_flags':int((~known).sum()),'original_CP_observations':len(cc),
            'raw_CP_receipts':int(cc.receipt.eq(True).sum()),'raw_CP_ready_observations':int(cc.ready.eq(True).sum()),
            'raw_CP_e0_valid_observations':int(cc.e0_valid.eq(True).sum()),
            'original_E0_positive_events':int(ee.event.eq(1).sum()),'original_E0_negative_events':int(ee.event.eq(-1).sum()),
            'first_price_date':None if pp.empty else str(pp.index.min().date()),
            'last_price_date':None if pp.empty else str(pp.index.max().date())}
    records.append(row)
    if (i+1)%100==0:print(json.dumps({'inventory_progress':i+1,'stocks':len(selected),'seconds':round(time.monotonic()-started,3)}),flush=True)
summary={'status':'SOURCE_INVENTORY_ONLY_COMPLETE','manifest_records':len(allrows),'shard':'sorted_symbol index % 2 == 1',
    'selected_stocks':len(selected),'manifest_status_counts':dict(Counter(r['manifest_status'] for r in records)),
    'inventory_status_counts':dict(Counter(r['status'] for r in records)),
    'periods':{},'original_cache_through_counts':dict(Counter(str(r.get('manifest_cache_through')) for r in records)),
    'new_FSM_runs':0,'new_accounts':0,'new_quantities':0,'new_returns':0,
    'limitations':['Counts are original source observations and CP receipts, not candidate events or trades.',
                   'Completely absent market sessions are not detected from these files; calendar completeness is not verified.',
                   'Missing halt/limit/ST/orderbook/receive-time fields are not reconstructed.'],
    'manifest_sha256':sources[str(MANIFEST)],'script_sha256':sha(__file__),'seconds':time.monotonic()-started}
for name in PERIODS:
    rr=[r['periods'][name] for r in records if r['status']=='ORIGINAL_INVENTORY_COMPLETE']
    keys=['original_price_observations','explicit_known_price_flag_valid','explicit_unknown_price_flags',
          'original_CP_observations','raw_CP_receipts','raw_CP_ready_observations','raw_CP_e0_valid_observations',
          'original_E0_positive_events','original_E0_negative_events']
    summary['periods'][name]={k:sum(x[k] for x in rr) for k in keys}
    summary['periods'][name]['stocks_with_original_price_observations']=sum(x['original_price_observations']>0 for x in rr)
    summary['periods'][name]['stocks_with_raw_CP_receipts']=sum(x['raw_CP_receipts']>0 for x in rr)
write('ORIGINAL_SOURCE_INVENTORY.json',records);write('INVENTORY_SUMMARY.json',summary)
write('SHARD_SYMBOLS.json',[r['symbol'] for r in selected])
print(json.dumps(summary,ensure_ascii=False),flush=True)

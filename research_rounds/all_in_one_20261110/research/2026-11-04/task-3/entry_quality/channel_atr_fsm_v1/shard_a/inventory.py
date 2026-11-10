"""Shard-A source/date/receipt inventory; no OHLC indicators or account model."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
import time
import pandas as pd
import pyarrow.parquet as pq

OUT = Path(__file__).resolve().parent
MANIFEST = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
FREEZE = OUT.parent / 'FREEZE.md'
END = pd.Timestamp('2026-06-30')
PERIODS = [('2022_2023', '2022-01-01', '2023-12-31'),
           ('2024_Sep_Dec', '2024-09-01', '2024-12-31')]
PRICE_REQUIRED = {'open','high','low','close','adjustment_factor','segment_id','price_eligible',
                  'observed_bar','synthetic_event_bar','source_invalid'}
CP_REQUIRED = {'ready','receipt','candidate','e0_valid','e0_floor'}
FLAGS = ['price_eligible','observed_bar','synthetic_event_bar','source_invalid']

def schema_info(path, required):
    p = Path(path)
    if not p.exists(): return {'exists': False, 'missing_fields': sorted(required), 'path': str(p)}
    pf = pq.ParquetFile(p)
    return {'exists': True, 'rows_file': pf.metadata.num_rows,
            'missing_fields': sorted(required-set(pf.schema.names)),
            'columns': pf.schema.names, 'path': str(p)}

def inspect(item):
    index, row = item
    sid = row['symbol']
    result = {'sid': sid, 'sorted_universe_index_zero_based': index,
              'manifest_status': row['status'], 'cache_through_claim': row.get('cache_through'),
              'periods': {}}
    try:
        signal = [p for p in row['source_sha256'] if p.endswith('/signal.parquet')]
        event = [p for p in row['source_sha256'] if p.endswith('/events.parquet')]
        if len(signal) != 1 or len(event) != 1:
            raise ValueError(f'unique original source files required: {signal}/{event}')
        result['original_refs'] = {'signal': signal[0], 'events': event[0], **row['refs']}
        result['declared_source_sha256'] = row['source_sha256']
        result['declared_output_sha256'] = row['output_sha256']
        result['signal_schema'] = schema_info(signal[0], PRICE_REQUIRED)
        result['event_schema'] = schema_info(event[0], {'event','confirmed_pivot_price','segment_id'})
        result['CP_schema'] = schema_info(row['refs']['CP1'], CP_REQUIRED)
        result['CP_input_schema'] = schema_info(row['refs']['CP1_input'], {'close','segment_id','i_target','i_floor'})
        if any(not result[k]['exists'] or result[k]['missing_fields'] for k in
               ['signal_schema','event_schema','CP_schema','CP_input_schema']):
            raise ValueError('required schema unavailable; see per-file fields')
        # Read only dates/mask flags and original receipt/ready booleans.
        p = pd.read_parquet(signal[0], columns=FLAGS)
        full_source_rows = len(p)
        p = p.loc[:END]
        cp = pd.read_parquet(row['refs']['CP1'], columns=['receipt','ready']).loc[:END]
        result.update(source_rows_through_cutoff=len(p), CP_rows_through_cutoff=len(cp),
                      source_rows_after_cutoff_ignored=full_source_rows-len(p),
                      source_first=None if p.empty else str(p.index.min().date()),
                      source_last=None if p.empty else str(p.index.max().date()),
                      CP_first=None if cp.empty else str(cp.index.min().date()),
                      CP_last=None if cp.empty else str(cp.index.max().date()),
                      unknown_boolean_cells_through_cutoff=int(p[FLAGS].isna().sum().sum()),
                      source_dates_without_original_CP=len(p.index.difference(cp.index)),
                      original_CP_dates_without_source=len(cp.index.difference(p.index)))
        declared = p.price_eligible.eq(True) & p.observed_bar.eq(True) & p.synthetic_event_bar.eq(False) & p.source_invalid.eq(False)
        for name, start, stop in PERIODS:
            ps, cs = p.loc[start:stop], cp.loc[start:stop]
            result['periods'][name] = {'source_date_rows': len(ps),
                'source_declared_mask_eligible_rows_not_HLC_validated': int(declared.reindex(ps.index).sum()),
                'original_CP_observations': len(cs),
                'original_CP_ready': int(cs.ready.eq(True).sum()),
                'original_raw_CP_receipts': int(cs.receipt.eq(True).sum()),
                'original_receipt_dates_not_in_source': cs.index[cs.receipt.eq(True)].difference(ps.index).strftime('%Y-%m-%d').tolist()}
        result['status'] = 'INVENTORIED'
    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = f'{type(e).__name__}: {e}'
    return result

t0 = time.monotonic()
all_rows = sorted(json.loads(MANIFEST.read_text()), key=lambda x: x['symbol'])
assert len(all_rows) == 1709 and len({x['symbol'] for x in all_rows}) == 1709
selected = [(i, x) for i, x in enumerate(all_rows) if i % 2 == 0]
with ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(inspect, selected))
(OUT / 'INVENTORY.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
(OUT / 'SYMBOLS.json').write_text(json.dumps([x['symbol'] for _, x in selected], indent=2)+'\n')
flat = []
for x in rows:
    r = {k: x.get(k) for k in ['sid','sorted_universe_index_zero_based','manifest_status','status',
         'source_rows_through_cutoff','CP_rows_through_cutoff','source_first','source_last','CP_first','CP_last',
         'source_dates_without_original_CP','original_CP_dates_without_source','unknown_boolean_cells_through_cutoff','error']}
    for p, v in x.get('periods', {}).items():
        r.update({p+'__'+k: val for k, val in v.items() if not isinstance(val,list)})
    flat.append(r)
pd.DataFrame(flat).to_csv(OUT / 'INVENTORY.csv', index=False)
good = [x for x in rows if x['status']=='INVENTORIED']
summary = {'shard': 'A', 'rule': 'sorted original STOCK_MANIFEST symbol, zero-based even index',
    'whole_manifest_rows': len(all_rows), 'whole_manifest_status_counts': dict(Counter(x['status'] for x in all_rows)),
    'shard_rows': len(rows), 'shard_manifest_status_counts': dict(Counter(x['manifest_status'] for x in rows)),
    'inventory_status_counts': dict(Counter(x['status'] for x in rows)),
    'source_rows_through_2026Jun30': sum(x['source_rows_through_cutoff'] for x in good),
    'original_CP_rows_through_2026Jun30': sum(x['CP_rows_through_cutoff'] for x in good),
    'source_first': min((x['source_first'] for x in good if x['source_first']),default=None),
    'source_last': max((x['source_last'] for x in good if x['source_last']),default=None),
    'unknown_boolean_cells': sum(x['unknown_boolean_cells_through_cutoff'] for x in good),
    'symbols_with_source_dates_without_CP': sum(x['source_dates_without_original_CP']>0 for x in good),
    'symbols_with_CP_dates_without_source': sum(x['original_CP_dates_without_source']>0 for x in good),
    'periods': {}, 'seconds': time.monotonic()-t0,
    'source_inventory_only': True, 'OHLC_values_and_full_calendar_missing_sessions_not_yet_validated': True,
    'source_file_SHA_current_bytes_not_yet_verified': True,
    'missing_external_fields': ['historical_ST','dated_legal_limits','confirmed_suspension_state','intraday_orderbook','publication_received_at'],
    'FSM_runs': 0, 'pair_runs': 0, 'new_accounts': 0, 'new_quantities': 0,
    'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
    'freeze_sha256': hashlib.sha256(FREEZE.read_bytes()).hexdigest()}
for name, _, _ in PERIODS:
    summary['periods'][name] = {
        'symbols_with_any_source_date': sum(x['periods'][name]['source_date_rows']>0 for x in good),
        'symbols_with_any_original_CP_observation': sum(x['periods'][name]['original_CP_observations']>0 for x in good),
        'symbols_with_any_original_CP_receipt': sum(x['periods'][name]['original_raw_CP_receipts']>0 for x in good),
        **{k:sum(x['periods'][name][k] for x in good) for k in
           ['source_date_rows','source_declared_mask_eligible_rows_not_HLC_validated','original_CP_observations','original_CP_ready','original_raw_CP_receipts']}}
(OUT / 'INVENTORY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))

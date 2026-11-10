"""Extract original OHLC/factor inputs, without channel/ATR or account models."""
from pathlib import Path
import json
import hashlib
import math
import pandas as pd
import numpy as np

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3')
OUT = Path(__file__).resolve().parent
PM = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
BRIDGE = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py')
RULES = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
SID = '000620.SZ'
DAYS = ['2022-01-06', '2022-01-07', '2022-01-14', '2022-01-17', '2022-01-20',
        '2022-01-21', '2022-01-24', '2022-01-25', '2022-01-26', '2022-02-07']

def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if isinstance(v, pd.Timestamp): return str(v.date())
    if v is None or v is pd.NA: return None
    if isinstance(v, np.generic): v = v.item()
    return None if isinstance(v, float) and not math.isfinite(v) else v

def dump(name, value):
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')

rec = next(x for x in json.loads(PM.read_text())['series'] if x['series_id'] == SID)
stock = next(x for x in json.loads(SM.read_text()) if x['symbol'] == SID)
signal_path = next(Path(x) for x in stock['source_sha256'] if x.endswith('/signal.parquet'))
raw_path = Path(rec['raw']['path'])
actions_path = Path(rec['adjustment']['actions']['path'])
signal = pd.read_parquet(signal_path)
raw = pd.read_parquet(raw_path).set_index('trade_date')
facts_path = Path(stock['refs']['facts'])
facts = pd.read_parquet(facts_path)
cols = ['open', 'high', 'low', 'close', 'raw_open', 'raw_high', 'raw_low', 'raw_close',
        'adjustment_factor', 'volume_factor', 'segment_id', 'volume', 'amount', 'price_eligible',
        'observed_bar', 'synthetic_event_bar', 'source_invalid', 'quality_status', 'observed_at']
prefix = signal.loc[:'2022-02-07', cols].copy()
prefix['previous_source_close_adjusted'] = prefix.groupby('segment_id', sort=False).close.shift()
prefix['previous_source_close_raw'] = prefix.groupby('segment_id', sort=False).raw_close.shift()
prefix.to_csv(OUT / 'ORIGINAL_OHLC_FULL_PREFIX.csv', index_label='day')
key = []
for ds in DAYS:
    d = pd.Timestamp(ds)
    z = prefix.loc[d]
    n = raw.loc[d]
    record = {'sid': SID, 'day': ds, 'signal_source': z.to_dict(),
              'native_raw_source': n.to_dict(),
              'raw_OHLC_exact_equal': {c: float(z['raw_' + c]) == float(n[c]) for c in ['open', 'high', 'low', 'close']},
              'adjusted_C_equals_original_No60_fact': float(z.close) == float(facts.loc[d, 'close']),
              'factor_equals_original_No60_fact': float(z.adjustment_factor) == float(facts.loc[d, 'factor'])}
    key.append(record)
dump('KEY_OHLC_INPUTS.json', key)
pd.DataFrame([{'day': x['day'], **x['signal_source']} for x in key]).to_csv(OUT / 'KEY_OHLC_INPUTS.csv', index=False)
actions = json.loads(actions_path.read_text())
sources = [PM, SM, BRIDGE, RULES, raw_path, signal_path, facts_path, actions_path, Path(__file__).resolve()]
dump('SOURCE_MANIFEST.json', {'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                              'raw_record': rec, 'signal_path': str(signal_path),
                              'source_only_no_channel_ATR_computation': True})
dump('SOURCE_CHECKS.json', {
    'sid': SID, 'source_rows_through_Feb7': len(prefix),
    'source_start': str(prefix.index.min().date()), 'source_end': str(prefix.index.max().date()),
    'requested_rows': len(key), 'all_requested_raw_OHLC_exact': all(all(x['raw_OHLC_exact_equal'].values()) for x in key),
    'all_requested_adjusted_C_matches_No60': all(x['adjusted_C_equals_original_No60_fact'] for x in key),
    'all_requested_factors_match_No60': all(x['factor_equals_original_No60_fact'] for x in key),
    'factors_2021Oct_through_2022Feb7': prefix.loc['2021-10-01':].adjustment_factor.unique().tolist(),
    'first_source_factor': float(prefix.adjustment_factor.iloc[0]),
    'actions_in_2021Oct_through_2022Feb7': [x for x in actions['events'] if '2021-10-01' <= x['effective_date'] <= '2022-02-07'],
    'original_raw_columns': list(raw.columns),
    'not_saved': ['historical_ST_status', 'dated_legal_price_limit_bounds', 'tick_size',
                  'suspension_state', 'intraday_orderbook', 'actual_publication_received_at'],
    'raw_observed_at_on_requested_rows': [x['native_raw_source'].get('observed_at') for x in key],
    'channel_computations': 0, 'ATR_computations': 0, 'new_accounts': 0, 'new_quantities': 0,
})
print(json.dumps(clean({'rows': len(prefix), 'days': DAYS, 'factor': prefix.loc[DAYS[0], 'adjustment_factor'],
                       'all_raw_exact': all(all(x['raw_OHLC_exact_equal'].values()) for x in key)}), indent=2))

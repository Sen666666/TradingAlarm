"""Apply the parent's unique frozen market-only helper; no account imports."""
from pathlib import Path
import importlib.util
import hashlib
import json
import math
import pandas as pd
import numpy as np

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3')
OUT = Path(__file__).resolve().parent
BASE = OUT.parent
HELPER = BASE / 'balance.py'
FREEZE = BASE / 'FREEZE.md'
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
PREPARED = OUT / 'ORIGINAL_WINDOW_DAILY.json'
ROWS = ROOT / 'entry_quality/structural_failure_v1/state_semantics/2022_2024_ROWS.json'

def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if isinstance(v, pd.Timestamp): return str(v.date())
    if v is None or v is pd.NA: return None
    if isinstance(v, np.generic): v = v.item()
    return None if isinstance(v, float) and not math.isfinite(v) else v

def dump(name, v):
    (OUT / name).write_text(json.dumps(clean(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')

spec = importlib.util.spec_from_file_location('frozen_effective_progress_helper', HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
manifest = json.loads(SM.read_text())
prepared = {(x['sid'], x['day']): x for x in json.loads(PREPARED.read_text())}
original_rows = json.loads(ROWS.read_text())
sources = {HELPER, FREEZE, SM, PREPARED, ROWS, Path(__file__).resolve()}
scope = [('000620.SZ', '2022-01-01', '2022-01-31'),
         ('002583.SZ', '2024-01-01', '2024-01-31'),
         ('002583.SZ', '2024-09-01', '2024-11-30')]
key_days = {'000620.SZ': ['2022-01-20', '2022-01-21', '2022-01-24', '2022-01-25'],
            '002583.SZ': ['2024-09-20', '2024-09-30', '2024-10-11', '2024-10-18',
                          '2024-10-21', '2024-11-20', '2024-11-28', '2024-11-29']}
daily, summaries, prefixes = [], [], []
prefix_check = None
for sid in key_days:
    refs = next(x for x in manifest if x['symbol'] == sid)['refs']
    cp_path, q_path = Path(refs['CP1']), Path(refs['CP1_input'])
    sources.update([cp_path, q_path])
    end = '2022-01-31' if sid == '000620.SZ' else '2024-11-30'
    cp = pd.read_parquet(cp_path).loc[:end].copy()
    cp_input = pd.read_parquet(q_path).loc[cp.index].copy()
    assert cp.index.equals(cp_input.index)
    result = helper.calculate(cp, cp_input)
    cp.add_prefix('original_CP_').join(cp_input.add_prefix('input_')).join(result).to_csv(
        OUT / (sid.replace('.', '_') + '_FROZEN_BALANCE_FULL_PREFIX.csv'), index_label='day')
    prefixes.append({'sid': sid, 'first': str(cp.index.min().date()), 'last': str(cp.index.max().date()),
                     'observations': len(cp), 'helper_calls': 1})
    if sid == '002583.SZ':
        cut = pd.Timestamp('2024-10-18')
        truncated_cp = cp.loc[:cut].copy()
        truncated_input = cp_input.loc[:cut].copy()
        short = helper.calculate(truncated_cp, truncated_input)
        # Actual independent helper call with the later source rows removed.
        expected = result.loc[short.index]
        exact = short.equals(expected)
        prefix_check = {'sid': sid, 'cutoff': str(cut.date()), 'full_source_observations': len(cp),
                        'truncated_source_observations': len(short), 'helper_rerun_on_truncated_inputs': True,
                        'all_output_fields_and_all_common_rows_exact': exact,
                        'scope': 'Frozen balance helper only; original CP is read cached, not recalculated.'}
        assert exact
    for s, start, stop in scope:
        if s != sid: continue
        view = result.loc[start:stop]
        raw = cp.loc[view.index]
        accepted = raw.index[raw.receipt & view.effective_advance]
        rejected = raw.index[raw.receipt & ~view.effective_advance]
        summaries.append({'sid': sid, 'start': start, 'end': stop, 'observations': len(view),
                          'original_receipts': int(raw.receipt.sum()), 'effective_receipts': int(view.effective_advance.sum()),
                          'accepted_original_receipt_days': accepted.strftime('%Y-%m-%d').tolist(),
                          'rejected_original_receipt_days': rejected.strftime('%Y-%m-%d').tolist(),
                          'first_original_receipt': None if not raw.receipt.any() else str(raw.index[raw.receipt][0].date()),
                          'first_effective_receipt': None if len(accepted) == 0 else str(accepted[0].date())})
        for day, z in view.iterrows():
            ds = str(day.date())
            original = prepared[(sid, ds)]
            item = {'sid': sid, 'day': ds, 'C_adjusted': original['original_CP_generator_input']['close'],
                    'C_raw': original['original_facts']['raw_close'],
                    'original_CP': original['original_CP'], 'original_CP_input': original['original_CP_generator_input'],
                    'fixed_balance': clean(z.to_dict()),
                    'original_actual_fills_annotations_only': [
                        {k: x.get(k) for k in ['layer', 'role', 'signal_day', 'opened', 'action',
                                              'quantity_before_actual_buy', 'actual_fill_quantity', 'receipt',
                                              'original_stock_state']}
                        for x in original_rows if x['sid'] == sid and x['signal_day'] == ds]}
            daily.append(item)

assert len(daily) == 99
daily.sort(key=lambda x: (x['sid'], x['day']))
dump('FROZEN_BALANCE_WINDOW_DAILY.json', daily)
flat = []
for x in daily:
    flat.append({'sid': x['sid'], 'day': x['day'], 'C_adjusted': x['C_adjusted'], 'C_raw': x['C_raw'],
                 'r': x['original_CP']['r'], 'm': x['original_CP']['m'],
                 'delta_frontier': x['original_CP']['delta_frontier'], 'used_scale': x['original_CP']['scale'],
                 'original_receipt': x['original_CP']['receipt'], 'original_reset': x['original_CP']['reset_reason'],
                 **x['fixed_balance']})
pd.DataFrame(flat).to_csv(OUT / 'FROZEN_BALANCE_WINDOW_DAILY.csv', index=False)
dump('KEY_DAYS.json', [x for x in daily if x['day'] in key_days[x['sid']]])
dump('ALL_ORIGINAL_RECEIPTS_PASS_REJECT.json', [x for x in daily if x['original_CP']['receipt']])
dump('FROZEN_SUMMARY.json', {'status': 'FIXED_BALANCE_MARKET_SIGNAL_ONLY', 'windows': summaries,
                            'original_receipts_total': sum(x['original_receipts'] for x in summaries),
                            'effective_receipts_total': sum(x['effective_receipts'] for x in summaries),
                            'prefixes': prefixes, 'real_truncation_check': prefix_check,
                            'helper_sha256': hashlib.sha256(HELPER.read_bytes()).hexdigest(),
                            'freeze_sha256': hashlib.sha256(FREEZE.read_bytes()).hexdigest(),
                            'new_accounts': 0, 'new_quantities': 0, 'new_returns': 0, 'new_CP_calculations': 0,
                            'parameter_searches': 0})
dump('FROZEN_RUN_SOURCE_MANIFEST.json', {'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
                                       'helper_calls': 3, 'fullprefix_calls': 2, 'truncated_prefix_calls': 1,
                                       'account_imports': 0, 'new_orders': 0})
print(json.dumps(clean({'windows': summaries, 'prefix_check': prefix_check,
                       'helper_sha256': hashlib.sha256(HELPER.read_bytes()).hexdigest()}), ensure_ascii=False, indent=2))

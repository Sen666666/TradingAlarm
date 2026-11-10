"""Copy existing CP/source fields; do not calculate the candidate balance."""
from pathlib import Path
import hashlib
import json
import math
import pandas as pd
import numpy as np

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3')
OUT = Path(__file__).resolve().parent
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
MODEL = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
V4 = ROOT / 'entry_quality/e0_i_structure_redesign_v1/signal_traces_v4/v4_two_stock'

def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if isinstance(v, pd.Timestamp): return str(v.date())
    if v is None or v is pd.NA: return None
    if isinstance(v, np.generic): v = v.item()
    return None if isinstance(v, float) and not math.isfinite(v) else v

def dump(name, value):
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')

manifest = json.loads(SM.read_text())
sources = {SM, MODEL, Path(__file__).resolve()}
scopes = [('000620.SZ', '2022-01-01', '2022-01-31'),
          ('002583.SZ', '2024-01-01', '2024-01-31'),
          ('002583.SZ', '2024-09-01', '2024-11-30')]
summary, all_window, prefix_status, receipt_paths = [], [], [], []
for sid in ['000620.SZ', '002583.SZ']:
    row = next(x for x in manifest if x['symbol'] == sid)
    refs = {k: Path(v) for k, v in row['refs'].items()}
    sources.update([refs['CP1'], refs['CP1_input'], refs['facts']])
    cp = pd.read_parquet(refs['CP1'])
    inp = pd.read_parquet(refs['CP1_input'])
    facts = pd.read_parquet(refs['facts'])
    end = '2022-01-31' if sid == '000620.SZ' else '2024-11-30'
    prefix = cp.loc[:end].copy()
    data = prefix.add_prefix('CP_').join(inp.add_prefix('input_'), how='left').join(facts.add_prefix('facts_'), how='left')
    # Original amount-median B is deliberately named CP_B: it is not the proposed balance B_t.
    data.index.name = 'day'
    data.to_csv(OUT / (sid.replace('.', '_') + '_ORIGINAL_FULL_PREFIX.csv'))
    v4path = V4 / (sid.replace('.', '_') + '_DAILY.json')
    sources.add(v4path)
    saved_v4 = {x['day']: x for x in json.loads(v4path.read_text())}
    missing = facts.loc[:end].index.difference(prefix.index)
    prefix_status.append({
        'sid': sid, 'original_CP_start': str(prefix.index.min().date()),
        'original_CP_end': str(prefix.index.max().date()), 'original_CP_observations': len(prefix),
        'generator_input_missing_CP_dates': prefix.index.difference(inp.index).strftime('%Y-%m-%d').tolist(),
        'facts_dates_without_original_CP': missing.strftime('%Y-%m-%d').tolist(),
        'original_CP_unready_observations': int((~prefix.ready).sum()),
        'original_CP_source_reset_days': prefix.index[prefix.reset_reason.eq('source_reset')].strftime('%Y-%m-%d').tolist(),
        'input_segment_boundary_days_including_first': inp.loc[:end].index[inp.loc[:end].segment_id.ne(inp.loc[:end].segment_id.shift())].strftime('%Y-%m-%d').tolist(),
        'reset_reason_is_not_exhaustive_for_source_change': True,
        'fresh_positive_and_negative_r_same_day': int(((prefix.delta_frontier > 0) & (prefix.r < 0)).sum()),
        'candidate_not_computed': True,
    })
    # Pure original-path diagnostic: downside since the preceding CP reset/receipt.
    # This is not the proposed decaying balance or an effective-receipt simulation.
    negatives = []
    anchor_day = None
    for day, z in prefix.iterrows():
        reason = None if pd.isna(z.reset_reason) else str(z.reset_reason)
        if reason in {'unprepared', 'E0_invalid', 'E0_down_reset', 'start', 'lower_anchor', 'source_reset'}:
            negatives = []
            anchor_day = str(day.date())
        if math.isfinite(float(z.r)) and z.r < 0:
            negatives.append({'day': str(day.date()), 'r': float(z.r)})
        if z.receipt:
            if any(s == sid and start <= str(day.date()) <= stop for s, start, stop in scopes):
                receipt_paths.append({'sid': sid, 'day': str(day.date()), 'original_reset_or_receipt_anchor_day': anchor_day,
                                      'negative_CP_observations_since_that_anchor': negatives.copy(),
                                      'negative_log_sum': -sum(x['r'] for x in negatives),
                                      'original_scale': float(z.scale), 'original_credit': float(z.credit),
                                      'original_delta_frontier': float(z.delta_frontier)})
            negatives = []
            anchor_day = str(day.date())
    for s, start, stop in scopes:
        if s != sid: continue
        view = prefix.loc[start:stop]
        current = []
        for day, z in view.iterrows():
            ds = str(day.date())
            old = clean(z.to_dict())
            original_input = clean(inp.loc[day].to_dict()) if day in inp.index else None
            original_fact = clean(facts.loc[day].to_dict()) if day in facts.index else None
            sv4 = saved_v4.get(ds)
            item = {'sid': sid, 'day': ds, 'original_CP': old, 'original_CP_generator_input': original_input,
                    'original_facts': original_fact,
                    'saved_CP_star': None if sv4 is None else sv4['CP_star'],
                    'saved_V3_I_hold': None if sv4 is None else sv4['V3']['I_hold'],
                    'saved_V3_I_mature': None if sv4 is None else sv4['V3']['I_expand'],
                    'CP_star_status': 'NOT_SAVED_IN_REUSED_V4_DISPLAY' if sv4 is None else sv4['CP_input_status']}
            current.append(item)
        all_window.extend(current)
        summary.append({'sid': sid, 'start': start, 'end': stop, 'original_CP_observations': len(view),
                        'negative_r_days': int((view.r < 0).sum()), 'downside_log_sum': float(-view.r.clip(upper=0).sum()),
                        'original_receipts': int(view.receipt.sum()),
                        'original_receipt_days': view.index[view.receipt].strftime('%Y-%m-%d').tolist(),
                        'original_reset_reason_counts': view.reset_reason.value_counts().to_dict(),
                        'input_missing_days': view.index.difference(inp.index).strftime('%Y-%m-%d').tolist(),
                        'missing_saved_CP_star_days': [x['day'] for x in current if x['saved_CP_star'] is None]})

dump('ORIGINAL_WINDOW_DAILY.json', all_window)
flat = []
for x in all_window:
    flat.append({'sid': x['sid'], 'day': x['day'], **{'CP_' + k: v for k, v in x['original_CP'].items()},
                 **{'input_' + k: v for k, v in (x['original_CP_generator_input'] or {}).items()},
                 **{'facts_' + k: v for k, v in (x['original_facts'] or {}).items()},
                 'saved_CPstar_receipt': None if x['saved_CP_star'] is None else x['saved_CP_star']['receipt'],
                 'saved_V3_I_hold': x['saved_V3_I_hold'], 'saved_V3_I_mature': x['saved_V3_I_mature'],
                 'CPstar_status': x['CP_star_status']})
pd.DataFrame(flat).to_csv(OUT / 'ORIGINAL_WINDOW_DAILY.csv', index=False)
dump('SUMMARY.json', {'status': 'ORIGINAL_SOURCE_PREPARATION_NO_CANDIDATE_EXECUTION',
                      'windows': summary, 'prefixes': prefix_status,
                      'original_receipt_path_diagnostics': receipt_paths,
                      'candidate_B_computed': False, 'new_CP_calculations': 0, 'new_accounts': 0, 'new_quantities': 0})
dump('SOURCE_MANIFEST.json', {'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
                              'strategy_imports': 0, 'account_replays': 0, 'candidate_executions': 0})
print(json.dumps(clean({'windows': summary, 'prefixes': prefix_status}), ensure_ascii=False, indent=2))

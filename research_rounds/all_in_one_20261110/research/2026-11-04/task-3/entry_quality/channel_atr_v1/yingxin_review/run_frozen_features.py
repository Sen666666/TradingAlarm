"""Frozen OHLC indicators and conditional paper-line diagnostics, no account."""
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
HELPER = BASE / 'indicators.py'
SPEC = BASE / 'PAPER_SPEC.md'
SIGNAL = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/000072/signal.parquet')
FACTS = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/facts/000620.SZ.parquet')
LAUNCH = pd.Timestamp('2022-01-06')
DAYS = ['2022-01-06', '2022-01-07', '2022-01-14', '2022-01-17', '2022-01-20',
        '2022-01-21', '2022-01-24', '2022-01-25', '2022-01-26', '2022-02-07']

def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if isinstance(v, pd.Timestamp): return str(v.date())
    if v is None or v is pd.NA: return None
    if isinstance(v, np.generic): v = v.item()
    return None if isinstance(v, float) and not math.isfinite(v) else v

def dump(name, v):
    (OUT / name).write_text(json.dumps(clean(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')

spec = importlib.util.spec_from_file_location('fixed_channel_atr_indicators', HELPER)
ind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ind)
price = pd.read_parquet(SIGNAL).loc[:'2022-02-07'].copy()
facts = pd.read_parquet(FACTS).reindex(price.index)
f = ind.features(price)
price[['open', 'high', 'low', 'close', 'adjustment_factor', 'raw_open', 'raw_high', 'raw_low', 'raw_close',
       'segment_id', 'price_eligible', 'observed_bar', 'synthetic_event_bar', 'source_invalid']].join(f).to_csv(
    OUT / 'FROZEN_FEATURES_FULL_PREFIX.csv', index_label='day')

first = []
milestones = []
for L in [20, 55]:
    post = f.loc[LAUNCH:]
    dates = post.index[post['break' + str(L)].eq(True)]
    if not len(dates):
        first.append({'L': L, 'first_break': None})
        continue
    day = dates[0]
    A, S = float(price.loc[day, 'close']), float(f.loc[day, 'ATR14_prior'])
    factor = float(price.loc[day, 'adjustment_factor'])
    first.append({'L': L, 'first_break': str(day.date()), 'A_adjusted': A, 'A_raw': A / factor,
                  'S_adjusted': S, 'S_raw_at_break': S / factor,
                  'U_adjusted': float(f.loc[day, 'U' + str(L)]),
                  'U_raw_at_break': float(f.loc[day, 'U' + str(L)]) / factor,
                  'z': float(f.loc[day, 'z' + str(L)])})
    frontier, consumed = A, 0
    for stamp, row in price.loc[day:].iterrows():
        C, old_frontier = float(row.close), frontier
        fresh = ind.gt(C, old_frontier)
        frontier = max(frontier, C)
        j = math.floor((frontier - A) / S)
        event = 'CHANNEL_CONFIRM' if stamp == day else 'ATR_NET_ADVANCE' if fresh and j > consumed else None
        if event: consumed = j
        milestones.append({'L': L, 'day': str(stamp.date()), 'C_adjusted': C, 'C_raw': float(row.raw_close),
                           'A_fixed_adjusted': A, 'S_fixed_adjusted': S, 'frontier_before': old_frontier,
                           'frontier_after': frontier, 'j': j, 'j_consumed': consumed, 'event': event,
                           'current_channel_break': clean(f.loc[stamp, 'break' + str(L)]),
                           'original_I_target': clean(facts.loc[stamp, 'i_target']),
                           'scope': 'Market milestone if Jan7 latch remains valid; no actual holding, exit, or permission inferred.'})

key = []
for ds in DAYS:
    stamp = pd.Timestamp(ds)
    p, z = price.loc[stamp], f.loc[stamp]
    factor = float(p.adjustment_factor)
    prior = price.loc[LAUNCH:stamp].iloc[:-1]
    peak = None if prior.empty else float(prior.high.max())
    ap = float(z.ATR14_prior)
    trials = []
    for N in [2, 3, 4]:
        line = None if peak is None else peak - N * ap
        trials.append({'N': N, 'raw_component_adjusted': line,
                       'raw_component_in_current_raw_units': None if line is None else line / factor,
                       'comparison': 'NO_PRIOR_PEAK_ON_LAUNCH' if line is None else
                                     'GE_C_NEW_PROPOSAL_INVALID_IF_OLD_LINE_NOT_ALREADY_TRIGGERED' if line >= p.close else
                                     'BELOW_C_RAW_COMPONENT_ONLY_NOT_INSTALLED_LINE',
                       'not_final_Q': 'Final Q=max(P_old, I_hard_floor_old, component); old-line check precedes Q. '
                                      'No prior hypothetical P_old is invented and no decreasing component is installed.'})
    key.append({'sid': '000620.SZ', 'day': ds, 'launch': str(LAUNCH.date()),
                'C_adjusted': float(p.close), 'C_raw': float(p.raw_close), 'factor': factor,
                **clean(z.to_dict()),
                'U20_raw': float(z.U20) / factor, 'U55_raw': float(z.U55) / factor,
                'ATR14_prior_raw': ap / factor, 'known_peak_before_t_adjusted': peak,
                'known_peak_before_t_raw': None if peak is None else peak / factor,
                'N_paper_comparisons': trials,
                'original_I_target': clean(facts.loc[stamp, 'i_target']),
                'original_I_floor_adjusted': clean(facts.loc[stamp, 'i_floor'])})
dump('FROZEN_KEY_10_DAYS.json', key)
pd.DataFrame([{k: x[k] for k in ['day', 'C_adjusted', 'C_raw', 'U20', 'U55', 'ATR14_prior',
                               'U20_raw', 'U55_raw', 'ATR14_prior_raw', 'z20', 'z55', 'break20', 'break55',
                               'known_peak_before_t_raw', 'original_I_target']}
              for x in key]).to_csv(OUT / 'FROZEN_KEY_10_DAYS.csv', index=False)
dump('FIRST_BREAK_AND_FIXED_MILESTONES.json', {'launch': str(LAUNCH.date()), 'first_breaks': first,
                                             'conditional_market_milestones': milestones})
launchC = float(price.loc[LAUNCH, 'close'])
launchATR = float(f.loc[LAUNCH, 'ATR14_prior'])
early = price.loc[LAUNCH:]
hits = early.index[(early.close - launchC) >= 2 * launchATR]
dump('FROZEN_FEATURE_RUN_RECEIPT.json', {
    'status': 'FROZEN_INDICATORS_AND_POINTWISE_PAPER_COMPONENTS_ONLY', 'source_rows': len(price),
    'source_first': str(price.index.min().date()), 'source_last': str(price.index.max().date()),
    'fixed_launch': str(LAUNCH.date()), 'key_rows': len(key), 'first_breaks': first,
    'early_2ATR_diagnostic_only': {'launch_C': launchC, 'launch_ATRprior': launchATR,
                                 'first_hit': None if len(hits) == 0 else str(hits[0].date()),
                                 'not_a_primary_OR_permission': True},
    'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in [HELPER, SPEC, SIGNAL, FACTS, Path(__file__).resolve()]},
    'no_hypothetical_Pold_or_fills_generated': True,
    'new_accounts': 0, 'new_quantities': 0, 'new_returns': 0, 'parameter_selection': False})
print(json.dumps(clean({'first_breaks': first, 'early_first_hit': None if len(hits) == 0 else str(hits[0].date()),
                       'helper_sha256': hashlib.sha256(HELPER.read_bytes()).hexdigest()}), indent=2))

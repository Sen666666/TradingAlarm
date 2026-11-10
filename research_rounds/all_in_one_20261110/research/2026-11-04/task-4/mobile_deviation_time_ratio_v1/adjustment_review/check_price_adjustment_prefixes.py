"""Four-source pure price arithmetic audit. Never imports original models."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib
import json
import math

import pandas as pd

OUT = Path(__file__).resolve().parent
TASK = OUT.parents[1]
PRICE = TASK / 'mobile_trend_measurements_v1'
RR = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
PLAN = json.loads((OUT / 'FROZEN_PRICE_PREFIX_CHECK_PLAN.json').read_text())
STOCK_MANIFEST = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
PREP_MANIFEST = RR / 'a-share-selection-e0-20261024/prepared-v2/manifest.json'
INPUT_MANIFEST = RR / 'a-share-selection-e0-20261024/inputs-v2/input-manifest.json'
stocks = {r['symbol']: r for r in json.loads(STOCK_MANIFEST.read_text())}
prepared = json.loads(PREP_MANIFEST.read_text())
inputs = json.loads(INPUT_MANIFEST.read_text())
metadata = {r['sid']: r for r in json.loads((PRICE / 'METRIC_INPUTS_AND_WARMUP.json').read_text())}
OHLC = ('open', 'high', 'low', 'close')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def d(value):
    return Decimal(str(value))


def read_frame(path):
    f = pd.read_parquet(path)
    if 'trade_date' in f:
        f = f.rename(columns={'trade_date': 'date'})
    if 'date' in f:
        f = f.set_index('date')
    f.index = pd.DatetimeIndex(pd.to_datetime(f.index)).as_unit('ns')
    assert f.index.is_unique and f.index.is_monotonic_increasing and f.index.tz is None
    return f


def manual_prefix(raw, events, cut):
    source = raw.loc[:cut]
    active = {pd.Timestamp(e['effective_date']): e for e in events
              if source.index[0] < pd.Timestamp(e['effective_date']) <= source.index[-1]}
    dates = sorted(set(source.index) | set(active))
    result = {}
    factor, previous = Decimal(1), None
    with localcontext() as context:
        context.prec = 40
        context.rounding = ROUND_HALF_EVEN
        for date in dates:
            event = active.get(date)
            observed = date in source.index
            row = source.loc[date] if observed else None
            values = {k: d(row[k]) if pd.notna(row[k]) and math.isfinite(float(row[k])) else None
                      for k in OHLC} if observed else None
            if event:
                cash = d(event.get('signal_cash_per_old_share', event['cash_per_old_share']))
                split = d(event.get('signal_split_ratio', event['split_ratio']))
                assert previous is not None and previous > cash
                ex_price = (previous - cash) / split
                factor *= previous / ex_price
                if not observed:
                    values = {k: ex_price for k in OHLC}
            assert values is not None
            result[date] = {'adjustment_factor': float(factor)} | {
                k: float(values[k] * factor) if values[k] is not None else math.nan for k in OHLC}
            if values['close'] is not None and values['close'] > 0:
                previous = values['close']
    return result, active


bindings, summaries, errors, checkpoints, mapping = [], [], [], [], []
max_error = {'factor': 0.0, 'adjusted_OHLC': 0.0, 'facts_coordinate': 0.0, 'EMA_raw_mapping': 0.0,
             'ratio_cancellation': 0.0}
total_scalar_comparisons = 0
assert prepared['source_manifest_sha256'] == sha(INPUT_MANIFEST)
assert prepared['source_manifest'] == str(INPUT_MANIFEST)
for sid, cuts in PLAN['cuts'].items():
    stock = stocks[sid]
    prep_record = next(r for r in prepared['series'] if r['series_id'] == sid)
    record = next(r for r in inputs['series'] if r['series_id'] == sid)
    assert record['adjustment']['method'] == 'theoretical_ex_price' and record.get('segments') is None
    raw_path = Path(record['raw']['path'])
    action_path = Path(record['adjustment']['actions']['path'])
    assert sha(raw_path) == record['raw']['sha256']
    assert sha(action_path) == record['adjustment']['actions']['sha256']
    signal_path = PREP_MANIFEST.parent / prep_record['files']['signal']['path']
    assert sha(signal_path) == prep_record['files']['signal']['sha256'] == stock['source_sha256'][str(signal_path)]
    assert str(signal_path) == metadata[sid]['sources']['signal']['path']
    facts_path = Path(stock['refs']['facts'])
    assert sha(facts_path) == stock['output_sha256'][str(facts_path)] == metadata[sid]['sources']['facts']['sha256']
    raw, signal, facts = (read_frame(p) for p in [raw_path, signal_path, facts_path])
    actions = json.loads(action_path.read_text())
    assert actions['series_id'] == sid and not actions['unresolved']
    events = actions['events']
    assert len({e['effective_date'] for e in events}) == len(events)
    binding = {'sid': sid, 'method': record['adjustment']['method'], 'source_start': record['source_start'],
               'raw': {'path': str(raw_path), 'sha256': sha(raw_path)},
               'actions': {'path': str(action_path), 'sha256': sha(action_path), 'status': actions['status'],
                           'exact_pay_dates_certified': actions.get('exact_pay_dates_certified'),
                           'event_count': len(events), 'event_keys': sorted({k for e in events for k in e}),
                           'event_dates': [e['effective_date'] for e in events]},
               'signal': {'path': str(signal_path), 'sha256': sha(signal_path)},
               'facts': {'path': str(facts_path), 'sha256': sha(facts_path)}}
    bindings.append(binding)
    for cut in cuts:
        calculated, active = manual_prefix(raw, events, cut)
        count = 0
        for date, values in calculated.items():
            assert date in signal.index, (sid, cut, date, 'saved signal row absent')
            for key, value in values.items():
                saved = float(signal.at[date, key])
                equal = value == saved or (math.isnan(value) and math.isnan(saved))
                category = 'factor' if key == 'adjustment_factor' else 'adjusted_OHLC'
                if math.isfinite(value) and math.isfinite(saved):
                    max_error[category] = max(max_error[category], abs(value - saved))
                count += 1
                if not equal:
                    errors.append({'sid': sid, 'cut': cut, 'date': str(date.date()), 'field': key,
                                   'manual': value if math.isfinite(value) else None,
                                   'saved': saved if math.isfinite(saved) else None})
        fact_rows = facts.loc[:cut]
        for date, row in fact_rows.iterrows():
            assert date in calculated
            tests = [('factor', float(row.factor), calculated[date]['adjustment_factor']),
                     ('close', float(row.close), calculated[date]['close']),
                     ('raw_close', float(row.raw_close), float(signal.at[date, 'raw_close']))]
            for key, value, saved in tests:
                max_error['facts_coordinate'] = max(max_error['facts_coordinate'], abs(value - saved))
                count += 1
                if value != saved:
                    errors.append({'sid': sid, 'cut': cut, 'date': str(date.date()), 'field': 'facts.' + key,
                                   'manual': value, 'saved': saved})
        date = pd.Timestamp(cut)
        checkpoints.append({'sid': sid, 'cut': cut, 'factor': calculated[date]['adjustment_factor'],
                            'raw_close': float(raw.at[date, 'close']), 'adjusted_close': calculated[date]['close'],
                            'last_included_action': max((e['effective_date'] for e in active.values()), default=None),
                            'future_effective_actions_excluded': [e['effective_date'] for e in events if e['effective_date'] > cut]})
        total_scalar_comparisons += count
        summaries.append({'sid': sid, 'cut': cut, 'calculated_price_rows': len(calculated),
                          'native_fact_rows': len(fact_rows), 'scalar_comparisons': count,
                          'future_raw_rows_not_used_by_arithmetic': int((raw.index > date).sum()),
                          'future_effective_actions_excluded': len([e for e in events if e['effective_date'] > cut])})
    csv_path = PRICE / 'metrics' / (sid + '.csv')
    csv = pd.read_csv(csv_path, index_col='date', parse_dates=True, float_precision='round_trip')
    for date, row in csv.iterrows():
        historical_factor = float(facts.at[date, 'factor'])
        assert historical_factor == float(row.factor)
        for n in [20, 60]:
            expected = float(row['ema%d_a' % n]) / historical_factor
            actual = float(row['ema%d_raw_current_units' % n])
            residual = abs(expected - actual)
            max_error['EMA_raw_mapping'] = max(max_error['EMA_raw_mapping'], residual)
            if not math.isclose(expected, actual, rel_tol=5e-13, abs_tol=1e-10):
                errors.append({'sid': sid, 'date': str(date.date()), 'field': 'EMA raw mapping', 'residual': residual})
            mapping.append({'sid': sid, 'date': str(date.date()), 'ema': n, 'factor_used': historical_factor,
                            'expected_raw_current_units': expected, 'absolute_residual': residual})
        original_ratio = float(row.close_a) / float(row.ema20_a)
        same_day_raw_ratio = float(row.raw_close) / (float(row.ema20_a) / historical_factor)
        residual = abs(original_ratio - same_day_raw_ratio)
        max_error['ratio_cancellation'] = max(max_error['ratio_cancellation'], residual)
        if not math.isclose(original_ratio, same_day_raw_ratio, rel_tol=5e-13, abs_tol=1e-10):
            errors.append({'sid': sid, 'date': str(date.date()), 'field': 'ratio coordinate cancellation', 'residual': residual})
    binding['metrics'] = {'path': str(csv_path), 'sha256': sha(csv_path), 'rows': len(csv),
                          'case_factor_first': float(csv.factor.iloc[0]), 'case_factor_last': float(csv.factor.iloc[-1]),
                          'frozen_facts_last_date': str(facts.index[-1].date()),
                          'frozen_facts_last_factor': float(facts.factor.iloc[-1])}

report = {'status': 'PASS_FIXED_SNAPSHOT_PRICE_PREFIX_AND_HISTORICAL_ROW_FACTOR' if not errors else 'FAIL_PRICE_ADJUSTMENT_CHECK',
          'reviewer': '/root/upside_logic', 'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Four original raw/actions prefixes; independent Decimal40 theoretical-ex-price arithmetic only. No original source imports, prepare_signal invocation, EMA/model/account/strategy reruns or parameter fitting.',
          'stocks': 4, 'prefix_cuts': len(summaries), 'price_and_native_coordinate_scalar_comparisons': total_scalar_comparisons,
          'EMA_raw_current_unit_checks': len(mapping), 'case_daily_ratio_checks': len(mapping) // 2,
          'maximum_absolute_residuals': max_error, 'errors': errors,
          'manifests': [{'path': str(p), 'sha256': sha(p)} for p in [STOCK_MANIFEST, PREP_MANIFEST, INPUT_MANIFEST]],
          'script_sha256': sha(__file__), 'plan_sha256': sha(OUT / 'FROZEN_PRICE_PREFIX_CHECK_PLAN.json'),
          'hard_limits': ['Mathematical prefix causality is conditional on fixed saved raw/action terms',
                          'Action effective_date does not prove original announcement published/received time',
                          'Later revisions to past raw prices or effective-dated terms were not historically version-audited',
                          'Historical EMA raw current units is not EMA on unadjusted raw historical series',
                          'No real execution or economic performance is validated'],
          'old_models_recomputed': False, 'new_accounts': 0, 'new_backtests': 0, 'new_EMA_computations': 0}
for name, value in [('ACTUAL_SOURCE_BINDINGS.json', bindings), ('PREFIX_PRICE_CHECKS.json', summaries),
                    ('PREFIX_CHECKPOINTS.json', checkpoints), ('HISTORICAL_FACTOR_MAPPING_CHECKS.json', mapping),
                    ('PRICE_ADJUSTMENT_REVIEW.json', report)]:
    dump(name, value)
print(json.dumps({'status': report['status'], 'prefix_cuts': len(summaries), 'scalar_checks': total_scalar_comparisons,
                  'mapping_checks': len(mapping), 'ratio_checks': len(mapping) // 2,
                  'max_residuals': max_error, 'errors': len(errors),
                  'review_sha256': sha(OUT / 'PRICE_ADJUSTMENT_REVIEW.json')}, ensure_ascii=False))
assert not errors, errors[:10]

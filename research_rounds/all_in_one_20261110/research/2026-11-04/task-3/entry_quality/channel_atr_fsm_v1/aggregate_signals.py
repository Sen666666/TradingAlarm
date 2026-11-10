"""Read-only aggregation of the frozen single-run signal outputs; no FSM rerun."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent
RUNS = [ROOT / x / 'run_v1' for x in ['shard_a', 'shard_b', 'semiconductor_full']]


def load(p):
    return json.loads(p.read_text())


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def distribution(values):
    a = np.asarray([x for x in values if finite(x)], dtype=float)
    return {'n': len(a), **({f'q{int(q*100):02}': float(np.quantile(a, q))
                             for q in [0, .1, .5, .9, 1]} if len(a) else {})}


def relation(row):
    c, a = row['CP'], row['ATR3']
    if c['outcome'] == a['outcome'] == 'EXIT_SIGNAL':
        return ('ATR_EARLIER' if a['exit_day'] < c['exit_day'] else
                'SAME_DAY' if a['exit_day'] == c['exit_day'] else 'ATR_LATER')
    return f"CP_{c['outcome']}__ATR_{a['outcome']}"


def summarize(rows, threshold=None):
    paired = [x for x in rows if x['status'] == 'PAIRED_SHADOWS']
    result = {
        'raw_anchors': len(rows),
        'distinct_stocks': len({x['sid'] for x in rows}),
        'status_counts': dict(Counter(x['status'] for x in rows)),
        'paired_distinct_stocks': len({x['sid'] for x in paired}),
        'common_end_counts': dict(Counter(x['common_end_reason'] for x in paired)),
        'exit_relation': dict(Counter(relation(x) for x in paired)),
        'status20_cross': dict(Counter(f"CP:{x['CP']['status_at20']}|ATR:{x['ATR3']['status_at20']}" for x in paired)),
        'held_delta_ATR_minus_CP_both_exit': distribution([
            x['ATR3']['effective_observations_held'] - x['CP']['effective_observations_held']
            for x in paired if x['CP']['outcome'] == x['ATR3']['outcome'] == 'EXIT_SIGNAL']),
        'branches': {},
    }
    for arm in ['CP', 'ATR3']:
        result['branches'][arm] = {
            'outcomes': dict(Counter(x[arm]['outcome'] for x in paired)),
            'status_at20': dict(Counter(x[arm]['status_at20'] for x in paired)),
            'held_observations': distribution([x[arm]['effective_observations_held'] for x in paired]),
            'post20_close_drawdown_in_initial_ATR': distribution([x[arm]['post20_max_close_drawdown_ATR'] for x in paired]),
            'post20_nonmissing_distinct_stocks': len({x['sid'] for x in paired if finite(x[arm]['post20_max_close_drawdown_ATR'])}),
        }
    bothpost = [x for x in paired if all(finite(x[arm]['post20_max_close_drawdown_ATR']) for arm in ['CP', 'ATR3'])]
    result['both_post20_comparable'] = {
        'n': len(bothpost),
        'CP_drawdown': distribution([x['CP']['post20_max_close_drawdown_ATR'] for x in bothpost]),
        'ATR3_drawdown': distribution([x['ATR3']['post20_max_close_drawdown_ATR'] for x in bothpost]),
        'ATR_minus_CP_drawdown': distribution([x['ATR3']['post20_max_close_drawdown_ATR']-x['CP']['post20_max_close_drawdown_ATR'] for x in bothpost]),
        'warning': 'Conditional survivor subset, not total risk or a portfolio causal effect',
    }
    if threshold is not None:
        strong = [x for x in paired if finite(x.get('common_favorable_excursion_ATR')) and x['common_favorable_excursion_ATR'] >= threshold]
        result['strong_common_price_opportunities'] = {
            'diagnostic_future_label_only': True,
            'global_window_q90_initial_ATR': threshold,
            'n': len(strong),
            'distinct_stocks': len({x['sid'] for x in strong}),
            'common_end_counts': dict(Counter(x['common_end_reason'] for x in strong)),
            'exit_relation': dict(Counter(relation(x) for x in strong)),
            'CP_held_observations': distribution([x['CP']['effective_observations_held'] for x in strong]),
            'ATR3_held_observations': distribution([x['ATR3']['effective_observations_held'] for x in strong]),
            'ATR_earlier_with_later_higher_common_close': sum(relation(x) == 'ATR_EARLIER' and x['ATR3']['common_peak_after_shadow_truncation_ATR'] > 0 for x in strong),
        }
    return result


def main():
    allrows = []
    receipts = []
    events = defaultdict(Counter)
    identities = set()
    for run in RUNS:
        receipt = load(run / 'RUN_RECEIPT.json')
        assert receipt['status'] == 'COMPLETE' and receipt['errors'] == 0
        receipts.append({'run': str(run.relative_to(ROOT)), 'receipt_sha256': hashlib.sha256((run / 'RUN_RECEIPT.json').read_bytes()).hexdigest(), 'receipt': receipt})
        for path in sorted(run.glob('*/CP_ANCHOR_PAIRS.json')):
            rows = load(path)
            assert len(rows) == len({x['anchor_id'] for x in rows})
            for x in rows:
                identity = (x['sid'], x['anchor_id'], x['window'])
                assert identity not in identities, identity
                identities.add(identity)
            allrows.extend(rows)
        for path in sorted(run.glob('*/MARKET_EVENTS.json')):
            for e in load(path):
                events[e['window']][e['kind']] += 1
    versions = {x['receipt']['version'] for x in receipts}
    code = {json.dumps(x['receipt']['code_sha256'], sort_keys=True) for x in receipts}
    assert len(versions) == len(code) == 1
    assert len(allrows) == sum(x['receipt']['raw_CP_anchors'] for x in receipts)
    windows = sorted({x['window'] for x in allrows})
    result = {
        'status': 'FIXED_SINGLE_RUN_READ_ONLY_DIAGNOSTIC',
        'version': next(iter(versions)),
        'new_accounts': 0, 'new_quantities': 0, 'new_returns': 0,
        'receipts': receipts,
        'raw_anchors_total': len(allrows),
        'full_calendar_gap_check': 'NOT_VERIFIED',
        'windows': {},
        'main_market_event_counts_not_orders': {k: dict(v) for k, v in events.items()},
        'counterexamples_global_strong_decile_ATR_earlier': {},
        'limits': [
            'Signals and price-reference shadows only; no actual orders, fills, quantity, fees or portfolio returns',
            'Raw CP anchors overlap within stocks; these counts are not independent experiments',
            'Common future excursion decile is a diagnostic post-label, never an input or parameter selection',
            'Source-end truncated future labels are lower bounds; common-end counts reported',
            'Conditional post20 survivors differ; early exits, missing and censored are not zero risk',
            'Semiconductor membership is current-metadata non-PIT; full historical calendar gaps not verified',
        ],
    }
    for window in windows:
        rows = [x for x in allrows if x['window'] == window]
        values = [x['common_favorable_excursion_ATR'] for x in rows if x['status'] == 'PAIRED_SHADOWS' and finite(x.get('common_favorable_excursion_ATR'))]
        threshold = float(np.quantile(values, .9)) if values else None
        result['windows'][window] = summarize(rows, threshold)
        early = [x for x in rows if x['status'] == 'PAIRED_SHADOWS' and relation(x) == 'ATR_EARLIER' and x['common_favorable_excursion_ATR'] >= threshold and x['ATR3']['common_peak_after_shadow_truncation_ATR'] > 0]
        # One strongest diagnostic per stock, then top ten; repeated CP anchors aren't independent evidence.
        perstock = {}
        for x in early:
            score = x['ATR3']['common_peak_after_shadow_truncation_ATR']
            if x['sid'] not in perstock or score > perstock[x['sid']]['ATR3']['common_peak_after_shadow_truncation_ATR']:
                perstock[x['sid']] = x
        result['counterexamples_global_strong_decile_ATR_earlier'][window] = sorted(perstock.values(), key=lambda x: x['ATR3']['common_peak_after_shadow_truncation_ATR'], reverse=True)[:10]
    (ROOT / 'AGGREGATE_DIAGNOSTICS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    # Compact stdout only; complete evidence is saved above.
    for window, s in result['windows'].items():
        print(window, json.dumps({k: s[k] for k in ['raw_anchors', 'status_counts', 'exit_relation', 'strong_common_price_opportunities', 'both_post20_comparable']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

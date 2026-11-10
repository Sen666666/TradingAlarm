"""Narrow read-only aggregation of already computed CP/ATR3 pair outputs."""
from pathlib import Path
from collections import Counter
import json
import math
import hashlib

OUT = Path(__file__).resolve().parent
RUN = OUT / 'run_v1'
coverage = json.loads((RUN / 'COVERAGE_ALL_SYMBOLS.json').read_text())

def bucket():
    return dict(raw_anchors=0, pair_status=Counter(), paired=0, precedence=Counter(),
                outcome_cross=Counter(), status20_cross=Counter(), common_end=Counter(),
                common_lt20=0, CP_outcomes=Counter(), ATR3_outcomes=Counter(),
                CP_status20=Counter(), ATR3_status20=Counter(), CP_censor=Counter(), ATR3_censor=Counter(),
                CP_post20_defined=0, ATR3_post20_defined=0, both_post20_defined=0,
                both_alive_at20=0, both_have_twentieth_record=0,
                both_alive_at20_both_post20_defined=0)

def cross_rows(counter, names):
    return [{names[0]: a, names[1]: b, 'count': count} for (a, b), count in sorted(counter.items())]

def numeric(v):
    return isinstance(v, (int, float)) and math.isfinite(v)

windows = {}
opportunities = []
pair_sources = {}
for report in coverage:
    if report['status'] != 'COMPLETE':
        continue
    path = RUN / report['sid'].replace('.', '_') / 'CP_ANCHOR_PAIRS.json'
    pair_sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    pairs = json.loads(path.read_text())
    for r in pairs:
        b = windows.setdefault(r['window'], bucket())
        b['raw_anchors'] += 1
        b['pair_status'][r['status']] += 1
        if r['status'] != 'PAIRED_SHADOWS':
            continue
        b['paired'] += 1
        cp, atr = r['CP'], r['ATR3']
        co, ao = cp['outcome'], atr['outcome']
        cd, ad = cp['exit_day'], atr['exit_day']
        if cd and ad:
            order = 'ATR3_EARLIER_BOTH_EXIT' if ad < cd else 'CP_EARLIER_BOTH_EXIT' if cd < ad else 'SAME_EXIT_DAY'
        elif ad:
            order = 'ATR3_EXIT_CP_' + co
        elif cd:
            order = 'CP_EXIT_ATR3_' + ao
        else:
            order = 'NEITHER_EXIT_CP_' + co + '__ATR3_' + ao
        b['precedence'][order] += 1
        b['outcome_cross'][(co, ao)] += 1
        b['status20_cross'][(cp['status_at20'], atr['status_at20'])] += 1
        b['common_end'][r['common_end_reason']] += 1
        b['common_lt20'] += r['common_observations'] < 20
        for name, side in [('CP', cp), ('ATR3', atr)]:
            b[name + '_outcomes'][side['outcome']] += 1
            b[name + '_status20'][side['status_at20']] += 1
            if side['censor_reason'] is not None:
                b[name + '_censor'][side['censor_reason']] += 1
        c_defined = numeric(cp['post20_max_close_drawdown_ATR'])
        a_defined = numeric(atr['post20_max_close_drawdown_ATR'])
        b['CP_post20_defined'] += c_defined
        b['ATR3_post20_defined'] += a_defined
        b['both_post20_defined'] += c_defined and a_defined
        both_alive = cp['status_at20'] == 'ALIVE_AT_20' and atr['status_at20'] == 'ALIVE_AT_20'
        b['both_alive_at20'] += both_alive
        b['both_alive_at20_both_post20_defined'] += both_alive and c_defined and a_defined
        b['both_have_twentieth_record'] += cp['twentieth_observation'] is not None and atr['twentieth_observation'] is not None
        metric = atr['common_peak_after_shadow_truncation_ATR']
        if order == 'ATR3_EARLIER_BOTH_EXIT' and numeric(metric) and metric > 0:
            opportunities.append({
                'sid': r['sid'], 'anchor_day': r['anchor_day'], 'anchor_id': r['anchor_id'], 'window': r['window'],
                'source_pair_json': str(path), 'anchor_C': r['anchor_C'], 'P0': r['P0'],
                'anchor_ATR_prior': r['anchor_ATR_prior'],
                'common_end_day': r['common_end_day'], 'common_end_reason': r['common_end_reason'],
                'common_observations': r['common_observations'], 'common_max_close': r['common_max_close'],
                'common_favorable_excursion_ATR': r['common_favorable_excursion_ATR'],
                'ATR3_future_common_peak_gap_ATR': metric,
                'CP_future_common_peak_gap_ATR': cp['common_peak_after_shadow_truncation_ATR'],
                'CP': cp, 'ATR3': atr,
                'selection': 'Future diagnostic only: descending ATR3 common_peak_after_shadow_truncation_ATR; no profit/decile/strategy selection.',
            })

result = {}
for name, b in windows.items():
    assert b['raw_anchors'] == sum(b['pair_status'].values())
    assert b['paired'] == sum(b['precedence'].values()) == sum(b['status20_cross'].values())
    result[name] = {
        'raw_anchor_denominator': b['raw_anchors'], 'pair_status_counts': dict(b['pair_status']),
        'paired_shadow_denominator': b['paired'], 'exit_precedence_counts': dict(b['precedence']),
        'right_censoring_and_unknown_counts': {
            'CP_right_censored': b['CP_outcomes'].get('RIGHT_CENSORED', 0),
            'ATR3_right_censored': b['ATR3_outcomes'].get('RIGHT_CENSORED', 0),
            'CP_unknown': b['CP_outcomes'].get('UNKNOWN', 0),
            'ATR3_unknown': b['ATR3_outcomes'].get('UNKNOWN', 0),
        },
        'exit_outcome_cross_counts': cross_rows(b['outcome_cross'], ['CP_outcome', 'ATR3_outcome']),
        'status_at20_cross_counts': cross_rows(b['status20_cross'], ['CP_status_at20', 'ATR3_status_at20']),
        'status_at20_cross_denominator': b['paired'],
        'cross_zero_cells_omitted': True,
        'common_end_counts_among_paired': dict(b['common_end']),
        'common_horizon_fewer_than20_among_paired': b['common_lt20'],
        'CP': {'outcome_counts': dict(b['CP_outcomes']), 'status_at20_counts': dict(b['CP_status20']),
               'censor_reason_counts': dict(b['CP_censor']), 'post20_drawdown_defined_denominator': b['CP_post20_defined']},
        'ATR3': {'outcome_counts': dict(b['ATR3_outcomes']), 'status_at20_counts': dict(b['ATR3_status20']),
                 'censor_reason_counts': dict(b['ATR3_censor']), 'post20_drawdown_defined_denominator': b['ATR3_post20_defined']},
        'joint_denominators': {k: b[k] for k in ['both_alive_at20', 'both_have_twentieth_record',
                                                'both_post20_defined', 'both_alive_at20_both_post20_defined']},
    }
assert sum(x['raw_anchor_denominator'] for x in result.values()) == 24151
opportunities.sort(key=lambda x: (-x['ATR3_future_common_peak_gap_ATR'], x['sid'], x['anchor_day']))
distinct = []
seen = set()
for row in opportunities:
    if row['sid'] not in seen:
        distinct.append(row)
        seen.add(row['sid'])
        if len(distinct) == 3:
            break
payload = {
    'status': 'READ_ONLY_NARROW_AGGREGATION_NO_MODEL_RERUN', 'windows': result,
    'ranked_larger_future_common_peak_gap_candidates': len(opportunities),
    'top3_raw_anchors': opportunities[:3],
    'top3_distinct_symbols_for_readability': distinct,
    'selection_scope': 'Shard-A descriptive extreme cases only, not a global decile. Distinct-symbol appendix is explicit, not replacing raw top3.',
    'global_strong_decile_assigned': False, 'early_exit_post20_not_imputed_zero': True,
    'no_new_FSM_or_parameters_or_accounts_or_quantities_or_returns': True,
    'source_count': len(pair_sources),
}
(OUT / 'CP_ATR3_NARROW_AGGREGATE.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
(OUT / 'PAIR_AGGREGATION_SOURCE_SHA256.json').write_text(json.dumps(pair_sources, indent=2) + '\n')
print(json.dumps({'windows': result, 'top3': [{k: x[k] for k in ['sid','anchor_day','window','ATR3_future_common_peak_gap_ATR','common_max_close']} for x in opportunities[:3]]}, indent=2))

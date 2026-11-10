"""Draft conditional-price diagnostic aggregation; no CUSUM/CP/account engine.

Only consumes a frozen, causal, one-stock/day reference panel supplied later.
This module has not been run on a panel; upstream freeze/smoke is required.
"""
from collections import Counter, defaultdict
import math

LEVEL = 3.0
MIN_SIDE = 20
MEASURES = ('MFE20', 'MAE20')
COVARIATES = ('oldP_logdist_s', 'known_close_drawdown_s', 'holding_age', 's63')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def strict_bool(value):
    return value if isinstance(value, bool) else None


def controls(row):
    """Current known prices only; oldP is before today's CP/I line updates."""
    C, P, peak, s, age = (row.get(k) for k in ('C', 'P_old', 'known_close_peak', 's63', 'holding_age'))
    if not all(finite(v) and v > 0 for v in (C, P, peak, s, age)):
        return None
    if int(age) != age:
        return None
    if peak < C:
        return None  # provider must include the current completed close in its past-known peak.
    dist = math.log(C / P) / s
    dd = max(0.0, math.log(peak / C)) / s
    return {'oldP_logdist_s': dist, 'known_close_drawdown_s': dd,
            'holding_age': int(age), 's63': s}


def bins(v):
    dist, dd, age, s = (v[k] for k in COVARIATES)
    return (
        'LE0' if dist <= 0 else 'GT0_LE1' if dist <= 1 else 'GT1_LE3' if dist <= 3 else 'GT3',
        'GE0_LT1' if dd < 1 else 'GE1_LT2' if dd < 2 else 'GE2_LT4' if dd < 4 else 'GE4',
        '1_5' if age <= 5 else '6_20' if age <= 20 else '21_60' if age <= 60 else 'GT60',
        'LT.01' if s < .01 else 'GE.01_LT.02' if s < .02 else 'GE.02_LT.04' if s < .04 else 'GE.04',
    )


def classify_primary(row):
    """Anchor is already selected BEFORE these exclusions; never choose again."""
    if row.get('reference_status') != 'ENTERED_ORIGINAL_CP_REFERENCE':
        return 'REFERENCE_NOT_FORMED_OR_UNKNOWN', None
    current_exit = strict_bool(row.get('current_CP_I_exit'))
    if current_exit is None:
        return 'CURRENT_ORIGINAL_CP_TRACE_UNKNOWN', None
    if current_exit:
        return 'CURRENT_CLOSE_ORIGINAL_CP_I_EXIT', None
    if row.get('native_i_target') != 1:
        return 'CURRENT_I_NOT_KNOWN_ACTIVE', None
    D = row.get('D')
    if row.get('D_status') != 'KNOWN' or not finite(D) or D < 0:
        return 'CUSUM_UNKNOWN_OR_INACTIVE', None
    if row.get('scale_status') != 'READY':
        return 'CURRENT_SCALE_UNREADY_OR_GUARDED', None
    values = controls(row)
    if values is None:
        return 'CURRENT_CONTROL_INPUT_UNKNOWN', None
    return 'PRIMARY_KNOWN', {'warning': D >= LEVEL, 'controls': values, 'stratum': bins(values)}


def complete_label(row):
    if row.get('label_status') != 'COMPLETE_20':
        return False
    if row.get('forward20_n_observations') != 20:
        raise ValueError('COMPLETE_20 must contain exactly 20 future completed comparable closes')
    if not all(finite(row.get(k)) and row[k] >= 0 for k in MEASURES):
        raise ValueError('Complete price labels require finite nonnegative MFE20/MAE20')
    return True


def mean(rows, key):
    return None if not rows else math.fsum(row[key] for row in rows) / len(rows)


def identity_counts(rows):
    return {'reference_days': len(rows),
            'unique_sid': len({x['sid'] for x in rows}),
            'unique_anchor': len({(x['sid'], x['anchor_id']) for x in rows}),
            'unique_I_cycle': len({(x['sid'], x.get('cycle_id')) for x in rows if x.get('cycle_id') is not None}),
            'unique_decision_date': len({x['day'] for x in rows})}


def condition_stats(rows):
    return {'identity_counts': identity_counts(rows),
            'means': {key: mean(rows, key) for key in (*MEASURES, *COVARIATES)}}


def aggregate(rows):
    """Aggregate explicit analysis_window tags; no calendar/data selection here.

    A post-924 appendix may duplicate primary-window rows only under a different
    explicit tag. Such scopes must not be added as independent observations.
    """
    by_window = defaultdict(list)
    for row in rows:
        by_window[row['analysis_window']].append(row)
    output = {}
    for window, original in sorted(by_window.items()):
        identities = [(x['sid'], x['day']) for x in original]
        if len(set(identities)) != len(identities):
            raise ValueError('One selected oldest reference per stock/day/window is required')
        funnel = Counter()
        excluded_current_exit = Counter()
        crossing = Counter()
        label_states = {False: Counter(), True: Counter()}
        eligible = {False: [], True: []}
        labelled = {False: [], True: []}
        strata = defaultdict(lambda: {False: [], True: []})
        cooccurrence = {False: Counter(), True: Counter()}
        for source in original:
            D = source.get('D')
            known_D = source.get('D_status') == 'KNOWN' and finite(D) and D >= 0
            is_warning = D >= LEVEL if known_D else None
            current_exit = strict_bool(source.get('current_CP_I_exit'))
            if current_exit:
                excluded_current_exit['D_GE3' if is_warning else 'D_LT3' if is_warning is False else 'D_UNKNOWN'] += 1
            if strict_bool(source.get('threshold_cross')) is True:
                crossing['CURRENT_CP_I_EXIT' if current_exit else 'CURRENT_TRACE_UNKNOWN' if current_exit is None else 'NOT_CURRENT_CP_I_EXIT'] += 1
            reason, classification = classify_primary(source)
            funnel[reason] += 1
            if classification is None:
                continue
            warning = classification['warning']
            row = dict(source, **classification['controls'])
            eligible[warning].append(row)
            today = strict_bool(row.get('E0_down_same_close'))
            past = strict_bool(row.get('E0_down_in_prior5_complete_observations'))
            cooccurrence[warning][f'TODAY_{today}__PRIOR5_{past}'] += 1
            label_states[warning][source.get('label_status', 'LABEL_STATUS_ABSENT')] += 1
            if not complete_label(row):
                continue
            labelled[warning].append(row)
            strata[classification['stratum']][warning].append(row)
        overlap = []
        all_cells = []
        for stratum, sides in sorted(strata.items()):
            W, C = sides[True], sides[False]
            include = len(W) >= MIN_SIDE and len(C) >= MIN_SIDE
            cell = {'stratum': list(stratum), 'n_warning': len(W), 'n_control': len(C),
                    'included_in_descriptive_standardization': include,
                    'warning_means': {key: mean(W, key) for key in (*MEASURES, *COVARIATES)},
                    'control_means': {key: mean(C, key) for key in (*MEASURES, *COVARIATES)}}
            all_cells.append(cell)
            if include:
                overlap.append((cell, W, C))
        Nw = sum(len(W) for _, W, _ in overlap)
        Nc = sum(len(C) for _, _, C in overlap)
        standardized = None
        if Nw:
            Wmeans = {key: math.fsum(len(W) * cell['warning_means'][key] for cell, W, C in overlap) / Nw
                      for key in (*MEASURES, *COVARIATES)}
            Cmeans = {key: math.fsum(len(W) * cell['control_means'][key] for cell, W, C in overlap) / Nw
                      for key in (*MEASURES, *COVARIATES)}
            standardized = {'weighting': 'Warning-labelled reference-day n within included stratum / all included warning n',
                            'warning_means': Wmeans, 'control_means': Cmeans,
                            'warning_minus_control': {key: Wmeans[key] - Cmeans[key] for key in MEASURES}}
        output[window] = {
            'selected_reference_day_rows': len(original), 'primary_funnel': dict(funnel),
            'current_close_exit_excluded_D_counts': dict(excluded_current_exit),
            'crossing_current_exit_counts_not_primary_comparison': dict(crossing),
            'warning_primary_known': identity_counts(eligible[True]),
            'control_primary_known': identity_counts(eligible[False]),
            'warning_label_status_counts': dict(label_states[True]), 'control_label_status_counts': dict(label_states[False]),
            'raw_warning_labelled': condition_stats(labelled[True]), 'raw_control_labelled': condition_stats(labelled[False]),
            'warning_E0_down_cooccurrence_known_primary': dict(cooccurrence[True]),
            'control_E0_down_cooccurrence_known_primary': dict(cooccurrence[False]),
            'strata_complete_label_total': len(all_cells), 'strata_with_both_sides_at_least20': len(overlap),
            'warning_overlap_n': Nw, 'control_overlap_n': Nc,
            'warning_overlap_fraction_of_labelled': None if not labelled[True] else Nw / len(labelled[True]),
            'control_overlap_fraction_of_labelled': None if not labelled[False] else Nc / len(labelled[False]),
            'warning_overlap_fraction_of_known_primary': None if not eligible[True] else Nw / len(eligible[True]),
            'standardized': standardized, 'all_strata_including_sparse': all_cells,
            'sparse_strata_not_relaxed_or_merged': True,
            'not_independent_trade_samples_or_account_returns': True,
        }
    return output

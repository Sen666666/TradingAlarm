"""Frozen same-day caliper diagnostic. Match before inspecting future labels."""
from collections import Counter, defaultdict
import math
import numpy as np
from stratify import classify_primary, complete_label, mean, identity_counts

CAP_LOGVOL = math.log(1.25)


def labelled_status(w, c):
    a, b = complete_label(w), complete_label(c)
    return 'BOTH_COMPLETE' if a and b else 'WARNING_LABEL_MISSING' if b else 'CONTROL_LABEL_MISSING' if a else 'BOTH_LABELS_MISSING'


def run(rows):
    windows = defaultdict(list)
    for source in rows:
        reason, classification = classify_primary(source)
        if classification is not None:
            windows[source['analysis_window']].append(dict(source, **classification['controls']))
    summaries, all_matches = {}, []
    for window, eligible in sorted(windows.items()):
        # Defined on the whole labelled primary cohort, before warning arms/matching.
        labelled = [x for x in eligible if complete_label(x)]
        q90 = None if not labelled else float(np.quantile([x['MFE20'] for x in labelled], .9, method='linear'))
        dates = defaultdict(list)
        for x in eligible:
            dates[x['day']].append(x)
        matched, unmatched = [], Counter()
        for day, current in sorted(dates.items()):
            warning = sorted([x for x in current if x['D'] >= 3], key=lambda x: x['sid'])
            control = sorted([x for x in current if x['D'] < 3], key=lambda x: x['sid'])
            if not control:
                unmatched['NO_SAME_DAY_CONTROL'] += len(warning)
                continue
            values = np.array([[x['known_close_drawdown_s'], x['oldP_logdist_s'], math.log(x['s63']), x['holding_age']] for x in control])
            used = np.zeros(len(control), dtype=bool)
            for w in warning:
                vector = np.array([w['known_close_drawdown_s'], w['oldP_logdist_s'], math.log(w['s63']), w['holding_age']])
                caps = np.array([.25, .25, CAP_LOGVOL, max(2., .2 * w['holding_age'])])
                differences = np.abs(values - vector)
                feasible = np.all(differences <= caps, axis=1)
                available = feasible & ~used
                ids = np.flatnonzero(available)
                if not len(ids):
                    unmatched['FEASIBLE_CONTROLS_ALREADY_USED' if feasible.any() else 'NO_CONTROL_WITHIN_FIXED_CALIPERS'] += 1
                    continue
                scores = np.sum((differences[ids] / caps) ** 2, axis=1)
                ci = int(ids[int(np.argmin(scores))])  # control list is sid-sorted, exact ties pick first.
                used[ci] = True
                c = control[ci]
                # Future fields are first inspected AFTER the match choice.
                status = labelled_status(w, c)
                item = {'analysis_window': window, 'day': day, 'warning_sid': w['sid'], 'control_sid': c['sid'],
                        'warning_anchor_id': w['anchor_id'], 'control_anchor_id': c['anchor_id'],
                        'score': float(np.sum((differences[ci] / caps) ** 2)),
                        'warning': w, 'control': c, 'label_pair_status': status,
                        'residuals_warning_minus_control': {key: w[key] - c[key] for key in
                            ['known_close_drawdown_s','oldP_logdist_s','s63','holding_age']},
                        'logvol_ratio': math.log(w['s63'] / c['s63']),
                        'warning_future_q90_MFE': None if q90 is None or not complete_label(w) else w['MFE20'] >= q90,
                        'control_future_q90_MFE': None if q90 is None or not complete_label(c) else c['MFE20'] >= q90}
                matched.append(item)
        warn = [x for x in eligible if x['D'] >= 3]
        ctrl = [x for x in eligible if x['D'] < 3]
        complete = [x for x in matched if x['label_pair_status'] == 'BOTH_COMPLETE']
        w_all, c_all = [x['warning'] for x in matched], [x['control'] for x in matched]
        w_lab, c_lab = [x['warning'] for x in complete], [x['control'] for x in complete]
        keys = ['known_close_drawdown_s','oldP_logdist_s','s63','holding_age','I_cycle_age']
        def balance(key):
            valid = [x for x in matched if x['warning'].get(key) is not None and x['control'].get(key) is not None]
            return {'n': len(valid), 'warning_mean': None if not valid else math.fsum(x['warning'][key] for x in valid) / len(valid),
                    'control_mean': None if not valid else math.fsum(x['control'][key] for x in valid) / len(valid),
                    'mean_absolute_difference': None if not valid else math.fsum(abs(x['warning'][key]-x['control'][key]) for x in valid) / len(valid)}
        summaries[window] = {
            'primary_warning_known': identity_counts(warn), 'primary_control_known': identity_counts(ctrl),
            'matched_pairs': len(matched), 'warning_matched_coverage': None if not warn else len(matched) / len(warn),
            'unmatched_warning_reasons': dict(unmatched),
            'matched_warning_identities': identity_counts(w_all), 'matched_control_identities': identity_counts(c_all),
            'match_label_status_counts': dict(Counter(x['label_pair_status'] for x in matched)),
            'complete_label_pair_n': len(complete), 'complete_pair_warning_means': {k: mean(w_lab,k) for k in ['MFE20','MAE20']},
            'complete_pair_control_means': {k: mean(c_lab,k) for k in ['MFE20','MAE20']},
            'mean_warning_minus_control': {k: None if not complete else math.fsum(x['warning'][k]-x['control'][k] for x in complete) / len(complete) for k in ['MFE20','MAE20']},
            'continuous_balance_on_all_matches_no_future_selection': {key: balance(key) for key in keys},
            'future_MFE_q90': q90, 'q90_population': 'all complete20 primary known reference-days before warning arm or matching',
            'q90_population_n': len(labelled), 'q90_ties_ge_threshold': None if q90 is None else sum(x['MFE20']>=q90 for x in labelled),
            'matched_warning_future_q90_n': sum(x['warning_future_q90_MFE'] is True for x in matched),
            'matched_control_future_q90_n': sum(x['control_future_q90_MFE'] is True for x in matched),
            'primary_warning_first_hit20_counts': dict(Counter(x.get('first_hit20_label','ABSENT') for x in warn)),
            'primary_control_first_hit20_counts': dict(Counter(x.get('first_hit20_label','ABSENT') for x in ctrl)),
            'matched_warning_first_hit20_counts': dict(Counter(x.get('first_hit20_label','ABSENT') for x in w_all)),
            'matched_control_first_hit20_counts': dict(Counter(x.get('first_hit20_label','ABSENT') for x in c_all)),
            'matched_warning_down_first_rebound_counts': dict(Counter(str(x.get('rebound_after_down')) for x in w_all if x.get('first_hit20_label')=='DOWN_FIRST')),
            'matched_control_down_first_rebound_counts': dict(Counter(str(x.get('rebound_after_down')) for x in c_all if x.get('first_hit20_label')=='DOWN_FIRST')),
            'same_day_control_without_replacement': True, 'no_label_used_to_select_match': True,
            'no_caliper_relaxation_or_parameter_search': True,
        }
        all_matches.extend(matched)
    return summaries, all_matches

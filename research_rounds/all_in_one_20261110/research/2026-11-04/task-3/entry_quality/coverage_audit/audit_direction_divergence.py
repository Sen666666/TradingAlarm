"""Independent bounded audit of saved direction-divergence outputs, no cold rerun."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
import csv, gzip, hashlib, json, math

getcontext().prec = 60
BASE = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/direction_divergence')
ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
OUT = Path(__file__).parent
SHA = {}
COUNTS = defaultdict(int)
MAX = defaultdict(float)


def read(p, gz=False):
    SHA[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    with (gzip.open(p, 'rt') if gz else p.open()) as f: return json.load(f)


def close(a, b, where):
    assert abs(D(str(a)) - D(str(b))) < D('1e-18'), (where, a, b)


def aggregate(rows):
    return dict(layers=len(rows), stocks=len({x['sid'] for x in rows}),
                cost=sum((D(x['cost']) for x in rows), D(0)), net=sum((D(x['net']) for x in rows), D(0)),
                positive_net=sum((D(x['net']) for x in rows if D(x['net']) > 0), D(0)),
                negative_net=sum((D(x['net']) for x in rows if D(x['net']) < 0), D(0)),
                open_layers=sum(bool(x['qty']) for x in rows),
                strict_realized=None if any('strict_realized' not in x for x in rows) else sum((D(x['strict_realized']) for x in rows), D(0)),
                open_unrealized=None if any('open_unrealized' not in x for x in rows) else sum((D(x['open_unrealized']) for x in rows), D(0)),
                dividend_AR=None if any('recognized_dividend_AR' not in x for x in rows) else sum((D(x['recognized_dividend_AR']) for x in rows), D(0)))


def check_agg(rows, saved, label):
    actual = aggregate(rows)
    for k, v in actual.items():
        if v is None: assert saved[k] is None, (label, k)
        elif k in ['layers', 'stocks', 'open_layers']: assert saved[k] == v, (label, k, saved[k], v)
        else: close(v, saved[k], (label, k))
    COUNTS['group_aggregates_checked'] += 1


def finite(v):
    return v is not None and math.isfinite(float(v))


def scalar_check(s, label):
    if finite(s.get('pvr_e')) and finite(s.get('pvr_r')):
        r, u, b, e = (float(s[k]) for k in ['pvr_r', 'pvr_u', 'pvr_b', 'pvr_e'])
        mult = 1 + .5 * abs(u) * b
        assert .5 <= mult <= 1.5 and abs(u) <= 1 and abs(b) <= 1
        err = abs(e - u * mult)
        MAX['pvr_e_formula_error'] = max(MAX['pvr_e_formula_error'], err)
        assert err < 1e-14 and (e > 0) == (r > 0) and (e < 0) == (r < 0), label
        COUNTS['pvr_scalar_sign_formula_checks'] += 1
    if finite(s.get('act_x')) and finite(s.get('act_r')):
        r, w, x = (float(s[k]) for k in ['act_r', 'act_multiplier', 'act_x'])
        assert 0 < w <= 1
        err = abs(x - r * w)
        MAX['act_x_formula_error'] = max(MAX['act_x_formula_error'], err)
        assert err < 1e-14 and (x > 0) == (r > 0) and (x < 0) == (r < 0), label
        COUNTS['act_scalar_sign_formula_checks'] += 1


FLAGS = ['pvr_daily_down_smooth_positive', 'act_daily_down_smooth_positive',
         'pvr_amount_smooth_positive_price_smooth_nonpositive', 'act_amount_smooth_positive_price_smooth_nonpositive']


def flags(s):
    def cmp(k, f): return finite(s.get(k)) and f(float(s[k]))
    return dict(pvr_daily_down_smooth_positive=cmp('pvr_r', lambda x: x < 0) and cmp('pvr_E', lambda x: x > 0),
                act_daily_down_smooth_positive=cmp('act_r', lambda x: x < 0) and cmp('act_mom', lambda x: x > 0),
                pvr_amount_smooth_positive_price_smooth_nonpositive=cmp('pvr_E', lambda x: x > 0) and cmp('pvr_price_smooth', lambda x: x <= 0),
                act_amount_smooth_positive_price_smooth_nonpositive=cmp('act_mom', lambda x: x > 0) and cmp('act_price_smooth', lambda x: x <= 0))


results = read(BASE / 'RESULTS.json')
validation = read(BASE / 'VALIDATION.json')
protocol = read(BASE / 'PROTOCOL.json')
source = (BASE / 'analyze.py').read_text()
SHA[str(BASE / 'analyze.py')] = hashlib.sha256(source.encode()).hexdigest()
original = read(ROOT / 'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
SUMMARY = {}
allrows = {}
for ref, pair in [('2022_2024', ROOT / 'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),
                  ('strong', ROOT / 'pvr_pool_feasibility/runs/2025_26/pair')]:
    rr = read(BASE / (ref + '_ROWS.json'))
    allrows[ref] = rr
    assert len(rr) == (2265 if ref == '2022_2024' else 1171)
    native = read(pair / 'B.json.gz', gz=True)
    intents = {(d['at'].replace('T', ' '), i['sid'], i['role']): i for d in native['decisions'] for i in d['intents']}
    for x in rr:
        s = x['direction_snapshot']
        assert x['decision_at'] < x['opened']
        scalar_check(s, (ref, x['layer'], 'decision'))
        current = flags(s)
        i = intents[x['decision_at'], x['sid'], x['role']]
        expected = 50 + 50 * math.tanh(2 * s['pvr_E'])
        err = abs(expected - float(i['PVR_score']))
        MAX['native_intent_PVR_score_error_math_tanh'] = max(MAX['native_intent_PVR_score_error_math_tanh'], err)
        assert err < 1e-12, (ref, x['layer'], expected, i['PVR_score'])
        COUNTS['native_PVR_score_checks'] += 1
        for flag in FLAGS:
            v = x['divergence'][flag]
            assert v['current'] == current[flag]
            assert v['ever_in_current_I_episode'] == (v['latest_day'] is not None)
            assert (v['count'] > 0) == v['ever_in_current_I_episode']
            assert v['fresh_CP1_after_prior_divergence'] == bool(s['cp1_receipt'] and v['latest_day'] is not None and v['latest_day'] < x['decision_at'][:10])
            if v['latest_snapshot'] is not None:
                old = v['latest_snapshot']
                assert v['latest_day'] <= x['decision_at'][:10]
                assert old['I_episode'] == s['I_episode'] and old['segment_id'] == s['segment_id'] and old['i_target'] == 1
                assert flags(old)[flag]
                scalar_check(old, (ref, x['layer'], 'latest', flag))
                COUNTS['past_only_same_I_checks'] += 1
    scopes = {'ALL': rr}
    if ref == '2022_2024':
        scopes['2022_2023'] = [x for x in rr if x['opened'][:10] <= '2023-12-29']
        scopes['strict303_postOct8'] = [x for x in rr if '2024-10-08' < x['opened'][:10] <= '2024-12-31']
        assert len(scopes['2022_2023']) == 1557 and len(scopes['strict303_postOct8']) == 303
    for scope, sr in scopes.items():
        saved = results[ref]['scopes'][scope]
        check_agg(sr, saved['all'], (ref, scope, 'all'))
        check_agg([x for x in sr if x['unknown']], saved['unknown'], (ref, scope, 'unknown'))
        for flag in FLAGS:
            v = saved['flags'][flag]
            current = [x for x in sr if x['divergence'][flag]['current']]
            ever = [x for x in sr if x['divergence'][flag]['ever_in_current_I_episode']]
            fresh = [x for x in sr if x['role'] == 'mobile' and x['divergence'][flag]['fresh_CP1_after_prior_divergence']]
            for label, group in [('current', current), ('ever_in_current_I_episode', ever), ('fresh_mobile_after_prior_divergence', fresh),
                                 ('confirmed_fresh_mobile_after_prior_divergence', [x for x in fresh if x['pool_at_fill'] == 'confirmed'])]:
                check_agg(group, v[label], (ref, scope, flag, label))
            for a, data in v['current_by_action'].items(): check_agg([x for x in current if x['action'] == a], data, (ref, scope, flag, a))
    tails = read(BASE / (ref + '_FIXED_ORIGINAL_TAILS.json'))
    assert len(tails) == len(original[ref]) == (83 if ref == '2022_2024' else 94)
    for x, old in zip(tails, original[ref]):
        for k, v in old.items(): assert x[k] == v, (ref, 'fixed tail identity', k)
        assert x['decision_at'] < x['opened']
    fixed = results[ref]['fixed_original_tails']
    check_agg(tails, fixed['all'], (ref, 'all tails'))
    assert fixed['matched_original_members'] == sum(bool(x['matched_No60_layers']) for x in tails)
    byid = {x['layer']: x for x in rr}
    for x in tails: check_agg([byid[lid] for lid in x['matched_No60_layers']], x['matched_No60_money'], (ref, 'matched', x['layer']))
    for flag in FLAGS:
        for level, saved in fixed['flags'][flag].items(): check_agg([x for x in tails if x['divergence'][flag][level]], saved, (ref, 'tail', flag, level))
    SUMMARY[ref] = dict(scopes={k: {'pvr_current_daily_down': v['flags'][FLAGS[0]]['current'], 'act_current_daily_down': v['flags'][FLAGS[1]]['current'],
                                  'pvr_same_I_ever': v['flags'][FLAGS[0]]['ever_in_current_I_episode'],
                                  'pvr_current_amount_price_smoother_divergence': v['flags'][FLAGS[2]]['current']} for k, v in results[ref]['scopes'].items()},
                        fixed_tail_members=len(tails), matched_fixed_tail_members=fixed['matched_original_members'])

# Case CSV audit uses saved case rows only; does not claim full I-history replay.
for p in BASE.glob('*_DAILY.csv'):
    SHA[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    sid = p.name.split('_DAILY')[0]
    with p.open() as f: raw = list(csv.DictReader(f))
    rows = {}
    for row in raw:
        day = row[next(iter(row))][:10]
        s = {k: (None if v in ['', 'nan', 'NaN', 'NaT'] else float(v)) for k, v in row.items()
             if k in ['pvr_r', 'pvr_u', 'pvr_b', 'pvr_e', 'pvr_E', 'pvr_price_smooth', 'act_r', 'act_multiplier', 'act_x', 'act_mom', 'act_price_smooth']}
        scalar_check(s, (sid, day, 'CSV'))
        rows[day] = s
        COUNTS['case_CSV_rows'] += 1
    for rr in allrows.values():
        for x in rr:
            if x['sid'] != sid: continue
            s = rows[x['decision_at'][:10]]
            for k, v in s.items():
                if v is None: assert x['direction_snapshot'][k] is None
                else: assert v == x['direction_snapshot'][k], (sid, x['layer'], k)
            COUNTS['case_entry_CSV_exact_checks'] += 1

assert validation['actual_decision_intent_PVR_score_checked'] == COUNTS['native_PVR_score_checks'] == 3436
assert not validation['actual_decision_intent_PVR_score_mismatches']
report = dict(status='PASS_WITH_SCOPE_LIMITS', counts=dict(COUNTS), max_numeric_errors=dict(MAX),
              formula_proof={'PVR': 'u=tanh(r/s), s>0; multiplier=1+0.5|u|b lies [0.5,1.5], so e has the same sign as r.',
                             'ACT': 'x=r*min(1,sqrt(amount/prior21median)); eligible positive finite amounts make multiplier in (0,1], so x has the same sign as r.',
                             'interpretation': 'Positive historical smoother during a negative day does not mean volume reversed that daily negative sign. PVR E versus same-weight pure-u is a distinct smoother comparison.'},
              summary=SUMMARY,
              limits=['No independent cold read/recalculation of 1206 stocks or all source SHA files.',
                      'Verified stored decision/latest snapshots, group money/clock/IDs, five case CSVs, and native original intent PVR_score for all3436 fills.',
                      'Case CSVs start at first selected decision; cannot independently verify historical latest/count completeness before CSV start.',
                      'Original I-episode ever flags may describe very old divergence; broad coverage is association, not failure timing or a validated rule.',
                      'Fixed original tails preserve83/94 including38/27 unmatched; marked/open and dividend AR are not all cash profits.',
                      'No new accounts/signals, no policy counterfactual, no expanded engine.'],
              sources=SHA)
with (OUT / 'DIRECTION_DIV_AUDIT.json').open('x') as f: json.dump(report, f, ensure_ascii=False, indent=2, default=str)
print(json.dumps(dict(status=report['status'], counts=dict(COUNTS), max_numeric_errors=dict(MAX), summary=SUMMARY), ensure_ascii=False, default=str, indent=2))

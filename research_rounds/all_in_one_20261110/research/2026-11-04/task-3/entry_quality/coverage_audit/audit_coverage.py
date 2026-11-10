"""Pure-read Decimal audit of existing fill populations; no account/signal execution."""
import hashlib
import json
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
OUT = Path(__file__).parent
MA = ROOT / 'risk_constraints/ma63_information_diagnostic_v1'
LOSS = ROOT / 'loss_correction'
SOURCES = {}


def read(p):
    b = p.read_bytes()
    SOURCES[str(p)] = hashlib.sha256(b).hexdigest()
    return json.loads(b)


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + '\n')


def agg(rows):
    sums = {k: sum((D(str(x[k])) for x in rows), D(0)) for k in ['cost', 'net']}
    pos = [x for x in rows if D(x['net']) >= 0]
    neg = [x for x in rows if D(x['net']) < 0]
    tail = [x for x in rows if D(x['net']) / D(x['cost']) >= D('.3')]
    return dict(fills=len(rows), stocks=len({x['sid'] for x in rows}), **sums,
                positive_fills=len(pos), positive_net=sum((D(x['net']) for x in pos), D(0)),
                negative_fills=len(neg), negative_net=sum((D(x['net']) for x in neg), D(0)),
                negative_own_buycash=sum((D(x['cost']) for x in neg), D(0)),
                lifecycle_tail30_fills=len(tail), lifecycle_tail30_net=sum((D(x['net']) for x in tail), D(0)),
                lifecycle_tail30_cost=sum((D(x['cost']) for x in tail), D(0)),
                open_fills=sum(bool(x['qty']) for x in rows))


def group(rows, keys):
    groups = defaultdict(list)
    for x in rows:
        groups[tuple(x[k] for k in keys)].append(x)
    return [dict(labels=dict(zip(keys, k)), **agg(v)) for k, v in sorted(groups.items())]


full = read(MA / '2022_2024_ENTRIES.json')
strong = read(MA / 'strong_ENTRIES.json')
post = [x for x in full if '2024-10-09' <= x['opened'][:10] <= '2024-12-31']
post_saved = read(MA / 'POST_OCT8_303_ACTUAL_FILLS.json')['fills']
assert post == post_saved
assert len(post) == 303
two = [x for x in full if x['opened'][:10] < '2024-01-01']
year24 = [x for x in full if '2024-01-01' <= x['opened'][:10] <= '2024-12-31']
assert len(two) == 1557 and len(full) == 2265 and len(strong) == 1171
checks = []
for name, rows, path in [
    ('2022_2023', two, LOSS / 'absolute_loss_2022_2023/PVR_NO60-2022_2023-JOINED_ENTRIES.json'),
    ('strong', strong, LOSS / 'absolute_loss_2022_2023/PVR_NO60-strong-JOINED_ENTRIES.json'),
]:
    other = {x['layer']: x for x in read(path)}
    assert len(other) == len(rows)
    for x in rows:
        z = other[x['layer']]
        for key in ['sid', 'opened', 'action', 'role', 'receipt', 'qty']:
            assert x[key] == z[key], (name, x['layer'], key)
        for key in ['cost', 'net']:
            assert abs(D(x[key]) - D(z[key])) < D('1e-18'), (name, x['layer'], key)
    checks.append(dict(name=name, rows=len(rows), identity_action_role_receipt_quantity_money=True))

scopes = {'2022_2023': two, 'year2024': year24, 'postOct8_new_fills': post, '2022_2024': full, 'strong': strong}
tables = {}
for name, rows in scopes.items():
    for x in rows:
        assert x['decision_at'] < x['opened']
        assert x['stock']['source_max_used_day'] == x['decision_at'][:10]
        assert x['industry_state']['source_max_used_day'] == x['decision_at'][:10]
        if x['action'] == 'add_to_existing_stock':
            assert x['quantity_before_actual_buy'] > 0
        else:
            assert x['quantity_before_actual_buy'] == 0
        assert abs(D(x['net']) - D(x['strict_realized']) - D(x['open_unrealized']) - D(x['recognized_dividend_AR'])) < D('1e-18')
    with_r = [dict(x, original_probe_R_bin=x['probe_progress']['R_bin']) for x in rows]
    tables[name] = dict(all=agg(rows), by_action=group(rows, ['action']), by_action_role=group(rows, ['action', 'role']),
                        by_action_MA=group(rows, ['action', 'MA63_class']), by_industry_R=group(with_r, ['original_probe_R_bin']),
                        by_action_industry_R=group(with_r, ['action', 'original_probe_R_bin']), by_pool=group(rows, ['pool_at_fill']),
                        scope='Actual fill lifecycle contributions to original account cutoff; NOT deletion-policy or period-wealth counterfactual')
    for g in tables[name]['by_action']:
        g['net_share_of_total_loss_descriptive'] = D(g['net']) / D(tables[name]['all']['net']) if tables[name]['all']['net'] else None

bridge = read(LOSS / 'continuation2024_layers/AFTER_924_LAYER_WEALTH_BRIDGE.json')['PVR_NO60']
assert D(bridge['groups']['new_fill_after_boundary']['after_boundary_wealth_change']) == tables['postOct8_new_fills']['all']['net']
assert sum((D(x['after_boundary_wealth_change']) for x in bridge['groups'].values()), D(0)) == D(bridge['actual_after_wealth_change'])
for x in tables['postOct8_new_fills']['by_action']:
    old = bridge['newfill_actions'][x['labels']['action']]
    assert old['layers'] == x['fills']
    assert abs(D(old['terminal_lifecycle_net']) - x['net']) < D('1e-18')

fixedtails = {}
for ref, rows in [('2022_2024', full), ('strong', strong)]:
    tails = read(MA / (ref + '_ORIGINAL_FIXED_TAIL_COVERAGE.json'))
    ids = {x['layer']: x for x in rows}
    matched = []
    unmatched = []
    for t in tails:
        assert (len(t['matched_No60_layers']) > 0) == (not t['unmatched'])
        if t['unmatched']:
            unmatched.append(t)
        for lid in t['matched_No60_layers']:
            x = ids[lid]
            orig = t['original']
            assert x['sid'] == orig['sid'] and x['decision_at'] == orig['decision_at'] and x['role'] == orig['role'] and x['receipt'] == orig['receipt']
            matched.append(x)
    assert len({x['layer'] for x in matched}) == len(matched)
    fixedtails[ref] = dict(original_tail_members=len(tails), matched_original_members=sum(not x['unmatched'] for x in tails),
                          unmatched_original_members=len(unmatched), matched_fill_by_action=group(matched, ['action']),
                          matched_fill_all=agg(matched),
                          scope='Original whole-life >=30% tail cohort retained in full; matched No60 actual-fill actions only. Unmatched members are NOT synthetic fills or lost profits.')

joined = read(LOSS / 'absolute_loss_2022_2023/PVR_NO60-2022_2023-JOINED_ENTRIES.json')
reentry = [x for x in joined if x['action'] == 'fresh_reentry_after_actual_flat']
same = [x for x in reentry if x['reentry_same_cached_E0']]
new = [x for x in reentry if not x['reentry_same_cached_E0']]
structure = dict(all_reentry=agg(reentry), same_cached_E0=agg(same), different_cached_E0=agg(new),
                 same_E0_loss_share_of_total_2y_loss=agg(same)['net'] / tables['2022_2023']['all']['net'])
predecessors = {}
for ref in ['2022_2023', 'strong']:
    tt = read(LOSS / 'absolute_loss_2022_2023' / ('PVR_NO60-' + ref + '-TAIL_PREDECESSORS.json'))
    neg = [x for x in tt if x['prior_negative_campaigns'] > 0]
    predecessors[ref] = dict(tail_stocks=len(tt), tail_stocks_with_negative_predecessor=len(neg),
                             prior_negative_net=sum((D(x['prior_negative_net']) for x in neg), D(0)),
                             status_counts=dict((s, sum(x['tail_status'] == s for x in tt)) for s in sorted({x['tail_status'] for x in tt})),
                             scope='Earliest ex-post >=30% actual campaign per stock; predecessor negative campaigns counted once. Outcome labels only, no entry rule.')

breadth = {}
for ref, rows in [('2022_2023', two), ('postOct8_new_fills', post),
                  ('postOct8_probe_ge2R', [x for x in post if x['probe_progress']['R_bin'] == '>=2R'])]:
    ss = group(rows, ['sid'])
    negative = sorted([x for x in ss if x['net'] < 0], key=lambda x: x['net'])
    breadth[ref] = dict(stock_groups=len(ss), negative_net_stocks=len(negative),
                        negative_stock_net_sum=sum((x['net'] for x in negative), D(0)),
                        worst5_stock_negative_net=sum((x['net'] for x in negative[:5]), D(0)),
                        worst5_share_of_negative_stock_net=sum((x['net'] for x in negative[:5]), D(0)) / sum((x['net'] for x in negative), D(0)),
                        industries=len({x['industry'] for x in rows}),
                        by_industry=group(rows, ['industry']),
                        scope='Stock and industry netting within this actual-fill cohort; NOT negative-layer gross loss or policy-saving estimate')

save('COVERAGE_TABLES.json', tables)
save('LOSS_BREADTH.json', breadth)
save('FIXED_TAIL_ACTION_COVERAGE.json', fixedtails)
save('REENTRY_STRUCTURE_AND_PREDECESSORS.json', dict(structure=structure, predecessors=predecessors))
save('AUDIT_CHECKS.json', dict(passed=True, checks=checks, post303_saved_exact=True, post303_wealth_bridge=True,
                              fills_3y=len(full), fills_strong=len(strong), unknown_actions=0, account_events=0, signal_recomputations=0,
                              financial_independence='Independent Decimal summation and cross-file identity/bridge audit of shared derived layer ledger; NOT independent native-basis reconstruction'))
save('SOURCE_SHA256.json', SOURCES)
print(json.dumps(dict(scopes={k:v['all'] for k,v in tables.items()}, post_actions=tables['postOct8_new_fills']['by_action'],
                      two_actions=tables['2022_2023']['by_action'], fixedtails=fixedtails, structure=structure, predecessors=predecessors), default=str, ensure_ascii=False, indent=2))

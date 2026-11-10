"""Read original No60 history only. Pre-buy labels use exact decision-CLOSE state.

Primary label: raw marked inventory minus remaining original buy-fee-inclusive
cost basis. Realized PnL and accrued dividends are distinct past-only fields.
Future layer net is joined only AFTER constructing those labels, for attribution.
This is a bounded book reader, not an account/policy or signal implementation.
"""
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path
import gzip
import hashlib
import json
import pandas as pd

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
PAIR = ROOT / 'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'
MA = ROOT / 'risk_constraints/ma63_information_diagnostic_v1'
MANIFEST = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
OUT = Path(__file__).parent / 'add_preprofit_current_no60'
OUT.mkdir(exist_ok=False)
SRC = {}
Z = D(0)
TOL = D('1e-18')


def n(x): return D(str(x))


def read(p, gz=False, lines=False):
    SRC[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    with (gzip.open(p, 'rt') if gz else p.open()) as f:
        return [json.loads(x) for x in f] if lines else json.load(f)


def save(name, x):
    with (OUT / name).open('x') as f:
        json.dump(x, f, indent=2, ensure_ascii=False, default=str)
        f.write('\n')


def close(a, b, k):
    assert abs(n(a) - n(b)) < TOL, (k, a, b)


def sign(v): return 'profit' if v > 0 else 'loss' if v < 0 else 'flat'


b = read(PAIR / 'B.json.gz', gz=True)
daily = read(PAIR / 'daily.jsonl.gz', gz=True, lines=True)
entries = read(MA / '2022_2024_ENTRIES.json')
sm = {x['symbol']: x for x in read(MANIFEST)}
targets = [x for x in entries if x['action'] == 'add_to_existing_stock']
assert len(targets) == 588
target_day = defaultdict(list)
for x in targets: target_day[x['decision_at']].append(x)
frames = {}


def price(sid, at):
    if sid not in frames:
        p = Path(sm[sid]['refs']['facts'])
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert h == sm[sid]['output_sha256'][str(p)]
        SRC[str(p)] = h
        frames[sid] = pd.read_parquet(p, columns=['raw_close', 'factor', 'close'])
        assert frames[sid].index.is_unique and frames[sid].index.is_monotonic_increasing
    d = pd.Timestamp(at[:10])
    r = frames[sid].loc[d]
    assert n(r.raw_close) > 0 and n(r.factor) > 0
    assert abs(n(r.close) - n(r.raw_close) * n(r.factor)) < D('.000001')
    return n(r.raw_close)


events = []
for ix, t in enumerate(b['trades']): events.append((t['at'], 1, ix, 'trade', t))
for ix, t in enumerate(b['audit']):
    if t['kind'] == 'split': events.append((t['at'], 0, ix, 'split', t))
    elif t['kind'] == 'dividend_accrual':
        assert t['receivable']['paid_at'] is None
        events.append((t['receivable']['ex_at'], 2, ix, 'dividend', t['receivable']))
assert not any(x['kind'] == 'dividend_paid' for x in b['audit'])
events.sort(key=lambda e: e[:3])
layers = {}
qstock = defaultdict(int)
campaign_no = defaultdict(int)
campaign_layers = defaultdict(list)
ei = 0
snapshots = []
check = dict(native_closes=0, held_layer_checks=0, split_events=0, dividend_events=0,
             no_fractional_splits=True, no_dividend_payments=True, source_quote_unknowns=0)
for r in daily:
    at = r['at']
    while ei < len(events) and events[ei][0] <= at:
        et, _, _, kind, t = events[ei]
        ei += 1
        if kind == 'split':
            check['split_events'] += 1
            for l in layers.values():
                if l['sid'] == t['sid'] and l['q']:
                    exact = D(l['q']) * n(t['ratio'])
                    assert exact == int(exact)
                    qstock[l['sid']] += int(exact) - l['q']
                    l['q'] = int(exact)
        elif kind == 'dividend':
            check['dividend_events'] += 1
            held = [l for l in layers.values() if l['sid'] == t['security_id'] and l['q']]
            total = sum(l['q'] for l in held)
            assert total > 0
            for l in held:
                l['div'] += n(t['net_local']) * D(l['q']) / D(total)
                l['div_events'].append(dict(ex_at=et, event_id=t['event_id'], receivable_paid_at=t['paid_at']))
        elif t['side'] == 'buy':
            sid = t['security_id']
            if qstock[sid] == 0: campaign_no[sid] += 1
            lid = t['layer']
            assert lid not in layers
            cost = n(t['gross_cny']) + n(t['fees_cny'])
            layers[lid] = dict(id=lid, sid=sid, q=t['shares'], basis=cost, cash=-cost,
                               real=Z, div=Z, div_events=[], campaign=campaign_no[sid],
                               buy_at=t['at'], last_trade_at=t['at'], last_split_at=None)
            campaign_layers[sid, campaign_no[sid]].append(lid)
            qstock[sid] += t['shares']
        else:
            proceeds = Z
            for part in t['parts']:
                l = layers[part['layer']]
                q = part['shares']
                assert l['sid'] == t['security_id'] and 0 < q <= l['q']
                used = l['basis'] * D(q) / D(l['q'])
                net = n(part['net_cash'])
                l['basis'] -= used
                l['q'] -= q
                l['cash'] += net
                l['real'] += net - used
                l['last_trade_at'] = t['at']
                qstock[l['sid']] -= q
                proceeds += net
            close(proceeds, n(t['gross_cny']) - n(t['fees_cny']), 'native sell parts')
    native = {x['id']: x for x in r['layers']}
    assert {sid: q for sid, q in qstock.items() if q} == {sid: int(q) for sid, q in r['positions'].items() if q}
    assert set(native) == {lid for lid, l in layers.items() if l['q']}
    for lid, nl in native.items():
        l = layers[lid]
        assert l['q'] == nl['qty']
        close(l['cash'], nl['cash'], ('native held cash', at, lid))
        close(l['div'], nl['dividend'], ('native held dividend', at, lid))
        close(l['cash'], l['real'] - l['basis'], ('cash-real-basis', at, lid))
        check['held_layer_checks'] += 1
    close(sum((l['div'] for l in layers.values()), Z), r['dividend_receivable'], ('native total unpaid AR', at))
    check['native_closes'] += 1
    for x in target_day.get(at, []):
        sid = x['sid']
        held = [l for l in layers.values() if l['sid'] == sid and l['q']]
        q = sum(l['q'] for l in held)
        mark = price(sid, at)
        basis = sum((l['basis'] for l in held), Z)
        value = D(q) * mark
        unreal = value - basis
        current = [layers[lid] for lid in campaign_layers[sid, campaign_no[sid]]] if q else []
        realized = sum((l['real'] for l in current), Z)
        div = sum((l['div'] for l in current), Z)
        economic = realized + unreal + div
        active_real = sum((l['real'] for l in held), Z)
        active_div = sum((l['div'] for l in held), Z)
        for l in held:
            assert l['buy_at'] <= at and l['last_trade_at'] <= at
            assert all(z['ex_at'] <= at and z['receivable_paid_at'] is None for z in l['div_events'])
        snapshots.append(dict(layer=x['layer'], sid=sid, name=x['name'], industry=x['industry'],
                              decision_at=at, fill_at=x['opened'], original_budget_order=x['budget_order'],
                              pre_close_q=q, actual_q_before_fill=x['quantity_before_actual_buy'],
                              raw_close=mark, remaining_buy_fee_inclusive_basis=basis, marked_inventory=value,
                              pre_close_unrealized=unreal, pre_close_unrealized_state=sign(unreal) if q else 'no_preclose_inventory',
                              pre_close_current_campaign=campaign_no[sid] if q else None,
                              pre_close_campaign_realized=realized, pre_close_campaign_accrued_dividend_AR=div,
                              pre_close_campaign_wealth=economic,
                              pre_close_campaign_wealth_state=sign(economic) if q else 'no_preclose_inventory',
                              pre_close_active_layer_realized=active_real, pre_close_active_layer_accrued_dividend_AR=active_div,
                              pre_close_active_layer_wealth=active_real + unreal + active_div,
                              native_daily_source=str(PAIR / 'daily.jsonl.gz'), facts_source=sm[sid]['refs']['facts'],
                              held_layers=[dict(layer=l['id'], q=l['q'], basis=l['basis'], cash=l['cash'],
                                                realized=l['real'], accrued_dividend=l['div'],
                                                buy_at=l['buy_at'], last_trade_at=l['last_trade_at'], div_events=l['div_events']) for l in held]))
assert ei == len(events) and len(snapshots) == len(targets)
native_final = {x['id']: x for x in b['layers']}
for lid, l in layers.items():
    assert l['q'] == native_final[lid]['qty']
    close(l['cash'], native_final[lid]['cash'], ('final native cash', lid))
    close(l['div'], native_final[lid]['dividend'], ('final native div', lid))
    close(l['basis'], Z, ('all final positions closed', lid))

# Future outcome labels are attached here, after past-only snapshot construction.
entrymap = {x['layer']: x for x in entries}
for x in snapshots:
    e = entrymap[x['layer']]
    x.update(actual_add_buycash=n(e['cost']), actual_add_terminal_net=n(e['net']),
             actual_add_terminal_loss=e['qty'] == 0 and n(e['net']) < 0,
             terminal_scope='Added-layer complete lifetime through 2024 cutoff, including recognized dividend AR; NOT pre-buy knowledge or whole-position outcome')


def aggregate(rr):
    neg = [x for x in rr if x['actual_add_terminal_loss']]
    pos = [x for x in rr if not x['actual_add_terminal_loss']]
    return dict(fills=len(rr), stocks=len({x['sid'] for x in rr}),
                actual_add_buycash=sum((x['actual_add_buycash'] for x in rr), Z),
                terminal_net=sum((x['actual_add_terminal_net'] for x in rr), Z),
                terminal_negative_fills=len(neg), terminal_negative_net=sum((x['actual_add_terminal_net'] for x in neg), Z),
                terminal_negative_own_add_buycash=sum((x['actual_add_buycash'] for x in neg), Z),
                terminal_positive_fills=len(pos), terminal_positive_net=sum((x['actual_add_terminal_net'] for x in pos), Z),
                pre_close_held_basis_observation_sum=sum((x['remaining_buy_fee_inclusive_basis'] for x in rr), Z),
                pre_close_unrealized_observation_sum=sum((x['pre_close_unrealized'] for x in rr), Z))


summaries = {}
for ref, rr in [('2022_2023', [x for x in snapshots if x['fill_at'][:10] < '2024-01-01']),
                ('postOct8_303_adds', [x for x in snapshots if '2024-10-09' <= x['fill_at'][:10] <= '2024-12-31'])]:
    allstats = aggregate(rr)
    groups = {}
    for field in ['pre_close_unrealized_state', 'pre_close_campaign_wealth_state']:
        groups[field] = []
        for label in sorted({x[field] for x in rr}):
            g = aggregate([x for x in rr if x[field] == label])
            g.update(label=label,
                     share_of_all_add_negative_net=g['terminal_negative_net'] / allstats['terminal_negative_net'],
                     share_of_all_add_buycash=g['actual_add_buycash'] / allstats['actual_add_buycash'],
                     share_of_all_add_negative_own_buycash=g['terminal_negative_own_add_buycash'] / allstats['terminal_negative_own_add_buycash'])
            groups[field].append(g)
    summaries[ref] = dict(all_adds=allstats, groups=groups)
assert summaries['2022_2023']['all_adds']['fills'] == 404
assert summaries['postOct8_303_adds']['all_adds']['fills'] == 85
save('ADD_PREPROFIT_ROWS.json', snapshots)
save('SUMMARY.json', summaries)
save('CHECKS.json', dict(passed=True, **check, add_rows=len(snapshots), source_book_version='No60 own continuous 2022->2024, not original PVR or C10',
                         primary='decision raw mark minus remaining original buy-fee-inclusive held basis; no hypothetical sale fee',
                         alternative='same currently open flat-to-flat stock campaign realized + held unrealized + past accrued dividend AR',
                         lookahead='All pre-close features built before joining terminal added-layer net; no future close or label used in pre-close state',
                         account_events=0, new_signals=0, no_counterfactual=True))
SRC[str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
save('SOURCE_SHA256.json', SRC)
print(json.dumps(summaries, indent=2, ensure_ascii=False, default=str))

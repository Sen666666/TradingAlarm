"""Read saved native trade/split/AR streams; describe past-only decision timeline.
No account/policy initialization, signal rebuild, horizon search or deleted-PnL.
"""
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path
import gzip, hashlib, json, csv
import pandas as pd

O = Path(__file__).parent
B = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
E = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality')
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC = {}
Z = D(0)
TOL = D('1e-17')
FRAMES = {}
SM = {}
ACTIONS = ['first_actual_participation', 'add_to_existing_stock', 'fresh_reentry_after_actual_flat']


def n(x): return D(str(x))


def read(p, gz=False, lines=False):
    SRC[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    with (gzip.open(p, 'rt') if gz else p.open()) as f:
        return [json.loads(x) for x in f] if lines else json.load(f)


def save(name, x):
    with (O / name).open('x') as f:
        json.dump(x, f, ensure_ascii=False, indent=2, default=str)
        f.write('\n')


def close(a, b, label): assert abs(n(a) - n(b)) < TOL, (label, a, b)


def state(v, count=1): return 'no_cohort' if not count else 'positive' if v > 0 else 'negative' if v < 0 else 'zero'


def mark(sid, d):
    if sid not in FRAMES:
        p = Path(SM[sid]['refs']['facts'])
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert h == SM[sid]['output_sha256'][str(p)]
        SRC[str(p)] = h
        f = pd.read_parquet(p, columns=['raw_close'])
        assert f.index.is_unique and f.index.is_monotonic_increasing
        FRAMES[sid] = f
    f = FRAMES[sid]
    ix = f.index.searchsorted(pd.Timestamp(d), side='right') - 1
    assert ix >= 0
    price = n(f.iloc[ix].raw_close)
    observed = str(f.index[ix].date())
    assert price.is_finite() and price > 0 and observed <= d
    return price, observed


def money(ll, marks):
    cost = sum((l['cost'] for l in ll), Z)
    real = sum((l['real'] for l in ll), Z)
    basis = sum((l['basis'] for l in ll), Z)
    value = sum((D(l['q']) * marks[l['sid']][0] for l in ll if l['q']), Z)
    div = sum((l['div'] for l in ll), Z)
    cash = sum((l['cash'] for l in ll), Z)
    net = real + value - basis + div
    close(net, cash + value + div, 'cohort cash/real/unreal bridge')
    return dict(layers=len(ll), stocks=len({l['sid'] for l in ll}), actual_buycash=cost,
                strict_realized=real, unrealized=value-basis, recognized_dividend_AR=div,
                recognized_wealth=net, net_trade_cash=cash, remaining_basis=basis,
                current_market_value=value, active_layers=sum(l['q'] > 0 for l in ll),
                state=state(net, len(ll)), own_buycash_descriptive_ratio=net/cost if cost else None)


def completed(ll, at, coreids):
    assert all(l['q'] == 0 for l in ll)
    cash = sum((l['cash'] for l in ll), Z)
    ar = sum((l['div'] for l in ll), Z)
    return dict(closed_at=at, layer_ids=[l['id'] for l in ll], actual_buycash=sum((l['cost'] for l in ll), Z),
                net_trade_cash=cash, recognized_dividend_AR=ar, recognized_wealth=cash+ar,
                negative_trade_cash=cash < 0, negative_recognized_wealth=cash+ar < 0,
                same_stock_core_layers_alive_at_mobile_close=coreids)


def history(hh, at):
    assert all(x['closed_at'] <= at for x in hh)
    return dict(completed_cycles=len(hh), negative_trade_cash_cycles=sum(x['negative_trade_cash'] for x in hh),
                negative_recognized_wealth_cycles=sum(x['negative_recognized_wealth'] for x in hh),
                cumulative_completed_net_trade_cash=sum((x['net_trade_cash'] for x in hh), Z),
                cumulative_completed_AR=sum((x['recognized_dividend_AR'] for x in hh), Z),
                last_completed=None if not hh else dict(hh[-1]))


def outcome(rr):
    return dict(fills=len(rr), stocks=len({x['sid'] for x in rr}), actual_buycash=sum((n(x['cost']) for x in rr), Z),
                net=sum((n(x['net']) for x in rr), Z), positive_net=sum((n(x['net']) for x in rr if n(x['net'])>0), Z),
                negative_net=sum((n(x['net']) for x in rr if n(x['net'])<0), Z),
                negative_fills=sum(n(x['net'])<0 for x in rr),
                negative_own_buycash=sum((n(x['cost']) for x in rr if n(x['net'])<0), Z),
                strict_realized=sum((n(x['strict_realized']) for x in rr), Z),
                open_unrealized=sum((n(x['open_unrealized']) for x in rr), Z),
                recognized_dividend_AR=sum((n(x['recognized_dividend_AR']) for x in rr), Z),
                open_layers=sum(bool(x['qty']) for x in rr))


def groups(rr, fields):
    bins = defaultdict(list)
    for x in rr: bins[tuple(x[k] for k in fields)].append(x)
    return [dict(labels=dict(zip(fields, key)), **outcome(v)) for key, v in sorted(bins.items())]


def run(ref, pair, expected):
    b = read(pair / 'B.json.gz', gz=True)
    ds = read(pair / 'daily.jsonl.gz', gz=True, lines=True)
    ee = read(B / 'risk_constraints/ma63_information_diagnostic_v1' / (ref+'_ENTRIES.json'))
    assert len(ds) == expected
    emap = {x['layer']: x for x in ee}
    byat = defaultdict(list)
    for x in ee:
        assert x['decision_at'] < x['opened']
        byat[x['decision_at']].append(x)
    # Existing local-high fields are copied by exact identity; no q/cut policy field.
    local = {x['layer']: x for x in read(E / 'local_high' / (ref+'_ROWS.json'))}
    events = [(t['at'], 1, ix, 'trade', t) for ix, t in enumerate(b['trades'])]
    for ix, t in enumerate(b['audit']):
        if t['kind'] == 'split': events.append((t['at'], 0, ix, 'split', t))
        elif t['kind'] == 'dividend_accrual':
            assert t['receivable']['paid_at'] is None
            events.append((t['receivable']['ex_at'], 2, ix, 'dividend', t['receivable']))
    assert not any(x['kind'] == 'dividend_paid' for x in b['audit'])
    events.sort(key=lambda x:x[:3])
    layers = {}
    qstock = defaultdict(int)
    qmobile = defaultdict(int)
    stock_current = defaultdict(list)
    mobile_current = defaultdict(list)
    stock_history = defaultdict(list)
    mobile_history = defaultdict(list)
    allcompleted = []
    ei = 0
    snapshots = []
    daily = []
    recent_sector_daily = []
    previous_action_wealth = {a:Z for a in ACTIONS}
    check = dict(closes=0, held_layer_checks=0, stale_mark_observations=0, split_events=0, dividend_events=0)
    for di, r in enumerate(ds):
        at = r['at']; d = at[:10]
        while ei < len(events) and events[ei][0] <= at:
            et, _, _, kind, t = events[ei]; ei += 1
            if kind == 'split':
                check['split_events'] += 1
                for l in layers.values():
                    if l['sid'] == t['sid'] and l['q']:
                        exact = D(l['q']) * n(t['ratio']); assert exact == int(exact)
                        delta = int(exact) - l['q']; qstock[l['sid']] += delta
                        if l['role'] == 'mobile': qmobile[l['sid']] += delta
                        l['q'] = int(exact)
            elif kind == 'dividend':
                check['dividend_events'] += 1
                ll = [l for l in layers.values() if l['sid']==t['security_id'] and l['q']]
                tq = sum(l['q'] for l in ll); assert tq > 0
                for l in ll: l['div'] += n(t['net_local']) * D(l['q']) / D(tq)
            elif t['side'] == 'buy':
                sid = t['security_id']; lid = t['layer']; e = emap[lid]
                assert lid not in layers
                if qstock[sid] == 0: stock_current[sid] = []
                if e['role']=='mobile' and qmobile[sid]==0: mobile_current[sid] = []
                cost = n(t['gross_cny']) + n(t['fees_cny'])
                layers[lid] = dict(id=lid, sid=sid, sector=e['sector'], role=e['role'], action=e['action'],
                                   opened=t['at'], opened_day=t['at'][:10], q=t['shares'], basis=cost,
                                   real=Z, cash=-cost, div=Z, cost=cost)
                stock_current[sid].append(lid)
                if e['role']=='mobile': mobile_current[sid].append(lid); qmobile[sid] += t['shares']
                qstock[sid] += t['shares']
            else:
                sid = t['security_id']; before_m = qmobile[sid]
                proceeds = Z
                for part in t['parts']:
                    l = layers[part['layer']]; q = part['shares']
                    assert l['sid']==sid and 0<q<=l['q']
                    used = l['basis'] * D(q)/D(l['q']); net = n(part['net_cash'])
                    l['basis'] -= used; l['q'] -= q; l['cash'] += net; l['real'] += net-used
                    qstock[sid] -= q
                    if l['role']=='mobile': qmobile[sid] -= q
                    proceeds += net
                close(proceeds, n(t['gross_cny'])-n(t['fees_cny']), 'native sale parts')
                coreids = [l['id'] for l in layers.values() if l['sid']==sid and l['q'] and l['role']=='core']
                if before_m and qmobile[sid]==0:
                    mobile_history[sid].append(completed([layers[lid] for lid in mobile_current[sid]], et, coreids))
                if qstock[sid]==0:
                    x = completed([layers[lid] for lid in stock_current[sid]], et, [])
                    stock_history[sid].append(x); allcompleted.append(dict(x, sid=sid))
        native = {x['id']:x for x in r['layers']}
        assert {sid:q for sid,q in qstock.items() if q} == {sid:int(q) for sid,q in r['positions'].items() if q}
        assert set(native)=={lid for lid,l in layers.items() if l['q']}
        marks = {sid:mark(sid,d) for sid,q in qstock.items() if q}
        check['stale_mark_observations'] += sum(v[1]!=d for v in marks.values())
        for lid,nl in native.items():
            l = layers[lid]; assert l['q']==nl['qty']
            close(l['cash'],nl['cash'],('native cash',at,lid));close(l['div'],nl['dividend'],('native AR',at,lid))
            check['held_layer_checks'] += 1
        total = money(list(layers.values()),marks)
        close(total['current_market_value'],r['inventory'],('native raw mark',at))
        close(total['recognized_dividend_AR'],r['dividend_receivable'],('native AR total',at))
        close(D(1000000)+total['recognized_wealth'],r['nav'],('native NAV bridge',at))
        lo = ds[max(0,di-20)]['at'][:10]
        recent = [l for l in layers.values() if lo <= l['opened_day'] <= d]
        recent_all = money(recent,marks)
        recent_actions = {a:money([l for l in recent if l['action']==a],marks) for a in ACTIONS}
        sectors = {l['sector'] for l in recent}
        recent_sector = {s:money([l for l in recent if l['sector']==s],marks) for s in sectors}
        byaction = {}
        for a in ACTIONS:
            al = [l for l in layers.values() if l['action']==a]
            allm = money(al,marks)
            new = [l for l in al if l['opened_day']==d]
            byaction[a] = dict(wealth_change=allm['recognized_wealth']-previous_action_wealth[a],
                               new_buycash=sum((l['cost'] for l in new),Z), new_layers=len(new))
            previous_action_wealth[a] = allm['recognized_wealth']
        dd = dict(at=at, nav=n(r['nav']), ACT_after_CLOSE=r['on'],
                  wealth_change=sum((x['wealth_change'] for x in byaction.values()),Z),
                  actions=byaction, recent21_window_first=lo,recent21_window_last=d,
                  recent21_close_observations=min(di+1,21),recent21_all=recent_all,
                  recent21_by_action=recent_actions,
                  completed_stock_cycles=history(allcompleted,at))
        daily.append(dd)
        for sector,m in recent_sector.items():recent_sector_daily.append(dict(at=at,sector=sector,**m))
        for x in byat.get(at,[]):
            sid=x['sid']; sector=x['sector']; lcl=local[x['layer']]
            assert lcl['sid']==sid and lcl['decision_at']==at and lcl['opened']==x['opened']
            held=[l for l in layers.values() if l['sid']==sid and l['q']]
            current=[layers[lid] for lid in stock_current[sid]] if qstock[sid] else []
            sh=history(stock_history[sid],at); mh=history(mobile_history[sid],at)
            sm=money([l for l in recent if l['sid']==sid],marks)
            industry_recent=recent_sector.get(sector,money([],marks))
            snap=dict(layer=x['layer'],sid=sid,name=x['name'],industry=x['industry'],sector=sector,
                      decision_at=at,actual_fill_at=x['opened'],action=x['action'],role=x['role'],pool=x['pool_at_fill'],
                      budget_order=x['budget_order'],
                      stock_price_position=dict(x['stock']),industry_price_position=dict(x['industry_state']),
                      original_industry_probe_progress=dict(x['probe_progress']),MA63_class=x['MA63_class'],ETF_macro=x['ETF_macro'],
                      pre_close_stock_quantity=qstock[sid],pre_close_mobile_quantity=qmobile[sid],
                      pre_close_held=money(held,marks),pre_close_current_stock_campaign=money(current,marks),
                      past_completed_stock=sh,past_completed_mobile=mh,
                      recent21_window_first=lo,recent21_window_last=d,recent21_close_observations=min(di+1,21),
                      recent21_account=recent_all,recent21_account_by_action=recent_actions,
                      recent21_same_industry=industry_recent,recent21_same_stock=sm,
                      recent21_account_state=recent_all['state'],recent21_industry_state=industry_recent['state'],
                      past_stock_failure_state='past_negative_completed_cash' if sh['negative_trade_cash_cycles'] else 'no_past_negative_completed_cash',
                      past_mobile_failure_state='past_negative_completed_cash' if mh['negative_trade_cash_cycles'] else 'no_past_negative_completed_cash',
                      original_local_price_context={k:lcl.get(k) for k in ['last_actual_buy_layer','last_actual_buy_at','post_entry_high_excluding_current',
                                                                        'post_entry_high_observations','previous_mobile_exit_high','mobile_restart_with_core_alive']})
            snapshots.append(snap)
        check['closes']+=1
    assert ei==len(events) and len(snapshots)==len(ee)
    final={x['id']:x for x in b['layers']}
    for lid,l in layers.items():
        assert l['q']==final[lid]['qty'];close(l['cash'],final[lid]['cash'],('final cash',lid));close(l['div'],final[lid]['dividend'],('final AR',lid))
        e=emap[lid]; price=mark(l['sid'],ds[-1]['at'][:10])[0] if l['q'] else Z
        close(l['cash']+l['div']+D(l['q'])*price,e['net'],('terminal layer',lid))
    # Attach final outcomes only after all historical snapshots have been made.
    for x in snapshots:
        e=emap[x['layer']]
        for k in ['cost','net','qty','strict_realized','open_unrealized','recognized_dividend_AR']:x[k]=e[k]
        assert x['recent21_window_last']==x['decision_at'][:10]
        for histkey in ['past_completed_stock','past_completed_mobile']:
            last=x[histkey]['last_completed'];assert last is None or last['closed_at']<=x['decision_at']
    save(ref+'_DECISION_TIMELINE.json',snapshots)
    save(ref+'_DAILY.json',daily)
    save(ref+'_RECENT21_SECTOR_DAILY.json',recent_sector_daily)
    save(ref+'_COMPLETED_STOCK_CYCLES.json',dict(stock_history))
    save(ref+'_COMPLETED_MOBILE_CYCLES.json',dict(mobile_history))
    print('DONE',ref,len(snapshots),'closes',len(ds),'marks',len(FRAMES),flush=True)
    return snapshots,daily,check


def main():
    global SM
    SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
    save('PROTOCOL.json',dict(horizon=21,horizon_search=0,
         recent_window='Current plus previous20 saved native trading CLOSE observations, inclusive actual opens within those dates. Not21 calendar days or exact per-stockPVR valid-bar21.',
         snapshot='Only actual fills/splits/AR ex_at<=decisionCLOSE; current raw mark is native last-known source observation<=day.',
         recent_cohort='All layers ACTUALLY opened within window, including those already closed. Their strict real+unreal+AR at current decision, and original actual buycash. No terminal labels.',
         failures='Original full-stock or mobile flat-to-flat cycles completed before decision. Primary negative net executed trade cash, AR separate. Not pending exit requests.',
         worst_months=['2022-12','2022-01','2022-04','2022-03','2023-05','2022-08'],
         worst_months_source=str(B/'risk_constraints/absolute_loss_2022_2023/READOUT.md'),
         account_events=0,new_signals=0,policy_tests=0))
    data={};checks={}
    for ref,pair,days in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',726),
                          ('strong',B/'pvr_pool_feasibility/runs/2025_26/pair',242)]:
        rr,dd,cc=run(ref,pair,days);data[ref]=(rr,dd);checks[ref]=cc
    summaries={}
    for ref,(rr,dd) in data.items():
        scopes={'all':rr}
        if ref=='2022_2024':
            scopes['2022_2023']=[x for x in rr if x['actual_fill_at'][:10]<'2024-01-01']
            scopes['post303']=[x for x in rr if '2024-10-09'<=x['actual_fill_at'][:10]<='2024-12-31']
            assert len(scopes['2022_2023'])==1557 and len(scopes['post303'])==303
        for scope,sr in scopes.items():
            summaries[ref+'_'+scope]=dict(all=outcome(sr),by_action=groups(sr,['action']),
                 action_recent_account_state=groups(sr,['action','recent21_account_state']),
                 action_recent_industry_state=groups(sr,['action','recent21_industry_state']),
                 action_prior_stock_failure=groups(sr,['action','past_stock_failure_state']),
                 action_prior_mobile_failure=groups(sr,['action','past_mobile_failure_state']))
    save('SUMMARY.json',summaries)
    months=['2022-12','2022-01','2022-04','2022-03','2023-05','2022-08']
    rr,dd=data['2022_2024'];mm=[]
    for month in months:
        days=[d for d in dd if d['at'].startswith(month)]
        filled=[x for x in rr if x['actual_fill_at'].startswith(month)]
        decisions=[x for x in rr if x['decision_at'].startswith(month)]
        mm.append(dict(month=month,actual_period_wealth=sum((d['wealth_change'] for d in days),Z),
                       actual_period_by_action={a:dict(wealth=sum((d['actions'][a]['wealth_change'] for d in days),Z),
                                                    actual_buycash=sum((d['actions'][a]['new_buycash'] for d in days),Z)) for a in ACTIONS},
                       entry_month_lifetime_outcomes_by_action=groups(filled,['action']),
                       decision_month_recent21_action_state=groups(decisions,['action','recent21_account_state']),
                       daily_trace=days))
    save('FIXED_WORST_MONTHS.json',mm)
    # A compact daily CSV avoids repeatedly summing overlapping rolling cohorts.
    cols=['reference','at','nav','wealth_change','recent21_window_first','recent21_window_last',
          'recent21_layers','recent21_buycash','recent21_realized','recent21_unrealized','recent21_AR','recent21_wealth','recent21_state',
          'new_first_buycash','new_add_buycash','new_reentry_buycash']
    with (O/'DAILY_TRACE.csv').open('x') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for ref,(_,dd) in data.items():
            for d in dd:
                m=d['recent21_all'];w.writerow(dict(reference=ref,at=d['at'],nav=d['nav'],wealth_change=d['wealth_change'],
                  recent21_window_first=d['recent21_window_first'],recent21_window_last=d['recent21_window_last'],
                  recent21_layers=m['layers'],recent21_buycash=m['actual_buycash'],recent21_realized=m['strict_realized'],
                  recent21_unrealized=m['unrealized'],recent21_AR=m['recognized_dividend_AR'],recent21_wealth=m['recognized_wealth'],recent21_state=m['state'],
                  new_first_buycash=d['actions'][ACTIONS[0]]['new_buycash'],new_add_buycash=d['actions'][ACTIONS[1]]['new_buycash'],
                  new_reentry_buycash=d['actions'][ACTIONS[2]]['new_buycash']))
    save('VALIDATION.json',dict(passed=True,references=checks,all_funded_decisions=3436,
         native_q_cash_dividend_rawmark_NAV=True,no_new_accounts=True,new_signals=0,
         limitations=['Original survivors/current sectors/daily proxy execution/development data.',
                      'Rolling cohorts overlap and cannot be summed as independent profit; summary groups are final realized paths, not policy savings.',
                      'Native last-known raw marking retained for suspensions/missing day; quote observation day<=decision asserted.',
                      'First observed21 early account dates have shorter warm cohort; not padded with earlier nonexistent account positions.',
                      'First/add/reentry classified at real fill; timeline features at original decisionCLOSE. No skipped/unfunded opportunities.']))
    SRC[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save('SOURCE_SHA256.json',SRC)


if __name__=='__main__':main()

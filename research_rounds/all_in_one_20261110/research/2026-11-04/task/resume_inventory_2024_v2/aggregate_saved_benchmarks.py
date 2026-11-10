"""Read-only aggregation of archived ETF records; no strategy or account execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
from datetime import datetime, timezone
import csv, gzip, hashlib, json

O = Path(__file__).resolve().parent
T = O.parent
BASE = T / 'benchmark_2022_2023/continuation2024'
Z = D(0)
EPS = D('.000001')
SOURCES = {}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def bind(p):
    p = Path(p)
    SOURCES[str(p.relative_to(T))] = sha(p)
    return p

def read(p):
    return json.loads(bind(p).read_text())

def rows(p):
    return list(csv.DictReader(bind(p).open()))

def near(a, b):
    assert abs(D(a) - D(b)) < EPS, (a, b)

def save(name, value):
    p = O / name
    assert not p.exists(), p
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')

def write_csv(name, items):
    p = O / name
    assert not p.exists(), p
    with p.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)

def local_dd(start, values):
    peak, dd = start, Z
    for value in values:
        peak = max(peak, value)
        dd = max(dd, 1-value/peak)
    return dd*100

inventory_paths = [
    'market_gross_robustness_small_ledger_review_v1/FINAL_SMALL87_FINANCE_ATOMIC_COST_CONTROL_REVIEW.json',
    'market_gross_robustness_v1/SMALL87_PRODUCER_HANDOFF.json',
    'market_gross_robustness_v1/small87-cost1-v2/COMPLETED.json',
    'market_gross_robustness_v1/small87-cost15-v2/COMPLETED.json',
    'market_gross_robustness_v1/small87-cost1-v1/FAILED_PRE_ACCOUNT.json',
    'market_gross_robustness_v1/small87-cost15-v1/FAILED_PRE_ACCOUNT.json',
    'market_gross_robustness_v1/FULL_NO_AUTHORIZATION_ZERO_EVENT_CHECK.json',
    'market_gross_robustness_v1/FULL_PREPARATION_PROTOCOL.txt',
    'market_gross_robustness_v1/full_adapter.py',
    'market_gross_robustness_v1/run_window.py',
]
inventory = []
for name in inventory_paths:
    p = bind(T/name)
    record = dict(path=name, SHA256=sha(p), bytes=p.stat().st_size,
                  mtime_UTC=datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat())
    if p.suffix == '.json':
        j = json.loads(p.read_text())
        record['status_fields'] = {k:j[k] for k in ['status','passed','account_daily_bridges',
            'actual_atomic_snapshots','full','new_accounts','full_economic_run_authorized',
            'financial_input_loader_calls','native_accounts','trades','reason'] if k in j}
    inventory.append(record)
robust = T/'market_gross_robustness_v1'
all_paths = sorted(str(p.relative_to(robust)) for p in robust.rglob('*') if p.is_file())
current_full_evidence = [p for p in all_paths if 'source-history/' not in p and
    ('FULL_SOURCE_MANIFEST.json' in p or 'PROPOSED_FULL_AUTHORIZATION.json' in p or
     ('full-' in p and any(x in p for x in ['STARTED','DONE','WINDOW_RESULT'])))]
assert not current_full_evidence, current_full_evidence
gate = read(T/inventory_paths[0])
assert gate['status'] == 'PASS_SMALL87_NATIVE_FINANCE_ATOMIC_ACTUAL_COST15_AND_CONTROL_ONLY'
driver = (T/'market_gross_robustness_v1/run_window.py').read_text()
gate_expression = "read(q).get('passed')is True or read(q).get('status')=='PASS'"
assert gate_expression in driver
assert not (gate.get('passed') is True or gate.get('status') == 'PASS')
save('INVENTORY.json', dict(recorded_UTC=datetime.now(timezone.utc).isoformat(), files=inventory,
    final_small_gate='ACTUAL_FILE_PASS_87_DAILY_1448_ATOMIC',
    full_economic_run_markers_or_full_manifest=current_full_evidence,
    full_run_status='NOT_ESTABLISHED_BY_ANY_SAVED_FULL_AUTHORIZATION_MANIFEST_OR_RUN_MARKER',
    process_liveness='UNKNOWN: ps -axo pid,etime,command denied with PermissionError(EPERM); no process was resumed or signaled',
    static_full_preparation_blocker=dict(path='market_gross_robustness_v1/run_window.py',line=60,
        expected='passed is True OR status == PASS', actual_status=gate['status'],
        actual_passed_key_present='passed' in gate,
        result='Current exact final finance receipt would be rejected before loading/account; not executed or modified'),
    new_accounts_or_backtests=0))

audit = read(T/'independent_review/BENCHMARK_2024_CONTINUATION_INDEPENDENT_AUDIT.json')
assert audit['status']=='PASS_WITH_SCOPE'
parent = read(BASE/'PARENT_STATE.json')
BOUNDARIES = ['2023-12-29', '2024-09-23', '2024-10-08', '2024-12-31']
PHASES = [('pre924','2024-01-02','2024-09-23'),
          ('924_to_Oct8','2024-09-24','2024-10-08'),
          ('post_Oct8','2024-10-09','2024-12-31'),
          ('year2024','2024-01-02','2024-12-31')]
boundaries, phases, realized_proofs = [], [], {}
calendar = None
for arm in ['BUY_HOLD','MA63_90']:
    ds = rows(BASE/'daily_2022_2024'/f'{arm}.csv')
    year = [r for r in ds if r['date'].startswith('2024')]
    assert len(ds)==726 and len(year)==242
    if calendar is None: calendar = [r['date'] for r in year]
    else: assert calendar == [r['date'] for r in year]
    dates = {r['date']:i for i,r in enumerate(ds)}
    near(ds[dates['2023-12-29']]['NAV'],parent[arm]['NAV'])
    fills = read(BASE/'logs_2022_2024'/f'{arm}_fills.json')
    terminal = read(BASE/'logs_2024'/f'{arm}_terminal.json')
    fill_byday = {}
    for t in fills: fill_byday.setdefault(t['day'],[]).append(t)
    # Original ETF holdings do not overlap distinct entry lots. FIFO allocation here
    # only aggregates actual quantities/costs; it creates no order or market signal.
    lots, cum_realized, cum_dividend, accounting = [], Z, Z, {}
    for r in ds:
        day = r['date']
        for f in fill_byday.get(day,[]):
            q, gross, fee = int(f['quantity']), D(f['gross']), D(f['fee'])
            if f['side']=='buy': lots.append([q,gross+fee])
            else:
                remain, cost = q, Z
                while remain:
                    lq, lc = lots[0]
                    take=min(remain,lq)
                    used=lc*D(take)/D(lq)
                    cost+=used; remain-=take; lots[0]=[lq-take,lc-used]
                    if not lots[0][0]:lots.pop(0)
                cum_realized += gross-fee-cost
        basis=sum((cost for q,cost in lots),Z)
        shares=sum(q for q,cost in lots)
        assert shares==int(r['shares'])
        unrealized=D(r['market_value'])-basis
        cum_dividend+=D(r['dividend_accrued'])
        near(D('1000000')+cum_realized+unrealized+cum_dividend,r['NAV'])
        accounting[day]=dict(open_basis=basis,unrealized=unrealized,
            cumulative_realized_trade_net=cum_realized,cumulative_dividend_recognition=cum_dividend)
    for day in BOUNDARIES:
        r=ds[dates[day]]; a=accounting[day]
        boundaries.append(dict(arm=arm,date=day,NAV_CNY=r['NAV'],cash_CNY=r['cash'],
            shares=r['shares'],inventory_mark_CNY=r['market_value'],
            dividend_receivable_CNY=r['dividend_receivable'],
            close_exposure_pct=D(r['market_value'])/D(r['NAV'])*100,
            cumulative_fee_CNY=r['cumulative_fee'],open_cost_including_buy_fee_CNY=a['open_basis'],
            unrealized_price_gain_after_buy_fee_CNY=a['unrealized'],
            cumulative_realized_trade_net_CNY=a['cumulative_realized_trade_net'],
            cumulative_dividend_recognition_CNY=a['cumulative_dividend_recognition'],
            pending_side=r['pending_side'],pending_quantity=r['pending_quantity'],execution_verified=False))
    for name,lo,hi in PHASES:
        ids=[i for i,r in enumerate(ds) if lo<=r['date']<=hi]
        before=ds[ids[0]-1]; start,end=D(before['NAV']),D(ds[ids[-1]]['NAV'])
        rr=[ds[i] for i in ids]; tx=[f for f in fills if lo<=f['day']<=hi]
        realized=accounting[hi]['cumulative_realized_trade_net']-accounting[before['date']]['cumulative_realized_trade_net']
        unreal=accounting[hi]['unrealized']-accounting[before['date']]['unrealized']
        div=sum((D(r['dividend_accrued']) for r in rr),Z)
        near(realized+unreal+div,end-start)
        phases.append(dict(arm=arm,phase=name,start=lo,end=hi,closes=len(ids),
            own_start_NAV_CNY=start,own_end_NAV_CNY=end,wealth_change_CNY=end-start,
            own_return_pct=(end/start-1)*100,local_close_DD_pct=local_dd(start,[D(r['NAV']) for r in rr]),
            mean_previous_close_exposure_pct=sum((D(ds[i-1]['market_value'])/D(ds[i-1]['NAV'])*100 for i in ids),Z)/D(len(ids)),
            mean_close_exposure_pct=sum((D(r['market_value'])/D(r['NAV'])*100 for r in rr),Z)/D(len(ids)),
            fee_CNY=sum((D(r['fee']) for r in rr),Z),
            actual_buy_fills=sum(f['side']=='buy' for f in tx),actual_sell_fills=sum(f['side']=='sell' for f in tx),
            buy_gross_CNY=sum((D(f['gross'])for f in tx if f['side']=='buy'),Z),
            sell_gross_CNY=sum((D(f['gross'])for f in tx if f['side']=='sell'),Z),
            dividend_recognized_CNY=div,dividend_paid_CNY=sum((D(r['dividend_paid'])for r in rr),Z),
            realized_trade_net_CNY=realized,change_unrealized_price_gain_CNY=unreal,
            execution_verified=False))
    near(sum((D(p['wealth_change_CNY'])for p in phases if p['arm']==arm and p['phase']!='year2024'),Z),D(terminal['NAV'])-D(parent[arm]['NAV']))
    realized_proofs[arm]=dict(all_726_daily_NAV_equal_initial_plus_cumulative_realized_plus_open_unrealized_plus_recognized_dividends=True,
        year2024_fills=[f for f in fills if f['day'].startswith('2024')],terminal_pending=terminal['pending'],
        year2024_parent_state_is_original_2023_terminal=True)

# Explicit zero-interest, no-fee cash arithmetic reference; no new simulated account.
for day in BOUNDARIES:
    boundaries.append(dict(arm='CASH_REFERENCE',date=day,NAV_CNY=1000000,cash_CNY=1000000,
        shares=0,inventory_mark_CNY=0,dividend_receivable_CNY=0,close_exposure_pct=0,
        cumulative_fee_CNY=0,open_cost_including_buy_fee_CNY=0,unrealized_price_gain_after_buy_fee_CNY=0,
        cumulative_realized_trade_net_CNY=0,cumulative_dividend_recognition_CNY=0,
        pending_side='',pending_quantity=0,execution_verified='NOT_APPLICABLE_ARITHMETIC_REFERENCE'))
for name,lo,hi in PHASES:
    item={k:0 for k in phases[0]}
    item.update(arm='CASH_REFERENCE',phase=name,start=lo,end=hi,closes=sum(lo<=d<=hi for d in calendar),
        own_start_NAV_CNY=1000000,own_end_NAV_CNY=1000000,
        execution_verified='NOT_APPLICABLE_ARITHMETIC_REFERENCE')
    phases.append(item)
write_csv('BENCHMARK_2024_BOUNDARIES.csv',boundaries)
write_csv('BENCHMARK_2024_PHASES.csv',phases)
save('BENCHMARK_2024_ACCOUNTING_PROOFS.json',realized_proofs)

index_year=rows(BASE/'inputs/HS300_2024_daily.csv')
index_reference=rows(BASE/'HS300_2024_REFERENCE.csv')
assert len(index_reference)==242
historical_index=rows(T/'benchmark_2022_2023/inputs/HS300_daily.csv')
index_previous=historical_index[-1]
print('INDEX_COLUMNS',list(index_previous))
save('SOURCE_BINDING.json',dict(recorded_UTC=datetime.now(timezone.utc).isoformat(),
    aggregation_script_SHA256=sha(__file__),source_SHA256=SOURCES,
    operation='Saved CSV/log aggregation only: no Account, policy, indicators, data download or new financial path'))
print(json.dumps(dict(boundaries=boundaries,phases=phases),default=str))

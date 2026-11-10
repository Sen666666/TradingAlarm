"""Read saved original records and perform scalar reconciliation only.

No strategy/data-engine imports, model construction, feature calculation, or account replay.
"""
import csv
import gzip
import hashlib
import json
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

D = lambda x: Decimal(str(x))
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SRC = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json')
PAIR = ROOT / 'new_price_trend_v1/funding/runs/long_OFF/pair'
data = json.loads(SRC.read_text())
days = {r['day']: r for r in data['days']}

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')

def csvsave(name, rows):
    with (OUT / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

with gzip.open(PAIR / 'B.json.gz', 'rt') as f:
    book = json.load(f)
saved_daily = {}
with gzip.open(PAIR / 'daily.jsonl.gz', 'rt') as f:
    for line in f:
        r = json.loads(line)
        if r['account'] == 'B' and r['at'][:10] in days:
            saved_daily[r['at'][:10]] = r
saved_bridge = {}
with gzip.open(PAIR / 'balances.jsonl.gz', 'rt') as f:
    for line in f:
        r = json.loads(line)
        if r['account'] == 'B' and r['at'][:10] in days:
            saved_bridge[r['at'][:10]] = r

fills, close_rows, evidence, ledger_checks = [], [], [], []
running_qty = 0
for day, r in days.items():
    bar = r['original_bar']
    acc = r['original_account']
    live = r['original_live_layers']
    factor = D(r['original_stock_facts']['factor'])
    sells = r['original_OPEN_sells']
    running_qty -= sum(x['shares'] for x in sells)
    for buy in r['original_OPEN_buys']:
        signal = days[buy['signal_at'][:10]]
        role = 'core' if buy['kind'] == 'core' else 'mobile'
        intents = [i for i in signal['original_intents'] if i['role'] == role]
        assert len(intents) == 1
        intent = intents[0]
        actual = next(x for x in data['selected_actual_layers'] if x['native']['id'] == buy['layer'])
        accounting = actual['original_layer_accounting']
        assert running_qty == accounting['quantity_before_actual_buy']
        assert buy == actual['original_buy']
        assert buy in book['trades']
        source_decision = next(x for x in book['decisions'] if x['at'] == buy['signal_at'])
        assert intent in source_decision['intents']
        q = buy['shares']
        op, p = D(buy['raw_open']), D(buy['price'])
        floor = D(buy['floor']) / factor
        before = running_qty
        running_qty += q
        sigqty = sum(x['qty'] for x in signal['original_live_layers'])
        signav = D(signal['original_account']['NAV'])
        sigmark = D(signal['original_stock_mark'])
        nominal2 = signav * D('.02')
        stockspace = max(D(0), signav * D('.1') - sigmark)
        mobile_nominal = min(nominal2, stockspace)
        assert role != 'mobile' or D(intent['budget']) == mobile_nominal
        gross, fee = D(buy['gross_cny']), D(buy['fees_cny'])
        assert gross == D(q)*p
        audit = [x for x in r['original_audit_today'] if x.get('kind') == 'lot_risk_funded' and x.get('layer_kind') == buy['kind']]
        assert len(audit) == 1
        assert audit[0]['shares'] == q
        nominal_open_max = min(intent['cap'], int((D(intent['budget']) / p).to_integral_value(rounding=ROUND_FLOOR)) // 100 * 100)
        fills.append(dict(
            layer=buy['layer'], role=role, pool_at_fill=accounting['pool_at_fill'],
            signal_at=buy['signal_at'], OPEN_at=buy['at'],
            signal_NAV=signav, signal_stock_qty=sigqty, signal_stock_mark=sigmark,
            original_intent_budget=intent['budget'], original_intent_cap=intent['cap'],
            original_intent_risk_budget=intent.get('risk_budget'),
            original_audit_risk_budget=audit[0].get('risk_budget'),
            signal_two_percent_NAV=nominal2, signal_ten_percent_stock_remaining=stockspace,
            mobile_nominal_formula_check=role != 'mobile' or D(intent['budget']) == mobile_nominal,
            existing_qty_before_actual_buy=before,
            known_raw_OPEN=op, existing_mark_at_raw_OPEN_for_stock_cap=D(before)*op,
            slipped_buy_price=p, actual_shares=q, actual_gross=gross, actual_buy_fee=fee,
            actual_cash_spent=gross+fee,
            original_frozen_cap_and_gross_at_OPEN_max_shares=nominal_open_max,
            actual_below_that_max=q < nominal_open_max,
            stock_qty_after_buy=running_qty,
            stock_mark_after_buy_at_raw_OPEN=D(running_qty)*op,
            stock_cap_gate_lhs_existing_raw_mark_plus_new_slipped_gross=D(before)*op+gross,
            stock_cap_gate_signal_NAV_limit=signav*D('.1'),
            frozen_entry_floor_adjusted=buy['floor'], OPEN_factor=factor, frozen_entry_floor_raw=floor,
            new_order_route_mark_to_floor_excluding_fees=D(q)*max(D(0),p-floor),
            CLOSE_stock_mark=r['original_stock_mark'],
            CLOSE_stock_remaining_fee_aware_basis=r['original_stock_remaining_basis'],
            CLOSE_stock_guard_risk_before=r['original_mark_to_guard_before_CLOSE'],
            CLOSE_stock_guard_risk_after=r['original_mark_to_guard_after_CLOSE'],
            actual_lifecycle_net=accounting['net'],
        ))
    assert running_qty == sum(x['qty'] for x in live)
    sd = saved_daily[day]
    fieldmap = {'NAV':'nav','available_cash':'available','order_reserved':'order_reserved','settlement_locked':'settlement_locked','payable':'payable','sale_receivable':'sale_receivable','dividend_receivable':'dividend_receivable','inventory':'inventory','pool_probe':'pool_probe','pool_confirmed':'pool_confirmed','pending_intents':'pending_intents'}
    assert all(acc[a] == sd[b] for a,b in fieldmap.items())
    assert sd['positions'].get('000620.SZ',0) == running_qty
    assert [x['saved_native_layer'] for x in live] == [x for x in sd['layers'] if x['sid']=='000620.SZ']
    nav_calc = sum((D(acc[k]) for k in ['available_cash','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),D(0))-D(acc['payable'])
    pool_cap = D(acc['pool_probe'][0])+D(acc['pool_confirmed'][0])
    pool_risk = D(acc['pool_probe'][1])+D(acc['pool_confirmed'][1])
    guard_before = sum((D(x['native_mark_to_guard_before_check']) for x in live),D(0))
    guard_after = sum((D(x['native_mark_to_guard_after_checks']) for x in live),D(0))
    # Decimal rounding can differ by <1e-20 from diagnostic summed quantities.
    assert abs(guard_before-D(r['original_mark_to_guard_before_CLOSE'])) < D('1e-20')
    assert abs(guard_after-D(r['original_mark_to_guard_after_CLOSE'])) < D('1e-20')
    close_rows.append(dict(
        day=day, CLOSE_at=r['original_CLOSE_clock'], NAV=acc['NAV'],
        available_cash=acc['available_cash'], inventory=acc['inventory'],
        order_reserved=acc['order_reserved'],settlement_locked=acc['settlement_locked'],
        payable=acc['payable'],sale_receivable=acc['sale_receivable'],dividend_receivable=acc['dividend_receivable'],
        probe_capital=acc['pool_probe'][0], confirmed_capital=acc['pool_confirmed'][0],
        probe_risk=acc['pool_probe'][1],confirmed_risk=acc['pool_confirmed'][1],
        probe_plus_confirmed_risk=pool_risk,
        reported_native_account_mark_risk=acc['native_reported_account_mark_risk'],
        NAV_balance_identity_difference=nav_calc-D(acc['NAV']),
        pool_capital_minus_inventory=pool_cap-D(acc['inventory']),
        pool_risk_sum_minus_reported=pool_risk-D(acc['native_reported_account_mark_risk']),
        full_account_stock_count=len(sd['positions']),full_account_live_layer_count=len(sd['layers']),
        pending_intents=acc['pending_intents'],pending_sell_sids='|'.join(acc['pending_sell_sids']),
        yingxin_qty=running_qty,yingxin_raw_close=bar['raw_close'],yingxin_stock_mark=r['original_stock_mark'],
        yingxin_basis=r['original_stock_remaining_basis'],
        yingxin_guard_risk_before=r['original_mark_to_guard_before_CLOSE'],
        yingxin_guard_risk_after=r['original_mark_to_guard_after_CLOSE'],
        shared_loss_saved=sd['shared_loss'],
        saved_bridge_independent_NAV_difference=saved_bridge[day]['independent_NAV_difference'],
    ))
    ledger_checks.append(dict(day=day, task3_original_fields_equal_sealed_daily=True,
                              task3_stock_layers_equal_sealed_daily=True,
                              saved_bridge=saved_bridge[day]))
    evidence.append({k:v for k,v in r.items() if k.startswith('original_')})

csvsave('PER_ACTUAL_BUY.csv', fills)
csvsave('ALL_SAVED_CLOSE_ACCOUNT_TOTALS.csv', close_rows)
save('PER_ACTUAL_BUY.json',fills)
save('ORIGINAL_ONLY_DAILY_INPUTS.json', evidence)
save('SEALED_BOOK_CROSSCHECK.json', ledger_checks)
save('EXACT_SELECTED_ORIGINAL_LAYERS.json',[
    dict(native=x['native'], original_buy=x['original_buy'],
         original_layer_accounting={k:v for k,v in x['original_layer_accounting'].items()
                                    if k in ['layer','role','pool_at_fill','quantity_before_actual_buy','cost','net','buy_fee','sell_fee','actual_sale_parts','original_exit_request_events']})
    for x in data['selected_actual_layers']])
groups=[]
for label,ids in [('Mobile_round1',[69,75,78]),('Mobile_round2',[113,122]),('CORE',[68])]:
    rows=[x for x in fills if x['layer'] in ids]
    groups.append(dict(group=label,layers=ids,shares_bought=sum(x['actual_shares'] for x in rows),
                       actual_gross=sum((x['actual_gross'] for x in rows),D(0)),
                       actual_buy_fees=sum((x['actual_buy_fee'] for x in rows),D(0)),
                       actual_cash_spent=sum((x['actual_cash_spent'] for x in rows),D(0)),
                       actual_lifecycle_net=sum((D(x['actual_lifecycle_net']) for x in rows),D(0))))
save('GROUP_TOTALS.json',groups)
paths=[SRC,PAIR/'B.json.gz',PAIR/'daily.jsonl.gz',PAIR/'balances.jsonl.gz']
source_paths=[
    '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py',
    '/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py',
    '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py',
    '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py',
    '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py',
    '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py',
]
save('SOURCE_SHA256.json',[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths+[Path(x) for x in source_paths]])
print(json.dumps(dict(groups=groups, fills=[{k:r[k] for k in ['layer','signal_at','OPEN_at','original_intent_budget','original_intent_cap','existing_qty_before_actual_buy','existing_mark_at_raw_OPEN_for_stock_cap','actual_shares','actual_cash_spent','original_frozen_cap_and_gross_at_OPEN_max_shares','new_order_route_mark_to_floor_excluding_fees','stock_mark_after_buy_at_raw_OPEN','CLOSE_stock_mark']} for r in fills],
                      all_saved_rows=len(close_rows),baseline_exact_match=True),ensure_ascii=False,default=str))

"""Read original saved ledger/snapshots only. No financial engine imports."""
from pathlib import Path
from decimal import Decimal as D
import csv
import gzip
import hashlib
import json
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BASE = ROOT / 'new_price_trend_v1/funding/runs/long_OFF/pair'
SAVED = ROOT / 'native_algorithm_read_v1/daily_hytera'
SID = '002583.SZ'
NS = 'NOT_SAVED'
SOURCES = {}

def bind(p):
    p = Path(p).resolve()
    SOURCES[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p

def read(p):
    return json.loads(bind(p).read_text())

def gz(p, lines=False):
    with gzip.open(bind(p), 'rt') as f:
        return [json.loads(line) for line in f] if lines else json.load(f)

def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def dec(x):
    return D(str(x))

def dstr(x):
    return str(x)

def csvwrite(name, rows):
    if not rows:
        return
    with (OUT/name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False, separators=(',', ':')) if isinstance(v, (dict, list)) else v for k,v in row.items()})

def main():
    t0 = time.monotonic()
    bind(__file__)
    stock = read(SAVED/'ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json')
    book = gz(BASE/'B.json.gz')
    all_daily = gz(BASE/'daily.jsonl.gz', True)
    balances = gz(BASE/'balances.jsonl.gz', True)
    daily = {r['at'][:10]:r for r in all_daily}
    days = list(daily)
    stockday = {r['day']:r for r in stock}
    decisions = {r['at'][:10]:r for r in book['decisions']}
    balance_byday = {r['at'][:10]:r for r in balances}
    for p in [SAVED/'SOURCE_REFERENCE_MAP.json', SAVED/'SOURCE_SHA256.json',
              ROOT/'new_price_trend_v1/funding/runs/long_OFF/ORIGINAL_IDENTITY.json']:
        read(p)
    for n in ['funding', 'industry', 'rank-policy']:
        bind(BASE/(n+'.jsonl.gz'))

    outputdays = [r['day'] for r in stock]
    selected = [daily[d] for d in outputdays]
    save('ORIGINAL_43_CLOSE_ACCOUNT_SNAPSHOTS.json', selected)
    save('ORIGINAL_43_BALANCE_CHECKS.json', [balance_byday[d] for d in outputdays])
    account_rows=[]
    for r in selected:
        day=r['at'][:10]
        s=stockday[day]
        qty=r['positions'].get(SID,0)
        raw=dec(s['source_signal']['raw_close'])
        p=r['pool_probe'];c=r['pool_confirmed']
        capital=dec(p[0])+dec(c[0])
        assert abs(capital-dec(r['inventory'])-dec(r['order_reserved']))<D('.000001')
        assert dec(r['nav']) == sum((dec(r[k]) for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),D(0))-dec(r['payable'])
        row={k:r[k] for k in ['at','nav','available','inventory','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','on']}
        row.update(hytera_qty=qty,hytera_raw_close=dstr(raw),hytera_stock_mark_cny=dstr(dec(qty)*raw),
            hytera_mark_NAV_fraction=dstr(dec(qty)*raw/dec(r['nav'])),
            pool_probe_capital=p[0],pool_probe_risk=p[1],pool_probe_reserve=p[2],
            pool_confirmed_capital=c[0],pool_confirmed_risk=c[1],pool_confirmed_reserve=c[2],
            risk_sum_of_saved_pool_aggregates=float(p[1])+float(c[1]),
            hytera_contemporary_layers=[l for l in r['layers'] if l['sid']==SID])
        account_rows.append(row)
    csvwrite('DAILY_ACCOUNT_AND_STOCK_OCCUPANCY.csv', account_rows)

    # All original original October signal intentions and their actual next OPEN.
    # This is a join of saved rows, not an order or resource simulation.
    orderrows=[]
    for day,s in stockday.items():
        if not '2024-10-01'<=day<='2024-10-31':
            continue
        a=daily[day]
        nxt=days[days.index(day)+1]
        ns=stockday[nxt]
        for intent in s['intents']:
            raw=dec(s['source_signal']['raw_close']);nav=dec(a['nav']);qty=a['positions'].get(SID,0)
            held=dec(qty)*raw
            nominal=min(nav*D('.02'), max(D(0),nav*D('.1')-held))
            if intent['role']=='mobile':
                assert nominal==dec(intent['budget'])
            row=dict(signal_CLOSE=decisions[day]['at'],role=intent['role'],
                original_intent=intent,signal_NAV=a['nav'],signal_stock_qty=qty,
                signal_raw_mark=dstr(raw),signal_held_stock_mark=dstr(held),
                two_percent_NAV=dstr(nav*D('.02')),ten_percent_NAV=dstr(nav*D('.1')),
                ten_percent_NAV_less_held_mark=dstr(max(D(0),nav*D('.1')-held)),
                pre_CORE_resize_nominal_budget=dstr(nominal),
                original_intent_budget=intent['budget'],original_intent_cap=intent['cap'],
                CORE_resize_applied=intent['role']=='core',
                signal_contemporary_layers=s['current_CLOSE_stock_layers'],
                next_original_OPEN=nxt+' 09:30:00+08:00',
                next_OPEN_saved_raw_open=ns['source_signal']['raw_open'],
                original_funding_outcomes=[f for f in ns['funding']if f['role']==intent['role']],
                original_buy_fills=[f for f in ns['trades']if f['side']=='buy'and f.get('signal_at','')[:10]==day and ('mobile'if f['kind']=='add'else'core')==intent['role']],
                next_OPEN_instant_pre_route_resource_snapshot=NS,
                next_OPEN_instant_reason_for_each_tested_quantity=NS,
                rejection_union_is_first_blocker=False)
            orderrows.append(row)
    save('OCTOBER_INTENT_TO_NEXT_OPEN_ORIGINAL_ROWS.json',orderrows)
    csvwrite('OCTOBER_INTENT_TO_NEXT_OPEN.csv',orderrows)

    buyrows=[]
    for trade in book['trades']:
        if trade.get('security_id')!=SID or trade['side']!='buy' or not '2024-10-01'<=trade['at'][:10]<='2024-10-31':
            continue
        day=trade['at'][:10];signal=trade['signal_at'][:10];src=stockday[signal]
        intent=next(i for i in src['intents']if i['role']==('mobile'if trade['kind']=='add'else'core'))
        prior=src['current_CLOSE_stock_layers'];now=stockday[day]['current_CLOSE_stock_layers']
        oldqty=sum(l['qty'] for l in prior);newqty=oldqty+trade['shares']
        original_reserve=next(r for r in book['audit']if r.get('kind')=='reserve'and r.get('sid')==SID and r.get('at')==trade['at'])
        original_bo=book['budget']['orders'][f"B|{trade['signal_at'].replace(' ','T')}|{SID}|{intent['role']}"]
        row=dict(layer=trade['layer'],original_trade=trade,original_CLOSE_intent=intent,
            original_reserve_audit=original_reserve,
            original_created_order_record=original_bo,
            created_order_note='Original preserved order record, status/qty are terminal filled/0; its limit/floor are the frozen entry values, NOT a terminal holding floor.',
            before_OPEN_contemporary_previous_CLOSE_layers=prior,
            actual_OPEN_entry_protection_continuous=trade['floor'],
            actual_OPEN_entry_protection_raw_saved_order=original_bo['floor'],
            total_gross_and_buy_fee=dstr(dec(trade['gross_cny'])+dec(trade['fees_cny'])),
            old_qty=oldqty,new_qty=newqty,
            old_qty_marked_at_same_raw_OPEN=dstr(dec(oldqty)*dec(trade['raw_open'])),
            new_total_qty_marked_at_same_raw_OPEN=dstr(dec(newqty)*dec(trade['raw_open'])),
            new_total_qty_marked_at_same_slipped_fill=dstr(dec(newqty)*dec(trade['price'])),
            OPEN_valuation_note='Scalar qty×saved raw OPEN only, not a regenerated account mark; prior holdings are not repriced at this buy fill in an account replay.',
            same_day_original_CLOSE_layers=now,
            same_day_original_CLOSE_stock_mark=dstr(dec(newqty)*dec(stockday[day]['source_signal']['raw_close'])),
            original_funding_record=[f for f in stockday[day]['funding']if f['result']=='reserved'],
            original_book_journal_rows=[r for r in book['journal']if r.get('sid')==SID and r.get('at')==trade['at']],
            exact_instant_routing_resource_certificate=NS)
        if intent['role']=='mobile':
            assert dec(trade['shares'])*dec(trade['price'])<=dec(intent['budget'])
            row['frozen_cap_gross_at_saved_fill']=dstr(dec(intent['cap'])*dec(trade['price']))
            row['frozen_cap_gross_exceeds_frozen_budget']=dec(intent['cap'])*dec(trade['price'])>dec(intent['budget'])
            row['next_100_shares_gross_at_saved_fill']=dstr(dec(trade['shares']+100)*dec(trade['price']))
            row['next_100_gross_exceeds_budget']=dec(trade['shares']+100)*dec(trade['price'])>dec(intent['budget'])
            assert row['next_100_gross_exceeds_budget']
        buyrows.append(row)
    assert [r['layer']for r in buyrows]==[1994,2017,2039]
    save('THREE_ACTUAL_PROXY_BUYS_ALLOCATION_AND_PROTECTION.json',buyrows)

    # Preserve original account-wide same-clock funding order, without invoking a route.
    funding=gz(BASE/'funding.jsonl.gz',True)
    keydays=['2024-10-15','2024-10-16','2024-10-17','2024-10-21','2024-10-22','2024-10-23','2024-10-24','2024-10-25','2024-10-28','2024-10-30','2024-11-01']
    contexts=[]
    for day in keydays:
        prev=days[days.index(day)-1]
        reserves=[dict(original_audit_index=k,**r)for k,r in enumerate(book['audit'])if r.get('kind')=='reserve'and r.get('at','')[:10]==day]
        hyteraidx=next((k for k,r in enumerate(reserves)if r.get('sid')==SID),None)
        before=reserves[:hyteraidx]if hyteraidx is not None else None
        trades=[r for r in book['trades']if r['at'][:10]==day]
        contexts.append(dict(day=day,previous_original_CLOSE_account=daily[prev],
            current_original_CLOSE_account=daily[day],
            all_original_funding_rows_in_saved_sequence=[r for r in funding if r['at'][:10]==day],
            original_reserve_audits_in_sequence=reserves,
            earlier_original_reserve_count_before_Hytera=len(before)if before is not None else NS,
            earlier_original_reserve_gross_and_fee_before_Hytera=dstr(sum((dec(r['gross_budget_cny'])+dec(r['fee_reserved_cny'])for r in before),D(0)))if before is not None else NS,
            all_original_proxy_trades=trades,
            original_day_buy_cash_outflow=dstr(sum((dec(t['gross_cny'])+dec(t['fees_cny'])for t in trades if t['side']=='buy'),D(0))),
            original_day_sell_net_cash_inflow=dstr(sum((dec(t['gross_cny'])-dec(t['fees_cny'])for t in trades if t['side']=='sell'),D(0))),
            current_CLOSE_balances_original_crosscheck=balance_byday[day],
            OPEN_pre_route_NAV_cash_marks_full_risk_snapshot=NS,
            caution='Original opening reserves every funded intent in order before proxy fills. Same-day CLOSE is later; do not substitute it for pre-route resources or infer per-quantity failure certificates.'))
    save('KEY_OPEN_GLOBAL_ORIGINAL_FUNDING_AND_CASH_CONTEXT.json',contexts)

    # Bound only the actually consumed source code by verbatim text and SHA.
    code={
      '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py':[(36,61),(222,259),(260,324)],
      '/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py':[(16,31),(42,66)],
      '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py':[(106,118)],
      '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py':[(1,41)],
      '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py':[(14,35)],
    }
    pieces=[]
    for path,ranges in code.items():
        p=bind(path);lines=p.read_text().splitlines()
        for lo,hi in ranges:
            pieces.append(f'PATH {p}\nSHA256 {SOURCES[str(p)]}\nLINES {lo}-{hi}\n'+'\n'.join(f'{n:5d} {lines[n-1]}'for n in range(lo,hi+1))+'\n')
    (OUT/'ORIGINAL_SOURCE_EXCERPTS.txt').write_text('\n'.join(pieces))
    save('SOURCE_SHA256.json',SOURCES)
    save('SCOPE_AND_GAPS.json',dict(stock=SID,original_43_stock_observations=len(stock),
        October_saved_intents=len(orderrows),actual_proxy_buys=len(buyrows),
        original_account_source=str(BASE),actual_trade_is_daily_bar_proxy_not_broker_receipt=True,
        original_CLOSE_pool_tuple_fields=['capital','risk','reserve'],
        directly_saved=['43 CLOSE NAV,available,inventory,receivables and live layer qty/floor/last_core_line/pool','43 CLOSE probe/confirmed resource tuples','frozen CLOSE intentions budget/cap/risk_budget/floor','actual funding result unions and reserved share quantities','actual proxy OPEN raw/fill/gross/fee shares and preserved entry order floors','original global reserve sequence and trades on 11 relevant OPEN days'],
        unavailable_without_new_replay=['exact whole-account OPEN pre-each-route marked state, per-pool/per-sector resources and pending fees','numeric failed predicates for each tested quantity and first binding constraint','CLOSE intra-planning protection update event timing','real exchange order book, minutes, queue or broker fill receipt'],
        no_terminal_holding_floor_backfill=True,no_market_account_or_model_import=True,
        accounts_run=0,backtests_run=0,indicators_computed=0,resource_or_order_replay=0,
        operations='Original JSON joins, verbatim source reads, SHA256, Decimal scalar accounting identities; no new financial state.',
        elapsed_seconds=time.monotonic()-t0))

if __name__=='__main__':
    main()

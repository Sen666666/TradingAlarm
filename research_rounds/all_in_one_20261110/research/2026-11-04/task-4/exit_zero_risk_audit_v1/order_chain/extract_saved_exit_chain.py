"""Only read saved JSON/gzip, calendar configuration and source text; no model imports."""
import csv
import gzip
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SID = '000620.SZ'
BEGIN, END = '2022-01-27', '2022-02-08'
CASE = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json')
BOOK = ROOT / 'new_price_trend_v1/funding/runs/long_OFF/pair/B.json.gz'
DAILY = ROOT / 'new_price_trend_v1/funding/runs/long_OFF/pair/daily.jsonl.gz'
RULES = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
PROTOCOL = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

case = json.loads(CASE.read_text())
with gzip.open(BOOK,'rt') as f:
    book = json.load(f)
days = {d['day']:d for d in case['days'] if BEGIN <= d['day'] <= END}
rules, protocol = json.loads(RULES.read_text()), json.loads(PROTOCOL.read_text())
calendar = rules['calendars']['A']
opens = {t[:10]:t for t in calendar if BEGIN <= t[:10] <= END}
audit = []
for r in book['audit']:
    rec = r.get('receipt', {})
    at = r.get('at', rec.get('at', ''))
    sid = r.get('sid', rec.get('security_id', ''))
    settlement = r.get('settlement',{})
    if BEGIN <= at[:10] <= END and (sid == SID or settlement.get('settlement_id') == 'sale:000620.SZ:637'):
        audit.append(r)
journal = [r for r in book['journal'] if r.get('sid') == SID and BEGIN <= r.get('at','')[:10] <= END]
trades = [r for r in book['trades'] if r['security_id'] == SID and BEGIN <= r['at'][:10] <= END]
assert len(trades) == 1 and trades[0]['shares'] == 9900 and trades[0]['at'].startswith('2022-02-08')
assert [r['event_id'] for r in audit if r['kind'] == 'exit_request'] == ['exit:000620.SZ:600']
assert next(r for r in audit if r['kind']=='fill')['order_id'] == 'exit:000620.SZ:600'
saved_daily={}
with gzip.open(DAILY,'rt') as f:
    for line in f:
        r=json.loads(line)
        if r['account']=='B' and r['at'][:10] in days:
            saved_daily[r['at'][:10]]=r
write('ORIGINAL_BOOK_EVENTS.json',dict(audit=audit,journal=journal,trades=trades))
write('FOUR_SAVED_CLOSE_ORIGINAL_FIELDS.json',[
    dict(day=day, **{k:d[k] for k in ['original_bar','original_stock_facts','original_CLOSE_specific_exit_requests','original_live_layers','original_account','original_OPEN_buys','original_OPEN_sells']})
    for day,d in days.items()])

rows=[]
current=date.fromisoformat(BEGIN)
while current <= date.fromisoformat(END):
    day=str(current);d=days.get(day)
    if d:
        sd=saved_daily[day]
        assert [x['saved_native_layer'] for x in d['original_live_layers']] == [x for x in sd['layers'] if x['sid']==SID]
        assert (SID in d['original_account']['pending_sell_sids']) == (SID in sd['pending_sells'])
        bar=d['original_bar'];live=d['original_live_layers']
        state = {
            '2022-01-27':'OPEN before first exit request; CLOSE CP targets [113,122] 9800, CORE68 excluded',
            '2022-01-28':'Existing 9800 Mobile request; no sell fill; CLOSE sid still pending',
            '2022-02-07':'OPEN existing 9800 Mobile request; CLOSE I exit adds CORE68 to same order, requested total 9900',
            '2022-02-08':'OPEN same order fills 9900; CLOSE no stock/pending exit',
        }[day]
        flat = bar['raw_high'] <= bar['raw_low']
        block = 'First exit not yet requested at OPEN' if day=='2022-01-27' else ('Saved flat bar + original reject_flat_day=true is a sufficient model sell blocker; per-attempt returned reason NOT_SAVED' if flat else 'Actual sell receipt proves model fill; no replay')
        row=dict(day=day,saved_A_OPEN=opens.get(day,'NONE'),saved_CLOSE=True,
                 raw_open=bar['raw_open'],raw_high=bar['raw_high'],raw_low=bar['raw_low'],raw_close=bar['raw_close'],
                 original_i_target=d['original_stock_facts']['i_target'],
                 live_qty_at_CLOSE=sum(x['qty'] for x in live),
                 target_layers_requested_at_or_before_CLOSE='113|122' if day in ['2022-01-27','2022-01-28'] else ('68|113|122' if day=='2022-02-07' else 'NONE; completed'),
                 requested_target_shares_from_saved_proposal=9800 if day in ['2022-01-27','2022-01-28'] else (9900 if day=='2022-02-07' else 0),
                 pending_sid_at_CLOSE=SID in d['original_account']['pending_sell_sids'],
                 recorded_internal_remaining_target='NOT_SAVED',recorded_submitted_remaining='NOT_SAVED',
                 recorded_physical_inventory_lot_snapshot='NOT_SAVED',
                 core_native_guard_risk=next((x['native_mark_to_guard_after_checks'] for x in live if x['role']=='core'),'0'),
                 mobile_native_guard_risk='0',
                 OPEN_sell_evidence=block,state_interpretation=state)
    else:
        assert day not in opens
        row=dict(day=day,saved_A_OPEN='NONE',saved_CLOSE=False,
                 raw_open='NOT_SAVED',raw_high='NOT_SAVED',raw_low='NOT_SAVED',raw_close='NOT_SAVED',
                 original_i_target='NOT_SAVED',live_qty_at_CLOSE='NO_SAVED_CLOSE',
                 target_layers_requested_at_or_before_CLOSE='NO_NEW_SAVED_EVENT',
                 requested_target_shares_from_saved_proposal='NO_NEW_SAVED_EVENT',
                 pending_sid_at_CLOSE='NO_SAVED_CLOSE',recorded_internal_remaining_target='NOT_SAVED',
                 recorded_submitted_remaining='NOT_SAVED',recorded_physical_inventory_lot_snapshot='NOT_SAVED',
                 core_native_guard_risk='NO_SAVED_CLOSE',mobile_native_guard_risk='NO_SAVED_CLOSE',
                 OPEN_sell_evidence='No OPEN in original saved calendar',state_interpretation='No synthetic daily snapshot filled')
    rows.append(row);current += timedelta(days=1)
write('CALENDAR_DAY_CHAIN.json',rows)
with (OUT/'CALENDAR_DAY_CHAIN.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

buys=[r for r in book['trades'] if r['security_id']==SID and r['side']=='buy' and r['at'][:10] <= END]
last_buy=max(r['at'] for r in buys)
latest_calendar_open=last_buy[:10]+'T09:30:00+08:00'
t1_next=calendar[calendar.index(latest_calendar_open)+1]
write('T1_AND_MISSING_ORDER_FIELDS.json',dict(
    original_protocol_sellable_lag_A=protocol['sellable_lag_sessions']['A'],
    original_protocol_settlement_lag_A=protocol['settlement_lag_sessions']['A'],
    latest_actual_buy=last_buy,latest_actual_buy_calendar_derived_T1_sellable=t1_next,
    later_actual_buys_in_window=[r for r in buys if r['at'][:10]>=BEGIN],
    physical_inventory_lot_snapshots='NOT_SAVED; not fabricated from logical layer opened dates',
    conclusion='All actual purchases predate Jan27; calendar/protocol imply T+1 age already satisfied by Jan26 for latest purchase. Flat-day denial precedes inventory sellability check. No claim of independently observed lot.sellable_at snapshot.',
    exact_internal_exit_order_snapshots='NOT_SAVED',
    exact_per_attempt_no_fill_log='NOT_SAVED',
    no_claim_of_real_exchange_queue_or_executable_counterfactual=True,
    derived_target_is_request_evidence_not_saved_remaining_target=True,
))

sources=[
    (Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py'),[(74,89),(104,115)]),
    (Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py'),[(130,136),(222,249),(302,307)]),
    (Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py'),[(17,21),(45,67)]),
    (Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py'),[(267,279),(570,595),(666,686),(746,809)]),
]
out=[]
for p,ranges in sources:
    lines=p.read_text().splitlines()
    out.extend([str(p),'SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest()])
    for first,last in ranges:
        out.extend(f'{n}: {lines[n-1]}' for n in range(first,last+1))
    out.append('')
(OUT/'SOURCE_EXCERPTS.txt').write_text('\n'.join(out))
write('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [CASE,BOOK,DAILY,RULES,PROTOCOL]+[x[0] for x in sources]])
print(json.dumps(dict(saved_A_OPEN_dates=list(opens),audit_events=len(audit),journal_events=len(journal),actual_sell_receipts=len(trades),order_id='exit:000620.SZ:600',latest_actual_buy=last_buy,calendar_derived_T1=t1_next),ensure_ascii=False))

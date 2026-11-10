"""Inventory concentration at actual OPEN and complete E post-exit diagnostics.
Uses frozen signal files solely for reporting; never changes account execution.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib,sys
sys.dont_write_bytecode=True
import pandas as pd
O=Path(__file__).resolve().parent;Z=D(0)
SUFFIX=sys.argv[1] if len(sys.argv)>1 else 'v1'
REPORT=O if SUFFIX=='v1' else O/f'report_{SUFFIX}'
if REPORT!=O:REPORT.mkdir(exist_ok=True)
def read(p):return json.loads(Path(p).read_text())
def dec(x):return D(str(x))
def save(name,rows):
 (REPORT/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(rows,list) and rows:pd.DataFrame(rows).to_csv(O/(name+'.csv'),index=False)
freeze=read(O/'EXECUTION_FREEZE.json')['data_hashes']
mp='/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
assert hashlib.sha256(Path(mp).read_bytes()).hexdigest()==freeze[mp]
manifest={m['symbol']:m for m in read(mp)};cache={}
def frame(s):
 if s not in cache:
  p=next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'))
  assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==freeze[p]
  cache[s]=pd.read_parquet(p,columns=['raw_open','raw_close','adjustment_factor']).loc['2024-09-02':'2024-10-31']
 return cache[s]
ro=pd.read_csv(O.parent/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv');sector=ro.set_index('symbol').sector51.to_dict()
runs={p.name.split('_')[1]:p for p in O.glob(f'run_*_{SUFFIX}') if (p/'RUN_STATUS.json').exists()};openrows=[]
for arm,run in runs.items():
 p=run/'full_prefix';holds=read(p/'HOLDINGS.json');ledger=read(p/'DAY_LEDGER.json');equity=read(p/'EQUITY_EVENTS.json');byday=defaultdict(list)
 for h in holds:byday[h['day']].append(h)
 for l in ledger:
  date=l['day'];sec=defaultdict(lambda:Z)
  # No post-OPEN inventory trades. Subtract only pay-CLOSE cash to reconstruct
  # post-fill OPEN cash, and put that amount back into receivable.
  paid=sum((dec(e['cash_delta']) for e in equity if e['day']==date and e['event']=='PAY_CLOSE_NET80'),Z)
  cash=dec(l['cash'])-paid;receivable=dec(l['receivable'])+paid
  for h in byday[date]:
   f=frame(h['sid']);op=dec(f.at[pd.Timestamp(date),'raw_open']);sec[sector[h['sid']]]+=h['qty']*op
  nav=cash+receivable+sum(sec.values(),Z)
  for s,v in sec.items():openrows.append(dict(arm=arm,day=date,sector51=s,post_fill_OPEN_value=str(v),post_fill_OPEN_NAV=str(nav),post_fill_OPEN_weight_pct=str(100*v/nav)))
save('ALL_ARMS_POST_FILL_OPEN_SECTORS',openrows)
maxima=[]
for arm in runs:
 rr=[r for r in openrows if r['arm']==arm]
 if rr:maxima.append(max(rr,key=lambda r:dec(r['post_fill_OPEN_weight_pct'])))
save('MAX_POST_FILL_OPEN_CONCENTRATION',maxima)
# Every E incremental condition: include never executed and OPEN-overridden cases.
e=read(runs['E']/'full_prefix/ADDITIONAL_EXIT.json');orders=read(runs['E']/'full_prefix/ORDERS.json');rounds=read(runs['E']/'full_prefix/ATTEMPTS.json');rmap={r['id']:r for r in rounds};arounds=read(runs['A']/'full_prefix/ATTEMPTS.json');amap={(r['sid'],r['signal_day'],r['birth_type']):r for r in arounds};cal=pd.DatetimeIndex([r['day'] for r in read(runs['A']/'full_prefix/DAY_LEDGER.json')]);future_cal=pd.bdate_range('2024-10-28','2024-10-31');cal=cal.union(future_cal)
paths=[];summary=[]
for event in e:
 if not event['incremental_exit']:continue
 rid=event['round_id'];r=rmap[rid];s=r['sid'];matched=amap.get((s,r['signal_day'],r['birth_type']));sales=[t for t in orders if t['round_id']==rid and t['day']>event['day'] and t['side'].startswith('SELL')]
 row=dict(sid=s,round_id=rid,condition_day=event['day'],signal_day=r['signal_day'],birth_type=r['birth_type'],E_round_marked_net=r['marked_net_pnl'],A_matched_round_id=matched['id'] if matched else None,A_matched_round_marked_net=matched['marked_net_pnl'] if matched else None,comparison_note='Matched ticket identity, not a counterfactual or same capital trajectory',price_path_note='Adjusted signal-coordinate prices only; not dividend-adjusted realizable net P&L')
 if not sales:row.update(status='NO_CERTIFIED_NEXT_OPEN_EXECUTION');summary.append(row);continue
 sale=sales[0];date=sale['day'];f=frame(s);fac=dec(f.at[pd.Timestamp(date),'adjustment_factor']);sold_coord=dec(sale['price'])/D('.9995')*fac;prices=[];missing=[]
 for d in cal[cal>=pd.Timestamp(date)]:
  if d not in f.index or pd.isna(f.at[d,'raw_close']):missing.append(str(d.date()));continue
  coordinate=dec(f.at[d,'raw_close'])*dec(f.at[d,'adjustment_factor']);ratio=coordinate/sold_coord-1;prices.append((str(d.date()),ratio))
  paths.append(dict(sid=s,round_id=rid,condition_day=event['day'],actual_sell_day=date,day=str(d.date()),signal_coordinate_close=str(coordinate),sell_OPEN_signal_coordinate=str(sold_coord),change_from_sell_OPEN_pct=str(ratio*100)))
 row.update(status='ACTUAL_EXIT',actual_sell_day=date,actual_exit_reason=sale['reason'],executed_from_E_reason=sale['reason']=='UNCONFIRMED_STOCK_M3_FALSE',original_OPEN_protection_overrode=sale['reason']=='I_OPEN_PROTECTION',sold_qty=sale['qty'],sell_net_cash=sale['cash_delta'],sell_fee=sale['fee'],max_later_close_change_pct=str(max(v for _,v in prices)*100) if prices else None,last_observed_day=prices[-1][0] if prices else None,last_observed_close_change_pct=str(prices[-1][1]*100) if prices else None,missing_dates=missing,closed_round_total_fees=r['fees']);summary.append(row)
save('E_ALL_INCREMENTAL_EXIT_PATH_SUMMARY',summary);save('E_ALL_POST_EXIT_DAILY_PRICE_PATHS',paths)
print(json.dumps(dict(max_open=maxima,E_incremental_conditions=len(summary),E_executed=sum(r['status']=='ACTUAL_EXIT' for r in summary),E_any_later_price_above_sell_OPEN=sum(r.get('max_later_close_change_pct') is not None and dec(r['max_later_close_change_pct'])>0 for r in summary)),ensure_ascii=False))

"""Static original quantity/raw-reference/cash components only; no annual backtest."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,math
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=Path(__file__).resolve().parent;SRC={};SID='000547.SZ';IDS={548,555,565}
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 SRC[str(p)]=h.hexdigest();return p
def rj(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return x.isoformat()
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return{k:clean(v)for k,v in x.items()}
 if isinstance(x,list):return[clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
full=rj(OUT/'FULL_DAILY_ORIGINAL_2025_11_20_2026_01_16.json');boundary=next(r for r in full if r['day']=='2025-12-31');bl=[r for r in boundary['original_live_layers_at_CLOSE']if r['id']in IDS];assert {r['id']for r in bl}==IDS
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared');m=rj(P/'manifest.json');rec=next(r for r in m['series']if r['series_id']==SID)
rp=bind(rec['raw']['path']);assert SRC[str(rp)]==rec['raw']['sha256'];raw=pd.read_parquet(rp);row=raw.loc[pd.to_datetime(raw.trade_date).eq(pd.Timestamp('2025-12-31'))].iloc[0]
assert str(row.close)==str(boundary['facts']['raw_close'])and bool(row.observed_bar)and bool(row.price_eligible)and not bool(row.source_invalid)and not bool(row.synthetic_event_bar)
ap=bind(rec['adjustment']['actions']['path']);assert SRC[str(ap)]==rec['adjustment']['actions']['sha256'];action=rj(ap)
ca=[e for e in action['events']if'2026-01-01'<=e.get('effective_date','')<='2026-01-16']
pair=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair';book=json.load(gzip.open(bind(pair/'B.json.gz'),'rt'))
trades=[r for r in book['trades']if r['security_id']==SID and'2026-01-01'<=r['at'][:10]<='2026-01-16'];audit=[r for r in book['audit']if'2026-01-01'<=r.get('at','')[:10]<='2026-01-16'and SID in str(r)]
action_kinds={'split','dividend_accrual','dividend_payment','dividend_pay','accrue_dividend','pay_dividend','corporate_action'};action_audit=[r for r in audit if r.get('kind')in action_kinds]
jan=[]
for r in full:
 if'2026-01-01'<=r['day']<='2026-01-16':
  ls=[x for x in r['original_live_layers_at_CLOSE']if x['id']in IDS]
  jan.append(dict(day=r['day'],original_stock_qty=r['original_stock_qty_at_CLOSE'],original_selected_layers=[{k:x[k]for k in ['id','qty','cash','dividend','floor']}for x in ls]))
q=sum(r['qty']for r in bl);mark=D(str(row.close));cash=sum((D(r['cash'])for r in bl),D(0));div=sum((D(r['dividend'])for r in bl),D(0));net_sale=sum((D(t['gross_cny'])-D(t['fees_cny'])for t in trades if t['side']=='sell'),D(0))
save('YEAR_BOUNDARY_SAVED_COMPONENTS_2025_12_31_TO_2026_01_16.json',dict(
 execution_boundary='Original daily-bar-proxy No60 research ledger and frozen daily raw data, not broker receipts, quote-minute executions, or an annual account run.',
 boundary_day='2025-12-31',original_stock_qty_at_CLOSE=boundary['original_stock_qty_at_CLOSE'],original_three_layer_snapshots=bl,three_layer_qty_sum=q,
 raw_price_source=dict(manifest_record=rec,exact_saved_raw_bar=row.to_dict(),raw_close_agrees_with_saved_facts=True,existing_daily_bar_is_observed_and_price_eligible=True),
 mark_scope=dict(independent_per_stock_Mark_object_saved_in_daily_json=False,raw_CLOSE_reference=str(mark),effective_source_reasoning='Original native latest_mark at15:10 uses the same-date eligible observed daily CLOSE, declared available15:05. No native Market/Mark function called. This is a source-bound scalar reconstruction, not a stored standalone per-stock inventory field.',per_layer_quantity_times_raw_reference=[dict(id=r['id'],qty=r['qty'],raw_mark_reference=mark,scalar_inventory_value=D(r['qty'])*mark)for r in bl],stock_scalar_inventory_value=q*mark),
 saved_three_layer_cumulative_cash_at_boundary=cash,saved_three_layer_recognized_dividend_at_boundary=div,
 January_original_daily_quantities_and_layer_cash_dividends=jan,January_original_trades=trades,January_original_stock_audit_entries=audit,January_original_action_callbacks_matching_named_kinds=action_audit,
 frozen_corporate_action_source=dict(path=str(ap),sha256=SRC[str(ap)],status=action.get('status'),exact_pay_dates_certified=action.get('exact_pay_dates_certified'),Jan1_to_16_effective_events=ca,limitation='No action recorded for this interval in the original declared research proxy; not a new certification of all real-world corporate actions.'),
 static_identity_terms=dict(start_inventory_reference=q*mark,actual_proxy_net_sell_cash=net_sale,intermediate_buy_fills=sum(t['side']=='buy'for t in trades),intermediate_corporate_action_count=len(ca),boundary_recognized_dividend=div,original_closed_lifecycle_net_for_these_three_layers='51001.6073036677000',scope='Terms supplied for root static segment bridge. Lifecycle total includes2025December and is not2026calendar-year gain; no annual account/valuation/backtest was run.'),
 assertions_from_saved_records=dict(boundary_qty_is_3700=q==3700,Jan_pre_exit_saved_CLOSE_quantities_all3700=all(r['original_stock_qty']==3700 for r in jan if r['day']<'2026-01-16'),Jan16_CLOSE_qty_zero=next(r for r in jan if r['day']=='2026-01-16')['original_stock_qty']==0,only_Jan16_sell_trade=len(trades)==1 and trades[0]['side']=='sell'and trades[0]['at'][:10]=='2026-01-16',frozen_Jan_actions_absent=not ca,stock_action_callbacks_absent=not action_audit),
 new_models_indicators_accounts_or_annual_backtests=0))
for p in [Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/code/multi_runner.py'),Path(__file__)]:bind(p)
save('YEAR_BOUNDARY_SOURCE_SHA256.json',SRC)
print(json.dumps(clean(dict(qty=q,raw_mark_reference=mark,stock_scalar_inventory=q*mark,boundary_cash=cash,boundary_dividend=div,Jan_trades=len(trades),Jan_action_events=len(ca),net_sale_cash=net_sale,new_accounts=0)),ensure_ascii=False))

from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');P=W/'pvr-slot1-native-readiness-20261101';SRC={};Z=D(0)
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 if p.suffix=='.gz':
  with gzip.open(p,'rt')as f:return json.load(f)
 return json.loads(p.read_text())
rows=read(O/'PLANNED_ALL576.json');daily={x['day']:x for x in read(O/'DAILY_CLOSE_RESOURCE_ALL116.json')};r=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
with gzip.open(P/'runs/2025_26/pair/daily.jsonl.gz','rt')as f:dd={x['at'][:10]:x for x in map(json.loads,f)}
SRC[str(P/'runs/2025_26/pair/daily.jsonl.gz')]=hashlib.sha256((P/'runs/2025_26/pair/daily.jsonl.gz').read_bytes()).hexdigest();b=read(P/'runs/2025_26/pair/B.json.gz');im={(x['at'][:10],i['sid'],i['role']):i for x in b['decisions']for i in x['intents']};frames={}
def ver(v,d):
 a=[x for x in v if x['from']<=d and (x['to']is None or d<x['to'])];assert len(a)==1;return a[0]
output=[]
for row in rows:
 if row['category']!='opening_rejected_raw_merged_constraints':continue
 sid=row['sid'];d=row['signal_day'];i=im[d,sid,'mobile'];s=daily[d];snap=dd[d];nav=D(s['NAV']);assert D(snap['order_reserved'])==0,'nonzero pending requires different screen'
 if sid not in frames:
  p=Path(sm[sid]['refs']['facts']);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();assert SRC[str(p)]==sm[sid]['output_sha256'][str(p)];frames[sid]=pd.read_parquet(p,columns=['raw_close','factor'])
 raw=D(str(frames[sid].loc[d,'raw_close']));factor=D(str(frames[sid].loc[d,'factor']));price=raw*D('1.0005');floor=D(i['floor'])/factor;qty=D(ver(r['quantity_versions'][sid],d)['rule']['buy_minimum']);gross=qty*price;venue=ver(r['venue_versions'][sid],d)['venue'];schedule=ver(r['fee_versions'][venue],d)['schedule'];fee=Z
 for c in schedule['components']:
  if c.get('side','buy')=='sell':continue
  base=qty if c.get('amount_basis')=='par_value'else gross
  fee+=max(base*D(c['rate']),D(c.get('minimum_local','0')))
 bn=nav-fee;risk=qty*max(Z,price-floor);fails=[]
 if raw<=floor:fails.append('open_at_or_below_protection_at_close_proxy')
 if qty>D(i['cap']) or gross>D(i['budget']):fails.append('frozen_contract_minimum')
 if gross+fee>D(snap['available'])-nav*D('.1'):fails.append('cash_original_reserve')
 if D(s['confirmed_capital'])+gross>bn*D('.6'):fails.append('confirmed60')
 frac={'confirmed':D('.1'),'expanded':D('.2')}[s['sector_stage']]
 if D(s['sector_capital'])+gross>frac*bn:fails.append('sector_stage_capital')
 if D(s['sector_nominal_risk'])+risk>bn*D('.01'):fails.append('sector_risk1')
 if D(snap['positions'].get(sid,0))*raw+gross>nav*D('.1'):fails.append('stock10')
 other=[x for x in fails if x!='confirmed60'];output.append(dict(sid=sid,signal_day=d,priority=row['priority'],minimum_quantity=qty,proxy_price=price,actual_intent_floor_raw=floor,minimum_gross=gross,buy_fee=fee,new_nominal_risk=risk,NAV=nav,numeric_confirmed_route_failures=fails,other_numeric_failures_after_omit_confirmed60=other,passes_other_numeric_checks_at_close=not other,original_merged_opening_reasons=row['raw_reasons'],actual_open_route_feasibility='UNKNOWN_not_restored_not_projected'))
assert len(output)==537
survive=[x for x in output if x['passes_other_numeric_checks_at_close']];exclusive=[x for x in survive if 'confirmed60'in x['numeric_confirmed_route_failures']]
sumry={'unit':'original rejected planned canonical stock/signal-day, repeated shares not independent orders','screen_clock':'signal CLOSE prices/slip/actual holdings; no actual OPEN or serial route projection','all_rejected':len(output),'original_close_numeric_fail_combinations':dict(Counter(','.join(x['numeric_confirmed_route_failures'])or'none'for x in output)),'after_omit_confirmed60_numeric_fail_combinations':dict(Counter(','.join(x['other_numeric_failures_after_omit_confirmed60'])or'none'for x in output)),'passes_other_close_numeric_checks':len(survive),'passes_other_close_numeric_unique_stocks':len({x['sid']for x in survive}),'fails_only_confirmed60_in_this_close_screen':len(exclusive),'fails_only_confirmed60_unique_stocks':len({x['sid']for x in exclusive}),'passes_others_by_month':dict(Counter(x['signal_day'][:7]for x in survive)),'optimistic_screen_not_actual_unblocked_orders':True,'does_not_remove_migration_pending_dependency':True,'no_new_cap90':True,'financial_events':0,'new_price_labels':0}
(O/'MINIMUM_SCREEN_ALL537.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str));(O/'MINIMUM_SCREEN_SUMMARY.json').write_text(json.dumps(sumry,ensure_ascii=False,indent=2,default=str));(O/'MINIMUM_SCREEN_SOURCE_SHA256.json').write_text(json.dumps(SRC,ensure_ascii=False,indent=2));print(json.dumps(sumry,ensure_ascii=False,indent=2))

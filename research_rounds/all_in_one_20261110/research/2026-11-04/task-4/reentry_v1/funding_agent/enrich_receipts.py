"""Saved-evidence enrichment only: no Runner/account, restore, or fills."""
from pathlib import Path
from decimal import Decimal as D
import csv,gzip,hashlib,json,sys
import pandas as pd
OUT=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
sys.path.insert(0,str(BASE));import native_adapter as A
J=A.J;P=A.P
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def effective(versions,day):return next(x for x in reversed(versions)if x['from']<=day and(x.get('to')is None or day<x['to']))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
targets=read(OUT/'TARGET_RECEIPTS_SOURCE.json');opens=read(OUT/'ALL15_OPEN_FUNDING_RESPONSIBILITY.json')
om={(x['sid'],x['signal_day']):x for x in opens}
root=BASE/'runs/2025_26/pair'
with gzip.open(root/'B.json.gz','rt')as f:book=json.load(f)
with gzip.open(root/'daily.jsonl.gz','rt')as f:daily={x['at'][:10]:x for x in map(json.loads,f)}
rules_path=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=read(rules_path)
sm=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');sm={x['symbol']:x for x in sm}
market=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared');manifest={x['series_id']:x for x in read(market/'manifest.json')['series']}
sources={str(rules_path):sha(rules_path),str(market/'manifest.json'):sha(market/'manifest.json'),str(root/'B.json.gz'):sha(root/'B.json.gz'),str(root/'daily.jsonl.gz'):sha(root/'daily.jsonl.gz')}
facts={};raw={};cp1={}
for sid in ['300666.SZ','301611.SZ','603061.SH']:
 fp=Path(sm[sid]['refs']['facts']);rp=Path(manifest[sid]['raw']['path']);cpp=Path(sm[sid]['refs']['CP1'])
 assert sha(rp)==manifest[sid]['raw']['sha256']
 sources.update({str(fp):sha(fp),str(rp):sha(rp),str(cpp):sha(cpp)})
 facts[sid]=pd.read_parquet(fp);cp1[sid]=pd.read_parquet(cpp);raw[sid]=pd.read_parquet(rp);raw[sid].index=pd.to_datetime(raw[sid].trade_date)
rows=[]
for target in targets:
 sid=target['sid'];day=target['signal_day'];opening=target['next_saved_OPEN'];x=om.get((sid,day));close=daily[day]
 qr=effective(rules['quantity_versions'][sid],day);rule=J.LR.L.QuantityRule(**qr['rule']);minq=rule.buy_minimum
 venue=effective(rules['venue_versions'][sid],day)['venue'];fs=effective(rules['fee_versions'][venue],day)['schedule'];fee=J.LR.L.FeeSchedule(fs['schedule_id'],tuple(J.LR.L.FeeComponent(**v)for v in fs['components']))
 par=D(rules['security_metadata'][sid]['par_value']);fr=facts[sid].loc[day];factor=D(str(fr.factor));signal_price=D(str(fr.raw_close));ref=signal_price*(1+J.LR.SLIP)
 continuous_floor=D(target['frozen_intent']['floor']) if target['frozen_intent']else max(D(str(fr.i_floor)),D(str(cp1[sid].loc[day,'candidate'])))
 floor=continuous_floor/factor
 nav=D(close['nav']);reference_risk=J.LR.protection_risk(minq,ref,floor,fee,par);risk_budget=nav*D('.0025')
 reference=dict(signal_raw_close=signal_price,signal_factor=factor,reference_price_including_buy_slippage=ref,known_signal_floor_raw=floor,
  floor_provenance='original frozen mobile intent' if target['frozen_intent']else 'pre-intent reconstruction max(I floor, CP1 candidate), not an original frozen intent',
  signal_I_floor_continuous=D(str(fr.i_floor)),signal_CP1_candidate_continuous=D(str(cp1[sid].loc[day,'candidate'])),mobile_floor_continuous=continuous_floor,
  min_quantity=minq,min_gross=minq*ref,min_buy_fee=J.LR.fees(minq,ref,fee,'buy',par),min_nominal_stop_risk=minq*(ref-floor),
  min_protection_risk_with_buy_sell_fees=reference_risk,quarter_percent_decision_nav_risk=risk_budget,min_fits_quarter_percent_risk=reference_risk<=risk_budget)
 row=dict(sid=sid,name=target['name'],signal_day=day,receipt=target['receipt'],category=target['category'],
  original_frozen_intent=target['frozen_intent'],reference=reference,dated_quantity_rule=qr,dated_fee_schedule=fs,
  actual_close_state=dict(at=close['at'],nav=close['nav'],available=close['available'],original_ten_percent_nav_reserve=nav*D('.1'),
   close_only_available_minus_original_reserve=D(close['available'])-nav*D('.1'),inventory=close['inventory'],order_reserved=close['order_reserved'],
   pool_probe=close['pool_probe'],pool_confirmed=close['pool_confirmed'],all_positions=close['positions'],all_live_layers=close['layers'],
   pending_sells=close['pending_sells'],clock_scope='signal CLOSE only; not candidate OPEN state'),
  next_open=opening,close_no_plan=target['normalized_no_plan'])
 if x:
  op=D(x['open_execution_price']);of=D(x['open_floor']);risk=J.LR.protection_risk(minq,op,of,fee,par)
  assert op==D(str(raw[sid].loc[opening,'open']))*(1+J.LR.SLIP)
  reference.update(open_raw=x['open_raw'],open_execution_price=op,open_floor=of,open_min_buy_fee=J.LR.fees(minq,op,fee,'buy',par),
   open_min_stop_risk=minq*(op-of),open_min_protection_risk_with_buy_sell_fees=risk,open_min_fits_quarter_percent_decision_nav_risk=risk<=risk_budget)
  competitors=[]
  dec=next(z for z in book['decisions']if z['at'][:10]==day)
  for c in x['prior_same_open_funding']:
   if c['result']!='reserved':continue
   z=next(z for z in book['audit']if z['kind']=='reserve'and z['at'][:10]==opening and z['sid']==c['sid'])
   intent=next(z for z in dec['intents']if z['sid']==c['sid'] and z['role']==c['role'])
   competitors.append(dict(**c,name=rules['security_metadata'].get(c['sid'],{}).get('name'),
    gross_reserved=z['gross_budget_cny'],fee_reserved=z['fee_reserved_cny'],native_order_id=z['order_id'],original_frozen_intent=intent))
  x['prior_actual_reserved_competitors']=competitors
  x['prior_actual_reserved_gross']=sum((D(c['gross_reserved'])for c in competitors),D(0));x['prior_actual_reserved_fees']=sum((D(c['fee_reserved'])for c in competitors),D(0))
  x['all_available_routes_fail_cash_at_legal_minimum']=all('cash_or_original_reserve'in p['minimum_failures_code_order']for p in x['pools'])
  row['exact_open_responsibility']=x
 else:
  row['first_actual_branch']='CLOSE sizing: positive 2% NAV target below legal initial minimum; no intent/no OPEN route'
  row['exact_open_responsibility']=None
 rows.append(row)
save('ALL16_RECEIPTS_WITH_REAL_RESOURCES.json',rows);save('SUPPLEMENT_SOURCE_SHA256.json',sources)
summary=dict(total_receipts=len(rows),original_open_rejects=len(opens),close_no_plan=1,
 cash_fails_on_every_available_route_at_original_min=sum(x['exact_open_responsibility']['all_available_routes_fail_cash_at_legal_minimum']for x in rows if x['exact_open_responsibility']),
 contract_request_reached=0,smaller_upper_bound_in_same_state_creates_new_route=False,
 min_reference_fits_quarter_percent_risk=sum(x['reference']['min_fits_quarter_percent_risk']for x in rows),
 min_open_fits_quarter_percent_risk=sum(x['reference'].get('open_min_fits_quarter_percent_decision_nav_risk',False)for x in rows),
 these_risk_fit_counts_are_sizing_only_not_funded_orders=True,
 all_exact_open_states_verified_against_five_original_full_prefixes=all(x['passed']for x in read(OUT/'RESTORE_IDENTITY.json')),
 competing_orders_not_assumed_cancelable=True,no_healthy_winner_sales_assumed=True)
save('SUMMARY.json',summary)
fields=['name','signal_day','next_open','route_pools','minimum_quantity','minimum_cash','spendable','cash_gap','prior_reserved','minimum_open_risk','quarter_percent_risk','reference_risk_fits','open_risk_fits','pool_failures']
with(OUT/'ALL16_FUNDING_CHAIN.csv').open('w')as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in rows:
  x=r['exact_open_responsibility'];ref=r['reference'];ps=x['pools']if x else[];p=ps[0]if ps else{}
  w.writerow(dict(name=r['name'],signal_day=r['signal_day'],next_open=r['next_open'],route_pools='|'.join(z['pool']for z in ps),minimum_quantity=ref['min_quantity'],
   minimum_cash=p.get('minimum_capital',0)+p.get('minimum_fee',0)if p else'',spendable=p.get('spendable_admission',''),cash_gap=p.get('minimum_cash_shortfall',''),
   prior_reserved=x['prior_actual_reserved_gross']+x['prior_actual_reserved_fees']if x else'',minimum_open_risk=ref.get('open_min_protection_risk_with_buy_sell_fees',''),
   quarter_percent_risk=ref['quarter_percent_decision_nav_risk'],reference_risk_fits=ref['min_fits_quarter_percent_risk'],open_risk_fits=ref.get('open_min_fits_quarter_percent_decision_nav_risk',''),
   pool_failures=' | '.join(z['pool']+':'+','.join(z['minimum_failures_code_order'])for z in ps)if x else'no_plan_target_below_minimum'))
print(json.dumps(summary,ensure_ascii=False,indent=2))

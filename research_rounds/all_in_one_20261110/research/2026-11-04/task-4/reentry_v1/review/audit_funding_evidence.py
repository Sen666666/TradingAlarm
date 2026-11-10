from pathlib import Path
from decimal import Decimal,localcontext
from collections import Counter
import json,hashlib,gzip,ast,textwrap
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/reentry_v1/funding_agent');R=O.parent/'review';D=Decimal
read=lambda p:json.loads(Path(p).read_text())
all16=read(O/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');states=read(O/'PRE_CANDIDATE_EXACT_STATE.json');s0={k[:10]:v['state'] for k,v in read(O/'PREOPEN_EXACT_STATE.json').items()};bounds=read(O/'EXISTING_OCCUPANCY_VS_PREFIX_RESERVATIONS.json');ident=read(O/'RESTORE_IDENTITY.json')
assert len(all16)==16 and len(states)==15 and len(s0)==13 and len(bounds)==15
assert len({r['receipt'] for r in all16})==16
assert Counter(r['sid'] for r in all16)=={'300666.SZ':7,'301611.SZ':4,'603061.SH':5}
engine=read(O/'ENGINE_IDENTITY_PY313.json');assert engine['expected']==engine['actual'] and not engine['differences']
assert engine['actual']['python_version'].startswith('3.13.')
# The diagnostic route differs from native No60 route by one observation hook only.
orig=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py').read_text()
old="    if pc+cap>(.10 if pool=='probe' else .60)*nav+1e-9:fails.append('pool_capital')"
new="    if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')"
expected=orig.replace(old,new)
actual=(O/'private_route_readonly_observer.py').read_text().replace('\n   observe_pool(a,i,x,at,pool,q,allowed)','')
assert actual==expected
# Read exact route resource fields independently, without importing Runner or a model.
def resources(s,pool=None,sector=None):
 lots=[v for v in s['lots'] if (pool is None or v['pool']==pool) and (sector is None or v['sector']==sector)]
 orders=[v for v in s['orders'].values() if v['qty']>0 and v['status'] in ['open','cancel_pending'] and (pool is None or v['pool']==pool) and (sector is None or v['sector']==sector)]
 return (sum(v['qty']*s['prices'][v['stock']] for v in lots)+sum(v['qty']*v['limit'] for v in orders),sum(v['qty']*max(0,s['prices'][v['stock']]-v['floor']) for v in lots)+sum(v['qty']*max(0,v['limit']-v['floor']) for v in orders),sum(v['qty']*(v['limit']+v['fee_per_share']) for v in orders),sum(v['qty']*v['fee_per_share'] for v in orders))
def fee(q,p,components,side):
 value=D(q)*p;return sum((max(value*D(c['rate']),D(c.get('minimum_local','0'))) for c in components if c.get('side',side)==side),D(0))
confirmed=Counter();riskref=0;riskopen=0;per=[]
with localcontext() as ctx:
 ctx.prec=70
 for row in all16:
  ref=row['reference'];q=ref['min_quantity'];cs=row['dated_fee_schedule']['components'];p=D(ref['reference_price_including_buy_slippage']);floor=D(ref['known_signal_floor_raw'])
  assert q==100
  assert p==D(ref['signal_raw_close'])*D('1.0005')
  assert abs(fee(q,p,cs,'buy')-D(ref['min_buy_fee']))<D('1e-20')
  risk=max(D(0),q*(p-floor*D('.9995'))+fee(q,p,cs,'buy')+fee(q,floor*D('.9995'),cs,'sell'))
  assert abs(risk-D(ref['min_protection_risk_with_buy_sell_fees']))<D('1e-19')
  riskref+=risk<=D(ref['quarter_percent_decision_nav_risk'])
  x=row['exact_open_responsibility']
  if x is None:
   assert row['sid']=='603061.SH' and row['signal_day']=='2026-06-29'
   assert row['original_frozen_intent'] is None
   assert row['close_no_plan']['normalized']=='positive_target_below_legal_initial_minimum'
   continue
  p=D(ref['open_execution_price']);floor=D(ref['open_floor'])
  assert p==D(ref['open_raw'])*D('1.0005')
  risk=max(D(0),q*(p-floor*D('.9995'))+fee(q,p,cs,'buy')+fee(q,floor*D('.9995'),cs,'sell'))
  assert abs(risk-D(ref['open_min_protection_risk_with_buy_sell_fees']))<D('1e-19')
  riskopen+=risk<=D(ref['quarter_percent_decision_nav_risk'])
  assert not x['request_reached'] and x['preview_maxq']>=100
  assert {z['pool'] for z in x['pools']}=={'probe','confirmed'}
  assert len(x['migration_observation'])==1 and x['migration_observation'][0]['result'] is True
  raw=next(z for z in states if z['intent']['CP1_id']==row['receipt']);s=raw['state']
  for z in x['pools']:
   pc,pr,_,_=resources(s,z['pool']);sc,sr,_,_=resources(s,sector='URFI881121');_,_,reserve,pending=resources(s)
   # Successful No60 migration can change pools but not sector/global resources. Here moved is empty.
   assert not x['migration_observation'][0]['moved']
   assert abs(pc-z['pool_capital'])<1e-7 and abs(pr-z['pool_risk'])<1e-7
   assert abs(sc-z['sector_capital'])<1e-7 and abs(sr-z['sector_risk'])<1e-7
   assert abs(reserve-z['reserved_cash'])<1e-7
   fmin=float(fee(q,p,cs,'buy'));nav=s['nav']-pending-fmin;cap=q*float(p);nr=q*max(0,float(p-floor));spend=min(float(D(s['available_exact'])-D(s['decision_nav'])*D('.1')),s['cash']-reserve)
   fails=[]
   if cap+fmin>spend+1e-9:fails.append('cash_or_original_reserve')
   if z['pool']=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')
   if z['pool']=='probe' and pr+nr>.005*nav+1e-9:fails.append('probe_risk')
   if sc+cap>z['sector_fraction']*nav+1e-9:fails.append('sector_capital')
   if sr+nr>.01*nav+1e-9:fails.append('sector_risk')
   held=sum(l['qty'] for l in s['lots'] if l['stock']==row['sid']);assert held==0
   if held*float(ref['open_raw'])+cap>.10*float(s['decision_nav'])+1e-9:fails.append('stock_capital')
   assert fails==z['minimum_failures_code_order'],(row['sid'],row['signal_day'],z['pool'],fails,z['minimum_failures_code_order'])
   assert 'cash_or_original_reserve' in fails and z['maximum_legal_quantity']==0
   assert abs(spend-z['spendable_admission'])<1e-7
   if z['pool']=='confirmed':confirmed[','.join(fails)]+=1
  per.append({'sid':row['sid'],'signal_day':row['signal_day'],'confirmed_failures':next(z for z in x['pools'] if z['pool']=='confirmed')['minimum_failures_code_order'],'minimum_open_allin_risk_fits':ref['open_min_fits_quarter_percent_decision_nav_risk']})
 assert riskref==9 and riskopen==9
 # Check9/6 direct original-prefix capability classes from independent JSON arithmetic.
 cls=Counter();s0riskbad=0;capable_and_riskfits=0
 for r in bounds:
  s=s0[r['opening']];_,_,reserve,pending=resources(s);spend=min(float(D(s['available_exact'])-D(s['decision_nav'])*D('.1')),s['cash']-reserve)
  assert abs(spend-r['original_S0']['spendable_above_original_cash_reserve'])<1e-7
  relief=sum((D(z['cash_excess_above_legal_minimum']) for z in r['prior_original_reservations'] if z['pool']=='confirmed'),D(0))
  assert relief==D(r['confirmed_excess_cash_arithmetic_upper_bound'])
  for z in r['prior_original_reservations']:
   assert z['excess_quantity']==z['actual_quantity']-z['legal_minimum']
   # Native order limit is exact original reference in the corresponding live order.
   full=next(z2 for z2 in all16 if z2['receipt'] in [p['receipt'] for p in all16] and z2['sid']==r['sid'] and z2['signal_day']==r['signal_day'])
   order=next(z2 for z2 in full['exact_open_responsibility']['live_reserved_orders'] if z2['oid']==z['original_budget_order'])
   direct=D(z['gross_reservation'])-D(z['legal_minimum'])*D(str(order['limit']))+D(z['fee_reservation'])-D(z['minimum_fee'])
   assert abs(direct-D(z['cash_excess_above_legal_minimum']))<D('1e-8')
  need=r['at_candidate']['minimum_cash']
  category='S0_insufficient' if spend+1e-7<need else 'S0_fits_and_original_confirmed_excess_directly_covers' if r['at_candidate']['spendable']+float(relief)+1e-7>=need else 'S0_fits_but_direct_release_insufficient'
  cls[category]+=1
  assert category!='S0_fits_but_direct_release_insufficient'
  s0riskbad+=not r['original_S0']['own_minimum_nominal_risk_fits']
  if category.startswith('S0_fits'):
   rr=next(z for z in all16 if z['sid']==r['sid'] and z['signal_day']==r['signal_day']);capable_and_riskfits+=rr['reference']['open_min_fits_quarter_percent_decision_nav_risk']
 assert cls=={'S0_insufficient':6,'S0_fits_and_original_confirmed_excess_directly_covers':9}
 assert s0riskbad==0 and capable_and_riskfits==6
# Verify saved full-prefix receipt counts against original records by cutoff; no new restoration.
root=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26/pair')
with gzip.open(root/'B.json.gz','rt') as f:book=json.load(f)
def atstr(s):return s.replace('T',' ')
streams={}
for name,fn in [('funding','funding.jsonl.gz'),('daily','daily.jsonl.gz'),('balances','balances.jsonl.gz')]:
 with gzip.open(root/fn,'rt') as f:streams[name]=[json.loads(x) for x in f]
for z in ident:
 assert z['passed'];end=atstr(z['end']);counts=z['full_prefix_records']
 for key,rows in streams.items():assert sum(atstr(r['at'])<=end for r in rows)==counts[key]
 assert sum(atstr(r['at'])<=end for r in book['trades'])==counts['trades']
 assert len(book['journal'][:counts['journal']])==counts['journal']
 ev=read(O/f"REPLAY_EVENTS_{z['checkpoint']}.json");assert len(ev)==z['events'] and sum(r['OPEN'] for r in ev)==z['opens'] and sum(r['CLOSE'] for r in ev)==z['closes']
 # Producer exact() explicitly canonical-digests all five complete restored prefixes; reviewed, not rerun.
script=(O/'observe_original.py').read_text()
for label in ['whole funding prefix','whole trade prefix','whole journal prefix','whole daily prefix','whole balance prefix']:assert label in script
res={'status':'PASS_WITH_SCOPE','receipts':16,'available_OPEN_routes':15,'unique_OPEN_dates':13,'confirmed_minimum_failures':dict(confirmed),'all15_probe_and_confirmed_available_migration_success_no_request':True,'min_reference_risk_fit_count_all16':riskref,'min_OPEN_risk_fit_count_all15':riskopen,'cash_precedence_classes':dict(cls),'S0_sector_risk_insufficient':s0riskbad,'cash_direct_release_capable9_also_allin_risk_fit':capable_and_riskfits,'engine_expected_actual_exact':True,'restoration_receipts_original_count_checks':ident,'scope':'JSON resource/fee/guard/capability arithmetic independently recomputed and original route hook identity verified. Inspected producer exact canonical digest checks for all5 restored full prefixes; independently checked original counts/cutoff clocks, but did not run another Runner or recompare unstored restored stream bytes. This is not an alternative strategy allocation or profit counterfactual.','direct_release_warning':'Original-prefix confirmed excess is conditional direct release under original roles/pools; not a global upper bound for evolving alternative allocation. Same-state quantity cap cannot rescue a minimum rejection.','new_accounts':0,'source_sha256':{str(O/n):hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ['RESTORE_IDENTITY.json','SUMMARY.json','ALL16_RECEIPTS_WITH_REAL_RESOURCES.json','EXISTING_OCCUPANCY_VS_PREFIX_RESERVATIONS.json','RESERVATION_BOUND_SUMMARY.json','ENGINE_IDENTITY_PY313.json','observe_original.py','private_route_readonly_observer.py','PREOPEN_EXACT_STATE.json','PRE_CANDIDATE_EXACT_STATE.json']}}
(R/'FUNDING_15OPEN_EVIDENCE_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in res.items() if k not in ['source_sha256','restoration_receipts_original_count_checks']},ensure_ascii=False,indent=2))

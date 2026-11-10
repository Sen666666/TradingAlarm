"""Screen existing complete Jul-Aug ledgers. No restore, engine or event calls."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction
from collections import defaultdict,Counter
from datetime import datetime
import json,hashlib,gc
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
A=W/'g-s-C-August-continuation-v1-20261102';M=W/'g-s-C-month-continuation-20261102'
Z=D(0);SOURCE={};ALL=[]
def read(p):
 p=Path(p);b=p.read_bytes();SOURCE[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def stamp(x):return datetime.fromisoformat(x)
def positive_negative(rows,key):
 vals=[D(r[key]) for r in rows]
 return dict(rows=len(vals),positive_rows=sum(v>0 for v in vals),negative_rows=sum(v<0 for v in vals),zero_rows=sum(v==0 for v in vals),
  gross_positive=sum((max(Z,v) for v in vals),Z),gross_negative=sum((min(Z,v) for v in vals),Z),net=sum(vals,Z))
for cell,arm in [('C10','C10'),('C20','C_BATCH20')]:
 x=read(A/'runs'/cell/'2025-08-29-CLOSE.json');a=x['account'];g=x['goal_coverage']
 layers={r['layer']:r for r in read(A/'analysis'/(cell+'-LAYERS.json'))}
 daily={r['day']:r for r in read(M/'july_end_analysis/DAILY.json')['2025_26-'+arm]}
 daily.update({r['day']:r for r in read(A/'analysis'/(cell+'-DAILY.json'))})
 by_at={stamp(r['certificate']['known_at']):r for r in x['results']}
 trades={t['receipt_id']:t for t in a['trades']};groups={};sale_ids=set()
 for oid,owner in a['funding_coverage']['order_goals'].items():
  batch=by_at[stamp(owner['created_at'])];cert=batch['certificate'];cid=cert['certificate_id']
  sales=[trades[eid] for eid,v in g['sale_events'].items() if v['order']==oid and '2025-07-01'<=trades[eid]['at'][:10]<='2025-08-29']
  if not sales:continue
  assert all(t['side']=='sell' and t['reason']=='actionable_S_funding' for t in sales)
  b=groups.setdefault(cid,dict(cell=cell,certificate=cid,original_plan_at=cert['known_at'],deadline=cert['deadline'],Q={s:q for s,q in cert['Q'].items() if q},D=cert['D'],source_orders=[],source_fills=[]))
  b['source_orders'].append(oid)
  for t in sales:
   assert t['receipt_id'] not in sale_ids;sale_ids.add(t['receipt_id']);b['source_fills'].append(t)
 # Every actual funding sell must appear once, including old July receipts.
 expected={t['receipt_id'] for t in a['trades'] if t['side']=='sell' and t.get('reason')=='actionable_S_funding' and '2025-07-01'<=t['at'][:10]<='2025-08-29'}
 assert expected==sale_ids,('missing original funding sales',cell,expected-sale_ids)
 for cid,b in sorted(groups.items(),key=lambda z:stamp(z[1]['original_plan_at'])):
  c=by_at[stamp(b['original_plan_at'])]['certificate'];projection=by_at[stamp(b['original_plan_at'])]['projection'];ff=[];anchor=defaultdict(Fraction)
  for eid,event in x['authority']['events'].items():
   ao=x['authority']['orders'][event['oid']]
   if ao['cid']==cid:
    t=trades[eid];assert stamp(c['known_at'])<stamp(t['at'])<=stamp(c['deadline'])
    ff.append(t);anchor[t['security_id']]+=Fraction(str(event['anchor_q']))
  allroles=[t for t in a['trades'] if t['side']=='buy' and t['security_id'] in b['Q'] and stamp(c['known_at'])<stamp(t['at'])<=stamp(c['deadline'])]
  def category(available):
   n=sum(s in available for s in b['Q']);return 'NONE' if n==0 else 'ALL_TARGET_NAMES' if n==len(b['Q']) else 'SOME_TARGET_NAMES'
  b.update(target_stocks=len(b['Q']),same_certificate_C_buys=ff,all_roles_target_buys_in_original_window=allroles,
   C_category=category({t['security_id'] for t in ff}),all_roles_category=category({t['security_id'] for t in allroles}),
   original_quantity_all_filled=all(anchor[s]==q for s,q in b['Q'].items()),filled_anchor_quantities=dict(anchor))
  assert all(anchor[s]<=q for s,q in b['Q'].items())
  b['actual_source_gross']=sum((D(t['gross_cny']) for t in b['source_fills']),Z)
  b['actual_source_net']=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in b['source_fills']),Z)
  b['actual_C_receiver_gross']=sum((D(t['gross_cny']) for t in ff),Z)
  b['actual_all_roles_receiver_gross']=sum((D(t['gross_cny']) for t in allroles),Z)
  source_parts=[]
  for t in b['source_fills']:
   assert t['settlement_id'] in g['settled']
   for p in t['parts']:
    candidates=[v for v in layers[p['layer']]['actual_sell_parts'] if v['receipt']==t['receipt_id'] and v['shares']==p['shares']]
    assert len(candidates)==1
    source_parts.append(dict(sid=t['security_id'],**candidates[0]))
  b['source_sell_parts']=source_parts;b['source_realized_PNL']=positive_negative(source_parts,'realized_trade_PNL')
  entry_layers=[layers[lid] for lid in {t['layer'] for t in ff}]
  b['C_receiver_actual_layer_outcomes_through_Aug29']=[{k:r[k] for k in ['layer','sid','opened','closed','realized_trade_PNL','unrealized_net_buy_cost','booked_dividend_income','total_contribution']} for r in entry_layers]
  b['C_receiver_outcomes']=positive_negative(entry_layers,'total_contribution')
  source_days=sorted({t['at'][:10] for t in b['source_fills']})
  b['actual_source_days']=source_days;b['source_day_end_fields']=[]
  for day in source_days:
   r=daily[day]
   risk=r.get('risk')
   if risk is None:
    flow=read(M/'runs'/('2025_26-'+arm)/(day+'-CLOSE-FLOW.json'))
    assert D(flow['after_balance']['available'])==D(r['available'])
    risk=flow['after_balance']['resources']['risk']
   rejections=[v for v in a['rejections'] if str(v.get('at',''))[:10]==day and v.get('sid') in b['Q']]
   b['source_day_end_fields'].append(dict(day=day,available=r['available'],NAV=r['NAV'],risk=risk,
    risk_scope='original CLOSE total; July read from existing small CLOSE-FLOW',
    receiver_rejections=rejections))
  b['quote_recheck']={'status':'NOT_YET_RECHECKED' if b['C_category']=='NONE' else 'NOT_REQUESTED_NONZERO_ACTUAL_C_FILL',
    'note':'Daily fill failures cannot be assumed knowable before first sale.'}
  # Preserve small original evidence only; no new portfolio state.
  b['original_target_trace']=[{k:r[k] for k in ['sid','q','raw_max','priority','blockers_or_necessary_bounds'] if k in r} for r in projection['trace'] if r['sid'] in b['Q']]
  ALL.append(b)
 # Cross-check old independent August per-order export without counting shared target buys repeatedly.
 old=read(A/'analysis'/(cell+'-ACTUAL_FUNDING_FLOWS.json'))['rows']
 old_ids={r['source_exit_order'] for r in old};now_ids={oid for b in groups.values() for oid in b['source_orders'] if any(t['at'].startswith('2025-08') and t['receipt_id'] in {s['receipt_id'] for s in b['source_fills']} for t in b['source_fills'])}
 assert old_ids==now_ids
 print(cell,'batches',len(groups),'C',dict(Counter(b['C_category'] for b in groups.values())),'all_roles',dict(Counter(b['all_roles_category'] for b in groups.values())),flush=True)
 del x,a,g,trades,groups,layers;gc.collect()

save('BATCHES.json',ALL)
summary={}
for cell in ['C10','C20','COMBINED']:
 rr=[r for r in ALL if cell=='COMBINED' or r['cell']==cell]
 summary[cell]=dict(batches=len(rr),source_orders=sum(len(r['source_orders']) for r in rr),source_fills=sum(len(r['source_fills']) for r in rr),
  C_categories=dict(Counter(r['C_category'] for r in rr)),all_roles_categories=dict(Counter(r['all_roles_category'] for r in rr)),
  all_original_Q_filled_batches=sum(r['original_quantity_all_filled'] for r in rr),
  by_C_category={cat:dict(batches=len(vv),source_gross=sum((r['actual_source_gross'] for r in vv),Z),source_net=sum((r['actual_source_net'] for r in vv),Z),
    receiver_C_gross=sum((r['actual_C_receiver_gross'] for r in vv),Z),receiver_all_roles_gross=sum((r['actual_all_roles_receiver_gross'] for r in vv),Z),
    source_actual_realized=positive_negative([p for r in vv for p in r['source_sell_parts']],'realized_trade_PNL'),
    receiver_actual_layer_outcomes=positive_negative([p for r in vv for p in r['C_receiver_actual_layer_outcomes_through_Aug29']],'total_contribution'),
    dates=[dict(cell=r['cell'],plan=r['original_plan_at'],source_days=r['actual_source_days'],certificate=r['certificate']) for r in vv])
    for cat in ['NONE','SOME_TARGET_NAMES','ALL_TARGET_NAMES'] if (vv:=[r for r in rr if r['C_category']==cat])})
save('SCREEN_SUMMARY.json',summary);save('SOURCE_SHA256.json',SOURCE)
save('SCREEN_CHECKS.json',dict(passed=True,financial_events=0,account_restores=0,all_original_funding_sell_receipts_exactly_once=True,all_August_order_exports_matched=True,
 denominator='cell x original CLOSE certificate with at least one actual actionable_S_funding sale by Aug29; two cells correlated, not independent trials',
 categories='stock-name coverage; ALL_TARGET_NAMES allows lower actual quantity than Q; separate full-Q completion count',
 no_per_dollar_attribution=True,no_counterfactual_PNL=True))

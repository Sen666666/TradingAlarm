"""Arithmetic prerequisites from captured ORIGINAL S0; no proposed allocation."""
from pathlib import Path
from decimal import Decimal as D
import json,sys
OUT=Path(__file__).resolve().parent
sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility');import native_adapter as A
J=A.J;P=A.P
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def eff(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
def resources(s,pool=None,sector=None):
 lots=[x for x in s['lots']if(pool is None or x['pool']==pool)and(sector is None or x['sector']==sector)]
 orders=[x for x in s['orders'].values()if x['qty']>0 and x['status']in['open','cancel_pending']and(pool is None or x['pool']==pool)and(sector is None or x['sector']==sector)]
 return dict(capital=sum(x['qty']*s['prices'][x['stock']]for x in lots)+sum(x['qty']*x['limit']for x in orders),
  risk=sum(x['qty']*max(0,s['prices'][x['stock']]-x['floor'])for x in lots)+sum(x['qty']*max(0,x['limit']-x['floor'])for x in orders),
  reserve=sum(x['qty']*(x['limit']+x['fee_per_share'])for x in orders),pending_fees=sum(x['qty']*x['fee_per_share']for x in orders))
s0=read(OUT/'PREOPEN_EXACT_STATE.json');s0={k[:10]:v for k,v in s0.items()}
all16=read(OUT/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json')
rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
rows=[]
for r in all16:
 x=r['exact_open_responsibility']
 if x is None:continue
 day=r['next_open'];s=s0[day]['state'];glob=resources(s);sector='URFI881121';sec=resources(s,sector=sector);pool=x['pools'][0]
 mincash=pool['minimum_capital']+pool['minimum_fee'];spend=min(float(D(s['available_exact'])-D(s['decision_nav'])*D('.1')),s['cash']-glob['reserve'])
 initialnav=s['nav']-glob['pending_fees']-pool['minimum_fee'];risk=pool['minimum_stop_risk'];confirmed=next(p for p in x['pools']if p['pool']=='confirmed')
 prior=[]
 for c in x['prior_actual_reserved_competitors']:
  sid=c['sid'];rule=eff(rules['quantity_versions'][sid],day)['rule'];minq=rule['buy_minimum'];q=c['shares'];assert q>=minq
  venue=eff(rules['venue_versions'][sid],day)['venue'];fs=eff(rules['fee_versions'][venue],day)['schedule'];fees=J.LR.L.FeeSchedule(fs['schedule_id'],tuple(J.LR.L.FeeComponent(**z)for z in fs['components']))
  minfee=J.LR.fees(minq,D(c['price']),fees,'buy',D(rules['security_metadata'][sid]['par_value']))
  grossrelief=(q-minq)*D(c['price']);feerelief=D(c['fee_reserved'])-minfee
  order=next(o for o in x['live_reserved_orders']if o['stock']==sid and o['qty']==q and o['role']==c['role'])
  prior.append(dict(sid=sid,name=c['name'],pool=c['pool'],role=c['role'],rank=c['original_frozen_intent']['rank'],actual_quantity=q,legal_minimum=minq,
   excess_quantity=q-minq,gross_reservation=c['gross_reserved'],fee_reservation=c['fee_reserved'],cash_excess_above_legal_minimum=grossrelief+feerelief,
   minimum_fee=minfee,sector=order['sector'],nominal_risk_excess=(q-minq)*max(0,order['limit']-order['floor']),
   dated_rule=rule,original_budget_order=order['oid']))
 confirmed_excess=sum((p['cash_excess_above_legal_minimum']for p in prior if p['pool']=='confirmed'),D(0))
 all_excess=sum((p['cash_excess_above_legal_minimum']for p in prior),D(0))
 cash_after_upper=confirmed['spendable_admission']+float(confirmed_excess)
 if spend+1e-7<mincash:classification='existing_holdings_cash_reserve_already_leave_less_than_minimum_before_first_new_candidate'
 elif cash_after_upper+1e-7<mincash:classification='prior_admissions_use_cash_but_confirmed_excess_above_minimum_cannot_cover_own_minimum'
 else:classification='cash_prerequisite_only_could_be_met_by_reducing_prior_confirmed_excess_no_allocation_or_profit_claim'
 rows.append(dict(sid=r['sid'],name=r['name'],signal_day=r['signal_day'],opening=day,classification=classification,
  original_S0=dict(available=s['available_exact'],decision_nav=s['decision_nav'],budget_nav=s['nav'],cash=s['cash'],outstanding_reserve=glob['reserve'],
   spendable_above_original_cash_reserve=spend,sector_capital=sec['capital'],sector_risk=sec['risk'],
   sector_capital_headroom=confirmed['sector_fraction']*initialnav-sec['capital'],sector_risk_headroom=.01*initialnav-sec['risk'],
   own_minimum_cash_fits=spend+1e-7>=mincash,own_minimum_nominal_risk_fits=risk<=.01*initialnav-sec['risk']+1e-7),
  at_candidate=dict(spendable=confirmed['spendable_admission'],minimum_cash=mincash,nominal_minimum_risk=risk,confirmed_constraints=confirmed['minimum_failures_code_order']),
  prior_original_reservations=prior,confirmed_excess_cash_arithmetic_upper_bound=confirmed_excess,all_pool_excess_cash_upper_bound=all_excess,
  at_candidate_spendable_plus_confirmed_excess_upper_bound=cash_after_upper,
  prior_confirmed_orders_with_excess=sum(p['pool']=='confirmed'and p['excess_quantity']>0 for p in prior),
  original_sequence_unchanged=True,no_alternative_order_created=True,no_rerestore=True,
  bound_is_not_an_executable_allocation=True,no_winner_sales_or_cancellations_assumed=True))
save('EXISTING_OCCUPANCY_VS_PREFIX_RESERVATIONS.json',rows)
from collections import Counter
summary=dict(original_open_targets=15,classes=dict(Counter(x['classification']for x in rows)),
 existing_sector_risk_insufficient_before_any_new_candidate=sum(not x['original_S0']['own_minimum_nominal_risk_fits']for x in rows),
 source='saved exact S0 and original admission orders only; no proposed account/path/route evaluation',new_policy_paths=0,new_replays=0)
save('RESERVATION_BOUND_SUMMARY.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
for x in rows:print(x['name'],x['signal_day'],'S0',round(x['original_S0']['spendable_above_original_cash_reserve'],2),'need',round(x['at_candidate']['minimum_cash'],2),'prior excess',round(float(x['confirmed_excess_cash_arithmetic_upper_bound']),2),'cashupper',round(x['at_candidate_spendable_plus_confirmed_excess_upper_bound'],2),x['classification'])

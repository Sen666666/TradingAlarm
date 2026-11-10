"""Independent M4 snapshot arithmetic/fee/core audit; reads only existing outputs."""
from pathlib import Path
from decimal import Decimal as D,ROUND_HALF_UP,ROUND_CEILING
from collections import defaultdict,Counter
import json,hashlib
O=Path(__file__).resolve().parent;P=O.parent;S=P/'mainline_candidate_v4_design_v1';Z=D(0)
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();dec=lambda r,k:D(str(r[k]))
raw={n:read(S/(n+'.json')) for n in ['SNAPSHOT_SUMMARY','ALL_SELECTED_REQUESTS','ALL50_STATIC_FEASIBILITY','ALL_REAL_REQUESTS','ALL_PLANNED_DONORS','EVENT_CAPITAL_IDENTITIES','CURRENT_SEED_RETIREMENT_AND_CORE']}
rules=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json'))
prior=read(P/'independent_audit_mainline_v3/economic_minimum_formula/SEP26_STATIC_TICKETS.json');checks=Counter();errors=[]
def check(k,v,ctx=None):
 checks[k]+=1
 if not v:errors.append(dict(check=k,context=ctx))
def version(vs,dt):
 a=[x for x in vs if x['from']<=dt and (not x.get('to') or dt<x['to'])];assert len(a)==1;return a[0]
def fee(s,dt,q,p,side,minimum_extra=False):
 venue=version(rules['venue_versions'][s],dt)['venue'];cs=version(rules['fee_versions'][venue],dt)['schedule']['components'];v=Z
 for c in cs:
  if c.get('side','both') not in ('both',side):continue
  basis=c.get('amount_basis','notional');base=q*p if basis=='notional' else D(q) if basis=='shares' else q*D(rules['security_metadata'][s]['par_value'])
  prop=base*D(c['rate']);a=max(prop,D(c.get('minimum_local','0')))
  if c.get('maximum_local') is not None:a=min(a,D(c['maximum_local']))
  if c.get('rounding_unit') is not None:
   u=D(c['rounding_unit']);a=(a/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
  if minimum_extra:
   if c['name']=='net_brokerage':v+=max(Z,a-prop)
  else:v+=a
 return v
def surcharge(s,dt,q,C):return fee(s,dt,q,C*D('1.0005'),'buy',True)+fee(s,dt,q,C*D('.9995'),'sell',True)
summary=[]
for sm in raw['SNAPSHOT_SUMMARY']:
 day=sm['snapshot_day'];sel=[r for r in raw['ALL_SELECTED_REQUESTS'] if r['snapshot_day']==day];ss=[r for r in raw['ALL50_STATIC_FEASIBILITY'] if r['snapshot_day']==day];req=[r for r in raw['ALL_REAL_REQUESTS'] if r['snapshot_day']==day];ds=[r for r in raw['ALL_PLANNED_DONORS'] if r['snapshot_day']==day];ls={r['lot_id']:r for r in raw['CURRENT_SEED_RETIREMENT_AND_CORE'] if r['day']==day};events={r['sector51']:r for r in raw['EVENT_CAPITAL_IDENTITIES'] if r['snapshot_day']==day};bysec={r['sector51']:r for r in ss}
 for r in req:
  q=r['unit_q'];s=r['sid'];nxt=r['next_known_trade_day'];C=dec(r,'C')
  if q:
   check('unit_cost_independent_dated_fee',dec(r,'unit_cost')==q*C*D('1.0005')+fee(s,nxt,q,C*D('1.0005'),'buy'),[day,s])
  if r['kind']=='SEED' and q:
   qr=version(rules['quantity_versions'][s],nxt)['rule'];check('econ_legal_quantity',q>=qr['buy_minimum'] and (q-qr['buy_minimum'])%qr['buy_step']==0,[day,s]);check('minimum_commission_threshold',surcharge(s,nxt,q,C)<=D('.001')*q*C,[day,s]);prev=q-qr['buy_step'];check('minimal_economic_quantity',prev<qr['buy_minimum'] or surcharge(s,nxt,prev,C)>D('.001')*prev*C,[day,s]);check('original_2pct_ticket_cap',dec(r,'unit_cost')<=D('.02')*dec(r,'original_ticket_NAV'),[day,s]);check('capacity_ceiling',q*C<=dec(r,'capacity_value'),[day,s]);check('stock_cap',dec(r,'unit_cost')<=D('.1')*dec(sm,'NAV'),[day,s]);check('surcharge_logged_exact',dec(r,'surcharge')==surcharge(s,nxt,q,C),[day,s])
 for r in sel:
  q=r['static_funded_q'];check('seed_no_small_fragment',r['kind']!='SEED' or q in (0,r['unit_q']),[day,r['sid']]);check('funded_not_above_plan',q<=r['planned_q'],[day,r['sid']])
  if q:check('funded_cost_independent_fee',dec(r,'static_funded_cost')==q*dec(r,'C')*D('1.0005')+fee(r['sid'],r['next_known_trade_day'],q,dec(r,'C')*D('1.0005'),'buy'),[day,r['sid']])
 phases={p:sum((dec(r,'static_funded_cost') for r in sel if r['phase']==p),Z) for p in ['EVENT','MATURE','RESIDUAL']};event=sum((dec(r,'planned_cost') for r in sel if r['phase']=='EVENT'),Z);net=sum((dec(r,'net_cash') for r in ds),Z);buy=sum(phases.values());mature=dec(sm,'mature_budget_after_event');B=dec(sm,'budget_before_event');j=[r for r in ss if r['M']==1 and r['E'] is not None and D(str(r['E']))>0]
 check('actual_reservation_deducted',B-event==mature,day);check('reservation_log',event==dec(sm,'event_reserved_actual_cost'),day);check('T_sum_equals_reduced_B',not j or abs(sum((dec(r,'T_mature_residual') for r in j),Z)-mature)<D('1e-16'),day);check('event_core_budget',event<=max(Z,B-sum((dec(r,'new_fixed') for r in j),Z)),day);check('cash_reconstruction',dec(sm,'cash')+dec(sm,'mandatory_close_estimate')+net-buy==dec(sm,'closing_cash_after_conditional_orders'),day);check('cash_floor',dec(sm,'closing_cash_after_conditional_orders')>=dec(sm,'reserve'),day);check('same_industry_single_direction',not ({r['sector51'] for r in ds}&{r['sector51'] for r in sel if r['static_funded_q']}),day)
 for r in ss:
  check('T_total_not_double_counted',dec(r,'T_total_including_event')==dec(r,'T_mature_residual')+dec(r,'event_reserved_cost'),[day,r['sector51']]);check('T_above_fixed',dec(r,'T_mature_residual')>=dec(r,'new_fixed'),[day,r['sector51']])
 for sec,e in events.items():
  selected=[r for r in sel if r['sector51']==sec and r['phase'] in ('EVENT','RESIDUAL')];cost=sum((dec(r,'static_funded_cost') for r in selected),Z);check('event_spend_cap',cost<=dec(e,'remaining'),[day,sec]);check('no_old_priority',not any(r['phase']=='EVENT' for r in selected) or (e['priority_available'] and not e['priority_attempted']),[day,sec]);check('cap_frozen_NAV',not e['birth_NAV'] or dec(e,'capital_cap')==D('.02')*dec(e,'birth_NAV'),[day,sec]);check('remaining_no_refill',dec(e,'remaining')==max(Z,dec(e,'capital_cap')-dec(e,'actual_prior_SEED_consumption')),[day,sec])
 nextday=next(r['next_known_trade_day'] for r in req)
 for d in ds:
  l=ls[d['lot_id']];q=d['qty'];p=dec(l,'raw_mark')*D('.9995');check('donor_net_fee',dec(d,'net_cash')==q*p-fee(d['sid'],nextday,q,p,'sell'),[day,d['lot_id']]);check('no_core_sold',q<=l['qty']-l['core_qty'],[day,d['lot_id']]);check('within_mobile',q<=l['mobile_qty_m4'],[day,d['lot_id']]);check('known_donor',not l['unknown'],[day,d['lot_id']]);check('T1',l['bought']<nextday,[day,d['lot_id']]);check('no_locked_donor',l['locked'] in (False,'False'),[day,d['lot_id']])
 summary.append(dict(day=day,phase_costs=phases,donor_net=net,cash_end=sm['closing_cash_after_conditional_orders'],event_names=sum(r['phase']=='EVENT' for r in sel)))
old={r['sid']:r for r in prior if r['selected']};new={r['sid']:r for r in raw['ALL_SELECTED_REQUESTS'] if r['snapshot_day']=='2024-09-26' and r['phase']=='EVENT'};check('independent_373_ticket_selection_exact',set(old)==set(new));
for s,r in old.items():check('independent_373_quantity_and_cost',r['q_econ']==new[s]['unit_q'] and D(r['all_in_cost'])==D(new[s]['unit_cost']),s)
report=dict(status='PASS' if not errors else 'FAIL',checks=dict(checks),error_count=len(errors),errors=errors,snapshots=summary,source_hashes={str(p):sha(p) for p in [S/'STATIC_MECHANISM.md',S/'build_static.py']+[S/(n+'.json') for n in raw]},limitations=['Static substitutions on M3 account states, not M4 account history.','Event priority/spend mapped from past M3 logs, not independently existent M4 event lifecycle.','No next-OPEN market data used; OPEN cost proxy never establishes matching.','Assertion scaffold is not a substitute for actual engine integration and exact migration tests.'])
(O/'STATIC_SNAPSHOT_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['source_hashes','checks']},ensure_ascii=False,indent=2,default=str))

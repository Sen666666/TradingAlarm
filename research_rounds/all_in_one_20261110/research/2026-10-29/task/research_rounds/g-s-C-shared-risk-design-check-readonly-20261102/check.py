"""Read frozen references only. No provider, allocator, account or price model."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
HERE=Path(__file__).resolve().parent;W=HERE.parent;P=W/'g-s-C-UP-loss-capital-design-readonly-20261102'
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,default=str)+'\n')
def need_S(rows,Gcap):
 total=sum((D(z['risk'])for z in rows),D(0));left=Gcap;exempt=D(0)
 for z in sorted(rows,key=lambda z:-(D(z['risk'])/D(z['gross']))if D(z['gross'])else D(0)):
  cap=min(left,D(z['gross']));exempt+=cap*D(z['risk'])/D(z['gross'])if D(z['gross'])else D(0);left-=cap
 return dict(total_risk=total,optimistic_G_risk_exempt=exempt,minimum_S_risk_needed=max(D(0),total-exempt),fractional_G_relaxation_not_legal_target=True)
def main():
 refs=read(P/'RISK_ENVELOPES.json');events=read(W/'g-s-C-cp1-reset-capital-readonly-20261102/EVENTS.json');context=read(W/'g-s-C-engineering-causal-readonly-20261102/DAILY_RESOURCE_CONTEXT.json');market=read(P/'INDUSTRY_ASOF.json');out={};maxcheck={}
 for arm,a in refs.items():
  em={(e['sid'],e['day']):e for e in events[arm]};nav={e['day']:D(e['decision_NAV'])for e in context[arm]};ss=[];mm=[]
  for key,b in a['reference_budgets'].items():
   if b['sector']not in ['URFI881268','URFI881271','URFI881129']:continue
   day=b['first_legal_candidate_batch'];rr=[]
   for z in b['reference_candidates']:
    e=em[(z['sid'],day)];rr.append(dict(z,name=e['name'],original_C_plan=e['C_plan_q'],actual_confirmed_C_filled=any(o['filled_qty']for o in e['C_orders']),other_T_orders=e['T_orders']))
   widest=max(rr,key=lambda z:D(z['risk']));funded=[z for z in rr if z['actual_confirmed_C_filled']];mf=max(funded,key=lambda z:D(z['risk']))if funded else None
   mm.append(dict(sector=b['sector'],proof_day=__import__('datetime').date.fromordinal(b['source_proof']['confirmed']).isoformat(),first_reference_day=day,B=b['B'],max_reference=widest,max_among_actually_funded_references=mf,
    effect_of_unfunded_reference_on_B=D(b['B'])-D(mf['risk'])if mf else None,funding_outcome_used_only_for_diagnosis_not_candidate_domain=True))
   if b['sector']not in ['URFI881271','URFI881129']:continue
   ordered=sorted(rr,key=lambda z:(z['priority'],z['sid']));base=nav[day]*D('.2');prefix=[]
   for count in [5,8]:
    rows=ordered[:count];v=need_S(rows,base);prefix.append(dict(requested_stocks=count,available=len(ordered),actual_prefix_count=len(rows),original_independent_target_capital=sum((D(z['gross'])for z in rows),D(0)),
      capital_fraction=sum((D(z['gross'])for z in rows),D(0))/nav[day],min_S_risk=v['minimum_S_risk_needed'],B=b['B'],B_unused_upper_bound_not_ruled_out=len(rows)==count and v['minimum_S_risk_needed']<=D(b['B']),
      minimum_native_units_already_respected=True,stock_list=[z['sid']for z in rows],all_old_occupancy_and_cash_ignored=True,not_guaranteed_feasibility=True))
   ss.append(dict(sector=b['sector'],proof=b['source_proof'],reference_day=day,decision_NAV=nav[day],B=b['B'],B_NAV=D(b['B'])/nav[day],eligible_reference_stocks=len(rr),original_priority_prefix_checks=prefix))
  out[arm]=ss;maxcheck[arm]=mm
 save('WINNER_INDUSTRY_CAPACITY_BOUNDS.json',out);save('UNFUNDED_MAX_EFFECT.json',maxcheck)
 timeline={s:[dict(day=z['day'],events=z['scope']['events'],mature=z['scope']['mature'],permit=z['scope']['permit'],support=z['scope']['support'],latest_same_context_proof=z['latest_same_context_advance'],industry_H1=z['H1'],rank=z['H1_rank90'])for z in market if z['sector']==s]for s in ['URFI881271','URFI881129']};save('ACTUAL_PROOF_TIMELINES.json',timeline)
 # A deterministic logical counterexample, not a threshold proposal or cash ledger.
 assert max(D(5000),D(9000))==D(9000)>D(5000)
 assert D(1000)*(D(105)-D(95))==D(10000)>D(5000)
 assert D(500)*(D(105)-D(95))==D(5000)
 save('STATIC_CHECKS.json',dict(unfunded_wide_candidate_can_expand_first_B=True,later_candidate_cannot_change_already_frozen_B_under_current_contract=True,
  opening_gap_requires_pre_fill_shrink=True,example=dict(close_preview_already_includes_execution_adjustment=100,floor=95,close_qty=1000,B=5000,new_open_preview=105,unchanged_qty_risk=10000,upper_qty_before_other_checks=500),
  no_account_events=True,no_new_Q_D_generated=True,no_target_allocator=True,design_source_sha256=hashlib.sha256((P/'CANDIDATE.txt').read_bytes()).hexdigest()))
 print('STATIC_READY',flush=True)
if __name__=='__main__':main()

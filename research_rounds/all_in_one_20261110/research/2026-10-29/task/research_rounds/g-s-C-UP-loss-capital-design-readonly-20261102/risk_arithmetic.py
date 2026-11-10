"""Necessary risk-cap inequalities on original plans, NOT a new target allocator."""
from pathlib import Path
from decimal import Decimal as D
import sys,pickle,hashlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import analyze as A
Z=D(0)
def optimistic_S_risk(rows,gross_G_upper):
 """Relaxed fractional G partition: ignore all old positions and all other limits.
 Returns a LOWER bound on S risk needed by this original fixed set of new orders.
 No candidate quantities or donations are changed or generated.
 """
 risk=sum((z['risk']for z in rows),Z);left=gross_G_upper;exempt=Z
 for z in sorted(rows,key=lambda z:-(z['risk']/z['gross'])if z['gross']else Z):
  cap=min(left,z['gross']);exempt+=cap*z['risk']/z['gross']if z['gross']else Z;left-=cap
 return dict(total_risk=risk,optimistic_G_capital_upper=gross_G_upper,maximum_G_risk_exempt=exempt,minimum_S_risk_needed=max(Z,risk-exempt),all_old_industry_commitments_ignored_for_upper_bound=True,fractional_relaxation=True,not_target_plan=True)
def main():
 A.M.guard();i={(z['sector'],z['day']):z for z in A.read(HERE/'INDUSTRY_ASOF.json')};result=A.read(HERE/'RESULTS.json');out={};origsrc={}
 for arm,res in result.items():
  p=A.MONTH/'runs'/arm/'2025-07-31-CLOSE.pkl';r=pickle.loads(p.read_bytes());origsrc[str(p)]=A.E.M.P.sha(p);proof_budgets={};daily=[];early={}
  for v in r.results:
   day=v['at'][:10];tr=r.trusted[v['certificate']['trusted_id']]
   # Import the SAME already-guarded C transform; no solve/route/account call.
   import c_selector as C
   s,ds,audit=C.transform(tr['snapshot'],tr['demands'],tr['evidence']);nd=D(s['decision_nav'])
   sectors=sorted({d['sector']for d in ds if d['use']=='S'})
   for sec in sectors:
    m=i[(sec,day)];proof=m['latest_same_context_advance'];key=proof['event_id']if proof else None;dd=[d for d in ds if d['sector']==sec and d['use']=='S'];legal=[]
    for d in dd:
     p0=D(d['mark'])*D('1.0005');stock_cap=sum((D(z['capital'])for z in s['rows']if z['sid']==d['sid']),Z);q=C.J.rule(d['quantity']).buy_floor(min(d['max_q'],max(0,int((nd*D('.1')-stock_cap)/p0))))
     if q>=d['quantity']['buy_minimum']:legal.append(dict(sid=d['sid'],q=q,price=p0,floor=d['floor'],risk=D(q)*max(Z,p0-D(d['floor'])),gross=D(q)*p0,priority=d['priority']))
    if key and key not in proof_budgets and legal:
     proof_budgets[key]=dict(sector=sec,first_legal_candidate_batch=day,source_proof=proof,B=max(z['risk']for z in legal),reference_candidates=legal,design_sha256=hashlib.sha256((HERE/'CANDIDATE.txt').read_bytes()).hexdigest())
    planned=[]
    for d in dd:
     q=v['projection']['Q'][d['sid']]
     if q:planned.append(dict(sid=d['sid'],q=q,gross=D(q)*D(d['mark'])*D('1.0005'),risk=D(q)*max(Z,D(d['mark'])*D('1.0005')-D(d['floor']))))
    if not planned:continue
    # Actual same-date G permission from immutable saved CLOSE, no hypothetical fallback.
    x,_=A.E.snapshot(arm,day);g=x['account']['policy']['scopes']['G'];Gnew=g['permit']and g['support']and x['account']['policy']['act']['on']
    envelope=optimistic_S_risk(planned,nd*D('.2')if Gnew else Z);b=proof_budgets.get(key)
    actual=[]
    for z in res['funded_layers']:
     if z['event']['day']==day and z['layer']['sector']==sec and z['layer']['purpose']=='S':
      l=z['layer'];pr=z['source_initial_protection'];actual.append(dict(sid=l['sid'],gross=D(l['buy_gross']),risk=D(l['initial_qty'])*max(Z,D(pr['entry_price'])-D(pr['initial_floor_raw']))))
    daily.append(dict(day=day,sector=sec,proof=proof,reference=b,original_planned_rows=planned,decision_envelope=envelope,
      B_sufficient_even_if_completely_unused=envelope['minimum_S_risk_needed']<=b['B']if b else None,
      actual_UP_S_fills=actual,actual_open_price_envelope=optimistic_S_risk(actual,nd*D('.2')if Gnew else Z),
      actual_quantities_and_open_prices_evaluation_only=True,no_budget_consumption_or_new_Q_D_simulated=True))
  out[arm]=dict(reference_budgets=proof_budgets,daily_positive_S_plans=daily)
  print(arm,'refs',len(proof_budgets),'positive_sector_batches',len(daily),flush=True)
 A.save('RISK_ENVELOPES.json',out);A.save('RISK_ARITHMETIC_CHECKS.json',dict(account_events=0,new_allocations=0,source_checkpoints=origsrc,design_hash_before_arithmetic=hashlib.sha256((HERE/'CANDIDATE.txt').read_bytes()).hexdigest()))
if __name__=='__main__':main()

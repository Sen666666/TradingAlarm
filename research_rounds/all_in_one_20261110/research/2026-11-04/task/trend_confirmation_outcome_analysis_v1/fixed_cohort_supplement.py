"""Existing frozen cohorts and native held/new layer observations only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import gzip,json,importlib.util
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
sp=importlib.util.spec_from_file_location('reused_cohort_helpers',T/'capacity_cost_guard_analysis_v1/analyze_completed_v1.py');H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H)
n=H.n;day=H.day;read=H.read;save=H.save
tailsource=T/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json';tails=read(tailsource)['members'];semis={r['sid'] for r in read(T/'capacity_cost_guard_analysis_v1/STRICT_SEMICONDUCTOR_MEMBERS.json')['members']};out={}
def key(budget,receipt):return (budget.split('|',1)[1] if budget and '|' in budget else budget,receipt)
for win in ('long','strong'):
 ww={};cohort=tails['2022_2024' if win=='long' else 'strong'];p=O/f'full_{win}_v1';run=T/'trend_confirmation_native_v1'/f'full-{win}-v1/pair';snaps={}
 if win=='strong':
  with gzip.open(run/'daily.jsonl.gz','rt') as f:
   for line in f:
    r=json.loads(line)
    if day(r['at'])=='2025-12-31':snaps[r['account']]=r
 for arm in ('B','UNIFORM50','A_ONLY','A_OR_B'):
  ls=read(p/'analysis'/win/arm/'LAYERS.json')
  with gzip.open(run/f'{arm}.json.gz','rt') as f:b=json.load(f)
  mapping=defaultdict(list)
  for l in ls:m=b['metadata'][str(l['layer'])];mapping[key(m.get('budget_order'),l.get('receipt'))].append(l)
  tailrows=[dict(original=r,matched_actual_layers=mapping.get(key(r.get('budget_order'),r.get('receipt')),[])) for r in cohort]
  members=[l for r in tailrows for l in r['matched_actual_layers']]
  z=ww[arm]=dict(original_fixed_tail_order_matches=tailrows,original_tail_summary=dict(frozen_original_orders=len(cohort),matched_original_orders=sum(bool(r['matched_actual_layers']) for r in tailrows),matched_actual_layers=len(members),actual_buy_cash=sum((n(l['cost']) for l in members),Z),actual_life_contribution_through_window_end=sum((n(l['net']) for l in members),Z)),scope='Original old PVR83/94 list preserved unchanged; no forced sid-only matches; actual native cohort contributions, not lost profits or causal alpha.')
  if win=='strong':
   bound='2025-12-31';active={l['id']:l for l in snaps[arm]['layers']};groups=defaultdict(lambda:dict(layers=0,wealth=Z));cases=[]
   fixed=read(T/'risk_constraints/no60_capital_deployment_v2/2025_26_ORIGINAL_FIXED_WINNERS_AND_CONTROLS.json');ids=[r['sid'] for r in fixed]+['002747.SZ','002718.SZ','688766.SH','688605.SH','002969.SZ','300489.SZ']
   for sid in dict.fromkeys(ids):
    ss=[l for l in ls if l['sid']==sid];rg={}
    for role in ('core','mobile'):
     rr=[l for l in ss if l['role']==role];rg[role]=dict(actual_layers=len(rr),actual_buy_cash=sum((n(l['cost']) for l in rr),Z),actual_window_life_contribution=sum((n(l['net']) for l in rr),Z),actual_layers_detail=rr)
    cases.append(dict(sid=sid,name=H.A.META[sid]['name'],roles=rg))
   z['fixed_stock_cases_with_core_mobile']=cases
   for l in ls:
    if l['sid'] not in semis:continue
    if day(l['opened'])<=bound:
     if l['layer'] not in active:continue
     x=active[l['layer']];before=n(x['cash'])+n(x['dividend'])+D(x['qty'])*H.A.price(l['sid'],bound);g='strict_semi_actually_held_2025Dec31'
    else:before=Z;g='strict_semi_newly_filled_2026H1'
    groups[g]['layers']+=1;groups[g]['wealth']+=n(l['net'])-before
   phase=read(p/'FIXED_PHASE_WEALTH.json')[arm]['strict_semiconductor_2026H1'];H.expect(sum((v['wealth'] for v in groups.values()),Z),n(phase['interval_wealth']),'H1semiheldnew')
   z['strict_semiconductor_H1_old_new_layer_bridge']=dict(boundary=bound,groups=dict(groups),interval_wealth=phase['interval_wealth'])
 out[win]=ww
save(O/'FIXED_COHORT_SUPPLEMENT.json',dict(windows=out,original_tail_source=str(tailsource),original_tail_sha256=H.sha(tailsource),analysis_sha256=H.sha(__file__),new_account_events=0,derived_statistics_independent_review='PENDING'))
for w,ww in out.items():print(w,{a:v['original_tail_summary'] for a,v in ww.items()},flush=True)

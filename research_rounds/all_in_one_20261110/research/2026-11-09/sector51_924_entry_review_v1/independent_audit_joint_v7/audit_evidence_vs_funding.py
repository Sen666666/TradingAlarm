"""Read-only descriptive diagnosis. Never modifies strategy, runs allocation, or computes a counterfactual."""
from pathlib import Path
from decimal import Decimal as D,ROUND_HALF_UP,ROUND_CEILING
from collections import Counter,defaultdict
import ast,json,csv,hashlib
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;P=O.parent;F=P/'joint51_candidate_v7_facts/full_20241031_once';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
orders=read(F/'ORDERS.json');cands=read(F/'CANDIDATES.json');holds=read(F/'HOLDINGS.json');equity=read(F/'EQUITY_EVENTS.json');events=read(F/'CP_EVENTS.json');attempts={x['id']:x for x in read(F/'ATTEMPTS.json')};seed={x['round_id']:x for x in orders if x['side']=='BUY_SEED'};last=read(F/'DAY_LEDGER.json')[-1]['day'];sector={(x['day'],x['sector51']):x for x in read(F/'SECTOR_DAILY.json')};cpcreated={x['cp_id']:x for x in events if x['event']=='CREATED_AFTER_SEED'}
trial=[x for x in orders if '2024-10-10'<=x['day']<=last and x['reason']=='TRIAL_SECTOR_FALSE'];assert all(attempts[x['round_id']]['add_count']==0 for x in trial);assert len({x['round_id'] for x in trial})==len(trial)
allowed={'ADD_NO_LEGAL_Q:cash_reserve','ADD_NO_LEGAL_Q:sector_cap'};targets={x['round_id']:x for x in trial};rejections=[x for x in cands if x['phase']=='OPEN' and x['event']=='ADD' and x['decision'] in allowed and x.get('round_id') in targets and x['day']<targets[x['round_id']]['day']]
M={x['symbol']:x for x in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};ids={x['sid'] for x in rejections};raw={s:pd.read_parquet(next(p for p in M[s]['source_sha256'] if p.endswith('/signal.parquet'))) for s in ids};cp={s:pd.read_parquet(M[s]['refs']['CP1']) for s in ids};facts={s:pd.read_parquet(M[s]['refs']['facts']) for s in ids}
rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json')
# Reuse only independent fee arithmetic by AST, never importing account or execution code.
source=ast.parse((O/'reconcile_joint.py').read_text());pure=ast.Module(body=[x for x in source.body if isinstance(x,ast.FunctionDef) and x.name in ['version','fee']],type_ignores=[]);exec(compile(pure,'independent_fee_arithmetic','exec'))
checks=Counter();errors=[]
def check(k,v,ctx):
 checks[k]+=1
 if not v:errors.append({'check':k,'context':ctx})
def lin(z):return tuple(str(z[k]) for k in ['source_kind','source_path','segment_id'])
def tru(x):return pd.notna(x) and x in [True,1]
def div(rid,d):return sum((D(x['receivable_delta']) for x in equity if x.get('round_id')==rid and x['event']=='ACCRUE_NET80' and x['day']<=d),D(0))
def flow(rid,d):return sum((D(x['cash_delta']) for x in orders if x['round_id']==rid and x['day']<=d),D(0))
closeplans={(x['day'],x.get('round_id')):x for x in cands if x['phase']=='CLOSE' and x['event']=='ADD_GATE'};detail=[]
for x in rejections:
 rid=x['round_id'];s=x['sid'];dt=x['day'];t=x['signal_day'];d=pd.Timestamp(dt);tt=pd.Timestamp(t);a=attempts[rid];ss=seed[rid];q=ss['qty'];z=raw[s].loc[d];old=raw[s].loc[tt];ce=cpcreated[x['cp_id']];ct=pd.Timestamp(ce['day']);floor=D(ce['candidate']);ctx=[rid,dt]
 check('no_actual_ADD_ever',a['add_count']==0 and not any(o['round_id']==rid and o['side']=='BUY_ADD' for o in orders),ctx)
 check('no_prior_exit_before_rejected_ADD',not any(o['round_id']==rid and o['side'].startswith('SELL') and o['day']<=dt for o in orders),ctx)
 cl=closeplans[(t,rid)];check('matching_positive_close_plan',cl['decision']=='ADD_PLANNED' and cl['cp_id']==x['cp_id'] and D(cl['close_net'])>0,ctx)
 check('own_sector_strength_previous_CLOSE',sector[(t,x['sector51'])]['strength'],ctx)
 nets=[]
 for when,bar,field in [(t,old,'raw_close'),(dt,z,'raw_open')]:
  price=D(str(bar[field]))*D('.9995');net=flow(rid,when)+div(rid,when)+q*price-fee(s,when,q,price,'sell');nets.append(net)
 check('recomputed_close_net_matches_and_positive',nets[0]==D(x['close_net']) and nets[0]>0,ctx);check('recomputed_OPEN_net_matches_and_positive',nets[1]==D(x['open_net']) and nets[1]>0,ctx)
 check('post_seed_source_CP_receipt',ss['day']<=ce['day']<=t and tru(cp[s].loc[ct,'receipt']) and floor==D(str(cp[s].loc[ct,'candidate'])),ctx)
 check('same_source_lineage',all(lin(v)==lin(raw[s].loc[ct]) for _,v in raw[s].loc[ct:d].iterrows()),ctx)
 vals=[]
 for b,z0 in raw[s].loc[ct:d].iterrows():
  fac=D(str(z0.adjustment_factor))
  if b>ct:vals.append(D(str(z0.raw_open))*fac>floor)
  if b<d:vals.append(D(str(z0.raw_close))*fac>floor)
 check('source_CP_unbreached_to_OPEN',all(vals),ctx)
 cur=None;invalid=set()
 for e in events:
  if e['round_id']!=rid or e['day']>dt or (e['day']==dt and e['phase']!='OPEN'):continue
  if e['event']=='CREATED_AFTER_SEED':cur=e['cp_id']
  elif e['event']=='INVALIDATED':invalid.add(e['cp_id'])
  elif e['event'] in ['SUPERSEDED','CONSUMED_ON_FILL']:cur=None
 check('latest_unconsumed_valid_CP',cur==x['cp_id'] and cur not in invalid,ctx)
 fs=facts[s].loc[pd.Timestamp(ss['day']):tt];initial=facts[s].loc[pd.Timestamp(ss['signal_day'])];ifr=max([D(str(initial.i_floor))]+[D(str(y.i_floor)) for _,y in fs.iterrows() if tru(y.i_target) and pd.notna(y.i_floor) and y.i_floor>0])
 check('OPEN_above_known_I_and_CP',D(str(z.raw_open))*D(str(z.adjustment_factor))>max(ifr,floor),ctx)
 check('logged_no_filled_quantity',x['executed_q']==0,ctx)
 detail.append({k:x[k] for k in ['day','sid','round_id','sector51','signal_day','decision','cp_id','planned_q','attempt_budget','stock_cap','sector_cap','cash_reserve']}|{'independent_close_net':str(nets[0]),'independent_OPEN_net':str(nets[1]),'known_I_floor':str(ifr),'known_CP_floor':str(floor)})
# Per-round existing-ledger contribution and exit scale. No assumed post-exit prices/holdings.
def holding_mv(rid,d):return sum((D(x['market_value']) for x in holds if x['round_id']==rid and x['day']==d),D(0))
def contribution(rid,d):return flow(rid,d)+div(rid,d)+holding_mv(rid,d)
byr=defaultdict(list)
for x in rejections:byr[x['round_id']].append(x)
rows=[]
for tr in trial:
 rid=tr['round_id'];z=byr[rid];prev=max(x['day'] for x in holds if x['round_id']==rid and x['day']<tr['day']);mv=D(tr['notional'])/D('.9995');rows.append({'round_id':rid,'sid':tr['sid'],'name':tr['name'],'sector51':tr['sector51'],'seed_day':seed[rid]['day'],'zero_ADD_trial_exit_day':tr['day'],'exit_qty':tr['qty'],'last_close_MV_before_exit':str(holding_mv(rid,prev)),'raw_OPEN_value_of_exited_qty':str(mv),'proxy_net_sale_proceeds':tr['cash_delta'],'round_marked_PNL_at_exit':str(contribution(rid,tr['day'])),'prior_cash_rejected_ADDs':sum(x['decision'].endswith('cash_reserve') for x in z),'prior_sector_rejected_ADDs':sum(x['decision'].endswith('sector_cap') for x in z),'prior_capital_rejected_ADDs':len(z),'prior_capital_rejected_days':','.join(x['day'] for x in z),'weak_ADD_gate_ever_passed_but_never_funded':bool(z)})
software_ids={x['round_id'] for x in holds if x['day']=='2024-10-08' and x['sector51']=='软件与IT服务'};software=[]
for rid in sorted(software_ids):
 a=attempts[rid];oo=[x for x in orders if x['round_id']==rid and x['day']>='2024-10-10' and x['side'].startswith('SELL')];zz=[x for x in cands if x.get('round_id')==rid and x['phase']=='OPEN' and x['event']=='ADD' and x['decision'] in allowed and (not oo or x['day']<oo[0]['day'])];tt=[x for x in rows if x['round_id']==rid];hs=[x for x in holds if x['day']==last and x['round_id']==rid];v={'round_id':rid,'sid':a['sid'],'name':seed[rid]['name'],'seed_day':a['seed_day'],'actual_ADD_count':a['add_count'],'oct8_MV':str(holding_mv(rid,'2024-10-08')),'oct8_cumulative_round_PNL':str(contribution(rid,'2024-10-08')),'exit_orders_since_oct10':len(oo),'exit_days':','.join(x['day'] for x in oo),'exit_reasons':','.join(x['reason'] for x in oo),'total_exit_qty_since_oct10':sum(x['qty'] for x in oo),'total_raw_OPEN_exit_value':str(sum((D(x['notional'])/D('.9995') for x in oo),D(0))),'net_exit_proceeds':str(sum((D(x['cash_delta']) for x in oo),D(0))),'capital_rejected_ADDs_before_first_exit':len(zz),'cash_rejected_ADDs_before_first_exit':sum(x['decision'].endswith('cash_reserve') for x in zz),'sector_rejected_ADDs_before_first_exit':sum(x['decision'].endswith('sector_cap') for x in zz),'final_qty':sum(x['qty'] for x in hs),'final_MV':str(holding_mv(rid,last)),'final_cumulative_round_PNL':str(contribution(rid,last)),'zero_ADD_TRIAL_exit':bool(tt),'trial_exit_metrics':tt[0] if tt else None};software.append(v)
hit=[x for x in rows if x['weak_ADD_gate_ever_passed_but_never_funded']];softtrial=[x for x in rows if x['round_id'] in software_ids];cash_ids={x['round_id'] for x in rejections if x['decision'].endswith('cash_reserve')};sector_ids={x['round_id'] for x in rejections if x['decision'].endswith('sector_cap')}
summary={'status':'PASS_DIAGNOSTIC' if not errors else 'FAIL','certified_through':last,'independent_gate_checks':sum(checks.values()),'check_counts':dict(checks),'errors':errors,'zero_ADD_TRIAL_exit_rounds':len(rows),'rounds_prior_weak_ADD_gate_passed_but_capital_rejected':len(hit),'share_pct':str(D(len(hit))/D(len(rows))*100),'cash_rejected_rounds':len(cash_ids),'sector_rejected_rounds':len(sector_ids),'both_cash_and_sector_rounds':len(cash_ids&sector_ids),'prior_rejected_ADD_attempts':len(rejections),'prior_rejected_ADD_by_reason':dict(Counter(x['decision'] for x in rejections)),'hit_round_exit_qty':sum(x['exit_qty'] for x in hit),'hit_round_raw_OPEN_exit_value':str(sum((D(x['raw_OPEN_value_of_exited_qty']) for x in hit),D(0))),'hit_round_PNL_at_exit':str(sum((D(x['round_marked_PNL_at_exit']) for x in hit),D(0))),'software_old_oct8_rounds':len(software),'software_old_zero_ADD_TRIAL_exits':len(softtrial),'software_old_zero_ADD_with_prior_rejected_ADD':sum(x['weak_ADD_gate_ever_passed_but_never_funded'] for x in softtrial),'software_old_zero_ADD_prior_rejected_ADD_attempts':sum(x['prior_capital_rejected_ADDs'] for x in softtrial),'software_old_zero_ADD_exit_qty':sum(x['exit_qty'] for x in softtrial),'software_old_zero_ADD_raw_OPEN_exit_value':str(sum((D(x['raw_OPEN_value_of_exited_qty']) for x in softtrial),D(0))),'software_old_zero_ADD_last_close_value_before_exit':str(sum((D(x['last_close_MV_before_exit']) for x in softtrial),D(0))),'software_old_zero_ADD_net_sale_proceeds':str(sum((D(x['proxy_net_sale_proceeds']) for x in softtrial),D(0))),'software_old_zero_ADD_PNL_at_exit':str(sum((D(x['round_marked_PNL_at_exit']) for x in softtrial),D(0))),'software_old_mature_surviving_rounds':sum(x['actual_ADD_count']>0 and x['final_qty']>0 for x in software),'software_old_mature_final_qty':sum(x['final_qty'] for x in software if x['actual_ADD_count']>0),'software_old_mature_final_MV':str(sum((D(x['final_MV']) for x in software if x['actual_ADD_count']>0),D(0))),'limitations':['This is a descriptive join and independent arithmetic/source verification of actual frozen outputs, not a changed maturity rule or counterfactual return test.','Passing these gates means only the frozen weak net-profit/CP/sector conditions passed at those historical observations; it does not establish strong or durable trend evidence, real fillability, or profit-funded downside coverage.','By later exit, the sector was FALSE. Earlier evidence passing is not proof it remained valid at exit.','Maturity is defined in existing code as actual add_count>0; capital rejection keeps zero-ADD rounds exposed to TRIAL_SECTOR_FALSE. This establishes state coupling, not that changing it would improve performance.','Proceeds and contribution use the conditional OPEN cost ledger. They are not market-execution certification or opportunity-cost estimates.'],'source_hashes':{str(F/(k+'.json')):sha(F/(k+'.json')) for k in ['ORDERS','CANDIDATES','HOLDINGS','EQUITY_EVENTS','CP_EVENTS','ATTEMPTS','SECTOR_DAILY']}}
for name,value in [('EVIDENCE_VS_FUNDING_DIAGNOSTIC.json',summary),('EVIDENCE_VS_FUNDING_REJECTED_ADDS.json',detail),('SOFTWARE_OLD33_ROUNDS.json',software)]: (O/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
for name,rr in [('ZERO_ADD_TRIAL_EXIT_292.csv',rows),('SOFTWARE_OLD33_ROUNDS.csv',[{k:v for k,v in x.items() if k!='trial_exit_metrics'} for x in software])]:
 with (O/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
print(json.dumps({k:v for k,v in summary.items() if k not in ['source_hashes','check_counts']},ensure_ascii=False,indent=2))
assert not errors

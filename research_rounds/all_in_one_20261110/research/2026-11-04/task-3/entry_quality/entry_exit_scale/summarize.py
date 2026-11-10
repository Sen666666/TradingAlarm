"""Thin descriptive join of audited original-path fields; no new strategy."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
from itertools import product
import json, csv, hashlib
import numpy as np

getcontext().prec=60
O=Path(__file__).resolve().parent
A=O/'analysis_summary';A.mkdir(exist_ok=True)
SRC={};Z=D(0)
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(name,x):
 with (A/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def n(x):return D(str(x))
def money(rr):
 out={'layers':len(rr),'stocks':len({x['sid'] for x in rr})}
 for k in ['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']:
  out[k]=sum((n(x[k]) for x in rr),Z)
 out.update(negative_net=sum((min(Z,n(x['net'])) for x in rr),Z),positive_net=sum((max(Z,n(x['net'])) for x in rr),Z),negative_layers=sum(n(x['net'])<0 for x in rr),positive_layers=sum(n(x['net'])>0 for x in rr),open_layers=sum(bool(x['qty']) for x in rr))
 return out
FEATURES=['width_pct','gap_prior20close_pct','gap_prior20high_pct','r5_pct','r20_pct','decision_budget_pct_NAV','decision_cap_nominal_risk_pct_NAV','CP1_used_scale_over_current_z','CP1_freeze_to_decision_original_valid_observations','initial_width_over_current_z','held_close_observations','entry_to_primary_request_held_CLOSE_observations','peak_held_close_unrealized_per_own_buycash','comparable_price_MFE_ratio','calendar_days_to_actual_exit_or_cutoff']
def stats(rr):
 out={'money':money(rr),'features':{}}
 for k in FEATURES:
  v=[float(x[k]) for x in rr if x.get(k) is not None]
  out['features'][k]={'known':len(v),'unknown':len(rr)-len(v),'quantiles':None if not v else np.quantile(v,[0,.1,.25,.5,.75,.9,1]).tolist()}
 return out
def group(rr,cols):
 d=defaultdict(list)
 for x in rr:d[tuple(x[k] for k in cols)].append(x)
 return [{'labels':dict(zip(cols,k)),**stats(v)} for k,v in sorted(d.items(),key=lambda kv:str(kv[0]))]

rows={}
scale_keys=['initial_order_floor_binding','CP1_scale_role','CP1_used_scale','CP1_current_z','CP1_next_scale','CP1_used_scale_over_current_z','CP1_scale_frozen_at','CP1_freeze_to_decision_original_valid_observations','initial_log_distance_close_to_order_floor','initial_width_over_used_scale','initial_width_over_current_z']
hold_keys=['terminal_equity_state','actual_exit_class','actual_exit_reason_set','exit_family','holding_end_at','holding_end_kind','held_close_observations','calendar_days_to_actual_exit_or_cutoff','peak_held_close_unrealized_per_own_buycash','peak_held_close_wealth_per_own_buycash','held_close_peak_unrealized_state','comparable_price_MFE_ratio','signal_price_domain_comparable','held_close_peak_unrealized','held_close_peak_wealth']
request_keys=['primary_actual_order_id','primary_actual_order_request_at','actual_exit_at','entry_to_primary_request_held_CLOSE_observations','request_to_fill_native_session_steps','request_to_fill_intervening_CLOSE_observations','request_to_fill_calendar_days','actual_exit_is_next_native_session_OPEN','request_clock_status']
decision_keys=['window','layer','sid','name','industry','sector','role','action','decision_at','opened','closed','qty','cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee','width_pct','gap_prior20close_pct','gap_prior20high_pct','r5_pct','r20_pct','r5_span_calendar_days','r20_span_calendar_days','decision_budget_pct_NAV','decision_cap_nominal_risk_pct_NAV','break20close','r5_sign','r20_sign','width_pct_q','r5_pct_q','r20_pct_q','gap_prior20close_pct_q']
for ref in ['2022_2024','strong']:
 f=read(O/'decision_features'/(ref+'_ROWS.json'));h={x['layer']:x for x in read(O/'holding_exit'/(ref+'_LAYERS.json'))};s={x['layer']:x for x in read(O/'mechanism_review'/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json'))};r={x['layer']:x for x in read(O/'holding_exit'/(ref+'_REQUEST_CLOCK_JOIN.json'))}
 out=[]
 for x in f:
  hh,ss,rr=h[x['layer']],s[x['layer']],r[x['layer']]
  for y in [hh,ss,rr]:
   assert x['sid']==y['sid'] and x['action']==y['action']
  for k in ['decision_at','role']:assert x[k]==hh[k]==ss[k]
  for k in ['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']:assert abs(n(x[k])-n(hh[k]))<D('1e-18')
  assert n(x['cost'])==n(ss['original_cost']) and abs(n(x['net'])-n(ss['original_net']))<D('1e-18')
  assert x['opened']==rr['opened_at']==ss['actual_fill_at']
  assert bool(x['qty']) or hh['held_close_observations']==rr['entry_to_primary_request_held_CLOSE_observations']+rr['request_to_fill_intervening_CLOSE_observations']
  z={k:x[k] for k in decision_keys};z.update({k:hh[k] for k in hold_keys});z.update({k:ss[k] for k in scale_keys});z.update({k:rr[k] for k in request_keys})
  z['outcome_label']='negative' if n(z['net'])<0 else 'positive' if n(z['net'])>0 else 'zero'
  out.append(z)
 rows[ref]=out;save(ref+'_JOINED_ROWS.json',out)

scopes={'two_year':[x for x in rows['2022_2024'] if x['opened'][:10]<='2023-12-29'],'post303':[x for x in rows['2022_2024'] if x['opened'][:10]>'2024-10-08'],'post924_new320':[x for x in rows['2022_2024'] if x['opened'][:10]>='2024-09-24'],'strong':rows['strong']}
allsummary={}
for name,rr in scopes.items():
 allsummary[name]={'all':stats(rr),'action_outcome_terminal':group(rr,['action','outcome_label','terminal_equity_state']),'action_exit':group(rr,['action','actual_exit_class']),'binding_outcome':group(rr,['initial_order_floor_binding','outcome_label']),'role_outcome':group(rr,['role','outcome_label'])}
save('DISTRIBUTIONS.json',allsummary)

# Every frozen grid cell, including empty cells. These are descriptions, not fitted gates.
pairs={'width_r5':['width_pct_q','r5_pct_q'],'width_r20':['width_pct_q','r20_pct_q'],'break20_r20':['break20close','r20_pct_q']}
levels={'width_pct_q':['Q1','Q2','Q3','Q4','unknown'],'r5_pct_q':['Q1','Q2','Q3','Q4','unknown'],'r20_pct_q':['Q1','Q2','Q3','Q4','unknown'],'break20close':['above_prior20close','at_prior20close','below_prior20close','unknown']}
actions=sorted({x['action'] for rr in rows.values() for x in rr});roles=['core','mobile']
fullcells=[]
for name,rr in {'full_2022_2024':rows['2022_2024'],**scopes}.items():
 mother=money(rr)
 for pair,cols in pairs.items():
  buckets=defaultdict(list)
  for x in rr:buckets[tuple(x[k] for k in ['action','role']+cols)].append(x)
  for key in product(actions,roles,*[levels[k] for k in cols]):
   mm=money(buckets[key]);fullcells.append(dict(scope=name,pair=pair,**dict(zip(['action','role']+cols,key)),**mm,negative_money_share=mm['negative_net']/mother['negative_net'] if mother['negative_net'] else None,positive_money_share=mm['positive_net']/mother['positive_net'] if mother['positive_net'] else None))
cols=list(dict.fromkeys(k for x in fullcells for k in x))
with (A/'COMPLETE_PAIR_CELLS.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(fullcells)

# Normalize the actual negative and positive contributions within the same action/role.
# No counterfactual P&L is inferred. Include closed-strong separately to expose censoring.
overlap=[];cellcomparisons=[]
for weak in ['two_year','post303','post924_new320']:
 for strongstate in ['all_positive','closed_positive']:
  for action in ['ALL']+actions:
   for role in ['ALL']+roles:
    aa=[x for x in scopes[weak] if n(x['net'])<0 and (action=='ALL' or x['action']==action) and (role=='ALL' or x['role']==role)]
    bb=[x for x in scopes['strong'] if n(x['net'])>0 and (strongstate=='all_positive' or not x['qty']) and (action=='ALL' or x['action']==action) and (role=='ALL' or x['role']==role)]
    wa=-money(aa)['negative_net'];wb=money(bb)['positive_net']
    for pair,cc in pairs.items():
     ca=defaultdict(lambda:Z);cb=defaultdict(lambda:Z)
     for x in aa:ca[tuple(x[k] for k in cc)]-=n(x['net'])
     for x in bb:cb[tuple(x[k] for k in cc)]+=n(x['net'])
     ol=sum((min(ca[k]/wa,cb[k]/wb) for k in ca.keys()|cb.keys()),Z) if wa and wb else None
     overlap.append(dict(weak=weak,strongstate=strongstate,action=action,role=role,pair=pair,negative_money=wa,positive_money=wb,normalized_money_overlap=ol))
     if action=='ALL' and role=='ALL':
      for k in product(*[levels[c] for c in cc]):
       ar=[x for x in scopes[weak] if tuple(x[c] for c in cc)==k];br=[x for x in scopes['strong'] if tuple(x[c] for c in cc)==k and (strongstate=='all_positive' or not x['qty'])]
       cellcomparisons.append(dict(weak=weak,strongstate=strongstate,pair=pair,labels=dict(zip(cc,k)),weak_money=money(ar),strong_money=money(br),weak_negative_share=ca[k]/wa if wa else None,strong_positive_share=cb[k]/wb if wb else None))
save('MONEY_WEIGHTED_OVERLAP.json',overlap);save('ALL_CELL_COMPARISONS.json',cellcomparisons)

# Literal narrow-floor / hot-entry hypothesis, using the already frozen descriptive cuts.
literal={}
for name,rr in scopes.items():
 d={}
 for label,pred in [('tightest_width_Q1_hottest_r5_Q4',lambda x:x['width_pct_q']=='Q1' and x['r5_pct_q']=='Q4'),('tightest_width_Q1_hottest_r20_Q4',lambda x:x['width_pct_q']=='Q1' and x['r20_pct_q']=='Q4'),('tightest_width_Q1',lambda x:x['width_pct_q']=='Q1'),('hottest_r5_Q4',lambda x:x['r5_pct_q']=='Q4')]:
  sel=[x for x in rr if pred(x)];m=money(rr);a=stats(sel);a['negative_money_share']=a['money']['negative_net']/m['negative_net'];a['positive_money_share']=a['money']['positive_net']/m['positive_net'] if m['positive_net'] else None;a['by_action']=group(sel,['action']);d[label]=a
 literal[name]=d
save('LITERAL_HYPOTHESIS_DESCRIPTIVE.json',literal)

# Keep all 83/94 original controls and their exact original matching; never rematch layer numbers.
tails={}
for ref in rows:
 controls=read(O.parents[0]/'local_high'/(ref+'_FIXED_TAILS.json'));byid={x['layer']:x for x in rows[ref]};out=[]
 for t in controls:
  mm=[byid[x['layer']] for x in t['matched_actual_No60_rows']]
  out.append(dict(original=t['original'],unmatched=t['unmatched'],matched_rows=mm))
 tails[ref]=out
save('FIXED_ORIGINAL_TAILS.json',tails)
flat=[x for rr in rows.values() for x in rr];cols=[k for k,v in flat[0].items() if not isinstance(v,(dict,list))]
with (A/'ALL_ENTRY_EXIT_CONTEXT.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(flat)
save('JOIN_VALIDATION.json',dict(layers=len(flat),rows_by_ref={k:len(v) for k,v in rows.items()},financial_identity='all7 amount fields 1e-18, original cost/net exact; amounts never recomputed',clock_identity='all closed layers held CLOSE count equals entry→actually executed request held CLOSE count plus intervening CLOSEs until actual execution',complete_pair_rows=len(fullcells),unknown_input_context=0,new_accounts=0,new_models=0,sources=SRC,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
print('JOIN_DESCRIPTIVE_COMPLETE',len(flat),len(fullcells))

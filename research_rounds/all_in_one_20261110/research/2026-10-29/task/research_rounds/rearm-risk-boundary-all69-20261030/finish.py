"""Aggregate the single completed experiment; no signal/parameter or trading-path changes."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
from datetime import datetime,timezone
import csv,json,hashlib,statistics,time
T=time.monotonic();O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
def readcsv(p):return list(csv.DictReader(Path(p).open()))
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(name,x):
 with (O/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=readcsv(O/'full/unit-ledgers.csv');ix={(x['cycle_id'],x['cost'],x['arm']):x for x in rows};ids=list(dict.fromkeys(x['cycle_id'] for x in rows));assert len(ids)==69 and len(ix)==276
beh={x['cycle_id']:x for x in readcsv(O/'CASE_RESULTS.csv')};mother={x['cycle_id']:x for x in readcsv(O/'FROZEN_CASES.csv')};old={(x['cycle_id'],x['cost'],x['arm']):x for x in readcsv(W/'old-side-exit-all69-20261030/full/unit-ledgers.csv')};ex={(x['cycle_id'],x['cost']):x for x in readcsv(O/'full/exit-execution.csv')}
targets=['605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'];unknown=[k for k in ids if int(beh[k]['unknown_count'])]
def group(k):
 a=ix[k,'1','A'];return '3严重亏损' if k in targets else '38其他原亏损' if D(a['full_cycle_net'])<0 else '14原≥30%赢家' if a['original_tail30']=='True' else '14其他原盈利'
groups=['3严重亏损','38其他原亏损','14原≥30%赢家','14其他原盈利'];assert [sum(group(k)==g for k in ids) for g in groups]==[3,38,14,14]
def mechanism(k):
 b=beh[k]
 if b['added_request']:return '再次武装后新增退出' if int(b['rearm_count']) else '首段风险线延后退出'
 if mother[k]['triggered']=='False':return '无合规首警或原退出优先_动作同原账'
 if json.loads(b['handoff_dates']):return '安全移交后未新增退出_含后续未触线'
 return '未穿新增线_原退出先至'
def stat(v):return dict(net=sum(v,Z),improve=sum(x>0 for x in v),harm=sum(x<0 for x in v),same=sum(x==0 for x in v),positive=sum((x for x in v if x>0),Z),negative=sum((x for x in v if x<0),Z))
pairs=[]
for k in ids:
 for cost in ['1','2']:
  a,b=ix[k,cost,'A'],ix[k,cost,'B'];p=dict(cycle_id=k,symbol=a['symbol'],name=a['name'],cost=cost,group=group(k),conditional_missing=k in unknown,added_request=beh[k]['added_request'],first_known_warning=mother[k]['date'],rearm_count=beh[k]['rearm_count'],mechanism=mechanism(k),basis=D(a['initial_actual_cost']),A_net=D(a['full_cycle_net']),B_net=D(b['full_cycle_net']),B_minus_A=D(b['full_cycle_net'])-D(a['full_cycle_net']),A_return=D(a['full_cycle_net'])/D(a['initial_actual_cost']),B_return=D(b['full_cycle_net'])/D(b['initial_actual_cost']),A_fees=D(a['full_fees']),B_fees=D(b['full_fees']),A_dividend=D(a['dividend']),B_dividend=D(b['dividend']),B_first_sell=b['first_sell'],B_last_sell=b['last_sell'],B_sell_quantity=b['sold_quantity'],B_remaining_shares=b['final_shares'],A_min_return=D(a['min_full_cycle_return']),B_min_return=D(b['min_full_cycle_return']),A_local_DD=D(a['max_full_cycle_DD']),B_local_DD=D(b['max_full_cycle_DD']),old_single_negative_B=D(old[k,cost,'B']['full_cycle_net']),v2_minus_old_single_negative=D(b['full_cycle_net'])-D(old[k,cost,'B']['full_cycle_net']))
  assert p['A_net']==D(old[k,cost,'A']['full_cycle_net']);pairs.append(p)
export('cycle-differences.csv',pairs);group_rows=[];mechanism_rows=[];summary={}
for cost in ['1','2']:
 pp=[p for p in pairs if p['cost']==cost];s={}
 for label,kk in [('all69_conditional',ids),('known68_excluding_documented_missing', [k for k in ids if k not in unknown])]+[(g,[k for k in ids if group(k)==g]) for g in groups]:
  gg=[p for p in pp if p['cycle_id'] in kk];st=stat([p['B_minus_A'] for p in gg]);a=sum((p['A_net'] for p in gg),Z);b=sum((p['B_net'] for p in gg),Z);assert b-a==st['net'];s[label]=dict(cycles=len(gg),A=a,B=b,**st)
  group_rows.append(dict(cost=cost,group=label,cycles=len(gg),A_net=a,B_net=b,B_minus_A=st['net'],improve=st['improve'],harm=st['harm'],same=st['same'],gross_benefit=st['positive'],gross_harm=st['negative']))
 assert sum((s[g]['A'] for g in groups),Z)==s['all69_conditional']['A'];assert sum((s[g]['B'] for g in groups),Z)==s['all69_conditional']['B']
 for label in sorted(set(mechanism(k) for k in ids)):
  gg=[p for p in pp if p['mechanism']==label];mechanism_rows.append(dict(cost=cost,mechanism=label,cycles=len(gg),v2_minus_A=sum((p['B_minus_A'] for p in gg),Z),v2_minus_old_single_negative=sum((p['v2_minus_old_single_negative'] for p in gg),Z)))
 arms={}
 for arm in ['A','B']:
  rr=[ix[k,cost,arm] for k in ids];arms[arm]=dict(net=sum((D(x['full_cycle_net']) for x in rr),Z),all_negative_loss=-sum((D(x['full_cycle_net']) for x in rr if D(x['full_cycle_net'])<0),Z),positive_contribution=sum((D(x['full_cycle_net']) for x in rr if D(x['full_cycle_net'])>0),Z),positive_cycles=sum(D(x['full_cycle_net'])>0 for x in rr),negative_cycles=sum(D(x['full_cycle_net'])<0 for x in rr),full_fees=sum((D(x['full_fees']) for x in rr),Z),dividend=sum((D(x['dividend']) for x in rr),Z),mean_cycle_min_return=statistics.mean(D(x['min_full_cycle_return']) for x in rr),worst_cycle_min_return=min(D(x['min_full_cycle_return']) for x in rr),mean_cycle_max_DD=statistics.mean(D(x['max_full_cycle_DD']) for x in rr),worst_cycle_max_DD=max(D(x['max_full_cycle_DD']) for x in rr),holding_close_observations=sum(int(x['holding_close_observations']) for x in rr),unclosed=sum(int(x['final_shares'])>0 for x in rr))
 tail=[p for p in pp if p['group']==groups[2]];summary[cost]=dict(groups=s,arms=arms,old_single_negative_B=sum((p['old_single_negative_B'] for p in pp),Z),v2_minus_old_single_negative=sum((p['v2_minus_old_single_negative'] for p in pp),Z),tail_gross_truncated=-sum((p['B_minus_A'] for p in tail if p['B_minus_A']<0),Z),tail_improvements=sum((p['B_minus_A'] for p in tail if p['B_minus_A']>0),Z),tail_net_retained=sum((p['B_net'] for p in tail),Z)/sum((p['A_net'] for p in tail),Z),targets=[p for p in pp if p['cycle_id'] in targets],largest_harms=sorted(pp,key=lambda p:p['B_minus_A'])[:3],largest_benefits=sorted(pp,key=lambda p:p['B_minus_A'],reverse=True)[:3])
 assert sum((x['v2_minus_old_single_negative'] for x in mechanism_rows if x['cost']==cost),Z)==summary[cost]['v2_minus_old_single_negative']
export('group-summary.csv',group_rows);export('mechanism-accounting.csv',mechanism_rows)
# Descriptive first repair only: already stored original holding-day market facts, no signal recomputation.
exposure=readcsv(W/'down-event-transfer-exposure-20261030/all-holding-exposure-before-labels.csv');paths=readcsv(W/'act-loss-facts-20261030/actual-holding-close-paths.csv');path={(x['cycle_id'],x['day']):x for x in paths};repair=[]
for k in ids:
 b=beh[k];day=b['added_request']
 if not day:continue
 g=[x for x in exposure if x['cycle_id']==k and day<x['date']<b['original_request'][:10]];positive=[x for x in g if x['event']=='1.0' and x['e0_I_active']=='True' and x['ACT_on']=='True'];t=positive[0] if positive else None
 px=D(path[k,day]['causal_close']);warn=mother[k]['date'];wp=D(path[k,warn]['causal_close']);r=dict(cycle_id=k,name=ix[k,'1','A']['name'],new_request=day,first_postrequest_positive=t['date'] if t else '',postrequest_event_unknown=sum(x['event']=='' for x in g),T1_causal_close=path[k,t['date']]['causal_close'] if t else '',T1_vs_request=D(path[k,t['date']]['causal_close'])/px-1 if t else '',T1_vs_original_warning=D(path[k,t['date']]['causal_close'])/wp-1 if t else '',original_window_end=b['original_request'],B_minus_A=next(p['B_minus_A'] for p in pairs if p['cycle_id']==k and p['cost']=='1'),status='first_independent_positive_observed' if t else 'no_positive_observed_before_original_exit_request_not_permanent_failure')
 repair.append(r)
export('postrequest-first-repair.csv',repair)
save('RESULTS.json',dict(costs=summary,conditional_missing_cycles=unknown,behavior=dict(Counter(mechanism(k) for k in ids)),postrequest_repair=dict(cases=len(repair),with_first_positive=sum(bool(x['first_postrequest_positive']) for x in repair),harmed_cases_with_positive=sum(bool(x['first_postrequest_positive']) and x['B_minus_A']<0 for x in repair)),amount_unit='CNY',not_a_portfolio_profit=True))
assert summary['1']['arms']['A']['net']==D('2984160.2756603511085');assert summary['2']['arms']['A']['net']==D('2974920.4848282269060');assert all(int(ix[k,c,'B']['final_shares'])==0 for k in ids for c in ['1','2']);assert all(x['unknown']=='' for x in ex.values())
assert len(ex)==42 and all(x['sell_fill_count']=='1' and x['final_shares']=='0' for x in ex.values())
for f in ['FREEZE.json','ECONOMIC_FREEZE.json','INPUT_IDENTITY.json']:
 for p,h in json.loads((O/f).read_text())['sha256'].items():assert sha(p)==h,p
save('FINAL_VERIFICATION.json',dict(passed=True,cycles=69,paired_rows=138,unit_rows=276,groups=[3,38,14,14],A_original_normal_exact='2984160.2756603511085',A_original_cost2_exact='2974920.4848282269060',new_exit_cycles=21,simulated_exit_fills_two_costs=42,full_sell_fills=42,partial_or_unfilled=0,unknown_execution=0,known_behavior_missing_cycles=unknown,unknown_behavior_rows=3,missing_not_counted_as_no_trigger=True,no_holding_remaining_at_endpoint=True,all_input_hashes_unchanged=True,core_spec_unchanged=True,group_and_mechanism_sums_exact=True,finish_seconds=time.monotonic()-T))
print(json.dumps(dict(normal=summary['1']['groups']['all69_conditional'],cost2=summary['2']['groups']['all69_conditional'],mechanisms=dict(Counter(mechanism(k) for k in ids)),repair=repair),ensure_ascii=False,default=str),flush=True)

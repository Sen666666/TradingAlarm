"""Full484-day actual signal/admission chain. No alternative order or account."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import csv,gzip,json,statistics,gc
import analyze_phase as A
O=A.O
def percentile(values,p):
 if not values:return None
 s=sorted(values);return s[round((len(s)-1)*p)]
def main():
 dates,anchor,hs=A.load_inputs();_,legs,phase=A.zigzag([anchor]+dates,[hs[d]for d in [anchor]+dates]);prev={d:dates[i-1]for i,d in enumerate(dates)if i};nxt={d:dates[i+1]for i,d in enumerate(dates[:-1])}
 rulepath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=A.read(rulepath)
 all_daily={};all_periods=[];outcome_examples={};source={}
 for label,conf in A.CONFIG.items():
  rawbook=A.book(conf['native']/'B.json.gz');d={day:Counter()for day in dates};ranks={day:defaultdict(list)for day in dates};barrier_detail={day:Counter()for day in dates}
  for r in A.stream(conf['native']/'opportunities.jsonl.gz'):
   day=r['day'];c=d[day];c['all_stock_days']+=1;c['core_Q_true']+=r['core_Q']is True;c['mobile_Q_true']+=r['mobile_Q']is True
   cp=bool(r['CP1_id']);c['raw_fresh_CP1_stock_days']+=cp
   if cp:
    c['fresh_CP1_mobile_Q_true']+=r['mobile_Q']is True
    c['fresh_CP1_mobile_Q_not_true']+=r['mobile_Q']is not True
    if r['core_Q']is True and r['mobile_Q']is not True:c['CP1_Q_block_only_changed_market_buyability']+=1
    if r['mobile_Q']is not True:
     for b in r['barriers']:barrier_detail[day][b]+=1
   roles=r['roles'];c['eligible_role_events_before_barriers']+=len(roles);c['eligible_stock_days_before_barriers']+=bool(roles)
   bs=set(r['barriers']);gate='ACT_paused'if'ACT_paused'in bs else'exit_pending'if'exit_pending'in bs else'buy_pending'if'buy_pending'in bs else'other_barriers'if bs else'clear'
   for role in roles:c['eligible_'+role]+=1;c['role_barrier_'+gate]+=1;c[role+'_barrier_'+gate]+=1
  for day in dates:assert d[day]['all_stock_days']==1709
  # NextOPEN records may have2rows after a reservation(no execution window).
  opening=defaultdict(list)
  for r in A.stream(conf['native']/'funding.jsonl.gz'):
   day=r['at'][:10]
   if '15:10:00'in r['at']:
    d[day]['native_CLOSE_size_rejections']+=1;d[day]['CLOSE_reject|'+r['result']]+=1
   elif'09:30:00'in r['at']:
    opening[day,r['sid'],r['role']].append(r)
    d[day]['OPEN_log_rows']+=1
    if r['result']!='no_execution_window_after_reservation':d[day]['OPEN_result|'+r['result']]+=1
  buys=defaultdict(list);reserved={};actual_rows=[]
  for r in rawbook['journal']:
   if r['kind']=='real_buy_fill':buys[r['budget_order']].append(r)
   elif r['kind']=='real_reserve':reserved[r['budget_order']]=r
  for dec in rawbook['decisions']:
   day=dec['at'][:10];c=d[day];c['planned_role_intents']+=len(dec['intents']);c['planned_stock_days']+=len({i['sid']for i in dec['intents']})
   outcome=Counter()
   for i in dec['intents']:
    sid=i['sid'];role=i['role'];key='B|'+dec['at'].replace(' ','T')+'|'+sid+'|'+role;rank=i['priority_rank'];c['planned_'+role]+=1
    assert rank==i['rank'];rows=opening[nxt.get(day),sid,role]
    found=[r for r in rows if r['result']=='reserved'];fill=buys.get(key,[])
    if found:
     assert len(found)==1 and key in reserved
     k='funded_filled'if fill else'funded_zero_fill';ranks[day]['reserved_priority'].append(rank);c['planned_reserved_'+role]+=1
     if fill:
      openday=found[0]['at'][:10];versions=[v['rule']for v in rules['quantity_versions'][sid]if v['from']<=openday and(not v.get('to')or openday<v['to'])];assert len(versions)==1
      rule=versions[0];q=found[0]['shares'];assert q>=rule['buy_minimum']and(q-rule['buy_minimum'])%rule['buy_step']==0
      assert q<=i['cap']and D(q)*D(found[0]['price'])<=D(i['budget'])
      c['planned_filled_'+role]+=1;actual_rows.append(dict(policy=label,signal_day=day,OPEN_day=openday,sid=sid,role=role,priority=rank,
       original_H1_rank=i['original_H1_rank'],PVR_score=i['PVR_score'],frozen_budget=i['budget'],frozen_max_quantity=i['cap'],frozen_floor_adjusted=i['floor'],
       reserved_quantity=found[0]['shares'],reserved_pool=found[0]['pool'],actual_fills=fill,CP1_id=i.get('CP1_id'),
       legal_minimum_quantity=rule['buy_minimum'],legal_step=rule['buy_step'],reservation_original_target_and_unit_rechecked=True,
       factual_same_time_signal_legal_quantity_and_cash_admission_proof=True,execution_scope='existing native daily-bar proxy; external dated halt/limit fillability not independently verified',not_counterfactual_or_hindsight_trade=True))
    elif rows:
     assert not fill;k='OPEN_rejected';ranks[day]['rejected_priority'].append(rank)
     assert len(rows)==1
     c['planned_OPEN_reject|'+rows[0]['result']]+=1
     c['planned_OPEN_reject_role|'+role+'|'+rows[0]['result']]+=1
     for tag in rows[0]['result'].split(','):c['planned_reject_tag_presence|'+tag]+=1
    elif day not in nxt:k='terminal_next_OPEN_outside';assert not fill
    elif role=='mobile'and any(x['result']=='reserved'for x in opening[nxt[day],sid,'core']):k='same_stock_core_reserved_suppresses_mobile';assert not fill
    else:k='no_OPEN_record_unknown_pending_or_skip';assert not fill
    c['intent_outcome|'+k]+=1;outcome[k]+=1
   assert sum(outcome.values())==len(dec['intents'])
  for day in dates:
   c=d[day];c['clear_role_unplanned_unknown_quote_or_floor']=c['role_barrier_clear']-c['planned_role_intents']-c['native_CLOSE_size_rejections'];assert c['clear_role_unplanned_unknown_quote_or_floor']>=0
   assert sum(v for k,v in c.items()if k.startswith('intent_outcome|'))==c['planned_role_intents']
  policies=[]
  for grain,key in [('month',lambda x:x[:7]),('quarter',A.quarter),('HS300_zigzag10_leg',lambda x:phase[x])]:
   groups=defaultdict(list)
   for day in dates:groups[key(day)].append(day)
   for ident,days in groups.items():
    count=sum((d[day]for day in days),Counter());pr={k:sum((ranks[day].get(k,[])for day in days),[])for k in ['reserved_priority','rejected_priority']}
    row=dict(policy=label,grain=grain,period=ident,start=days[0],end=days[-1],days=len(days),counts=dict(count),
     priority=dict(reserved_median=statistics.median(pr['reserved_priority'])if pr['reserved_priority']else None,
      rejected_median=statistics.median(pr['rejected_priority'])if pr['rejected_priority']else None,
      reserved_top50=sum(x<=50 for x in pr['reserved_priority']),rejected_top50=sum(x<=50 for x in pr['rejected_priority'])),
     fresh_CP1_not_Q_raw_barrier_presence=dict(sum((barrier_detail[day]for day in days),Counter())),
     overlapping_reject_tags_not_exclusive_causes=True,clock='candidates/outcomes attributed to original signal CLOSE; OPEN_log_rows/results are actual OPEN-day counts, explicitly named')
    all_periods.append(row);policies.append(row)
  all_daily[label]=[dict(day=day,counts=dict(d[day]))for day in dates]
  A.save(label+'_ACTUAL_EXECUTABLE_FILLS.json',actual_rows)
  examples=[]
  for leg in legs:
   es=[r for r in actual_rows if leg['first_analysis_day']<=r['OPEN_day']<=leg['right']]
   examples.append(dict(leg=leg['id'],actual_filled_orders=len(es),earliest_actual_filled_orders=es[:5],
    lower_bound_of_existing_rule_executable_opportunities=True,not_all_raw_signals_are_executable=True))
  outcome_examples[label]=examples
  del rawbook;gc.collect()
 A.save('FUNNEL_ALL_PERIODS.json',all_periods);A.save('FUNNEL_DAILY.json',all_daily);A.save('PHASE_EXECUTABLE_LOWER_BOUND.json',outcome_examples)
 source.update(A.SRC);source[str(Path(__file__))]=A.sha(__file__);A.save('FUNNEL_SOURCE_SHA256.json',source)
 A.save('FUNNEL_GATE.json',dict(passed=True,policies=2,days_each=484,stock_days_each=1709*484,complete_months_each=24,complete_quarters_each=8,
  all_planned_role_intents_partitioned=True,clear_roles_bridged_to_size_or_plans_or_named_unknown=True,
  funding_and_fills_same_original_intent_or_terminal=True,actual_fills_used_only_as_factual_executable_lower_bound=True,
  no_account_constructed=True,new_policy_events=0,rank_changes=0,phase_labels_not_used_as_signal=True))
 for label in A.CONFIG:
  for x in [r for r in all_periods if r['policy']==label and r['grain']=='HS300_zigzag10_leg']:
   c=x['counts'];print(label,x['period'],'CP1',c.get('raw_fresh_CP1_stock_days'),'eligibleMobile',c.get('eligible_mobile'),'ACTblockRoles',c.get('role_barrier_ACT_paused',0),'plans',c.get('planned_role_intents'),'filled',c.get('intent_outcome|funded_filled',0),'coreSuppressed',c.get('intent_outcome|same_stock_core_reserved_suppresses_mobile',0),'rejects',c.get('intent_outcome|OPEN_rejected',0),flush=True)
if __name__=='__main__':main()

"""Final corrected-V11 saved-output analysis. No strategy import, Data or replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,csv,ast,sys
sys.dont_write_bytecode=True
import audit_saved_outputs as au
O=Path(__file__).resolve().parent;R=O.parent;C=R/'mainline_candidate_v11_structural_maturity_entry_execution_fix_v2';P=C/'once_20250120';B=R/'mainline_m7_cash_batch_design_v6/once_20260630';ANCHOR='2024-11-06';END='2025-01-20';Z=D(0)
read=au.read;sha=au.sha;save=au.save;sm=au.sm;near=au.near
result=read(O/'INDEPENDENT_V11_VS_M7.json');semantic=read(O/'STRICT_ENTRY_SEMANTICS.json');assert semantic['verdict']=='PASS_SAVED_ENTRY_SEMANTICS'
# Frozen runner and exact repaired input boundary.
ap=read(C/'EXPERIMENT_APPROVAL.json');fr=read(C/'FROZEN_INPUTS.json');qa=read(C/'SYNTHETIC_QA.json');types=read(C/'INPUT_TYPE_QA.json');status=read(C/'RUN_STATUS.json');started=read(C/'RUN_STARTED.json')
assert ap['approved'] and ap['one_shot'] and ap['end']==END and ap['initial_cash']=='1200000'
for p,h in ap['code_hashes'].items():assert sha(p)==h,('approved_source_drift',p)
assert fr['hashes']==read(P/'SOURCE_HASHES.json') and fr['code_hashes']==ap['code_hashes']
assert sha(C/'engine.py')==started['engine_sha256']==qa['engine_sha256']==types['engine_sha256']=='15c30e8b3eb3a6dfec5777febe33b1e161d5160057d75c13749f9f50e3384d4c'
assert sha(C/'shadow.py')==qa['shadow_sha256']==types['shadow_sha256']=='8714fec329c22a39cfd2962735fcc3e353de9ce5a9e283354de6c55a949a53ec'
assert ap['formula_design_sha256']==sha(R/'mainline_structural_maturity_design_v1/DESIGN.md')
assert status['result']=='COMPLETED' and status['days']==93 and not status['blockers'] and status['atomic_block'] is None and status['runtime_error'] is None
src=(C/'run_approved_once.py').read_text();ast.parse(src);assert 'data=m.Data()' in src and 'run_days=[d for d in data.days if m.day(d)<="2025-01-20"]' in src and src.count('pending=e.atomic_step(d,pending,prev)')==1
freeze=dict(verdict='PASS',engine_sha256=sha(C/'engine.py'),shadow_sha256=sha(C/'shadow.py'),runner_sha256=sha(C/'run_approved_once.py'),design_sha256=ap['formula_design_sha256'],approval_sha256=sha(C/'EXPERIMENT_APPROVAL.json'),frozen_input_sha256=sha(C/'FROZEN_INPUTS.json'),run_status_sha256=sha(C/'RUN_STATUS.json'),synthetic_groups=qa['passed_groups'],synthetic_assertions=qa['assertions'],real_boolean_regressions=types['assertions'],output_source_matches_frozen=True,unchanged_engine=True,only_input_boolean_compatibility_fix=True,old_v1='INVALID_IMPLEMENTATION, excluded from performance comparison',history_replayed_by_auditor=False)
save('RUNNER_FREEZE_REVIEW',freeze)
paths={'V11':P,'M7':B};records={};stock_at={};round_at={};ledgers={};all_dates={};dividends=[];name_map={};sector_map={}
for label,path in paths.items():
    os=read(path/'ORDERS.json');hs=read(path/'HOLDINGS.json');eq=read(path/'EQUITY_EVENTS.json');ls=read(path/'DAY_LEDGER.json');ledgers[label]={x['day']:x for x in ls};all_dates[label]=[x['day'] for x in ls]
    seeds={x['round_id']:x for x in os if x['side']=='BUY_SEED'};rk={rid:s['sid']+'|'+s['signal_day'] for rid,s in seeds.items()};record=dict(orders=os,holds=hs,equity=eq,seeds=seeds,rk=rk);records[label]=record
    for x in os:name_map[x['sid']]=x['name'];sector_map[x['sid']]=x['sector51']
    for day in [ANCHOR,END]:
        rr=defaultdict(lambda:Z);ss=defaultdict(lambda:Z)
        for x in os:
            if x['day']<=day:rr[rk[x['round_id']]]+=D(x['cash_delta']);ss[x['sid']]+=D(x['cash_delta'])
        for x in eq:
            if x['day']<=day and D(x.get('receivable_delta','0'))>0:rr[rk[x['round_id']]]+=D(x['receivable_delta']);ss[x['sid']]+=D(x['receivable_delta'])
        for x in hs:
            if x['day']==day:rr[rk[x['round_id']]]+=D(x['market_value']);ss[x['sid']]+=D(x['market_value'])
        near(sum(ss.values()),D(ledgers[label][day]['NAV'])-D(1200000),('stock_pnl',label,day));near(sum(rr.values()),sum(ss.values()),('round_pnl',label,day));stock_at[(label,day)]=ss;round_at[(label,day)]=rr
    # Check every admitted, locally described cash event, including missing-accrual negative space.
    terms=au.cash_event_terms(path);admitted={(x['sid'],x['ex_date']) for x in read(path/'EVENT_ADMISSION.json')}
    for (sid,ex),t in terms.items():
        if not '2024-09-02'<=ex<=END or (sid,ex) not in admitted:continue
        q=sum(x['qty'] for x in hs if x['sid']==sid and x['day']==t['record_date']);expected=D(q)*D(t['d_cash'])*D('.8')
        accrued=[x for x in eq if x['sid']==sid and x['day']==ex and x['event']=='ACCRUE_NET80'];near(sm(accrued,'receivable_delta'),expected,('all_admitted_cash_entitlement',label,sid,ex));assert sum(x['record_qty'] for x in accrued)==q
        paid=[x for x in eq if x['sid']==sid and x['day']==t['pay_date'] and x['event']=='PAY_CLOSE_NET80']
        if t['pay_date']<=END:near(sm(paid,'cash_delta'),expected,('all_admitted_cash_pay',label,sid,ex))
        dividends.append(dict(account=label,sid=sid,ex_date=ex,record_date=t['record_date'],pay_date=t['pay_date'],record_qty=q,expected_NET80=expected,actual_accrual=sm(accrued,'receivable_delta'),actual_paid=sm(paid,'cash_delta')))
save('ALL_ADMITTED_DIVIDEND_RECHECK',dividends)
# Temporal segment is separate from fixed baseline new-round cohorts.
segment={}
for label in paths:
    a=ledgers[label][ANCHOR];e=ledgers[label][END];pnl=D(e['NAV'])-D(a['NAV']);fees=D(e['fees_paid'])-D(a['fees_paid'])
    ss=records[label]['seeds'];keys_before={s['sid']+'|'+s['signal_day'] for s in ss.values() if s['day']<=ANCHOR};keys_after={s['sid']+'|'+s['signal_day'] for s in ss.values() if s['day']>ANCHOR}
    old_increment=sum((round_at[(label,END)].get(k,Z)-round_at[(label,ANCHOR)].get(k,Z) for k in keys_before),Z);new_net=sum((round_at[(label,END)].get(k,Z) for k in keys_after),Z);near(old_increment+new_net,pnl,('old_plus_new_late',label))
    segment[label]=dict(anchor_NAV=D(a['NAV']),end_NAV=D(e['NAV']),absolute_PnL=pnl,return_pct_own_anchor=100*pnl/D(a['NAV']),fees_paid_at_anchor=D(a['fees_paid']),fees_paid_at_end=D(e['fees_paid']),late_fees=fees,late_fee_added_back_PnL=pnl+fees,old_round_increment_after_anchor=old_increment,own_new_seed_rounds_after_anchor=len(keys_after),own_new_seed_rounds_whole_PnL=new_net)
segment['delta']=dict(lead_at_anchor=segment['V11']['anchor_NAV']-segment['M7']['anchor_NAV'],lead_at_end=segment['V11']['end_NAV']-segment['M7']['end_NAV'],late_absolute_PnL_improvement=segment['V11']['absolute_PnL']-segment['M7']['absolute_PnL'],late_return_pct_point_difference=segment['V11']['return_pct_own_anchor']-segment['M7']['return_pct_own_anchor'],fee_saving_to_anchor=segment['M7']['fees_paid_at_anchor']-segment['V11']['fees_paid_at_anchor'],late_fee_saving=segment['M7']['late_fees']-segment['V11']['late_fees'],late_fee_added_back_PnL_difference=segment['V11']['late_fee_added_back_PnL']-segment['M7']['late_fee_added_back_PnL'])
near(segment['delta']['lead_at_anchor']+segment['delta']['late_absolute_PnL_improvement'],result['delta']['NAV'],'temporal_delta_closure');segment['scope']='Absolute PnL anchored at actual 11/6 NAV; percentage returns each use their own NAV denominator. Fees are already charged, adding them back is a decomposition, never a new credit. This is not the fixed 954-opportunity cohort.'
save('NOV6_ANCHORED_ACCOUNT_SEGMENT',segment)
stockrows=[]
for sid in sorted(set(name_map)):
    va=stock_at[('V11',ANCHOR)].get(sid,Z);ba=stock_at[('M7',ANCHOR)].get(sid,Z);ve=stock_at[('V11',END)].get(sid,Z);be=stock_at[('M7',END)].get(sid,Z)
    stockrows.append(dict(sid=sid,name=name_map[sid],sector51=sector_map[sid],V11_anchor_PnL=va,M7_anchor_PnL=ba,delta_at_anchor=va-ba,V11_final_PnL=ve,M7_final_PnL=be,delta_at_end=ve-be,V11_after_anchor=ve-va,M7_after_anchor=be-ba,delta_after_anchor=(ve-va)-(be-ba)))
stockrows.sort(key=lambda x:x['delta_at_end'],reverse=True);near(sm(stockrows,'delta_at_anchor'),segment['delta']['lead_at_anchor'],'stock_anchor_delta');near(sm(stockrows,'delta_at_end'),result['delta']['NAV'],'stock_final_delta');save('ACTUAL_STOCK_CONTRIBUTIONS',stockrows)
# Complete actual cash order traces for the material gains and costs, not hypothetical WAIT returns.
focus=['000158.SZ','688660.SH','688503.SH','601336.SH','603063.SH','600094.SH','002261.SZ','300113.SZ','601865.SH']
traces=[]
for label,rec in records.items():
    for x in rec['orders']:
        if x['sid'] in focus:traces.append(dict(account=label,**x))
save('MATERIAL_STOCK_ACTUAL_ORDER_TRACES',traces)
b=read(O/'M7_COMMON_ROUNDS.json');c=read(O/'V11_ACTUAL_ROUNDS.json');bb={x['opportunity_key']:x for x in b};cc={x['opportunity_key']:x for x in c};cohorts=read(R/'mainline_tail_capture_baseline_v1/COHORT_OPPORTUNITY_MEMBERSHIP.json');group=defaultdict(list)
for x in cohorts:group[x['cohort']].append(x['opportunity_key'])
lossrows=[]
for name,keys in group.items():
    bs=[bb[k] for k in keys];loss=[x for x in bs if not x['open_at_cutoff'] and D(x['marked_net_pnl'])<0];matched=[x for x in loss if x['opportunity_key'] in cc];missed=[x for x in loss if x['opportunity_key'] not in cc];actual=[cc[x['opportunity_key']] for x in matched];closed=[x for x in matched if not cc[x['opportunity_key']]['open_at_cutoff']]
    lossrows.append(dict(cohort=name,baseline_negative_closed_count=len(loss),baseline_negative_closed_PnL=sm(loss,'marked_net_pnl'),same_identity_participated=len(matched),same_identity_baseline_PnL=sm(matched,'marked_net_pnl'),same_identity_candidate_actual_PnL=sm(actual,'marked_net_pnl'),same_identity_candidate_minus_baseline=sm(actual,'marked_net_pnl')-sm(matched,'marked_net_pnl'),candidate_still_open_count=sum(x['open_at_cutoff'] for x in actual),both_closed_count=len(closed),both_closed_baseline_PnL=sm(closed,'marked_net_pnl'),both_closed_candidate_PnL=sm([cc[x['opportunity_key']] for x in closed],'marked_net_pnl'),untraded_count=len(missed),untraded_baseline_PnL_reference_only=sm(missed,'marked_net_pnl'),label='Post-outcome loss labels, not known-at-entry false signals; untraded baseline losses are not earned candidate profits.'))
save('FIXED_NEGATIVE_ROUND_COMPARISON',lossrows)
# Identity-preserving attribution algebra, with actual money components shown separately.
matched_b=[x for x in b if x['opportunity_key'] in cc];matched_c=[x for x in c if x['opportunity_key'] in bb];missing_b=[x for x in b if x['opportunity_key'] not in cc];new=[x for x in c if x['opportunity_key'] not in bb]
attribution=dict(matched_count=len(matched_b),matched_baseline_PnL=sm(matched_b,'marked_net_pnl'),matched_candidate_PnL=sm(matched_c,'marked_net_pnl'),matched_actual_path_delta=sm(matched_c,'marked_net_pnl')-sm(matched_b,'marked_net_pnl'),unmatched_baseline_count=len(missing_b),unmatched_baseline_reference_PnL=sm(missing_b,'marked_net_pnl'),candidate_new_count=len(new),candidate_new_actual_PnL=sm(new,'marked_net_pnl'),candidate_new_closed=sum(not x['open_at_cutoff'] for x in new),candidate_new_open=sum(x['open_at_cutoff'] for x in new),candidate_new_closed_PnL=sm([x for x in new if not x['open_at_cutoff']],'marked_net_pnl'),candidate_new_open_PnL=sm([x for x in new if x['open_at_cutoff']],'marked_net_pnl'),NAV_delta=result['delta']['NAV'],warning='Reconciliation algebra only. Subtracting an unmatched baseline reference is not cash generated by a filter; actual redistribution, ADD and exit effects are in actual order PnL and account NAV.')
near(attribution['matched_actual_path_delta']-attribution['unmatched_baseline_reference_PnL']+attribution['candidate_new_actual_PnL'],result['delta']['NAV'],'opportunity_partition_delta');save('ACTUAL_ACCOUNT_ATTRIBUTION',attribution)
# Rich identity details: original lifecycle and post-seed CP / ADD timing.
original=read(O/'FIXED_OPPORTUNITY_COMPARISON.json');tickets=read(P/'TICKET_STATE.json');cpfirst={};infofirst={}
for label,path in paths.items():
    cps=read(path/'CP_EVENTS.json');ifs=read(path/'INFORMATION_CONFIRMATIONS.json');rk=records[label]['rk'];cpfirst[label]={};infofirst[label]={}
    for x in cps:
        if x['event']=='CREATED_AFTER_SEED':cpfirst[label].setdefault(rk[x['round_id']],x['day'])
    for x in ifs:
        if x['decision']=='INFORMATION_OPEN_CONFIRMED':infofirst[label].setdefault(rk[x['round_id']],x['day'])
for x in original:
    key=x['opportunity_key'];st=x.get('candidate_path_state');last=st.get('last_decision') if st else None;term=st.get('terminal') if st else None
    x['candidate_terminal_reason']=term.get('reason') if term else None;x['baseline_first_postseed_CP_CLOSE']=cpfirst['M7'].get(key);x['candidate_first_postseed_CP_CLOSE']=cpfirst['V11'].get(key)
    if not x['candidate_captured'] and last and x['candidate_status']=='BYPASS':x['candidate_interpreted_status']='ORIGINAL_PHASE_'+last['allocation_phase']
    elif not x['candidate_captured'] and x['candidate_status']=='READY':x['candidate_interpreted_status']='GATE_READY_BUT_NOT_FILLED'
    else:x['candidate_interpreted_status']=x['candidate_status']
    t=tickets.get(x['sid'])
    if t and t['signal_day']==x['baseline_original_signal']:x['candidate_final_ticket_status']=t['status'];x['candidate_final_ticket_reason']=t.get('reason')
save('FIXED_OPPORTUNITY_DETAILED',original)
notfilled=[x for x in original if not x['candidate_captured']];save('UNFILLED_FIXED_OPPORTUNITIES',notfilled)
# Requested 9/24 MATURE and 10/24 PV MATURE subgroups, using baseline actual OPEN and original identity.
bo=records['M7']['orders'];special=[]
for name,pred in [('SEP24_MATURE',lambda o:o['day']=='2024-09-24' and o.get('allocation_phase')=='MATURE'),('PV_OCT24_MATURE',lambda o:o['day']=='2024-10-24' and o['sector51']=='光伏风电设备' and o.get('allocation_phase')=='MATURE')]:
    ks={o['sid']+'|'+o['signal_day'] for o in bo if o['side']=='BUY_SEED' and pred(o)};rs=[x for x in original if x['opportunity_key'] in ks];special.append(dict(cohort=name,baseline_count=len(rs),candidate_captured=sum(x['candidate_captured'] for x in rs),delayed=sum(x.get('delay_trading_sessions',0)>0 for x in rs),same_day=sum(x.get('delay_trading_sessions')==0 for x in rs),baseline_PnL=sm(rs,'baseline_common_pnl'),candidate_actual_PnL=sm(rs,'candidate_actual_pnl'),miss_reason_counts=dict(Counter(x['candidate_terminal_reason'] or x['candidate_interpreted_status'] for x in rs if not x['candidate_captured']))))
save('FIXED_MATURE_OPEN_SUBGROUPS',special)
# 605499 now follows original guarded path. Do not infer the old guard was changed.
sid='605499.SH';q0=dict(ticket_events=[x for x in read(P/'RETRY_TICKETS.json') if x['sid']==sid and x['day']<='2024-10-09'],equity_events=[x for x in read(P/'EQUITY_EVENTS.json') if x['sid']==sid and x['day']<='2024-10-09'],orders=[x for x in records['V11']['orders'] if x['sid']==sid and x['day']<='2024-10-09'],guard_source_sha256=sha(R/'mainline_m7_downturn_q0_split_v3/engine.py'))
assert not q0['orders'] and any(x['event']=='Q0_SPLIT_BRIDGE_VERIFIED_NO_ENTITLEMENT' for x in q0['equity_events']);save('Q0_605499_UNCHANGED_GUARD_PATH',q0)
result['verdict']='PASS_ACCOUNTING_AND_SAVED_ENTRY_SEMANTICS';result['accounting_verdict']='PASS';result['semantics_verdict']='PASS';result['semantic_audit']=dict(artifact='STRICT_ENTRY_SEMANTICS.json',sha256=sha(O/'STRICT_ENTRY_SEMANTICS.json'),checks=semantic['checks'],routes=semantic['route_counts']);result['runner_freeze_review']=freeze;result['nov6_segment']=segment;result['actual_opportunity_attribution']=attribution;result['fixed_negative_rounds']=lossrows;result['special_fixed_mature_subgroups']=special
result['limits'].insert(0,'Only corrected execution_fix_v2 is performance-evaluable. Old execution has INVALID_IMPLEMENTATION and is never pooled with this run.')
result['limits'].append('Whole-account lead was already 21,994.659037 by Nov6; Nov7-Jan20 improves absolute PnL only 509.255349 despite 3,224.066919 lower fees. The fixed 954-opportunity cohort is not the same as the temporal account segment.')
save('INDEPENDENT_V11_VS_M7',result)
print(json.dumps(dict(verdict=result['verdict'],segment=segment,attribution=attribution,special=special,dividend_rows_verified=len(dividends),lossrows=lossrows),ensure_ascii=False,default=str))

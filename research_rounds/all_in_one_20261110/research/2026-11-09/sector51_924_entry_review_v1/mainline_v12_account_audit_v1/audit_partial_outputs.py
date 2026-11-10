"""Audit a certified, atomically blocked M12 prefix. Saved JSON only."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import ast,importlib.util,json,sys
sys.dont_write_bytecode=True
import accounting_core as au
from audit_saved_outputs import states
O=Path(__file__).resolve().parent;R=O.parent;C=R/'mainline_candidate_v12_winner_funding_competition';P=C/'once_20250120';B=au.BASE;Z=D(0)
read=au.read;sha=au.sha;save=au.save;sm=au.sm;near=au.near
def main():
    status=read(C/'RUN_STATUS.json');end=status['last']['day']
    assert status['result']=='ATOMIC_BLOCK' and status['runtime_error'] is None and status['atomic_block']['atomic_rollback'] is True
    assert status['days']==22 and status['orders']==664 and end=='2024-10-10'
    assert sha(au.HELPER)=='928c7af9608badf81285d41bdad1bc85d9998cbb0779673ec025c8ebb0cf3339'
    spec=importlib.util.spec_from_file_location('independent_saved_account_helper',au.HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    a,ar=au.account(P,end,helper);b,br=au.account(B,end,helper)
    assert read(P/'DAY_LEDGER.json')[-1]==status['last']
    near(a['NAV'],status['last']['NAV'],'actual_run_status_NAV')
    assert [x['day'] for x in read(P/'DAY_LEDGER.json')]==[x['day'] for x in read(B/'DAY_LEDGER.json') if x['day']<=end]
    rows,cohorts,new,winners=au.compare(br,ar,end,states(P));bb={x['opportunity_key']:x for x in br};cc={x['opportunity_key']:x for x in ar};rr={x['opportunity_key']:x for x in rows}
    for n,v in [('M7_COMMON_ROUNDS',br),('M12_ACTUAL_ROUNDS',ar),('FIXED_OPPORTUNITY_COMPARISON',rows),('FIXED_COHORT_SUMMARY',cohorts),('CANDIDATE_NEW_OPPORTUNITIES',new),('FIXED_WINNER_COMPARISON',winners),('CANDIDATE_OPEN_ROUNDS',[x for x in ar if x['open_at_cutoff']])]:save(n,v)
    delta={k:a[k]-b[k] for k in ('NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct')};delta['fees']=a['trading']['fees']-b['trading']['fees']
    delta['mean_close_exposure_pct']=a['exposure_stats']['mean_close_weight_pct']-b['exposure_stats']['mean_close_weight_pct']
    special=[]
    os=read(B/'ORDERS.json')
    groups=[dict(name='SEP24_MATURE',keys=[x['sid']+'|'+x['signal_day'] for x in os if x['day']=='2024-09-24' and x['side']=='BUY_SEED' and x.get('allocation_phase')=='MATURE'])]
    groups+=read(O/'FIXED_SPECIAL_OPPORTUNITIES.json')
    for g in groups:
        keys=[k for k in g['keys'] if k in bb];rs=[rr[k] for k in keys];cs=[cc[k] for k in keys if k in cc];miss=[bb[k] for k in keys if k not in cc]
        special.append(dict(name=g['name'],fixed_count=len(g['keys']),baseline_reached=len(keys),captured=len(cs),same_day=sum(x.get('delay_trading_sessions')==0 for x in rs),delayed=sum(x.get('delay_trading_sessions',0)>0 for x in rs),not_captured=len(miss),baseline_common_PnL=sm([bb[k] for k in keys],'marked_net_pnl'),candidate_actual_PnL=sm(cs,'marked_net_pnl'),missed_baseline_common_PnL_reference_only=sm(miss,'marked_net_pnl'),candidate_ADD_orders=sum(x['add_count'] for x in cs),baseline_ADD_orders=sum(bb[k]['add_count'] for k in keys),candidate_open=sum(x['open_at_cutoff'] for x in cs),rows=rs))
    save('FIXED_MATURE_OPPORTUNITY_COSTS',special)
    startup='SEPT_STARTUP_SEED_OPEN_0923_0930';strong=[x for x in winners if x['cohort']==startup and x['fixed_in_top_decile']]
    assert len(strong)==19
    save('STARTUP_19_STRONG_WINNER_PATHS',strong)
    matched=[k for k in bb if k in cc];miss=[k for k in bb if k not in cc];extra=[k for k in cc if k not in bb]
    attribution=dict(matched_count=len(matched),matched_baseline_PnL=sm([bb[k] for k in matched],'marked_net_pnl'),matched_candidate_PnL=sm([cc[k] for k in matched],'marked_net_pnl'),matched_actual_path_delta=sm([cc[k] for k in matched],'marked_net_pnl')-sm([bb[k] for k in matched],'marked_net_pnl'),unmatched_baseline_count=len(miss),unmatched_baseline_reference_PnL=sm([bb[k] for k in miss],'marked_net_pnl'),candidate_new_count=len(extra),candidate_new_actual_PnL=sm([cc[k] for k in extra],'marked_net_pnl'),warning='All PnL at certified Oct10 mark. Missing baseline PnL is a reference-only term, not candidate earnings.')
    near(attribution['matched_actual_path_delta']-attribution['unmatched_baseline_reference_PnL']+attribution['candidate_new_actual_PnL'],delta['NAV'],'identity_partition')
    save('ACTUAL_ACCOUNT_ATTRIBUTION',attribution)
    waits=read(P/'FUNDING_WAIT_LOG.json');unique_wait={x['original_request']['sid']+'|'+x['original_request']['signal_day'] for x in waits}
    wait_summary=dict(events=len(waits),unique_original_opportunities=len(unique_wait),outcomes=dict(Counter(x['reason'] for x in waits)),eventually_filled_by_end=sum(k in cc for k in unique_wait),eventually_filled_actual_PnL=sm([cc[k] for k in unique_wait if k in cc],'marked_net_pnl'),never_filled_by_end=sum(k not in cc for k in unique_wait))
    save('ACTUAL_WAIT_SUMMARY',wait_summary)
    stockrows=[];stockp={}
    for label,rs in [('M12',ar),('M7',br)]:
        groups=au.bykey(rs,'sid');stockp[label]={k:sm(v,'marked_net_pnl') for k,v in groups.items()}
    names={x['sid']:x['name'] for x in ar+br}
    for sid in sorted(set(stockp['M12'])|set(stockp['M7'])):
        av=stockp['M12'].get(sid,Z);bv=stockp['M7'].get(sid,Z);stockrows.append(dict(sid=sid,name=names[sid],M12_PnL=av,M7_PnL=bv,actual_path_delta=av-bv))
    stockrows.sort(key=lambda x:x['actual_path_delta'],reverse=True);near(sm(stockrows,'actual_path_delta'),delta['NAV'],'stock_delta');save('ACTUAL_STOCK_CONTRIBUTIONS',stockrows)
    fund={}
    for label,path in [('M12',P),('M7',B)]:
        tt=[x for x in read(path/'TRANSFERS.json') if x['day']<=end and x.get('event')=='DONOR_EXECUTION'];oo=[x for x in read(path/'ORDERS.json') if x['day']<=end]
        donororders=[x for x in oo if x.get('transfer_rank') is not None]
        fund[label]=dict(planned_execution_records=len(tt),positive_executed_lots=sum(x['executed_q']>0 for x in tt),actual_donor_orders=len(donororders),actual_funding_net=sm(donororders,'cash_delta'),actual_funding_fees=sm(donororders,'fee'),all_actual_buy_cost=-sm([x for x in oo if x['side'].startswith('BUY')],'cash_delta'),actual_ADD_buy_cost=-sm([x for x in oo if x['side']=='BUY_ADD'],'cash_delta'))
    save('ACTUAL_FUNDING_SUMMARY',fund)
    blocked=read(P/'UNCERTIFIED_DAY.json');assert blocked==status['atomic_block']
    scans=read(P/'ALL_TARGETS_BLOCKER_SCAN.json');assert all(x['day']==blocked['day'] for x in scans)
    evidence=dict(run_status=status,uncertified=blocked,restored_688200=[x for x in scans if x.get('sid')=='688200.SH'],orders_688200=[dict(account=label,**x) for label,path in [('M12',P),('M7',B)] for x in read(path/'ORDERS.json') if x['sid']=='688200.SH' and x['day']<=blocked['day']],last_holdings_688200=[dict(account=label,**x) for label,path in [('M12',P),('M7',B)] for x in read(path/'HOLDINGS.json') if x['sid']=='688200.SH' and x['day']==end],last_CAPITAL_LOTS_688200=[x for x in read(P/'CAPITAL_LOTS.json') if x['sid']=='688200.SH' and x['day']==end])
    save('ATOMIC_BLOCK_688200_SAVED_PATH',evidence)
    result=dict(verdict='PASS_PREFIX_ACCOUNTING_PENDING_BRANCH_AUDIT',accounting_verdict='PASS',common_end=end,days=22,target_end='2025-01-20',target_complete=False,certified_frontier_only=True,candidate_output=str(P),run_status=status,M12=a,M7=b,delta=delta,cohorts=cohorts,special_fixed_groups=[{k:v for k,v in x.items() if k!='rows'} for x in special],fixed_19_strong_summary=dict(captured=sum(x['candidate_captured'] for x in strong),not_captured=sum(not x['candidate_captured'] for x in strong),baseline_common_PnL=sm(strong,'baseline_common_pnl'),candidate_actual_PnL=sm(strong,'candidate_actual_pnl')),actual_attribution=attribution,waits=wait_summary,funding=fund,not_available=['Nov6 anchored late account PnL','PV Oct23-Oct29 fixed window','Original late 954 cohort','Dec5 robot boundary','Jan20 terminal NAV/full-window economic judgment'],limits=['Only certified Sep2-Oct10 prefix. Atomic-blocked day has no certified orders or NAV.','Original Jan20 winner/loser labels are fixed evaluation labels only; all compared cash PnL is recomputed at Oct10.','Mature same-day health funding group is not directed funding or a causal attribution.','No-funding Sep24 is not an exemption from ADD/EVENT q lower bounds.','Original full-day no_fill and non-PIT input limitations remain.'])
    save('INDEPENDENT_M12_VS_M7_PREFIX',result)
    print(json.dumps(dict(end=end,accounting='PASS',delta=delta,M12=a,M7=b,cohorts=cohorts,special=result['special_fixed_groups'],strong=result['fixed_19_strong_summary'],waits=wait_summary,funding=fund),ensure_ascii=False,default=str))
    # Manifest integrity includes 7 GB book streaming SHA, never loading it as JSON.
    hashes={'M12':au.verify_hashes(P),'M7':au.verify_hashes(B)}
    ap=read(C/'EXPERIMENT_APPROVAL.json');fr=read(C/'FROZEN_INPUTS.json')
    assert fr['hashes']==read(P/'SOURCE_HASHES.json') and fr['code_hashes']==ap['code_hashes']
    for p,h in ap['code_hashes'].items():assert sha(p)==h
    baseline_sources=read(B/'SOURCE_HASHES.json');candidate_sources=read(P/'SOURCE_HASHES.json')
    for p,h in baseline_sources.items():assert candidate_sources.get(p)==h,('original_M7_source_changed',p)
    assert read(P/'EVENT_ADMISSION.json')==read(B/'EVENT_ADMISSION.json')
    result['hashes']=hashes;result['frozen_inputs_match']=True;save('INDEPENDENT_M12_VS_M7_PREFIX',result)
    print('PREFIX_OUTPUT_SOURCE_MANIFESTS_PASS',flush=True)
if __name__=='__main__':main()

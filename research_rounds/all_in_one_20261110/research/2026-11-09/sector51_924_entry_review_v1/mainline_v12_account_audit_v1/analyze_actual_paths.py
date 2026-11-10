"""Independent money/cohort attribution from saved accounts only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import accounting_core as au
O=Path(__file__).resolve().parent;R=O.parent;B=au.BASE;ANCHOR='2024-11-06';END='2025-01-20';Z=D(0)
read=au.read;sha=au.sha;save=au.save;sm=au.sm;near=au.near

def analyze(candidate,result,base_rounds,candidate_rounds):
    paths={'M12':candidate,'M7':B};records={};ledgers={};stock_at={};round_at={};dividends=[];name_map={};sector_map={}
    for label,path in paths.items():
        os=read(path/'ORDERS.json');hs=read(path/'HOLDINGS.json');eq=read(path/'EQUITY_EVENTS.json');ls=read(path/'DAY_LEDGER.json')
        ledgers[label]={x['day']:x for x in ls};seeds={x['round_id']:x for x in os if x['side']=='BUY_SEED'}
        rk={rid:s['sid']+'|'+s['signal_day'] for rid,s in seeds.items()}
        records[label]=dict(orders=os,holds=hs,equity=eq,seeds=seeds,rk=rk)
        buys={x['lot_id']:x for x in os if x['side'].startswith('BUY')}
        for x in buys.values():
            expected='INITIAL' if x['side']=='BUY_SEED' and x.get('allocation_phase') in ('EVENT','RESIDUAL') else 'EXPANSION'
            assert x['capital_role']==expected,('original_M5_acquisition_role',label,x['order_seq'])
        for x in read(path/'CAPITAL_LOTS.json'):
            assert x['capital_role']==buys[x['lot_id']]['capital_role'],('role_changed_after_acquisition',label,x['lot_id'],x['day'])
        for x in os:name_map[x['sid']]=x['name'];sector_map[x['sid']]=x['sector51']
        for day in (ANCHOR,END):
            rr=defaultdict(lambda:Z);ss=defaultdict(lambda:Z)
            for x in os:
                if x['day']<=day:rr[rk[x['round_id']]]+=D(x['cash_delta']);ss[x['sid']]+=D(x['cash_delta'])
            for x in eq:
                if x['day']<=day and D(x.get('receivable_delta','0'))>0:rr[rk[x['round_id']]]+=D(x['receivable_delta']);ss[x['sid']]+=D(x['receivable_delta'])
            for x in hs:
                if x['day']==day:rr[rk[x['round_id']]]+=D(x['market_value']);ss[x['sid']]+=D(x['market_value'])
            near(sum(ss.values()),D(ledgers[label][day]['NAV'])-D(1200000),('stock_pnl',label,day))
            near(sum(rr.values()),sum(ss.values()),('round_pnl',label,day))
            stock_at[label,day]=ss;round_at[label,day]=rr
        terms=au.cash_event_terms(path);admitted={(x['sid'],x['ex_date']) for x in read(path/'EVENT_ADMISSION.json')}
        for (sid,ex),t in terms.items():
            if not '2024-09-02'<=ex<=END or (sid,ex) not in admitted:continue
            q=sum(x['qty'] for x in hs if x['sid']==sid and x['day']==t['record_date']);expected=D(q)*D(t['d_cash'])*D('.8')
            accrued=[x for x in eq if x['sid']==sid and x['day']==ex and x['event']=='ACCRUE_NET80']
            near(sm(accrued,'receivable_delta'),expected,('all_admitted_cash_entitlement',label,sid,ex));assert sum(x['record_qty'] for x in accrued)==q
            paid=[x for x in eq if x['sid']==sid and x['day']==t['pay_date'] and x['event']=='PAY_CLOSE_NET80']
            if t['pay_date']<=END:near(sm(paid,'cash_delta'),expected,('all_admitted_cash_pay',label,sid,ex))
            dividends.append(dict(account=label,sid=sid,ex_date=ex,record_date=t['record_date'],pay_date=t['pay_date'],record_qty=q,expected_NET80=expected,actual_accrual=sm(accrued,'receivable_delta'),actual_paid=sm(paid,'cash_delta')))
    assert Counter(x['account'] for x in dividends)=={'M7':267,'M12':267},'all_534_account_cash_action_checks_required'
    save('ALL_ADMITTED_DIVIDEND_RECHECK',dividends)
    segment={}
    for label in paths:
        a=ledgers[label][ANCHOR];e=ledgers[label][END];pnl=D(e['NAV'])-D(a['NAV']);fees=D(e['fees_paid'])-D(a['fees_paid'])
        seeds=records[label]['seeds'];before={s['sid']+'|'+s['signal_day'] for s in seeds.values() if s['day']<=ANCHOR};after={s['sid']+'|'+s['signal_day'] for s in seeds.values() if s['day']>ANCHOR}
        old=sum((round_at[label,END].get(k,Z)-round_at[label,ANCHOR].get(k,Z) for k in before),Z);new=sum((round_at[label,END].get(k,Z) for k in after),Z)
        near(old+new,pnl,('late_old_plus_new',label))
        segment[label]=dict(anchor_NAV=D(a['NAV']),end_NAV=D(e['NAV']),absolute_PnL=pnl,return_pct_own_anchor=100*pnl/D(a['NAV']),fees_paid_at_anchor=D(a['fees_paid']),fees_paid_at_end=D(e['fees_paid']),late_fees=fees,late_fee_added_back_PnL=pnl+fees,old_round_increment_after_anchor=old,own_new_seed_rounds_after_anchor=len(after),own_new_seed_rounds_whole_PnL=new)
    near(segment['M7']['absolute_PnL'],'-204229.2637350250050','known_original_M7_late')
    segment['delta']=dict(lead_at_anchor=segment['M12']['anchor_NAV']-segment['M7']['anchor_NAV'],lead_at_end=segment['M12']['end_NAV']-segment['M7']['end_NAV'],late_absolute_PnL_improvement=segment['M12']['absolute_PnL']-segment['M7']['absolute_PnL'],late_return_pct_point_difference=segment['M12']['return_pct_own_anchor']-segment['M7']['return_pct_own_anchor'],late_fee_saving=segment['M7']['late_fees']-segment['M12']['late_fees'],late_fee_added_back_PnL_difference=segment['M12']['late_fee_added_back_PnL']-segment['M7']['late_fee_added_back_PnL'])
    near(segment['delta']['lead_at_anchor']+segment['delta']['late_absolute_PnL_improvement'],result['delta']['NAV'],'temporal_delta_closure')
    segment['scope']='Actual cash/claims/mark PnL from own Nov6 NAV; not the fixed 954 baseline opportunity cohort. Fee addback is only decomposition.'
    save('NOV6_ANCHORED_ACCOUNT_SEGMENT',segment)
    stocks=[]
    for sid in sorted(name_map):
        ca=stock_at['M12',ANCHOR].get(sid,Z);ba=stock_at['M7',ANCHOR].get(sid,Z);ce=stock_at['M12',END].get(sid,Z);be=stock_at['M7',END].get(sid,Z)
        stocks.append(dict(sid=sid,name=name_map[sid],sector51=sector_map[sid],M12_anchor_PnL=ca,M7_anchor_PnL=ba,delta_at_anchor=ca-ba,M12_final_PnL=ce,M7_final_PnL=be,delta_at_end=ce-be,M12_after_anchor=ce-ca,M7_after_anchor=be-ba,delta_after_anchor=(ce-ca)-(be-ba)))
    stocks.sort(key=lambda x:x['delta_at_end'],reverse=True);near(sm(stocks,'delta_at_end'),result['delta']['NAV'],'stock_final_delta');save('ACTUAL_STOCK_CONTRIBUTIONS',stocks)
    b={x['opportunity_key']:x for x in base_rounds};c={x['opportunity_key']:x for x in candidate_rounds}
    matched_b=[x for k,x in b.items() if k in c];matched_c=[c[x['opportunity_key']] for x in matched_b];miss=[x for k,x in b.items() if k not in c];new=[x for k,x in c.items() if k not in b]
    attribution=dict(matched_count=len(matched_b),matched_baseline_PnL=sm(matched_b,'marked_net_pnl'),matched_candidate_PnL=sm(matched_c,'marked_net_pnl'),matched_actual_path_delta=sm(matched_c,'marked_net_pnl')-sm(matched_b,'marked_net_pnl'),unmatched_baseline_count=len(miss),unmatched_baseline_reference_PnL=sm(miss,'marked_net_pnl'),candidate_new_count=len(new),candidate_new_actual_PnL=sm(new,'marked_net_pnl'),candidate_new_closed=sum(not x['open_at_cutoff'] for x in new),candidate_new_open=sum(x['open_at_cutoff'] for x in new),candidate_new_closed_PnL=sm([x for x in new if not x['open_at_cutoff']],'marked_net_pnl'),candidate_new_open_PnL=sm([x for x in new if x['open_at_cutoff']],'marked_net_pnl'),NAV_delta=result['delta']['NAV'],warning='Reconciliation algebra, not a credit for filtered losses; only candidate actual orders and holdings generate its PnL.')
    near(attribution['matched_actual_path_delta']-attribution['unmatched_baseline_reference_PnL']+attribution['candidate_new_actual_PnL'],result['delta']['NAV'],'partition_delta');save('ACTUAL_ACCOUNT_ATTRIBUTION',attribution)
    group=au.bykey(read(au.TAIL/'COHORT_OPPORTUNITY_MEMBERSHIP.json'),'cohort');lossrows=[]
    for name,members in group.items():
        bs=[b[x['opportunity_key']] for x in members];loss=[x for x in bs if not x['open_at_cutoff'] and D(x['marked_net_pnl'])<0];matched=[x for x in loss if x['opportunity_key'] in c];missed=[x for x in loss if x['opportunity_key'] not in c];actual=[c[x['opportunity_key']] for x in matched]
        lossrows.append(dict(cohort=name,baseline_negative_closed_count=len(loss),baseline_negative_closed_PnL=sm(loss,'marked_net_pnl'),same_identity_participated=len(matched),same_identity_baseline_PnL=sm(matched,'marked_net_pnl'),same_identity_candidate_actual_PnL=sm(actual,'marked_net_pnl'),same_identity_candidate_minus_baseline=sm(actual,'marked_net_pnl')-sm(matched,'marked_net_pnl'),candidate_still_open_count=sum(x['open_at_cutoff'] for x in actual),untraded_count=len(missed),untraded_baseline_PnL_reference_only=sm(missed,'marked_net_pnl'),label='Post-outcome loss labels; untraded baseline losses are not candidate earned profits.'))
    save('FIXED_NEGATIVE_ROUND_COMPARISON',lossrows)
    # Preserve original identity through all cohort and missed-opportunity outputs.
    rows=read(O/'FIXED_OPPORTUNITY_COMPARISON.json');byrow={x['opportunity_key']:x for x in rows};cpfirst={};infofirst={}
    for label,path in paths.items():
        rk=records[label]['rk'];cpfirst[label]={};infofirst[label]={}
        for x in read(path/'CP_EVENTS.json'):
            if x['event']=='CREATED_AFTER_SEED':cpfirst[label].setdefault(rk[x['round_id']],x['day'])
        for x in read(path/'INFORMATION_CONFIRMATIONS.json'):
            if x['decision']=='INFORMATION_CONFIRMED':infofirst[label].setdefault(rk[x['round_id']],x['day'])
    for x in rows:
        k=x['opportunity_key'];x['baseline_first_postseed_CP_CLOSE']=cpfirst['M7'].get(k);x['candidate_first_postseed_CP_CLOSE']=cpfirst['M12'].get(k);x['baseline_first_information_OPEN']=infofirst['M7'].get(k);x['candidate_first_information_OPEN']=infofirst['M12'].get(k)
        x['baseline_full_round']=b[k];x['candidate_full_round']=c.get(k)
    save('FIXED_OPPORTUNITY_DETAILED',rows);save('UNFILLED_FIXED_OPPORTUNITIES',[x for x in rows if not x['candidate_captured']])
    # Explicit profitable displaced-entry opportunity costs, not only unhealthy losers.
    bo=records['M7']['orders'];special=[]
    predicates=[('SEP24_MATURE',lambda o:o['day']=='2024-09-24' and o.get('allocation_phase')=='MATURE'),('PV_OCT24_MATURE',lambda o:o['day']=='2024-10-24' and o['sector51']=='光伏风电设备' and o.get('allocation_phase')=='MATURE'),('ROBOT_DEC05_MATURE',lambda o:o['day']=='2024-12-05' and o['sector51']=='自动化与机器人' and o.get('allocation_phase')=='MATURE')]
    fixedfile=O/'FIXED_SPECIAL_OPPORTUNITIES.json'
    if fixedfile.exists():frozen_special=read(fixedfile)
    else:frozen_special=[]
    for name,pred in predicates:
        keys=[o['sid']+'|'+o['signal_day'] for o in bo if o['side']=='BUY_SEED' and pred(o)]
        frozen_special.append(dict(name=name,keys=keys))
    for gs in frozen_special:
        keys=gs['keys'];rs=[byrow[k] for k in keys];actual=[c[k] for k in keys if k in c]
        special.append(dict(cohort=gs['name'],baseline_count=len(keys),baseline_PnL=sm([b[k] for k in keys],'marked_net_pnl'),candidate_captured=len(actual),candidate_actual_PnL=sm(actual,'marked_net_pnl'),candidate_open=sum(x['open_at_cutoff'] for x in actual),candidate_add_orders=sum(x['add_count'] for x in actual),delayed=sum(x.get('delay_trading_sessions',0)>0 for x in rs),same_day=sum(x.get('delay_trading_sessions')==0 for x in rs),missing_reference_PnL_only=sm([b[k] for k in keys if k not in c],'marked_net_pnl'),identities=keys))
    save('FIXED_MATURE_OPPORTUNITY_COSTS',special)
    # Daily actual cash, new demand, funding, all buy cost and participation; M_actual_buy_cost is not all buys.
    daily=[]
    for label,path in paths.items():
        transfers=au.bykey(read(path/'TRANSFERS.json'),'day');refs=au.bykey(read(path/'REFERENCE_DAILY.json'),'day');orders=au.bykey(records[label]['orders'],'day')
        for day,l in ledgers[label].items():
            tt=transfers[day];oo=orders[day];rf=refs[day]
            daily.append(dict(account=label,day=day,cash=D(l['cash']),receivable=D(l['receivable']),NAV=D(l['NAV']),weight_pct=D(l['weight_pct']),stocks=l['stocks'],fees_paid=D(l['fees_paid']),all_actual_buy_cost=-sm([x for x in oo if x['side'].startswith('BUY')],'cash_delta'),seed_actual_buy_cost=-sm([x for x in oo if x['side']=='BUY_SEED'],'cash_delta'),add_actual_buy_cost=-sm([x for x in oo if x['side']=='BUY_ADD'],'cash_delta'),new_mature_seed_count=sum(x['side']=='BUY_SEED' and x.get('allocation_phase')=='MATURE' for x in oo),actual_ADD_count=sum(x['side']=='BUY_ADD' for x in oo),funding_records=tt,reference_records=rf))
    save('DAILY_CASH_DEMAND_EXPOSURE',daily)
    focus=set(x['sid'] for x in stocks[:15]+stocks[-15:])|{'000158.SZ','688660.SH','688503.SH','603063.SH','300085.SZ'}
    traces=[dict(account=label,**x) for label,rec in records.items() for x in rec['orders'] if x['sid'] in focus]
    save('MATERIAL_STOCK_ACTUAL_ORDER_TRACES',traces)
    # Compare actual full-round paths for affected H donors and withdrawn seed identities.
    fq=O/'FUNDING_QUANTITY_COMPARISON.json'
    if fq.exists():
        quantities=read(fq);affected=defaultdict(list);withdrawn=defaultdict(list)
        rid_to_key=records['M12']['rk']
        for x in quantities:
            if x['kind']=='DONOR' and x.get('healthy') and (x.get('full_C_y',0)!=x.get('selected_C_y',0) or x.get('selected_O_y',0)!=x.get('shadow_O_y',0) or x.get('actual_y',0)!=x.get('selected_O_y',0)):
                if x.get('round_id') in rid_to_key:affected[rid_to_key[x['round_id']]].append(x)
        affected_rows=[]
        for key,changes in affected.items():
            affected_rows.append(dict(opportunity_key=key,sid=c[key]['sid'],name=c[key]['name'],candidate_actual_round=c[key],baseline_same_identity_round=b.get(key),candidate_actual_PnL=c[key]['marked_net_pnl'],baseline_reference_PnL=b[key]['marked_net_pnl'] if key in b else None,actual_path_delta=D(c[key]['marked_net_pnl'])-D(b[key]['marked_net_pnl']) if key in b else None,quantity_changes=changes,not_isolated_causal_effect=True))
        save('AFFECTED_HEALTHY_DONOR_ACTUAL_ROUNDS',affected_rows)
        for x in read(candidate/'FUNDING_WAIT_LOG.json'):
            rr=x['original_request'];withdrawn[rr['sid']+'|'+rr['signal_day']].append(x)
        withdrawn_rows=[]
        for key,ws in withdrawn.items():
            cr=c.get(key);br=b.get(key)
            withdrawn_rows.append(dict(opportunity_key=key,sid=ws[0]['original_request']['sid'],wait_days=[x['day'] for x in ws],wait_outcomes=[dict(day=x['day'],status=x['status'],reason=x['reason']) for x in ws],candidate_eventually_captured=cr is not None,candidate_actual_round=cr,baseline_same_identity_round=br,candidate_actual_PnL=cr['marked_net_pnl'] if cr else Z,unfilled_baseline_reference_PnL_only=br['marked_net_pnl'] if br and not cr else None))
        save('WITHDRAWN_NEW_REQUEST_ACTUAL_OUTCOMES',withdrawn_rows)
    result['nov6_segment']=segment;result['actual_opportunity_attribution']=attribution;result['fixed_negative_rounds']=lossrows;result['special_fixed_mature_subgroups']=special
    result['dividend_recheck_count']=len(dividends)
    result['cash_statistics']={label:dict(mean_close_cash=sm(list(ledgers[label].values()),'cash')/93,max_close_cash=max(D(x['cash']) for x in ledgers[label].values()),min_close_cash=min(D(x['cash']) for x in ledgers[label].values())) for label in paths}
    save('INDEPENDENT_M12_VS_M7',result)
    return result

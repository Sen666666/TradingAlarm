"""Finish partial-account explanations, zero-space cash checks and block proof. No Data/history."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,sys
sys.dont_write_bytecode=True
import accounting_core as au
O=Path(__file__).resolve().parent;R=O.parent;P=R/'mainline_candidate_v12_winner_funding_competition/once_20250120';B=au.BASE;END='2024-10-10';Z=D(0)
read=au.read;save=au.save;sha=au.sha;sm=au.sm;near=au.near
def main():
    r=read(O/'INDEPENDENT_M12_VS_M7_PREFIX.json');sem=read(O/'SAVED_FUNDING_SEMANTICS.json');assert sem['verdict']=='PASS_ALL_CERTIFIED_SAVED_BRANCH_SEMANTICS' and sem['issues']==0
    records={};div=[];daily=[];role_count=Counter();roundday={};names={};marks={}
    for label,path in [('M12',P),('M7',B)]:
        orders=[x for x in read(path/'ORDERS.json') if x['day']<=END];holds=[x for x in read(path/'HOLDINGS.json') if x['day']<=END];eq=[x for x in read(path/'EQUITY_EVENTS.json') if x['day']<=END];led=[x for x in read(path/'DAY_LEDGER.json') if x['day']<=END]
        buys={x['lot_id']:x for x in orders if x['side'].startswith('BUY')};seeds={x['round_id']:x for x in orders if x['side']=='BUY_SEED'};keys={rid:x['sid']+'|'+x['signal_day'] for rid,x in seeds.items()}
        records[label]=dict(orders=orders,holds=holds,equity=eq,ledger=led,seeds=seeds,keys=keys)
        names.update({keys[k]:x['name'] for k,x in seeds.items()})
        for x in buys.values():assert x['capital_role']==('INITIAL' if x['side']=='BUY_SEED' and x['allocation_phase'] in ('EVENT','RESIDUAL') else 'EXPANSION');role_count[label+'_buy_role_checks']+=1
        for x in read(path/'CAPITAL_LOTS.json'):
            if x['day']<=END:assert x['capital_role']==buys[x['lot_id']]['capital_role'];role_count[label+'_unchanged_lot_role_checks']+=1
        terms=au.cash_event_terms(path);admitted={(x['sid'],x['ex_date']) for x in read(path/'EVENT_ADMISSION.json')};scope={(s,e) for s,e in admitted if '2024-09-02'<=e<=END}
        assert scope<=set(terms)
        for sid,ex in sorted(scope):
            t=terms[sid,ex];q=sum(x['qty'] for x in holds if x['sid']==sid and x['day']==t['record_date']);expected=D(q)*D(t['d_cash'])*D('.8')
            accr=[x for x in eq if x['sid']==sid and x['day']==ex and x['event']=='ACCRUE_NET80'];paid=[x for x in eq if x['sid']==sid and x['day']==t['pay_date'] and x['event']=='PAY_CLOSE_NET80']
            near(sm(accr,'receivable_delta'),expected,'all_admitted_entitlement');assert sum(x['record_qty'] for x in accr)==q
            if t['pay_date']<=END:near(sm(paid,'cash_delta'),expected,'all_admitted_payment')
            div.append(dict(account=label,sid=sid,record_date=t['record_date'],ex_date=ex,pay_date=t['pay_date'],record_qty=q,expected_NET80=expected,actual_accrued=sm(accr,'receivable_delta'),actual_paid=sm(paid,'cash_delta')))
        byorders=au.bykey(orders,'day');byholds=au.bykey(holds,'day');byeq=au.bykey(eq,'day');bytransfers=au.bykey([x for x in read(path/'TRANSFERS.json') if x['day']<=END],'day');byrefs=au.bykey([x for x in read(path/'REFERENCE_DAILY.json') if x['day']<=END],'day');cashflow=defaultdict(lambda:Z)
        for l in led:
            day=l['day']
            for x in byorders[day]:cashflow[keys[x['round_id']]]+=D(x['cash_delta'])
            for x in byeq[day]:
                if D(x.get('receivable_delta','0'))>0:cashflow[keys[x['round_id']]]+=D(x['receivable_delta'])
            mark=dict(cashflow)
            for x in byholds[day]:key=keys[x['round_id']];mark[key]=mark.get(key,Z)+D(x['market_value'])
            near(sum(mark.values(),Z),D(l['NAV'])-D(1200000),'daily_round_mark_total');roundday[label,day]=mark
            oo=byorders[day];tt=bytransfers[day];rr=byrefs[day]
            daily.append(dict(account=label,day=day,cash=l['cash'],NAV=l['NAV'],market_value=l['market_value'],weight_pct=l['weight_pct'],fees_paid=l['fees_paid'],all_actual_buy_cost=-sm([x for x in oo if x['side'].startswith('BUY')],'cash_delta'),ADD_buy_cost=-sm([x for x in oo if x['side']=='BUY_ADD'],'cash_delta'),new_mature_seed_count=sum(x['side']=='BUY_SEED' and x.get('allocation_phase')=='MATURE' for x in oo),funding_net=sm([x for x in oo if x.get('transfer_rank') is not None],'cash_delta'),original_D_total=sm(rr,'D'),original_desired_and_cash=[x for x in tt if x.get('event') in ('DEMAND_PLAN','TRANSFER_CASH','RECEIVER_FUNDING')]))
    save('ALL_ADMITTED_DIVIDEND_RECHECK',div);save('CAPITAL_ROLE_IMMUTABILITY_AUDIT',dict(role_count));save('DAILY_CASH_DEMAND_EXPOSURE',daily)
    bb={x['opportunity_key']:x for x in read(O/'M7_COMMON_ROUNDS.json')};cc={x['opportunity_key']:x for x in read(O/'M12_ACTUAL_ROUNDS.json')}
    matched=[]
    for key in set(bb)&set(cc):
        a=cc[key];b=bb[key]
        matched.append(dict(opportunity_key=key,name=a['name'],sid=a['sid'],M12_PnL=a['marked_net_pnl'],M7_PnL=b['marked_net_pnl'],delta=D(a['marked_net_pnl'])-D(b['marked_net_pnl']),M12_seed=a['actual_seed_OPEN'],M7_seed=b['actual_seed_OPEN'],M12_ADD=a['add_count'],M7_ADD=b['add_count'],M12_exit=a['exit_day'],M7_exit=b['exit_day'],M12_open=a['open_at_cutoff'],M7_open=b['open_at_cutoff'],M12_orders=a['actual_orders'],M7_orders=b['actual_orders']))
    matched.sort(key=lambda x:x['delta'],reverse=True);save('MATCHED_ACTUAL_ROUND_PATH_DELTAS',matched)
    ds=read(P/'FUNDING_OPEN_DECISIONS.json');keybyrid=records['M12']['keys'];healthy=defaultdict(list)
    for d in ds:
        for h in d['H'].values():
            if h['H'] and h['round_id'] in keybyrid:
                key=keybyrid[h['round_id']]
                if d['day'] not in healthy[key]:healthy[key].append(d['day'])
    giveback=[]
    for key in set(bb)&set(cc):
        days=[x['day'] for x in records['M12']['ledger'] if key in roundday['M12',x['day']]]
        peak=max((roundday['M12',d][key],d) for d in days)
        va=roundday['M12','2024-10-08'].get(key,Z);ve=roundday['M12',END].get(key,Z);ba=roundday['M7','2024-10-08'].get(key,Z);be=roundday['M7',END].get(key,Z)
        giveback.append(dict(opportunity_key=key,name=names[key],M12_oct8_PnL=va,M12_end_PnL=ve,M7_oct8_PnL=ba,M7_end_PnL=be,M12_oct8_to_end=ve-va,M7_oct8_to_end=be-ba,extra_oct8_to_end_delta=(ve-va)-(be-ba),M12_own_peak_PnL=peak[0],M12_own_peak_day=peak[1],M12_end_minus_own_peak=ve-peak[0],H_OPEN_dates=healthy[key],H_OPEN_oct8_or_after=[d for d in healthy[key] if d>='2024-10-08'],scope='Actual cashflow+entitlement+mark; own-peak and Oct8 anchor are distinct. H is decision-time conditional snapshot, not a permanent role.'))
    giveback.sort(key=lambda x:x['extra_oct8_to_end_delta']);save('HEALTHY_ROUND_GIVEBACK_PATHS',giveback)
    focus={'300085.SZ','600663.SH','300059.SZ','600648.SH','600848.SH','000158.SZ','600779.SH','603369.SH','000596.SZ','300457.SZ','002709.SZ','603659.SH'}
    trace=[dict(account=label,**x) for label,rec in records.items() for x in rec['orders'] if x['sid'] in focus];save('MATERIAL_STOCK_ACTUAL_ORDER_TRACES',trace)
    # Prove saved atomic prefix did not commit Oct11 changes; no strategy replay.
    blocked=read(P/'UNCERTIFIED_DAY.json');status=read(P.parent/'RUN_STATUS.json');assert blocked==status['atomic_block'] and blocked['day']>END
    dated={}
    excludes={'EVENT_ADMISSION','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY','BLOCKERS','FUNDING_BRANCH_BOOKS'}
    for p in P.glob('*.json'):
        if p.stem in excludes:continue
        x=read(p)
        if isinstance(x,list):
            dates=[v['day'] for v in x if isinstance(v,dict) and isinstance(v.get('day'),str)]
            assert all(d<=END for d in dates),(p.name,'postfrontier_commit');dated[p.name]=len(dates)
    assert all(x['day']<=END for x in records['M12']['orders']) and all(x['close_day']<=END for x in read(O/'FUNDING_PLAN_SELECTION_AUDIT.json'))
    assert [x['day'] for x in read(P/'FUNDING_PREFLIGHT.json')]==[x['day'] for x in records['M12']['ledger']]
    guard=(R/'mainline_candidate_v12_winner_funding_competition/engine.py').read_text()
    assert 'vars(self).update(snapshot)' in guard and 'pending[:]=p0' in guard
    rollback=dict(verdict='PASS_SAVED_NO_PARTIAL_ACCOUNT_COMMIT',frontier=END,blocked_day=blocked['day'],dated_saved_rows=dated,certified_books=22,certified_OPEN_decisions=21,blocked_OPEN_selection_saved=False,blocked_orders_saved=False,blocked_funding_wait_saved=False,source_bound_atomic_restore=True,limit='Saved absence and reviewed restoration source checked; no replay of failing step or direct in-memory pre/post snapshot comparison.')
    save('ATOMIC_ROLLBACK_PREFIX_AUDIT',rollback)
    # Independently recalculate the ordinary 200-share Oct8 budget threshold.
    factpath=R/'mainline_winner_funding_review_v1/V12_688200_EVENT_ADMISSION_QA.json';fact=read(factpath)
    assert sha(factpath)=='b329c2a3f80ec60c6103c40ffd2e5052a29fb079501e8ba9089caf7ce0151d8f'
    for p,h in fact['evidence_hashes'].items():assert sha(p)==h
    signal=Path(next(p for p in fact['evidence_hashes'] if p.endswith('signal.parquet')))
    import pyarrow.parquet as pq
    source_rows=pq.read_table(signal,columns=['date','raw_open','adjustment_factor']).to_pylist()
    quote=next(x for x in source_rows if str(x['date'])[:10]=='2024-10-08');raw=D(str(quote['raw_open']));price=raw*D('1.0005');fee=au.fee_calc(read(au.RULES),read(au.PROTOCOL)['approved_proxy_ids'],'688200.SH','2024-10-08',200,price,'buy');cost=200*price+fee
    pt=read(P/'TICKET_STATE.json')['688200.SH'];bt=next(x for x in read(B/'RETRY_TICKETS.json') if x['sid']=='688200.SH' and x['day']=='2024-10-08' and x['event']=='OPEN_OUTCOME')
    bbudget=D(bt['original_nav'])*D('.02');pbudget=D(pt['budget']);near(cost,'25939.808894736000','688200_native_budget_cost')
    assert bbudget<cost<=pbudget
    assert not [x for x in read(P/'ORDERS.json') if x['sid']=='688200.SH'] and not [x for x in read(B/'ORDERS.json') if x['sid']=='688200.SH']
    assert not [x for x in read(P/'HOLDINGS.json') if x['sid']=='688200.SH']
    assert pt['signal_day']=='2024-09-26' and pt['status']=='RETAINED'
    assert not [x for x in read(P/'EVENT_ADMISSION.json') if x['sid']=='688200.SH' and x['ex_date']=='2024-10-11']
    sourcehashes=read(P/'SOURCE_HASHES.json');assert str(fact['adapter_path']) not in sourcehashes
    blockproof=dict(verdict='NATIVE_GUARD_BLOCK_FROM_CHANGED_RETAINED_TICKET_PATH',sid='688200.SH',original_signal='2024-09-26',ticket_id=pt['ticket_id'],held_qty=0,no_actual_orders_in_either_account=True,raw_OPEN_20241008=raw,buy_price_with_native_slippage=price,qty=200,dated_fee=fee,all_in_cost=cost,M7_original_budget=bbudget,M12_original_budget=pbudget,M7_shortfall=cost-bbudget,M12_headroom=pbudget-cost,M7_cancelled_on='2024-10-08',M7_reason=bt['decision'],M12_remained_original_valid_capital_wait=True,blocked_day='2024-10-11',local_event=fact['exact_scope'],local_event_not_admitted_in_frozen_old_run=True,local_fact_review_path=str(factpath),local_fact_review_sha256=sha(factpath),local_evidence_hashes_verified=len(fact['evidence_hashes']),candidate_error_identified=False,no_new_event_admission_or_v2_run_imported=True)
    save('ATOMIC_BLOCK_688200_CAUSE_AUDIT',blockproof)
    # Attach separately hash-bound independent implementation review.
    ip=R/'mainline_winner_funding_review_v1/V12_INDEPENDENT_INTERFACE_QA.json';ir=read(ip)
    assert ir['engine_sha256']==sha(P.parent/'engine.py') and ir['tests_sha256']==sha(P.parent/'synthetic_tests.py') and ir['source_manifest_sha256']==sha(P.parent/'SOURCE_HASHES.json')
    for p,h in read(P.parent/'SOURCE_HASHES.json')['files'].items():assert sha(p)==h
    r.update(verdict='PASS_CERTIFIED_PREFIX_ACCOUNTING_AND_SAVED_BRANCH_SEMANTICS',saved_semantics=sem,static_review=dict(path=str(ip),sha256=sha(ip),scope=ir['scope'],not_certified=ir['not_certified']),all_admitted_cash_recheck=dict(count=len(div),by_account=dict(Counter(x['account'] for x in div)),scope='Only cash events effective by certified Oct10, not the 534 checks planned for a completed Jan20 comparison.'),capital_role_checks=dict(role_count),atomic_rollback=rollback,atomic_block_cause=blockproof,matched_top5=matched[:5],matched_bottom6=matched[-6:])
    r['cash_statistics']={label:dict(mean_close_cash=sm(rec['ledger'],'cash')/len(rec['ledger']),max_close_cash=max(D(x['cash']) for x in rec['ledger']),min_close_cash=min(D(x['cash']) for x in rec['ledger'])) for label,rec in records.items()}
    r['peak_reversal']={label:dict(oct8_NAV=D(next(x['NAV'] for x in rec['ledger'] if x['day']=='2024-10-08')),end_NAV=D(rec['ledger'][-1]['NAV']),oct8_to_end_PnL=D(rec['ledger'][-1]['NAV'])-D(next(x['NAV'] for x in rec['ledger'] if x['day']=='2024-10-08'))) for label,rec in records.items()}
    plans=read(O/'FUNDING_PLAN_SELECTION_AUDIT.json');openplans=[x for x in plans if 'OPEN_day' in x]
    r['selection_summary']=dict(books=22,branches=2213,certified_OPEN_decisions=len(openplans),CLOSE_deletions=sum(x['CLOSE_deleted'] for x in plans),additional_OPEN_deletions=sum(x['OPEN_additional_deleted'] for x in openplans),total_removed_request_day_occurrences=sum(x['OPEN_total_deleted'] for x in openplans),empty_N_OPEN_days=sum(x['N_OPEN_selected']==0 for x in openplans),full_request_day_occurrences=sum(x['N_full'] for x in openplans),certified_close_not_executed='2024-10-10 CLOSE / 2024-10-11 planned OPEN is not a certified actual trade')
    save('INDEPENDENT_M12_VS_M7_PREFIX',r)
    print(json.dumps(dict(verdict=r['verdict'],cash_checks=r['all_admitted_cash_recheck'],roles=dict(role_count),block_cause=blockproof,selection=r['selection_summary']),ensure_ascii=False,default=str))
if __name__=='__main__':main()

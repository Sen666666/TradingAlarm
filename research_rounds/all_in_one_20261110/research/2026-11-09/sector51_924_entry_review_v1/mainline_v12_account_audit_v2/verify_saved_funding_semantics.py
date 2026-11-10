"""Independent saved M12 branch/account semantic checks. No candidate import/history."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import argparse,hashlib,json,sys
sys.dont_write_bytecode=True
import accounting_core as au
O=Path(__file__).resolve().parent;R=O.parent;Z=D(0)
read=au.read;save=au.save;sha=au.sha;near=au.near
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def request_id(r):
    ticket=hashlib.sha256(json.dumps([r['sid'],r['birth_type'],r['signal_day'],r['origin']]).encode()).hexdigest()[:24] if r['kind']=='SEED' else None
    return digest([r['sid'],r['kind'],r['signal_day'],r.get('birth_type'),ticket,r.get('round_id'),r.get('cp_id'),r.get('cp_date'),r.get('event_id'),r.get('origin')])[:24]
def new_seed(r):return r['kind']=='SEED' and r.get('allocation_phase')=='MATURE'
def protected(r):return r['kind']=='ADD' or r.get('allocation_phase')=='EVENT'
def comparison(p,p0,H,A):
    y=[k for k,h in H.items() if h['H'] and p['y'].get(k,0)>p0['y'].get(k,0)]
    q=[k for k in A if p['q'].get(k,0)<p0['q'].get(k,0)]
    return dict(passed=not y and not q,healthy_donor_increase=y,add_event_reduction=q)
def equivalent_comparison(got,want):
    assert got['passed'] is want['passed']
    for k in ('healthy_donor_increase','add_event_reduction'):assert set(got[k])==set(want[k]),(k,got,want)
def quantities(p,branch,ids):
    assert set(p['q'])==set(ids),('projection_identity_inventory',set(p['q'])^set(ids))
    assert all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in [*p['q'].values(),*p['y'].values()])
    for k,q in p['q'].items():assert q<=branch['bar_q_C'][k],('branch_authorized_q',k,q,branch['bar_q_C'][k])
    donors={x['lot_id']:x for x in branch['plan']['transfer_plan']}
    for k,q in p['y'].items():assert k in donors and q<=donors[k]['max_q'],('branch_authorized_y',k,q)
    # Independently decode saved native reservation/transfer rows.
    lookup={(r['sid'],r['kind'],r['signal_day'],r.get('cp_id')):request_id(r) for r in ids.values()}
    assert len(lookup)==len(ids),'ambiguous_request_lookup'
    qq={k:0 for k in ids}
    for x in p['reservation_rows']:
        key=(x['sid'],x.get('event'),x.get('signal_day'),x.get('cp_id'))
        assert key in lookup,('unfrozen_receiver',key)
        qq[lookup[key]]=x['executed_q']
    yy={x['lot_id']:x['executed_q'] for x in p['transfer_rows'] if x.get('event')=='DONOR_EXECUTION'}
    assert qq==p['q'] and yy==p['y'],'projection_summary_not_native_rows'
def capped_water(weights,upper,budget):
    target=min(max(Z,budget),sum(upper.values(),Z));left=target;active=set(weights);out={s:Z for s in weights};lam=Z
    while active:
        lam=left/sum((weights[s] for s in sorted(active)),Z)
        capped=[s for s in sorted(active) if upper[s]<=lam*weights[s]]
        if not capped:
            out.update({s:lam*weights[s] for s in sorted(active)});break
        for s in capped:out[s]=upper[s];left-=upper[s];active.remove(s)
    if not active and weights:lam=max(upper[s]/weights[s] for s in weights)
    return out,lam,max(Z,budget-target)
def reference(branch):
    """Recompute arithmetic from each branch's own saved native legal-demand details.
    Does not certify the source timing or upstream legal qualification of those details."""
    ref=branch['plan']['reference'];keys=set(ref['D']);requests=branch['requests']
    for k in ('K','U','X','T','T_residual','envelope','fixed','core','sector_value'):assert set(ref[k])==keys,('reference_sector_inventory',k)
    ids={(r['sid'],r['kind'],r['signal_day'],r.get('cp_id')) for r in requests if r.get('allocation_phase')=='MATURE'}
    demand={s:Z for s in keys};seen=[]
    for row in ref['independent_demand_details']:
        ident=(row['sid'],row['kind'],row['signal_day'],row.get('cp_id'));assert ident in ids,'demand_from_deleted_request'
        seen.append(ident);demand[row['sector51']]+=D(row['independent_all_in_cost'])
    assert set(seen)==ids,'branch_mature_demand_missing'
    for s in keys:
        near(demand[s],ref['D'][s],('native_branch_D',s))
        near(D(ref['sector_value'][s])-D(ref['fixed'][s]),ref['K'][s],('native_branch_K',s))
        near(D(ref['K'][s])+demand[s],ref['U'][s],('native_branch_U',s))
    reserved=sum((D(v) for v in ref['event_by_sector'].values()),Z)
    budget=D(ref['budget_before_event'])-reserved;free=budget-sum((D(v) for v in ref['lower'].values()),Z)
    near(reserved,ref['event_reserve'],'event_reserve');near(budget,ref['budget'],'branch_budget');near(free,ref['expansion_budget'],'branch_free_budget')
    weights={k:D(v) for k,v in ref['W'].items()};upper={k:D(ref['U'][k]) for k in weights}
    expected='INFEASIBLE_LOWER_EXCEEDS_BUDGET' if free<0 else 'NO_POSITIVE_E_M' if not weights else 'PASS'
    assert ref['status']==expected
    xx={s:Z for s in keys};unallocated=max(Z,free)
    if expected=='PASS':
        allocated,lam,unallocated=capped_water(weights,upper,free);xx.update(allocated);near(lam,ref['lambda_value'],'branch_lambda')
    else:assert ref['lambda_value'] is None
    near(unallocated,ref['unallocated_expansion_budget'],'branch_unallocated')
    for s in keys:
        near(xx[s],ref['X'][s],('branch_X',s));near(D(ref['fixed'][s])+xx[s],ref['T_residual'][s],('branch_T_residual',s))
        near(D(ref['fixed'][s])+xx[s]+D(ref['event_by_sector'].get(s,0)),ref['T'][s],('branch_T',s))
        env=max(Z,xx[s]-D(ref['K'][s])) if expected=='PASS' and s in weights else Z;near(env,ref['envelope'][s],('branch_envelope',s))
    donors=branch['plan']['transfer_plan'];assert [x['rank'] for x in donors]==list(range(1,len(donors)+1))
    assert len({x['lot_id'] for x in donors})==len(donors)
    assert set(branch['plan']['_donor_sectors'])=={x['sector51'] for x in donors}
    rows={x['lot_id']:x for x in ref['rows']}
    for x in donors:
        s=x['sector51'];near(max(D(ref['fixed'][s]),D(ref['T'][s])),x['close_sector_floor'],('branch_sector_floor',x['lot_id']))
        assert x['frozen_lot_qty']==rows[x['lot_id']]['frozen_qty']==ref['frozen_lot_qty'][x['lot_id']]
        assert x['max_q']>0 and x['max_q']<=rows[x['lot_id']]['mobile_qty']
def health(H,phase,day,rules,proxies):
    byround=defaultdict(list)
    for lid,h in H.items():
        assert h['lot_id']==lid and isinstance(h['H'],bool)
        assert h['H']==all(h['components'].values()),('saved_H_components',lid)
        assert all(isinstance(v,bool) for v in h['components'].values())
        assert h['conditionally_predicted']==(phase=='OPEN')
        assert D(h['conditional_prefix_cashflow'])<=0 or phase=='OPEN','CLOSE_has_predicted_cashflow'
        assert h['knowledge']['day']<=day
        byround[h['round_id']].append(h)
    for rid,hs in byround.items():
        h=hs[0];q=sum(x['quantity'] for x in hs);price=D(h['raw_mark'])*D('.9995')
        expected=D(h['actual_cashflow_before_prefix'])+D(h['conditional_prefix_cashflow'])+D(h['dividend'])+q*price-au.fee_calc(rules,proxies,h['sid'],day,q,price,'sell')
        for x in hs:
            near(expected,x['net_liquidation'],('H_round_liquidation',rid));assert x['components']['current_net_positive']==(expected>0)
            if x['H']:assert D(x['raw_mark'])*D(x['current_factor'])>D(x['effective_protection'])
def audit(path):
    path=Path(path);books=read(path/'FUNDING_BRANCH_BOOKS.json');decisions=read(path/'FUNDING_OPEN_DECISIONS.json')
    actual=read(path/'FUNDING_ACTUAL_DIAGNOSTICS.json');waits=read(path/'FUNDING_WAIT_LOG.json');preflight=read(path/'FUNDING_PREFLIGHT.json')
    orders=read(path/'ORDERS.json');transfers=read(path/'TRANSFERS.json');ledger=read(path/'DAY_LEDGER.json')
    rules=read(au.RULES);proxies=read(au.PROTOCOL)['approved_proxy_ids']
    counts=Counter();plans=[];bookmap={b['book_id']:b for b in books};assert len(bookmap)==len(books)
    assert [b['close_day'] for b in books]==[x['day'] for x in ledger]
    for book in books:
        integrity=book['scratch_integrity'];assert integrity['passed'] is True and integrity['before']==integrity['after'],'reported_CLOSE_scratch_mutation'
        assert digest({k:v for k,v in book.items() if k!='book_id'})==book['book_id'],'book_content_hash'
        ids={request_id(r):r for r in book['original_requests']};assert len(ids)==len(book['original_requests'])
        priority=book['N_priority'];assert len(set(priority))==len(priority) and set(priority)=={k for k,r in ids.items() if new_seed(r)}
        assert set(book['A'])=={k for k,r in ids.items() if protected(r)},'protected_request_set'
        assert len(book['branches'])==len(priority)+1
        health(book['H'],'CLOSE',book['close_day'],rules,proxies)
        cpref=book['close_conditional_prefix']
        assert digest([book['close_day'],'CLOSE',cpref['actual_cash_before'],cpref['actual_receivable'],book['H']])==book['health_snapshot_id'],'CLOSE_H_snapshot_hash'
        shadow=book['branches'][-1];passing=[]
        for i,b in enumerate(book['branches']):
            assert b['deletion_index']==i and b['retained']==priority[:len(priority)-i],'non_nested_or_reordered_N'
            rids={request_id(r):r for r in b['requests']}
            assert set(rids)=={k for k,r in ids.items() if not new_seed(r) or k in b['retained']},'branch_membership'
            for k,r in rids.items():
                assert r['allocation_phase']==ids[k]['allocation_phase'],'phase_rewrite'
                for field in ('sid','kind','signal_day','birth_type','ticket_id','round_id','cp_id','cp_date','event_id','origin','nav0','budget'):
                    assert r.get(field)==ids[k].get(field),('branch_identity_changed',field,k)
            assert set(b['bar_q_C'])==set(ids)
            for k in ids:
                r=rids.get(k);bar=min(r['planned_q'],r['capacity'],r.get('_ref_q',0),r.get('econ_q',r['planned_q'])) if r else 0
                assert b['bar_q_C'][k]==bar,('bar_quantity',k)
            payload={k:b[k] for k in ('retained','requests','plan','event_reserved','bar_q_C')}
            assert digest(payload)==b['branch_id'],'branch_content_hash'
            reference(b);quantities(b['close_projection'],b,ids)
            want=comparison(b['close_projection'],shadow['close_projection'],book['H'],book['A']);equivalent_comparison(b['close_comparison'],want)
            if want['passed']:passing.append(i)
            counts['branch_reference_recomputed']+=1;counts['close_lot_comparisons']+=sum(h['H'] for h in book['H'].values());counts['close_request_comparisons']+=len(book['A'])
        assert passing and book['selected_close_index']==passing[0] and passing[-1]==len(priority)
        assert not shadow['retained'] and shadow['close_comparison']['passed'],'empty_N_must_be_shadow'
        plans.append(dict(close_day=book['close_day'],book_id=book['book_id'],N_full=len(priority),CLOSE_deleted=book['selected_close_index'],N_CLOSE_selected=len(priority)-book['selected_close_index'],CLOSE_first_pass=book['branches'][book['selected_close_index']]['branch_id'],branch_count=len(book['branches']),CLOSE_failures=len(book['branches'])-len(passing)))
    decisionmap={d['day']:d for d in decisions};assert len(decisionmap)==len(decisions)
    assert set(decisionmap)=={x['day'] for x in ledger[1:]}
    premap={x['day']:x for x in preflight};assert len(premap)==len(preflight)==len(ledger)
    actualmap={x['day']:x for x in actual};assert set(actualmap)==set(decisionmap)
    actual_byday=au.bykey(orders,'day');transfer_byday=au.bykey(transfers,'day');prediction_rows=[];deviations=[]
    for d in decisions:
        integrity=d['scratch_integrity'];assert integrity['passed'] is True and integrity['before']==integrity['after'],'reported_OPEN_scratch_mutation'
        book=bookmap[d['book_id']];ids={request_id(r):r for r in book['original_requests']};branches=book['branches'];assert d['day']==book['next_day']
        health(d['H'],'OPEN',d['day'],rules,proxies)
        assert digest([d['day'],'OPEN',d['common_conditional_prefix'],d['H']])==d['health_snapshot_id']
        prefix=d['common_conditional_prefix'];near(D(prefix['actual_cash_before'])+au.sm(prefix['predicted_prefix_orders'],'cash_delta'),prefix['predicted_cash_after'],'conditional_prefix_cash')
        inv={lid:q for v in prefix['conditional_inventory'].values() for lid,q in v.items()};assert {k:h['quantity'] for k,h in d['H'].items()}==inv,'H_not_common_inventory'
        p0=d['shadow_projection'];quantities(p0,branches[-1],ids)
        eligible=[i for i,b in enumerate(branches) if i>=book['selected_close_index'] and b['close_comparison']['passed']]
        assert d['selected_index'] in eligible
        expected_indices=eligible[:eligible.index(d['selected_index'])+1]
        assert [e['index'] for e in d['evaluated']]==expected_indices,'not_first_passing_frozen_suffix'
        for e in d['evaluated']:
            b=branches[e['index']];assert e['branch_id']==b['branch_id'] and e['health_snapshot_id']==d['health_snapshot_id']
            quantities(e['projection'],b,ids);want=comparison(e['projection'],p0,d['H'],book['A']);equivalent_comparison(e['comparison'],want)
            assert want['passed']==(e['index']==d['selected_index'])
        chosen=branches[d['selected_index']];assert chosen['branch_id']==d['selected_branch_id']
        assert d['chosen_projection']==d['evaluated'][-1]['projection']
        if not chosen['retained']:assert d['chosen_projection']==p0,'empty_N_not_exact_P0'
        assert d['selection_before_actual_orders']==sum(x['day']<d['day'] for x in orders),'selection_after_actual_orders'
        pf=premap[d['day']]
        assert {x['sid'] for x in pf['original_pending']}<=set(pf['original_targets']),'preflight_missing_pending'
        assert set(pf['original_targets'])>=set(book['preflight_original_targets']),'preflight_shrunk_previous_close_targets'
        a=actualmap[d['day']];assert a['diagnostic_only'] is True and a['reselected'] is False and a['selected_branch_id']==d['selected_branch_id']
        assert a['actual_orders']==actual_byday[d['day']],'actual_orders_not_complete_account'
        qq={k:0 for k in ids};lookup={(r['sid'],r['kind'],r['signal_day'],r.get('cp_id')):k for k,r in ids.items()}
        for x in actual_byday[d['day']]:
            if x['side'].startswith('BUY'):
                key=(x['sid'],x['side'][4:],x['signal_day'],x.get('cp_id'));assert key in lookup,'actual_buy_not_close_authorized'
                k=lookup[key];qq[k]+=x['qty'];assert k in {request_id(r) for r in chosen['requests']},'actual_buy_from_wrong_branch'
        yy={x['lot_id']:x['executed_q'] for x in transfer_byday[d['day']] if x.get('event')=='DONOR_EXECUTION'}
        assert qq==a['actual_q'] and yy==a['actual_y'],'reported_actual_quantity_not_account'
        for k,q in qq.items():assert q<=chosen['bar_q_C'][k],('actual_buy_above_branch_permission',k)
        donor_limits={x['lot_id']:x['max_q'] for x in chosen['plan']['transfer_plan']}
        assert all(k in donor_limits and q<=donor_limits[k] for k,q in yy.items()),'actual_donor_outside_branch_permission'
        if 'actual_prefix_cash' in a:
            near(D(prefix['actual_cash_before'])+au.sm(a['actual_prefix_orders'],'cash_delta'),a['actual_prefix_cash'],'actual_prefix_cash')
            near(D(a['actual_prefix_cash'])-D(prefix['predicted_cash_after']),a['prefix_cash_deviation'],'actual_prefix_cash_difference')
        qdev={k:qq.get(k,0)-d['chosen_projection']['q'].get(k,0) for k in set(qq)|set(d['chosen_projection']['q']) if qq.get(k,0)!=d['chosen_projection']['q'].get(k,0)}
        ydev={k:yy.get(k,0)-d['chosen_projection']['y'].get(k,0) for k in set(yy)|set(d['chosen_projection']['y']) if yy.get(k,0)!=d['chosen_projection']['y'].get(k,0)}
        assert qdev==a['q_deviation'] and ydev==a['y_deviation']
        prefix_difference=D(a.get('prefix_cash_deviation','0'))!=0 or ('actual_prefix_inventory' in a and a['actual_prefix_inventory']!=prefix['conditional_inventory'])
        if qdev or ydev or prefix_difference:deviations.append(dict(day=d['day'],q_deviation=qdev,y_deviation=ydev,prefix_cash_deviation=a.get('prefix_cash_deviation'),prefix_inventory_different=a.get('actual_prefix_inventory',prefix['conditional_inventory'])!=prefix['conditional_inventory'],no_fill_events=a['no_fill_events'],cause=a.get('deviation_reasons',a.get('deviation_cause')),must_not_imply_selection_failure=True))
        for k in ids:
            prediction_rows.append(dict(day=d['day'],kind='RECEIVER',identity=k,sid=ids[k]['sid'],request_kind=ids[k]['kind'],allocation_phase=ids[k]['allocation_phase'],protected=k in book['A'],full_C_q=branches[0]['close_projection']['q'][k],shadow_C_q=branches[-1]['close_projection']['q'][k],selected_C_q=chosen['close_projection']['q'][k],selected_bar_q_C=chosen['bar_q_C'][k],shadow_O_q=p0['q'][k],selected_O_q=d['chosen_projection']['q'][k],actual_q=qq[k]))
        for k in set(d['H'])|set(yy)|set(p0['y'])|set(d['chosen_projection']['y']):
            h=d['H'].get(k,{})
            prediction_rows.append(dict(day=d['day'],kind='DONOR',identity=k,sid=h.get('sid'),round_id=h.get('round_id'),healthy=h.get('H'),healthy_CLOSE=book['H'].get(k,{}).get('H'),full_C_y=branches[0]['close_projection']['y'].get(k,0),shadow_C_y=branches[-1]['close_projection']['y'].get(k,0),selected_C_y=chosen['close_projection']['y'].get(k,0),shadow_O_y=p0['y'].get(k,0),selected_O_y=d['chosen_projection']['y'].get(k,0),actual_y=yy.get(k,0)))
        row=next(x for x in plans if x['book_id']==book['book_id']);row.update(OPEN_day=d['day'],OPEN_total_deleted=d['selected_index'],OPEN_additional_deleted=d['selected_index']-book['selected_close_index'],N_OPEN_selected=len(book['N_priority'])-d['selected_index'],OPEN_selected_branch=d['selected_branch_id'],shadow_predicted_cash=p0['cash_after'],selected_predicted_cash=d['chosen_projection']['cash_after'],actual_cash_after=a['actual_cash_after'],conditional_healthy_lots=sum(h['H'] for h in d['H'].values()),actual_prefix_healthy_lots_diagnostic_only=sum(h['H'] for h in a.get('actual_prefix_H_diagnostic_only',{}).values()))
        counts['open_lot_comparisons']+=sum(h['H'] for h in d['H'].values())*len(d['evaluated']);counts['open_request_comparisons']+=len(book['A'])*len(d['evaluated'])
    stable={}
    for w in waits:
        d=decisionmap[w['day']];b=bookmap[d['book_id']];r=w['original_request'];rid=request_id(r);assert rid==w['request_id'] and new_seed(r)
        chosen=b['branches'][d['selected_index']];assert rid in b['N_priority'] and rid not in chosen['retained'],'wait_not_removed_N'
        assert w['selected_branch_id']==d['selected_branch_id'];assert w.get('has_lot',False) is False and w['actual_quantity']==0 and w['new_round_created'] is False
        assert not [x for x in actual_byday[w['day']] if x['side']=='BUY_SEED' and x['sid']==r['sid'] and x['signal_day']==r['signal_day']],'wait_also_filled'
        key=(r['sid'],r['signal_day'],r.get('birth_type'));budget=(r['nav0'],r['budget'],r['origin'])
        if key in stable:assert stable[key]==budget,'wait_reset_attempt_budget'
        stable[key]=budget
        assert w['reason']=='FUNDING_NONDISPLACEMENT_WAIT' or w['status'] in ('CANCELLED','PAUSED','ORIGINAL_REJECT_NO_TICKET','RETAINED'),'unrecognized_original_wait_outcome'
        if w['reason']=='FUNDING_NONDISPLACEMENT_WAIT':assert w['status']=='RETAINED' and w['original_open_check']=='PASS'
    cps=[x for x in read(path/'CP_EVENTS.json') if x['event']=='CONSUMED_ON_FILL'];adds=[x for x in orders if x['side']=='BUY_ADD']
    cpkeys=lambda rows:Counter((x['day'],x['round_id'],x['cp_id']) for x in rows)
    assert cpkeys(cps)==cpkeys(adds) and all(v==1 for v in cpkeys(cps).values()),'CP_consumption_not_actual_once'
    events=read(path/'EVENT_LOG.json');attempts=[x for x in events if x['event']=='PRIORITY_REAL_OPEN_ATTEMPT']
    assert all(v==1 for v in Counter(x['event_id'] for x in attempts).values()),'priority_attempt_consumed_twice'
    spent=[x for x in events if x['event']=='ACTUAL_SEED_CAPITAL_CONSUMED'];seed_event=[x for x in orders if x['side']=='BUY_SEED' and x.get('allocation_phase') in ('EVENT','RESIDUAL')]
    assert len(spent)==len(seed_event),'event_spent_not_actual_fills'
    cost_keys=lambda x:(x['day'],x['sid'],x.get('event_id'),x['qty'])
    spendmap={cost_keys(x):x for x in spent};assert len(spendmap)==len(spent)
    for x in seed_event:
        e=spendmap[cost_keys(x)];near(-D(x['cash_delta']),e['actual_cost'],'event_spent_actual_cost')
        near(D(e['spent_after'])-D(e['spent_before']),e['actual_cost'],'event_spent_increment')
    registry=read(path/'EVENT_REGISTRY.json')
    for eid,event in registry.items():
        total=sum((D(x['actual_cost']) for x in spent if x['event_id']==eid),Z);near(total,event['spent'],('event_spent_once',eid))
    counts.update(books=len(books),open_decisions=len(decisions),waiting_records=len(waits),CP_fills=len(adds),real_event_priority_attempts=len(attempts),actual_deviation_days=len(deviations))
    save('FUNDING_PLAN_SELECTION_AUDIT',plans);save('FUNDING_QUANTITY_COMPARISON',prediction_rows);save('ACTUAL_PREDICTION_DEVIATIONS',deviations)
    result=dict(verdict='PASS_SAVED_BRANCH_SEMANTICS',counts=dict(counts),sources={n:sha(path/n) for n in ('FUNDING_BRANCH_BOOKS.json','FUNDING_OPEN_DECISIONS.json','FUNDING_ACTUAL_DIAGNOSTICS.json','FUNDING_WAIT_LOG.json','FUNDING_PREFLIGHT.json','ORDERS.json','TRANSFERS.json')},checks=['Content hashes and stable request identities','Original rank nested deletions and CLOSE-first-passing suffix','Each saved native D/K/U/X/T/envelope and own-reference sector floor arithmetic','Each lot/request CLOSE/OPEN nondisplacement recomputed, not candidate pass flags','Quantity distinctions and exact empty-N shadow equality','Actual order/transfer quantities and deviations independently decoded','Preflight saved coverage and WAIT original identity/budget/no-fill facts','CP actual ADD once and EVENT attempts never duplicated'],not_covered=['Saved legal-demand details do not prove their raw input provenance or legal-qualification source timing.','Saved health component/net arithmetic is verified; underlying I/CP/source knowledge timing still needs static/poison tests.','No read-only audit can prove candidate had no unlogged scratch mutation or no hidden future read; require source-bound independent static review.','WAIT unknown/False behavior not exercised in real path requires independent synthetic evidence.','Actual no_fill divergence is diagnostic, not an automatic violation of conditional q/y guarantees.'],deviation_cause_gaps=[x['day'] for x in deviations if not any(e.get('event') in ('SELL_NO_FILL','DONOR_NO_FILL','BUY_NO_FILL') for e in x['no_fill_events']) and not x['cause']],strategy_imported=False,history_executed=False,auditor_source_sha256=sha(__file__))
    if result['deviation_cause_gaps']:result['verdict']='INCOMPLETE_UNEXPLAINED_ACTUAL_DEVIATION'
    save('SAVED_FUNDING_SEMANTICS',result);return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',required=True,type=Path);a=ap.parse_args()
    print(json.dumps(audit(a.candidate),ensure_ascii=False,default=str))

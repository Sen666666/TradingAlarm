"""Full saved branch audit for certified atomic prefix, streaming the 7 GB source."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import argparse,json,sys,time
sys.dont_write_bytecode=True
import accounting_core as au
import verify_saved_funding_semantics as sem
from stream_branch_books import iter_books
HOME=Path(__file__).resolve().parent;O=HOME;R=O.parent;P=None;Z=D(0)
read=au.read;sha=au.sha;save=au.save;near=au.near;sm=au.sm
errors=[];counts=Counter();plans=[];quantities=[];deviations=[];daychecks=[]
def check(stage,location,fn):
    counts['attempted_'+stage]+=1
    try:fn();counts['passed_'+stage]+=1
    except Exception as e:
        row=dict(stage=stage,location=location,type=type(e).__name__,reason=str(e)[:1500]);errors.append(row)
        if len(errors)<=12:print('AUDIT_ISSUE '+json.dumps(row,ensure_ascii=False),flush=True)
def require(condition,label):
    assert condition,label
def inspect_branch(b,i,prefix,context):
    loc=dict(book_id=prefix['book_id'],branch=i)
    if i==0:context['ids']={sem.request_id(r):r for r in b['requests']}
    ids=context['ids'];priority=prefix['N_priority']
    check('branch_hash',loc,lambda:require(sem.digest({k:b[k] for k in ('retained','requests','plan','event_reserved','bar_q_C')})==b['branch_id'],'branch_payload_hash'))
    check('reference_arithmetic',loc,lambda:sem.reference(b))
    check('close_projection_rows',loc,lambda:sem.quantities(b['close_projection'],b,ids))
    def membership():
        assert b['deletion_index']==i and b['retained']==priority[:len(priority)-i],'fixed_nested_deletion'
        rs={sem.request_id(r):r for r in b['requests']};assert len(rs)==len(b['requests'])
        assert set(rs)=={k for k,r in ids.items() if not sem.new_seed(r) or k in b['retained']},'native_branch_membership'
        assert set(b['bar_q_C'])==set(ids)
        for k,r in rs.items():
            for field in ('sid','kind','signal_day','birth_type','ticket_id','round_id','cp_id','cp_date','event_id','origin','nav0','budget','allocation_phase'):
                assert r.get(field)==ids[k].get(field),('branch_identity',k,field)
        for k in ids:
            r=rs.get(k);bar=min(r['planned_q'],r['capacity'],r.get('_ref_q',0),r.get('econ_q',r['planned_q'])) if r else 0
            assert bar==b['bar_q_C'][k],('bar_q',k)
    check('branch_membership_and_bar',loc,membership)
    proj=b['close_projection'];ref=b['plan']['reference']
    return dict(branch_id=b['branch_id'],retained=b['retained'],request_ids=[sem.request_id(r) for r in b['requests']],bar_q_C=b['bar_q_C'],close_projection={k:proj[k] for k in ('q','y','cash_after')},close_comparison=b['close_comparison'],deletion_index=b['deletion_index'],plan=dict(transfer_plan=b['plan']['transfer_plan']),reference_summary=dict(D_total=sum((D(v) for v in ref['D'].values()),Z),expansion_budget=ref['expansion_budget'],unallocated=ref['unallocated_expansion_budget'],reference_status=ref['status'],reference_sha256=sem.digest(ref)))
def main(candidate, output):
    global P,O,errors,counts,plans,quantities,deviations,daychecks
    P=Path(candidate);O=Path(output);au.O=O
    errors=[];counts=Counter();plans=[];quantities=[];deviations=[];daychecks=[]
    started=time.time()
    ledger=read(P/'DAY_LEDGER.json');end=ledger[-1]['day'];days=[x['day'] for x in ledger];orders=read(P/'ORDERS.json');transfers=read(P/'TRANSFERS.json');waits=read(P/'FUNDING_WAIT_LOG.json')
    ds=read(P/'FUNDING_OPEN_DECISIONS.json');dm={x['day']:x for x in ds};db={x['book_id']:x for x in ds};actual=read(P/'FUNDING_ACTUAL_DIAGNOSTICS.json');am={x['day']:x for x in actual};pf=read(P/'FUNDING_PREFLIGHT.json');pm={x['day']:x for x in pf}
    ob=au.bykey(orders,'day');tb=au.bykey(transfers,'day');wb=au.bykey(waits,'day');rules=read(au.RULES);proxies=read(au.PROTOCOL)['approved_proxy_ids'];stable={};bookdays=[];maxraw=0
    check('decision_inventory',end,lambda:require(set(dm)==set(days[1:]) and len(dm)==len(ds) and set(am)==set(dm) and set(pm)==set(days),'certified_decision_inventory'))
    for book in iter_books(P/'FUNDING_BRANCH_BOOKS.json.gz',inspect_branch):
        day=book['close_day'];bookdays.append(day);maxraw=max(maxraw,book['_max_raw_branch_chars']);ids={sem.request_id(r):r for r in book['original_requests']};branches=book['branches'];priority=book['N_priority'];shadow=branches[-1];loc=dict(close_day=day,book_id=book['book_id'])
        def meta():
            assert len(ids)==len(book['original_requests']) and set(ids)==set(book['_context']['ids']),'original_request_inventory'
            assert book['_stream_content_sha256']==book['book_id'],'stream_canonical_book_hash'
            assert len(branches)==len(priority)+1 and len(set(priority))==len(priority)
            assert set(priority)=={k for k,r in ids.items() if sem.new_seed(r)}
            assert set(book['A'])=={k for k,r in ids.items() if sem.protected(r)}
            assert book['scratch_integrity']['before']==book['scratch_integrity']['after'] and book['scratch_integrity']['passed'] is True
            for k,r in ids.items():
                orig=book['_context']['ids'][k]
                for field in ('sid','kind','signal_day','birth_type','ticket_id','round_id','cp_id','cp_date','event_id','origin','nav0','budget','allocation_phase'):assert r.get(field)==orig.get(field)
            prefix=book['close_conditional_prefix']
            assert sem.digest([day,'CLOSE',prefix['actual_cash_before'],prefix['actual_receivable'],book['H']])==book['health_snapshot_id']
        check('book_hash_identity_snapshot',loc,meta)
        check('close_health_arithmetic',loc,lambda:sem.health(book['H'],'CLOSE',day,rules,proxies))
        passing=[]
        for i,b in enumerate(branches):
            want=sem.comparison(b['close_projection'],shadow['close_projection'],book['H'],book['A'])
            check('close_nondisplacement',dict(close_day=day,branch=i),lambda b=b,want=want:sem.equivalent_comparison(b['close_comparison'],want))
            if want['passed']:passing.append(i)
        check('close_first_passing',loc,lambda:require(passing and book['selected_close_index']==passing[0] and passing[-1]==len(priority) and not shadow['retained'],'close_first_pass_or_empty_shadow'))
        plan=dict(close_day=day,book_id=book['book_id'],N_full=len(priority),CLOSE_deleted=book['selected_close_index'],N_CLOSE_selected=len(priority)-book['selected_close_index'],branch_count=len(branches),CLOSE_failed_branches=len(branches)-len(passing),full_D=branches[0]['reference_summary']['D_total'],selected_CLOSE_D=branches[book['selected_close_index']]['reference_summary']['D_total'],shadow_D=shadow['reference_summary']['D_total'])
        counts['books']+=1;counts['branches']+=len(branches)
        if book['book_id'] in db:
            d=db[book['book_id']];od=d['day'];a=am[od];prefix=d['common_conditional_prefix'];chosen=branches[d['selected_index']];p0=d['shadow_projection']
            def open_identity():
                assert od==book['next_day'] and d['selected_branch_id']==chosen['branch_id']
                assert sem.digest([od,'OPEN',prefix,d['H']])==d['health_snapshot_id']
                assert d['scratch_integrity']['before']==d['scratch_integrity']['after'] and d['scratch_integrity']['passed'] is True
                inv={lid:q for v in prefix['conditional_inventory'].values() for lid,q in v.items()};assert inv=={k:v['quantity'] for k,v in d['H'].items()}
                near(D(prefix['actual_cash_before'])+sm(prefix['predicted_prefix_orders'],'cash_delta'),prefix['predicted_cash_after'],'common_prefix_cash')
                allowed=[i for i,b in enumerate(branches) if i>=book['selected_close_index'] and b['close_comparison']['passed']]
                assert d['selected_index'] in allowed
                assert [e['index'] for e in d['evaluated']]==allowed[:allowed.index(d['selected_index'])+1],'not_first_frozen_passing_suffix'
                assert d['chosen_projection']==d['evaluated'][-1]['projection']
                if not chosen['retained']:assert d['chosen_projection']==p0
                assert d['selection_before_actual_orders']==sum(x['day']<od for x in orders)
            check('open_identity_prefix_selection',dict(day=od),open_identity)
            check('open_health_arithmetic',dict(day=od),lambda:sem.health(d['H'],'OPEN',od,rules,proxies))
            check('open_shadow_projection',dict(day=od),lambda:sem.quantities(p0,shadow,ids))
            for e in d['evaluated']:
                b=branches[e['index']];eloc=dict(day=od,branch=e['index'])
                check('open_native_projection_rows',eloc,lambda b=b,e=e:sem.quantities(e['projection'],b,ids))
                def oq(e=e,b=b):
                    assert e['branch_id']==b['branch_id'] and e['health_snapshot_id']==d['health_snapshot_id']
                    want=sem.comparison(e['projection'],p0,d['H'],book['A']);sem.equivalent_comparison(e['comparison'],want)
                    assert want['passed']==(e['index']==d['selected_index'])
                check('open_nondisplacement',eloc,oq)
            def preflight():
                p=pm[od];assert {x['sid'] for x in p['original_pending']}<=set(p['original_targets'])
                assert set(book['preflight_original_targets'])<=set(p['original_targets']),'original_preflight_shrunk'
            check('preflight_coverage',dict(day=od),preflight)
            lookup={(r['sid'],r['kind'],r['signal_day'],r.get('cp_id')):k for k,r in ids.items()};qq={k:0 for k in ids}
            for x in ob[od]:
                if x['side'].startswith('BUY'):
                    key=(x['sid'],x['side'][4:],x['signal_day'],x.get('cp_id'))
                    if key not in lookup:errors.append(dict(stage='actual_unfrozen_request',location=od,reason=str(key)));continue
                    qq[lookup[key]]+=x['qty']
            yy={x['lot_id']:x['executed_q'] for x in tb[od] if x.get('event')=='DONOR_EXECUTION'}
            qdev={k:qq.get(k,0)-d['chosen_projection']['q'].get(k,0) for k in set(qq)|set(d['chosen_projection']['q']) if qq.get(k,0)!=d['chosen_projection']['q'].get(k,0)}
            ydev={k:yy.get(k,0)-d['chosen_projection']['y'].get(k,0) for k in set(yy)|set(d['chosen_projection']['y']) if yy.get(k,0)!=d['chosen_projection']['y'].get(k,0)}
            def actual_checks():
                assert a['diagnostic_only'] is True and a['reselected'] is False and a['selected_branch_id']==d['selected_branch_id']
                assert a['actual_orders']==[{k:v for k,v in x.items() if k!='sector51'} for x in ob[od]],'actual_order_economic_fields' # Export adds sector51 classification only.
                assert qq==a['actual_q'] and yy==a['actual_y'],'actual_quantity_summary'
                assert qdev==a['q_deviation'] and ydev==a['y_deviation']
                assert all(not q or k in chosen['request_ids'] for k,q in qq.items())
                assert all(q<=chosen['bar_q_C'][k] for k,q in qq.items())
                donor={x['lot_id']:x for x in chosen['plan']['transfer_plan']}
                for k,q in yy.items():assert k in donor and q<=donor[k]['max_q']
                near(D(prefix['actual_cash_before'])+sm(a['actual_prefix_orders'],'cash_delta'),a['actual_prefix_cash'],'actual_prefix_cash')
                near(D(a['actual_prefix_cash'])-D(prefix['predicted_cash_after']),a['prefix_cash_deviation'],'prefix_cash_difference')
            check('actual_order_projection_binding',dict(day=od),actual_checks)
            invdiff=a['actual_prefix_inventory']!=prefix['conditional_inventory']
            if qdev or ydev or invdiff or D(a['prefix_cash_deviation'])!=0:
                deviations.append(dict(day=od,q_deviation=qdev,y_deviation=ydev,prefix_cash_deviation=a['prefix_cash_deviation'],prefix_inventory_difference=invdiff,reasons=a['deviation_reasons'],no_fill_events=a['no_fill_events'],diagnostic_only=True))
            for w in wb[od]:
                def wait_check(w=w):
                    r=w['original_request'];rid=sem.request_id(r);assert rid==w['request_id'] and sem.new_seed(r)
                    assert rid in priority and rid not in chosen['retained'],'wait_must_be_removed_N'
                    assert w['selected_branch_id']==d['selected_branch_id'] and w['actual_quantity']==0 and w['new_round_created'] is False
                    assert not qq.get(rid,0)
                    key=(r['sid'],r['signal_day'],r['birth_type']);basis=(r['nav0'],r['budget'],r['origin'])
                    if key in stable:assert stable[key]==basis,'wait_reset_NAV_budget_origin'
                    stable[key]=basis
                    if w['reason']=='FUNDING_NONDISPLACEMENT_WAIT':assert w['status']=='RETAINED' and w['original_open_check']=='PASS' and w.get('has_lot') is False
                check('wait_identity_budget_no_fill',dict(day=od,request_id=w['request_id']),wait_check)
            for k,r in ids.items():
                quantities.append(dict(day=od,kind='RECEIVER',identity=k,sid=r['sid'],signal_day=r['signal_day'],request_kind=r['kind'],allocation_phase=r['allocation_phase'],protected=k in book['A'],full_C_q=branches[0]['close_projection']['q'][k],shadow_C_q=shadow['close_projection']['q'][k],selected_C_q=chosen['close_projection']['q'][k],selected_bar_q_C=chosen['bar_q_C'][k],shadow_O_q=p0['q'][k],selected_O_q=d['chosen_projection']['q'][k],actual_q=qq[k]))
            for k in set(d['H'])|set(yy)|set(p0['y'])|set(d['chosen_projection']['y']):
                h=d['H'].get(k,{})
                quantities.append(dict(day=od,kind='DONOR',identity=k,sid=h.get('sid'),round_id=h.get('round_id'),healthy=h.get('H'),healthy_CLOSE=book['H'].get(k,{}).get('H'),full_C_y=branches[0]['close_projection']['y'].get(k,0),shadow_C_y=shadow['close_projection']['y'].get(k,0),selected_C_y=chosen['close_projection']['y'].get(k,0),shadow_O_y=p0['y'].get(k,0),selected_O_y=d['chosen_projection']['y'].get(k,0),actual_y=yy.get(k,0)))
            plan.update(OPEN_day=od,OPEN_total_deleted=d['selected_index'],OPEN_additional_deleted=d['selected_index']-book['selected_close_index'],N_OPEN_selected=len(priority)-d['selected_index'],OPEN_selected_branch=d['selected_branch_id'],OPEN_evaluated_branches=len(d['evaluated']),shadow_predicted_cash=p0['cash_after'],selected_predicted_cash=d['chosen_projection']['cash_after'],actual_cash_after=a['actual_cash_after'],conditional_H_lots=sum(h['H'] for h in d['H'].values()),actual_prefix_H_lots=sum(h['H'] for h in a['actual_prefix_H_diagnostic_only'].values()))
        else:assert day==end and book['next_day']>end,'missing_committed_OPEN_decision'
        plans.append(plan);daychecks.append(dict(close_day=day,branches=len(branches),issues_so_far=len(errors),max_raw_branch_chars=book['_max_raw_branch_chars']))
        print('BOOK_AUDITED '+json.dumps(daychecks[-1],ensure_ascii=False),flush=True)
        save('STREAM_AUDIT_PROGRESS',dict(completed_books=len(bookdays),last_book=day,counts=dict(counts),errors=errors,elapsed_seconds=time.time()-started))
        del book
    check('book_inventory',end,lambda:require(bookdays==days,'certified_book_days'))
    cps=[x for x in read(P/'CP_EVENTS.json') if x['event']=='CONSUMED_ON_FILL'];adds=[x for x in orders if x['side']=='BUY_ADD']
    check('CP_actual_once',end,lambda:require(Counter((x['day'],x['round_id'],x['cp_id']) for x in cps)==Counter((x['day'],x['round_id'],x['cp_id']) for x in adds) and all(v==1 for v in Counter(x['cp_id'] for x in cps).values()),'CP_consumption'))
    ev=read(P/'EVENT_LOG.json');attempt=[x for x in ev if x['event']=='PRIORITY_REAL_OPEN_ATTEMPT'];spent=[x for x in ev if x['event']=='ACTUAL_SEED_CAPITAL_CONSUMED'];seeds=[x for x in orders if x['side']=='BUY_SEED' and x.get('allocation_phase') in ('EVENT','RESIDUAL')]
    def event_checks():
        assert all(v==1 for v in Counter(x['event_id'] for x in attempt).values())
        key=lambda x:(x['day'],x['sid'],x['event_id'],x['qty'])
        by={key(x):x for x in spent};assert len(by)==len(spent)==len(seeds)
        for x in seeds:
            e=by[key(x)];near(-D(x['cash_delta']),e['actual_cost'],'event_cost');near(D(e['spent_after'])-D(e['spent_before']),e['actual_cost'],'event_increment')
        for eid,e in read(P/'EVENT_REGISTRY.json').items():near(sum((D(x['actual_cost']) for x in spent if x['event_id']==eid),Z),e['spent'],'event_spent_once')
    check('EVENT_actual_once',end,event_checks)
    gaps=[x['day'] for x in deviations if not x['reasons'] and not any(e.get('event') in ('SELL_NO_FILL','DONOR_NO_FILL','BUY_NO_FILL') for e in x['no_fill_events'])]
    for day in gaps:errors.append(dict(stage='unexplained_actual_deviation',location=day))
    save('FUNDING_PLAN_SELECTION_AUDIT',plans);save('FUNDING_QUANTITY_COMPARISON',quantities);save('ACTUAL_PREDICTION_DEVIATIONS',deviations);save('STREAM_BRANCH_AUDIT_ERRORS',errors)
    result=dict(verdict='PASS_ALL_CERTIFIED_SAVED_BRANCH_SEMANTICS' if not errors else 'SAVED_BRANCH_AUDIT_ISSUES',common_end=end,counts=dict(counts),issues=len(errors),actual_deviation_days=len(deviations),unexplained_deviation_days=gaps,max_raw_branch_chars=maxraw,parser='One branch at a time; stream canonical book digest; no whole 7 GB JSON load',elapsed_seconds=time.time()-started,auditor_source_sha256=sha(__file__),parser_source_sha256=sha(HOME/'stream_branch_books.py'),shared_checker_sha256=sha(sem.__file__),history_executed=False,strategy_imported=False,not_covered=['Saved raw legal-demand/H provenance remains bound to independent static/poison review, not proved solely by saved q/y.','Only the declared certified output frontier is audited; economic segment eligibility is separately checked.'])
    save('SAVED_FUNDING_SEMANTICS',result);print('FINAL '+json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);args=ap.parse_args();args.output.mkdir(exist_ok=False);main(args.candidate,args.output)

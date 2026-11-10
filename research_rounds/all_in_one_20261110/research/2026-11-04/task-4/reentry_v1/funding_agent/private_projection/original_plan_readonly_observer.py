def plan(s0,intents,at,remove_confirmed60=False):
    """Original single pass/max quantity. Private reserve feedback; no fills."""
    before=digest([s0.view(),[B.intent_view(i) for i in intents]])
    b=copy.deepcopy(s0);b.remove_confirmed60=remove_confirmed60;b.migrations=[]
    a=AccountView(b);runner=NS(sector_by_sid=b.sector_by_sid);orders=[];attempts=[];done=set();validations=[]
    for src in sorted(intents,key=B.key):
        i=copy.deepcopy(src);sid=i['sid'];x=i.get('_preview');key=B.bid(i)
        if sid in done or sid in s0.pending_sells or any(o.stock==sid and o.qty>0 and o.status in ['open','cancel_pending'] for o in s0.orders.values()):
            attempts.append(dict(sid=sid,role=i['role'],skip=True));continue
        if x is None:
            attempts.append(dict(sid=sid,role=i['role'],result=i['_preview_failure']));continue
        b.context=key;b.phase='evaluation';pre=copy.deepcopy(b);pre_available=a.available
        observe_pre(a,i,at)
        result,why=ROUTES[remove_confirmed60](runner,a,i,x,at)
        if result:
            q,pool=result
            # Native route/request already checked all rules; independently
            # inspect the retained numerical predicates at the admission clock.
            pending_fees=sum(o.qty*o.fee_per_share for o in pre.orders.values() if o.status in ['open','cancel_pending'])
            fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value)
            nav=pre.nav-pending_fees-float(fee);cap=q*float(x['price']);risk=q*max(0.,float(x['price']-x['floor']))
            # route migration changes only pool, so sector/global checks use pre.
            sc,sr,_=pre.resources(sector=pre.sector_by_sid[sid]);s=pre.sectors[pre.sector_by_sid[sid]]
            pc,pr,_=b.resources(pool);new=b.orders[i['budget_order']]
            assert x['rule'].buy_floor(q)==q and 0<q<=x['maxq'] and D(q)*x['price']<=i['budget']
            assert cap+float(fee)<=min(float(pre_available-a.current_nav*D('.1')),pre.cash-pre.resources()[2])+1e-7
            assert sc+cap<=(.02 if pool=='probe' else (.02,.1,.2)[s.level])*nav+1e-7
            assert sr+risk<=.01*nav+1e-7
            assert a.quantity(sid)*float(x['known_open'])+cap<=.10*float(a.current_nav)+1e-7
            if pool=='probe':assert pc<=.10*nav+1e-7 and pr<=.005*nav+1e-7
            elif not remove_confirmed60:assert pc<=.60*nav+1e-7
            assert new.role==i['role'] and new.floor==float(x['floor'])
            paid=a.reserve_private(i,q,pool,x);assert paid==fee
            orders.append(B.order_record(i,q,pool,x,fee));done.add(sid)
            attempts.append(dict(sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
            validations.append(dict(key=key,quantity=q,pool=pool,capital=cap,risk=risk,fee=fee,budget_NAV=nav,all_retained_admission_guards_passed=True))
        else:attempts.append(dict(sid=sid,role=i['role'],result=why))
    assert before==digest([s0.view(),[B.intent_view(i) for i in intents]])
    for oid,o in s0.orders.items():assert b.orders[oid]==o
    return dict(orders=orders,attempts=attempts,migrations=b.migrations,validations=validations,final_state=serial(b.view()),
        capital=b.resources()[0],nominal_risk=b.resources()[1],cash_reserve=b.resources()[2],available=a.available,
        fees=sum((x['fee'] for x in orders),D(0)),input_sha256=before,inputs_unchanged=True,
        native_Account_initializations=0,real_fills=0,new_financial_paths=0,not_PnL=True)

def plan(s0,intents,at,mode='two_pass'):
    assert mode in ['single_pass','two_pass']
    before=digest([s0.view(),[intent_view(i) for i in intents]])
    b=copy.deepcopy(s0);b.migrations=[];a=AccountView(b);runner=NS(sector_by_sid=b.sector_by_sid);orders=[];attempts=[];rejected=[];done=set();input_by={bid(i):i for i in intents}
    for source in sorted(intents,key=key):
        i=copy.deepcopy(source);sid=i['sid'];x=i.get('_preview')
        if sid in done:
            rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason='same_stock_earlier_role_reserved'));continue
        if sid in s0.pending_sells or any(o.stock==sid and o.qty>0 and o.status in ['open','cancel_pending'] for o in s0.orders.values()):
            rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason='original_pending_buy_or_exit'));continue
        if x is None:
            rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason=i['_preview_failure']));continue
        b.context=bid(i);b.phase='evaluation';n=len(b.migrations)
        if mode=='single_pass':
            result,why=NATIVE_ROUTE(runner,a,i,x,at)
            if result:
                q,pool=result;fee=a.reserve_private(i,q,pool,x);orders.append(order_record(i,q,pool,x,fee));done.add(sid)
        else:
            result,why=EVAL_ROUTE(runner,a,i,x,at)
            if result:
                q=x['minq'] if result['pool']=='probe' else result['quantity'];pool=result['pool']
                r,why=reserve_fixed(a,i,x,q,pool,at)
                if why:raise AssertionError(('private minimum reservation failed',bid(i),why))
                orders.append(r);done.add(sid)
        new=b.migrations[n:]
        attempts.append(dict(key=bid(i),eval_migrate=any(z['phase']=='evaluation' for z in new)))
        if why:rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason=why))
    first_pass=copy.deepcopy(orders);expected=copy.deepcopy(b.migrations);first_pass_migrations=copy.deepcopy(b.migrations)
    if mode=='two_pass':
        initial=fixed_validation(s0,intents,attempts,orders,at,expected)
        if not initial['valid']:raise AssertionError(('initial fixed plan invalid',initial['failures']))
        for old in list(orders):
            if old['pool']!='probe':continue
            i=input_by[old['key']];x=i['_preview'];lo=(old['quantity']-x['minq'])//x['rule'].buy_step;hi=(x['maxq']-x['minq'])//x['rule'].buy_step
            def trial(k):
                q=x['minq']+k*x['rule'].buy_step;fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);candidate=order_record(i,q,'probe',x,fee);os=[candidate if z['key']==old['key'] else z for z in orders]
                return os,fixed_validation(s0,intents,attempts,os,at,expected)
            while lo<hi:
                mid=(lo+hi+1)//2;_,v=trial(mid)
                if v['valid']:lo=mid
                else:hi=mid-1
            orders,v=trial(lo);assert v['valid']
        final=fixed_validation(s0,intents,attempts,orders,at,expected);assert final['valid'];b=final['state'];a=AccountView(b);a.available=final['available']
    after=digest([s0.view(),[intent_view(i) for i in intents]]);assert before==after
    return dict(mode=mode,orders=orders,first_pass=first_pass,first_pass_migrations=first_pass_migrations,rejected=rejected,attempts=attempts,migrations=b.migrations,final_state=serial(b.view()),input_before_sha256=before,input_after_sha256=after,available=a.available,capital=b.resources()[0],nominal_risk=b.resources()[1],cash_reserve=b.resources()[2],fees=sum((z['fee'] for z in orders),Z),proposed_stock_receipt_consumptions=sorted(b.consumed-s0.consumed),original_inputs_unchanged=True,native_Account_constructed=False,real_submissions=0,real_fills=0)

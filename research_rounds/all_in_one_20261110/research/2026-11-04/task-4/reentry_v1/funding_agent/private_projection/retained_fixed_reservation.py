def reserve_fixed(a,i,x,q,pool,at):
    if x['rule'].buy_floor(q)!=q or not 0<q<=x['maxq'] or D(q)*x['price']>i['budget']:
        return None,'original_minimum_step_or_frozen_target'
    if i['role']=='core' and LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value)>i['risk_budget']:
        return None,'original_core_risk'
    predicate=fixed_predicate(a,i,x,at,pool)
    if predicate(q,True):return None,','.join(predicate(q,True))
    b=a.budget;fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);bar=J.ordinal(i['clock'].decision_at.date());sector=b.sector_by_sid[i['sid']]
    b.phase='request';result=b.request(bid(i),i['sid'],sector,q,float(x['price']),float(x['floor']),token_for(b,i),bar,float(fee/D(q)),probe_request=pool=='probe',role=i['role'],order_expiry_bar=J.ordinal(at.date()),core_epoch_locked=i['role']=='core' and a.core_epoch.get(i['sid'])==i['epoch'])
    if result!='reserved':return None,result
    a.reserve_private(i,q,pool,x);return order_record(i,q,pool,x,fee),None

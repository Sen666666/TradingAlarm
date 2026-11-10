"""Only the approved per-receipt C2 gross upper bound. No financial events."""
from pathlib import Path
from decimal import Decimal as D
import sys,copy,json,hashlib
O=Path(__file__).resolve().parent
CROOT=O.parent/'g-s-C-industry-first-projection-v1-20261102'
DESIGN=O.parent/'g-s-C-mobile-step-size-design-20261102/DESIGN_DIFF.txt'
sys.path.insert(0,str(CROOT))
import c_selector as C
J=C.J
CONTRACT_SHA='0ddfbaa8fe3b5cfc4d057de9767cca6c3cc0269870942538c0570231ba74ec07'
C_SHA='8a4b89cec342763f922ae65b3d138792cc6945f452595d86a263f5c0b15bc130'
sha=C.sha;read=C.read;save=C.save

def guard():
    C.guard()
    assert sha(CROOT/'c_selector.py')==C_SHA,'C10 selector source changed'
    assert sha(DESIGN)==CONTRACT_SHA,'size amendment changed'

def cap2(s,ds):
    J.schema(s,ds);before=J.digest((s,ds));dd=copy.deepcopy(ds);rows=[]
    for old,d in zip(ds,dd):
        if d['role']!='mobile':raise ValueError('C2 scope is mobile demands only')
        p=D(d['mark'])*(D(1)+C.B.SLIP)
        if not p.is_finite() or p<=0:raise ValueError('unknown/nonpositive saved price')
        rule=J.rule(d['quantity']);budget=D('.02')*D(s['decision_nav'])
        raw=int(budget/p);q2=rule.buy_floor(raw);d['max_q']=min(old['max_q'],q2)
        rows.append(dict(sid=d['sid'],receipt_id=d['receipt_id'],decision_NAV=s['decision_nav'],known_price=p,
            original_C10_max_q=old['max_q'],original_2pct_gross_budget=budget,raw_2pct_shares=raw,
            legal_2pct_max_q=q2,C2_max_q=d['max_q'],minimum=rule.buy_minimum,step=rule.buy_step,
            target_minlot_lost=bool(old['max_q']>=rule.buy_minimum and d['max_q']==0)))
    recovered=copy.deepcopy(dd)
    for a,b in zip(recovered,ds):a['max_q']=b['max_q']
    assert J.digest(recovered)==J.digest(ds),'more than max_q changed'
    assert J.digest((s,ds))==before
    return dd,rows

def solve_C2(s,ds,e,**kwargs):
    guard();before=J.digest((s,ds,e));dd,rows=cap2(s,ds)
    _,_,k0=C.transform(s,ds,e);_,_,k2=C.transform(s,dd,e)
    assert k0['stock_priority']==k2['stock_priority'] and k0['industry_order']==k2['industry_order']
    r=C.solve_C(s,dd,e,**kwargs);base=r.pop('result_id')
    r.update(policy='C_INDUSTRY_FIRST_MOBILE_2PCT',C2_base_C_result_id=base,
        C2_selector_sha256=sha(__file__),C2_amendment_sha256=CONTRACT_SHA,
        C10_original_snapshot_sha256=J.digest(s),C10_original_demands_sha256=J.digest(ds),
        C2_converted_demands_sha256=J.digest(dd),C2_upper_bounds=rows,
        same_qualification_priority_receipt_and_resources=True,submit_allowed=False,financial_events=0)
    r['result_id']=J.digest(r);assert J.digest((s,ds,e))==before
    return r

def verify(x,r):
    guard()
    assert r['result_id']==J.digest({k:v for k,v in r.items() if k!='result_id'}),'result body changed'
    assert r['C2_selector_sha256']==sha(__file__),'C2 source binding changed'
    assert r['C2_amendment_sha256']==CONTRACT_SHA
    assert r['C10_original_snapshot_sha256']==J.digest(x['snapshot'])
    assert r['C10_original_demands_sha256']==J.digest(x['B_demands'])
    dd,rows=cap2(x['snapshot'],x['B_demands'])
    assert r['C2_upper_bounds']==json.loads(json.dumps(rows,default=str))
    assert r['C2_converted_demands_sha256']==J.digest(dd)
    C.verify_result(dict(snapshot=x['snapshot'],B_demands=dd,industry_evidence=x['industry_evidence']),r)
    return True

if __name__=='__main__':
    ip=Path(sys.argv[1]);assert sha(ip)==sys.argv[2],'trusted input bytes changed'
    x=read(ip);r=read(sys.argv[3]);verify(x,r)
    fresh=solve_C2(x['snapshot'],x['B_demands'],x['industry_evidence'])
    assert fresh['result_id']==r['result_id'],'pure C2 restart differs'
    save(sys.argv[4],dict(exact=True,result_id=fresh['result_id'],Q=fresh['Q'],D=fresh['D'],financial_events=0))

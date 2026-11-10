"""Original C10 ordering/targets with one additional full-D budget predicate."""
from pathlib import Path
import sys,copy,json,hashlib,importlib.util
from decimal import Decimal as D
O=Path(__file__).resolve().parent;CROOT=O.parent/'g-s-C-industry-first-projection-v1-20261102'
DESIGN=O.parent/'g-s-C-batch20-migration-design-20261102/CONTRACT_PROPOSAL.txt'
sys.path.insert(0,str(CROOT));import c_selector as C
sys.path.insert(0,str(O));from batch_book import BatchBook
J=C.J;read=C.read;save=C.save;sha=C.sha
CONTRACT_SHA='32a12526cf267ba7b1c3fe480269b45cc83db9855dd0c1397b45248b95fe9472'
C_SHA='8a4b89cec342763f922ae65b3d138792cc6945f452595d86a263f5c0b15bc130'

def guard():
    C.guard();assert sha(CROOT/'c_selector.py')==C_SHA
    assert sha(DESIGN)==CONTRACT_SHA
    assert sha(O/'frozen_selector.py')==C.BASE_SHA

def new_book(s):
    # Ratio 1 is the book's current-raw-quantity anchor, not an assumption about
    # the security's historical adjustment factor (already applied in s).
    lines=[dict(layer=str(z['id']),sid=z['sid'],qty=z['qty'],opp=0,mandatory=0,relative_ratio='1') for z in s['lots']]
    b=BatchBook(s['account_id'],J.digest(s),lines)
    b.begin(s['at'],s['decision_nav'],{str(z['id']):z['mark'] for z in s['lots']})
    return b

def solve_C20(s,ds,e,book=None,**kwargs):
    guard();before=J.digest((s,ds,e));book=book or new_book(s);book_before=book.dumps()
    if book.batch['cursor']!=s['at'] or D(book.batch['NAV'])!=D(s['decision_nav']):raise ValueError('budget decision binding mismatch')
    if book.account_id!=s['account_id'] or book.source_binding!=J.digest(s):raise ValueError('budget account/snapshot binding')
    ss,dd,audit=C.transform(s,ds,e)
    # A private byte-identical module instance; the original B/C module globals
    # and files are never modified. Only this instance's predicate is extended.
    spec=importlib.util.spec_from_file_location('private_C_BATCH20_evaluator',O/'frozen_selector.py')
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    native_evaluate=engine.evaluate
    native_upper=engine.necessary_upper
    def bounded_upper(s0,d0,Q,d,plan):
        a=book.preview({str(p['layer']):p['q'] for p in plan['rows']})
        if not a['ok']:return 0,['opportunity_gross_batch20']
        return native_upper(s0,d0,Q,d,plan)
    def bounded_evaluate(s0,d0,Q,Dmap):
        r=native_evaluate(s0,d0,Q,Dmap)
        requests={str(p['layer']):p['q'] for p in r['donors']['rows']}
        a=book.preview(requests)
        r['batch20']=a
        check=dict(stage='full_batch_D',constraint='opportunity_gross_batch20',value=str(D(a['carry'])+D(a['already_new'])+D(a['additional'])),limit=a['limit'],residual=a['residual'])
        r['validation']['checks'].append(check)
        if not a['ok']:r['validation']['ok']=False;r['validation']['violations'].append('opportunity_gross_batch20')
        return r
    engine.evaluate=bounded_evaluate
    engine.necessary_upper=bounded_upper
    result=engine.solve_B(ss,dd,**kwargs);underlying=result.pop('result_id')
    assert book.dumps()==book_before,'shadow search spent budget'
    requests={str(p['layer']):p['q'] for p in result['donors']['rows']}
    working=BatchBook.loads(book_before,trusted_sha256=hashlib.sha256(book_before.encode()).hexdigest(),account_id=book.account_id,
        source_binding=book.source_binding,actual_commitments=book.commitments())
    working.approve(book.batch['id']+'|complete_target_plan',requests,target_binding=J.digest(dict(Q=result['Q'],receipts=[d['receipt_id'] for d in ds])))
    after=working.dumps()
    result.update(policy='C_BATCH20',base_private_B_result_id=underlying,C_rank_binding=audit,
        C_selector_sha256=C_SHA,C_contract_sha256=C.CONTRACT_SHA,industry_evidence_sha256=J.digest(e),
        batch20_selector_sha256=sha(__file__),batch_book_sha256=sha(O/'batch_book.py'),batch20_contract_sha256=CONTRACT_SHA,
        frozen_B_copy_sha256=sha(O/'frozen_selector.py'),budget_before=book_before,budget_after=after,
        budget_after_sha256=hashlib.sha256(after.encode()).hexdigest(),target_policy_no_change=True,
        source_joint_guard_unchanged=True,submit_allowed=False,financial_events=0)
    result['result_id']=J.digest(result)
    assert J.digest((s,ds,e))==before and book.dumps()==book_before
    return result

def verify(x,r):
    guard();assert r['result_id']==J.digest({k:v for k,v in r.items() if k!='result_id'})
    assert r['batch20_selector_sha256']==sha(__file__) and r['batch_book_sha256']==sha(O/'batch_book.py')
    assert r['batch20_contract_sha256']==CONTRACT_SHA and r['frozen_B_copy_sha256']==C.BASE_SHA
    C.verify_result(x,r)

if __name__=='__main__':
    ip=Path(sys.argv[1]);assert sha(ip)==sys.argv[2]
    x=read(ip);r=read(sys.argv[3]);verify(x,r)
    fresh=solve_C20(x['snapshot'],x['B_demands'],x['industry_evidence'])
    assert fresh['result_id']==r['result_id']
    save(sys.argv[4],dict(exact=True,Q=fresh['Q'],D=fresh['D'],result_id=fresh['result_id'],financial_events=0))

"""Auditor-only arithmetic/regression checks; never imports a strategy."""
from pathlib import Path
from copy import deepcopy
import ast,json,sys
sys.dont_write_bytecode=True
import accounting_core as au
import verify_saved_funding_semantics as sem
O=Path(__file__).resolve().parent;R=O.parent
def rejected(fn):
    try:fn()
    except (AssertionError,KeyError,ValueError):return True
    return False
def main():
    count=0
    for p in O.glob('*.py'):
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,(ast.Import,ast.ImportFrom)):
                assert 'engine' not in ast.unparse(n) and 'numpy' not in ast.unparse(n) and 'pandas' not in ast.unparse(n)
        count+=1
    H={'l':{'H':True},'u':{'H':False}};A=['a'];p0={'q':{'a':100,'residual':50},'y':{'l':0}}
    assert sem.comparison({'q':{'a':100,'residual':0},'y':{'l':0,'u':900}},p0,H,A)['passed'];count+=1
    assert not sem.comparison({'q':{'a':100},'y':{'l':100}},p0,H,A)['passed'];count+=1
    assert not sem.comparison({'q':{'a':0},'y':{}},p0,H,A)['passed'];count+=1
    assert sem.comparison(p0,p0,H,A)['passed'];count+=1
    req={'sid':'S','kind':'SEED','signal_day':'2024-01-02','birth_type':'A','origin':['x','y','z']}
    r2=deepcopy(req);r2['plan_day']='2024-01-08';assert sem.request_id(req)==sem.request_id(r2);count+=1
    r2['signal_day']='2024-01-03';assert sem.request_id(req)!=sem.request_id(r2);count+=1
    ref=au.read(au.BASE/'REFERENCE_AT_END.json');plans=au.read(au.BASE/'TRANSFER_PLAN_AT_END.json')
    reqs=[dict(sid=x['sid'],kind=x['kind'],signal_day=x['signal_day'],cp_id=x.get('cp_id'),allocation_phase='MATURE') for x in ref['independent_demand_details']]
    branch=dict(requests=reqs,plan=dict(reference=ref,transfer_plan=plans,_donor_sectors=sorted({x['sector51'] for x in plans})))
    sem.reference(branch);count+=1
    bad=deepcopy(branch);s=next(iter(ref['D']));bad['plan']['reference']['D'][s]=str(au.D(ref['D'][s])+1)
    assert rejected(lambda:sem.reference(bad));count+=1
    bad=deepcopy(branch);s=next(iter(ref['X']));bad['plan']['reference']['X'][s]=str(au.D(ref['X'][s])+1)
    assert rejected(lambda:sem.reference(bad));count+=1
    result=dict(verdict='PASS_AUDITOR_ONLY_CHECKS',assertion_groups=count,scope='Parser/import boundaries, selector arithmetic, identity, original-M7 saved reference recomputation and tamper rejection. Not candidate synthetic QA, not history.',strategy_imported=False,history_executed=False,source_sha256={p.name:au.sha(p) for p in O.glob('*.py')})
    au.save('AUDITOR_SELF_CHECK',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()

"""Independent output accounting and M9 matched-window evaluation; never runs strategy."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,importlib.util,sys,datetime,ast
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent;C=R/'mainline_candidate_v9_persistent_stock_failure'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda n,x:(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
old=R/'mainline_candidate_v8_false_mainline_retirement_run_v1/evaluate_independent.py'
sp=importlib.util.spec_from_file_location('independent_output_accounting',old);v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v)
REASON='PERSISTENT_STOCK_NONPROFIT_EXPANSION_RETIREMENT';v.REASON=REASON
ap=read(O/'CONTRACT_APPROVAL.json');q=read(C/'SYNTHETIC_QA.json')
assert ap['approved'] and ap['runner_sha256']==sha(O/'run.py') and ap['engine_sha256']==sha(C/'engine.py')==q['engine_sha256']
assert ap['contract_sha256']==sha(C/'CONTRACT.md')==q['contract_sha256'] and ap['test_sha256']==sha(C/'synthetic_retirement.py')==q['test_sha256']
assert q['count']==102 and q['result']=='PASS'
deps=read(C/'DEPENDENCY_SEAL.json')['hashes'];assert all(sha(p)==h for p,h in deps.items())
src=(O/'run.py').read_text();ast.parse(src)
assert src.count('e=m.run_loop(m.Engine(data),checkpoint=False)')==1 and "data=m.Data(end='2024-11-06')" in src
status=read(O/'RUN_STATUS.json');assert status['completed_horizon'] and not status['blockers']
paths=dict(M9=O/'once_20241106',M7_oct=R/'mainline_m7_downturn_cash_batch_v6/once_20241031',M7_nov=R/'mainline_m7_long_horizon_sealed_v2/once_20260630',M8=R/'mainline_candidate_v8_false_mainline_retirement_run_v1/once_20241031')
for p in paths.values():
    h=read(p/'OUTPUT_HASHES.json');assert all(sha(p/n)==x for n,x in h.items() if n!='OUTPUT_HASHES.json')
result={}
for end in ['2024-10-31','2024-11-06']:
    a=v.evaluate(paths['M9'],end);b=v.evaluate(paths['M7_oct'] if end=='2024-10-31' else paths['M7_nov'],end)
    result[end]=dict(M9=a,M7=b,delta={k:a[k]-b[k] for k in ['NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct']})
    if end=='2024-10-31':result[end]['M8']=v.evaluate(paths['M8'],end)
orders=read(paths['M9']/'ORDERS.json');ret=[o for o in orders if o['reason']==REASON]
for o in ret:
    for lid,ev in o['retirement_evidence'].items():
        assert ev['confirmed'] and ev['consecutive']
        assert ev['prior']['round_id']==ev['current']['round_id']==o['round_id']
        assert ev['prior']['day']<ev['current']['day']<o['day']
        for obs in [ev['prior'],ev['current']]:
            assert obs['known'] and obs['observed_close'] and obs['qualifies']
            assert all(obs[k]==0 for k in ['sector_state','M','stock_state']) and D(obs['close_net'])<=0
daily=read(paths['M9']/'CANDIDATES.json')
evidence=[r for r in daily if r.get('event')=='M9_CLOSE_EVIDENCE']
marks=[r for r in daily if r.get('event')=='EXPANSION_RETIREMENT']
result['diagnostic']=dict(evidence_records=len(evidence),qualifying_observations=sum(r['current']['qualifies'] for r in evidence),confirmed_observations=sum(r['confirmed'] for r in evidence),marks=len(marks),retirement_orders=ret,source_checks='PASS',accounting='PASS',research_scope='Frozen single hypothesis, once Sep2-Nov6, already observed development window; no shared pool or live trades; not out of sample.')
save('INDEPENDENT_M9_VS_M7.json',result)
save('EVALUATION_SEAL.json',dict(evaluator_sha256=sha(__file__),accounting_helper_sha256=sha(old),result_sha256=sha(O/'INDEPENDENT_M9_VS_M7.json'),input_hashes={str(p/'OUTPUT_HASHES.json'):sha(p/'OUTPUT_HASHES.json') for p in paths.values()}))
print(json.dumps(dict(endpoint={end:dict(NAV=result[end]['M9']['NAV'],delta=result[end]['delta'],maxdd=result[end]['M9']['max_close_drawdown_pct']) for end in ['2024-10-31','2024-11-06']},diagnostic={k:v for k,v in result['diagnostic'].items() if k!='retirement_orders'},retirement_orders=len(ret)),ensure_ascii=False,default=str))

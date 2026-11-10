"""Independent saved-output M10 accounting audit; no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib,importlib.util,sys,ast
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent;C=R/'mainline_candidate_v10_positive_cp_initial_protection'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda n,x:(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
helper=R/'mainline_candidate_v8_false_mainline_retirement_run_v1/evaluate_independent.py'
sp=importlib.util.spec_from_file_location('m10_independent_accounting',helper);v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v)
REASON='POSITIVE_CP_INITIAL_PROTECTION';v.REASON=REASON
ap=read(O/'CONTRACT_APPROVAL.json');qa=read(C/'SYNTHETIC_QA.json')
assert ap['approved'] and ap['runner_sha256']==sha(O/'run.py')
assert ap['engine_sha256']==sha(C/'engine.py')==qa['engine_sha256']
assert ap['contract_sha256']==sha(C/'CONTRACT.md')==qa['contract_sha256']
assert ap['test_sha256']==sha(C/'synthetic_protection.py')==qa['test_sha256']
assert ap['evaluation_plan_sha256']==sha(R/'M10_PREDECLARED_EVALUATION.md')
assert qa['result']=='PASS' and qa['count']==85
deps=read(C/'DEPENDENCY_SEAL.json')['hashes'];assert all(sha(p)==h for p,h in deps.items())
src=(O/'run.py').read_text();ast.parse(src)
assert src.count('e=m.run_loop(m.Engine(data),checkpoint=False)')==1 and "data=m.Data(end='2024-11-06')" in src
status=read(O/'RUN_STATUS.json');assert status['completed_horizon'] and not status['blockers']
paths=dict(M10=O/'once_20241106',M7_oct=R/'mainline_m7_downturn_cash_batch_v6/once_20241031',M7_nov=R/'mainline_m7_long_horizon_sealed_v2/once_20260630',M9=R/'mainline_candidate_v9_persistent_stock_failure_run_v1/once_20241106')
for p in paths.values():
 hashes=read(p/'OUTPUT_HASHES.json');assert all(sha(p/n)==h for n,h in hashes.items() if n!='OUTPUT_HASHES.json')
result={}
for end in ['2024-10-31','2024-11-06']:
 a=v.evaluate(paths['M10'],end);b=v.evaluate(paths['M7_oct'] if end=='2024-10-31' else paths['M7_nov'],end)
 for x in [a,b]:
  x.pop('retirement',None);x.pop('retirement_rebuy',None)
 result[end]=dict(M10=a,M7=b,delta={k:a[k]-b[k] for k in ['NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct']})
orders=read(paths['M10']/'ORDERS.json');buys={o['lot_id']:o for o in orders if o['side'].startswith('BUY')}
candidates=read(paths['M10']/'CANDIDATES.json')
admissions=[r for r in candidates if r.get('event')=='M10_INITIAL_CP_ADMISSION']
accepted=[r for r in admissions if r['decision']=='ADOPT']
for r in accepted:
 lot=r['lot_id'];cp=r['new_protection'];assert buys[lot]['capital_role']=='INITIAL'
 assert r['day']>=buys[lot]['day'] and cp['receipt_day']==cp['adopted_day']==r['day']
 assert D(r['net_close'])>0 and D(r['net_at_CP'])>0 and r['candidate_is_today_valid']
 assert cp['round_id']==r['round_id'] and D(r['raw_close'])*D(r['factor'])>D(cp['floor'])
 if r['old_protection']:assert D(cp['floor'])>D(r['old_protection']['floor'])
guard_orders=[]
for o in orders:
 ids=[lid for lid,reason in o.get('lot_reasons',{}).items() if reason==REASON]
 if not ids:continue
 for lid in ids:
  ev=o['initial_protection_evidence'][lid];p=ev['protection']
  assert buys[lid]['capital_role']=='INITIAL'
  assert p['adopted_day']<o['day'] and ev['day']<=o['day']
  assert D(p['net_close'])>0 and D(p['net_at_CP'])>0
 q=sum(o['lot_quantities'][lid] for lid in ids)
 guard_orders.append(dict(order=o,extra_initial_lots=ids,extra_initial_qty=q,allocated_fee=D(o['fee'])*q/o['qty']))
holds=read(paths['M10']/'HOLDINGS.json')
for h in holds:
 if h.get('seed_cp_floor') is not None:
  assert D(h['effective_protection_signal'])==max(D(h['baseline_I_signal']),D(h['seed_cp_floor']))
diagnostic=dict(admission_records=len(admissions),adopted=len(accepted),adopted_lots=len(set(r['lot_id'] for r in accepted)),admission_reason_counts=dict(Counter(r['decision'] for r in admissions)),breach_records=sum(r.get('event')=='M10_INITIAL_BREACH' for r in candidates),protection_orders=len(guard_orders),protection_shares=sum(r['extra_initial_qty'] for r in guard_orders),orders=guard_orders,positive_CP_but_layered_pressure_nonpositive=sum(D(r['layered_pressure_after']['net'])<=0 for r in accepted),accounting='PASS',admission_and_actual_sale_evidence='PASS',scope='One offline development-window single-factor comparison. No M9 stacking. INITIAL-only, no expansion-seed protection. Static CP and layered pressure are not guaranteed fills or profits.')
result['diagnostic']=diagnostic
save('INDEPENDENT_M10_VS_M7.json',result)
save('EVALUATION_SEAL.json',dict(evaluator_sha256=sha(__file__),helper_sha256=sha(helper),result_sha256=sha(O/'INDEPENDENT_M10_VS_M7.json'),input_hashes={str(p/'OUTPUT_HASHES.json'):sha(p/'OUTPUT_HASHES.json') for p in paths.values()},predeclared_plan_sha256=sha(R/'M10_PREDECLARED_EVALUATION.md')))
print(json.dumps(dict(endpoints={d:dict(NAV=result[d]['M10']['NAV'],delta=result[d]['delta']) for d in ['2024-10-31','2024-11-06']},diagnostic={k:v for k,v in diagnostic.items() if k!='orders'}),ensure_ascii=False,default=str))

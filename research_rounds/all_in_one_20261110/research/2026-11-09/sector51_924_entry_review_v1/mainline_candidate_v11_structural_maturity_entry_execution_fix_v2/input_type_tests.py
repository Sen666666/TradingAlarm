"""Read-only scalar compatibility regression, not a market/account replay.
Only two existing canonical parquet receipt scalars are inspected.
No Data constructor, Engine, history runner, source admission or network is used.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import numpy as np
import pandas as pd

sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
OLD=O.parent/'mainline_candidate_v11_structural_maturity_entry'
CP=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/CP1/605499.SH.parquet')
CP_SHA='a9eb7ec318fac128c5ed324826b948bff568e80fc555ce22c214033173e883bd'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n,p):
    spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
sh=load('fixed_scalar_shadow',O/'shadow.py');old=load('sealed_invalid_scalar_shadow',OLD/'shadow.py')
checks=[]
def ok(n,v):
    assert v,n
    checks.append(n)


def main():
    ok('canonical_parquet_hash_unchanged',sha(CP)==CP_SHA)
    ok('engine_byte_identical_to_sealed_candidate',sha(O/'engine.py')==sha(OLD/'engine.py'))
    ok('original_27_group_tests_byte_identical',sha(O/'synthetic_tests.py')==sha(OLD/'synthetic_tests.py'))
    expected=(OLD/'shadow.py').read_text().replace('import copy\n','import copy\nimport numpy as np\n').replace(
       "    # Canonical parquet supplies numpy.bool_; integer/string sentinels are not receipts.\n    if type(value) is bool or type(value).__name__ == 'bool_':",
       "    # NumPy 2 uses the class name 'bool'; use type identity, never its display name.\n    # Integer/string sentinels are still not canonical Boolean receipts.\n    if isinstance(value, (bool, np.bool_)):")
    ok('only_boolean_type_recognition_changed',(O/'shadow.py').read_text()==expected)
    cases=[('python_true',True,1),('python_false',False,0),('numpy_true',np.bool_(True),1),('numpy_false',np.bool_(False),0),
           ('none',None,-1),('nan',np.nan,-1),('pandas_missing',pd.NA,-1),('python_int_true',1,-1),('python_int_false',0,-1),
           ('numpy_int_true',np.int64(1),-1),('numpy_int_false',np.int64(0),-1),('float_true',1.0,-1),('float_false',0.0,-1),
           ('numpy_float_true',np.float64(1),-1),('string_true','True',-1),('string_false','False',-1),('string_one','1',-1),('minus_one',-1,-1)]
    for name,value,wanted in cases:ok(name,sh.bool_state(value)==wanted)
    for dtype in ['bool','boolean']:
        series=pd.Series([True,False],dtype=dtype)
        for i,wanted in enumerate([1,0]):ok('series_'+dtype+'_'+str(i),sh.bool_state(series.iloc[i])==wanted)
    frame=pd.read_parquet(CP,columns=['receipt','ready','candidate'])
    evidence=[]
    for date,wanted in [('2024-09-26',0),('2024-09-27',1)]:
        row=frame.loc[pd.Timestamp(date)];value=row['receipt']
        ok('actual_parquet_scalar_'+date,sh.bool_state(value)==wanted)
        evidence.append(dict(day=date,repr=repr(value),type_module=type(value).__module__,type_name=type(value).__name__,
                             sealed_old_result=old.bool_state(value),fixed_result=sh.bool_state(value),expected=wanted))
    ok('old_implementation_demonstrably_wrong_for_real_scalars',all(r['sealed_old_result']==-1 for r in evidence))
    # Exercise the production shadow path with those exact scalar objects, on artificial dates/prices.
    req=dict(sid='SYNTHETIC',birth_type='B',signal_day='2001-01-01',plan_day='2001-01-01',
             nav0=sh.D(1200000),budget=sh.D(24000),origin=('synthetic','memory://type-fixture','0'),factor=sh.D(1),ifloor=sh.D(5))
    shadow=sh.new_shadow(req,'a'*64);log=[]
    f=frame.loc[pd.Timestamp('2024-09-26'),'receipt'];t=frame.loc[pd.Timestamp('2024-09-27'),'receipt']
    sh.observe_close(shadow,'2001-01-01',raw_open=10,raw_close=10,factor=1,origin=req['origin'],receipt=f,candidate=None,log=log)
    ok('real_false_scalar_is_known_no_receipt_not_unknown',sh.state(shadow)==0 and not shadow['unknown_gap'])
    sh.observe_close(shadow,'2001-01-02',raw_open=10,raw_close=10,factor=1,origin=req['origin'],receipt=t,candidate=8,log=log)
    ok('real_true_scalar_creates_slot',sh.state(shadow)==1 and any(r['event']=='CREATED' for r in log))
    sh.observe_close(shadow,'2001-01-03',raw_open=10,raw_close=10,factor=1,origin=req['origin'],receipt=f,candidate=None,log=log)
    ok('real_false_scalar_preserves_valid_slot',sh.state(shadow)==1)
    ok('no_history_started',not(O/'RUN_STARTED.json').exists())
    out=dict(result='PASS',checks=checks,assertions=len(checks),python=sys.executable,numpy=np.__version__,pandas=pd.__version__,
        actual_input= str(CP),actual_input_sha256=CP_SHA,scalar_evidence=evidence,
        history_run=False,historical_Data_instantiated=False,no_network=True,source_admission_changed=False,
        q0_guard_changed=False,formula_changed=False,old_run_classification='INVALID_IMPLEMENTATION_NOT_CANDIDATE_PERFORMANCE',
        engine_sha256=sha(O/'engine.py'),shadow_sha256=sha(O/'shadow.py'),type_tests_sha256=sha(O/'input_type_tests.py'))
    (O/'INPUT_TYPE_QA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['result','assertions','history_run','python','numpy','pandas']}))


if __name__=='__main__':main()

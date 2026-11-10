"""Read three sealed fact/CP files for scalar types only. No Data/history."""
from pathlib import Path
import importlib.util,json,sys
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('v12_input_types',O/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
def run():
    manifest=e.m4.b.U/'STOCK_MANIFEST.json'
    records=json.loads(manifest.read_text())[:3];rows=[]
    for r in records:
        f=e.pd.read_parquet(r['refs']['facts']);c=e.pd.read_parquet(r['refs']['CP1'])
        when=e.pd.Timestamp('2024-11-04');iv=f.at[when,'i_target'];cv=c.at[when,'receipt']
        assert isinstance(iv,(bool,e.np.bool_,int,e.np.integer)) and iv in (0,1)
        assert isinstance(cv,(bool,e.np.bool_))
        assert bool(e.m4.truth(iv))==(int(iv)==1)
        assert e.boolean(cv) is bool(cv)
        rows.append(dict(sid=r['symbol'],day=e.day(when),i_target_type=type(iv).__name__,i_target=int(iv),
                         original_truth=bool(e.m4.truth(iv)),receipt_type=type(cv).__name__,receipt=bool(cv),
                         facts_path=r['refs']['facts'],facts_sha256=e.sha(r['refs']['facts']),
                         cp_path=r['refs']['CP1'],cp_sha256=e.sha(r['refs']['CP1'])))
    checks={str(v):bool(e.m4.truth(v)) for v in (True,e.np.bool_(True),1,e.np.int64(1))}
    assert all(checks.values())
    result=dict(result='PASS',history_run=False,real_Data_constructed=False,scope='3 sealed inputs scalar inspection only',
                i_target_predicate='unchanged native truth/false accepts integer 0/1 and bool',
                cp_receipt_predicate='isinstance(bool,np.bool_) only',samples=rows,
                manifest_sha256=e.sha(manifest),engine_sha256=e.sha(O/'engine.py'),tests_sha256=e.sha(O/'input_type_tests.py'))
    (O/'INPUT_TYPE_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))

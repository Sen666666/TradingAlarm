"""Independent non-economic checks. Never imports or executes a historical loop."""
from pathlib import Path
import ast,copy,hashlib,json,math,random,sys,unittest
from unittest.mock import patch
import numpy as np,pandas as pd
O=Path(__file__).resolve().parents[1]
A=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(O))
import runtime,priority
from joint_policy import rank_key
from joint_engine import JointConsumer
from test_joint_engine import JointTests
from test_execution_book import ExecutionTests
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,obj):
    with Path(p).open('x') as f:json.dump(obj,f,indent=2,default=str,allow_nan=False)
def oracle(rows,features):
    original=list(rows)
    slots=[i for i,(r,c) in enumerate(original) if r['owner_lane']=='PRICE' and r['PVR_known'] is True and isinstance(r['PVR_score'],(float,int)) and math.isfinite(r['PVR_score']) and features[r['sid']] is not None and math.isfinite(features[r['sid']])]
    eligible=[original[i] for i in slots]
    eligible.sort(key=lambda rc:(-features[rc[0]['sid']],-rc[0]['PVR_score'],rc[0]['sid']))
    result=list(original)
    for slot,pair in zip(slots,eligible):result[slot]=pair
    return result
def queues():
    rng=random.Random(168172)
    for n in range(5000):
        rows=[];d={}
        for i in range(rng.randrange(31)):
            sid=f'SYN_{i:03}';lane=rng.choice(['AB','PRICE','PRICE'])
            known=lane=='AB' or rng.choice([True,False])
            p=rng.choice([-5.,0.,50.,90.,101.]) if known else rng.choice([None,float('nan'),50.])
            if lane=='PRICE' and known and rng.random()<.05:p=float('inf')
            rows.append((dict(sid=sid,day=pd.Timestamp('2022-01-04'),sector='SYN',owner_lane=lane,PVR_known=known,PVR_score=p),dict(identity=sid)))
            d[sid]=rng.choice([None,float('nan'),float('inf'),-1.,-.3,0.,.3,1.])
        rows.sort(key=lambda rc:rank_key(rc[0]))
        calls=[]
        def feature(sid,day):
            calls.append(sid);return d[sid]
        actual,audit=priority.reorder_slots(rows,feature)
        expected=oracle(rows,d)
        assert [r['sid'] for r,c in actual]==[r['sid'] for r,c in expected],n
        assert len(actual)==len(rows)==len(audit)
        assert set(calls)=={r['sid'] for r,c in rows if r['owner_lane']=='PRICE'}
        assert len(calls)==len(set(calls))
        for (r,c),rec in zip(actual,audit):
            assert c['identity']==r['sid']
            assert rec['dmi_selected']==(rec['dmi_numeric_rank']<=2)
            if not rec['mutable']:assert rec['original_numeric_rank']==rec['dmi_numeric_rank']
    return 5000
def derived_ast():
    source=ast.parse((runtime.SOURCE/'joint_engine.py').read_text())
    cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='JointConsumer')
    original={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    captured={};compiler=compile
    def capture(tree,filename,*args,**kwargs):
        if isinstance(tree,ast.Module) and len(tree.body)==1 and isinstance(tree.body[0],ast.FunctionDef):
            captured[tree.body[0].name]=copy.deepcopy(tree.body[0])
        return compiler(tree,filename,*args,**kwargs)
    with patch('builtins.compile',side_effect=capture):
        runtime.make_loop();priority.selector()
    loop=copy.deepcopy(original['run_authorized']);loop.name='isolated_loop';removed=[ast.unparse(n) for n in loop.body[:3]];loop.body=loop.body[3:]
    assert ast.dump(loop)==ast.dump(captured['isolated_loop'])
    selector=captured['select_close'];count=0
    for n in ast.walk(selector):
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='ordered' and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='rank_options':
            assert len(n.value.args)==1 and not n.value.keywords
            n.value=n.value.args[0];count+=1
    assert count==1 and ast.dump(selector)==ast.dump(original['select_close'])
    for name in ['price_entry_open','price_held_open','price_held_close','_receipt','_validate_open','_new_state','_candidate_frame','_proxy_buy']:
        assert getattr(priority.DmiConsumer,name) is getattr(JointConsumer,name)
    return dict(loop_only_removed=removed,selector_only_one_wrapper=True,all_lifecycle_methods_inherited=True)
def scalar(raw):
    cols=['open','high','low','close'];out={};previous=None;buf=[];state=None;identity=None
    for date,r in raw.iterrows():
        vals=[r[c] for c in cols]
        good=all(pd.notna(v) and math.isfinite(v) and v>0 for v in vals)
        good=good and r.high>=max(vals) and r.low<=min(vals) and pd.notna(r.segment_id)
        good=good and all(pd.notna(r[c]) and bool(r[c]) for c in ['price_eligible','observed_bar','is_observed_bar'])
        good=good and all(pd.notna(r[c]) and not bool(r[c]) for c in ['source_invalid','synthetic_event_bar'])
        ident=(r.source_kind,r.source_path,r.segment_id)
        if not good or ident!=identity:previous=None;buf=[];state=None
        value=float('nan')
        if good and previous is not None:
            up=r.high-previous.high;down=previous.low-r.low
            plus=up if up>down and up>0 else 0.
            minus=down if down>up and down>0 else 0.
            if state is None:
                buf.append((plus,minus))
                if len(buf)==14:state=(sum(x[0] for x in buf)/14,sum(x[1] for x in buf)/14)
            else:state=((13*state[0]+plus)/14,(13*state[1]+minus)/14)
            if state is not None:value=(state[0]-state[1])/(state[0]+state[1]) if state[0]+state[1]!=0 else 0.
        out[date]=value
        previous=r if good else None;identity=ident if good else None
    return out
def feature_checks():
    p=O/'features';seal=read(p/'SEAL.json')
    assert all(sha(p/n)==h for n,h in seal.items())
    inputs=read(p/'INPUT_SHA256.json')
    for name,h in inputs.items():assert sha(name)==h,('FEATURE_SOURCE_DRIFT',name)
    f=pd.read_parquet(p/'ALL_PRICE_RECEIPT_FEATURES.parquet')
    q=pd.read_parquet(runtime.R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet',columns=['sid','day','window'])
    q=q[q.window.isin(['2022','2024_924'])]
    keys=['window','sid','day']
    pd.testing.assert_frame_equal(f[keys].sort_values(keys).reset_index(drop=True),q[keys].sort_values(keys).reset_index(drop=True),check_exact=True)
    assert f.d.notna().all()
    sample=f.sample(48,random_state=520801)
    manifest={r['symbol']:r for r in read(runtime.R.parent.parent/'2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')} if False else None
    source=pd.read_csv(p/'SOURCE_AUDIT.csv').set_index('sid').source.to_dict()
    H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
    cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);cal=cal[(cal>='2013-01-01')&(cal<='2026-05-15')]
    errors=[]
    for sid,g in sample.groupby('sid'):
        cut=g.day.max();dates=cal[cal<=cut]
        raw=pd.read_parquet(source[sid]).reindex(dates)
        values=scalar(raw)
        for r in g.itertuples():
            err=abs(values[r.day]-r.d);assert err<1e-13,(sid,r.day,err)
            errors.append(err)
    return dict(keys_exact=len(f),source_hashes=len(inputs),independent_full_identity_scalar_samples=len(errors),max_scalar_error=max(errors),windows={w:dict(rows=len(g),start=str(g.day.min()),end=str(g.day.max())) for w,g in f.groupby('window')})
def synthetic_lifecycle():
    suite=unittest.TestSuite()
    # The legacy release-state test would consult the historical economic gate.
    # Do not run it: no historical runner is reachable from this audit.
    names=[n for n in unittest.defaultTestLoader.getTestCaseNames(JointTests) if n!='test_real_price_economic_entry_is_locked']
    suite.addTests(JointTests(n) for n in names)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ExecutionTests))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    assert result.wasSuccessful()
    return result.testsRun
def main():
    checks=dict(status='PASS_NON_ECONOMIC_COMPONENTS_PENDING_BASELINES_AND_FINAL_RELEASE_CODE',economic_runs=0)
    checks['ast']=derived_ast();checks['random_queues']=queues();checks['synthetic_lifecycle_tests']=synthetic_lifecycle();checks['features']=feature_checks()
    checks['reviewed_components']={n:sha(O/n) for n in ['runtime.py','priority.py','features.py','run_baseline.py','DYNAMIC_PROTOCOL.json']}
    checks['test_sha256']=sha(__file__)
    save(A/'COMPONENT_CHECKS.json',checks)
    print(json.dumps(checks,indent=2))
if __name__=='__main__':main()

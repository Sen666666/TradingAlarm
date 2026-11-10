"""Independent frozen-adapter and saved-market-tape checks. Zero economic loops."""
from pathlib import Path
from types import SimpleNamespace as NS
import ast,copy,sys,unittest,json,hashlib,time,datetime
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent.parent;A=O/'independent_audit';R=O.parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(O))
from runtime import sha,read,SOURCE,make_loop
import entry_gate as eg,joint_engine as j,test_gate as t,test_execution_book
import market_adapter,baseline_regression,joint_policy,execution_book,gates
from report_saved import displacement
start=time.monotonic()
assert not (O/'ROOT_ENTRY_GATE_AUTHORIZATION.json').exists()
assert not list(O.glob('ENTRY_GATE_RUN_ONCE_*.json'))
code=read(O/'FREEZE_CODE_SHA256.json');inputs=read(O/'FREEZE_INPUT_SHA256.json');freeze=read(O/'FREEZE.json')
assert freeze['code_manifest_sha256']==sha(O/'FREEZE_CODE_SHA256.json')
assert freeze['input_manifest_sha256']==sha(O/'FREEZE_INPUT_SHA256.json')
assert freeze['protocol_sha256']==sha(O/'PROTOCOL.md')
for name,h in code.items():assert sha(O/name)==h,('FROZEN_CODE_DRIFT',name)
for p,h in inputs.items():assert sha(p)==h,('FROZEN_INPUT_DRIFT',p)
m,original=eg.selector_tree();removed=0
for node in ast.walk(m):
 for field,value in ast.iter_fields(node):
  if isinstance(value,list):
   matches=[n for n in value if isinstance(n,ast.If) and ast.unparse(n.test)=='not self._entry_permission(pr)']
   for n in matches:value.remove(n);removed+=1
assert removed==1 and ast.dump(m,include_attributes=False)==original
loop=make_loop()
for f in [eg.GateMixin.select_close,loop]:
 for k,v in vars(j).items():
  if k not in ['select_close','isolated_loop']:assert f.__globals__[k] is v,('GLOBAL_BINDING',k)
for n,v in j.JointConsumer.__dict__.items():
 if callable(v) and n not in {'__init__','select_close','_candidate_frame','process_day'}:assert getattr(eg.GateConsumer,n) is v,n
for name in ['joint_engine','joint_policy','execution_book','market_adapter','baseline_regression','gates']:
 assert Path(sys.modules[name].__file__).parent==SOURCE,('ORIGINAL_MODULE_BINDING',name)
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_offer' for n in ast.walk(ast.parse(__import__('inspect').getsource(eg.GateMixin)))),'GATE_AUDIT_NOT_SIDECAR_ONLY'
suite=unittest.TestSuite()
for cls in [t.GenerationTests,t.ConsumerTests,t.AllAllowInheritedJointTests]:
 for test in unittest.defaultTestLoader.loadTestsFromTestCase(cls):
  if test._testMethodName!='test_real_price_economic_entry_is_locked':suite.addTest(test)
suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_execution_book))
res=unittest.TextTestRunner(verbosity=1).run(suite);assert res.wasSuccessful()
assert read(O/'TEST_QA.json')['code_sha256']==sha(O/'test_gate.py')
assert read(O/'TEST_QA.json')['tests_run']==res.testsRun
# Actual ALLOW metadata path must preserve original outputs too.
out=[]
for cls in [j.JointConsumer,t.FixtureConsumer]:
 e=t.FakeEngine();mk=t.FakeMarket(e);c=cls(e,mk,'2022')
 rows=[t.price_row('P',score=90),t.price_row('U',score=float('nan'),known=False)]
 if cls is t.FixtureConsumer:
  for p in rows:c.add(p)
 c.process_day(t.CAL[0],None,[t.ab_row('A',score=60)],copy.deepcopy(rows))
 for i,d in enumerate(t.CAL[1:],1):c.process_day(d,t.CAL[i-1],[],[])
 vals={n:getattr(e,n) for n in ['rounds','actions','decisions','ranking_audit','archives','blocks','claims','trace','closecache','CURRENT_PHASE']}
 vals.update({n:getattr(c,n) for n in ['states','seq','books','price_audit','offer_audit','frozen_responsibilities','ab_decision_audit']});out.append(t.clean(vals))
assert out[0]==out[1]
for field,val in [('signal_raw_close',999.),('signal_identity','OTHER'),('signal_factor',float('nan'))]:
 e,mk,c=t.make();p=c.add(t.price_row());c._entry_features['SYN_A',t.CAL[0]][field]=val
 try:c.select_close(t.CAL[0],[],[p])
 except eg.GateUnknown:pass
 else:raise AssertionError(('METADATA_NOT_REJECTED',field))
 assert not c.states and not e.actions
e=t.FakeEngine();old=j.JointConsumer(e,t.FakeMarket(e),'2022');p=t.price_row('D');old.select_close(t.CAL[0],[],[copy.deepcopy(p)])
e,mk,new=t.make();new.add(p,'DENY_ENTRY_GENERATION_INACTIVE');new.select_close(t.CAL[0],[],[copy.deepcopy(p)])
assert [r['result'] for r in new.offer_audit]==['APPLICATION']
assert displacement(old,new)[0]['reason']=='DENY_ENTRY_GENERATION_INACTIVE'
new.entry_gate_audit[0]['receipt_id']='WRONG_RECEIPT'
assert displacement(old,new)[0]['reason']=='NO_NEW_OFFER'
# Freeze the complete market domain, independent of any portfolio path.
T=O/'market_tape';seal=read(T/'SEAL.json');qa=read(T/'QA.json')
for name,h in seal.items():assert sha(T/name)==h,('TAPE_SEAL',name)
assert qa['stocks']==1628 and qa['receipts']==37456 and qa['physical_prefix_checks']==1628 and qa['economic_runs']==0
prefix=read(T/'PREFIX_EXACT_QA.json');assert len(prefix)==len({r['sid'] for r in prefix})==1628
assert all(r['exact'] for r in prefix)
f=pd.read_parquet(T/'RECEIPT_GATE_FACTS.parquet').sort_values(['sid','day']).reset_index(drop=True)
oldf=pd.read_parquet(R/'price_entry_generation_gate_preflight_v1/RECEIPT_GATE_FACTS.parquet').sort_values(['sid','day']).reset_index(drop=True)
assert len(f)==37456 and f.sid.nunique()==1628 and not f.duplicated(['sid','day']).any()
fields=['sid','day','root_day','window','generation','entry_U','entry_active','gate_status','event','ever_returned_to_root_U','current20_high_break','contemporary_prior20_high','generation_birth','first_return_to_root_U','last_generation_retired']
for col in fields:
 av=f[col].copy();bv=oldf[col].copy()
 if 'datetime' in str(av.dtype) or 'datetime' in str(bv.dtype):
  av=pd.to_datetime(av).astype('datetime64[ns]');bv=pd.to_datetime(bv).astype('datetime64[ns]')
 pd.testing.assert_series_equal(av,bv,check_exact=True,check_dtype=False)
assert f.gate_known_at.eq('CLOSE').all()
domains={}
for w,window in [('2022','2022'),('2024','2024_924')]:
 holder=NS(window=window);c=j.JointConsumer._candidate_frame(holder)
 ff=f[f.window.eq(window)]
 assert not c.duplicated(['sid','day']).any()
 assert set(zip(c.sid,c.day))==set(zip(ff.sid,ff.day))
 records={(r['sid'],pd.Timestamp(r['day'])):r for r in ff.to_dict('records')}
 for r in c.to_dict('records'):
  z=records[r['sid'],pd.Timestamp(r['day'])]
  assert tuple(z['root_id'])==tuple(r['root_id'])
  assert z['receipt_identity']==repr(r['receipt_id'])
  assert z['signal_identity']==r['root_id'][1]
  assert z['signal_factor']==r['adjustment_factor']
  assert z['signal_raw_close']==r['raw_close']
 assert c.day.min()>=pd.Timestamp('2022-01-01' if w=='2022' else '2024-09-01')
 assert c.day.max()<=pd.Timestamp(w+'-12-31')
 domains[w]=dict(receipts=len(c),candidate_source_sha256=holder.candidate_source_sha256,all_root_receipt_source_factor_close_exact=True)
counts=dict(stocks=0,stock_day_rows=0,parent_failed_rows=0,parent_fail_above_entry_u_rows=0,parent_unknown_rows=0,allow_rows=0,active_transition_checks=0,retired_transition_checks=0,full_tail_prefix_old153_exact=0)
for sid in sorted(f.sid.unique()):
 z=pd.read_parquet(T/(sid+'.parquet')).sort_values('day').reset_index(drop=True)
 assert not z.day.duplicated().any()
 assert z.day.max()<=pd.Timestamp('2026-06-30')
 failed=z.failed & ~z.root_unknown;unk=z.root_unknown
 assert z.loc[failed,'gate_status'].eq('DENY_PARENT_FAILED').all()
 assert z.loc[unk,'gate_status'].eq('UNKNOWN_PARENT_ROOT').all()
 assert not z.loc[failed|unk,'entry_active'].any()
 assert (~z.entry_active | (z.active & ~z.failed & ~z.root_unknown & z.gate_source_valid & z.valid)).all()
 assert z.entry_active.eq(z.gate_status.eq('ALLOW')).all()
 same=z.root_day.eq(z.root_day.shift())
 live=z.active & ~z.born & ~z.failed & ~z.root_unknown & z.gate_source_valid & same
 prev_active=z.entry_active.shift(fill_value=False);pgen=z.generation.shift();pu=z.entry_U.shift()
 a=live & prev_active
 assert z.loc[a,'entry_active'].eq(z.loc[a,'close'].gt(pu[a])).all()
 assert z.loc[a,'generation'].eq(pgen[a]).all() and z.loc[a,'entry_U'].eq(pu[a]).all()
 retired=live & ~prev_active & ~z.gate_status.shift(fill_value='NONE').str.startswith('UNKNOWN')
 rebirth=retired & np.isfinite(z.contemporary_prior20_high) & z.close.gt(z.contemporary_prior20_high)
 assert z.loc[retired,'entry_active'].eq(rebirth[retired]).all()
 assert z.loc[rebirth,'generation'].eq(pgen[rebirth]+1).all()
 assert z.loc[rebirth,'entry_U'].eq(z.loc[rebirth,'contemporary_prior20_high']).all()
 stay=retired & ~rebirth
 assert z.loc[stay,'generation'].eq(pgen[stay]).all() and z.loc[stay,'entry_U'].eq(pu[stay]).all()
 born=z.born & ~z.failed & ~z.root_unknown
 validborn=born & z.gate_source_valid & np.isfinite(z.contemporary_prior20_high)
 assert z.loc[validborn,'generation'].eq(1).all() and z.loc[validborn,'entry_active'].all()
 assert z.loc[validborn,'entry_U'].eq(z.loc[validborn,'U']).all()
 assert not z.loc[born & ~validborn,'entry_active'].any()
 oldpath=O/'setup_attempt01/market_tape'/(sid+'.parquet')
 if oldpath.exists():
  v=pd.read_parquet(oldpath)
  for df in [v,z]:
   for col in df.columns:
    if pd.api.types.is_datetime64_any_dtype(df[col].dtype):df[col]=pd.to_datetime(df[col]).astype('datetime64[ns]')
  pd.testing.assert_frame_equal(v.reset_index(drop=True),z[v.columns].reset_index(drop=True),check_exact=True)
  counts['full_tail_prefix_old153_exact']+=1
 counts['stocks']+=1;counts['stock_day_rows']+=len(z);counts['parent_failed_rows']+=int(failed.sum());counts['parent_fail_above_entry_u_rows']+=int((failed & z.close.gt(z.entry_U)).sum());counts['parent_unknown_rows']+=int(unk.sum());counts['allow_rows']+=int(z.entry_active.sum());counts['active_transition_checks']+=int(a.sum());counts['retired_transition_checks']+=int(retired.sum())
assert counts['stocks']==1628 and counts['full_tail_prefix_old153_exact']==153
for p,h in read(T/'SOURCE_HASHES.json').items():assert sha(p)==h
assert not (O/'ROOT_ENTRY_GATE_AUTHORIZATION.json').exists() and not list(O.glob('ENTRY_GATE_RUN_ONCE_*.json'))
for name,h in code.items():assert sha(O/name)==h
out=dict(status='PASS_INDEPENDENT_FROZEN_ADAPTER_AND_COMPLETE_MARKET_TAPE',economic_calls=0,synthetic_tests=res.testsRun,all_allow_original_outputs_exact=True,actual_allow_metadata_path_exact=True,strict_sidecar_only=True,receipt_identity_attribution_exact=True,selector_removed_gate_ast_original_exact=True,original_loop_class_import_global_bindings_exact=True,all_frozen_code_inputs_verified=True,reviewed_code_sha256=code,code_manifest_sha256=sha(O/'FREEZE_CODE_SHA256.json'),input_manifest_sha256=sha(O/'FREEZE_INPUT_SHA256.json'),protocol_sha256=sha(O/'PROTOCOL.md'),market_tape_seal_sha256=sha(T/'SEAL.json'),full_domain=domains,full_lifecycle_counts=counts,receipt_count=37456,stock_count=1628,physical_prefix_checks_reused=1628,source_files=len(read(T/'SOURCE_HASHES.json')),baseline_reuse_audit_sha256=sha(A/'BASELINE_REUSE_AUDIT.json'),test_qa_sha256=sha(O/'TEST_QA.json'),script_sha256=sha(__file__),elapsed_seconds=time.monotonic()-start)
with (A/'ADAPTER_MARKET_AUDIT.json').open('x') as out_file:json.dump(out,out_file,ensure_ascii=False,indent=2,allow_nan=False);out_file.write('\n')
print(out['status'],json.dumps(counts),sha(A/'ADAPTER_MARKET_AUDIT.json'),flush=True)

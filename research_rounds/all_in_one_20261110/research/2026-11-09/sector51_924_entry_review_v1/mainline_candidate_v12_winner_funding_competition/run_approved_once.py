from pathlib import Path
import sys,json,hashlib,importlib.util,traceback
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
ROOT=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+"\n")
ENGINE="2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72"
TESTS="808f541527f67fdbe1090269a2dd61d6959e41fff044d0a9a9e341a3a9764b53"
MANIFEST="7e78f1851781f89c168123585d0d807d9f00527f7f1885a7e158fb95d3b50554"
QA="a847e01cc965d541c7bdda62e23a0a01404c95c8018aa9f8c38099b858f9679b"
DESIGN="3ffa6bd951e2377e65a83f9ee13bd3a2ed320970ed0f03fd277398e1b9856bd1"
review_path=ROOT/"mainline_winner_funding_review_v1/V12_INDEPENDENT_INTERFACE_QA.json"
design_path=ROOT/"mainline_winner_funding_design_v1/EXECUTION_FREEZE_ADDENDUM.md"
assert sha(O/"engine.py")==ENGINE and sha(O/"synthetic_tests.py")==TESTS
assert sha(O/"SOURCE_HASHES.json")==MANIFEST and sha(O/"SYNTHETIC_QA.json")==QA
assert sha(design_path)==DESIGN
review=json.loads(review_path.read_text())
assert review["result"]=="PASS_FOR_ONE_FROZEN_OFFLINE_EXPERIMENT"
assert review["engine_sha256"]==ENGINE and review["tests_sha256"]==TESTS and review["source_manifest_sha256"]==MANIFEST
assert review["native_and_contract_assertions"]==101 and review["independent_extra_assertions"]==8 and not review["remaining_blockers"]
qa=json.loads((O/"SYNTHETIC_QA.json").read_text())
assert qa["result"]=="PASS" and qa["assertions"]==101
assert json.loads((O/"INPUT_TYPE_QA.json").read_text())["result"]=="PASS"
manifest=json.loads((O/"SOURCE_HASHES.json").read_text())
for p,h in manifest["files"].items(): assert sha(p)==h,("SOURCE_DRIFT",p)
assert not (O/"RUN_STARTED.json").exists(),"ONE_SHOT_ALREADY_STARTED"
assert not (O/"once_20250120").exists(),"OUTPUT_ALREADY_EXISTS"
sp=importlib.util.spec_from_file_location("approved_v12_single_account",O/"engine.py")
m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
assert m.self_check()["result"]=="PASS"
names=["engine.py","synthetic_tests.py","input_type_tests.py","SYNTHETIC_QA.json","INPUT_TYPE_QA.json","STATIC_QA.json","SYNTHETIC_SCALE.json","CONTRACT_REF.md","SOURCE_HASHES.json","run_approved_once.py"]
code={str(O/n):sha(O/n) for n in names}
code[str(review_path)]=sha(review_path)
code[str(design_path)]=DESIGN
approval=dict(approved=True,research_only=True,one_shot=True,start="2024-09-02",end="2025-01-20",
 initial_cash="1200000",baseline="mainline_m7_cash_batch_design_v6/once_20260630",
 gate="Minimal A: original M7 natural branch projections; per healthy lot y<=shadow y and per ADD/EVENT q>=shadow q; reject lowest original-priority new MATURE SEED until feasible.",
 code_hashes=code,independent_review=review,
 no_external_reads=True,no_production_orders=True,no_G_or_V11_or_M9_M10_stacking=True,
 original_Q0_ST_cash_source_boundaries_unchanged=True)
save(O/"EXPERIMENT_APPROVAL.json",approval)
print("DATA_INITIALIZATION_START",flush=True)
data=m.Data()
run_days=[d for d in data.days if m.day(d)<="2025-01-20"]
assert len(run_days)==93 and m.day(run_days[0])=="2024-09-02" and m.day(run_days[-1])=="2025-01-20"
for p,h in code.items(): assert sha(p)==h;data.hashes[p]=h
data.hashes[str(O/"EXPERIMENT_APPROVAL.json")]=sha(O/"EXPERIMENT_APPROVAL.json")
save(O/"FROZEN_INPUTS.json",dict(hashes=data.hashes,code_hashes=code,end="2025-01-20",
 execution_days=93,sealed_loaded_end=m.day(data.cal[-1]),not_PIT=True))
e=m.Engine(data)
assert e.cash==m.D("1200000")
with (O/"RUN_STARTED.json").open("x") as f:
 json.dump(dict(started_at=str(m.pd.Timestamp.now(tz="UTC")),end="2025-01-20",engine_sha256=ENGINE,qa_sha256=QA),f,ensure_ascii=False,indent=2)
pending=[];runtime_error=None;blocked=None
for d in run_days:
 prev=data.cal[data.cal.get_loc(d)-1]
 try:
  pending=e.atomic_step(d,pending,prev)
 except m.Blocked as ex:
  blocked=dict(day=m.day(d),reason=str(ex),atomic_rollback=True)
  e.blockers.append(str(ex));e.uncertified_day=blocked
  try:e.all_blockers=e.scan_restored_targets(d,pending)
  except Exception as scan_ex:e.all_blockers=[dict(scan_error=str(scan_ex))]
  print("ATOMIC_BLOCK "+json.dumps(blocked,ensure_ascii=False),flush=True);break
 except Exception as ex:
  runtime_error=dict(day=m.day(d),type=type(ex).__name__,reason=str(ex),traceback=traceback.format_exc(),atomic_rollback=True)
  print("RUNTIME_ERROR "+json.dumps(runtime_error,ensure_ascii=False),flush=True);break
 print("DAY "+m.day(d)+" "+json.dumps(dict(orders=len(e.orders),NAV=e.ledger[-1]["NAV"],stocks=e.ledger[-1]["stocks"],
  branches=len(e.funding_book["branches"]) if e.funding_book else 0,wait_events=len(e.funding_wait_log)),ensure_ascii=False),flush=True)
e.pending=pending
out=O/"once_20250120"
print("EXPORT_START",flush=True)
e.export(out)
status=dict(result="RUNTIME_ERROR" if runtime_error else "ATOMIC_BLOCK" if blocked else "COMPLETED",
 days=len(e.ledger),orders=len(e.orders),last=e.ledger[-1] if e.ledger else None,blockers=e.blockers,
 atomic_block=blocked,runtime_error=runtime_error,output=str(out),
 source_hashes_verified=all(sha(p)==h for p,h in code.items()),finished_at=str(m.pd.Timestamp.now(tz="UTC")))
save(O/"RUN_STATUS.json",status)
print("FINAL "+json.dumps(status,ensure_ascii=False,default=str),flush=True)
if runtime_error:raise SystemExit(2)

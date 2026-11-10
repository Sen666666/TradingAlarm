from pathlib import Path
import sys, json, hashlib, importlib.util, traceback
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
ROOT=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+"\n")
expected_engine="15c30e8b3eb3a6dfec5777febe33b1e161d5160057d75c13749f9f50e3384d4c"
expected_qa="9207711d29ecfd949992432fbbd9d72afeb408831e7397bf2de8b087298b3d54"
expected_design="79ebeb73457914656eb70e4ecb59a58008e57d7cb92dd1296dd86d3577efbe12"
assert sha(O/"engine.py")==expected_engine
assert sha(O/"SYNTHETIC_QA.json")==expected_qa
assert sha(O/"INPUT_TYPE_QA.json")=="3d0205c219928e874599b2cb8dc3b5961b2711fb8ed4034a8d78171dcf7e207d"
assert json.loads((O/"INPUT_TYPE_QA.json").read_text())["result"]=="PASS"
design=ROOT/"mainline_structural_maturity_design_v1/DESIGN.md"
assert sha(design)==expected_design
qa=json.loads((O/"SYNTHETIC_QA.json").read_text())
assert qa["result"]=="PASS" and qa["passed_groups"]==27 and qa["assertions"]==166
for name,key in [("engine.py","engine_sha256"),("shadow.py","shadow_sha256"),("synthetic_tests.py","tests_sha256")]:
    assert sha(O/name)==qa[key],name
assert not (O/"RUN_STARTED.json").exists(),"ONE_SHOT_ALREADY_STARTED"
assert not (O/"once_20250120").exists(),"OUTPUT_ALREADY_EXISTS"
sp=importlib.util.spec_from_file_location("approved_v11_single_account",O/"engine.py")
m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
assert m.self_check()["result"]=="PASS"
code={str(O/n):sha(O/n) for n in ["engine.py","shadow.py","synthetic_tests.py","SYNTHETIC_QA.json","STATIC_QA.json","CONTRACT_REF.md","SOURCE_HASHES.json","input_type_tests.py","INPUT_TYPE_QA.json","run_approved_once.py"]}
approval=dict(approved=True,research_only=True,one_shot=True,start="2024-09-02",end="2025-01-20",
 initial_cash="1200000",baseline="mainline_m7_cash_batch_design_v6/once_20260630",
 formula_design_sha256=expected_design,code_hashes=code,
 independent_synthetic_review=dict(result="PASS",groups=27,assertions=166,qa_sha256=expected_qa),
 no_external_reads=True,no_production_orders=True,no_m9_m10_stacking=True,
 technical_fix="NumPy boolean input compatibility only; prior 20-day output INVALID_IMPLEMENTATION; Q0 guard unchanged",
 gate="MATURE SEED only: three-valued OR(F, valid entry CP with receipt_day >= original_signal_day)")
save(O/"EXPERIMENT_APPROVAL.json",approval)
print("DATA_INITIALIZATION_START",flush=True)
data=m.Data()
run_days=[d for d in data.days if m.day(d)<="2025-01-20"]
assert len(run_days)==93 and m.day(run_days[0])=="2024-09-02" and m.day(run_days[-1])=="2025-01-20"
for path,h in code.items(): assert sha(path)==h;data.hashes[path]=h
data.hashes[str(design)]=sha(design)
data.hashes[str(O/"EXPERIMENT_APPROVAL.json")]=sha(O/"EXPERIMENT_APPROVAL.json")
save(O/"FROZEN_INPUTS.json",dict(hashes=data.hashes,code_hashes=code,end="2025-01-20",execution_days=93,sealed_loaded_end=m.day(data.cal[-1]),not_PIT=True))
e=m.Engine(data)
assert e.cash==m.D("1200000")
started=dict(started_at=str(m.pd.Timestamp.now(tz="UTC")),end="2025-01-20",engine_sha256=expected_engine,qa_sha256=expected_qa)
with (O/"RUN_STARTED.json").open("x") as f: json.dump(started,f,ensure_ascii=False,indent=2)
pending=[];runtime_error=None;blocked=None
for d in run_days:
    prev=data.cal[data.cal.get_loc(d)-1]
    try:
        pending=e.atomic_step(d,pending,prev)
    except m.Blocked as ex:
        blocked=dict(day=m.day(d),reason=str(ex),atomic_rollback=True)
        e.blockers.append(str(ex))
        e.uncertified_day=blocked
        try: e.all_blockers=e.scan_restored_targets(d,pending)
        except Exception as scan_ex: e.all_blockers=[dict(scan_error=str(scan_ex))]
        print("ATOMIC_BLOCK "+json.dumps(blocked,ensure_ascii=False),flush=True)
        break
    except Exception as ex:
        runtime_error=dict(day=m.day(d),type=type(ex).__name__,reason=str(ex),traceback=traceback.format_exc(),atomic_rollback=True)
        print("RUNTIME_ERROR "+json.dumps(runtime_error,ensure_ascii=False),flush=True)
        break
    print("DAY "+m.day(d)+" "+json.dumps(dict(orders=len(e.orders),NAV=e.ledger[-1]["NAV"],stocks=e.ledger[-1]["stocks"],tickets=len(e.live_tickets()),entry_cp_created=sum(x.get("event")=="CREATED" for x in e.entry_log)),ensure_ascii=False),flush=True)
e.pending=pending
out=O/"once_20250120"
e.export(out)
status=dict(result="RUNTIME_ERROR" if runtime_error else "ATOMIC_BLOCK" if blocked else "COMPLETED",
 days=len(e.ledger),orders=len(e.orders),last=e.ledger[-1] if e.ledger else None,
 blockers=e.blockers,atomic_block=blocked,runtime_error=runtime_error,
 output=str(out),source_hashes_verified=all(sha(path)==h for path,h in code.items()),
 finished_at=str(m.pd.Timestamp.now(tz="UTC")))
save(O/"RUN_STATUS.json",status)
print("FINAL "+json.dumps(status,ensure_ascii=False,default=str),flush=True)
if runtime_error: raise SystemExit(2)

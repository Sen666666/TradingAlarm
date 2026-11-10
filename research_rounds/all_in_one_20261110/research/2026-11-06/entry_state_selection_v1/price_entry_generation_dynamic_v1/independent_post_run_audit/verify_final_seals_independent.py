import json,hashlib,csv,datetime,math,ast
from pathlib import Path
import pandas as pd
D=Path(__file__).resolve().parent.parent;J=D.parent/"independent_channel_joint_economic_v1"
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(D/"ROOT_ENTRY_GATE_AUTHORIZATION.json");rev=read(D/"INDEPENDENT_PRE_ECONOMIC_AUDIT.json");oa=read(J/"ROOT_ECONOMIC_AUTHORIZATION.json");os=read(J/"FINAL_RUN_SEAL.json");old=read(D/"ORIGINAL_INTEGRITY_AFTER_INTERRUPTED_TEST.json");cache={}
def check(p,h):
 p=Path(p)
 if str(p) not in cache:cache[str(p)]=sha(p)
 assert cache[str(p)]==h,str(p)
for n,h in a["code_sha256"].items():check(D/n,h)
for n,h in a["input_sha256"].items():check(n,h)
assert a["code_sha256"]==rev["reviewed_code_sha256"]==read(D/"FREEZE_CODE_SHA256.json")
assert a["input_sha256"]==rev["reviewed_input_sha256"]==read(D/"FREEZE_INPUT_SHA256.json")
check(D/"PROTOCOL.md",a["protocol_sha256"]);check(D/"INDEPENDENT_PRE_ECONOMIC_AUDIT.json",a["implementation_audit_sha256"])
for n,h in oa["code_sha256"].items():check(J/n,h)
for n,h in oa["input_sha256"].items():check(n,h)
for n,h in os["files"].items():check(Path(n) if Path(n).is_absolute() else J/n,h)
for n,h in old["outputs"].items():check(n,h)
for v in old["locks"].values():check(v["path"],v["sha256"])
windows={}
for w in ["2022","2024"]:
 g=D/("gate_"+w);complete=read(g/"COMPLETE_SAVED_SNAPSHOT.json");assert not list(g.glob("FAILED*"));check(g/"OUTPUT_SEAL.json",complete["output_seal_sha256"])
 for n,h in read(g/"OUTPUT_SEAL.json").items():check(g/n,h)
 for p in [g/"COMPLETE_SAVED_SNAPSHOT.json",g/"STARTED.json",D/("ENTRY_GATE_RUN_ONCE_"+w+".json"),D/("RUN_LAUNCH_"+w+".json")]:assert read(p)["authorization_sha256"]==sha(D/"ROOT_ENTRY_GATE_AUTHORIZATION.json")
 for folder in [D/("report_"+w),D/("cases_"+w),D/"report_supplements_v1"/w]:
  for n,h in read(folder/"OUTPUT_SHA256.json").items():check(folder/n,h)
 sup=read(D/"report_supplements_v1"/w/"CORRECTED_FEES_AND_PROTECTION_PATHS.json")
 for n,h in sup["source_sha256"].items():check(n,h)
 check(D/"report_supplements_v1/supplement_cases.py",sup["script_sha256"])
 raw={};checked=0;protection=0
 for arm,folder in [("baseline",J/("economic_"+w)),("joint",g)]:raw[arm]={r["round_id"]:r for r in csv.DictReader((folder/"joint/ROUNDS.csv").open())}
 for case in sup["cases"]:
  sid=case["sid"];tp=D/"market_tape"/(sid+".parquet");tape=pd.read_parquet(tp) if tp.exists() else None
  for arm,path in case["paths"].items():
   for r in path["native_rounds"]:
    native=raw[arm][r["round_id"]];fees=native.get("all_fees");aa=r["actions"]
    if fees:
     assert math.isclose(float(fees),r["all_fees"],abs_tol=1e-9)
     if aa:assert abs(sum(float(x["fee"]) for x in aa)-float(fees))<1e-8;checked+=1
    else:assert r["all_fees"] is None
    if native["owner_lane"]=="PRICE" and aa and tape is not None:
     root=ast.literal_eval(native["price_root"]);end=native["exit_day"] or native["status_day"]
     z=tape[(tape.day>=pd.Timestamp(native["signal_day"]))&(tape.day<=pd.Timestamp(end))&(tape.root_day==pd.Timestamp(root[-1]))]
     exp=[];prev=None
     for i,x in enumerate(z.to_dict("records")):
      if i==0 or x["S_new"]!=prev or x["failed"] or x["root_unknown"] or x["e0_raised"]:exp.append(x)
      prev=x["S_new"]
     actual=r["original_price_protection_changes"];assert len(actual)==len(exp)
     for x,y in zip(actual,exp):
      for key in x:
       val=y[key]
       if isinstance(val,pd.Timestamp):assert x[key]==str(val)
       elif isinstance(val,float) and math.isnan(val):assert x[key] is None
       elif isinstance(val,tuple):assert x[key]==list(val) or str(x[key])==str(val)
       else:assert x[key]==val,(sid,key,x[key],val)
     protection+=len(exp)
 assert checked==sup["checked_entered_rounds"]
 cohort=read(D/"independent_post_run_audit"/("sealed_cohort_raw_"+w+".json"));report=read(D/("report_"+w)/"COMPARISON_REPORT.json");stocks={(r["sid"],r["arm"]):r for r in report["stock_rows"]}
 for sid,paths in cohort["whole_stock_paths"].items():
  for arm,path in paths.items():
   st=stocks[sid,arm];assert abs(st["fees"]-path["fee_total"])<1e-6;assert st["unknown_liability"]==bool(path["unknown_rounds"])
 diffs=[x for x in report["differences"] if x["sid"] in cohort["whole_stock_paths"]]
 windows[w]=dict(ready=True,sealed_output_files=len(read(g/"OUTPUT_SEAL.json")),supplement_entered_round_fees_checked=checked,supplement_stocks=sup["stocks"],original_protection_points_checked=protection,full_cohort_stock_fee_and_unknown_match=True,cohort_unique_stocks=len(diffs),cohort_common_covered_stocks=sum(x["common_covered"] for x in diffs),cohort_common_full_path_delta=sum(x["joint_minus_baseline"] for x in diffs if x["common_covered"]))
 print("WINDOW_PASS",w,windows[w],flush=True)
out=dict(status="PASS_FINAL_SEALS_COHORT_PACKAGES_AND_REPORT_SUPPLEMENTS",checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),unique_files_rehashed=len(cache),hash_mismatches=[],code_files=len(a["code_sha256"]),input_files=len(a["input_sha256"]),original_frozen_code_inputs_locks_and_outputs_unchanged=True,authorization_sha256=sha(D/"ROOT_ENTRY_GATE_AUTHORIZATION.json"),windows=windows,economic_executions=0,original_cases_preserved=True,known_reporting_defect="Original cases round fees field is null; use verified all_fees supplement, raw action fees and formal report totals remain intact.")
with (D/"independent_post_run_audit/sealed_cohort_final_integrity.json").open("x") as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))

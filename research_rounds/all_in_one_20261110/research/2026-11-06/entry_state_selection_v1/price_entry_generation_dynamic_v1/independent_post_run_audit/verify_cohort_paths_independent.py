import json,csv,hashlib,sys,datetime
from pathlib import Path
from collections import Counter,defaultdict
D=Path(__file__).resolve().parent.parent;R=D.parent;J=R/"independent_channel_joint_economic_v1"
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
csvread=lambda p:list(csv.DictReader(p.open()))
w=sys.argv[1];g=D/("gate_"+w);a=read(D/"ROOT_ENTRY_GATE_AUTHORIZATION.json");complete=read(g/"COMPLETE_SAVED_SNAPSHOT.json");seal=read(g/"OUTPUT_SEAL.json")
assert not list(g.glob("FAILED*"))
assert complete["output_seal_sha256"]==sha(g/"OUTPUT_SEAL.json")
assert complete["authorization_sha256"]==sha(D/"ROOT_ENTRY_GATE_AUTHORIZATION.json")
assert complete["implementation_audit_sha256"]==a["implementation_audit_sha256"]
assert complete["protocol_sha256"]==a["protocol_sha256"]
for n,h in seal.items():assert sha(g/n)==h,n
for p in [D/("ENTRY_GATE_RUN_ONCE_"+w+".json"),D/("RUN_LAUNCH_"+w+".json"),g/"STARTED.json"]:assert read(p)["authorization_sha256"]==sha(D/"ROOT_ENTRY_GATE_AUTHORIZATION.json")
cohort=[x for x in csvread(R/"old_result_association_v1/COMMON_167_DENY_BUYS.csv") if x["window"]==("2022" if w=="2022" else "2024_924")]
assert len(cohort)==(117 if w=="2022" else 50)
data={}
for arm,folder in [("baseline",J/("economic_"+w)),("joint",g)]:
 rounds=csvread(folder/"joint/ROUNDS.csv");actions=csvread(folder/"joint/ACTIONS.csv");books=read(folder/"EXECUTION_BOOKS.json");claims=read(folder/"joint/CLAIMS.json")
 data[arm]=dict(rounds=rounds,actions=actions,books=books,claims=claims)
paths={};problems=[]
for sid in sorted({x["sid"] for x in cohort}):
 paths[sid]={}
 for arm,d in data.items():
  rounds=[x for x in d["rounds"] if x["sid"]==sid];ids={x["round_id"] for x in rounds};actions=[x for x in d["actions"] if x["sid"]==sid];assert all(x["round_id"] in ids for x in actions)
  chronological=sorted(enumerate(actions),key=lambda z:(z[1]["day"],z[0]));bought=set();closed=set();entry_labels={};traces=[]
  for pos,act in chronological:
   rid=act["round_id"]
   if act["side"]=="buy_core":
    label="REENTRY_AFTER_OWN_BUY_SELL_ALL" if closed else "FIRST_ENTRY" if not bought else "ENTRY_WITHOUT_PROVED_PRIOR_FLAT"
    entry_labels[rid]=label;bought.add(rid);traces.append(dict(round_id=rid,day=act["day"],signal_day=act["signal_day"],label=label,prior_closed_rounds=sorted(closed)))
   elif act["side"]=="sell_all" and rid in bought:closed.add(rid)
  br={rid:d["books"][rid] for rid in ids if rid in d["books"]};cl=[x for x in d["claims"] if x.get("sid")==sid or x.get("owner_round_id") in ids]
  unknown=[x["round_id"] for x in rounds if "UNKNOWN" in x["status"] or "PENDING" in x["status"] or br.get(x["round_id"],{}).get("responsibility",{}).get("unknown")]
  paths[sid][arm]=dict(rounds=rounds,actions=actions,books=br,claims=cl,entry_labels=entry_labels,entry_traces=traces,unknown_rounds=unknown,fee_total=sum(float(x["fee"] or 0) for x in actions),action_counts=dict(Counter(x["side"] for x in actions)))
rows=[]
for old in cohort:
 sid=old["sid"];base=paths[sid]["baseline"];new=paths[sid]["joint"];original=[r for r in base["rounds"] if r["round_id"]==old["round_id"]];assert len(original)==1;original=original[0];assert original["signal_day"][:10]==old["signal_day"][:10]
 same=[r for r in new["rounds"] if r["event_id"]==original["event_id"] and r["owner_lane"]==original["owner_lane"]]
 nextbuy=[t for t in new["entry_traces"] if t["signal_day"]>=original["signal_day"]]
 rows.append(dict(old_round_id=old["round_id"],sid=sid,old_signal_day=original["signal_day"],event_id=original["event_id"],old_net=float(old["old_FULL_net"]),same_receipt_registered=[r["round_id"] for r in same],same_receipt_bought=[r["round_id"] for r in same if r["round_id"] in new["entry_labels"]],new_stock_any_buy=bool(new["entry_traces"]),next_buy_on_or_after_original_signal=nextbuy[0] if nextbuy else None,new_stock_unknown=bool(new["unknown_rounds"]),new_stock_unknown_rounds=new["unknown_rounds"]))
def summary(rr):
 return dict(old_round_denominator=len(rr),unique_stocks=len({r["sid"] for r in rr}),same_receipt_registered=sum(bool(r["same_receipt_registered"]) for r in rr),same_receipt_bought=sum(bool(r["same_receipt_bought"]) for r in rr),stock_ever_bought=sum(r["new_stock_any_buy"] for r in rr),next_buy_after_old_signal=sum(r["next_buy_on_or_after_original_signal"] is not None for r in rr),next_buy_identity=dict(Counter(r["next_buy_on_or_after_original_signal"]["label"] if r["next_buy_on_or_after_original_signal"] else "NO_LATER_BUY" for r in rr)),unknown_stock_rows=sum(r["new_stock_unknown"] for r in rr))
out=dict(window=w,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),economic_executions=0,seal_pass=True,sealed_output_count=len(seal),output_seal_sha256=sha(g/"OUTPUT_SEAL.json"),all_olds_retained=True,summary=summary(rows),old_losses=summary([r for r in rows if r["old_net"]<0]),old_wins=summary([r for r in rows if r["old_net"]>0]),rows=rows,whole_stock_paths=paths,financial_report_crosscheck="PENDING",execution_model="CONDITIONAL_PROXY_NOT_REAL_BROKER_FILL",reentry_method="CHRONOLOGICAL_SAME_STOCK_OWN_BUY_CORE_THEN_SELL_ALL_THEN_BUY_CORE; raw file order breaks same-day ties")
p=D/"independent_post_run_audit"/("sealed_cohort_raw_"+w+".json")
with p.open("x") as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in out.items() if k not in ["rows","whole_stock_paths"]},ensure_ascii=False,indent=2))

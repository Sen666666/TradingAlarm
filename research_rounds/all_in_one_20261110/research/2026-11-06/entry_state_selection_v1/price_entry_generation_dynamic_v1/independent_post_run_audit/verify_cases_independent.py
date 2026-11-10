import json,csv,hashlib,sys,math
from pathlib import Path
from collections import Counter
D=Path(__file__).resolve().parent.parent;J=D.parent/"independent_channel_joint_economic_v1";w=sys.argv[1]
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();csvread=lambda p:list(csv.DictReader(p.open()))
c=read(D/("cases_"+w)/"AFFECTED_OLD_COHORT_FULL_NEW_PATHS.json");ind=read(D/"independent_post_run_audit"/("sealed_cohort_raw_"+w+".json"));report=read(D/("report_"+w)/"COMPARISON_REPORT.json");stocks={(r["sid"],r["arm"]):r for r in report["stock_rows"]}
for n,h in read(D/("cases_"+w)/"OUTPUT_SHA256.json").items():assert sha(D/("cases_"+w)/n)==h
for n,h in c["source_sha256"].items():assert sha(Path(n))==h
assert len(c["old_cohort_rows"])==len(ind["rows"])
assert {r["old_round_id"] for r in c["old_cohort_rows"]}=={r["old_round_id"] for r in ind["rows"]}
data={}
for arm,folder in [("baseline",J/("economic_"+w)),("joint",D/("gate_"+w))]:data[arm]=dict(rounds=csvread(folder/"joint/ROUNDS.csv"),actions=csvread(folder/"joint/ACTIONS.csv"),books=read(folder/"EXECUTION_BOOKS.json"),claims=read(folder/"joint/CLAIMS.json"))
numkeys={"q","price","fee","prior_round_net"}
def norm(v):
 if v is None:return ""
 if isinstance(v,float) and math.isnan(v):return ""
 return str(v)
def same(a,b):
 try:return math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-8)
 except (ValueError,TypeError):return norm(a)==norm(b)
def actions_check(actual,expected):
 assert len(actual)==len(expected),(len(actual),len(expected))
 for a,b in zip(actual,expected):
  for k,v in b.items():assert same(a.get(k),v),(k,a.get(k),v)
focus={};checks=[]
labels={"FIRST_ENTRY":"CONDITIONAL_PROXY_FIRST_ENTRY","REENTRY_AFTER_OWN_BUY_SELL_ALL":"PROXY_REENTRY_AFTER_THIS_ARM_PRIOR_BUY_AND_SELL_ALL","ENTRY_WITHOUT_PROVED_PRIOR_FLAT":"LATER_PROXY_ENTRY_WITHOUT_PROVED_PRIOR_SELL_ALL"}
for sid,package in c["whole_stock_paths"].items():
 focus[sid]={}
 for arm,p in package["paths"].items():
  d=data[arm];rr=[r for r in d["rounds"] if r["sid"]==sid];aa=[a for a in d["actions"] if a["sid"]==sid];ids={r["round_id"] for r in rr};assert {r["round_id"] for r in p["rounds"]}==ids
  actions_check(p["actions"],aa);assert p["claims"]==[x for x in d["claims"] if x.get("owner_round_id",x.get("round_id")) in ids]
  chronological=sorted(enumerate(aa),key=lambda z:(z[1]["day"],z[0]));bought=set();closed=set();typed={}
  for _,action in chronological:
   rid=action["round_id"]
   if action["side"]=="buy_core":typed[rid]="REENTRY_AFTER_OWN_BUY_SELL_ALL" if closed else "FIRST_ENTRY" if not bought else "ENTRY_WITHOUT_PROVED_PRIOR_FLAT";bought.add(rid)
   elif action["side"]=="sell_all" and rid in bought:closed.add(rid)
  detail=[]
  for r in rr:
   rid=r["round_id"];pack=next(x for x in p["rounds"] if x["round_id"]==rid);own=[a for a in aa if a["round_id"]==rid];actions_check(pack["actions"],own);assert pack["execution_book"]==d["books"].get(rid)
   assert pack["participation_identity"]==labels.get(typed.get(rid),"NO_INITIAL_PROXY_FILL"),(sid,arm,rid,"LABEL")
   for key in ["sid","event_id","owner_lane","signal_day","entry_day","exit_day","status","entry_q","entry_price","entry_fee","added_q","net_pnl","cash_after_payouts","receivable_after_payouts","dividend_net80_total"]:assert same(pack.get(key),r.get(key)),(sid,arm,rid,key)
   detail.append(dict(round_id=rid,lane=r["owner_lane"],signal_day=r["signal_day"],entry_day=r["entry_day"],exit_day=r["exit_day"],entry_q=r["entry_q"],added_q=r["added_q"],status=r["status"],participation=typed.get(rid,"NO_INITIAL_PROXY_FILL"),fees=sum(float(a["fee"] or 0) for a in own),net_pnl=r["net_pnl"],book_responsibility=d["books"].get(rid,{}).get("responsibility"),actions=own))
  assert p["stock"]==stocks[sid,arm]
  focus[sid][arm]=dict(stock=p["stock"],rounds=detail,claims=p["claims"],total_buy_core_qty=sum(float(a["q"]) for a in aa if a["side"]=="buy_core"),total_add_qty=sum(float(a["q"]) for a in aa if "buy" in a["side"] and a["side"]!="buy_core"),action_counts=dict(Counter(a["side"] for a in aa)))
  checks.append(dict(sid=sid,arm=arm,rounds=len(rr),actions=len(aa),claims=len(p["claims"])))
rows={r["old_round_id"]:r for r in c["old_cohort_rows"]}
for r in ind["rows"]:
 p=rows[r["old_round_id"]];assert p["sid"]==r["sid"] and p["old_full_net"]==r["old_net"]
 assert {x["round_id"] for x in p["same_original_receipt_new_registered"]}==set(r["same_receipt_registered"])
 nxt=p["next_new_proxy_entry_on_or_after_old_signal"];expected=r["next_buy_on_or_after_original_signal"]
 assert (nxt["round_id"] if nxt else None)==(expected["round_id"] if expected else None)
 assert p["new_unknown"]==r["new_stock_unknown"]
out=dict(window=w,case_package_pass=True,old_rounds_retained=len(rows),whole_stock_arm_checks=checks,focus={sid:focus[sid] for sid in ["000977.SZ","002174.SZ"]},economic_executions=0)
p=D/"independent_post_run_audit"/("sealed_cohort_cases_"+w+".json")
with p.open("x") as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
print("PASS",w,len(rows),len(checks))
for sid,arms in out["focus"].items():
 print(sid)
 for arm,p in arms.items():print(arm,json.dumps(p,ensure_ascii=False))

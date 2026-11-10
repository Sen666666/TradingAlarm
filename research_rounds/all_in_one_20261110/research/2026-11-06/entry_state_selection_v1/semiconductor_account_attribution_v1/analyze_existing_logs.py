import gzip,json,pandas as pd,collections,pathlib,hashlib,math
from decimal import Decimal as D
R=pathlib.Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
P=R/"account_comparison_continuous_v1/run_1200000/pair"
S=R/"semiconductor_h1_scope_v1"
roster=pd.read_csv(S/"ALL_126_COVERAGE_WITH_NAMES.csv")
timing=pd.read_csv(S/"ALL_120_NAMED_SIGNAL_TIMING.csv")
strict=timing[timing.exact_base&timing.exact_end].copy()
ids=set(strict.sid); double=set(strict.loc[strict.H1_return>=1,"sid"])
daily_sig=pd.read_parquet(S/"ENRICHED_DAILY.parquet")
sig=daily_sig[daily_sig.day.le("2026-05-15") & daily_sig.sid.isin(ids)].copy()
a=json.load(gzip.open(P/"PVR.json.gz","rt"))
def logs(name,start="2026-01-01"):
 return [x for x in [json.loads(l) for l in gzip.open(P/name,"rt") if ('"PVR"' in l and ('2026-' in l or '2025-12-31' in l))] if x["account"]=="PVR"]
op=logs("opportunities.jsonl.gz"); op=[x for x in op if x["sid"] in ids]
fund=logs("funding.jsonl.gz"); fund=[x for x in fund if x["sid"] in ids]
daily=logs("daily.jsonl.gz")
ind=logs("industry.jsonl.gz");ind=[x for x in ind if x["sector"]=="URFI881121"]
rank=logs("rank-policy.jsonl.gz");rank=[x for x in rank if x["sid"] in ids]
decs=[x for x in a["decisions"] if x["at"][:10]>="2025-12-31"]
intents=[dict(day=d["at"][:10],**i) for d in decs for i in d["intents"] if i["sid"] in ids]
tr=[x for x in a["trades"] if x["security_id"] in ids and x["at"]>="2026"]
rounds=pd.read_csv(R/"selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv")
rounds=rounds[(rounds.account=="PVR")&rounds.sid.isin(ids)&rounds.entry_day.ge("2026")].copy()
print("LOADED",len(sig),len(op),len(fund),len(daily),len(intents),len(tr),len(rounds))
print("sig stockcount",sig.sid.nunique(),"op stockcount",len(set(x["sid"] for x in op)))
print("rounds",rounds[["sid","entry_day","closed_day","layers","round_pnl","round_cost","closed"]].to_dict("records"))
print("industry",ind)
op26=[x for x in op if x["day"]>="2026"]
fund26=[x for x in fund if x["at"]>="2026"]
int26=[x for x in intents if x["day"]>="2026"]
opmap={(x["sid"],x["day"]):x for x in op}
imap={(x["sid"],x["day"],x["role"]):x for x in intents}
dmap={x["at"][:10]:x for x in daily}
days=sorted(dmap); nextday=dict(zip(days,days[1:]))
fmap=collections.defaultdict(list)
for x in fund:fmap[(x["sid"],x["at"][:10],x["role"],"open" if "09:30" in x["at"] else "close")].append(x)
buy_by_signal=collections.defaultdict(list)
for t in tr:
 if t["side"]=="buy":buy_by_signal[(t["security_id"],t["signal_at"][:10], "core" if t["kind"]=="core" else "mobile")].append(t)
cp=[]
for z in sig[sig.old_receipt.eq(True)].to_dict("records"):
 sid,day=z["sid"],z["day"];o=opmap.get((sid,day));i=imap.get((sid,day,"mobile"));nd=nextday.get(day);fr=fmap.get((sid,nd,"mobile","open"),[]) if nd else [];cr=fmap.get((sid,day,"mobile","close"),[])
 row=dict(sid=sid,name=z["name"],day=day,cp_id=o.get("CP1_id") if o else None,sector_auth=z["sector_authorization"],sector_E0=z["sector_E0"],stage=z["sector_stage"],I_root=z["I_root"],held=o["held"] if o else None,mobile_Q=o["mobile_Q"] if o else None,barriers=o["barriers"] if o else None,pending=bool(i),rank=i.get("priority_rank") if i else None,PVR=z["PVR_score"],close_reasons=[x["result"] for x in cr],open_day=nd,open_reasons=[x["result"] for x in fr],fill=buy_by_signal.get((sid,day,"mobile"),[]))
 if o is None:cat="missing_opportunity"
 elif not o["CP1_id"]:cat="missing_receipt_mapping"
 elif "mobile" not in o["roles"]:cat="stock_eligibility"
 elif o["barriers"]:cat="close_barrier"
 elif not i:cat="close_size_or_nominal"
 elif nd is None:cat="cutoff_pending"
 elif row["fill"]:cat="filled"
 elif fr:cat="open_rejected"
 else:cat="same_stock_core_or_pending_skip_unidentified"
 row["category"]=cat;cp.append(row)
print("CP FUNNEL",len(cp),len({x["sid"] for x in cp}),collections.Counter(x["category"] for x in cp))
print("CP COUNT alignment",sum(x["CP1_id"] is not None for x in op26),len(cp),set((x["sid"],x["day"]) for x in op26 if x["CP1_id"])-set((x["sid"],x["day"]) for x in cp))
for tag,pool in [("112",ids),("51",double)]:
 c=[x for x in cp if x["sid"] in pool];o=[x for x in op26 if x["sid"] in pool];ii=[x for x in int26 if x["sid"] in pool]
 print(tag,"stocks",len(pool),"sig_I",sig[sig.sid.isin(pool)&sig.i_target.eq(1)].sid.nunique(),"sig_i_buy",sig[sig.sid.isin(pool)&sig.i_buy.eq(True)].sid.nunique(),"CP",len(c),len({x["sid"] for x in c}))
 for k in sorted(set(x["category"] for x in c)):
  cc=[x for x in c if x["category"]==k];print(k,len(cc),len({x["sid"] for x in cc}))
 print("authCP",sum(bool(x["sector_auth"]) for x in c),len({x["sid"] for x in c if x["sector_auth"]}),"pending",len(ii),len({x["sid"] for x in ii}),"core",sum(x["role"]=="core" for x in ii),len({x["sid"] for x in ii if x["role"]=="core"}),"mobile",sum(x["role"]=="mobile" for x in ii),len({x["sid"] for x in ii if x["role"]=="mobile"}))
 print("CP reasons",collections.Counter(r for x in c for r in x["close_reasons"]+x["open_reasons"]))
print("unidentified",[(x["sid"],x["day"],x["category"]) for x in cp if "unidentified" in x["category"] or "missing" in x["category"]])
profiles=[]
def dates(rows):return sorted(set(x["day"] for x in rows))
for t in strict.to_dict("records"):
 sid=t["sid"];g=sig[sig.sid.eq(sid)];oo=[x for x in op26 if x["sid"]==sid];cc=[x for x in cp if x["sid"]==sid];ii=[x for x in int26 if x["sid"]==sid];ff=[x for x in fund26 if x["sid"]==sid];tt=[x for x in tr if x["security_id"]==sid];bb=[x for x in tt if x["side"]=="buy"]
 p=dict(sid=sid,name=t["name"],H1_return_posthoc=t["H1_return"],double_posthoc=sid in double,signal_rows=len(g),first_observation=min(g.day),E0_first=bool(g.iloc[0].e0_target),I_first=bool(g.iloc[0].i_target),I_root_first=g.iloc[0].I_root,first_i_buy=min(g.loc[g.i_buy.eq(True),"day"],default=None),first_CP=min((x["day"] for x in cc),default=None),first_authorized_CP=min((x["day"] for x in cc if x["sector_auth"]),default=None),CP_count=len(cc),first_core_role=min((x["day"] for x in oo if "core" in x["roles"]),default=None),first_core_pending=min((x["day"] for x in ii if x["role"]=="core"),default=None),first_mobile_pending=min((x["day"] for x in ii if x["role"]=="mobile"),default=None),pending_count=len(ii),pending_CP_count=sum(x["role"]=="mobile" for x in ii),first_buy=min((x["at"] for x in bb),default=None),buy_layers=len(bb),fund_reasons=dict(collections.Counter(x["result"] for x in ff)),CP_categories=dict(collections.Counter(x["category"] for x in cc)))
 p["terminal_group"]="bought" if bb else "pending_no_fill" if ii else "never_pending"
 profiles.append(p)
print("terminal",collections.Counter(p["terminal_group"] for p in profiles))
print("double_terminal",collections.Counter(p["terminal_group"] for p in profiles if p["double_posthoc"]))
print("never pending",[(p["sid"],p["name"],p["double_posthoc"],p["CP_count"],p["fund_reasons"]) for p in profiles if p["terminal_group"]=="never_pending"])
print("no CP",[(p["sid"],p["name"]) for p in profiles if not p["CP_count"]])
print("barriers",collections.Counter(k for o in op26 if o["roles"] for k in o["barriers"]))
print("mobileQ failures",collections.Counter(k for x in cp if x["category"]=="stock_eligibility" for k in x["barriers"]))
for tag,pool in [("all",ids),("double",double)]:
 f=[x for x in fund26 if x["sid"] in pool and "09:30" in x["at"]];rej=[x for x in f if x["result"]!="reserved"]
 print(tag,"fund_events",len(f),"rej",len(rej),"reject_unique",len({x["sid"] for x in rej}),"cash_rej",sum("cash_or_original_reserve" in x["result"] for x in rej),len({x["sid"] for x in rej if "cash_or_original_reserve" in x["result"]}),"stock_by_reason",{k:len({x["sid"] for x in rej if k in x["result"].split(",")}) for k in sorted(set(k for x in rej for k in x["result"].split(",")))})
import importlib.util,sys
lp=pathlib.Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/sector_account.py")
sys.path.insert(0,str(lp.parent))
sp=importlib.util.spec_from_file_location("audit_ledger_definitions_only",lp);L=importlib.util.module_from_spec(sp);sys.modules[sp.name]=L;sp.loader.exec_module(L)
rulespath=pathlib.Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json")
rules=json.loads(rulespath.read_text())
def version(kind,sid,day):
 z=[x for x in rules[kind][sid] if x["from"]<=day and (x["to"] is None or day<x["to"])]
 assert len(z)==1,(kind,sid,day);return z[0]
def qr(sid,day):return L.QuantityRule(**version("quantity_versions",sid,day)["rule"])
def fee_schedule(sid,day):
 venue=version("venue_versions",sid,day)["venue"];s=version("fee_versions",venue,day)["schedule"]
 return L.FeeSchedule(s["schedule_id"],tuple(L.FeeComponent(**x) for x in s["components"]))
def fee(q,px,sid,day,side):
 return sum(fee_schedule(sid,day).incremental(side,D(q)*px,{}, {},1,shares=q,par_value=rules["security_metadata"][sid].get("par_value")).values(),D(0))
sigmap={(x["sid"],x["day"]):x for x in sig.to_dict("records")}
minimum=[]
for f in fund26:
 if "15:10" not in f["at"] or f["result"] not in ("minimum_unit_exceeds_risk_or_nominal_cap","no_nominal_gap"):continue
 sid,day=f["sid"],f["at"][:10];z=sigmap[(sid,day)];o=opmap[(sid,day)];nav=D(dmap[day]["nav"]);px=D(str(z["raw_close"]));qmin=qr(sid,day).buy_minimum
 m=dict(sid=sid,day=day,role=f["role"],original_result=f["result"],raw_close=px,legal_minimum=qmin,decision_NAV=nav,original_i_buy=z["i_buy"],original_CP=z["old_receipt"],original_core_Q=o["core_Q"],original_mobile_Q=o["mobile_Q"],original_roles=o["roles"])
 if f["role"]=="core":
  assert o["core_Q"] is True and "core" in o["roles"] and z["i_buy"] is True
  floor=D(str(z["i_floor"]))/D(str(z["factor"]));ref=px*D("1.0005");stop=floor*D(".9995");risk=D(qmin)*(ref-stop)+fee(qmin,ref,sid,day,"buy")+fee(qmin,stop,sid,day,"sell");rb=nav*D(".0025");gross=D(qmin)*ref;nb=nav*D(".10")
  rf=risk>rb;nf=gross>nb
  assert rf or nf,(sid,day,risk,rb,gross,nb)
  m.update(factor=z["factor"],I_floor_adjusted=z["i_floor"],I_floor_raw=floor,reference_price=ref,minimum_gross=gross,nominal_cap=nb,minimum_protection_risk_with_both_fees=risk,risk_budget=rb,risk_block=rf,nominal_block=nf,classification="both_risk_and_nominal" if rf and nf else "risk_only" if rf else "nominal_only")
 else:
  assert z["old_receipt"] is True and "mobile" in o["roles"]
  held=D(dmap[day]["positions"].get(sid,0));budget=min(nav*D(".02"),max(D(0),nav*D(".10")-held*px));gross=D(qmin)*px
  assert qr(sid,day).buy_floor(int(budget/px))==0
  m.update(held=held,nominal_two_percent=nav*D(".02"),budget=budget,minimum_gross_no_slippage=gross,shortfall=gross-budget,classification="positive_2pct_or_stockgap_below_minimum" if budget>0 else "zero_stock_gap")
 minimum.append(m)
never={p["sid"] for p in profiles if p["terminal_group"]=="never_pending"}
print("MINIMUM_all",len(minimum),collections.Counter((x["role"],x["classification"]) for x in minimum))
print("MINIMUM_never26",len([x for x in minimum if x["sid"] in never]),collections.Counter((x["role"],x["classification"]) for x in minimum if x["sid"] in never))
for sid in sorted(never):
 c=[x for x in minimum if x["sid"]==sid and x["role"]=="core"];m=[x for x in minimum if x["sid"]==sid and x["role"]=="mobile"];o=[x for x in op26 if x["sid"]==sid and "core" in x["roles"] and not x["barriers"]]
 assert len(c)==len(o),(sid,len(c),len(o))
 print("NEVER",sid,len(c),dict(collections.Counter(x["classification"] for x in c)),len(m),"firstCore",{k:str(c[0][k]) for k in ("day","raw_close","legal_minimum","I_floor_raw","minimum_protection_risk_with_both_fees","risk_budget","minimum_gross","nominal_cap")},"firstMobile",{k:str(m[0][k]) for k in ("day","raw_close","minimum_gross_no_slippage","budget")})
import ast
from types import SimpleNamespace as NS
lrpath=pathlib.Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py")
astsrc=ast.parse(lrpath.read_text()); selected=ast.Module(body=[n for n in astsrc.body if isinstance(n,ast.FunctionDef) and n.name in ("fees","protection_risk","maximum_quantity","resize_core")],type_ignores=[])
env=dict(D=D,ZERO=D(0),ONE=D(1),RISK=D(".0025"),SLIP=D(".0005"));exec(compile(selected,str(lrpath),"exec"),env)
core_exact=0
for o in op26:
 if "core" not in o["roles"] or o["barriers"]:continue
 sid,day=o["sid"],o["day"];z=sigmap[(sid,day)]
 q=NS(raw_price=D(str(z["raw_close"])),quantity=qr(sid,day),fees=fee_schedule(sid,day),par_value=rules["security_metadata"][sid].get("par_value"))
 i=dict(quote=q,floor=D(str(z["i_floor"])))
 env["resize_core"](i,D(dmap[day]["nav"]),D(str(z["factor"])))
 original=imap.get((sid,day,"core")); fr=fmap.get((sid,day,"core","close"),[])
 if original:
  for k in ("cap","budget","risk_budget","frozen_floor_raw","signal_price","reference_price"):
   assert D(str(i[k]))==D(str(original[k])),(sid,day,k,i[k],original[k])
 else:assert i.get("size_reject") in [x["result"] for x in fr],(sid,day,i,fr)
 core_exact+=1
print("CORE_NATIVE_SIZING_EXACT",core_exact)
print("MOBILE all held",collections.Counter((int(x["held"]),x["budget"]==x["nominal_two_percent"]) for x in minimum if x["role"]=="mobile"))
print("min unique", {role:len({x["sid"] for x in minimum if x["role"]==role}) for role in ("core","mobile")})
for x in cp:
 o=opmap[(x["sid"],x["day"])]
 if not x["sector_E0"]:x["eligibility_stage"]="sector_E0_off"
 elif not x["sector_auth"]:x["eligibility_stage"]="sector_E0_on_attempt_inactive"
 elif "mobile" not in o["roles"]:x["eligibility_stage"]="other_native_eligibility"
 else:x["eligibility_stage"]="sector_authorized_and_mobile_Q"
print("CP stage",collections.Counter(x["eligibility_stage"] for x in cp))
print("CP stage category",collections.Counter((x["eligibility_stage"],x["category"]) for x in cp))
rmap={(x["sid"],x["day"]):x for x in rank}
for p in profiles:
 rr=[x for x in rank if x["sid"]==p["sid"] and x["day"]>="2026"];p["best_actual_pending_queue_position"]=min((x["final_slot"]+1 for x in rr),default=None)
 p["ever_pending_top20"]=any(x["final_slot"]<20 for x in rr)
 p["first_pending_queue_position"]=rr[0]["final_slot"]+1 if rr else None
 print_fields=[]
for tag,pool in [("112",ids),("51",double)]:
 pp=[p for p in profiles if p["sid"] in pool]
 print(tag,"ever_pending_top20",sum(p["ever_pending_top20"] for p in pp),"unbought_top20",sum(p["ever_pending_top20"] and not p["first_buy"] for p in pp),"no_fill_top5",[(p["sid"],p["name"],p["best_actual_pending_queue_position"]) for p in pp if not p["first_buy"] and p["best_actual_pending_queue_position"] is not None and p["best_actual_pending_queue_position"]<=5])
 print("minimum",collections.Counter((m["role"],m["classification"]) for m in minimum if m["sid"] in pool))

# Persist only independent diagnostic outputs, never source accounts or signals.
import numpy as np
OUT=R/"semiconductor_account_attribution_v1"
OUT.mkdir(exist_ok=True)
def norm(x):
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v) for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,x):(OUT/name).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
save("ALL_112_STOCK_PROFILES.json",profiles)
pd.DataFrame(profiles).drop(columns=["fund_reasons","CP_categories"]).to_csv(OUT/"ALL_112_STOCK_PROFILES.csv",index=False)
save("ALL_739_CP_EVENT_FUNNEL.json",cp)
save("ALL_1113_CLOSE_MINIMUM_DIAGNOSIS.json",minimum)
save("NEVER_PENDING_26_ALL_542_MINIMUM_DIAGNOSIS.json",[m for m in minimum if m["sid"] in never])
save("RAW_FILTERED_FUNDING_2026.json",fund26)
save("RAW_FILTERED_PENDING_2026.json",int26)
save("RAW_FILTERED_OPPORTUNITIES_2026.json",op26)
save("RAW_FILTERED_TRADES_2026.json",tr)
save("RAW_INDUSTRY_EVENTS_2026.json",ind)
save("ORIGINAL_ROUNDS_2026.json",rounds.to_dict("records"))
sources=[S/"ALL_120_NAMED_SIGNAL_TIMING.csv",S/"ENRICHED_DAILY.parquet",S/"ALL_126_COVERAGE_WITH_NAMES.csv",P/"PVR.json.gz",P/"daily.jsonl.gz",P/"funding.jsonl.gz",P/"opportunities.jsonl.gz",P/"rank-policy.jsonl.gz",P/"industry.jsonl.gz",P.parent/"PREDECLARED.json",lp,rulespath,lrpath,R/"selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv"]
save("SOURCE_HASHES.json",{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
save("METHOD.json",dict(account="1200000 PVR continuous 2022-01-01 to 2026-05-15, no annual reset",window=["2026-01-01","2026-05-15"],strict_stocks=112,double_posthoc=51,read_only_source_analysis=True,new_accounts=0,new_indicators=0,new_strategy_returns=False,scope="Current >=100亿元 fixed research pool, not PIT; historical price doubling only retrospective subgroup",core_pure_function_exact=core_exact,CP_events=len(cp),CP_unique_stocks=len({x["sid"] for x in cp}),funding_open_includes_4_intents_from_2025_12_31=True,CP_funnel_includes_only_2026_signal_dates=True,cutoff_pending_separate=True,ranking="priority_rank is a sparse original-slot key; actual queue position=final_slot+1; top20 diagnostic only, not actual execution cutoff",limitations=["Historical tradability unknown; source missing opens are not official suspension facts","No replay and no causal missed-profit claims","Funding reasons union failed routes and can overlap","No blocked amount claimed as independent capital requirement","H1 endpoint labels not used as selection reasons","Sector stage authorization alone is not full stock eligibility","Original opportunity barriers for non-core rows are event eligibility reasons; do not pretend all are the continuing MOBILE reason vector"]))
print("ARTIFACTS_SAVED",OUT)

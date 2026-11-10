import sys,json,collections,hashlib
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/shared_ab_entry_selection_attribution_v1");R=O.parent
S=R/"m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924"
def read(n):return json.loads((S/(n+".json")).read_text())
sys.path.insert(0,str(R/"m3_ab_shared_probe_v1/source_bridge_v1"));import bridge
s=bridge.load_original("2024_924")
j=read("EXACT_TRADE_JOURNAL");au=read("AUDIT");arc=read("ARCHIVES");dl={x["day"][:10]:x for x in read("DAY_LEDGER")}
er=pd.read_csv(O/"ALL_EVENT_FUNNEL.csv");reserve=pd.read_csv(O/"ACTUAL_INITIAL_RESERVATION_CONSTRAINTS.csv")
days=["2024-09-03","2024-09-13","2024-09-26","2024-09-27","2024-10-23","2024-12-03"]
details=[];summaries=[];zero=D(0)
for daystr in days:
 day=pd.Timestamp(daystr);prev=s.cal[s.cal<day][-1];q=collections.defaultdict(lambda:{"core":0,"add":0})
 for x in j:
  ad=pd.Timestamp(x["day"])
  if ad>day or (ad==day and x["side"].startswith("buy")):continue
  rid=x["round_id"];qty=int(x["q"]);side=x["side"]
  if side=="buy_core":q[rid]["core"]+=qty
  elif side=="buy_add":q[rid]["add"]+=qty
  elif side=="sell_add":q[rid]["add"]-=qty
  else:assert qty==sum(q[rid].values());q[rid]={"core":0,"add":0}
 promoted={x["round_id"] for x in au if x["type"]=="PROMOTED" and pd.Timestamp(x["day"])<=day}
 gross=zero;probecap=zero;proberisk=zero;nh=0;np=0
 for rid,parts in q.items():
  qty=sum(parts.values())
  if not qty:continue
  st=arc[rid];sid=st["sid"];s.load(sid);z=s.raw[sid].get(day);op=D(str(z["raw_open"]));fac=D(str(z["adjustment_factor"]));floor=D(str(s.facts[sid].get(prev)["i_floor"]))/fac
  cap=D(qty)*op;gross+=cap;nh+=1
  isprobe=rid not in promoted
  if isprobe:
   assert parts["add"]==0
   nominal=D(qty)*max(zero,op-floor);probecap+=cap;proberisk+=nominal;np+=1
   details.append(dict(open_day=daystr,round_id=rid,sid=sid,name=st["name"],signal_day=st["signal_day"],qty=qty,open=op,I_floor=floor,capital=cap,nominal_probe_risk=nominal))
 plan=next(x for x in au if x["type"]=="ALL_RESERVATIONS_COMPLETE" and x["day"].startswith(daystr))
 cash=D(plan["cash_before_fills"]);recv=D(dl[daystr]["OPEN"]["receivable"]);nav=cash+recv+gross
 buys=[x for x in j if x["day"].startswith(daystr) and x["side"].startswith("buy")]
 buycash=zero;newmark=zero
 for x in buys:
  sid=arc[x["round_id"]]["sid"];s.load(sid);op=D(str(s.raw[sid].get(day)["raw_open"]));qty=D(x["q"]);buycash+=qty*D(x["exact_price"])+D(x["exact_whole_order_fee"]);newmark+=qty*op
 assert nav-buycash+newmark==D(dl[daystr]["OPEN"]["NAV"]),(daystr,nav-buycash+newmark,dl[daystr]["OPEN"]["NAV"])
 rr=reserve[reserve.open_day.str.startswith(daystr)]
 ids=rr.event_id.tolist();es=er[er.event_id.isin(ids)]
 row=dict(open_day=daystr,original_signal_day=str(prev.date()),nav_before_reservations=nav,cash_before_fills=cash,held_names_after_original_sells=nh,probe_names_after_original_promotions=np,probe_capital=probecap,probe_nominal_risk=proberisk,total_probe_nominal_cap_before_new_fees=nav*D(".005"),probe_nominal_headroom_before_new_fees=nav*D(".005")-proberisk,original_INIT_attempts=len(rr),original_reserved_names=int((rr.shared_q>0).sum()),probe_risk_minimum_rejections=int(rr.last_reasons.str.contains("probe_risk",na=False).sum()),original_signal_top5=es.sort_values(["PVR_score","sid"],ascending=[False,True])[["sid","name","PVR_score","filled"]].head(5).to_dict("records"),provenance="Original funded path only; not a state reached by smaller-INIT policy")
 summaries.append(row)
pd.DataFrame(details).to_csv(O/"FIXED_DAYS_ORIGINAL_PROBE_HOLDINGS.csv",index=False)
(O/"FIXED_DAYS_ORIGINAL_PATH_SNAPSHOTS.json").write_text(json.dumps(summaries,ensure_ascii=False,indent=2,default=str))
assert all(bridge.sha(p)==h for p,h in s.hashes.items())
(O/"PATH_SNAPSHOT_QA.json").write_text(json.dumps(dict(original_snapshot_nav_exact_days=len(days),new_orders=0,new_fills=0,new_account_runs=0,source_hashes=s.hashes),ensure_ascii=False,indent=2))
for x in summaries:print(json.dumps({k:v for k,v in x.items() if k not in ["original_signal_top5","provenance"]},ensure_ascii=False,default=str));print("TOP_OLD_RISK",pd.DataFrame([d for d in details if d["open_day"]==x["open_day"]]).sort_values("nominal_probe_risk",ascending=False).head(4).to_dict("records") if x["probe_names_after_original_promotions"] else [])

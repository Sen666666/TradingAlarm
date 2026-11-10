import json,hashlib,sys,collections
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1");O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/shared_ab_entry_selection_attribution_v1")
S=R/"m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924"
Q=R/"m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1"
src=[S/(x+".json") for x in ["DECISIONS","SOURCE_ROUNDS","LAYER_REPORT","ACTIONS","AUDIT","ARCHIVES","DAY_LEDGER","EXACT_TRADE_JOURNAL"]]+[Q/"report/CORE_AND_FULL_ROUNDS.csv",Q/"economic/DECISIONS.csv",R/"m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv"]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in src}
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def read(n):return json.loads((S/(n+".json")).read_text())
d=pd.DataFrame(read("DECISIONS"));sr=pd.DataFrame(read("SOURCE_ROUNDS"));a=pd.DataFrame(read("ACTIONS"));audit=read("AUDIT");arc=read("ARCHIVES")
l=pd.DataFrame(read("LAYER_REPORT"));l=l[l.layer=="core"].copy();l["shared_core_net"]=pd.to_numeric(l.NET80);l["shared_core_return"]=pd.to_numeric(l.return_on_layer_buy_cash);l["shared_core_buy_cash"]=pd.to_numeric(l.buy_cash)
ev=d.merge(sr[["event_id","round_id","status"]],on=["event_id","round_id"],how="left").merge(l[["round_id","shared_core_net","shared_core_return","shared_core_buy_cash"]],on="round_id",how="left")
ev["signal_month"]=ev.day.str[:7];ev["filled"]=ev.shared_core_net.notna();ev["win"]=ev.shared_core_net>0
ev["global_pending_rank"]=None
for day,g in ev[ev.selected].groupby("day"):
 order=g.sort_values(["PVR_score","sid"],ascending=[False,True]).index
 ev.loc[order,"global_pending_rank"]=range(1,len(order)+1)
old=pd.read_csv(Q/"report/CORE_AND_FULL_ROUNDS.csv",low_memory=False);old=old[old.arm=="A_UNION_B"].copy();known=old[old.evidence_usable_closed==True].copy();od=pd.read_csv(Q/"economic/DECISIONS.csv",low_memory=False)
ev=ev.merge(od[["event_id","decision","selected","stock_state_before"]].rename(columns={"decision":"old_decision","selected":"old_selected","stock_state_before":"old_stock_state"}),on="event_id",how="left",validate="one_to_one")
ev=ev.merge(known[["event_id","core_net","core_return","entry_q","entry_price"]].rename(columns={"core_net":"old_independent_core_net","core_return":"old_independent_core_return","entry_q":"old_independent_q","entry_price":"old_independent_price"}),on="event_id",how="left",validate="one_to_one")
ev.to_csv(O/"ALL_EVENT_FUNNEL.csv",index=False)
filled=ev[ev.filled].copy()
context=pd.DataFrame([dict(round_id=k,**{f:v.get(f) for f in ["g_grade","i_buy","sector_run_age","sector_M3_n","sector_N","sector_K","sector_delta3","i_floor","raw_close","factor","previous_stock_state"]}) for k,v in arc.items()])
filled=filled.merge(context,on="round_id",how="left",validate="one_to_one")
filled["signal_I_log_distance"]=((filled.raw_close*filled.factor)/filled.i_floor).map(lambda x:__import__("math").log(x))
filled.to_csv(O/"ACTUAL_80_FIRST_LAYERS.csv",index=False)
reservation=[]
for index,x in enumerate(audit):
 if x["type"] not in ["RESERVED","BUDGET_REJECTED"] or x["kind"]!="INIT":continue
 ts=x.get("trials",[]);reasons=ts[-1]["reasons"] if ts else ["NO_QUANTITY_TRIAL"]
 reservation.append(dict(round_id=x["round_id"],open_day=x["day"],audit_order=index,result=x["type"],original_formula_q=x["original_formula_q"],before_shared_q=x["before_shared_q"],shared_q=x["shared_q"],minimum_q=x["minimum_buy_quantity"],last_trial_q=ts[-1]["q"] if ts else None,last_trial_fee_risk=ts[-1].get("fee_risk") if ts else None,last_reasons=",".join(reasons),initial_reasons=",".join(ts[0]["reasons"]) if ts else "NO_QUANTITY_TRIAL"))
rr=pd.DataFrame(reservation).merge(sr[["round_id","event_id","sid","name","signal_day","PVR_score"]],on="round_id")
rr.to_csv(O/"ACTUAL_INITIAL_RESERVATION_CONSTRAINTS.csv",index=False)
tail=known[known.core_return>=.3].merge(ev[["event_id","decision","filled","status","shared_core_net","global_pending_rank"]],on="event_id",how="left",suffixes=("_old","_shared"))
fby={s:g[["day","shared_core_net","shared_core_return"]].to_dict("records") for s,g in ev[ev.filled].groupby("sid")}
tail["shared_any_later_or_other_fill"]=tail.sid.isin(fby)
tail["shared_same_stock_all_fills"]=tail.sid.map(lambda x:json.dumps(fby.get(x,[]),ensure_ascii=False))
tail.to_csv(O/"OLD_TAIL_EVENT_PARTICIPATION_ONLY.csv",index=False)
monthly=[]
for m,g in ev.groupby("signal_month"):
 og=known[known.signal_day.str.startswith(m)]
 monthly.append(dict(signal_month=m,emitted=len(g),feasible=int(g.decision.isin(["PASS_NOT_TOP2","SELECTED_PENDING"]).sum()),selected=int(g.selected.sum()),filled=int(g.filled.sum()),wins=int(g.win.sum()),shared_rate=float(g.win.sum()/g.filled.sum()),old_known_n=len(og),old_wins=int((og.core_net>0).sum()),old_rate=float((og.core_net>0).mean()),old_tail30=int((og.core_return>=.3).sum()),shared_filled_pvr_median=float(g.loc[g.filled,"PVR_score"].median()),shared_pending_pvr_median=float(g.loc[g.selected,"PVR_score"].median()),all_emitted_pvr_median=float(g.PVR_score.median())))
pd.DataFrame(monthly).to_csv(O/"SIGNAL_MONTH_COMPOSITION.csv",index=False)
distribution=[]
for grouping,labels in [("stage",["emitted","feasible","selected","filled"]),("outcome",["filled_win","filled_loss"])]:
 for label in labels:
  mask=pd.Series(True,index=ev.index)
  if label=="feasible":mask=ev.decision.isin(["PASS_NOT_TOP2","SELECTED_PENDING"])
  elif label=="selected":mask=ev.selected
  elif label=="filled":mask=ev.filled
  elif label=="filled_win":mask=ev.filled&ev.win
  elif label=="filled_loss":mask=ev.filled&~ev.win
  z=ev[mask]
  distribution.append(dict(grouping=grouping,group=label,n=len(z),stocks=z.sid.nunique(),sectors=z.sector.nunique(),A=int((z.event_type=="A_SECTOR_BIRTH").sum()),B=int((z.event_type=="B_STOCK_BIRTH_DURING_SECTOR").sum()),PVR_p10=z.PVR_score.quantile(.1),PVR_median=z.PVR_score.median(),PVR_p90=z.PVR_score.quantile(.9),PVR_mean=z.PVR_score.mean()))
pd.DataFrame(distribution).to_csv(O/"SIGNAL_DISTRIBUTIONS.csv",index=False)
fixed_days=["2024-09-02","2024-09-12","2024-09-25","2024-09-26","2024-10-22","2024-12-02"]
ev[ev.day.str[:10].isin(fixed_days)].merge(rr[["event_id","open_day","last_reasons","last_trial_fee_risk","shared_q"]],on="event_id",how="left").to_csv(O/"FIXED_MARKET_DAY_ORIGINAL_EVENTS.csv",index=False)
matched=ev[ev.filled & ev.old_independent_core_net.notna()]
reason=collections.Counter(r for x in reservation if x["result"]=="BUDGET_REJECTED" for r in x["last_reasons"].split(","))
summary=dict(emitted=len(ev),decisions=ev.decision.value_counts().to_dict(),old_known_n=len(known),old_known_wins=int((known.core_net>0).sum()),shared_fills=int(ev.filled.sum()),shared_wins=int(ev.win.sum()),shared_matched_old_known=len(matched),matched_sign_differences=int(((matched.shared_core_net>0)!=(matched.old_independent_core_net>0)).sum()),new_other_old_decisions=ev[ev.filled&ev.old_independent_core_net.isna()].old_decision.value_counts().to_dict(),budget_reject_reasons_last_minimum=dict(reason),old_tail30=len(tail),old_tail_shared_status=tail.status_shared.fillna("NOT_SELECTED").value_counts().to_dict(),old_tail_same_stock_any_fill=int(tail.shared_any_later_or_other_fill.sum()),old_weighted_rate_by_shared_signal_month=sum(x["old_rate"]*x["filled"]/80 for x in monthly),new_account_runs=0)
save("ATTRIBUTION_SUMMARY.json",summary);save("INPUT_HASHES.json",hashes)
# Fixed first OPEN only: independently reconstruct original empty wallet reservations.
sys.path.insert(0,str(R/"m3_ab_shared_probe_v1/source_bridge_v1"));import bridge
sys.path.insert(0,str(R/"m3_ab_shared_probe_v1/shared_feasibility_v1"));from limits_v3 import Exposure,Snapshot,ReserveBook
s=bridge.load_original("2024_924")
day=s.pd.Timestamp("2024-09-03");queue=ev[(ev.selected)&ev.day.str.startswith("2024-09-02")].sort_values(["PVR_score","sid"],ascending=[False,True])
assert len(queue)==42
N=D("1200000");zero=D(0)
props=[]
for x in queue.to_dict("records"):
 sid=x["sid"];s.load(sid);z=s.raw[sid].get(day);prev=s.raw[sid].get(s.pd.Timestamp("2024-09-02"));st=arc[x["round_id"]]
 px=D(str(z["raw_open"]))*(1+s.SLIP);floor=D(str(st["i_floor"]))/D(str(prev["adjustment_factor"]))
 qr,fs,par=s.getmeta(sid,day);assert D(str(z["raw_open"]))>floor
 for label,cap in [("ORIGINAL_025",D(".0025")),("EXPLORATORY_0125",D(".00125"))]:
  q,bf,risk,_,_=s.size(sid,day,px,floor,N*D(".02"),N*cap,int(st["prior20_capacity"]))
  props.append(dict(label=label,sid=sid,name=x["name"],rid=x["round_id"],sector=x["sector"],pvr=x["PVR_score"],px=px,floor=floor,qr=qr,fs=fs,par=par,formula_q=q,q=qr.buy_floor(min(q,int(x["close_q"]))),cap=N*cap))
outrows=[]
for label in ["ORIGINAL_025","EXPLORATORY_0125"]:
 book=ReserveBook(Snapshot(N,zero,N,N,(),(),(),"ACTUAL_ORIGINAL_EMPTY_FIRST_OPEN_20240903"))
 for rank,p in enumerate([p for p in props if p["label"]==label],1):
  q=p["q"];initialq=q;firstreasons=[];lastreasons=[]
  while q>0:
   fee=s.fee(q,p["px"],p["fs"],"buy",p["par"]);risk=max(zero,D(q)*(p["px"]-p["floor"]*(1-s.SLIP))+fee+s.fee(q,p["floor"]*(1-s.SLIP),p["fs"],"sell",p["par"]))
   assert risk<=p["cap"]
   prop=Exposure(p["sid"],p["rid"],p["sector"],"probe",q,p["px"],p["floor"],fee,"live")
   reasons=book.reasons(prop);lastreasons=reasons
   if not firstreasons:firstreasons=reasons
   if not reasons:
    assert not book.reserve(prop);break
   q=p["qr"].buy_floor(q-1)
  fee=s.fee(q,p["px"],p["fs"],"buy",p["par"]) if q else zero
  nom=D(q)*max(zero,p["px"]-p["floor"])
  outrows.append(dict(arm=label,rank=rank,round_id=p["rid"],sid=p["sid"],name=p["name"],sector=p["sector"],PVR_score=p["pvr"],proposed_q=initialq,reserved_q=q,minimum_q=p["qr"].buy_minimum,price=p["px"],floor=p["floor"],nominal_risk=nom,buy_cash=D(q)*p["px"]+fee,buy_fee=fee,buy_fee_pct=(fee/(D(q)*p["px"])*100 if q else None),first_reasons=",".join(firstreasons),last_reasons=",".join(lastreasons),actual_fill_not_performed=True))
base={x["round_id"]:x for x in outrows if x["arm"]=="ORIGINAL_025"}
actual=rr[rr.open_day.str.startswith("2024-09-03")]
assert len(actual)==42
for x in actual.to_dict("records"):assert base[x["round_id"]]["reserved_q"]==x["shared_q"],(x["round_id"],base[x["round_id"]]["reserved_q"],x["shared_q"])
odf=pd.DataFrame(outrows);odf.to_csv(O/"FIXED_FIRST_OPEN_RESERVATION_COMPARISON.csv",index=False)
sm=[]
for arm,g in odf.groupby("arm"):
 g=g[g.reserved_q>0]
 sm.append(dict(arm=arm,reserved_names=len(g),sectors=g.sector.nunique(),cash=sum(g.buy_cash,zero),buy_fees=sum(g.buy_fee,zero),nominal_risk=sum(g.nominal_risk,zero),minimum_lot_count=int((g.reserved_q==g.minimum_q).sum()),mean_buy_fee_pct=sum(g.buy_fee_pct,zero)/D(len(g)),maximum_buy_fee_pct=max(g.buy_fee_pct),conditional_names=g[["sid","name","reserved_q"]].to_dict("records"),no_fills=True,no_future_path=True))
save("FIXED_FIRST_OPEN_SUMMARY.json",sm)
allhash={**hashes,**s.hashes}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in allhash.items())
save("FINAL_INPUT_HASHES.json",allhash)
save("QA.json",dict(event_ids_unique=not ev.event_id.duplicated().any(),first_open42_actual_quantity_exact=True,unchanged_source_files=len(allhash),original_engine_advance_calls=0,alternative_account_runs=0,alternate_fills=0,parameter_grid_search=0))
print(json.dumps(summary,ensure_ascii=False,default=str));print(json.dumps(sm,ensure_ascii=False,default=str))

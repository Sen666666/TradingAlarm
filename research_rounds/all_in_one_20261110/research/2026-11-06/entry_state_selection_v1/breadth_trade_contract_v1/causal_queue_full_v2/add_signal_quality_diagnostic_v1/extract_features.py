from pathlib import Path
import pandas as pd,numpy as np,json,sys,hashlib
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
P=R/"breadth_trade_contract_v1/causal_queue_full_v2"
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
sys.path.insert(0,"/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
from features import original_pvr, original_observation_clock
manifest={x["symbol"]:x for x in json.loads((U/"STOCK_MANIFEST.json").read_text())}
sel=pd.read_csv(P/"SEALED_CLOSE_SELECTED.csv")
panel=pd.read_parquet(R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet").sort_values(["sector","day"])
sectors={}
for sec,g in panel.groupby("sector"):
 g=g.set_index("day")
 g["breadth_change1"]=g.M3_right_known.diff()
 g["breadth_change3"]=g.M3_right_known.diff(3)
 g["breadth_run"]=g.M3_candidate.eq(1).groupby(g.M3_candidate.ne(1).cumsum()).cumsum()
 sectors[sec]=g
# Four fixed questions, no optimization: PVR progress versus previous CP; risk distance;
# close/mean-price joint frontier; breadth continuation. All decision-close fields.
parts=[]
for policy,fn in [("original","dual_budget_ablation_v1/baseline"),("dual","dual_budget_ablation_v1/dual"),("uhalf","dual_plus_half_profit_v1/uhalf")]:
 z=pd.read_csv(P/fn/"ALL_SHADOW_ROUNDS.csv")
 z=z[z.arm.eq("M3")&z.event_type.eq("FALSE_TO_TRUE")&z.window.isin(["2022","2024_924"])]
 for rr in z.to_dict("records"):
  actions=json.loads(rr["actions"]) if isinstance(rr["actions"],str) else []
  buy=next((a for a in actions if a["side"]=="buy_add"),None)
  if not buy:continue
  a=next(x for x in json.loads(rr["add_admission_details"]) if x["q"]>0)
  ex=next((x for x in actions if x["side"] in ("sell_add","sell_all") and x["day"]>=buy["day"]),None)
  cost=buy["q"]*float(buy["price"])+float(buy["fee"])
  net=buy["q"]*float(ex["price"])-float(ex["fee"])*buy["q"]/ex["q"]-cost if ex else np.nan
  row=dict(policy=policy,event_id=rr["event_id"],sid=rr["sid"],name=rr["name"],industry=rr["industry"],sector=rr["event_id"].split("|")[-1],window=rr["window"],entry_day=rr["entry_day"],event_day=rr["day"],round_status=rr["status"],unknown_day=rr.get("unknown_day"),round_net=rr.get("net_pnl"),round_return=rr.get("net_return_on_buy_cash"),entry_cash=rr["entry_price"]*rr["entry_q"]+rr["entry_fee"],core_entry_price=rr["entry_price"],core_entry_fee=rr["entry_fee"],add_cost=cost,add_net=net,add_return=net/cost,add_exit=ex["day"] if ex else None,add_closed=ex is not None,**a)
  parts.append(row)
df=pd.DataFrame(parts)
rows=[]
cache={}
for no,(sid,g) in enumerate(df.groupby("sid")):
 m=manifest[sid];sp=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 sig=pd.read_parquet(sp);pvr=original_pvr(sig);valid,block=original_observation_clock(sig)
 cp=pd.read_parquet(m["refs"]["CP1"]);fa=pd.read_parquet(m["refs"]["facts"])
 roots=fa.i_target.eq(1)&fa.i_target.shift(fill_value=0).ne(1)
 rootday=pd.Series(pd.NaT,index=fa.index);rootday.loc[roots]=fa.index[roots];rootday=rootday.ffill()
 dp=R/"dual_frontier_cp_full_v1/states"/(sid+".parquet")
 dual=pd.read_parquet(dp).assign(day=lambda x:pd.to_datetime(x.day)).set_index("day") if dp.exists() else None
 feat=pvr.rename(columns={"score":"pvr"}).copy()
 feat["pvr_prev1"]=feat.pvr.shift();feat["amount_multiple"]=sig.amount/feat.amount_ref
 for _,ss in sig[valid].groupby(block[valid],sort=False):
  ix=ss.index;feat.loc[ix,"return5"]=ss.close/ss.close.shift(5)-1
  feat.loc[ix,"return20"]=ss.close/ss.close.shift(20)-1
  feat.loc[ix,"breakout20"]=ss.close/ss.close.shift().rolling(20,min_periods=20).max()-1
  feat.loc[ix,"close_location"]=(ss.close-ss.low)/(ss.high-ss.low).replace(0,np.nan)
 for r in g.to_dict("records"):
  d=pd.Timestamp(r["signal_day"]);s=feat.loc[d];c=cp.loc[d]
  prior=cp.loc[cp.index<d];prior=prior[prior.receipt.astype(bool)]
  pd0=prior.index[-1] if len(prior) else None
  prevp=feat.loc[pd0,"pvr"] if pd0 in feat.index and block.loc[pd0]==block.loc[d] else np.nan
  sg=sectors[r["sector"]].loc[d]
  row=dict(r,**s.to_dict(),I_root_asof=str(rootday.loc[d].date()) if pd.notna(rootday.loc[d]) else None,prev_cp_same_I=bool(pd0 is not None and pd.notna(rootday.loc[d]) and pd0>=rootday.loc[d]),pvr_change1=s.pvr-s.pvr_prev1,prev_cp_day=str(pd0.date()) if pd0 is not None else None,pvr_prev_cp=prevp,cp_credit=c.credit,cp_scale=c.scale,cp_delta_frontier=c.delta_frontier,cp_displacement=c.displacement,breadth=sg.M3_right_known,breadth_change1=sg.breadth_change1,breadth_change3=sg.M3_delta3,breadth_fraction_change3=sg.breadth_change3,common3_K=sg.common3_K,breadth_run=sg.breadth_run,sector_stage=sg.sector_stage,
   pvr_change_cp=s.pvr-prevp,cp_distance=1-r["new_add_floor"]/sig.loc[d,"raw_close"],core_distance=1-r["core_floor"]/sig.loc[d,"raw_close"],signal_return=s.r,
   u_fraction=r["round_net_before"]/r["core_cost"],risk_per_cash=r["add_risk"]/r["add_cost"],cp_advance_scale=c.delta_frontier/c.scale if c.scale>0 else np.nan,
   previous_cp_protection=prior.candidate.iloc[-1]/sig.loc[d,"adjustment_factor"] if len(prior) else np.nan)
  if dual is not None and d in dual.index:
   ds=dual.loc[d];row.update(dual_receipt=bool(ds.new_receipt),dual_ready=bool(ds.new_ready),qok=bool(ds.qok),q_raw=ds.q_raw,q_vs_close=ds.q_raw/sig.loc[d,"raw_close"]-1,mean_frontier=ds.new_mean_frontier,old_receipt=bool(ds.old_receipt))
  rows.append(row)
 if (no+1)%100==0:print("loaded",no+1,flush=True)
out=pd.DataFrame(rows)
out["pvr_progress"]=out.pvr_change_cp.ge(0).astype("boolean").mask(out.pvr_change_cp.isna())
out["breadth_progress"]=out.breadth_change3.ge(0).astype("boolean").mask(out.breadth_change3.isna())
out["risk_distance_sigma"]=out.cp_distance/out.scale
out["joint_progress"]=out.pvr_progress&out.breadth_progress
out["cp_distance_wide"]=out.risk_distance_sigma.gt(np.sqrt(5))
out["price_breakout"]=out.breakout20.ge(0)
out["high_close"]=out.close_location.ge(.5).astype("boolean").mask(out.close_location.isna())
out["amount_above_ref"]=out.amount_multiple.ge(1)
def metrics(g):
 c=g[g.add_closed]
 w=c[c.add_net>0];l=c[c.add_net<0]
 return dict(n=len(g),closed=len(c),stocks=g.sid.nunique(),dates=g.signal_day.nunique(),win=c.add_net.gt(0).mean(),payoff=w.add_net.mean()/(-l.add_net.mean()) if len(w) and len(l) else None,mean_net=c.add_net.mean(),sum_net=c.add_net.sum(),mean_return=c.add_return.mean(),top10_net=c.add_net.nlargest(max(1,int(np.ceil(len(c)*.1)))).sum(),mean_u=g.u_fraction.mean(),mean_pvr=g.pvr.mean(),mean_risk=g.cp_distance.mean())
dest=P/"add_signal_quality_diagnostic_v1"
dest.mkdir(exist_ok=True)
out.to_csv(dest/"ALL_ACTUAL_ADD_FEATURES.csv",index=False)
print("COVERAGE",out.groupby(["policy","window"]).size().to_dict())
for pol in ["original","dual"]:
 a=out[out.policy.eq(pol)]
 for yr,g in a.groupby("window"):
  print("ALL",pol,yr,metrics(g))
  for f in ["pvr_progress","breadth_progress","joint_progress","dual_receipt","cp_distance_wide","price_breakout","high_close","amount_above_ref"]:
   for v,gg in g.groupby(f):print("GROUP",pol,yr,f,v,metrics(gg))
print("MISSING",out.isna().sum().loc[lambda s:s>0].to_dict())

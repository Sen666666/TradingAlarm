import pandas as pd,numpy as np,json,ast,sys,hashlib,time
from pathlib import Path
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
sys.path.insert(0,"/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
from features import original_pvr,original_observation_clock
for path,names in [(R/"cmf_pvr_component_v1/experiment.py",["calc"]),(R/"pvr_dmi_cmf_round_interaction_v1/preflight.py",["dcalc"])]:
 tree=ast.parse(path.read_text());exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(path),"exec"))
fullcal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);fullcal=fullcal[(fullcal>="2013-01-01")&(fullcal<="2026-05-15")]
mp={m["symbol"]:m for m in json.loads(M.read_text())}
parts=[]
for w in ("2022","2024"):
 E=R/f"independent_channel_joint_economic_v1/economic_{w}"
 r=pd.read_csv(E/"joint/ROUNDS.csv");r=r[r.owner_lane.eq("PRICE")].copy();r["window_label"]=w
 rep=json.loads((E/"COMPARISON_REPORT_RECOVERED.json").read_text())
 cov=pd.DataFrame(rep["round_coverage"]);cov=cov[cov.arm.eq("joint")][["round_id","financial_covered","reason"]].rename(columns={"reason":"financial_reason"})
 r=r.merge(cov,on="round_id",how="left",validate="one_to_one")
 cl=json.loads((E/"joint/CLAIMS.json").read_text());print("CLAIM_TYPE",w,type(cl).__name__,flush=True)
 r["has_claim"]=r.round_id.isin([x.get("owner_round_id") for x in cl] if isinstance(cl,list) else [])
 r["signal_day"]=pd.to_datetime(r.signal_day);r["exit_day"]=pd.to_datetime(r.exit_day)
 parts.append(r)
r=pd.concat(parts,ignore_index=True);out=[];start=time.time()
print("FEATURE_SUPPORT_ONLY",len(r),r.sid.nunique(),"stocks",flush=True)
for no,(sid,g) in enumerate(r.groupby("sid",sort=True)):
 m=mp[sid];pfile=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));actual=hashlib.sha256(Path(pfile).read_bytes()).hexdigest();assert actual==m["source_sha256"][pfile]
 p=pd.read_parquet(pfile).loc[:g.signal_day.max()]
 z=calc(p);d,age=dcalc(p)
 for idx,row in g.iterrows():
  day=row.signal_day
  pp=z.loc[day,"score"] if day in z.index else np.nan
  C=z.loc[day,"CMF21"] if day in z.index else np.nan
  D=d.loc[day] if day in d.index else np.nan
  err=abs(pp-row.PVR_score)
  out.append(dict(idx=idx,P=row.PVR_score,D=D,C=C,feature_known=bool(np.isfinite(row.PVR_score) and np.isfinite(D) and np.isfinite(C) and err<1e-8),pvr_error=err))
 if (no+1)%250==0:print("PROGRESS",no+1,round(time.time()-start,1),flush=True)
f=pd.DataFrame(out).set_index("idx").sort_index();r=r.join(f.drop(columns="P"));r["complete"]=r.status.eq("COMPLETE_CONDITIONAL_STOCK_ROUND")
r["ordinary"]=r.complete&r.financial_covered.eq(True)&r.financial_reason.eq("LOCAL_NO_ACTION_EVIDENCE")&~r.has_claim&r.dividend_net80_total.fillna(0).eq(0)&r.receivable_after_payouts.fillna(0).eq(0)
for w,g in r.groupby("window_label"):
 print("SUMMARY",w,json.dumps(dict(registered=len(g),entered=int(g.entry_day.notna().sum()),completed=int(g.complete.sum()),ordinary=int(g.ordinary.sum()),features_known=int(g.feature_known.sum()),ordinary_features=int((g.ordinary&g.feature_known).sum()),ordinary_feature_wins=int((g.ordinary&g.feature_known&g.net_pnl.gt(0)).sum()),features_unknown_on_entered=int((g.entry_day.notna()&~g.feature_known).sum()),max_pvr_error=float(g.pvr_error.max())),ensure_ascii=False),flush=True)
 print("ORDINARY_MONTHS",g[g.ordinary&g.feature_known].groupby(g.signal_day.dt.to_period("M")).agg(n=("sid","size"),wins=("net_pnl",lambda x:int(x.gt(0).sum())),stocks=("sid","nunique")).to_string(),flush=True)
r["t"]=fullcal.get_indexer(r.signal_day)
cuts=[str(fullcal[(fullcal.year==y)&(fullcal.month==mo)][0].date()) for y,months in [(2022,range(7,13)),(2024,range(9,13))] for mo in months]
for day in cuts:
 c=fullcal.get_loc(day);tr=r[r.ordinary&r.feature_known&r.exit_day.lt(day)&r.t.ge(c-504)&r.t.lt(c)]
 print("CUT",day,json.dumps(dict(n=len(tr),wins=int(tr.net_pnl.gt(0).sum()),losses=int(tr.net_pnl.le(0).sum()),dates=int(tr.signal_day.nunique()),stocks=int(tr.sid.nunique()),min_signal=str(tr.signal_day.min()),max_signal=str(tr.signal_day.max()),train_windows=tr.window_label.value_counts().to_dict()),ensure_ascii=False),flush=True)
print("ELAPSED",time.time()-start,flush=True)

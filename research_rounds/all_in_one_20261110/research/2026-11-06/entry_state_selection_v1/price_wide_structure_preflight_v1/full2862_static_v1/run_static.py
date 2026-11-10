from pathlib import Path
import ast,hashlib,json,math,time,sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent; BASE=O.parent;R=BASE.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
A=R/"price_round_path_attribution_v1/PRICE_ROUND_PATH_ATTRIBUTION.csv"
Q=R/"price_dmi_priority_preflight_v1/SEALED_RANKS.parquet"
K=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/strict-entry-capacity-20261027/code/entry_kernel.py")
AR=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/arithmetic.py")
IMPL=BASE/"run_preflight.py"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,(pd.Timestamp,)):return v.isoformat()
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+"\n")
env={"np":np,"pd":pd,"math":math}
exec(compile(AR.read_text(),str(AR),"exec"),env)
env["EVENT_COLUMNS"]=["confirmation","leg_direction","developing_extreme","confirmed_pivot","event","pivot_age","developing_extreme_price","confirmed_pivot_price","confirmed_pivot_date","developing_extreme_date"]
env["EVENT_DATE_COLUMNS"]=["confirmed_pivot_date","developing_extreme_date"]
exec(compile(K.read_text(),str(K),"exec"),env)
event=env["entry_events"];compare=env["compare"]
tree=ast.parse(IMPL.read_text()); node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="calc")
exec(compile(ast.Module(body=[node],type_ignores=[]),str(IMPL),"exec"),globals())
def work(task):
 sid,rec,ds,k,prefix=task;p=next(p for p in rec["source_sha256"] if p.endswith("/signal.parquet"));h=sha(p)
 assert h==rec["source_sha256"][p],("SOURCE_HASH_MISMATCH",sid)
 f=pd.read_parquet(p).loc[:max(ds)].copy();z=calc(f,k);hs={p:h}
 if k==1:
  fp=Path(rec["refs"]["facts"]);hs[str(fp)]=sha(fp);ff=pd.read_parquet(fp);idx=z.index.intersection(ff.index)
  ii=idx[ff.loc[idx,"e0_ready"].eq(1)&z.loc[idx,"ready"]]
  tm=int((z.loc[ii,"target"].astype(bool)!=ff.loc[ii,"e0_target"].astype(bool)).sum())
  ai=ii[z.loc[ii,"target"].astype(bool)&ff.loc[ii,"e0_target"].astype(bool)]
  fa=float(np.nanmax(abs(z.loc[ai,"floor"].to_numpy()-ff.loc[ai,"e0_floor"].to_numpy()))) if len(ai) else 0.
  return dict(sid=sid,source_rows=len(f),checked=len(ii),target_mismatch=tm,active_floor_max_error=fa,hashes=hs)
 rows=[]
 for d in ds:
  known=d in z.index and bool(z.loc[d,"ready"])
  v=dict(sid=sid,signal_day=d,known=known,gate_result="FALLBACK",wide_target=None,wide_floor=None,wide_floor_raw=None,wide_birth=None,wide_floor_known_at=None,wide_event=None,wide_confirmation=None,pivot_day=None)
  if d in z.index:
   t=z.loc[d];r=f.loc[d]
   if known:
    assert np.isclose(r.close,r.raw_close*r.adjustment_factor,rtol=1e-12,atol=1e-8),("RAW_MAPPING",sid,d)
    v.update(gate_result="PASS" if t.target else "REJECT_CURRENT_RECEIPT",wide_target=bool(t.target),wide_floor=float(t.floor),wide_floor_raw=float(t.floor/r.adjustment_factor),wide_birth=t.birth,wide_floor_known_at=t.floor_known_at,wide_event=t.event,wide_confirmation=t.confirmation,pivot_day=t.pivot_day)
  rows.append(v)
 qa=[]
 for d in prefix:
  zz=calc(f.loc[:d],1.5);pd.testing.assert_frame_equal(z.loc[:d],zz,check_exact=True);qa.append(dict(sid=sid,signal_day=d,exact=True,rows=len(zz)))
 return dict(rows=rows,prefix=qa,hashes=hs)
def stats(g):
 p=g[g.net_pnl>0];n=g[g.net_pnl<0]
 return dict(n=len(g),W=len(p),L=len(n),flat=int(g.net_pnl.eq(0).sum()),winrate=100*len(p)/len(g) if len(g) else None,net=float(g.net_pnl.sum()),positive=float(p.net_pnl.sum()),negative_abs=float(-n.net_pnl.sum()),mean_net=float(g.net_pnl.mean()),mean_positive=float(p.net_pnl.mean()),mean_negative=float(n.net_pnl.mean()),payoff=float(p.net_pnl.mean()/-n.net_pnl.mean()) if len(p) and len(n) else None,median_net_return=float(g.net_return_on_buy_cash.median()),tail30=int(g.net_return_on_buy_cash.ge(.30).sum()),tail30_net=float(g.loc[g.net_return_on_buy_cash.ge(.30),"net_pnl"].sum()),tail50=int(g.net_return_on_buy_cash.ge(.50).sum()),tail50_net=float(g.loc[g.net_return_on_buy_cash.ge(.50),"net_pnl"].sum()))
def main():
 assert not (O/"FEATURES_PRELABEL.parquet").exists(),"No rerun/overwrite"
 start=time.perf_counter();meta=pd.read_csv(A,usecols=["round_id","window","sid","signal_day"],parse_dates=["signal_day"])
 assert len(meta)==2862 and meta.round_id.is_unique and not meta.duplicated(["sid","signal_day"]).any()
 mp={r["symbol"]:r for r in json.loads(M.read_text())};hashes={str(p):sha(p) for p in [A,Q,M,K,AR,IMPL,BASE/"PROTOCOL.json",O/"PROTOCOL.json",Path(__file__)]}
 pref={}
 for win,g in meta.groupby("window"):
  h=g.sort_values(["signal_day","sid"])
  for _,r in pd.concat([h.head(1),h.tail(1)]).iterrows():pref.setdefault(r.sid,[]).append(r.signal_day)
 tasks=[(sid,mp[sid],list(g.signal_day),1,pref.get(sid,[])) for sid,g in meta.groupby("sid")]
 dump("RUN_STARTED.json",dict(cohort=len(meta),stocks=len(tasks),workers=3,formula_multiplier=1.5,started_utc=pd.Timestamp.now(tz="UTC").isoformat()))
 reg=[]
 with ProcessPoolExecutor(max_workers=3) as pool:
  for n,res in enumerate(pool.map(work,tasks),1):
   hashes.update(res.pop("hashes"));reg.append(res)
   if n%200==0:print("regression",n,len(tasks),round(time.perf_counter()-start,2),flush=True)
 pd.DataFrame(reg).to_csv(O/"MULTIPLIER1_REGRESSION.csv",index=False)
 assert all(r["target_mismatch"]==0 and r["active_floor_max_error"]<1e-8 for r in reg),"Full scope regression mismatch; no wide calculation"
 print("regression_pass",sum(r["checked"] for r in reg),round(time.perf_counter()-start,2),flush=True)
 rows=[];prefix=[]
 with ProcessPoolExecutor(max_workers=3) as pool:
  for n,res in enumerate(pool.map(work,[(s,r,d,1.5,p) for s,r,d,k,p in tasks]),1):
   for p,h in res["hashes"].items():assert hashes[p]==h
   rows.extend(res["rows"]);prefix.extend(res["prefix"])
   if n%200==0:print("wide",n,len(tasks),round(time.perf_counter()-start,2),flush=True)
 f=pd.DataFrame(rows);f=meta.merge(f,on=["sid","signal_day"],validate="one_to_one");assert len(f)==2862
 f.to_parquet(O/"FEATURES_PRELABEL.parquet",index=False);dump("PREFIX_QA.json",prefix);dump("FEATURE_SEAL.json",{"FEATURES_PRELABEL.parquet":sha(O/"FEATURES_PRELABEL.parquet")})
 # Only now attach outcome data, unchanged original closed rounds.
 a=pd.read_csv(A,parse_dates=["signal_day"],float_precision="round_trip");assert a.owner_lane.eq("PRICE").all() and a.status.eq("COMPLETE_CONDITIONAL_STOCK_ROUND").all()
 a=a.merge(f.drop(columns=["sid","signal_day","window"]),on="round_id",validate="one_to_one");assert len(a)==2862
 qp=pd.read_parquet(Q);qp=qp[qp.owner_lane.eq("PRICE")].copy();qp["day"]=pd.to_datetime(qp.day)
 cs=qp.groupby(["window","day","sector"]).agg(price_N=("sid","size"),price_K=("selected","sum")).reset_index()
 qp=qp.merge(cs,on=["window","day","sector"],validate="many_to_one")
 ctx=qp[["window","day","sid","selected","price_N","price_K"]].rename(columns={"day":"signal_day","selected":"queue_selected"})
 assert not ctx.duplicated(["window","signal_day","sid"]).any()
 a=a.merge(ctx,on=["window","signal_day","sid"],how="left",validate="one_to_one")
 a["competition_context_known"]=a.price_N.notna();a["no_price_competition"]=a.competition_context_known&a.price_N.le(a.price_K)
 a["static_admitted"]=a.gate_result.ne("REJECT_CURRENT_RECEIPT")
 a.to_csv(O/"ROUND_GROUPS.csv",index=False)
 summary=[]
 for win,g in a.groupby("window"):
  groups=[("ORIGINAL",g),("KNOWN_PASS",g[g.gate_result.eq("PASS")]),("REJECT",g[g.gate_result.eq("REJECT_CURRENT_RECEIPT")]),("UNKNOWN_FALLBACK",g[g.gate_result.eq("FALLBACK")]),("STATIC_ADMITTED_WITH_FALLBACK",g[g.static_admitted])]
  for label,q in groups:summary.append(dict(window=win,group=label,**stats(q)))
  for label,q in [("NO_PRICE_COMPETITION_ORIGINAL",g[g.no_price_competition]),("NO_PRICE_COMPETITION_REJECT",g[g.no_price_competition&~g.static_admitted])]:summary.append(dict(window=win,group=label,**stats(q)))
 pd.DataFrame(summary).to_csv(O/"STATIC_GROUP_SUMMARY.csv",index=False)
 ex=[]
 for win,g in a.groupby("window"):
  reject=g[~g.static_admitted]
  for label,q in [("FIRST3_REJECTED_WINNERS",reject[reject.net_pnl>0].sort_values(["signal_day","sid"]).head(3)),("FIRST3_REJECTED_LOSERS",reject[reject.net_pnl<0].sort_values(["signal_day","sid"]).head(3)),("TOP3_REJECTED_FINAL_TAILS",reject[reject.net_return_on_buy_cash>=.30].sort_values(["net_pnl","sid"],ascending=[False,True]).head(3))]:
   q=q.copy();q["example_rule"]=label;ex.append(q)
 pd.concat(ex).to_csv(O/"FIXED_RULE_EXAMPLES.csv",index=False)
 b=pd.read_csv(BASE/"CASE_STATES_PRELABEL.csv",parse_dates=["day"]);z=b.merge(a[["sid","signal_day","gate_result"]],left_on=["sid","day"],right_on=["sid","signal_day"],suffixes=("_case","_full"));assert z.gate_result_case.eq(z.gate_result_full).all()
 qa=dict(n=2862,stocks=1294,regression_known_intersection=sum(r["checked"] for r in reg),regression_target_mismatches=sum(r["target_mismatch"] for r in reg),max_active_floor_error=max(r["active_floor_max_error"] for r in reg),prefix_points=len(prefix),fixed_case_overlap=len(z),fixed_overlap_exact=True,queue_join_known=int(a.competition_context_known.sum()),queue_selected_true=int(a.queue_selected.eq(True).sum()),unknown=int(a.gate_result.eq("FALLBACK").sum()),elapsed_seconds=time.perf_counter()-start,new_account_runs=0,new_lifecycle_runs=0,thresholds_changed=0)
 assert all(sha(p)==h for p,h in hashes.items()),"Source changed"
 dump("SOURCE_HASHES.json",hashes);dump("FINAL_QA.json",qa);dump("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
 print(json.dumps(clean(qa),ensure_ascii=False),flush=True);print(pd.DataFrame(summary).to_string(index=False),flush=True)
if __name__=="__main__":main()

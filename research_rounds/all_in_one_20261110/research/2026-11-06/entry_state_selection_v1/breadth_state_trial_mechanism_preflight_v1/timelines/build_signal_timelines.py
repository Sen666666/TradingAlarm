
from pathlib import Path
import pandas as pd, numpy as np, json, hashlib
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=R/"breadth_state_trial_mechanism_preflight_v1/timelines"
M=R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2"; P=R/"pvr_persistence_breadth_v1"
src=[M/x for x in ["KNOWN3.parquet","RIGHT3.parquet","MU5.parquet","SECTOR_DAILY.parquet","WARM_PREFIX_M_K.parquet","WARM_PREFIX_M_R.parquet","WARM_PREFIX_P_STATE.parquet"]]+[P/"STOCK_DAILY.parquet",P/"INDUSTRY_DAILY_V2.parquet",R/"momentum_persistence_breadth_v1/FIXED_ROSTER.csv",P/"FIXED_MEMBERSHIP.csv"]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):sha(p) for p in src}
roster=pd.read_csv(src[-2]); ids=sorted(roster.symbol); assert len(ids)==1709 and roster.sector_id.nunique()==90
pm=pd.read_csv(P/"FIXED_MEMBERSHIP.csv")
assert roster.set_index("symbol").sector_id.sort_index().equals(pm.set_index("sid").sector_id.sort_index())
k=pd.concat([pd.read_parquet(M/"WARM_PREFIX_M_K.parquet"),pd.read_parquet(M/"KNOWN3.parquet")])[ids].fillna(False).astype(bool)
r=pd.concat([pd.read_parquet(M/"WARM_PREFIX_M_R.parquet"),pd.read_parquet(M/"RIGHT3.parquet")])[ids].fillna(False).astype(bool)
pstock=pd.read_parquet(P/"STOCK_DAILY.parquet")
ps=pd.concat([pd.read_parquet(M/"WARM_PREFIX_P_STATE.parquet"),pstock.pivot(index="day",columns="sid",values="state")])[ids].reindex(k.index)
assert ps.notna().all().all() and k.index.is_unique and r.index.equals(k.index)
assert not (r&~k).any().any()
pk,pr=ps.ge(0),ps.eq(1)
sector_sources={"M3":pd.read_parquet(M/"SECTOR_DAILY.parquet"),"PVR3":pd.read_parquet(P/"INDUSTRY_DAILY_V2.parquet")}
named=["通信设备","风电设备","半导体","证券","软件开发"]
sel=roster[roster.sector_name.isin(named)].groupby(["sector_id","sector_name"]).size().rename("N").reset_index()
assert len(sel)==5
windows=[("2022_JAN","2022-01-04","2022-01-21"),("2022_APRMAY","2022-04-25","2022-05-13"),("2022_OCTNOV","2022-10-10","2022-11-11"),("2024_SEPOCT","2024-09-09","2024-10-08"),("2024_NOV","2024-11-01","2024-11-15")]
fullmask=((k.index>="2022-01-04")&(k.index<="2022-12-30"))|((k.index>="2024-09-01")&(k.index<="2024-12-31"))
keepdates=k.index[fullmask]
def direction(lo,hi):
 return np.select([lo>0,hi<0,(lo==0)&(hi==0)],["POSITIVE","NEGATIVE","FLAT"],default="UNKNOWN")
def aggregate(model,sec,name,cols,kk,rr):
 kk,rr=kk[cols],rr[cols]; N=len(cols)
 z=pd.DataFrame(index=kk.index);z.index.name="day"
 z["model"]=model;z["sector"]=sec;z["sector_name"]=name;z["N"]=N;z["K"]=kk.sum(axis=1);z["n"]=rr.sum(axis=1);z["U"]=N-z.K
 z["known_share"]=z.n/z.K.replace(0,np.nan);z["fixedN_lower"]=z.n/N;z["fixedN_upper"]=(z.n+z.U)/N;z["known_coverage"]=z.K/N
 for lag in [1,3]:
  prev=rr.shift(lag,fill_value=False);pair=kk&kk.shift(lag,fill_value=False); J=pair.sum(axis=1)
  en=(pair&rr&~prev).sum(axis=1); ex=(pair&~rr&prev).sum(axis=1)
  z[f"J{lag}"]=J;z[f"entered{lag}"]=en;z[f"left{lag}"]=ex;z[f"paired_D{lag}"]=en-ex;z[f"paired_delta{lag}"]=(en-ex)/J.replace(0,np.nan)
  z[f"paired_direction{lag}"]=np.where(J>0,direction(en-ex,en-ex),"UNKNOWN")
  z[f"paired_coverage{lag}"]=J/N;z[f"prior_day{lag}"]=pd.Series(z.index,index=z.index).shift(lag)
  lo=z.n-(z.n+z.U).shift(lag);hi=z.n+z.U-z.n.shift(lag)
  z[f"whole_D{lag}_lower"]=lo;z[f"whole_D{lag}_upper"]=hi;z[f"whole_delta{lag}_lower"]=lo/N;z[f"whole_delta{lag}_upper"]=hi/N;z[f"whole_direction{lag}"]=direction(lo,hi)
  z[f"coverage_only_current{lag}"]=(kk&~kk.shift(lag,fill_value=False)).sum(axis=1)
  z[f"coverage_only_prior{lag}"]=(~kk&kk.shift(lag,fill_value=False)).sum(axis=1)
 z["NON_PIT"]=True
 return z.reset_index()
parts=[];markets=[]
for model,kk,rr in [("M3",k,r),("PVR3",pk,pr)]:
 for sec,g in roster.groupby("sector_id"):
  parts.append(aggregate(model,sec,g.sector_name.iloc[0],g.symbol.tolist(),kk,rr))
 markets.append(aggregate(model,"ALL1709","固定全池1709",ids,kk,rr))
daily=pd.concat(parts,ignore_index=True);market=pd.concat(markets,ignore_index=True)
qa={}
for model,orig in sector_sources.items():
 q=daily[daily.model.eq(model)].merge(orig,on=["day","sector"],suffixes=("_new","_source"))
 fields={"N":"N","K":"K","n":"n","U":"U" if model=="M3" else "unknown","J3":"common3_K" if model=="M3" else "paired_K","paired_D3":None}
 for ours,theirs in fields.items():
  a=q[ours+"_new"] if ours in orig else q[ours]
  b=q[theirs+"_source"] if theirs in ["N","K","n","U"] and theirs in daily else q[theirs] if theirs else (q.entered3_source-q.left3_source if model=="M3" else q.paired_delta_n)
  assert np.array_equal(a.to_numpy(),b.to_numpy()),(model,ours)
 qa[model]={"matched_original_rows":len(q),"N_K_n_U_J3_D3_exact":True}
assert daily.groupby(["model","day"]).n.sum().sort_index().equals(market.set_index(["model","day"]).n.sort_index())
groups=[]
for (model,day),q in daily[daily.day.isin(keepdates)].groupby(["model","day"]):
 z={"model":model,"day":day,"industries":len(q),"industries_any_unknown":int(q.U.gt(0).sum()),"stocks_unknown":int(q.U.sum())}
 for lag in [1,3]:
  for scope in ["whole","paired"]:
   for d in ["POSITIVE","NEGATIVE","FLAT","UNKNOWN"]:
    z[f"{scope}{lag}_{d}"]=int(q[f"{scope}_direction{lag}"].eq(d).sum())
  z[f"paired{lag}_netzero_with_turnover"]=int((q[f"paired_D{lag}"].eq(0)&q[f"entered{lag}"].gt(0)).sum())
 for c in ["n","known_share","fixedN_lower","fixedN_upper","known_coverage"]:
  for t in [0,.25,.5,.75,1]: z[c+"_q"+str(int(100*t))]=q[c].quantile(t)
 groups.append(z)
distribution=pd.DataFrame(groups)
full=daily[daily.day.isin(keepdates)].copy()
mfull=market[market.day.isin(keepdates)].merge(distribution,on=["model","day"])
fparts=[];mparts=[]
for label,a,b in windows:
 fparts.append(daily[daily.sector_name.isin(named)&daily.day.between(a,b)].assign(window=label))
 mparts.append(market[market.day.between(a,b)].assign(window=label).merge(distribution,on=["model","day"]))
fixed=pd.concat(fparts);mfixed=pd.concat(mparts)
semi=daily[daily.sector_name.eq("半导体")&daily.day.between("2026-04-08","2026-04-21")].copy()
# Existing native facts only. No new qualification or trading rule is calculated.
meta=sector_sources["M3"][["day","sector","sector_E0_valid","sector_stage","sector_action","sector_receipt","candidate"]].rename(columns={"candidate":"existing_M3_candidate"})
semi=semi.merge(meta,on=["day","sector"])
sid="300666.SZ"; assert sid in ids
dates=pd.to_datetime(["2025-12-15","2025-12-17","2026-01-05","2026-01-15"])
mu=pd.read_parquet(M/"MU5.parquet"); stocks=[]
for day in dates:
 z={"day":day,"symbol":sid,"name":"江丰电子","NON_PIT":True,"signal_only":True,"M3_known":bool(k.at[day,sid]),"M3_right":bool(r.at[day,sid]) if k.at[day,sid] else None,"mu5":mu.at[day,sid],"PVR3_state":int(ps.at[day,sid])}
 pp=pstock[pstock.sid.eq(sid)&pstock.day.eq(day)].iloc[0];z["PVR_score"]=pp.score;z["PVR_reason"]=pp.reason
 z["prior_common_days"]="|".join(str(t.date()) for t in k.index[max(0,k.index.get_loc(day)-2):k.index.get_loc(day)+1])
 stocks.append(z)
stockfacts=pd.DataFrame(stocks)
signalcontext=daily[daily.sector_name.eq("半导体")&daily.day.isin(dates)].copy()
O.mkdir(parents=True,exist_ok=True)
files={"ALL90_DAILY_2022_2024_SEP_DEC.csv":full,"MARKET_DAILY_2022_2024_SEP_DEC.csv":mfull,"FIXED5_WINDOWS_DAILY.csv":fixed,"FIXED_WINDOWS_MARKET_DAILY.csv":mfixed,"INDUSTRY_DIFFUSION_DISTRIBUTION_DAILY.csv":distribution,"SEMICONDUCTOR_APR2026_SIGNAL_ONLY.csv":semi,"JIANGFENG_FIXED_SIGNAL_ONLY.csv":stockfacts,"JIANGFENG_SECTOR_CONTEXT_SIGNAL_ONLY.csv":signalcontext,"FIXED5_IDENTITY.csv":sel}
for filename,d in files.items():d.to_csv(O/filename,index=False)
assert before=={str(p):sha(p) for p in src}
qa.update({"source_unchanged":True,"NON_PIT":True,"N":1709,"sectors":90,"prefix_dates":[str(x.date()) for x in k.index[:3]],"dates_2022":int(sum(keepdates.year==2022)),"dates_2024_sep_dec":int(sum(keepdates.year==2024)),"no_account_runs":True,"no_price_return_labels":True,"no_new_candidate_rules":True,"rows":{f:len(d) for f,d in files.items()}})
(O/"SOURCE_SHA256.json").write_text(json.dumps(before,indent=2))
(O/"QA.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2))
(O/"OUTPUT_SHA256.json").write_text(json.dumps({f:sha(O/f) for f in files},indent=2))
print("QA",json.dumps(qa,ensure_ascii=False))
print("IDENTITY",sel.to_csv(index=False))
cols=["day","model","n","K","U","whole_D1_lower","whole_D1_upper","whole_direction1","paired_D1","J1","entered1","left1","whole_D3_lower","whole_D3_upper","whole_direction3","paired_D3","whole1_POSITIVE","paired1_POSITIVE"]
print("2024_FIXED_MARKET");print(mfixed[mfixed.window.eq("2024_SEPOCT")][cols].to_csv(index=False))
print("SEMI_APR");print(semi[["day","model","n","K","N","U","whole_D1_lower","whole_D1_upper","whole_direction1","paired_D1","J1","entered1","left1","whole_D3_lower","whole_D3_upper","whole_direction3","paired_D3","J3","entered3","left3","sector_action"]].to_csv(index=False))
print("JIANGFENG");print(stockfacts.to_csv(index=False))

import warnings;warnings.filterwarnings('ignore')

import ast, json, hashlib, math
from pathlib import Path
import numpy as np, pandas as pd
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
mp={x["symbol"]:x for x in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
N=14
tree=ast.parse((R/"dmi_boundary_migration_v1/experiment.py").read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ("calc","rma")],type_ignores=[]),"OLD_DMI_functions_only","exec"))
def get(sid):
 m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==m["source_sha256"][path]
 p=pd.read_parquet(path).reindex(cal)
 f=pd.read_parquet(m["refs"]["facts"]).reindex(cal)
 assert (p.close-f.close).abs().max()<1e-7
 z=calc(p,cal);z["delta_adx"]=z.adx.diff();z["dx_minus_prior_adx"]=z.dx-z.adx.shift()
 z["cross_pos"]=z.d.gt(0)&z.d.shift().le(0)
 z["cross_neg"]=z.d.le(0)&z.d.shift().gt(0)
 z["turn_up"]=z.delta_adx.gt(0)&z.delta_adx.shift().le(0)
 z["turn_down"]=z.delta_adx.le(0)&z.delta_adx.shift().gt(0)
 z["positive_drive"]=z.d.gt(0)&z.delta_adx.gt(0)&z.raw_plus_dm.gt(0)
 z["U20"]=p.high.shift().rolling(20,min_periods=20).max()
 z["break20"]=p.close.gt(z.U20)
 z=z.join(p[["open","high","low","close","raw_open","raw_high","raw_low","raw_close","adjustment_factor"]])
 z=z.join(f[["e0_target","e0_floor","i_target","i_buy","g_grade"]])
 return z,p,f

def scalar(p):
 q=p.reindex(cal);cols=["open","high","low","close"]
 ok=np.isfinite(q[cols]).all(axis=1)&q[cols].gt(0).all(axis=1)&q.high.ge(q[cols].max(axis=1))&q.low.le(q[cols].min(axis=1))&q.segment_id.notna()
 for c in ["price_eligible","observed_bar","is_observed_bar"]:ok &= q[c].fillna(False).astype(bool)
 for c in ["source_invalid","synthetic_event_bar"]:ok &= ~q[c].fillna(True).astype(bool)
 out=pd.DataFrame(np.nan,index=q.index,columns=["d","plus_di","minus_di","dx","adx"])
 prev=None;buf=[];dxb=[];u=v=tr=ad=np.nan;sid=None;source=None
 for i,(dt,r) in enumerate(q.iterrows()):
  ident=(r.source_kind,r.source_path,r.segment_id)
  if not ok.iloc[i] or prev is None or r.segment_id!=sid:
   prev=None;buf=[];dxb=[];u=v=tr=ad=np.nan;source=None
  if not ok.iloc[i]:continue
  if prev is not None:
   assert ident==source,(dt,ident,source)
   up=r.high-prev.high;down=prev.low-r.low
   pu=up if up>down and up>0 else 0.
   pv=down if down>up and down>0 else 0.
   rt=max(r.high-r.low,abs(r.high-prev.close),abs(r.low-prev.close))
   if len(buf)<14:
    buf.append((pu,pv,rt))
    if len(buf)==14:u,v,tr=np.mean(buf,axis=0)
   else:u=(13*u+pu)/14;v=(13*v+pv)/14;tr=(13*tr+rt)/14
   if np.isfinite(u+v):
    d=(u-v)/(u+v) if u+v>0 else 0.;dx=100*abs(d)
    if len(dxb)<14:
     dxb.append(dx)
     if len(dxb)==14:ad=sum(dxb)/14
    else:ad=(13*ad+dx)/14
    out.loc[dt]=[d,100*u/tr if tr>0 else 0,100*v/tr if tr>0 else 0,dx,ad]
  prev=r;sid=r.segment_id;source=ident
 return out

O=R/"price_dmi_priority_preflight_v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(name,obj):
 with (O/name).open("x") as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))
def cs(name,x):x.to_csv(O/name,index=False,mode="x")
seal=json.loads((O/"FEATURE_PICK_SEAL.json").read_text())
assert all(sha(O/p)==h for p,h in seal.items())
q=pd.read_parquet(O/"SEALED_RANKS.parquet")
# Independent record-list slot mapping, not the vectorized rank writer.
for _,g in q.groupby(["window","day","sector"],sort=False):
 records=g.sort_values("joint_feasible_rank").to_dict("records")
 original={int(r["joint_feasible_rank"]):r["sid"] for r in records}
 slots=[int(r["joint_feasible_rank"]) for r in records if r["mutable"]]
 use=[r for r in records if r["mutable"]]
 use.sort(key=lambda r:(-float(r["d"]),-float(r["PVR_score"]),r["sid"]))
 changed=dict(original)
 for slot,r in zip(slots,use):changed[slot]=r["sid"]
 assert changed=={int(r["new_rank"]):r["sid"] for r in records}
samples=q[q.owner_lane.eq("PRICE")].sample(n=64,random_state=20261108)
checks=[]
for row in samples.itertuples():
 z,p,f=get(row.sid)
 cut=pd.Timestamp(row.day);c=cal[cal<=cut]
 a=calc(p.loc[:cut],c).loc[cut];b=scalar(p.loc[:cut]).loc[cut]
 assert abs(a.d-row.d)<1e-13 and abs(b.d-row.d)<1e-13
 m=mp[row.sid];fp=m["refs"]["facts"]
 assert sha(fp)==m["output_sha256"][fp]
 assert np.isclose(p.loc[cut,"adjustment_factor"],f.loc[cut,"factor"],rtol=1e-12,atol=1e-10)
 checks.append(dict(sid=row.sid,day=cut,prefix_error=abs(a.d-row.d),scalar_error=abs(b.d-row.d),fact_source_hash_verified=True))
cs("INDEPENDENT_PREFIX_CHECKS.csv",pd.DataFrame(checks))
p=q[q.owner_lane.eq("PRICE")].copy()
p["price_n"]=p.groupby(["window","day","sector"]).sid.transform("size")
p["price_k"]=p.groupby(["window","day","sector"]).selected.transform("sum")
p["contested"]=(p.price_k>0)&(p.price_n>p.price_k)
m=pd.read_parquet(R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet",columns=["sid","day","window","born","root_day","phase","E0","I"],filters=[("window","in",["2022","2024_924"])])
p=p.merge(m,on=["sid","day","window"],how="left",validate="one_to_one")
assert p.born.notna().all()
p["early"]=p.E0.ne(1)|p.I.ne(1)
p["stock_state"]=np.where(p.E0.ne(1),"E0_OFF",np.where(p.I.ne(1),"E0_ON_I_OFF","E0_ON_I_ON"))
def summarize(g):
 return dict(n=len(g),old_selected=int(g.selected.sum()),dmi_selected=int(g.dmi_selected.sum()),lost=int(g.lost_selection.sum()),gained=int(g.entered_selection.sum()),median_d=float(g.d.median()))
out=[]
for scope,x in [("ALL",p),("CONTESTED",p[p.contested])]:
 for kind in ["born","early","stock_state","phase"]:
  for (yr,value),g in x.groupby(["year",kind],dropna=False):
   out.append(dict(scope=scope,kind=kind,year=yr,value=value,**summarize(g)))
cs("EARLY_STATE_COUNTS.csv",pd.DataFrame(out))
# Previously seen historical labels are descriptive support only, never a new outcome.
label=R/"price_entry_mechanism_comparison_v1/ENTRY_FACTS.csv"
r=pd.read_csv(label,low_memory=False)[["year","sid","signal_day","closed_total_pnl","full_closed","common","entry_day","exit_day"]].rename(columns={"signal_day":"day"})
r["day"]=pd.to_datetime(r.day)
a=p.merge(r,on=["year","sid","day"],how="left",validate="one_to_one")
cs("LOST_ORIGINAL_CASES.csv",a[a.lost_selection])
cs("GAINED_UNOBSERVED_ALTERNATIVES.csv",a[a.entered_selection])
cases=[("688248.SH","2022-05-12"),("002031.SZ","2022-06-13"),("002896.SZ","2022-06-06"),("688256.SH","2022-03-04"),("300260.SZ","2022-02-25"),("000737.SZ","2022-04-18"),("600531.SH","2022-04-19"),("600056.SH","2022-03-03"),("600056.SH","2022-03-30"),("000620.SZ","2022-01-11"),("300085.SZ","2024-09-12"),("300085.SZ","2024-09-19"),("300085.SZ","2024-09-24"),("002583.SZ","2024-09-25"),("605488.SH","2024-09-30"),("002241.SZ","2024-09-30"),("688660.SH","2024-09-25"),("600126.SH","2024-12-11"),("002126.SZ","2024-12-25"),("605099.SH","2024-12-11"),("300229.SZ","2024-09-20"),("300607.SZ","2024-09-27"),("300024.SZ","2024-09-26")]
offers=[]
for year in ["2022","2024"]:
 v=pd.DataFrame(json.loads((R/"independent_channel_joint_economic_v1"/("economic_"+year)/"OFFER_AUDIT.json").read_text()))
 v["day"]=pd.to_datetime(v.day);offers.append(v)
offers=pd.concat(offers,ignore_index=True);nc=[];compet=[]
for sid,day in cases:
 z=q[q.sid.eq(sid)&q.day.eq(day)]
 if z.empty:
  oo=offers[offers.sid.eq(sid)&offers.day.eq(day)]
  nc.append(dict(sid=sid,day=day,status="ABSENT_ORIGINAL_FEASIBLE_QUEUE",offer_results="|".join(oo.result.astype(str))))
 else:
  rr=z.iloc[0];cell=q[q.window.eq(rr.window)&q.day.eq(day)&q.sector.eq(rr.sector)]
  d=rr.to_dict();d.update(status="ACTUAL_FEASIBLE",total_cell=len(cell),price_cell=int(cell.owner_lane.eq("PRICE").sum()))
  nc.append(d);compet.append(cell.assign(case_sid=sid,case_day=day))
cs("NAMED_CASES.csv",pd.DataFrame(nc));cs("NAMED_COMPETITORS.csv",pd.concat(compet,ignore_index=True))
overlap=[]
for name in ["dmi_boundary_migration_v1","core_stock_selection_dmi_v1"]:
 old=pd.read_parquet(R/name/"FEATURES.parquet");old["day"]=pd.to_datetime(old.day)
 old=old[["sid","day","d"]].drop_duplicates()
 matched=p.merge(old,on=["sid","day"],suffixes=("_new","_old"))
 err=float((matched.d_new-matched.d_old).abs().max());assert err==0.
 overlap.append(dict(old_study=name,overlapping_rows=len(matched),max_error=err))
# 2026 is explicitly NOT an actual joined queue: existing target bounds only.
cols=["sid","day","name","sector","root_day","born","E0","I","old_PVR_score","old_PVR_known","old_sector_known","old_sector_observed_today","old_sector_rs_ready_fresh","old_sector_up","conditional_unstarted_target_feasible","close_conditional_q","actual_new_empty_position_eligible"]
sx=R/"independent_channel_full1709_preflight_v1/overlap/SEMICONDUCTOR_2026_RECEIPT_OVERLAP.parquet"
x=pd.read_parquet(sx,columns=cols);x=x[x.day.between("2026-01-05","2026-01-16")].copy();x["d"]=np.nan
for sid,g in x.groupby("sid"):
 z,_,_=get(sid);x.loc[g.index,"d"]=z.d.reindex(g.day).to_numpy()
gate=x[["old_sector_known","old_sector_observed_today","old_sector_rs_ready_fresh","old_sector_up"]].eq(True).all(axis=1)
x["conditional_feasible"]=gate&x.conditional_unstarted_target_feasible
x["conditional_pvr_rank"]=np.nan;x["conditional_dmi_rank"]=np.nan
for _,g in x[x.conditional_feasible].groupby(["day","sector"]):
 old=g.sort_values(["old_PVR_score","sid"],ascending=[False,True])
 new=g.sort_values(["d","old_PVR_score","sid"],ascending=[False,False,True])
 x.loc[old.index,"conditional_pvr_rank"]=range(1,len(old)+1)
 x.loc[new.index,"conditional_dmi_rank"]=range(1,len(new)+1)
x["not_actual_joint_queue"]=True
cs("SEMICONDUCTOR_2026_MARKET_ONLY.csv",x)
js("INDEPENDENT_AUDIT.json",dict(status="PASS_STATIC_RANK_AND_PREFIX_NOT_ECONOMIC",independent_rank_all_rows=len(q),prefix_samples=len(checks),max_prefix_error=max(t["prefix_error"] for t in checks),max_scalar_error=max(t["scalar_error"] for t in checks),old_feature_overlap=overlap,labels_opened_only_after_pick_seal=True,labels_previously_seen_development=True,new_economic_runs=0,new_win_rates=0,source_hashes_reverified=all(sha(k)==h for k,h in json.loads((O/"INPUT_HASHES.json").read_text()).items()),note="The recovery print call failed on numpy int64 only after all sealed files and QA were saved. No recompute was performed. Original run and recovery source preserved.",semiconductor_market_rows=len(x),semiconductor_conditional_rows=int(x.conditional_feasible.sum()),semiconductor_actual_state="UNKNOWN_NOT_REBUILT",extra_source_hashes={str(label):sha(label),str(sx):sha(sx)}))
js("AUDIT_OUTPUT_HASHES.json",{f.name:sha(f) for f in O.iterdir() if f.is_file() and f.name!="AUDIT_OUTPUT_HASHES.json"})
print("STATIC_AUDIT_COMPLETE",len(q),len(checks),flush=True)

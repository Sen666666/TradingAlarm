from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
OLD=R/"direction_change_channel_preflight_v1"
PV=R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet"
DMI=R/"price_dmi_priority_preflight_v1/FEATURES.parquet"
FTR=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py")
def sha(x):return hashlib.sha256(Path(x).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+"\n")
assert not (O/"POINT_FEATURES_PRELABEL.csv").exists()
P=json.loads((O/"PROTOCOL.json").read_text())
cases=json.loads((OLD/"PROTOCOL.json").read_text())["cases"]
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
mp={x["symbol"]:x for x in json.loads(M.read_text())}
sources={str(p):sha(p) for p in [M,H,PV,DMI,FTR,OLD/"PROTOCOL.json",O/"PROTOCOL.json",Path(__file__)]}
pv=pd.read_parquet(PV,columns=["sid","day","score"],filters=[("sid","in",sorted(set(x[0] for x in cases)))])
pv["day"]=pd.to_datetime(pv.day);assert not pv.duplicated(["sid","day"]).any()
pv=pv.set_index(["sid","day"]).score
w=.9**np.arange(20,-1,-1);w=w/w.sum()
def calc(p,day):
 i=cal.get_loc(day)
 if i<84:return dict(known=False,reason="INSUFFICIENT_HISTORY"),None
 q=p.reindex(cal[i-84:i+1]);cols=["open","high","low","close"];raw=["raw_"+c for c in cols]
 ok=np.isfinite(q[cols+raw]).all(axis=1)&q[cols+raw].gt(0).all(axis=1)
 ok &=q.high.ge(q[["open","close","low"]].max(axis=1))&q.low.le(q[["open","close","high"]].min(axis=1))
 for c in ["observed_bar","is_observed_bar","price_eligible","volume_eligible"]:ok &=q[c].eq(True)
 for c in ["source_invalid","synthetic_event_bar"]:ok &=q[c].eq(False)
 ok &=np.isfinite(q.raw_volume)&q.raw_volume.gt(0)&np.isfinite(q.amount)&q.amount.gt(0)&q.volume_unit.eq("shares")&q.amount_unit.eq("CNY")
 for c in cols:ok &=(q[c]-q["raw_"+c]*q.adjustment_factor).abs().le(1e-10)
 av=q.amount/q.raw_volume;tol=.5/q.raw_volume+1e-8
 ok &=av.ge(q.raw_low-tol)&av.le(q.raw_high+tol)
 reasons=[]
 if not ok.all():reasons.append("INVALID_OR_MISSING_BAR")
 for c in ["source_kind","source_path","segment_id","adjustment_factor","volume_factor"]:
  if q[c].isna().any() or q[c].nunique(dropna=False)!=1:reasons.append("CHANGE_OR_UNKNOWN_"+c)
 if reasons:return dict(known=False,reason="|".join(reasons)),None
 r=np.log(q.close).diff();s=(1.4826*r.abs().shift().rolling(63,min_periods=63).median()).clip(lower=1e-8)
 ar=q.amount.shift().rolling(21,min_periods=21).median()
 u=np.tanh(r/s);bv=np.tanh(np.log(q.amount/ar));m=1+.5*u.abs()*bv
 a=np.log(q.high).diff();b=np.log(q.low).diff();g=pd.Series(np.median(np.stack([a,b,np.zeros(len(q))]),axis=0),index=q.index)
 v=np.tanh(g/s);ee=u*m;tt=v*m
 z=pd.DataFrame(dict(r=r,s=s,amount_ref=ar,u=u,bvol=bv,m=m,a=a,b=b,g=g,v=v,e=ee,translation_e=tt)).iloc[-21:].copy()
 assert np.isfinite(z).all(axis=None)
 z["weight"]=w;z["weighted_e"]=w*z.e;z["weighted_t"]=w*z.translation_e
 E=float(np.dot(w,z.e));T=float(np.dot(w,z.translation_e))
 out=dict(known=True,reason="",E=E,PVR_recomputed=50+50*np.tanh(2*E),T=T,gate_pass=bool(T>0),last_g=float(g.iloc[-1]),last_r=float(r.iloc[-1]),
          both_up21=int(((z.a>0)&(z.b>0)).sum()),both_down21=int(((z.a<0)&(z.b<0)).sum()),
          outside21=int(((z.a>0)&(z.b<0)).sum()),inside21=int(((z.a<0)&(z.b>0)).sum()),
          zero_g21=int((z.g==0).sum()),min_scale=float(z.s.min()),positive_translation=float(np.dot(w,np.maximum(z.translation_e,0))),
          negative_translation=float(np.dot(w,np.minimum(z.translation_e,0))))
 return out,z
# Algebraic examples fixed before cases. Same close direction can have different boundary motion.
syn=[(.03,.01,.01),(-.03,-.01,-.01),(.03,-.01,0),(-.03,.01,0),(.03,0,0)]
assert all(abs(float(np.median([a,b,0]))-g)<1e-15 for a,b,g in syn)
dump("SYNTHETIC_QA.json",{"triples":syn,"outside_down_can_be_neutral":True})
rows=[];daily=[];prefix=[]
for sid,group in pd.DataFrame(cases,columns=["sid","day","source"]).groupby("sid",sort=True):
 source=next(k for k in mp[sid]["source_sha256"] if k.endswith("/signal.parquet"))
 sources[source]=sha(source);assert sources[source]==mp[sid]["source_sha256"][source]
 p=pd.read_parquet(source)
 for r in group.itertuples():
  day=pd.Timestamp(r.day);z,c=calc(p,day);zz,cc=calc(p.loc[:day],day);assert z==zz
  if c is not None:pd.testing.assert_frame_equal(c,cc);c["sid"]=sid;c["signal_day"]=r.day;c["bar_day"]=c.index;daily.append(c.reset_index(drop=True))
  prior=float(pv.get((sid,day),np.nan))
  z["original_PVR_saved"]=prior
  if z["known"] and np.isfinite(prior):
   z["PVR_error"]=abs(z["PVR_recomputed"]-prior);assert z["PVR_error"]<1e-8
  rows.append(dict(sid=sid,day=r.day,case_source=r.source,**z));prefix.append(dict(sid=sid,day=r.day,exact=True))
f=pd.DataFrame(rows).sort_values(["day","sid"])
f.to_csv(O/"POINT_FEATURES_PRELABEL.csv",index=False)
pd.concat(daily,ignore_index=True).to_csv(O/"DAILY_COMPONENTS_PRELABEL.csv",index=False)
dump("PREFIX_QA.json",prefix)
dump("FEATURE_SEAL.json",dict(points=sha(O/"POINT_FEATURES_PRELABEL.csv"),daily=sha(O/"DAILY_COMPONENTS_PRELABEL.csv"),no_new_outcome_fit=True))
# Existing economics only after feature sealing. Never compute changed-path returns.
ctx=OLD/"FIXED_CASES_WITH_CONTEXT.csv";sources[str(ctx)]=sha(ctx)
q=pd.read_csv(ctx);keep=["sid","day","name","receipt","phase","E0","I","G","old_price_net","old_price_status","market_regime","close_size_check","open_size_check","historical_fill"]
f=f.merge(q[keep],on=["sid","day"],how="left",validate="one_to_one")
d=pd.read_parquet(DMI);d["day"]=pd.to_datetime(d.day).dt.strftime("%Y-%m-%d")
d=d[["sid","day","d"]].drop_duplicates()
assert not d.duplicated(["sid","day"]).any()
f=f.merge(d,on=["sid","day"],how="left",validate="one_to_one")
f.to_csv(O/"FIXED_CASES_WITH_CONTEXT.csv",index=False)
assert all(sha(p)==h for p,h in sources.items());dump("SOURCE_HASHES.json",sources)
dump("RESULT_SUMMARY.json",dict(cases=len(f),known=int(f.known.sum()),unknown=int((~f.known).sum()),pass_n=int(f.gate_pass.eq(True).sum()),reject_n=int(f.gate_pass.eq(False).sum()),max_PVR_error=float(f.PVR_error.max()),account_runs=0,consumer_runs=0))
print(f[["sid","day","name","known","reason","original_PVR_saved","E","d","T","gate_pass","last_g","outside21","inside21","old_price_net","open_size_check"]].to_string(index=False))
dump("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})

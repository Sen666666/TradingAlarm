from pathlib import Path
import json,hashlib,math,sys,ast
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
LEG=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/strict-entry-capacity-20261027")
AR=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/arithmetic.py")
K=LEG/"code/entry_kernel.py"
Q=R/"price_dmi_priority_preflight_v1/SEALED_RANKS.parquet"
OLD=R/"direction_change_channel_preflight_v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,pd.Timestamp):return v.isoformat()
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+"\n")
assert not (O/"CASE_STATES_PRELABEL.csv").exists()
cases=json.loads((OLD/"PROTOCOL.json").read_text())["cases"];ids=sorted(set(x[0] for x in cases))
mp={m["symbol"]:m for m in json.loads(M.read_text())}
sources={str(p):sha(p) for p in [M,K,AR,Q,OLD/"PROTOCOL.json",O/"PROTOCOL.json",Path(__file__)]}
env={"np":np,"pd":pd,"math":math}
exec(compile(AR.read_text(),str(AR),"exec"),env)
env["EVENT_COLUMNS"]=["confirmation","leg_direction","developing_extreme","confirmed_pivot","event","pivot_age","developing_extreme_price","confirmed_pivot_price","confirmed_pivot_date","developing_extreme_date"]
env["EVENT_DATE_COLUMNS"]=["confirmed_pivot_date","developing_extreme_date"]
exec(compile(K.read_text(),str(K),"exec"),env)
event=env["entry_events"];compare=env["compare"]
def calc(f,k):
 out=[]
 for seg,g in f.groupby("segment_id",sort=False):
  e,_=event(g,k);active=False;floor=math.nan;birth=pd.NaT;floor_known=pd.NaT;rows=[]
  for t,r in g.iterrows():
   exited=False
   if not np.isfinite(r.close) or r.close<=0:
    raise ValueError("Legacy state cannot safely replay invalid-close row")
   if active and compare(float(r.close),floor)<=0:active=False;exited=True
   if e.loc[t,"event"]==1:
    pivot=float(e.loc[t,"confirmed_pivot_price"])
    if active:
     if pivot>floor:floor_known=t
     floor=max(floor,pivot)
    elif not exited:active=True;floor=pivot;birth=t;floor_known=t
   valid=bool(np.isfinite(e.loc[t,"leg_direction"]) and r.volume>0 and np.isfinite(r.volume))
   for c in ["price_eligible","volume_eligible","observed_bar","is_observed_bar"]:
    valid &=bool(r[c])
   for c in ["source_invalid","synthetic_event_bar"]:valid &=not bool(r[c])
   rows.append(dict(day=t,target=active,floor=floor if active or exited else math.nan,event=float(e.loc[t,"event"]),ready=valid,birth=birth if active else pd.NaT,floor_known_at=floor_known if active or exited else pd.NaT,pivot_day=e.loc[t,"confirmed_pivot_date"],confirmation=e.loc[t,"confirmation"]))
  out.append(pd.DataFrame(rows).set_index("day"))
 return pd.concat(out).sort_index()
frames={};facts={};reg=[]
# All multiplier1 checks before any new1.5 computations.
for sid in ids:
 rec=mp[sid];p=next(p for p in rec["source_sha256"] if p.endswith("/signal.parquet"));sources[p]=sha(p);assert sources[p]==rec["source_sha256"][p]
 fp=Path(rec["refs"]["facts"]);sources[str(fp)]=sha(fp)
 f=pd.read_parquet(p);ff=pd.read_parquet(fp);frames[sid]=f;facts[sid]=ff
 z=calc(f,1.0);idx=z.index.intersection(ff.index);good=ff.loc[idx,"e0_ready"].eq(1)&z.loc[idx,"ready"]
 ii=idx[good];tm=int((z.loc[ii,"target"].astype(bool)!=ff.loc[ii,"e0_target"].astype(bool)).sum())
 a=z.loc[ii,"floor"].to_numpy(float);b=ff.loc[ii,"e0_floor"].to_numpy(float);both=np.isfinite(a)&np.isfinite(b);fm=int((np.isfinite(a)!=np.isfinite(b)).sum());mx=float(np.max(abs(a[both]-b[both]))) if both.any() else 0.
 # Some stored floors remain defined after exits; compare active-floor only.
 ai=ii[z.loc[ii,"target"].astype(bool)&ff.loc[ii,"e0_target"].astype(bool)];fa=float(np.nanmax(abs(z.loc[ai,"floor"].to_numpy()-ff.loc[ai,"e0_floor"].to_numpy()))) if len(ai) else 0.
 reg.append(dict(sid=sid,checked=len(ii),target_mismatch=tm,active_floor_max_error=fa,all_floor_finiteness_difference=fm,all_finite_floor_max_error=mx))
dump("MULTIPLIER1_REGRESSION.json",reg)
assert all(r["target_mismatch"]==0 and r["active_floor_max_error"]<1e-8 for r in reg),"CanonicalE0 regression differs; stop before widecase calculation"
queue=pd.read_parquet(Q);queue["day"]=pd.to_datetime(queue.day);qp=queue[queue.owner_lane.eq("PRICE")].copy()
group=["window","day","sector"];counts=qp.groupby(group).agg(price_N=("sid","size"),price_K=("selected","sum")).reset_index()
qp=qp.merge(counts,on=group,validate="many_to_one");qp=qp[qp.sid.isin(ids)].copy();qp["no_price_competition"]=qp.price_N.le(qp.price_K)
wide={};prefix=[];rows=[];oldcheck=[];all_states=[]
for sid in ids:
 f=frames[sid];z=calc(f,1.5);wide[sid]=z
 v=z.copy();v["sid"]=sid;v["day"]=v.index;all_states.append(v.reset_index(drop=True))
 for _,day,origin in [x for x in cases if x[0]==sid]:
  d=pd.Timestamp(day);zz=calc(f.loc[:d],1.5);pd.testing.assert_frame_equal(z.loc[:d],zz,check_exact=True)
  prefix.append(dict(sid=sid,day=day,exact=True,rows=len(zz)))
  if d not in z.index:
   rows.append(dict(sid=sid,day=day,known=False,reason="MISSING_POINT",gate_result="FALLBACK"));continue
  a=z.loc[d];fr=f.loc[d];known=bool(a.ready)
  assert abs(float(fr.close)-float(fr.raw_close)*float(fr.adjustment_factor))<1e-8
  rows.append(dict(sid=sid,day=day,known=known,reason="" if known else "UNREADY_OR_INVALID_CURRENT_OBSERVATION",wide_target=bool(a.target) if known else None,wide_floor=float(a.floor) if known else np.nan,wide_floor_raw=float(a.floor/fr.adjustment_factor) if known else np.nan,wide_birth=a.birth,wide_floor_known_at=a.floor_known_at,wide_event=a.event,wide_confirmation=a.confirmation,pivot_day=a.pivot_day,original_e0=facts[sid].loc[d,"e0_target"],original_i=facts[sid].loc[d,"i_target"],original_i_buy=facts[sid].loc[d,"i_buy"],gate_result=("PASS" if a.target else "REJECT_CURRENT_RECEIPT") if known else "FALLBACK"))
  lp=LEG/"signals"/(sid+".parquet")
  if lp.exists():
   sources[str(lp)]=sha(lp);lz=pd.read_parquet(lp)
   if d in lz.index:oldcheck.append(dict(sid=sid,day=day,old407_wide_target=bool(lz.loc[d,"strict_target"]),current_wide_target=bool(a.target),equal=bool(lz.loc[d,"strict_target"])==bool(a.target)))
for idx,r in qp.iterrows():
 d=r.day;z=wide[r.sid];known=d in z.index and bool(z.loc[d,"ready"])
 qp.at[idx,"wide_known"]=known
 qp.at[idx,"wide_target"]=bool(z.loc[d,"target"]) if known else None
 qp.at[idx,"would_reject"]=known and not bool(z.loc[d,"target"])
f=pd.DataFrame(rows).sort_values(["day","sid"])
f.to_csv(O/"CASE_STATES_PRELABEL.csv",index=False);qp.to_parquet(O/"QUEUE_STATES_PRELABEL.parquet",index=False);pd.concat(all_states).to_parquet(O/"WIDE_STATES.parquet",index=False)
dump("PREFIX_QA.json",prefix);dump("OLD407_POINT_COMPATIBILITY.json",oldcheck)
dump("FEATURE_SEAL.json",{n:sha(O/n) for n in ["CASE_STATES_PRELABEL.csv","QUEUE_STATES_PRELABEL.parquet","WIDE_STATES.parquet"]})
# Outcomes are old saved path labels only; do not simulate new entries.
ctx=OLD/"FIXED_CASES_WITH_CONTEXT.csv";sources[str(ctx)]=sha(ctx)
c=pd.read_csv(ctx);cols=["sid","day","name","old_price_net","old_price_status","receipt","phase","close_size_check","open_size_check","historical_fill"]
f=f.merge(c[cols],on=["sid","day"],how="left",validate="one_to_one");f.to_csv(O/"FIXED_CASES_WITH_CONTEXT.csv",index=False)
summary=[]
for window,g in qp.groupby("window"):
 for name,h in [("ALL_FIXED_STOCK_QUEUE",g),("ORIGINAL_SELECTED",g[g.selected]),("NO_PRICE_COMPETITION",g[g.no_price_competition])]:
  summary.append(dict(window=str(window),scope=name,n=len(h),known=int(h.wide_known.sum()),reject=int(h.would_reject.sum()),stocks=h.sid.nunique(),dates=h.day.nunique()))
pd.DataFrame(summary).to_csv(O/"QUEUE_COVERAGE.csv",index=False)
assert all(sha(p)==h for p,h in sources.items());dump("SOURCE_HASHES.json",sources)
print(f[["sid","day","name","known","wide_target","original_e0","original_i","original_i_buy","wide_birth","gate_result","old_price_net"]].to_string(index=False))
print(pd.DataFrame(summary).to_string(index=False))
dump("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})

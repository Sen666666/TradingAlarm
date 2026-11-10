from pathlib import Path
import json,hashlib,math,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent; B=O.parent
MAN=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
ROUND=B/"actual_round_probability_v1/ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv"
CE=B/"cp1_signal_mechanism_v1/cp_timing_quality_v1/candidate_test/CANDIDATE_CE.parquet"
CLOCK=B/"entry_probability_signal_v1/MARKET_CLOCK.csv"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
def compute(f,cp,ti,ai,floor):
 h=f.iloc[ai-21:ai+1]; assert len(h)==22 and h.segment_id.nunique()==1 and h.close.gt(0).all()
 p=np.log(h.close.to_numpy()); x=np.arange(22,dtype=float); x-=x.mean(); slope=float(x@p/(x@x))
 E=min(float(cp.displacement.iloc[ti]),float(cp.credit.iloc[ti]))
 R=math.log(float(f.close.iloc[ti])/floor); assert R>0 and E>0
 r=cp.r.to_numpy(); seg=f.segment_id.to_numpy(); vals=[]
 for j in range(ai+1,ti+1):
  a=r[:j][(seg[:j]==seg[j])&np.isfinite(r[:j])][-21:]; assert len(a)==21
  vals.append(max(float(np.mean(a*a)),math.log1p(.001)**2))
 V=math.fsum(vals); q=E*R/V; w=q/(1+q)
 return dict(slope=slope,T=1 if slope>=0 else -1,E=E,R=R,V=V,q=q,w=w,n=ti-ai)
def main():
 start=time.monotonic()
 assert not (O/"FEATURES.csv").exists()
 src={str(p):sha(p) for p in [MAN,ROUND,CE,CLOCK,O/"FREEZE.json",Path(__file__)]};dump("SOURCE_FREEZE.json",src)
 cols=["account","sid","first_layer","signal_day","entry_day","first_kind","original_close","first_role_floor","original_factor","t","entry_t","context"]
 a=pd.read_csv(ROUND,usecols=cols);a=a[(a.account=="PVR")&(a.first_kind=="add")].copy();assert len(a)==1814
 c=pd.read_parquet(CE,columns=["account","sid","day","floor","CE","formation_n","formation_anchor_day","anchor_index","variance_budget","source_receipt","source_displacement","source_credit"])
 c=c[c.account=="PVR"].copy();c["signal_day"]=c.day.astype(str).str[:10]
 a=a.merge(c.drop(columns=["account","day"]),on=["sid","signal_day"],how="left",validate="one_to_one")
 assert a.anchor_index.notna().all() and a.source_receipt.all()
 manifest={z["symbol"]:z for z in json.loads(MAN.read_text())}
 rows=[];audit=[];hashes=[]
 for sid,g in a.groupby("sid"):
  ref=manifest[sid]["refs"];f=pd.read_parquet(ref["facts"],columns=["close","segment_id"]);cp=pd.read_parquet(ref["CP1"])
  assert f.index.equals(cp.index)
  for p in [ref["facts"],ref["CP1"]]:
   hs=sha(p); exp=manifest[sid].get("output_sha256",{}).get(p);assert exp is None or exp==hs
   hashes.append(dict(sid=sid,path=p,sha256=hs,manifest_expected=exp))
  for rr in g.to_dict("records"):
   ti=f.index.get_loc(pd.Timestamp(rr["signal_day"])); ai=int(rr["anchor_index"]);floor=float(rr["first_role_floor"])
   assert abs(floor-float(rr["floor"]))<1e-8
   assert abs(float(f.close.iloc[ti])-rr["original_close"])<1e-8
   assert str(f.index[ai].date())==str(rr["formation_anchor_day"]) and ti-ai==rr["formation_n"]
   assert bool(cp.receipt.iloc[ti])
   z=compute(f,cp,ti,ai,floor);s=compute(f.iloc[:ti+1],cp.iloc[:ti+1],ti,ai,floor);assert z==s
   assert abs(z["V"]-rr["variance_budget"])<1e-12
   assert abs(z["E"]-min(rr["source_displacement"],rr["source_credit"]))<1e-12
   assert abs(z["E"]/math.sqrt(z["V"])-rr["CE"])<1e-10
   rows.append(dict(**rr,**z));audit.append(dict(sid=sid,signal_day=rr["signal_day"],prefix_exact=True,anchor_exact=True,floor_exact=True,variance_error=z["V"]-rr["variance_budget"]))
 out=pd.DataFrame(rows).sort_values(["signal_day","sid"]).reset_index(drop=True)
 out.to_csv(O/"FEATURES.csv",index=False);pd.DataFrame(audit).to_csv(O/"INPUT_PREFIX_AUDIT.csv",index=False);pd.DataFrame(hashes).to_csv(O/"CACHE_SOURCE_HASHES.csv",index=False)
 days=pd.read_csv(CLOCK,index_col=0,parse_dates=True).index;ident=[]
 for month in sorted({str(d.to_period("M")) for d in days if d.year>=2023 and d<=pd.Timestamp("2026-05-15")}):
  dt=next(d for d in days if str(d.to_period("M"))==month);cut=days.get_loc(dt)
  tr=out[(out.t>=cut-504)&(out.entry_t<=cut-120)];w=tr.w.to_numpy();T=tr.T if False else tr["T"].to_numpy()
  X=np.column_stack([1-w,w*(T==1),w*(T==-1)]);sv=np.linalg.svd(X,compute_uv=False);rank=np.linalg.matrix_rank(X);cond=float(sv[0]/sv[-1]) if len(sv)==3 and sv[-1]>0 else np.inf
  zz=dict(month=month,cutoff=str(dt.date()),cut=int(cut),n=len(tr),dates=tr.signal_day.nunique(),stocks=tr.sid.nunique(),rank=int(rank),condition=cond,singular_values=sv.tolist(),plus_n=int((T==1).sum()),minus_n=int((T==-1).sum()),w_min=float(w.min()) if len(w) else None,w_max=float(w.max()) if len(w) else None,w_std=float(w.std()) if len(w) else None)
  for tag,v in [("base",1-w),("plus",w*(T==1)),("minus",w*(T==-1))]:
   zz[tag+"_weight_mass"]=float(v.sum());zz[tag+"_weight_ess_nonindependent"]=float(v.sum()**2/(v@v)) if v@v>0 else 0
  ident.append(zz)
 pd.DataFrame(ident).to_csv(O/"MONTHLY_IDENTIFIABILITY.csv",index=False)
 for p,h in src.items():assert sha(p)==h
 summary=dict(status="FEATURES_FROZEN_NO_NEW_OUTCOME_LABELS_READ",rows=len(out),stocks=out.sid.nunique(),dates=out.signal_day.nunique(),prefix_checks=len(audit),all_input_lineage_passed=True,monthly_count=len(ident),rank_deficient_months=[z["month"] for z in ident if z["rank"]<3],max_condition=max(z["condition"] for z in ident),feature_sha256=sha(O/"FEATURES.csv"),freeze_sha256=sha(O/"FREEZE.json"),seconds=time.monotonic()-start,account_runs=0,parameter_searches=0,outcome_model_runs=0)
 dump("FEATURE_AUDIT_SUMMARY.json",summary);print(json.dumps(summary,ensure_ascii=False));print(pd.DataFrame(ident)[["month","n","dates","rank","condition"]].to_string(index=False))
if __name__=="__main__":main()

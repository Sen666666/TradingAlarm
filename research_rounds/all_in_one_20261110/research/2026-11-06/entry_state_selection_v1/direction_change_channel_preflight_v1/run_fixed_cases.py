from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
def logsumexp(values):
 a=np.asarray(values,dtype=float);m=float(np.max(a))
 return m+math.log(float(np.exp(a-m).sum()))
def log_ndtr(x):
 x=float(x)
 if x>-36:return math.log(.5*math.erfc(-x/math.sqrt(2)))
 z=-x;term=1.;total=1.
 for k in range(1,100):
  term*=-(2*k-1)/(z*z);total+=term
  if abs(term)<1e-17*abs(total):break
 return -.5*z*z-math.log(z)-.5*math.log(2*math.pi)+math.log(total)
# Exact/probability symmetry and overlap checks, before reading any case data.
assert abs(log_ndtr(0)+math.log(2))<1e-15
for _x in [-35.999,-20.,-10.,-2.,0.,2.,10.,20.]:
 assert abs(math.exp(log_ndtr(_x))+math.exp(log_ndtr(-_x))-1)<1e-14
assert abs(log_ndtr(-36)-math.log(.5*math.erfc(36/math.sqrt(2))))<2e-12
assert abs(logsumexp([-1000.,-1000.])-(-1000+math.log(2)))<1e-12
O=Path(__file__).resolve().parent;R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 return v
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+"\n")
def logs(x,w):
 W=w.sum();S=(w*x).sum();Q=(w*x*x).sum();a=-Q/2-math.log1p(W)/2+S*S/(2*(1+W));z=S/math.sqrt(1+W)
 return a+math.log(2)+log_ndtr(z),a+math.log(2)+log_ndtr(-z)
def evidence(x,w):
 pos,neg=logs(x,w);C=[pos-math.log(4)];RR=[];N=[neg-math.log(4)];rh=[]
 for h in range(2,22):
  pp,pn=logs(x[:-h],w[:-h]);qp,qn=logs(x[-h:],w[-h:]);base=-math.log(8*20)
  C.append(base+pp+qp);RR.append(base+pn+qp);N.extend([base+pp+qn,base+pn+qn]);rh.append(dict(h=h,post_sign_logBF=float(qp-qn),pre_mean=float(np.average(x[:-h],weights=w[:-h])),post_mean=float(np.average(x[-h:],weights=w[-h:]))))
 lc,lr,ln=logsumexp(C),logsumexp(RR),logsumexp(N);p=np.exp(np.array([lc,lr,ln])-logsumexp([lc,lr,ln]));k=int(np.argmax(RR))
 return dict(piC=float(p[0]),piR=float(p[1]),piN=float(p[2]),up_odds_log=float(np.logaddexp(lc,lr)-ln),structure_pass=bool(p[0]+p[1]>p[2]),qR=float(p[1]/(p[0]+p[1])),dominant_positive="R" if p[1]>p[0] else "C",R_map_h=rh[k]["h"],R_map_post_logBF=rh[k]["post_sign_logBF"],R_map_pre_x=rh[k]["pre_mean"],R_map_post_x=rh[k]["post_mean"])
P=json.loads((O/"PROTOCOL.json").read_text());assert not (O/"CASE_STRUCTURE_PRELABEL.csv").exists()
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);mp={m["symbol"]:m for m in json.loads(M.read_text())}
sources={str(p):sha(p) for p in [M,H,O/"PROTOCOL.json",Path(__file__)]}
def calc(p,day):
 i=cal.get_loc(day)
 if i<83:return dict(known=False,reason="INSUFFICIENT_COMMON_HISTORY")
 q=p.reindex(cal[i-83:i+1]);cols=["open","high","low","close"];raw=["raw_"+c for c in cols]
 ok=np.isfinite(q[cols+raw]).all(axis=1)&q[cols+raw].gt(0).all(axis=1)
 for c in ["observed_bar","is_observed_bar","price_eligible","volume_eligible"]:ok &=q[c].eq(True)
 for c in ["source_invalid","synthetic_event_bar"]:ok &=q[c].eq(False)
 ok &=np.isfinite(q.raw_volume)&q.raw_volume.gt(0)&np.isfinite(q.amount)&q.amount.gt(0)&q.volume_unit.eq("shares")&q.amount_unit.eq("CNY")
 for c in cols:ok &=(q[c]-q["raw_"+c]*q.adjustment_factor).abs().le(1e-10)
 av=q.amount/q.raw_volume;tol=.5/q.raw_volume+1e-8
 ok &=av.ge(q.raw_low-tol)&av.le(q.raw_high+tol)
 reasons=[]
 if not ok.all():reasons.append("INVALID_OR_MISSING_OBSERVATION")
 for c in ["source_kind","source_path","segment_id","adjustment_factor","volume_factor"]:
  if q[c].isna().any() or q[c].nunique(dropna=False)!=1:reasons.append("CHANGE_OR_UNKNOWN_"+c)
 if reasons:return dict(known=False,reason="|".join(reasons))
 rr=np.log(q.close).diff();prior=rr.iloc[-64:-1].to_numpy();s=1.4826*np.median(abs(prior-np.median(prior)))
 if not np.isfinite(s) or s<=0:return dict(known=False,reason="ZERO_OR_INVALID_PRIOR_MAD")
 x=rr.iloc[-63:].to_numpy()/s;v=q.raw_volume;B=v.shift().rolling(21,min_periods=21).median();w=1+.5*np.tanh(np.log(v/B)).iloc[-63:].to_numpy()
 assert np.isfinite(x).all() and np.isfinite(w).all() and (w>.5).all() and (w<1.5).all()
 z=evidence(x,w);return dict(known=True,reason="",sigma=s,r63=float(np.log(q.close.iloc[-1]/q.close.iloc[-64])),r21=float(np.log(q.close.iloc[-1]/q.close.iloc[-22])),weight_min=float(w.min()),weight_max=float(w.max()),**z)
# Structural algebra checks only, no outcomes.
assert abs(sum(evidence(np.zeros(63),np.ones(63))[k] for k in ["piC","piR","piN"])-1)<1e-14
null=evidence(np.r_[np.repeat(-1.,42),np.repeat(.001,21)],np.ones(63))
matched=logs(np.repeat(.001,21),np.ones(21));assert abs(matched[0]-matched[1])<.01
dump("SYNTHETIC_QA.json",dict(algebraic_false_reversal_case=null,matched_post_logBF=float(matched[0]-matched[1]),not_profit_validation=True))
rows=[];prefix=[]
for sid,dates in pd.DataFrame(P["cases"],columns=["sid","day","source"]).groupby("sid",sort=True):
 m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));sources[path]=sha(path);assert sources[path]==m["source_sha256"][path]
 p=pd.read_parquet(path)
 for r in dates.itertuples():
  day=pd.Timestamp(r.day);z=calc(p,day);zt=calc(p.loc[:day],day);assert z==zt
  rows.append(dict(sid=sid,day=r.day,case_source=r.source,**z));prefix.append(dict(sid=sid,day=r.day,exact=True))
f=pd.DataFrame(rows).sort_values(["day","sid"]);f.to_csv(O/"CASE_STRUCTURE_PRELABEL.csv",index=False);dump("PREFIX_QA.json",prefix)
dump("STRUCTURE_SEAL.json",dict(case_sha256=sha(O/"CASE_STRUCTURE_PRELABEL.csv"),no_outcomes_used_in_structure=True,case_count=len(f),known=int(f.known.sum())))
# Only after structure sealed, connect saved contexts and old same-path outcomes.
market=R/"selection_entry_diagnosis_v1/MARKET_FIXED1709_WARM.csv";sources[str(market)]=sha(market)
mk=pd.read_csv(market,index_col=0);mk.index=mk.index.astype(str)
for c in ["breadth20","delta5","known_n","regime"]:f["market_"+c]=f.day.map(mk[c])
overlap=R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet";sources[str(overlap)]=sha(overlap)
cols=["sid","day","window","name","industry","sector","E0","I","G","i_buy","CP","born","receipt","phase","old_sector_up","old_sector_known","close_size_check","open_size_check","close_conditional_q","open_conditional_q","next_raw_open","historical_fill"]
q=pd.read_parquet(overlap,columns=cols,filters=[("sid","in",f.sid.unique().tolist())]);q["day"]=pd.to_datetime(q.day).dt.strftime("%Y-%m-%d");q=q.drop_duplicates(["sid","day"])
f=f.merge(q,on=["sid","day"],how="left",validate="one_to_one")
extra=R/"independent_channel_probe_preflight_v1/FIXED_DAILY.csv";sources[str(extra)]=sha(extra);ex=pd.read_csv(extra);ex["day"]=pd.to_datetime(ex.day).dt.strftime("%Y-%m-%d")
for idx,row in f[f.window.isna()].iterrows():
 e=ex[(ex.sid==row.sid)&(ex.day==row.day)]
 if len(e)==1:
  for c in ["E0","I","G","i_buy","CP","born","receipt","phase"]:f.at[idx,c]=e.iloc[0][c]
  f.at[idx,"context_source"]="FIXED_DAILY_MARKET_ONLY"
f["old_price_net"]=np.nan;f["old_price_status"]="NO_EXACT_ORIGINAL_PRICE_ROUND"
for window in ["2022","2024"]:
 path=R/f"independent_channel_joint_economic_v1/economic_{window}/joint/ROUNDS.csv";sources[str(path)]=sha(path)
 rr=pd.read_csv(path);rr=rr[rr.owner_lane.eq("PRICE")];rr["signal_day"]=pd.to_datetime(rr.signal_day).dt.strftime("%Y-%m-%d")
 for idx,row in f.iterrows():
  a=rr[(rr.sid==row.sid)&(rr.signal_day==row.day)]
  if len(a)==1:
   f.at[idx,"old_price_net"]=a.iloc[0].net_pnl;f.at[idx,"old_price_status"]=a.iloc[0].status
f.to_csv(O/"FIXED_CASES_WITH_CONTEXT.csv",index=False)
assert all(sha(p)==h for p,h in sources.items());dump("SOURCE_HASHES.json",sources)
print(f[["sid","day","name","known","reason","piC","piR","piN","structure_pass","qR","dominant_positive","R_map_h","R_map_post_logBF","market_regime","receipt","phase","old_price_net","open_size_check"]].to_string(index=False))
dump("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})

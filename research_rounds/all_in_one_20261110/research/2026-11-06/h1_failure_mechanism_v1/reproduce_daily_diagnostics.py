
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq, json, hashlib
out=Path("/Users/bytedance/Documents/Codex/2026-11-06/h1_failure_mechanism_v1")
out.mkdir(parents=True,exist_ok=True)
P=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
cache=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1")
z=np.load(P); dates=pd.DatetimeIndex(z["dates"]); sy=z["symbols"].astype(str); col={s:j for j,s in enumerate(sy)}
C=z["close"];S=z["score"];R=z["raw"];H=z["h"];N=z["nref"];SEG=z["segment"];OB=z["obs_count"];stocks=np.array([not s.startswith("URFI") for s in sy])
groups=[("2024-09-09","2024-10-10",["002583.SZ","300085.SZ","URFI881129","URFI881272"]),("2025-12-15","2026-01-23",["300666.SZ","301611.SZ","603061.SH","URFI881121"])]
rows=[]; eps=[]; sig=[]; threshold_rows=[]
for a,b,ss in groups:
 idx=np.where((dates>=a)&(dates<=b))[0]
 for s in ss:
  j=col[s];pool=stocks if not s.startswith("URFI") else ~stocks
  for t in idx:
   h=int(H[t,j]);ls=np.minimum(np.arange(5)*63,h);ep=C[t-ls,j];ret=ep[:-1]/ep[1:]-1;w=ret*np.array([.4,.2,.2,.2]);w[ls[1:]==ls[:-1]]=0;score=S[t,j];finite=np.where(pool&np.isfinite(S[t]))[0]
   rank=1+sum((S[t,k]>score)or(S[t,k]==score and sy[k]<s)for k in finite)
   rawcheck=float(np.round(w.sum(),12));assert rawcheck==R[t,j]
   current_effect=.4*(C[t,j]-C[t-1,j])/C[t-1-63,j]
   delta=float(R[t,j]-R[t-1,j])
   d={"day":str(dates[t].date()),"symbol":s,"h":h,"cached_close":float(C[t,j]),"cached_raw":float(R[t,j]),"cached_percentile":float(score),"ordinal_1based_among_cached_known":int(rank),"known_group_size":len(finite),"cached_same_h_Nref":int(N[t,j]),"recent_weighted_term":float(w[0]),"older_weighted_sum":float(w[1:].sum()),"round12_exact":True,"daily_raw_change":delta,"current_close_effect_old_endpoints":float(current_effect),"all_endpoint_roll_residual":delta-current_effect,"price_change_from_window_start":float(C[t,j]/C[idx[0],j]-1)}
   for k in range(4):d["return"+str(k+1)]=float(ret[k]);d["weighted_term"+str(k+1)]=float(w[k])
   for k,lag in enumerate(ls):
    d["endpoint"+str(k)+"_date"]=str(dates[t-lag].date());d["endpoint"+str(k)+"_close"]=float(ep[k])
    eps.append({"day":d["day"],"symbol":s,"endpoint":k,"lag":int(lag),"date":str(dates[t-lag].date()),"close":float(ep[k]),"segment":int(SEG[t-lag,j])})
   rows.append(d)
  if not s.startswith("URFI"):
   cf=pq.read_table(cache/"artifacts"/(s+".parquet"),columns=["sid","day","source_row_present","native__e0_ready","native__i_target","native__i_entered","native__i_buy","native__g_grade","cp__receipt","price__close"]).to_pandas()
   cf=cf[(cf.day>=a)&(cf.day<=b)].copy();cf["warning"]="CANONICAL signal source, not original H1 price source or original account authorization";sig.append(cf)
f=pd.DataFrame(rows);f.to_csv(out/"ORIGINAL_H1_DAILY_DECOMPOSITION.csv",index=False);pd.DataFrame(eps).to_csv(out/"ORIGINAL_H1_ENDPOINTS.csv",index=False)
g=pd.concat(sig,ignore_index=True);g.to_csv(out/"CANONICAL_NATIVE_SIGNAL_COMPANION.csv",index=False)
for a,b,ss in groups:
 for s in ss:
  q=f[f.symbol.eq(s)]
  for label,condition in [("ordinal_top20",q.ordinal_1based_among_cached_known<=20),("ordinal_top100",q.ordinal_1based_among_cached_known<=100),("percentile_ge90",q.cached_percentile>=90)]:
   hit=q[condition]
   if len(hit):
    x=hit.iloc[0];threshold_rows.append({"symbol":s,"interval_start":a,"interval_end":b,"diagnostic_marker":label,"first_date_within_interval":x.day,"rise_from_interval_first_close":x.price_change_from_window_start,"cached_score":x.cached_percentile,"ordinal_1based":x.ordinal_1based_among_cached_known})
   else:threshold_rows.append({"symbol":s,"interval_start":a,"interval_end":b,"diagnostic_marker":label,"first_date_within_interval":None,"rise_from_interval_first_close":None,"cached_score":None,"ordinal_1based":None})
pd.DataFrame(threshold_rows).to_csv(out/"DIAGNOSTIC_THRESHOLD_CROSSINGS.csv",index=False)
audit={"scope":"Bounded read-only source analysis; new files only; no account or full-universe signal recomputation","original_h1_source":str(P),"original_h1_sha256":hashlib.sha256(P.read_bytes()).hexdigest(),"rows":len(f),"endpoint_rows":len(eps),"canonical_signal_rows":len(g),"all_raw_round12_exact":bool(f.round12_exact.all()),"rank_is_1based":True,"original_source_ordinal_is_0based":True,"thresholds_are_diagnostic_markers_not_original_admission_rules":True,"canonical_signals_not_original_S0_or_account_permissions":True,"pit_and_execution":"Not certified","candidate_formula_testing":"Not run; proposals and validation specification only"}
(out/"AUDIT.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(audit,ensure_ascii=False));print(pd.DataFrame(threshold_rows).to_string(index=False))

"""Read sealed predictions only: fixed-case, 924 and clustered uncertainty descriptions; no fit."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
r=pd.read_parquet(O/"PREDICTIONS.parquet")
assert hashlib.sha256((O/"PREDICTIONS.parquet").read_bytes()).hexdigest()==json.loads((O/"PREDICTION_SEAL.json").read_text())["predictions_sha256"]
def summary(g):
 w=g[g.net_pnl>0];l=g[g.net_pnl<0]
 return dict(n=len(g),W=len(w),L=len(l),winrate=len(w)/len(g) if len(g) else None,mean_net=g.net_pnl.mean(),mean_win=w.net_pnl.mean(),mean_loss=l.net_pnl.mean(),payoff=w.net_pnl.mean()/abs(l.net_pnl.mean()) if len(l) else None,tail30=int(g.net_return_on_buy_cash.ge(.3).sum()),old_net=g.net_pnl.sum())
rows=[]
for window,g in r.groupby("window_label"):
 for m in ["original","pvr","interaction"]:
  z=g[g.entered&g.ordinary&g.p_interaction.notna()&g["select_"+m]]
  rows.append(dict(window=window,model=m,scope="COMMON_KNOWN_SCORE_ORDINARY",**summary(z)))
pd.DataFrame(rows).to_csv(O/"KNOWN_SCORE_ONLY_OUTCOMES.csv",index=False)
g=r[r.signal_day.between("2024-09-19","2024-10-08")];rows=[]
for m in ["original","pvr","interaction"]:
 s=g[g["select_"+m]];z=s[s.entered&s.eval_financial_known]
 rows.append(dict(model=m,registered=len(s),filled=int(s.entered.sum()),known_closed=len(z),**summary(z)))
pd.DataFrame(rows).to_csv(O/"FIXED_924_DESCRIPTION.csv",index=False)
cases=[("605118.SH","2022-08-22"),("605020.SH","2022-07-15"),("002174.SZ","2022-11-08"),("688660.SH","2024-09-25"),("600396.SH","2024-10-28"),("605488.SH","2024-09-30"),("002241.SZ","2024-09-30"),("600126.SH","2024-12-11"),("605099.SH","2024-12-11"),("002126.SZ","2024-12-25"),("002583.SZ","2024-09-25")]
mask=[any(row.sid==sid and row.signal_day==pd.Timestamp(day) for sid,day in cases) for row in r.itertuples()]
r[mask].to_csv(O/"PRIOR_FIXED_CASES_IN_VALIDATION.csv",index=False)
def clustered(g,inf):
 x=g[["sid","t"]].copy();x["inf"]=np.asarray(inf);x["block"]=x.t//20
 def var(keys):
  s=x.groupby(keys).inf.sum();k=len(s)
  return k/(k-1)*float((s*s).sum()) if k>1 else np.nan,k
 vb,nb=var(["block"]);vs,ns=var(["sid"]);vi,_=var(["block","sid"])
 se=float(np.sqrt(max(0.,vb,vs,vb+vs-vi)))
 return dict(blocks=nb,stocks=ns,block_se=float(np.sqrt(vb)),stock_se=float(np.sqrt(vs)),conservative_se=se)
rows=[]
for w,g in r.groupby("window_label"):
 z=g[g.entered&g.ordinary];y=z.net_pnl.gt(0).to_numpy(float)
 for a,b in [("interaction","original"),("interaction","pvr"),("pvr","original")]:
  sa=z["select_"+a].to_numpy(bool);sb=z["select_"+b].to_numpy(bool);ma=y[sa].mean();mb=y[sb].mean()
  inf=sa*(y-ma)/sa.sum()-sb*(y-mb)/sb.sum();q=clustered(z,inf);d=float(ma-mb)
  rows.append(dict(window=w,metric="STATIC_ORDINARY_SELECTION_WINRATE",comparison=a+"-"+b,n=len(z),difference=d,approx95_low=d-1.96*q["conservative_se"],approx95_high=d+1.96*q["conservative_se"],**q))
 z=g[g.entered&g.ordinary&g.p_interaction.notna()];y=z.net_pnl.gt(0).to_numpy(float)
 for a,b in [("p_interaction","p0"),("p_interaction","p_pvr")]:
  pa=np.clip(z[a].to_numpy(float),1e-12,1-1e-12);pb=np.clip(z[b].to_numpy(float),1e-12,1-1e-12)
  for metric,v in [("BRIER",(pa-y)**2-(pb-y)**2),("LOGLOSS",-y*np.log(pa)-(1-y)*np.log(1-pa)+y*np.log(pb)+(1-y)*np.log(1-pb))]:
   d=float(v.mean());q=clustered(z,(v-d)/len(z))
   rows.append(dict(window=w,metric=metric,comparison=a+"-"+b,n=len(z),difference=d,approx95_low=d-1.96*q["conservative_se"],approx95_high=d+1.96*q["conservative_se"],**q))
pd.DataFrame(rows).to_csv(O/"DESCRIPTIVE_CLUSTER_UNCERTAINTY.csv",index=False)
(O/"SUPPLEMENT_BOUNDARIES.json").write_text(json.dumps({"sources":"Sealed existing predictions only; no refitting or model/threshold change.","cases":"Prior fixed19 cases that fall inside the two validation windows; no new winner-based rule.","period924":"Existing context Sep19-Oct8 descriptive slice; cannot replace the frozen whole2024 window.","cluster":"20-common-session date blocks plus stock clusters; conservative max(date variance,stock variance,two-way variance). Conditional on fitted models and known ordinary outcomes. Does not correct missingness, vintage/PIT, training-estimation uncertainty or multiple historical research."},indent=2))
print(pd.DataFrame(rows).to_string(index=False))

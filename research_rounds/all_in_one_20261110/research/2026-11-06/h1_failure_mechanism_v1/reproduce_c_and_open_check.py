
from pathlib import Path
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.dataset as ds,pyarrow.parquet as pq,json,hashlib,time
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/h1_failure_mechanism_v1");root=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1")
freeze={"candidate":"C_extension_discount","formula":"Z=max(0,(C_t-mean(C_(t-20)..C_(t-1)))/ATR_prior20); g=1/(1+Z^2); Cscore=H+g*(B-H)","ATR":"ATR_prior20=(1/20)*sum_{u=t-20}^{t-1} max(H_u-L_u,abs(H_u-C_(u-1)),abs(L_u-C_(u-1))). Current day excluded. Common-date clock; all21 required close and20 H/L observations finite, positive, coherent.","unknown_rule":"Unknown or nonpositive ATR disables new promotion and keeps H. Never replace missing ATR by epsilon.","constant_choice":"Unit ATR yields parameter-free attenuation beyond the frozen20 lookback. No threshold/window search; potentially very strong damping must be reported.","standing_H1_preservation":"Numeric score lower bound H; cross-stock ordinal can still move when others are promoted.","scope":"Same six dates and same mature252 i_buy candidates, same B and H frozen earlier. Exploration after named failures were already seen, explicitly not holdout or causal efficacy.","labels":"Same common-date horizon20 closes relative signal close; complete-path labels only, no backfill."}
(O/"C_EXTENSION_DISCOUNT_FREEZE.json").write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+"\n")
rk=pd.read_csv(O/"SIX_DATE_ALL_CANONICAL_RANKS.csv");days=pd.to_datetime(sorted(rk.day.unique()));grid=pd.DatetimeIndex(pq.read_table(root/"artifacts/000001.SZ.parquet",columns=["day"]).to_pandas().day)
needed=set()
for d in days:
 t=grid.get_loc(d);needed.update(grid[t-21:t+21])
files=[str(root/k)for k in json.loads((root/"CACHE_DATASET.json").read_text())["files"]];D=ds.dataset(files,format="parquet");f=D.to_table(columns=["sid","day","price__close","price__high","price__low"],filter=ds.field("day").isin(pa.array(sorted(needed)))).to_pandas()
P=f.pivot(index="day",columns="sid",values="price__close").reindex(grid);ids=P.columns.to_numpy();C=P.to_numpy();Hi=f.pivot(index="day",columns="sid",values="price__high").reindex(index=grid,columns=ids).to_numpy();Lo=f.pivot(index="day",columns="sid",values="price__low").reindex(index=grid,columns=ids).to_numpy();del f
rout=[];choices=[];coverage=[]
for d in days:
 t=grid.get_loc(d);q=rk[rk.day==str(d.date())].set_index("sid").reindex(ids).copy()
 a=C[t-20:t];prev=C[t-21:t-1];hi=Hi[t-20:t];lo=Lo[t-20:t];coherent=(np.isfinite(a)&np.isfinite(prev)&np.isfinite(hi)&np.isfinite(lo)&(a>0)&(prev>0)&(hi>=a)&(lo<=a)&(lo>0)).all(axis=0)
 tr=np.maximum.reduce([hi-lo,abs(hi-prev),abs(lo-prev)]);atr=np.mean(tr,axis=0);ma=np.mean(a,axis=0);valid=coherent&np.isfinite(atr)&(atr>0);z=np.divide(C[t]-ma,atr,out=np.full(len(ids),np.nan),where=valid);z=np.maximum(0,z);g=np.divide(1,np.add(1,z*z),out=np.zeros(len(ids)),where=np.isfinite(z));score=q.full_H1_percentile.to_numpy()+g*(q.B_score.to_numpy()-q.full_H1_percentile.to_numpy())
 q["ATR_prior20"]=atr;q["prior_SMA20"]=ma;q["extension_Z"]=z;q["ATR_over_current_close"]=atr/C[t];q["ATR_coherent_known"]=valid;q["discount_g"]=g;q["C_score"]=score
 eligible=q.eligible_cached_i_buy.to_numpy(dtype=bool);jj=np.flatnonzero(eligible&np.isfinite(score));jj=jj[np.lexsort((ids[jj],-score[jj]))];q["C_eligible_rank"]=pd.Series(np.arange(1,len(jj)+1),index=ids[jj]).reindex(ids)
 for k in [20,100]:
  for j in jj[:k]:choices.append({"day":str(d.date()),"sid":ids[j],"strategy":"C_extension","K":k,"rank":int(np.where(jj==j)[0][0]+1),"score":float(score[j]),"index_t":int(t),"index_j":int(j)})
 q=q.reset_index();rout.append(q)
 v=q.loc[eligible&valid,"ATR_over_current_close"];coverage.append({"day":str(d.date()),"i_buyN":int(eligible.sum()),"ATR_valid":int((eligible&valid).sum()),"ATR_relative_min":v.min(),"ATR_relative_q05":v.quantile(.05),"ATR_relative_median":v.median(),"below_1e_minus6_count":int((v<1e-6).sum()),"C_ge_H_all_finite":bool(np.all(score[eligible]>=q.full_H1_percentile.to_numpy()[eligible]-1e-12))})
rr=pd.concat(rout,ignore_index=True);rr.to_csv(O/"C_EXTENSION_ALL_RANKS.csv",index=False);pd.DataFrame(choices).to_csv(O/"C_SELECTIONS_BEFORE_LABELS.csv",index=False);pd.DataFrame(coverage).to_csv(O/"C_ATR_DOMAIN_AUDIT.csv",index=False)
(O/"C_RANK_FREEZE_RECEIPT.json").write_text(json.dumps({"rank_sha256":hashlib.sha256((O/"C_EXTENSION_ALL_RANKS.csv").read_bytes()).hexdigest(),"selection_sha256":hashlib.sha256((O/"C_SELECTIONS_BEFORE_LABELS.csv").read_bytes()).hexdigest(),"new_formula_frozen_after_A_B_results":True},indent=2)+"\n")
labels=[]
for x in choices:
 t=x["index_t"];j=x["index_j"];fut=C[t+1:t+21,j];ok=np.isfinite(fut).all()and(fut>0).all();r=x.copy();r["complete20"]=bool(ok);r["end20"]=float(fut[-1]/C[t,j]-1)if ok else None;r["mae20"]=float(min(0,np.min(fut/C[t,j]-1)))if ok else None;r["mfe20"]=float(max(0,np.max(fut/C[t,j]-1)))if ok else None;labels.append(r)
ll=pd.DataFrame(labels);ll.to_csv(O/"C_SELECTED_DESCRIPTIVE_LABELS.csv",index=False);old=pd.read_csv(O/"SIX_DATE_SELECTED_DESCRIPTIVE_LABELS.csv");summary=[]
for key,a in ll.groupby(["day","K"],sort=False):
 v=a[a.complete20];h=old[(old.day==key[0])&(old.K==key[1])&(old.strategy=="H1")];b=old[(old.day==key[0])&(old.K==key[1])&(old.strategy=="B_confirmed")];summary.append({"day":key[0],"K":key[1],"strategy":"C_extension","selected":len(a),"complete20":len(v),"mean_end20":v.end20.mean(),"median_end20":v.end20.median(),"positive_fraction":v.end20.gt(0).mean(),"mean_mae20":v.mae20.mean(),"overlap_H1":len(set(a.sid)&set(h.sid)),"overlap_B":len(set(a.sid)&set(b.sid))})
pd.DataFrame(summary).to_csv(O/"C_PILOT_SUMMARY.csv",index=False)
changed=pd.read_csv(O/"JAN15_ADDED_REMOVED_EXPLANATION.csv");jan=rr[rr.day=="2026-01-15"].set_index("sid");changed=changed.join(jan[["ATR_prior20","ATR_over_current_close","extension_Z","discount_g","C_score","C_eligible_rank"]],on="sid");changed.to_csv(O/"JAN15_CHANGED_WITH_C_AND_ATR.csv",index=False)
# Exact next-open anchor sensitivity uses actual future close path, not clipped old anchor MAE.
opens=pd.read_csv(O/"OCT08_EXECUTION_PRICE_PROXIES_ALL.csv").set_index("sid");sens=[];t=grid.get_loc(pd.Timestamp("2024-10-08"))
for st in ["H1","A_recent","B_confirmed"]:
 for k in [20,100]:
  a=old[(old.day=="2024-10-08")&(old.K==k)&(old.strategy==st)];ends=[];maes=[]
  for row in a.itertuples():
   j=np.where(ids==row.sid)[0][0];fu=C[t+1:t+21,j];op=C[t,j]*(1+opens.at[row.sid,"nextopen_gap_1009"]);ok=np.isfinite(fu).all()and np.isfinite(op)and op>0
   if ok:ends.append(fu[-1]/op-1);maes.append(min(0,np.min(fu/op-1)))
  sens.append({"strategy":st,"K":k,"selected":len(a),"complete20":len(ends),"close_anchor_mean":a.end20.mean(),"next_open_proxy_mean":np.mean(ends),"close_anchor_mae_mean":a.mae20.mean(),"next_open_proxy_close_path_mae_mean":np.mean(maes),"actual_future_path_recomputed":True})
pd.DataFrame(sens).to_csv(O/"OCT08_NEXT_OPEN_ANCHOR_SENSITIVITY.csv",index=False)
print("ATR_AUDIT");print(pd.DataFrame(coverage).to_string(index=False));print("SUMMARY_C");print(pd.DataFrame(summary).to_string(index=False));print("JAN_CHANGED_C");print(changed[["sid","current_name","change","H1_eligible_rank","B_eligible_rank","C_eligible_rank","ATR_prior20","ATR_over_current_close","extension_Z","discount_g","end20"]].to_string(index=False));print("ANCHOR_FIXED");print(pd.DataFrame(sens).to_string(index=False))

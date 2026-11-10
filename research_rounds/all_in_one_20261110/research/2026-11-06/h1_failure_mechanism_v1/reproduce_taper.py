
from pathlib import Path
import numpy as np,pandas as pd,pyarrow.parquet as pq,json,hashlib
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/h1_failure_mechanism_v1");root=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1")
freeze={"requested_central":[5,10],"neighbors":[[l,u]for l in [4,5,6]for u in [9,10,11]],"formula":"g=clip((U-Z)/(U-L),0,1); T=H+g*(B-H). Unknown Z disables promotion (T=H). Z and ATR unchanged.","reason":"5 and10 chosen after reading January15 cases; every neighbor is posthoc sensitivity, no tuning winner will be selected.","same_six_dates":True,"same_i_buy_pool":True,"K":[20,100],"diagnostics":"20-common-date close outcomes, completeness, medians, mean adverse path; remove largest positive outcome in each selected group only as ex-post concentration sensitivity, never alter original ranking."}
(O/"TAPER_POSTHOC_FREEZE.json").write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+"\n")
rk=pd.read_csv(O/"C_EXTENSION_ALL_RANKS.csv");old=pd.read_csv(O/"SIX_DATE_SELECTED_DESCRIPTIVE_LABELS.csv");cc=pd.read_csv(O/"C_SELECTED_DESCRIPTIVE_LABELS.csv");allold=pd.concat([old,cc],ignore_index=True);lookup={}
for r in allold.to_dict("records"):
 key=(r["day"],r["sid"]);v={k:r[k]for k in ["complete20","end20","mae20","mfe20"]}
 if key in lookup:
  assert all((pd.isna(v[k])and pd.isna(lookup[key][k]))or v[k]==lookup[key][k]for k in v)
 lookup[key]=v
selected=[];rankrows=[]
for day,q0 in rk.groupby("day",sort=True):
 q=q0.copy();h=q.full_H1_percentile.to_numpy();b=q.B_score.to_numpy();z=q.extension_Z.to_numpy();elig=q.eligible_cached_i_buy.to_numpy(dtype=bool)
 for l,u in [(l,u)for l in [4,5,6]for u in [9,10,11]]:
  g=np.where(np.isfinite(z),np.clip((u-z)/(u-l),0,1),0);score=h+g*(b-h);ix=np.flatnonzero(elig&np.isfinite(score));ids=q.sid.to_numpy();ix=ix[np.lexsort((ids[ix],-score[ix]))]
  ranks=pd.Series(np.arange(1,len(ix)+1),index=ix)
  for k in [20,100]:
   for i in ix[:k]:selected.append({"day":day,"sid":ids[i],"L":l,"U":u,"K":k,"rank":int(ranks[i]),"score":float(score[i]),"Z":float(z[i]),"g":float(g[i])})
  if l==5 and u==10:
   f=q[["day","sid","full_H1_percentile","B_score","extension_Z","H1_eligible_rank","B_confirmed_eligible_rank"]].copy();f["taper_score"]=score;f["taper_rank"]=ranks.reindex(f.index).to_numpy() if f.index.min()==0 else np.nan
   # ix positions use fresh range, not grouped original index.
   f["taper_rank"]=pd.Series(np.arange(1,len(ix)+1),index=ids[ix]).reindex(ids).to_numpy();rankrows.append(f)
sel=pd.DataFrame(selected);sel.to_csv(O/"TAPER_SELECTIONS_BEFORE_LABELS.csv",index=False);pd.concat(rankrows).to_csv(O/"TAPER_CENTRAL_ALL_RANKS.csv",index=False)
(O/"TAPER_RANK_FREEZE_RECEIPT.json").write_text(json.dumps({"selection_sha256":hashlib.sha256((O/"TAPER_SELECTIONS_BEFORE_LABELS.csv").read_bytes()).hexdigest(),"all_thresholds_posthoc":True},indent=2)+"\n")
missing=set((r["day"],r["sid"])for r in selected)-set(lookup)
for day,sid in sorted(missing):
 f=pq.read_table(root/"artifacts"/(sid+".parquet"),columns=["day","price__close"]).to_pandas().set_index("day");t=f.index.get_loc(pd.Timestamp(day));c=f["price__close"].iloc[t];fu=f["price__close"].iloc[t+1:t+21].to_numpy();ok=len(fu)==20 and np.isfinite(fu).all()and(fu>0).all();lookup[(day,sid)]={"complete20":bool(ok),"end20":fu[-1]/c-1 if ok else np.nan,"mae20":min(0,np.min(fu/c-1))if ok else np.nan,"mfe20":max(0,np.max(fu/c-1))if ok else np.nan}
out=pd.DataFrame([{**r,**lookup[(r["day"],r["sid"])]}for r in selected]);out.to_csv(O/"TAPER_SELECTED_LABELS.csv",index=False)
summary=[]
for key,q in out.groupby(["day","L","U","K"],sort=True):
 day,l,u,k=key;v=q[q.complete20];h=old[(old.day==day)&(old.K==k)&(old.strategy=="H1")];bb=old[(old.day==day)&(old.K==k)&(old.strategy=="B_confirmed")];hvalid=h[h.complete20];largest=v.end20.max();hmax=hvalid.end20.max()
 summary.append({"day":day,"L":l,"U":u,"K":k,"N":len(q),"complete20":len(v),"mean_end20":v.end20.mean(),"median_end20":v.end20.median(),"positive_fraction":v.end20.gt(0).mean(),"mean_mae20":v.mae20.mean(),"H1_mean_end20":hvalid.end20.mean(),"delta_vs_H1_mean":v.end20.mean()-hvalid.end20.mean(),"mean_without_best1":(v.end20.sum()-largest)/(len(v)-1),"H1_mean_without_best1":(hvalid.end20.sum()-hmax)/(len(hvalid)-1),"largest_end20":largest,"best1_share_positive_sum":largest/v.end20.clip(lower=0).sum()if v.end20.clip(lower=0).sum()>0 else np.nan,"overlap_H1":len(set(q.sid)&set(h.sid)),"overlap_B":len(set(q.sid)&set(bb.sid))})
s=pd.DataFrame(summary);s.to_csv(O/"TAPER_NINE_PARAMETER_SENSITIVITY.csv",index=False)
central=s[(s.L==5)&(s.U==10)];central.to_csv(O/"TAPER_CENTRAL_SUMMARY.csv",index=False)
changed=pd.read_csv(O/"JAN15_CHANGED_WITH_C_AND_ATR.csv");j=pd.concat(rankrows);j=j[j.day=="2026-01-15"].set_index("sid");changed=changed.join(j[["taper_score","taper_rank"]],on="sid");changed.to_csv(O/"JAN15_CHANGED_WITH_TAPER.csv",index=False)
print("CENTRAL");print(central.to_string(index=False));print("JAN_CASES");print(changed[["sid","current_name","change","H1_eligible_rank","B_eligible_rank","taper_rank","extension_Z","end20"]].to_string(index=False));print("SENSITIVITY_RANGE");print(s.groupby(["day","K"]).agg(delta_min=("delta_vs_H1_mean","min"),delta_max=("delta_vs_H1_mean","max"),overlap_min=("overlap_H1","min"),overlap_max=("overlap_H1","max")).to_string());print("NEW_LABELS_READ",len(missing))

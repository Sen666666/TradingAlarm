
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math
E=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality")
M=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv")
master=pd.read_csv(M);assert master.symbol.is_unique
mapper=master.set_index("symbol").industry_name
sources={"2022-01-24":E/"full_local_signal_two_dates_v1/2022-01-24","2024-09-24":E/"pvr_924_discrimination_v1","2026-01-15":E/"full_local_signal_two_dates_v1/2026-01-15"}
allout={}
scalar_features=pd.read_parquet(E/"local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet")
input_paths=[M,E/"local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet"]
for source_day,source_base in sources.items():
 input_paths += [source_base/"FROZEN_RANKS_WITH_PRICE_LABELS.parquet",source_base/"paths/LONG_PATHS.parquet",source_base/"GROUP_SUMMARIES.csv",source_base/"PRIOR_RANKS_RECEIPT.json",source_base/("FROZEN2313_PRIOR_RANKS.parquet" if source_day=="2024-09-24" else "FROZEN_IBUY_PRIOR_RANKS.parquet")]
input_hash_before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}

for day,b in sources.items():
 f=pd.read_parquet(b/"FROZEN_RANKS_WITH_PRICE_LABELS.parquet")
 paths=pd.read_parquet(b/"paths/LONG_PATHS.parquet")
 priorpath=b/("FROZEN2313_PRIOR_RANKS.parquet"if day=="2024-09-24"else"FROZEN_IBUY_PRIOR_RANKS.parquet")
 prior=pd.read_parquet(priorpath)
 receipt=json.loads((b/"PRIOR_RANKS_RECEIPT.json").read_text())
 assert hashlib.sha256(priorpath.read_bytes()).hexdigest()==receipt["prior_rank_sha256"]
 assert f.sid.is_unique and prior.sid.is_unique
 ranked=f[f.rank_ALL_LOCAL_I_BUY.notna()].sort_values("rank_ALL_LOCAL_I_BUY")
 assert ranked.sid.tolist()==ranked.sort_values(["score","sid"],ascending=[False,True]).sid.tolist()
 assert ranked.rank_ALL_LOCAL_I_BUY.tolist()==list(range(1,len(ranked)+1))
 maxerr=0
 pgrp={sid:g.sort_values("future_observation") for sid,g in paths.groupby("sid")}
 for _,r in f.iterrows():
  g=pgrp[r.sid];assert g.future_observation.tolist()==list(range(1,21))
  assert (g.observation_date>day).all()
  ret=g.close.to_numpy()/r.anchor_close-1
  maxerr=max(maxerr,float(np.max(np.abs(ret-g.close_change_from_anchor.to_numpy()))))
  for h in [5,20]:
   z=ret[:h]
   for col,v in [(f"h{h}_return",z[-1]),(f"h{h}_max_up",max(0,z.max())),(f"h{h}_max_adverse",min(0,z.min()))]:
    maxerr=max(maxerr,abs(float(r[col])-float(v)))
   assert r[f"h{h}_nth_date"]==g.iloc[h-1].observation_date
 assert maxerr<1e-12
 # Independent group memberships and all numerical main summaries.
 stored=pd.read_csv(b/"GROUP_SUMMARIES.csv")
 fields={"terminal_mean":lambda g,h:g[f"h{h}_return"].mean(),"terminal_median":lambda g,h:g[f"h{h}_return"].median(),"MFE_mean":lambda g,h:g[f"h{h}_max_up"].mean(),"MAE_signed_mean":lambda g,h:g[f"h{h}_max_adverse"].mean()}
 gs={"ALL":("rank_ALL_LOCAL_I_BUY","decile_ALL"),"OLD":("rank_OLD1709_STATIC_REFERENCE_I_BUY","decile_OLD"),"OUTSIDE":("rank_OUTSIDE_OLD1709_I_BUY","decile_OUTSIDE")}
 checked=0;maxgroup=0
 for _,rr in stored.iterrows():
  h=int(rr.horizon);scope=rr.scope;band=rr.band
  if rr.view=="WITHIN_SCOPE_RANKS":
   g=f if scope=="ALL"else f[f.in_old1709_exact.eq(scope=="OLD")]
   rc,dc=gs[scope]
  else:
   g=f[f.in_old1709_exact.eq(scope=="OLD")];rc,dc=gs["ALL"]
  if band=="RANKABLE":g=g[g[rc].notna()]
  elif band=="PVR_UNKNOWN":g=g[g[rc].isna()]
  elif band.startswith("TOP"):g=g[g[rc].le(int(band[3:]))]
  elif band.startswith("REST"):g=g[g[rc].gt(int(band[4:]))]
  elif band.startswith("D"):g=g[g[dc].eq(int(band[1:]))]
  else:assert band=="ALL"
  assert len(g)==int(rr.prior_N) and int(g[f"h{h}_complete"].sum())==int(rr.complete_N)
  g=g[g[f"h{h}_complete"]]
  for k,fn in fields.items():
   v=float(fn(g,h));saved=float(rr[k])
   if np.isnan(v):assert np.isnan(saved)
   else:maxgroup=max(maxgroup,abs(v-saved))
  checked+=1
 assert maxgroup<1e-12
 f["industry_current20261022"]=f.sid.map(mapper)
 ranked=f[f.rank_ALL_LOCAL_I_BUY.notna()].sort_values("rank_ALL_LOCAL_I_BUY")
 cases=[]
 for h in [5,20]:
  for k in [20,100]:
   top=ranked.iloc[:k];rest=ranked.iloc[k:];tr=top[f"h{h}_return"];rr=rest[f"h{h}_return"]
   topids=set(top.sid);restids=set(rest.sid)
   assert not topids&restids and topids|restids==set(ranked.sid)
   expected=json.loads((b/"paths/COVERAGE_METADATA.json").read_text()).get("common_endpoint_dates",{}).get(str(h), {5:"2024-10-08",20:"2024-10-29"}[h])
   a=top[top[f"h{h}_nth_date"]==expected];c=rest[rest[f"h{h}_nth_date"]==expected]
   loss=(-tr).clip(lower=0);positive=tr.clip(lower=0)
   jack=(tr.sum()-tr)/(len(tr)-1)
   cases.append(dict(h=h,k=k,topN=len(top),restN=len(rest),top_frac_rankable=len(top)/len(ranked),mean_top_pct=100*tr.mean(),mean_rest_pct=100*rr.mean(),mean_gap_pp=100*(tr.mean()-rr.mean()),median_top_pct=100*tr.median(),median_rest_pct=100*rr.median(),negative_top=int((tr<0).sum()),positive_top=int((tr>0).sum()),positive_rest=int((rr>0).sum()),top_leave_one_mean_min_pct=100*jack.min(),top_leave_one_mean_max_pct=100*jack.max(),best_leave_one_gap_pp=100*(jack.max()-rr.mean()),largest1_loss_mass_share=float(loss.max()/loss.sum())if loss.sum()else None,largest5_loss_mass_share=float(loss.nlargest(5).sum()/loss.sum())if loss.sum()else None,largest1_positive_mass_share=float(positive.max()/positive.sum())if positive.sum()else None,top_without_largest1_pct=100*tr.nsmallest(len(tr)-1).mean(),common_endpoint=expected,aligned_topN=len(a),aligned_restN=len(c),aligned_top_pct=100*a[f"h{h}_return"].mean(),aligned_rest_pct=100*c[f"h{h}_return"].mean(),aligned_gap_pp=100*(a[f"h{h}_return"].mean()-c[f"h{h}_return"].mean())))
 top=ranked.head(20);rest=ranked.iloc[20:];sectorrows=[];weighted_rest=0;covered=0
 for ind,g in top.groupby("industry_current20261022",dropna=False):
  rr=rest[rest.industry_current20261022.eq(ind)] if pd.notna(ind)else rest.iloc[:0]
  sectorrows.append(dict(industry=ind if pd.notna(ind)else"UNKNOWN",topN=len(g),top_mean20_pct=100*g.h20_return.mean(),rest_same_industry_N=len(rr),rest_same_industry_mean20_pct=100*rr.h20_return.mean(),top20_total_mean_contribution_pp=100*g.h20_return.sum()/20))
  if len(rr)and pd.notna(ind):weighted_rest+=len(g)/20*rr.h20_return.mean();covered+=len(g)
 out=dict(day=day,full_i_buy=len(f),rankable=len(ranked),rank_unknown=len(f)-len(ranked),prior_sha_verified=True,path_rows=len(paths),max_path_abs_error=maxerr,groups_rebuilt=checked,max_group_numeric_error=maxgroup,industry_map_unknown_total=int(f.industry_current20261022.isna().sum()),industry_map_unknown_top20=int(top.industry_current20261022.isna().sum()),score_h20_spearman_descriptive=float(ranked.score.rank().corr(ranked.h20_return.rank())),comparisons=cases,top20_sector_mix=sectorrows,sector_standardized_rest20_pct=100*weighted_rest if covered==20 else None,sector_standardized_gap_pp=100*(top.h20_return.mean()-weighted_rest)if covered==20 else None,sector_standardization_top_covered=covered,unknown_PVR_rows=f[f.rank_ALL_LOCAL_I_BUY.isna()][["sid","current_name","h5_return","h20_return"]].to_dict("records"),delayed_rows=f[f.h20_source_union_missing_row_proxy.gt(0)][["sid","current_name","rank_ALL_LOCAL_I_BUY","h20_nth_date","h20_return"]].to_dict("records"))
 z=scalar_features[scalar_features.day.eq(day)]
 assert len(z)==5517
 known=z[np.isfinite(z.score)]
 scalar_errors={"u":float(np.max(np.abs(known.u-np.tanh(known.r/known.scale)))),"b":float(np.max(np.abs(known.b-np.tanh(np.log(known.current_amount_passthrough/known.amount_ref))))),"e":float(np.max(np.abs(known.e-known.u*(1+.5*abs(known.u)*known.b)))),"score":float(np.max(np.abs(known.score-(50+50*np.tanh(2*known.E)))))}
 joined=f.merge(z[["sid","score"]],on="sid",suffixes=("_saved","_feature"),validate="one_to_one")
 score_error=float(np.nanmax(abs(joined.score_saved-joined.score_feature)))
 assert max(scalar_errors.values())==0 and score_error==0
 out["scalar_PVR_errors"]=scalar_errors
 out["frozen_vs_feature_score_max_error"]=score_error
 out["global20_by_static_membership"]=[]
 for old in [True,False]:
  aa=f[f.rank_ALL_LOCAL_I_BUY.le(20)&f.in_old1709_exact.eq(old)]
  bb=f[f.rank_ALL_LOCAL_I_BUY.gt(20)&f.in_old1709_exact.eq(old)]
  out["global20_by_static_membership"].append(dict(in_old1709=old,topN=len(aa),restN=len(bb),mean_top_pct=100*aa.h20_return.mean(),mean_rest_pct=100*bb.h20_return.mean(),gap_pp=100*(aa.h20_return.mean()-bb.h20_return.mean())))
 unknown_inclusive_rest=f[f.rank_ALL_LOCAL_I_BUY.gt(20).fillna(False)|f.rank_ALL_LOCAL_I_BUY.isna()]
 out["unknown_inclusive_rest_sensitivity"]={"N":len(unknown_inclusive_rest),"h20_mean_pct":100*unknown_inclusive_rest.h20_return.mean(),"not_original_group":True}
 out["top20_source_rows"]=top[["sid","current_name","rank_ALL_LOCAL_I_BUY","score","in_old1709_exact","industry_current20261022","anchor_close","h5_nth_date","h20_nth_date","h5_return","h20_return","h20_max_up","h20_max_adverse"]].to_dict("records")
 out["source_directory"]=str(b)
 allout[day]=out

input_hash_after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
assert input_hash_after==input_hash_before
result={
"scope":"Independent frozen-output and arithmetic audit. No model/account run, optimization, network, or modification of source artifacts.",
"units":"Summary percentage fields are percentages; gaps are percentage points. Raw top20 and unknown/delayed h*_return fields are decimal price changes.",
"input_sha256":input_hash_before,
"input_hash_unchanged_after_audit":True,
"total_path_rows":sum(x["path_rows"] for x in allout.values()),
"total_summary_groups":sum(x["groups_rebuilt"] for x in allout.values()),
"definitions":{
"clock":"h valid future stock observations, NOT a common-market holding period; labels from signal close, not achievable fills.",
"return":"C_h/C_0 - 1; only full h windows. MFE max of zero and anchor-relative future closes, MAE min of zero and same.",
"comparisons":"TOP20 vs REST20 and TOP100 vs REST100 internally disjoint; TOP20 nested in TOP100 so the two comparisons overlap.",
"unknown":"Unknown PVR remains in full i_buy and separate bucket, excluded from ranked TOP/REST.",
"current_industry":"2026-10-22 current static classification is a post-hoc descriptive concentration sensitivity, non-PIT and not a signal.",
"statistics":"Three consumed dates, correlated stocks/sectors, different top-k fractions. No iid p-values or proof of future efficacy.",
"source":"Canonical static local 5517; no harmonized retired archives; qfq reference vintage later than targets. Not historical full-market or tradability proof."
},
"dates":allout}
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 return x
result=clean(result)
import argparse
p=argparse.ArgumentParser();p.add_argument("--output",type=Path);args=p.parse_args()
payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
if args.output:
 assert args.output.resolve() not in [x.resolve() for x in input_paths]
 with args.output.open("x",encoding="utf-8") as h:h.write(payload)
 print(json.dumps({"output":str(args.output),"dates":list(allout),"path_rows":result["total_path_rows"],"summary_groups":result["total_summary_groups"],"source_hashes_unchanged":True}))
else:print(payload)

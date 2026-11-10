import pandas as pd, numpy as np, json, math
from pathlib import Path
B=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1")
manifest={x["symbol"]:x for x in json.loads(Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json").read_text())}

OUT=B/"cp1_signal_mechanism_v1/cp_timing_quality_v1/diagnosis"
fixed=pd.concat([pd.read_csv(B/"cp1_signal_mechanism_v1/FIRST_ENTRY_SIGNAL_FEATURES.csv")[["sid","signal_day"]],pd.read_csv(B/"cp1_signal_mechanism_v1/soft_cp1_quality_v1/SIGNAL_SUMMARY.csv")[["sid","signal_day"]]]).drop_duplicates()
q1=pd.read_csv(B/"cp1_signal_mechanism_v1/ALL_Q1_MOBILE_FIRST_CLOSED_ROUNDS.csv")
assert len(q1)==189 and q1.account.eq("PVR").all() and q1.closed.all()
fixedkeys=set(zip(fixed.sid,fixed.signal_day)); q1keys=set(zip(q1.sid,q1.signal_day))
cases=pd.concat([fixed,q1[["sid","signal_day"]]]).drop_duplicates().sort_values(["sid","signal_day"])
allentries=pd.read_csv(B/"ALL_FIRST_ENTRIES.csv"); allentries=allentries[allentries.account=="PVR"]
assert not allentries[["sid","signal_day"]].duplicated().any()
out=[]; daily=[]; source_checks=[]
for sid,g in cases.groupby("sid"):
 f=pd.read_parquet(manifest[sid]["refs"]["facts"]); cp=pd.read_parquet(manifest[sid]["refs"]["CP1"]); inp=pd.read_parquet(manifest[sid]["refs"]["CP1_input"])
 p=np.log(f.close); r=p.groupby(f.segment_id).diff()
 assert np.nanmax(np.abs(cp.r-r.reindex(cp.index)))<1e-12
 import hashlib
 for kind in ["facts","CP1_input","CP1"]:
  path=manifest[sid]["refs"][kind]; digest=hashlib.sha256(Path(path).read_bytes()).hexdigest(); expected=manifest[sid].get("output_sha256",{}).get(path)
  source_checks.append(dict(sid=sid,kind=kind,path=path,sha256=digest,manifest_sha256=expected,manifest_match=(digest==expected) if expected else None))
 rms={}
 for n in [5,21]:
  rms[n]=(r.pow(2).groupby(f.segment_id).transform(lambda x:x.shift().rolling(n,min_periods=n).mean()).pow(.5))
 origins=[]; origin=None
 for j,(day,c) in enumerate(cp.iterrows()):
  reason=str(c.reset_reason)
  if reason in ["unprepared","E0_invalid"]: origin=None
  elif reason in ["start","lower_anchor","E0_down_reset"]: origin=j
  if np.isfinite(c.scale) and origin is None: raise Exception((sid,day,"missing origin"))
  origins.append(origin)
  if c.receipt: origin=j
 for row in g.itertuples():
  day=pd.Timestamp(row.signal_day); j=cp.index.get_loc(day); c=cp.iloc[j]; k=origins[j]; origin_day=cp.index[k]
  assert abs(c.anchor-np.log(inp.loc[origin_day,"close"]))<1e-10
  assert abs(c.scale-cp.iloc[k].z)<1e-12
  n=j-k; cyc=cp.iloc[k+1:j+1].copy(); threshold=np.sqrt(5)*c.scale
  D=c.displacement; K=c.credit; E=min(D,K)
  def first(mask):
   days=cyc.index[mask.fillna(False)]; return str(days[0].date()) if len(days) else None
  a=allentries[(allentries.sid==sid)&(allentries.signal_day==row.signal_day)].iloc[0]
  fj=f.index.get_loc(day); future=f.iloc[fj+1:fj+6]
  sig5=future.close.iloc[-1]/f.loc[day,"close"]-1 if len(future)==5 else np.nan
  rms5=rms[5].loc[day];rms21=rms[21].loc[day]
  sd21=np.sqrt(max(0,rms21*rms21-(r.loc[:day].iloc[-22:-1].mean())**2))
  Eseq=cyc[["displacement","credit"]].min(axis=1)
  fresh=cyc.delta_frontier.gt(0)
  prior_sigmas={h:rms[h].reindex(cyc.index) for h in [5,21]}
  def future_first(mask):
   dates=future.index[mask];return str(dates[0].date()) if len(dates) else None
  out.append(dict(fixed_case=(sid,row.signal_day) in fixedkeys,q1_actual_mobile=(sid,row.signal_day) in q1keys,actual_closed_day=a.closed_day,actual_round_return=a.round_return_on_cumulative_cost,signal_raw_close=f.loc[day,"raw_close"],first_role_floor=a.first_role_floor,signal5_MAE=future.close.min()/f.loc[day,"close"]-1,signal5_MFE=future.close.max()/f.loc[day,"close"]-1,first5_close_below_initial_role_floor=future_first(future.close.le(a.first_role_floor)),first5_E0_invalid=future_first(inp.e0_valid.reindex(future.index).eq(False)),prior_std21=sd21,E_prior_std21_ratio=E/(np.sqrt(5)*sd21),E_age5_frozen_ratio=E/(np.sqrt(max(5,n))*c.scale),first_E_current63_in_cycle=first(Eseq.ge(np.sqrt(5)*cyc.z)&fresh),first_E_RMS21_in_cycle=first(Eseq.ge(np.sqrt(5)*prior_sigmas[21])&fresh),first_E_RMS5_in_cycle=first(Eseq.ge(np.sqrt(5)*prior_sigmas[5])&fresh),first_E_age5_in_cycle=first(Eseq.ge(np.sqrt(np.maximum(5,np.arange(1,n+1)))*c.scale)&fresh),sid=sid,signal_day=row.signal_day,origin_day=str(origin_day.date()),origin_reason=str(cp.iloc[k].reset_reason),n_returns=n,phase=str(c.phase),round_pnl=a.round_pnl,first_kind=a.first_kind,signal5_return=sig5,entry5_return=a.ret5_forward,frozen_z=c.scale,current_s=c.s,current_z=c.z,prior_rms5=rms5,prior_rms21=rms21,frozen_over_current=c.scale/c.z,rms5_over_frozen=rms5/c.scale,rms21_over_frozen=rms21/c.scale,D=D,K=K,m=c.m,bottleneck="D" if D<=K else "K",D_original_ratio=D/threshold,K_original_ratio=K/threshold,E_original_ratio=E/threshold,original_first_D=first(cyc.displacement.ge(threshold)),original_first_K=first(cyc.credit.ge(threshold)),original_first_both=first(cyc.displacement.ge(threshold)&cyc.credit.ge(threshold)&cyc.delta_frontier.gt(0)),E_current63_ratio=E/(np.sqrt(5)*c.z),E_prior_rms5_ratio=E/(np.sqrt(5)*rms5),E_prior_rms21_ratio=E/(np.sqrt(5)*rms21),E_n_frozen_ratio=E/(np.sqrt(n)*c.scale),E_n_rms21_ratio=E/(np.sqrt(n)*rms21),prior5_abs_max=r.loc[:day].iloc[-6:-1].abs().max(),signal_r=c.r,prior21_logreturn=r.loc[:day].iloc[-22:-1].sum(),prior5_logreturn=r.loc[:day].iloc[-6:-1].sum(),amount_relative=inp.loc[day,"amount"]/c.B))
  for dd,cc in cp.iloc[max(0,k-1):j+6].iterrows() if (sid,row.signal_day) in fixedkeys else []:
   fr=f.loc[dd]; ii=inp.loc[dd]
   daily.append(dict(sid=sid,case_signal=row.signal_day,day=str(dd.date()),offset=cp.index.get_loc(dd)-j,raw_close=fr.raw_close,close=fr.close,r=cc.r,reset_reason=str(cc.reset_reason),receipt=cc.receipt,origin_day=str(cp.index[origins[cp.index.get_loc(dd)]].date()) if origins[cp.index.get_loc(dd)] is not None else None,n_returns=cp.index.get_loc(dd)-origins[cp.index.get_loc(dd)] if origins[cp.index.get_loc(dd)] is not None else None,phase=str(cc.phase),frozen_z=cc.scale,current_s=cc.s,current_z=cc.z,prior_rms5=rms[5].loc[dd],prior_rms21=rms[21].loc[dd],D=cc.displacement,K=cc.credit,delta_frontier=cc.delta_frontier,m=cc.m,e0_valid=ii.e0_valid,e0_down=ii.e0_down,i_buy=fr.i_buy,g_grade=fr.g_grade))
o=pd.DataFrame(out);d=pd.DataFrame(daily)

o["signal5_negative"]=o.signal5_return.lt(0)
o["closed_round_positive"]=o.round_pnl.gt(0)
assert o.original_first_both.eq(o.signal_day).all()
co=o[o.q1_actual_mobile].copy()
cohort=[]
for name,mask in [("all",co.n_returns.ge(0)),("n_gt5",co.n_returns.gt(5)),("n_le5",co.n_returns.le(5)),("RMS21_lt1",co.E_prior_rms21_ratio.lt(1)),("RMS21_ge1",co.E_prior_rms21_ratio.ge(1)),("RMS5_lt1",co.E_prior_rms5_ratio.lt(1)),("RMS5_ge1",co.E_prior_rms5_ratio.ge(1)),("current63_lt1",co.E_current63_ratio.lt(1)),("current63_ge1",co.E_current63_ratio.ge(1)),("age5_lt1",co.E_age5_frozen_ratio.lt(1)),("age5_ge1",co.E_age5_frozen_ratio.ge(1))]:
 x=co[mask];cohort.append(dict(group=name,n=len(x),positive_rounds=int(x.closed_round_positive.sum()),positive_round_fraction=x.closed_round_positive.mean(),signal5_negative_fraction=x.signal5_negative.mean(),median_signal5_return=x.signal5_return.median(),sum_original_pnl=x.round_pnl.sum()))
cstats=pd.DataFrame(cohort)
OUT.mkdir(parents=True,exist_ok=True)
o[o.fixed_case].to_csv(OUT/"FIXED_CASES_TIMING.csv",index=False)
co.to_csv(OUT/"Q1_ACTUAL_MOBILE_TIMING.csv",index=False)
d.to_csv(OUT/"FIXED_CASES_DAILY.csv",index=False)
cstats.to_csv(OUT/"Q1_DESCRIPTIVE_GROUPS.csv",index=False)
pd.DataFrame(source_checks).to_csv(OUT/"SOURCE_HASHES.csv",index=False)
meta=dict(fixed_cases=int(o.fixed_case.sum()),q1_actual_mobile=len(co),unique_targets=len(o),all_original_first_crossings_match=True,all_anchor_and_frozen_scale_checks_pass=True,all_cp_returns_match_facts=True,manifest_hash_matches=int(sum(x["manifest_match"]==True for x in source_checks)),manifest_hash_mismatches=int(sum(x["manifest_match"]==False for x in source_checks)),manifest_hash_missing=int(sum(x["manifest_match"] is None for x in source_checks)),original_model_recalculated=False,new_account_run=False,new_parameter_grid=False,price_coordinate="same source facts.close; raw_close only for display",RMS_windows="strictly prior 5 / 21 observed log returns, signal return excluded; reset by segment_id",n_definition="CP1 observations after true last reset/receipt consumption, anchor observation excluded",scope="Read original caches, new diagnostic features only. All labels are original account results or future source prices, never feature inputs.")
(OUT/"VALIDATION.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print(json.dumps(meta,ensure_ascii=False));print(cstats.round(6).to_string(index=False))
print("N_GT5_WINNER",co[co.n_returns.gt(5)&co.closed_round_positive][["sid","signal_day","n_returns","round_pnl","E_age5_frozen_ratio","signal5_return"]].to_dict("records"))
print("FIXED",o[o.fixed_case][["sid","signal_day","first_E_RMS21_in_cycle","first_E_RMS5_in_cycle","first_E_current63_in_cycle","E_prior_std21_ratio","signal5_MAE","signal5_MFE","first5_close_below_initial_role_floor","first5_E0_invalid","actual_closed_day"]].round(6).to_string(index=False))

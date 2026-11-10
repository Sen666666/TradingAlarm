"""Frozen same-cardinality daily diagnostic; never an account backtest."""
from pathlib import Path
from collections import Counter
import json,hashlib
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;S=O.parents[1]
BASE=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
CSI=Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv")
STRATS=["Q5","P_sameQ","H1_sameQ","L3","T_sameL","H1_sameL","QL5plus3","PT_sameQL","H1_sameQL"]
HASH={}
def bind(p,h=None):
 p=Path(p);z=hashlib.sha256(p.read_bytes()).hexdigest()
 if h is not None:assert z==h,(str(p),"source SHA mismatch")
 HASH[str(p.resolve())]=z;return p
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if v is pd.NA or v is pd.NaT:return None
 if hasattr(v,"item"):return clean(v.item())
 if isinstance(v,float)and not np.isfinite(v):return None
 return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def phase(d):return "DEV_2022_2023"if d<"2024-01-01"else"OOTT_2024"if d<"2025-01-01"else"OOTT_2025_2026H1"
def main():
 bind(__file__);bind(O/"FROZEN_COMPARISON_PROTOCOL.txt");bind(O/"FROZEN_EVENT_PROTOCOL.txt")
 f=pd.read_parquet(bind(O/"ALL90_FULL_PERIOD.parquet"))
 oldcols=["date","sector_id_static","P_score","P_score_exact","P_order","T_score","T_score_exact","T_order","P_mature","UNION_selected","v3_H1_cache_same_date_score","v3_native_H1_order"]
 old=pd.read_parquet(bind(S/"separated_momentum_v4/ranking/STUDY_STATES_2022_2026.parquet"),columns=oldcols)
 f=f.merge(old,on=["date","sector_id_static"],validate="one_to_one")
 f["C_known"]=f[["Q","L","P_score","T_score","v3_H1_cache_same_date_score"]].notna().all(axis=1)
 for s in STRATS:f[s]=False
 cards=[]
 for day,g in f.groupby("date",sort=True):
  known=g[g.C_known];q=known[known.Q>1e-15].sort_values(["Q","sector_id_static"],ascending=[False,True]);l=known[known.L>1e-15].sort_values(["L","sector_id_static"],ascending=[False,True])
  pp=known.sort_values("P_order");tt=known.sort_values("T_order");hh=known.sort_values("v3_native_H1_order")
  qi=q.head(5).index.tolist();li=l.head(3).index.tolist();la=l[~l.index.isin(qi)].head(3).index.tolist();pi=pp.head(len(qi)).index.tolist()
  lists={"Q5":qi,"P_sameQ":pi,"H1_sameQ":hh.head(len(qi)).index.tolist(),"L3":li,"T_sameL":tt.head(len(li)).index.tolist(),"H1_sameL":hh.head(len(li)).index.tolist(),"QL5plus3":qi+la,"PT_sameQL":pi+tt[~tt.index.isin(pi)].head(len(la)).index.tolist(),"H1_sameQL":hh.head(len(qi)+len(la)).index.tolist()}
  for s,idx in lists.items():f.loc[idx,s]=True
  assert len(lists["Q5"])==len(lists["P_sameQ"])==len(lists["H1_sameQ"])
  assert len(lists["L3"])==len(lists["T_sameL"])==len(lists["H1_sameL"])
  assert len(lists["QL5plus3"])==len(lists["PT_sameQL"])==len(lists["H1_sameQL"])
  cards.append(dict(date=day,phase=phase(day),C_N=len(known),Q_positive_N=len(q),L_positive_N=len(l),N_Q=len(qi),N_L=len(li),N_L_added_union=len(la),N_union=len(qi)+len(la),Q_cutoff_tie_total=int((q.Q==q.loc[qi[-1],"Q"]).sum())if qi else 0,L_cutoff_tie_total=int((l.L==l.loc[li[-1],"L"]).sum())if li else 0,old_P_mature_count=int(g.P_mature.eq(True).sum()),old_state_union_count=int(g.UNION_selected.eq(True).sum())))
 f["phase"]=f.date.map(phase)
 # Freeze signal and selection before any future label file is loaded.
 f.to_parquet(O/"SELECTIONS_FROZEN_BEFORE_LABELS.parquet",index=False)
 frozenhash=hashlib.sha256((O/"SELECTIONS_FROZEN_BEFORE_LABELS.parquet").read_bytes()).hexdigest()
 save("SIGNAL_FREEZE_BEFORE_LABEL_READ.json",dict(rows=len(f),sha256=frozenhash,zero_score_not_selected=True,selection_used_future_labels=False,common_known_counts=f.groupby("date").C_known.sum().value_counts().to_dict()))
 pd.DataFrame(cards).to_csv(O/"DAILY_CARDINALITY.csv",index=False)
 print("SIGNAL_FROZEN",frozenhash,flush=True)
 labels=pd.read_parquet(bind(S/"industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.parquet"))
 tail=pd.read_parquet(bind(S/"separated_momentum_v4/evaluation/ALL90_FUTURE_TAIL_EVALUATION_ONLY.parquet"))
 f=f.merge(labels,on=["date","sector_id_static"],validate="one_to_one").merge(tail,on=["date","sector_id_static"],validate="one_to_one")
 bounds=f.groupby("phase").date.agg(["min","max"]).to_dict("index")
 f["eval20_complete_within_phase"]=f.label_valid20&f.label_end20.le(f.phase.map({p:v["max"]for p,v in bounds.items()}))
 f["evaluation_censor"]=np.where(~f.label_valid20,"SOURCE_"+f.label_status20,np.where(~f.eval20_complete_within_phase,"ADMIN_CROSS_PHASE_END","NONE"))
 metrics=["final20_rel_log","final20_abs_log","mfe20_rel_log","mfe20_abs_log","mae20_rel_log","mae20_abs_log"]
 for k in metrics:f[k.replace("_log","_ratio_pct")]=100*np.expm1(f[k])
 # Verify the saved future tail definition is same-day, not pooled across time.
 for day,g in f.groupby("date",sort=True):
  for v,p,flag in [("mfe20_rel_log","REL_MFE20_PRIMARY_midpercentile","REL_MFE20_PRIMARY_tail"),("final20_rel_log","REL_FINAL20_DIAGNOSTIC_midpercentile","REL_FINAL20_DIAGNOSTIC_tail")]:
   known=g[v].notna()&g.label_valid20
   pct=(g.loc[known,v].rank(method="average")-.5)/int(known.sum())
   assert np.allclose(pct,g.loc[known,p],atol=1e-15,rtol=0)
   assert ((pct>=.9)&g.loc[known,v].gt(0)).equals(g.loc[known,flag].astype(bool))
 rows=[]
 for ph,g in f.groupby("phase"):
  e=g[g.eval20_complete_within_phase];targets=int(e.REL_MFE20_PRIMARY_tail.sum());finaltargets=int(e.REL_FINAL20_DIAGNOSTIC_tail.sum())
  for s in STRATS:
   chosen=g[g[s]];z=e[e[s]];nd=len(z)
   rec=dict(phase=ph,strategy=s,signal_days=g.date.nunique(),eval_days=e.date.nunique(),candidate_industry_days=len(chosen),eval_candidate_industry_days=nd,administratively_censored_candidate_rows=int((chosen.evaluation_censor=="ADMIN_CROSS_PHASE_END").sum()),source_missing_candidate_rows=int((~chosen.label_valid20).sum()),empty_signal_days=int(g.date.nunique()-chosen.date.nunique()),empty_eval_days=int(e.date.nunique()-z.date.nunique()),signal_universe_rows=len(g),mean_daily_selected=len(chosen)/g.date.nunique(),future_relMFE_tail_total=targets,future_relMFE_tail_selected=int(z.REL_MFE20_PRIMARY_tail.sum()),future_relMFE_coverage=float(z.REL_MFE20_PRIMARY_tail.sum()/targets)if targets else np.nan,future_relMFE_precision=float(z.REL_MFE20_PRIMARY_tail.mean())if nd else np.nan,future_relFINAL_tail_total=finaltargets,future_relFINAL_tail_selected=int(z.REL_FINAL20_DIAGNOSTIC_tail.sum()),future_relFINAL_coverage=float(z.REL_FINAL20_DIAGNOSTIC_tail.sum()/finaltargets)if finaltargets else np.nan,negative_final_relative_fraction=float(z.final20_rel_log.lt(0).mean())if nd else np.nan,selected_distinct_industries=z.sector_id_static.nunique())
   for raw in metrics:
    k=raw.replace("_log","_ratio_pct")
    rec["daily_mean_"+k]=z.groupby("date")[k].mean().mean()
    rec["pooled_median_"+k]=z[k].median()
   rec["pooled_p10_mae20_abs_ratio_pct"]=z.mae20_abs_ratio_pct.quantile(.10)
   rows.append(rec)
 summary=pd.DataFrame(rows);summary.to_csv(O/"PERIOD_QUALITY_AND_COVERAGE.csv",index=False)
 # Weekly set changes use all signal days, never future labels.
 weeks=[];dailysets={(s,d):set(g.loc[g[s],"sector_id_static"])for d,g in f.groupby("date")for s in STRATS}
 full_calendar=pd.read_csv(bind(CSI),parse_dates=["date"]).date.dt.strftime("%Y-%m-%d").tolist()
 true_week_closes={}
 for d in full_calendar:
  iso=pd.Timestamp(d).isocalendar();true_week_closes[(iso.year,iso.week)]=d
 weekly_boundary_audit=[]
 for ph,g in f.groupby("phase"):
  days=sorted(g.date.unique());dayset=set(days)
  snaps=sorted(d for d in true_week_closes.values()if d in dayset)
  within_period_closes={}
  for d in days:
   iso=pd.Timestamp(d).isocalendar();within_period_closes[(iso.year,iso.week)]=d
  weekly_boundary_audit.append(dict(phase=ph,true_weekly_snapshots=len(snaps),removed_incomplete_week_dates=sorted(set(within_period_closes.values())-set(snaps))))
  for s in STRATS:
   for a,b in zip(snaps,snaps[1:]):
    sa,sb=dailysets[(s,a)],dailysets[(s,b)];union=sa|sb;inter=sa&sb
    weeks.append(dict(phase=ph,strategy=s,previous_week_close=a,current_week_close=b,previous_N=len(sa),current_N=len(sb),added=len(sb-sa),removed=len(sa-sb),intersection_N=len(inter),union_N=len(union),jaccard_similarity=len(inter)/len(union)if union else np.nan,both_empty=not union,entry_fraction_of_current=len(sb-sa)/len(sb)if sb else np.nan))
 save("WEEKLY_BOUNDARY_AUDIT.json",weekly_boundary_audit)
 wf=pd.DataFrame(weeks);wf.to_csv(O/"WEEKLY_SET_CHANGES.csv",index=False)
 ws=wf.groupby(["phase","strategy"]).agg(weekly_comparisons=("added","size"),mean_added=("added","mean"),mean_removed=("removed","mean"),mean_jaccard_similarity=("jaccard_similarity","mean"),both_empty_weeks=("both_empty","sum"),mean_entry_fraction_of_current=("entry_fraction_of_current","mean")).reset_index();ws.to_csv(O/"WEEKLY_CHANGE_SUMMARY.csv",index=False)
 # Prefix-known original low-confirmation events, preserved without hindsight filtering.
 im=json.loads(bind(BASE/"INDUSTRY_MANIFEST.json").read_text());events=[]
 globaldays=sorted(f.date.unique());pos={d:i for i,d in enumerate(globaldays)};phase_days={ph:sorted(g.date.unique())for ph,g in f.groupby("phase")};phasepos={ph:{d:i for i,d in enumerate(ds)}for ph,ds in phase_days.items()}
 calendar=pd.read_csv(bind(CSI),parse_dates=["date"]).date.dt.strftime("%Y-%m-%d").tolist();calpos={d:i for i,d in enumerate(calendar)}
 fidx=f.set_index(["date","sector_id_static"])
 for item in im:
  paths=[p for p in item["source_sha256"]if p.endswith("/events.parquet")];assert len(paths)==1
  ef=pd.read_parquet(bind(paths[0],item["source_sha256"][paths[0]]));ef.index=pd.DatetimeIndex(ef.index).as_unit("ns")
  for dt,r in ef.loc[(ef.index>=globaldays[0])&(ef.index<=globaldays[-1])&ef.event.eq(1)].iterrows():
   day=str(dt.date());sec=item["series"];a=pos[day];ph=phase(day);pp=phasepos[ph][day];phasecount=len(phase_days[ph])
   prefix_window_complete=pp>=5 and pp+20<phasecount
   old=fidx.loc[(day,sec)]
   base=dict(anchor_date=day,sector_id_static=sec,industry=old.industry,phase=ph,event=1,target=float(r.target),entered=bool(r.entered==1),confirmed_pivot_date=str(pd.Timestamp(r.confirmed_pivot_date).date())if pd.notna(r.confirmed_pivot_date)else None,segment_id=int(r.segment_id),phase_session_position=pp,sector_date_block=f"{sec}:{ph}:{pp//20}",complete_discovery_window=prefix_window_complete,left_phase_boundary_censored=pp<5,right_phase_boundary_censored=pp+20>=phasecount,eval20_complete_within_phase=bool(old.eval20_complete_within_phase),strong_relMFE_evaluation_only=bool(old.REL_MFE20_PRIMARY_tail),future_rel20_log=float(old.final20_rel_log),future_relMFE20_log=float(old.mfe20_rel_log),future_absMAE20_log=float(old.mae20_abs_log))
   for s in STRATS:
    rec=dict(base,strategy=s,at_anchor_selected=sec in dailysets[(s,day)])
    offsets=list(range(max(-5,-a),min(20,len(globaldays)-a-1)+1))
    found=[off for off in offsets if sec in dailysets[(s,globaldays[a+off])]]
    first=found[0]if found else None
    carry=bool(first==-5)
    observed_day=globaldays[a+first]if first is not None else None
    rec.update(first_observed_offset=first,left_censored_carry_at_minus5=carry,first_exact_entry_offset=None if carry else first,found_by_anchor=any(x<=0 for x in found),found_by_plus5=any(x<=5 for x in found),found_by_plus20=bool(found),first_observed_close_date=observed_day,next_possible_session_after_first_observed_close=calendar[calpos[observed_day]+1]if observed_day else None,no_hit_within_window=not found,discovery_window_start=globaldays[max(0,a-5)],discovery_window_end=globaldays[min(a+20,len(globaldays)-1)])
    events.append(rec)
 ev=pd.DataFrame(events);assert len(ev)==3911*len(STRATS);ev.to_csv(O/"ALL_E0_CONFIRMATION_DISCOVERY.csv",index=False)
 es=[]
 for (ph,s),g in ev.groupby(["phase","strategy"]):
  for subset in ["ALL_CAUSAL_CONFIRMATIONS","FUTURE_TOP_DECILE_REL_MFE_EVALUATION_ONLY"]:
   z=g if subset=="ALL_CAUSAL_CONFIRMATIONS"else g[g.strong_relMFE_evaluation_only]
   eligible=z[z.complete_discovery_window&z.eval20_complete_within_phase]
   exact=eligible[eligible.first_exact_entry_offset.notna()]
   blocks=eligible.groupby("sector_date_block").size()
   es.append(dict(phase=ph,strategy=s,subset=subset,all_events=len(z),eligible_complete_events=len(eligible),left_boundary_censored_events=int(z.left_phase_boundary_censored.sum()),right_boundary_censored_events=int(z.right_phase_boundary_censored.sum()),admin_label_censored_events=int((~z.eval20_complete_within_phase).sum()),at_anchor_count=int(eligible.at_anchor_selected.sum()),found_by_anchor_count=int(eligible.found_by_anchor.sum()),found_by_plus5_count=int(eligible.found_by_plus5.sum()),found_by_plus20_count=int(eligible.found_by_plus20.sum()),no_hit_count=int(eligible.no_hit_within_window.sum()),left_carry_count=int(eligible.left_censored_carry_at_minus5.sum()),at_anchor_rate=eligible.at_anchor_selected.mean(),found_by_anchor_rate=eligible.found_by_anchor.mean(),found_by_plus5_rate=eligible.found_by_plus5.mean(),found_by_plus20_rate=eligible.found_by_plus20.mean(),conditional_exact_entry_median_offset=exact.first_exact_entry_offset.median(),exact_entry_count=len(exact),sector_20session_blocks=len(blocks),max_events_in_sector_block=blocks.max()if len(blocks)else 0,blocks_with_multiple_events=int((blocks>1).sum())))
 es=pd.DataFrame(es);es.to_csv(O/"FIRST_DISCOVERY_SUMMARY.csv",index=False)
 f.to_parquet(O/"EVALUATION_PANEL.parquet",index=False)
 save("COMPARISON_AUDIT.json",dict(rows=len(f),days=len(globaldays),phases=bounds,common_C_counts=f.groupby("date").C_known.sum().value_counts().to_dict(),label_source_status_counts=f.label_status20.value_counts().to_dict(),evaluation_censor_rows=f.evaluation_censor.value_counts().to_dict(),event_rows=len(ev),unique_causal_events=len(ev)//len(STRATS),same_day_tail_identity_verified=True,signal_file_hash_unchanged=hashlib.sha256((O/"SELECTIONS_FROZEN_BEFORE_LABELS.parquet").read_bytes()).hexdigest()==frozenhash,all_same_cardinality=True,no_accounts=True,no_parameter_tuning=True,chronological_diagnostic_not_blind_OOS=True))
 save("SOURCE_SHA256_EVALUATION.json",HASH)
 print("QUALITY\n"+summary[["phase","strategy","eval_candidate_industry_days","empty_signal_days","daily_mean_final20_rel_ratio_pct","daily_mean_mfe20_abs_ratio_pct","daily_mean_mae20_abs_ratio_pct","future_relMFE_coverage","future_relMFE_precision","negative_final_relative_fraction"]].to_string(index=False),flush=True)
 print("CHURN\n"+ws.to_string(index=False),flush=True)
 print("STRONG_EVENT_DISCOVERY\n"+es[es.subset=="FUTURE_TOP_DECILE_REL_MFE_EVALUATION_ONLY"][["phase","strategy","all_events","eligible_complete_events","found_by_anchor_rate","found_by_plus5_rate","found_by_plus20_rate","left_carry_count","conditional_exact_entry_median_offset","no_hit_count"]].to_string(index=False),flush=True)
 print("DONE",flush=True)
if __name__=="__main__":main()

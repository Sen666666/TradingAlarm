from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1");O=R/"distribution_objective_feasibility_v1"
z=pd.read_parquet(O/"LABEL_ASOF_ROWS.parquet")
HFILE=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
cal=pd.DatetimeIndex(np.load(HFILE,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
source_paths=[O/"LABEL_ASOF_ROWS.parquet",O/"LABEL_QA.json",O/"MARKED_RETURN_DESIGN.md",HFILE]+[R/f"independent_channel_joint_economic_v1/economic_{w}/joint/ACTIONS.csv" for w in ["2022","2024"]]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source_hashes={str(p):sha(p) for p in source_paths}
actions=[]
for w in ["2022","2024"]:
 a=pd.read_csv(R/f"independent_channel_joint_economic_v1/economic_{w}/joint/ACTIONS.csv",float_precision="round_trip");a=a[a.round_id.isin(z.round_id.unique())];a["day"]=pd.to_datetime(a.day);actions.append(a)
a=pd.concat(actions,ignore_index=True)
cuts=pd.to_datetime(["2022-07-01","2024-09-02","2024-10-08","2024-11-01","2024-12-02"])
cats=["Y_le_minus1","Y_minus1_to_0","Y_0_to_1","Y_1_to_3","Y_gt_3","FROZEN_UNKNOWN","EXITED_MARK_PENDING"]
observations=[];hazards=[];horizons=[];cohorts=[]
for cut in cuts:
 p=z[z.cut.eq(cut)&z.in_504_signal_window].copy()
 ap=a[a.day.lt(cut)&a.round_id.isin(p.round_id)]
 buy=ap[ap.side.eq("buy_core")].set_index("round_id").day
 sell=ap[ap.side.eq("sell_all")].set_index("round_id").day
 assert buy.index.is_unique and sell.index.is_unique
 ap=ap.copy();ap["dq"]=np.where(ap.side.str.startswith("buy"),ap.q,-ap.q)
 pq=ap.groupby("round_id").dq.sum()
 assert pq.reindex(sell.index).eq(0).all()
 assert pq.loc[~pq.index.isin(sell.index)].gt(0).all()
 p=p[p.round_id.isin(buy.index)].copy()
 p["entry_day"]=p.round_id.map(buy)
 p["exit_day"]=p.round_id.map(sell)
 p["entry_t"]=cal.get_indexer(p.entry_day)
 p["observed_end_day"]=cal[cal.get_loc(cut)-1]
 p["age_end"]=cal.get_loc(cut)-p.entry_t
 p["event_type"]="ADMIN_HELD_AT_CUT"
 exited=p.exit_day.notna()
 p.loc[exited,"event_type"]="EXITED_MARK_PENDING"
 p.loc[exited,"observed_end_day"]=p.loc[exited,"exit_day"]
 p.loc[exited,"age_end"]=cal.get_indexer(p.loc[exited,"exit_day"])-p.loc[exited,"entry_t"]+1
 known=p.label_net_cash.notna()
 assert (known<=exited).all()
 p.loc[known,"event_type"]=p.loc[known,"label_bin_fixed3000"].astype(str)
 unknown=p.unknown_known_day.notna()
 assert not (unknown&exited).any()
 p.loc[unknown,"event_type"]="FROZEN_UNKNOWN"
 p.loc[unknown,"observed_end_day"]=p.loc[unknown,"unknown_known_day"]
 p.loc[unknown,"age_end"]=cal.get_indexer(p.loc[unknown,"unknown_known_day"])-p.loc[unknown,"entry_t"]+1
 assert p.age_end.ge(1).all()
 assert (p.loc[known,"label_known_at_proxy"]<cut).all()
 assert (p.loc[p.event_type.eq("EXITED_MARK_PENDING"),"state_asof"]=="CLOSED_NONORDINARY_LABEL_CLOCK_UNSUPPORTED").all()
 p["cut_key"]=str(cut.date())
 cols=["cut_key","round_id","sid","window_label","signal_day","entry_day","observed_end_day","age_end","event_type","label_net_cash","label_known_at_proxy"]
 observations.append(p[cols])
 for w,g in p.groupby("window_label"):
  cohorts.append(dict(cut=str(cut.date()),birth_window=w,n=len(g),**g.event_type.value_counts().to_dict()))
 S=1.;F={k:0. for k in cats};rows=[]
 for age in range(1,int(p.age_end.max())+1):
  risk=p[p.age_end.ge(age)];ev=p[p.age_end.eq(age)&~p.event_type.eq("ADMIN_HELD_AT_CUT")];n=len(risk)
  counts={k:int(ev.event_type.eq(k).sum()) for k in cats}
  hs={k:counts[k]/n for k in cats}
  spre=S
  for k in cats:F[k]+=spre*hs[k]
  S*=1-sum(hs.values())
  d=dict(cut=str(cut.date()),age=age,N=n,N_2022=int(risk.window_label.eq("2022").sum()),N_2024=int(risk.window_label.eq("2024").sum()),administrative_censors=int((p.age_end.eq(age)&p.event_type.eq("ADMIN_HELD_AT_CUT")).sum()),S_before=spre,S_after=S,mass_sum=S+sum(F.values()))
  for k in cats:d["d_"+k]=counts[k];d["h_"+k]=hs[k];d["F_"+k]=F[k]
  assert abs(d["mass_sum"]-1)<1e-12 and n>=sum(counts.values())
  rows.append(d)
 hazards.extend(rows)
 for H in [20,60,120,252]:
  support=H<=len(rows);last=rows[min(H,len(rows))-1]
  ev=p[p.age_end.le(H)&~p.event_type.eq("ADMIN_HELD_AT_CUT")]
  known_H=ev[ev.event_type.isin(cats[:5])]
  oc={k:int(ev.event_type.eq(k).sum()) for k in cats}
  held=int(((p.age_end.gt(H))|(p.age_end.eq(H)&p.event_type.eq("ADMIN_HELD_AT_CUT"))).sum())
  admin=int((p.age_end.lt(H)&p.event_type.eq("ADMIN_HELD_AT_CUT")).sum())
  assert sum(oc.values())+held+admin==len(p)
  d=dict(cut=str(cut.date()),H=H,n_entered=len(p),max_observed_age=int(p.age_end.max()),age_H_risk_supported=support,reported_curve_age=min(H,len(rows)),N_at_H=last["N"] if support else 0,N_at_H_2022=last["N_2022"] if support else 0,N_at_H_2024=last["N_2024"] if support else 0,S_H=last["S_after"] if support else np.nan,S_at_reported_age=last["S_after"],known_held_at_H_n=held,admin_cut_before_H_n=admin,closed_only_known_n=len(known_H),closed_only_win_fraction=float(known_H.label_net_cash.gt(0).mean()) if len(known_H) else np.nan)
  for k in cats:
   d["observed_"+k+"_n"]=oc[k];d["observed_"+k+"_mass"]=oc[k]/len(p);d["F_H_"+k]=last["F_"+k] if support else np.nan;d["F_at_reported_age_"+k]=last["F_"+k]
  for name,t in [("minus1",-3000),("zero",0),("plus1",3000),("plus3",9000)]:
   d["closed_only_CDF_"+name]=float(known_H.label_net_cash.le(t).mean()) if len(known_H) else np.nan
  d["known_terminal_mean_Y"]=float(known_H.label_net_cash.mean()/3000) if len(known_H) else np.nan
  d["raw_evidence_mass_sum"]=(sum(oc.values())+held+admin)/len(p)
  d["curve_mass_at_reported_age"]=last["mass_sum"]
  horizons.append(d)
hf=pd.DataFrame(horizons)

df=pd.DataFrame(hazards);ob=pd.concat(observations,ignore_index=True)
assert len(ob)==6221 and not ob.duplicated(["cut_key","round_id"]).any()
assert not ob.loc[~ob.event_type.isin(cats[:5]),"label_net_cash"].notna().any()
assert all(sha(p)==h for p,h in source_hashes.items())
names=["BASELINE_OBSERVED_ROUNDS.parquet","BASELINE_AGE_HAZARDS.csv","BASELINE_HORIZON_DECOMPOSITION.csv","BASELINE_COHORT_EVENT_COUNTS.csv","BASELINE_INPUT_HASHES.json","BASELINE_QA.json"]
assert not any((O/n).exists() for n in names),"REFUSE_OVERWRITE"
ob.to_parquet(O/names[0],index=False);df.to_csv(O/names[1],index=False);hf.to_csv(O/names[2],index=False);pd.DataFrame(cohorts).fillna(0).to_csv(O/names[3],index=False)
(O/names[4]).write_text(json.dumps(source_hashes,ensure_ascii=False,indent=2)+"\n")
qa=dict(status="FIXED_ASOF_EMPIRICAL_OBSERVATION_EVENT_BASELINE_ONLY",new_models_fit=0,economic_runs=0,features_used=0,cut_count=5,horizons=[20,60,120,252],scope="Original admitted PRICE births in last504 signal sessions, confirmed buy_core strictly before cut. No final ordinary/common/feature-known membership filter.",round_weight=1,observed_round_cut_rows=len(ob),unique_original_rounds=ob.round_id.nunique(),age_rows=len(df),categories=cats,unavailable_net_values_blank=True,each_exit_verified_by_saved_sell_all_and_zero_prefix_inventory=True,all_nonexited_prefix_inventory_positive=True,no_cut_day_actions_or_labels_used=True,max_curve_mass_error=float((df.mass_sum-1).abs().max()),raw_evidence_mass_error=float((hf.raw_evidence_mass_sum-1).abs().max()),horizon_curve_out_of_support_count=int((~hf.age_H_risk_supported).sum()),original_inputs_unchanged=True,interpretation="As-of observable held/known marked exit/frozen-quality/exit-mark-pending decomposition. Pending is snapshot label coverage state, not true cause or permanent quality failure. No claim of PIT full terminal return distribution or independent censoring/exchangeability across cohorts. No confidence intervals.",output_hashes={n:sha(O/n) for n in names[:5]})
(O/names[5]).write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n")
assert all(sha(p)==h for p,h in source_hashes.items())
print(json.dumps(qa,ensure_ascii=False,indent=2))
print(hf[["cut","H","N_at_H","N_at_H_2024","S_H","closed_only_known_n","closed_only_win_fraction","admin_cut_before_H_n"]].to_csv(index=False))

import json,hashlib,time
from pathlib import Path
import pandas as pd,numpy as np
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1");O=R/"market_activity_balance_preflight_v1"
members=pd.read_parquet(O/"MEMBER_FEATURES.parquet");src=pd.read_csv(O/"SOURCE_CHECKS.csv");dc=pd.read_csv(O/"DATE_CONTEXT.csv")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
with np.load(H,allow_pickle=False) as z:cal=pd.DatetimeIndex(z["dates"])
dates=pd.DatetimeIndex(pd.to_datetime(dc.day));windows={d:cal[cal.get_loc(d)-21:cal.get_loc(d)+1] for d in dates}
rows=[];blank=[];t=time.monotonic()
for x in src.to_dict("records"):
 if not x["native_available"]:continue
 raw=pd.read_parquet(x["path"],columns=["close","source_kind","source_path"])
 first,last=raw.index.min(),raw.index.max()
 missing=members[(members.sid.eq(x["sid"]))&members.reason.eq("MISSING_COMMON_PRICE_OR_WARMUP")]
 for day in dates:
  q=raw.reindex(windows[day])
  for col in ["source_kind","source_path"]:
   vals=q[col];b=vals.notna()&vals.astype("string").str.strip().eq("").fillna(False)
   if b.any():blank.append(dict(sid=x["sid"],day=day,field=col,blank_dates="|".join(q.index[b].strftime("%Y-%m-%d"))))
 for z in missing.to_dict("records"):
  day=pd.Timestamp(z["day"]);w=windows[day];q=raw.reindex(w)
  why="TARGET_BEFORE_FIRST_SOURCE_OBSERVATION" if day<first else "WINDOW_BEFORE_FIRST_SOURCE_OBSERVATION" if w[0]<first else "TARGET_AFTER_LAST_SOURCE_OBSERVATION" if day>last else "INTERNAL_MISSING_COMMON_PRICE"
  rows.append(dict(sid=x["sid"],day=day,missing_subreason=why,first_source_observation=first,last_source_observation=last,missing_close_rows=int(q.close.isna().sum())))
pd.DataFrame(rows).to_csv(O/"MISSING_PRICE_SUBREASONS.csv",index=False)
pd.DataFrame(blank,columns=["sid","day","field","blank_dates"]).to_csv(O/"EMPTY_SOURCE_FIELD_AUDIT.csv",index=False)
finite=dc[dc.D.notna()]
audit={"all_known_finite_D_inside_bounds":bool(((finite.D>=finite.D_L-1e-14)&(finite.D<=finite.D_U+1e-14)).all()),"finite_dates":len(finite),"empty_direction_dates":dc[dc.D.isna()].day.tolist(),"original_QA_false_explanation":"Original known_inside_outer_bounds boolean included NaN D/interval on all-up 2024-09-30; comparisons false. It is not a finite bound violation. Original QA retained unchanged.","minimum_abs_finite_lower_bound":float(finite.D_L.abs().min()),"minimum_abs_finite_upper_bound":float(finite.D_U.abs().min()),"empty_source_field_windows":len(blank),"missing_subreason_counts":pd.DataFrame(rows).missing_subreason.value_counts().to_dict(),"note":"Before first native observation is not independently proved pre-IPO. No listing or halt reason is inferred from a missing bar. No rule or feature changed.","seconds":time.monotonic()-t}
(O/"COMPLETENESS_QA_SUPPLEMENT.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2))
cs=pd.read_csv(O/"FEATURES_PRELABEL.csv")
sources=[R/"m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv",R/"m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv"]
labels=pd.concat([pd.read_csv(p,low_memory=False).assign(label_source=str(p)) for p in sources]);labels=labels[labels.arm.eq("A_UNION_B")].copy();labels["day"]=pd.to_datetime(labels.signal_day).dt.strftime("%Y-%m-%d");assert not labels.duplicated(["sid","day"]).any()
cols=["sid","day","round_id","PVR_score","evidence_usable_closed","core_net","core_return","net_pnl","net_return_on_buy_cash","label_source"]
joined=cs.merge(labels[cols],on=["sid","day"],how="left",validate="one_to_one")
joined["label_connection"]=np.where(joined.round_id.notna(),"EXACT_EXISTING_AB_IDENTITY","NO_MATCHING_AB_FINANCIAL_LABEL")
joined.to_csv(O/"CASES_WITH_OLD_AB_LABELS.csv",index=False)
lab={"matched_AB":int(joined.round_id.notna().sum()),"financial_closed":int(joined.evidence_usable_closed.eq(True).sum()),"cases":len(joined),"no_matching_AB_label":int(joined.round_id.isna().sum()),"labels_loaded_only_after_feature_seal":True,"not_new_strategy_pnl":True,"label_hashes":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
(O/"LABEL_CONNECTION.json").write_text(json.dumps(lab,ensure_ascii=False,indent=2))
print(json.dumps({"audit":audit,"labels":lab},ensure_ascii=False),flush=True)

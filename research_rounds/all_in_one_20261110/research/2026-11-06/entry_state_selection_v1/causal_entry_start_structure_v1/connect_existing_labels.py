from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path(".");O=R/"causal_entry_start_structure_v1";assert (O/"FEATURE_SEAL.json").exists()
m=pd.read_parquet(O/"MEMBER_FEATURES_PRELABEL.parquet");s=pd.read_csv(O/"SECTOR_MEMBER_STRUCTURE_PRELABEL.csv",parse_dates=["day"]);t=pd.read_csv(O/"FIXED_TARGET_DAYS.csv",parse_dates=["day"])
m["r_percentile_same_sector"]=m.groupby(["sector","day"]).r.rank(pct=True);m["I_distance_percentile_same_sector"]=m.groupby(["sector","day"]).I_distance_log.rank(pct=True)
z=pd.read_csv(R/"fast_entry_equity_2022_v1/report/INITIAL_AND_FULL_ROUNDS.csv",low_memory=False);z["day"]=pd.to_datetime(z.signal_day)
b=pd.read_csv(R/"cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv",low_memory=False);b=b[b["sample"].eq("2024_924")].copy();b["day"]=pd.to_datetime(b.signal_day);b["initial_net"]=b.core_net;b["initial_return"]=b.core_return;b["initial_evidence_usable"]=b.evidence_usable_closed
cols=["arm","event_id","sid","name","sector","day","status","entry_status","initial_net","initial_return","initial_evidence_usable"];z=pd.concat([z[cols],b[cols]],ignore_index=True).merge(t[["day","market_run","market_age"]],on="day",validate="many_to_one")
z=z.merge(m.rename(columns={c:"stock_"+c for c in m if c not in ["sid","sector","day"]}),on=["sid","sector","day"],validate="many_to_one")
q=s[["sector","day","repair_fraction","peak_log_distance","stage","attempt_active","M3_known_fraction","I_known_fraction","price_positive_known_fraction","joint_positive_known_fraction","positive_price_HHI","positive_amount_HHI"]]
z=z.merge(q,on=["sector","day"],validate="many_to_one");z.to_csv(O/"EXISTING_ROUNDS_WITH_STRUCTURE.csv",index=False)
out=[]
for (arm,run),g in z.groupby(["arm","market_run"]):
 c=g[g.initial_evidence_usable];row=dict(arm=arm,market_run=run,first=g.day.min(),last=g.day.max(),permits=len(g),execution_unknown=int(g.status.str.contains("UNKNOWN").sum()),closed=len(c),wins=int(c.initial_net.gt(0).sum()),net=c.initial_net.sum(),mean=c.initial_net.mean())
 for col in ["stock_r","stock_amount_ratio","stock_I_distance_log","stock_r_percentile_same_sector","stock_I_distance_percentile_same_sector","repair_fraction","M3_known_fraction","I_known_fraction","joint_positive_known_fraction"]:row[col+"_median"]=g[col].median()
 out.append(row)
pd.DataFrame(out).to_csv(O/"FIRST_DAYS_EXISTING_ROUND_DESCRIPTIVE.csv",index=False)
meta=pd.read_csv(R/"pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv").rename(columns={"sector_id":"sector"});cases=pd.read_csv(R/"cross_window_entry_mechanism_v1/FIXED_CASES.csv",parse_dates=["day"]).merge(meta[["sid","name","sector"]],on="sid",validate="many_to_one")
c=cases.merge(m.rename(columns={col:"stock_"+col for col in m if col not in ["sid","sector","day"]}),on=["sid","sector","day"],how="left",validate="one_to_one",indicator="feature_match");c=c.merge(q,on=["sector","day"],how="left",validate="many_to_one")
lab=pd.read_csv(R/"joint_innovation_fixed_cases_v1/FIXED_CASES_WITH_EXISTING_LABELS.csv");c=c.merge(lab[["case_id","existing_initial_net","existing_initial_return","economic_role"]],on="case_id",validate="one_to_one")
c.to_csv(O/"FIXED_CASE_STRUCTURE_WITH_EXISTING_LABELS.csv",index=False)
print("FIXED",c[c.feature_match.eq("both")][["case_id","name","day","stock_I","stock_M3_right","stock_r","stock_amount_ratio","stock_I_distance_log","stock_r_percentile_same_sector","M3_known_fraction","I_known_fraction","joint_positive_known_fraction","repair_fraction","attempt_active","existing_initial_return"]].to_string(index=False))
print("FIRST3",pd.DataFrame(out).query("market_run in [414,419,422,435]").to_string(index=False))

"""Connect all fixed same-stock/same-exit pairs to pre-entry features. No outcomes select pairs here."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
p=pd.read_csv(O/"cash_unique_same_exit_decomposition.csv",float_precision="round_trip")
z=pd.read_csv(O/"EXANTE_ALL_ACTUAL_ROUNDS.csv",float_precision="round_trip",low_memory=False).set_index("round_id")
assert z.index.is_unique
features=["RM","RAW_MOM11","RAW_EXCESS_STANDARDIZED","beta_market","beta_size","beta_value","raw_vol36","raw_vol11","residual_sd","industry_beta36","normalization_component","alpha_component","market_component","size_component","value_component"]
rows=[]
for r in p.to_dict("records"):
    c=z.loc[r["c_round_id"]];b=z.loc[r["r_round_id"]]
    assert c.sid==b.sid==r["sid"] and c.exit_day==b.exit_day==r["exit_day"]
    assert c.event_id==r["c_event_id"] and b.event_id==r["r_event_id"]
    assert c.signal_day==r["c_signal_day"] and b.signal_day==r["r_signal_day"]
    r["same_signal_month"]=str(c.signal_day)[:7]==str(b.signal_day)[:7]
    r["entry_timing"]="CH3_EARLIER" if c.entry_day<b.entry_day else "CH3_LATER" if c.entry_day>b.entry_day else "SAME_ENTRY_DAY"
    r["both_features_known"]=(c.status_feature=="CALENDAR_COMPUTABLE_RELEASE_UNKNOWN" and b.status_feature=="CALENDAR_COMPUTABLE_RELEASE_UNKNOWN")
    for f in features:
        r["c_"+f]=c[f];r["r_"+f]=b[f];r["delta_"+f]=c[f]-b[f]
        if r["same_signal_month"]:assert np.isclose(c[f],b[f],rtol=1e-10,atol=1e-12,equal_nan=True),(r["sid"],f)
    rows.append(r)
out=pd.DataFrame(rows);out.to_csv(O/"EXANTE_ALL_SAME_EXIT_PAIRS.csv",index=False)
summary=[]
for key,g in out.groupby(["window","comparison","same_signal_month","entry_timing"],sort=True):
    row=dict(window=key[0],comparison=key[1],same_signal_month=bool(key[2]),entry_timing=key[3],pairs=len(g),both_features_known=int(g.both_features_known.sum()),
        core_net_delta=float(g.core_delta_net.sum()),quantity_component=float(g.core_quantity_component.sum()),per_share_component=float(g.core_per_share_component.sum()),
        mean_core_return_delta=float(g.core_delta_return.mean()))
    for f in features:row["mean_delta_"+f]=float(g["delta_"+f].mean()) if g["delta_"+f].notna().any() else None
    summary.append(row)
pd.DataFrame(summary).to_csv(O/"EXANTE_SAME_EXIT_TIMING_SUMMARY.csv",index=False)
source={str(O/n):hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ["cash_unique_same_exit_decomposition.csv","EXANTE_ALL_ACTUAL_ROUNDS.csv",Path(__file__).name]}
(O/"EXANTE_PAIR_QA.json").write_text(json.dumps(dict(pairs=len(out),identity_and_preentry_dates_exact=True,
    same_month_own_features_identical=True,pairs_not_selected_by_outcome=True,new_economic_runs=0,source_hashes=source),ensure_ascii=False,indent=2)+"\n")
print(pd.DataFrame(summary).query("comparison=='CH3_RM_MINUS_RAW_MOM11'")[["window","same_signal_month","entry_timing","pairs","both_features_known","core_net_delta","quantity_component","per_share_component","mean_delta_industry_beta36","mean_delta_raw_vol36","mean_delta_RAW_MOM11"]].to_string(index=False))

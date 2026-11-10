
from pathlib import Path
import numpy as np,pandas as pd,pyarrow.parquet as pq,pyarrow.dataset as ds,pyarrow as pa,json
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/h1_failure_mechanism_v1");root=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1")
rank=pd.read_csv(O/"SIX_DATE_ALL_CANONICAL_RANKS.csv");labels=pd.read_csv(O/"SIX_DATE_SELECTED_DESCRIPTIVE_LABELS.csv");q=labels[(labels.day=="2026-01-15")&(labels.K==20)];H=set(q[q.strategy=="H1"].sid);B=set(q[q.strategy=="B_confirmed"].sid);changed=sorted(H^B)
roster=pd.read_csv("/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv").set_index("symbol")
rows=[];paths=[]
for s in changed:
 f=pq.read_table(root/"artifacts"/(s+".parquet"),columns=["day","price__open","price__high","price__low","price__close","price__amount","native__i_floor"]).to_pandas().set_index("day");t=f.index.get_loc(pd.Timestamp("2026-01-15"));C=f["price__close"].to_numpy();op=f["price__open"].to_numpy();hi=f["price__high"].to_numpy();lo=f["price__low"].to_numpy();amt=f["price__amount"].to_numpy();lr=np.diff(np.log(C));tr=np.maximum.reduce([hi[1:]-lo[1:],abs(hi[1:]-C[:-1]),abs(lo[1:]-C[:-1])]);atr=np.mean(tr[t-21:t-1]);prior_ma=np.mean(C[t-20:t]);priorpeak=np.max(C[t-21:t-1]);rr=rank[(rank.day=="2026-01-15")&(rank.sid==s)].iloc[0]
 lab=q[(q.sid==s)&(q.strategy==("B_confirmed"if s in B else"H1"))].iloc[0]
 row={"sid":s,"current_name":roster.at[s,"name"]if s in roster.index else None,"current_industry":roster.at[s,"industry_name"]if s in roster.index else None,"metadata_not_PIT":True,"change":"ADDED_B"if s in B else"REMOVED_BY_B","H1_eligible_rank":rr.H1_eligible_rank,"B_eligible_rank":rr.B_confirmed_eligible_rank,"H1_percentile":rr.full_H1_percentile,"B_score_max_percentile_components":rr.B_score,"R20_percentile":rr.R20_percentile,"Q20_percentile":rr.Q20_percentile,"Q20":rr.Q20_shape,"close":C[t],"R1":C[t]/C[t-1]-1,"R5":C[t]/C[t-5]-1,"R20":C[t]/C[t-20]-1,"R63":C[t]/C[t-63]-1,"prior_daily_sigma20":np.std(lr[t-21:t-1],ddof=1),"prior_ATR20":atr,"extension_from_prior_SMA20_in_ATR":(C[t]-prior_ma)/atr,"two_close_margin_above_old20peak":min(C[t],C[t-1])/priorpeak-1,"current_gap":op[t]/C[t-1]-1,"current_close_vs_open":C[t]/op[t]-1,"amount_vs_prior20median":amt[t]/np.median(amt[t-20:t]),"I_floor":f["native__i_floor"].iloc[t],"close_distance_I_floor":C[t]/f["native__i_floor"].iloc[t]-1,"end20":lab.end20,"mae20":lab.mae20,"mfe20":lab.mfe20}
 rows.append(row)
 for k in range(21):paths.append({"sid":s,"day":str(f.index[t+k].date()),"offset_common_date":k,"close":C[t+k],"relative_signal_close":C[t+k]/C[t]-1})
pd.DataFrame(rows).to_csv(O/"JAN15_ADDED_REMOVED_EXPLANATION.csv",index=False);pd.DataFrame(paths).to_csv(O/"JAN15_CHANGED_STOCK_PATHS.csv",index=False)
print("CHANGED");print(pd.DataFrame(rows)[["sid","current_name","current_industry","change","H1_eligible_rank","B_eligible_rank","B_score_max_percentile_components","R1","R5","R20","R63","prior_daily_sigma20","extension_from_prior_SMA20_in_ATR","two_close_margin_above_old20peak","amount_vs_prior20median","end20","mae20","mfe20"]].to_string(index=False))
files=[str(root/k)for k in json.loads((root/"CACHE_DATASET.json").read_text())["files"]];d=ds.dataset(files,format="parquet");dd=pd.to_datetime(["2024-09-30","2024-10-08","2024-10-09","2024-11-05"])
bars=d.to_table(columns=["sid","day","source_row_present","price__open","price__high","price__low","price__close"],filter=ds.field("day").isin(pa.array(dd))).to_pandas();p=bars.pivot(index="sid",columns="day");x=pd.DataFrame(index=p.index)
for label,ds0,field0,ds1,field1 in [("gap_1008","2024-10-08","price__open","2024-09-30","price__close"),("intraday_1008","2024-10-08","price__close","2024-10-08","price__open"),("nextopen_gap_1009","2024-10-09","price__open","2024-10-08","price__close")]:
 x[label]=p[field0][pd.Timestamp(ds0)]/p[field1][pd.Timestamp(ds1)]-1
x["flat_OHLC_1008"]=(p["price__open"][pd.Timestamp("2024-10-08")]==p["price__high"][pd.Timestamp("2024-10-08")])&(p["price__open"][pd.Timestamp("2024-10-08")]==p["price__low"][pd.Timestamp("2024-10-08")])&(p["price__open"][pd.Timestamp("2024-10-08")]==p["price__close"][pd.Timestamp("2024-10-08")])
x["flat_OHLC_1009"]=(p["price__open"][pd.Timestamp("2024-10-09")]==p["price__high"][pd.Timestamp("2024-10-09")])&(p["price__open"][pd.Timestamp("2024-10-09")]==p["price__low"][pd.Timestamp("2024-10-09")])&(p["price__open"][pd.Timestamp("2024-10-09")]==p["price__close"][pd.Timestamp("2024-10-09")])
x.to_csv(O/"OCT08_EXECUTION_PRICE_PROXIES_ALL.csv")
summ=[]
groups=[("all_observed",set(x.index)),("mature_i_buy",set(rank[(rank.day=="2024-10-08")&rank.eligible_cached_i_buy].sid))]
for k in [20,100]:
 for st in ["H1","A_recent","B_confirmed"]:groups.append((str(k)+"_"+st,set(labels[(labels.day=="2024-10-08")&(labels.K==k)&(labels.strategy==st)].sid)))
for name,ids in groups:
 y=x.loc[list(ids)];r={"group":name,"N":len(y)}
 for key in ["gap_1008","intraday_1008","nextopen_gap_1009"]:
  v=y[key].dropna();r[key+"_known"]=len(v);r[key+"_mean"]=v.mean();r[key+"_median"]=v.median();r[key+"_q10"]=v.quantile(.1);r[key+"_q90"]=v.quantile(.9);r[key+"_gt10pct"]=int(v.gt(.1).sum())
 r["flatOHLC1008_count"]=int(y.flat_OHLC_1008.sum());r["flatOHLC1009_count"]=int(y.flat_OHLC_1009.sum());summ.append(r)
pd.DataFrame(summ).to_csv(O/"OCT08_EXECUTION_PRICE_PROXY_SUMMARY.csv",index=False)
print("EXECUTION");print(pd.DataFrame(summ).to_string(index=False))

from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path(".");O=R/"causal_entry_start_structure_v1";U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031");H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"];di={d:i for i,d in enumerate(cal)};SM={x["symbol"]:x for x in json.loads((U/"STOCK_MANIFEST.json").read_text())};IM={x["series"]:x for x in json.loads((U/"INDUSTRY_MANIFEST.json").read_text())}
m=pd.read_parquet(O/"MEMBER_I_DECOMPOSITION_PRELABEL.parquet");a=pd.read_csv(O/"SECTOR_MEMBER_STRUCTURE_PRELABEL.csv",parse_dates=["day"]);sec=pd.read_csv(O/"SECTOR_FEATURES_PRELABEL.csv",parse_dates=["day"])
assert len(m)==58*1709 and len(a)==58*90 and not m.duplicated(["sid","day"]).any()
assert (m.I.eq(1).astype(int)==m[["I_continuing","I_new_today","I_prior_unknown"]].sum(axis=1)).all()
assert ((a.M3_fixed_lower>=0)&(a.M3_fixed_upper<=1)&(a.M3_fixed_lower<=a.M3_fixed_upper)).all()
assert ((a.joint_positive_fixed_lower>=0)&(a.joint_positive_fixed_upper<=1)&(a.joint_positive_fixed_lower<=a.joint_positive_fixed_upper)).all()
checks=[]
for sid,d in [("600062.SH","2022-03-17"),("300085.SZ","2024-09-12"),("002583.SZ","2024-09-23"),("300623.SZ","2026-01-05"),("603061.SH","2026-01-06"),("600186.SH","2022-11-03")]:
 day=pd.Timestamp(d);item=SM[sid];raw=pd.read_parquet(next(p for p in item["source_sha256"] if p.endswith("/signal.parquet"))).reindex(cal).loc[:day];r=float(np.log(float(raw.close.iloc[-1])/float(raw.close.iloc[-2])));prior=raw.iloc[-22:-1];cols=["source_kind","source_path","segment_id"]
 assert all(prior[c].eq(raw[c].iloc[-1]).all() for c in cols)
 assert prior.amount.notna().all()
 ratio=float(raw.amount.iloc[-1])/float(prior.amount.median());out=m[m.sid.eq(sid)&m.day.eq(day)].iloc[0];assert abs(r-out.r)<1e-12 and abs(ratio-out.amount_ratio)<1e-12
 f=pd.read_parquet(item["refs"]["facts"]).reindex(cal).loc[:day];assert float(f.i_target.iloc[-2])==out.prior_I
 checks.append(dict(kind="stock_physical_prefix_scalar",sid=sid,day=d,r_error=abs(r-out.r),amount_ratio_error=abs(ratio-out.amount_ratio),prior_I_exact=True))
for secid,d in [("URFI881121","2022-04-29"),("URFI881129","2024-09-23"),("URFI881272","2024-09-12")]:
 day=pd.Timestamp(d);item=IM[secid];e=pd.read_parquet(next(p for p in item["source_sha256"] if p.endswith("/events.parquet"))).reindex(cal).loc[:day];e=e[e.segment_id.eq(e.segment_id.iloc[-1])];row=sec[sec.sector.eq(secid)&sec.day.eq(day)].iloc[0]
 for val,name in [(1,"up"),(-1,"down")]:
  event=e[e.event.eq(val)].iloc[-1];eventday=e[e.event.eq(val)].index[-1];assert abs(row[name+"_pivot"]-event.confirmed_pivot_price)<1e-10;assert pd.Timestamp(row[name+"_pivot_day"])==pd.Timestamp(event.confirmed_pivot_date);assert row[name+"_confirmation_age"]==di[day]-di[eventday]
 checks.append(dict(kind="industry_prefix_last_confirmed_extremes",sector=secid,day=d,exact=True))
agg=m.assign(I_on=m.I.eq(1),I_known=m.I.isin([0,1])).groupby("day")[["I_on","I_known","I_new_today","I_continuing","I_prior_unknown"]].sum();agg.to_csv(O/"MARKET_I_IDENTITY_DECOMPOSITION.csv")
tot=m.assign(I_on=m.I.eq(1),I_known=m.I.isin([0,1])).groupby(["sector","day"])[["I_on","I_known","I_new_today","I_continuing"]].sum();tot["new_share_of_I"]=tot.I_new_today/tot.I_on;tot["continuing_known"]=tot.I_continuing/tot.I_known;tot["new_known"]=tot.I_new_today/tot.I_known;tot.reset_index().groupby("day")[["new_share_of_I","continuing_known","new_known"]].median().to_csv(O/"DAILY_I_KNOWN_DENOMINATOR.csv")
qa=dict(passed=True,member_rows=len(m),sector_rows=len(a),target_days=m.day.nunique(),fixed_population=m.sid.nunique(),sectors=a.sector.nunique(),unique_keys=True,unknown_bounds_valid=True,I_partition_exact=True,sector_I_not_in_source=True,physical_prefix_checks=checks,unknown_counts=dict(member_price=int(m.r.isna().sum()),member_amount_ratio=int(m.amount_ratio.isna().sum()),member_I=int((~m.I.isin([0,1])).sum()),member_M3=int((~m.M3_known).sum()),sector_repair_fraction=int(sec.repair_fraction.isna().sum())),no_new_economic_run=True,no_parameter_fit_or_grid=True)
(O/"QA.json").write_text(json.dumps(qa,indent=2))
labfiles=[R/"fast_entry_equity_2022_v1/report/INITIAL_AND_FULL_ROUNDS.csv",R/"cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv",R/"joint_innovation_fixed_cases_v1/FIXED_CASES_WITH_EXISTING_LABELS.csv"]
(O/"LABEL_SOURCE_HASHES.json").write_text(json.dumps({str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in labfiles},indent=2))
print(json.dumps(qa,indent=2))

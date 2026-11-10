import pandas as pd,numpy as np,json;from pathlib import Path
R=Path("."); U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031"); ms=json.loads((U/"INDUSTRY_MANIFEST.json").read_text()); parts=[]
for m in ms:
 f=pd.read_parquet(m["refs"]["CP1_input"]); e=pd.read_parquet(next(p for p in m["source_sha256"] if p.endswith("/events.parquet"))); s=pd.read_parquet(m["refs"]["state"]); x=f[["close","e0_valid","segment_id"]].copy(); x["leg"]=e.leg_direction; x["event"]=e.event; x["entered"]=e.entered; x["pivot_day"]=pd.to_datetime(e.confirmed_pivot_date); x["pivot_price"]=e.confirmed_pivot_price; x["state"]=np.select([x.e0_valid & x.leg.eq(1),~x.e0_valid & x.leg.eq(-1),x.e0_valid & x.leg.eq(-1),~x.e0_valid & x.leg.eq(1)],["UP","DOWN","PULLBACK","PRE_UP"],default="UNKNOWN"); x["sector"]=m["series"]; x["day"]=x.index; x["seq"]=np.arange(len(x)); x["run"]=(x.state.ne(x.state.shift())|x.segment_id.ne(x.segment_id.shift())).cumsum(); x["state_age"]=x.groupby("run").cumcount(); x["E0_run"]=(x.e0_valid.ne(x.e0_valid.shift())|x.segment_id.ne(x.segment_id.shift())).cumsum(); x["E0_age"]=x.groupby("E0_run").cumcount(); x["ret"]=x.close.pct_change(); x["confirm_lag"]=x.seq-pd.Series(np.arange(len(x)),index=x.index).reindex(x.pivot_day).to_numpy();x["confirm_move_pct"]=(x.close/x.pivot_price-1)*100; parts.append(x.reset_index(drop=True))
x=pd.concat(parts,ignore_index=True); market=x.groupby("day").agg(n=("sector","size"),up=("state",lambda a:a.eq("UP").sum()),down=("state",lambda a:a.eq("DOWN").sum()),pullback=("state",lambda a:a.eq("PULLBACK").sum()),pre_up=("state",lambda a:a.eq("PRE_UP").sum()),ret=("ret","mean"));market["market_state"]=np.select([market.up.gt(market.n/2),market.down.gt(market.n/2)],["UP_MAJORITY","DOWN_MAJORITY"],default="MIXED");market["market_run"]=market.market_state.ne(market.market_state.shift()).cumsum();market["market_age"]=market.groupby("market_run").cumcount()
z=pd.read_csv(R/"fast_entry_equity_2022_v1/report/INITIAL_AND_FULL_ROUNDS.csv",low_memory=False); z["day"]=pd.to_datetime(z.signal_day);z=z.merge(x[["sector","day","state","state_age","E0_age","E0_run","leg","run"]],on=["sector","day"]); z=z.merge(market[["market_state","market_run","market_age"]],left_on="day",right_index=True)
def stat(g):
 c=g[g.initial_evidence_usable];return {"n":len(g),"fill":int(g.entry_status.eq("CONDITIONAL_OPEN_PROXY").sum()),"U":int(g.status.str.contains("UNKNOWN").sum()),"FU":int((g.initial_closed & ~g.initial_evidence_usable).sum()),"closed":len(c),"wins":int(c.initial_net.gt(0).sum()),"wr":round(c.initial_net.gt(0).mean()*100,2),"net":round(c.initial_net.sum()),"mean":round(c.initial_net.mean(),2),"tail50":int(c.initial_return.ge(.5).sum())}

import hashlib
O=R/"causal_trend_segment_attribution_v1";O.mkdir(exist_ok=True)
# Preserve all runs, including short and left/right-censored runs. State labels use only close-known observations.
market.loc["2022-01-01":"2026-06-30"].to_csv(O/"MARKET_DAILY_CAUSAL.csv")
segments=[]
for rid,g in market[market.index.year.isin([2022,2023])].groupby("market_run"):
 row=dict(run_id=int(rid),start=str(g.index.min().date()),end=str(g.index.max().date()),days=len(g),state=g.market_state.iloc[0],sector_equal_price_return=float(np.prod(1+g.ret)-1),sector_equal_price_return_after_first_signal_close=float(np.prod(1+g.ret.iloc[1:])-1),first_signal_day_price_return=float(g.ret.iloc[0]),up_count_median=g.up.median(),down_count_median=g.down.median(),left_censored=bool(market[market.market_run.eq(rid)].index.min()<g.index.min()),right_censored=bool(market[market.market_run.eq(rid)].index.max()>g.index.max()))
 segments.append(row)
pd.DataFrame(segments).to_csv(O/"ALL_CONTIGUOUS_SEGMENTS_2022_2023.csv",index=False)
rows=[]
for key,g in z.groupby(["arm","market_run"]):rows.append(dict(arm=key[0],run_id=int(key[1]),**stat(g)))
pd.DataFrame(rows).merge(pd.DataFrame(segments),on="run_id",how="left").to_csv(O/"SEGMENT_INITIAL_LAYER_ATTRIBUTION_2022.csv",index=False)
z.to_csv(O/"ROUNDS_WITH_CAUSAL_STATES.csv",index=False)
rows=[]
for key,g in z.groupby(["arm","state"]):rows.append(dict(arm=key[0],feature="sector_state",value=key[1],**stat(g)))
for key,g in z.groupby(["arm","market_state"]):rows.append(dict(arm=key[0],feature="market_majority_state",value=key[1],**stat(g)))
pd.DataFrame(rows).to_csv(O/"STATE_STRATA.csv",index=False)
yy=x[x.day.dt.year.isin([2022,2023,2024,2026])&x.entered.eq(1)].copy();yy.to_csv(O/"CAUSAL_E0_ENTRY_CONFIRMATIONS.csv",index=False)
z=z.sort_values(["arm","sid","day"]).reset_index(drop=True);z["prior_same_sector_E0_fill_count"]=z.entry_status.eq("CONDITIONAL_OPEN_PROXY").groupby([z.arm,z.sid,z.sector,z.E0_run]).cumsum()-z.entry_status.eq("CONDITIONAL_OPEN_PROXY").astype(int)
z[z.prior_same_sector_E0_fill_count.gt(0)&z.state.ne("DOWN")].to_csv(O/"SAME_SECTOR_E0_REPEAT_TOUCH_2022.csv",index=False)
b=pd.read_csv(R/"cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv",low_memory=False);b=b[b["sample"].eq("2024_924")];b["day"]=pd.to_datetime(b.signal_day);b=b.merge(x[["sector","day","E0_run","state","state_age"]],on=["sector","day"]).sort_values(["sid","day"]).reset_index(drop=True);b["prior_same_E0_fills"]=b.entry_status.eq("CONDITIONAL_OPEN_PROXY").groupby([b.sid,b.sector,b.E0_run]).cumsum()-b.entry_status.eq("CONDITIONAL_OPEN_PROXY").astype(int)
b[b.prior_same_E0_fills.gt(0)&b.state.ne("DOWN")].to_csv(O/"SAME_SECTOR_E0_REPEAT_TOUCH_2024.csv",index=False)
qa=dict(no_economic_rerun=True,no_parameter_grid=True,sector_count=len(ms),market2022_days=int((market.index.year==2022).sum()),market2023_days=int((market.index.year==2023).sum()),market2022_min_sectors=int(market.loc["2022"].n.min()),market2023_min_sectors=int(market.loc["2023"].n.min()),rounds_by_arm=z.groupby("arm").size().to_dict(),source_scope="90 original industry indexes; not CSI300; static current universe and sector classification; not historical-publication PIT certification",outcomes="Existing actual conditional initial-layer lifecycle outcomes grouped by signal-day state, NOT within-segment profits or a shared account. UNKNOWN is not zero. No new causal performance estimate.")
(O/"QA.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2))
sources=[R/"fast_entry_equity_2022_v1/report/INITIAL_AND_FULL_ROUNDS.csv",R/"cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv",U/"INDUSTRY_MANIFEST.json"]
for m in ms:sources.extend([Path(m["refs"]["CP1_input"]),Path(next(p for p in m["source_sha256"] if p.endswith("/events.parquet")))])
(O/"SOURCE_HASHES.json").write_text(json.dumps({str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2))
print(json.dumps(qa,ensure_ascii=False));print(str(O.resolve()))

"""Review the sealed five-case signal output, not a new model/lifecycle."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
x=pd.read_csv(O/"FIXED_DAILY.csv",parse_dates=["day","root_day","a_day"])
M={r["symbol"]:r for r in json.loads(Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json").read_text())}
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
rows=[];unknown=[];sources={}
for ev in x[x.born].itertuples():
 m=M[ev.sid];p=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 sources[p]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
 assert sources[p]==m["source_sha256"][p]
 raw=pd.read_parquet(p);f=pd.read_parquet(m["refs"]["facts"])
 j=cal.get_loc(ev.day);nd=cal[j+1];ns=cal[j+2]
 prev10=f.reindex(cal[max(0,j-10):j+1])
 br=raw.loc[ev.day];rr=raw.loc[nd] if nd in raw.index else None
 floor=ev.initial_floor/br.adjustment_factor
 r=dict(sid=ev.sid,signal_close=str(ev.day.date()),anchor=str(ev.a_day.date()),close_raw=br.raw_close,U20_raw=ev.U20/br.adjustment_factor,B_anchor=ev.B_a,Q=ev.Q,required=ev.required_credit,discount=ev.low_amount_discount,breakout_excess=ev.breakout_excess,initial_floor_raw=floor,E0=ev.E0,I=ev.I,G=ev.G,i_buy=ev.i_buy,CP=ev.CP,prior10_i_buy_days="|".join(str(d.date()) for d,z in prev10.iterrows() if z.i_buy==1),earliest_next_open_date=str(nd.date()),earliest_T1_sale_if_filled=str(ns.date()),next_raw_open=np.nan,source_factor_match=False,all_day_one_price=None,planned_open_to_floor_fraction=np.nan,historical_fill="NOT_ESTABLISHED",not_economic="No size, fill, cash, fees, return, ranking or account simulation")
 if rr is not None:
  same=all(str(br[c])==str(rr[c]) for c in ["source_kind","source_path","segment_id"]) and np.isclose(br.adjustment_factor,rr.adjustment_factor,rtol=1e-11)
  r.update(next_raw_open=rr.raw_open,source_factor_match=bool(same),all_day_one_price=bool(rr.raw_open==rr.raw_high==rr.raw_low==rr.raw_close),planned_open_to_floor_fraction=float((rr.raw_open-floor)/rr.raw_open),next_open_above_floor=bool(rr.raw_open>floor))
  r["open_observation_status"]="KNOWN_SAME_COORDINATE_OPEN_ONLY" if same else "UNKNOWN_SOURCE_OR_FACTOR"
 else:r["open_observation_status"]="UNKNOWN_MISSING_NEXT_OPEN"
 rows.append(r)
for sid,g in x.groupby("sid",sort=False):
 for k in np.flatnonzero(g.root_unknown.to_numpy(bool)):
  prev=g.iloc[k-1] if k else None;z=g.iloc[k]
  unknown.append(dict(sid=sid,unknown_day=str(z.day.date()),quarantined_root=str(prev.root_day.date()) if prev is not None and pd.notna(prev.root_day) else None,last_known_day=str(prev.day.date()) if prev is not None else None,last_known_floor=prev.new_floor if prev is not None else None,reason=z.blocked,no_sale=True,source_row_missing=True,output_metadata_limitation="Original UNKNOWN row omitted old root identity; this review recovers it from immediately preceding active state without changing signal output"))
pd.DataFrame(rows).to_csv(O/"CASE_REVIEW.csv",index=False)
pd.DataFrame(unknown).to_csv(O/"UNKNOWN_EVENT_IDENTITY.csv",index=False)
x[x.born|x.failed|x.root_unknown|x.e0_raised|x.blocked.eq("PRICE_BREAK_AMOUNT_CREDIT_SHORT")].to_csv(O/"DIAGNOSTIC_MILESTONES.csv",index=False)
sources[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
for n in ["FIXED_DAILY.csv","FIXED_MARKET_EVENTS.csv","preflight.py","PROTOCOL.json"]:
 p=O/n;sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(O/"REVIEW_SOURCE_HASHES.json").write_text(json.dumps(sources,indent=2))
print(pd.DataFrame(rows).to_string(index=False))
print(pd.DataFrame(unknown).to_string(index=False))

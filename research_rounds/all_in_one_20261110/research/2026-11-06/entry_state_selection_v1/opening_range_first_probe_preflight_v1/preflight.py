import json,hashlib,math,datetime
from pathlib import Path
import pandas as pd
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/opening_range_first_probe_preflight_v1")
R=O.parent
cases=json.loads((O/"FROZEN_CASES.json").read_text())
manifest=json.loads(Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json").read_text())
paths={x["symbol"]: next((p for p in x["source_sha256"] if p.endswith("/signal.parquet")),None) for x in manifest}
def get(sid,day,freq):
 j=json.loads((O/"raw"/(sid+"_"+day+"_"+freq+".json")).read_text())
 d=pd.DataFrame(j["rows"],columns=j["fields"])
 for c in ["open","high","low","close","volume","amount","preclose"]: 
  if c in d:d[c]=pd.to_numeric(d[c],errors="raise")
 return j,d
def admit(d):
 # Uses only completed bars up to the candidate time, never future high/low.
 if len(d)<3:return None
 if d["clock"].iloc[:3].tolist()!=["09:35","09:40","09:45"]:return None
 R0=float(d.iloc[:3]["high"].max())
 for i in range(3,len(d)):
  x=d.iloc[i]
  if x["clock"]>"14:50":break
  if x["close"]>R0:return dict(idx=i,time=x["clock"],threshold=R0,close=float(x["close"]))
 return None
allbars=[];qa=[];results=[];hashes={}
for sid,day in sorted({(x["sid"],x["entry_day"]) for x in cases}):
 j,m=get(sid,day,"5");jd,ds=get(sid,day,"d")
 m["ts"]=pd.to_datetime(m["time"],format="%Y%m%d%H%M%S%f",errors="raise")
 m["clock"]=m["ts"].dt.strftime("%H:%M")
 expected=(pd.date_range(day+" 09:35",day+" 11:30",freq="5min").append(pd.date_range(day+" 13:05",day+" 15:00",freq="5min"))).strftime("%H:%M").tolist()
 exactgrid=m["clock"].tolist()==expected
 legal=((m.high>=m[["open","close","low"]].max(axis=1))&(m.low<=m[["open","close","high"]].min(axis=1))&(m.low>0)&(m.volume>=0)&(m.amount>=0)).all()
 ag=dict(open=float(m.open.iloc[0]),high=float(m.high.max()),low=float(m.low.min()),close=float(m.close.iloc[-1]),volume=float(m.volume.sum()),amount=float(m.amount.sum()))
 daily=ds.iloc[0].to_dict() if len(ds)==1 else {}
 rec=dict(sid=sid,day=day,n=len(m),grid_exact=exactgrid,date_exact=all(m["date"]==day),adjustflag3=all(m.adjustflag=="3"),ohlcv_legal=bool(legal),zero_volume_bars=int((m.volume==0).sum()),all_day_one_price=bool(m.high.max()==m.low.min()),tradestatus=daily.get("tradestatus"),isST=daily.get("isST"),minute_daily_ohlc_maxdiff=max(abs(ag[k]-daily[k]) for k in ["open","high","low","close"]),minute_daily_volume_difference=ag["volume"]-daily["volume"],minute_daily_amount_difference=ag["amount"]-daily["amount"],daily_preclose=daily.get("preclose"),raw_day_high=ag["high"],raw_day_low=ag["low"])
 p=paths[sid]; hashes[p]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
 native=pd.read_parquet(p); sub=native.loc[native.index.strftime("%Y-%m-%d")==day]
 rec["native_path"]=p;rec["native_day_rows"]=len(sub)
 if len(sub)==1:
  n=sub.iloc[0]
  rec.update(native_factor=float(n["adjustment_factor"]),native_source=str(n["source_kind"]),native_raw_ohlc_maxdiff=max(abs(ag[k]-float(n["raw_"+k])) for k in ["open","high","low","close"]),native_raw_volume_difference=ag["volume"]-float(n["raw_volume"]),native_amount_difference=ag["amount"]-float(n["amount"]),native_observed=bool(n["observed_bar"]),native_price_eligible=bool(n["price_eligible"]))
  for k in ["open","high","low","close"]:rec["native_raw_"+k]=float(n["raw_"+k]);rec["minute_aggregate_"+k]=ag[k]
 # audit-only daily price-limit proxy. Not a trading gate and not official historical limit-price certification.
 ratio=.20 if sid.startswith(("300","301","688")) else (.05 if str(daily.get("isST"))=="1" else .10)
 from decimal import Decimal,ROUND_HALF_UP
 upper=float((Decimal(str(daily["preclose"]))*(Decimal(1)+Decimal(str(ratio)))).quantize(Decimal(".01"),rounding=ROUND_HALF_UP))
 lower=float((Decimal(str(daily["preclose"]))*(Decimal(1)-Decimal(str(ratio)))).quantize(Decimal(".01"),rounding=ROUND_HALF_UP))
 rec["standard_limit_proxy_ratio"]=ratio;rec["upper_limit_proxy"]=upper;rec["lower_limit_proxy"]=lower
 q=admit(m)
 rec["intraday_signal"]=q is not None
 if q:
  pre=admit(m.iloc[:q["idx"]+1].copy());assert pre==q
  mutated=m.copy();mutated.loc[mutated.index>q["idx"],["open","high","low","close"]]=.001
  assert admit(mutated)==q
  rec["prefix_signal_exact"]=True
 qa.append(rec)
 allbars.append(m.assign(sid=sid,entry_day=day))
 for c in [c for c in cases if c["sid"]==sid and c["entry_day"]==day]:
  z=dict(c);z.update(threshold=float(m.iloc[:3].high.max()),signal_status="SIGNAL" if q else "NO_SIGNAL",signal_time=q["time"] if q else None,signal_close=q["close"] if q else None,minute_grid_exact=exactgrid,native_raw_ohlc_maxdiff=rec.get("native_raw_ohlc_maxdiff"),daily_tradestatus=rec["tradestatus"],execution_status="NOT_TESTED_REAL_QUOTES",all_day_one_price=rec["all_day_one_price"])
  if q:
   nxt=m.iloc[q["idx"]+1];start=nxt["ts"]-pd.Timedelta(minutes=5)
   z.update(next_bar_end=nxt["clock"],earliest_proxy_time=start.strftime("%H:%M"),next_bar_raw_open=float(nxt.open),next_bar_one_price=bool(nxt.high==nxt.low),next_bar_volume=float(nxt.volume),next_bar_open_at_upper_limit_proxy=bool(abs(nxt.open-upper)<1e-7),next_bar_flat_at_upper_limit_proxy=bool(abs(nxt.open-upper)<1e-7 and nxt.high==nxt.low),proxy_price_change_vs_original_open_pct=100*(float(nxt.open)/float(c["old_raw_open"])-1),next_bar_above_original_floor=(bool(nxt.open>c["original_initial_floor_raw"]) if c["original_initial_floor_raw"] is not None else None))
  results.append(z)
qad=pd.DataFrame(qa);res=pd.DataFrame(results)
qad.to_csv(O/"SOURCE_QA.csv",index=False);res.to_csv(O/"FIXED_CASE_RESULTS.csv",index=False)
pd.concat(allbars).to_csv(O/"ALL_MINUTE_BARS.csv",index=False)
(O/"NATIVE_SOURCE_HASHES.json").write_text(json.dumps(hashes,ensure_ascii=False,indent=2))
(O/"SUMMARY.json").write_text(json.dumps(dict(events=len(cases),unique_stock_days=len(qa),bars=sum(x["n"] for x in qa),all_grid_exact=bool(qad.grid_exact.all()),all_ohlcv_legal=bool(qad.ohlcv_legal.all()),minute_daily_ohlc_maxdiff=float(qad.minute_daily_ohlc_maxdiff.max()),native_raw_ohlc_maxdiff=float(qad.native_raw_ohlc_maxdiff.max()),source_price_mismatch_days=int((qad.native_raw_ohlc_maxdiff>1e-7).sum()),all_trade_status_1=bool((qad.tradestatus=="1").all()),statuses=res.groupby(["contract","signal_status"]).size().to_dict().__str__(),economic_runs=0),ensure_ascii=False,indent=2))
print(res[["contract","sid","name","signal_day","entry_day","threshold","signal_status","signal_time","earliest_proxy_time","next_bar_raw_open","proxy_price_change_vs_original_open_pct","next_bar_flat_at_upper_limit_proxy","old_pnl"]].to_string(index=False))
print(qad[["sid","day","minute_daily_ohlc_maxdiff","native_raw_ohlc_maxdiff","minute_daily_volume_difference","minute_daily_amount_difference","native_raw_volume_difference","native_amount_difference"]].to_string(index=False))
print("SUMMARY", (O/"SUMMARY.json").read_text())

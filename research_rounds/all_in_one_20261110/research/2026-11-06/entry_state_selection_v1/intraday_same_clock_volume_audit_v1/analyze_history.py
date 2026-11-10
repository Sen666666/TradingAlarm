"""Provider same-clock history diagnostics only. No model, trading gate or account."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import json,csv,hashlib,copy,time,math
import pandas as pd
getcontext().prec=70
O=Path(__file__).resolve().parent;R=O.parent;OLD=R/"opening_range_first_probe_preflight_v1"
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
CLOCKS=[x.strftime("%H:%M") for x in pd.date_range("2000-01-01 09:35","2000-01-01 11:30",freq="5min").append(pd.date_range("2000-01-01 13:05","2000-01-01 15:00",freq="5min"))]
P=CLOCKS[:4];Z=D(0)
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(blob):return [dict(zip(blob["fields"],v)) for v in blob["rows"]]
def clock(r):return r["time"][8:10]+":"+r["time"][10:12]
def median(a):
 s=sorted(a);n=len(s)
 return (s[(n-1)//2]+s[n//2])/2 if n else None
def dist(a,current=None):
 if not a:return dict(n=0)
 s=sorted(a);n=len(s);m=median(s)
 return dict(n=n,min=s[0],p25_empirical=s[max(0,math.ceil(n*.25)-1)],median=m,p75_empirical=s[max(0,math.ceil(n*.75)-1)],max=s[-1],mean=sum(s,Z)/n,zero_observations=sum(x==0 for x in s),current=current,current_midrank_fraction=(D(sum(x<current for x in s))+D(".5")*sum(x==current for x in s))/n if current is not None else None,reported_ratio=current/m if current is not None and m>0 else None)
def csvout(name,a):
 if not a:return save(O/(name+".json"),[])
 keys=list(dict.fromkeys(k for r in a for k in r))
 with (O/(name+".csv")).open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for r in a:w.writerow({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list,tuple)) else v for k,v in r.items()})
 save(O/(name+".json"),a)
def checks(r):
 errs=[]
 try:
  q={k:D(r[k]) for k in ["open","high","low","close","volume","amount"]}
  if any(not x.is_finite() for x in q.values()):return ["NONFINITE"]
  if not (0<q["low"]<=min(q["open"],q["close"])<=max(q["open"],q["close"])<=q["high"]):errs.append("OHLC")
  if q["volume"]<0 or q["amount"]<0:errs.append("NEGATIVE_VOLUME_AMOUNT")
  if q["volume"]==0:
   if q["amount"]!=0:errs.append("ZERO_VOLUME_NONZERO_AMOUNT")
  elif not q["low"]*q["volume"]<=q["amount"]<=q["high"]*q["volume"]:errs.append("AMOUNT_OUTSIDE_REPORTED_PRICE_SUPPORT")
 except Exception:errs.append("PARSE_OR_MISSING")
 return errs
def diagnose(w,by,current):
 rr=current[:4];assert [clock(x) for x in rr]==P
 h=[by[(w["sid"],d)] for d in w["prior_common_days"]]
 assert len(h)==20 and all(d<w["anchor_entry_day"] for d in w["prior_common_days"])
 values={k:[] for k in P};histprefix=[];complete=True
 for hist in h:
  m={clock(x):x for x in hist}
  if len(m)!=len(hist) or any(k not in m for k in P):complete=False;continue
  try:
   vs={k:D(m[k]["volume"]) for k in P}
   if any(v<0 or not v.is_finite() for v in vs.values()):complete=False;continue
   for k in P:values[k].append(vs[k])
   histprefix.append(sum(vs.values(),Z))
  except Exception:complete=False
 curr=[D(x["volume"]) for x in rr];med=[median(values[k]) for k in P]
 known=complete and all(len(values[k])==20 and med[i] is not None and med[i]>0 for i,k in enumerate(P))
 ratios=[curr[i]/med[i] for i in range(4)] if known else None
 pref=dist(histprefix,sum(curr,Z));known=known and pref["n"]==20 and pref["median"]>0
 decay=(ratios[-1]/ratios[0]) if known and ratios[0]>0 else None
 return dict(nominal_20day_status="KNOWN_REPORTED_QUANTITY" if known else "UNKNOWN",current_volumes=curr,history_median_volumes=med,same_clock_ratios=ratios if known else None,first4_total_ratio=pref.get("reported_ratio") if known else None,clock_adjusted_decay=decay,current_internal_errors=[dict(label=clock(x),errors=checks(x)) for x in rr if checks(x)],prefix_distribution=pref,clock_distributions={k:dist(values[k],curr[i]) for i,k in enumerate(P)})
def main():
 start=time.monotonic();assert read(O/"FETCH_DONE.json")["completed"];assert not (O/"ANALYSIS_ONCE.json").exists();save(O/"ANALYSIS_ONCE.json",dict(economic_runs=0,started=time.time()))
 wins=read(O/"FROZEN_WINDOWS.json");cases=read(OLD/"FROZEN_CASES.json");manifest=read(M)
 inputs={str(p):sha(p) for p in [Path(__file__),M,O/"PROTOCOL.json",O/"FROZEN_WINDOWS.json",O/"FETCH_DONE.json",O/"FETCH_LOG.json",OLD/"FROZEN_CASES.json"]}
 nativepaths={r["symbol"]:Path(next(p for p in r["source_sha256"] if p.endswith("/signal.parquet"))) for r in manifest if r["symbol"] in {w["sid"] for w in wins}}
 expected={(w["sid"],d) for w in wins for d in w["prior_common_days"]}
 by={};daily={};provenance=defaultdict(list);overlaps=[];captures=[]
 for w in wins:
  sid=w["sid"]
  for freq,target in [("5",by),("d",daily)]:
   p=O/"raw"/(sid+"_"+w["anchor_entry_day"]+"_"+freq+".json");inputs[str(p)]=sha(p);blob=read(p);assert blob["error_code"]=="0"
   rs=rows(blob);assert all(w["start"]<=r["date"]<=w["end"] and r["date"]<w["anchor_entry_day"] for r in rs)
   group=defaultdict(list)
   for r in rs:
    assert r["date"] in w["prior_common_days"] and r["adjustflag"]=="3"
    group[r["date"]].append(r)
   captures.append(dict(sid=sid,anchor=w["anchor_entry_day"],frequency=freq,request_start=blob["request_started_at"],request_end=blob["request_finished_at"],retrieved_at=blob["retrieved_at"],historical_available_at="UNKNOWN",rows=len(rs)))
   for d in w["prior_common_days"]:
    key=(sid,d);val=group.get(d,[])
    if key in target:
     assert target[key]==val,("OVERLAP_SOURCE_REVISION",sid,d,freq)
     overlaps.append(dict(sid=sid,day=d,frequency=freq,exact=True))
    else:target[key]=val
    provenance[key].append(str(p))
 assert set(by)==set(daily)==expected and len(expected)==601
 native={}
 for sid,p in nativepaths.items():
  inputs[str(p)]=sha(p);df=pd.read_parquet(p);ds=df.index.strftime("%Y-%m-%d")
  native[sid]={d:df.loc[ds==d] for s,d in expected if s==sid}
 qa=[];bad=[];old_overlap=[]
 for sid,day in sorted(expected):
  rs=by[sid,day];dd=daily[sid,day];d=dd[0] if len(dd)==1 else None;grid=[clock(r) for r in rs]
  q=dict(sid=sid,day=day,minute_rows=len(rs),daily_rows=len(dd),grid_exact=grid==CLOCKS,duplicate_labels=len(grid)-len(set(grid)),daily_status=d.get("tradestatus") if d else None,daily_isST=d.get("isST") if d else None,minute_absent=len(rs)==0,provider_suspended=bool(d and d["tradestatus"]=="0"),actual_exchange_suspension="UNKNOWN",historical_available_at="UNKNOWN",share_capital_PIT="UNKNOWN")
  errors=[(r,checks(r)) for r in rs];bad += [dict(sid=sid,day=day,label=clock(r),errors=e,**{k:r[k] for k in ["open","high","low","close","volume","amount"]}) for r,e in errors if e]
  q["bad_internal_bars"]=sum(bool(e) for r,e in errors);q["prefix_bad_internal_bars"]=sum(bool(e) and clock(r) in P for r,e in errors);q["zero_volume_bars"]=sum(D(r["volume"])==0 for r in rs)
  if rs and d:
   ag=dict(open=D(rs[0]["open"]),high=max(D(r["high"]) for r in rs),low=min(D(r["low"]) for r in rs),close=D(rs[-1]["close"]),volume=sum((D(r["volume"]) for r in rs),Z),amount=sum((D(r["amount"]) for r in rs),Z))
   for k in ag:q["minute_minus_daily_"+k]=ag[k]-D(d[k])
   q["OHLC_exact"]=all(q["minute_minus_daily_"+k]==0 for k in ["open","high","low","close"]);q["volume_exact"]=q["minute_minus_daily_volume"]==0;q["amount_exact"]=q["minute_minus_daily_amount"]==0
  else:ag=None;q.update(OHLC_exact=False,volume_exact=False,amount_exact=False)
  nf=native[sid][day];q["native_rows"]=len(nf);q["native_path"]=str(nativepaths[sid])
  if len(nf)==1:
   nr=nf.iloc[0];q.update(native_source_kind=str(nr.get("source_kind")),native_source_path=str(nr.get("source_path")),native_segment=str(nr.get("segment_id")),native_factor=str(nr.get("adjustment_factor")),native_observed=bool(nr.get("observed_bar")),native_price_eligible=bool(nr.get("price_eligible")))
   if d:
    for k in ["open","high","low","close","volume"]:q["daily_minus_native_"+k]=D(d[k])-D(str(nr["raw_"+k]))
    q["daily_minus_native_amount"]=D(d["amount"])-D(str(nr["amount"]))
    q["daily_native_OHLC_exact"]=all(q["daily_minus_native_"+k]==0 for k in ["open","high","low","close"]);q["daily_native_volume_exact"]=q["daily_minus_native_volume"]==0
  old=OLD/"raw"/(sid+"_"+day+"_5.json")
  if old.exists():
   inputs[str(old)]=sha(old);old_overlap.append(dict(sid=sid,day=day,current_old_snapshot_rows_exact=rows(read(old))==rs,old_path=str(old)))
  qa.append(q)
 qmap={(r["sid"],r["day"]):r for r in qa}
 windowqa=[];events=[];distributions=[];causal=[]
 for w in wins:
  sid,anchor=w["sid"],w["anchor_entry_day"];past=[qmap[sid,d] for d in w["prior_common_days"]]
  p=OLD/"raw"/(sid+"_"+anchor+"_5.json");inputs[str(p)]=sha(p);curr=rows(read(p))
  z=diagnose(w,by,curr)
  physical={k:v for k,v in by.items() if k[0]==sid and k[1]<anchor};assert diagnose(w,physical,curr[:4])==z
  poison=copy.deepcopy(curr)
  for r in poison[4:]:
   for k in ["open","high","low","close","volume","amount"]:r[k]="-99999999"
   r["time"]="20990101000000000"
  other=dict(by);other[sid,anchor]=[{"volume":"99999999999"}];other[sid,"2099-01-01"]=[{"volume":"-1"}]
  assert diagnose(w,other,poison)==z
  causal.append(dict(sid=sid,anchor=anchor,physical=True,future_poison=True))
  wq=dict(sid=sid,anchor_entry_day=anchor,expected_history_days=20,minute_grid_days=sum(r["grid_exact"] for r in past),provider_status1_days=sum(r["daily_status"]=="1" for r in past),provider_status0_days=sum(r["daily_status"]=="0" for r in past),absent_minute_days=sum(r["minute_absent"] for r in past),history_OHLC_exact_days=sum(r["OHLC_exact"] for r in past),history_volume_exact_days=sum(r["volume_exact"] for r in past),history_amount_exact_days=sum(r["amount_exact"] for r in past),history_internal_clean_days=sum(r["bad_internal_bars"]==0 for r in past),history_bad_bars=sum(r["bad_internal_bars"] for r in past),native_source_identities=len({(r.get("native_source_kind"),r.get("native_source_path"),r.get("native_segment")) for r in past}),native_factor_values=len({r.get("native_factor") for r in past}),share_capital_PIT="UNKNOWN",historical_available_at="UNKNOWN")
  wq["history_prefix_bad_bars"]=sum(r["prefix_bad_internal_bars"] for r in past)
  wq["prefix_internal_20day_coverage"]=all(r["grid_exact"] and r["daily_status"]=="1" and r["prefix_bad_internal_bars"]==0 for r in past)
  wq["volume_reconciled_20day_coverage"]=all(r["grid_exact"] and r["daily_status"]=="1" and r["volume_exact"] for r in past)
  wq["full_OHLCVA_internal_and_volume_coverage"]=wq["volume_reconciled_20day_coverage"] and all(r["OHLC_exact"] and r["bad_internal_bars"]==0 for r in past)
  wq["nominal_ratio_available"]=z["nominal_20day_status"]=="KNOWN_REPORTED_QUANTITY";windowqa.append(wq)
  for k in CLOCKS:
   vals=[]
   for day in w["prior_common_days"]:
    at=[r for r in by[sid,day] if clock(r)==k]
    if len(at)==1:vals.append(D(at[0]["volume"]))
   cv=D(curr[CLOCKS.index(k)]["volume"]) if k in P else None
   distributions.append(dict(sid=sid,anchor=anchor,label=k,history_days=w["prior_common_days"],history_volumes=vals,**dist(vals,cv),current_day_observation_used=k in P,history_internally_compatible_observations=sum(len([r for r in by[sid,day] if clock(r)==k])==1 and not checks(next(r for r in by[sid,day] if clock(r)==k)) for day in w["prior_common_days"]),history_daily_volume_reconciled=sum(qmap[sid,day]["volume_exact"] for day in w["prior_common_days"])))
  for c in cases:
   if c["sid"]!=sid or c["entry_day"]!=anchor:continue
   lab="FAST_FAILURE" if "fast_failure" in c["tag"] else "PRIOR_TAIL30" if "closed_tail30" in c["tag"] else "PRIOR_LOSS_CONTROL" if c["contract"].startswith("NOACT") else "OLD_FAILURE" if "失败" in c["tag"] else "OLD_PROFIT" if "盈利" in c["tag"] else "CLOCK_ONLY"
   events.append(dict(**c,year=anchor[:4],old_label_role=lab,**{k:v for k,v in z.items() if k not in ["prefix_distribution","clock_distributions"]},**{k:v for k,v in wq.items() if k not in ["sid","anchor_entry_day"]},ratio_units="Relative reported traded shares, not turnover or aggressive flow",new_order_permission="NOT_DEFINED",new_economic_outcome="NOT_COMPUTED"))
 groups=defaultdict(list)
 for e in events:groups[e["contract"],e["year"],e["old_label_role"]].append(e)
 cohorts=[]
 for key,es in sorted(groups.items()):
  z=dict(contract=key[0],year=key[1],old_label_role=key[2],events=len(es),case_ids=[x["case_id"] for x in es],nominal_known=sum(x["nominal_ratio_available"] for x in es),volume_reconciled=sum(x["volume_reconciled_20day_coverage"] for x in es),full_OHLCVA_coverage=sum(x["full_OHLCVA_internal_and_volume_coverage"] for x in es),prefix_internal_coverage=sum(x["prefix_internal_20day_coverage"] for x in es))
  for field in ["first4_total_ratio","clock_adjusted_decay"]:
   vals=[x[field] for x in es if x[field] is not None];z[field+"_reported_distribution"]=dist(vals)
   vals=[x[field] for x in es if x[field] is not None and x["volume_reconciled_20day_coverage"]];z[field+"_volume_reconciled_distribution"]=dist(vals)
  cohorts.append(z)
 for name,a in [("HISTORY_DAY_QA",qa),("HISTORICAL_BAD_BARS",bad),("WINDOW_QUALITY",windowqa),("SAME_CLOCK_DISTRIBUTIONS",distributions),("EVENT_DIAGNOSTICS",events),("COHORT_DESCRIPTIONS",cohorts),("CAPTURE_TIMES",captures),("OVERLAP_CHECKS",overlaps),("OLD_CACHE_OVERLAP",old_overlap),("CAUSAL_CHECKS",causal)]:csvout(name,a)
 summary=dict(status="COMPLETE_DESCRIPTIVE_DATA_AUDIT_NO_ENTRY_RULE",windows=len(wins),events=len(events),history_window_slots=640,unique_history_stock_days=len(qa),unique_minute_rows=sum(r["minute_rows"] for r in qa),all_grids_exact=all(r["grid_exact"] for r in qa),minute_absent_days=sum(r["minute_absent"] for r in qa),provider_status_counts=dict(Counter(r["daily_status"] for r in qa)),OHLC_mismatch_days=sum(not r["OHLC_exact"] for r in qa),volume_mismatch_days=sum(not r["volume_exact"] for r in qa),amount_mismatch_days=sum(not r["amount_exact"] for r in qa),internal_bad_bars=len(bad),days_with_internal_bad=sum(r["bad_internal_bars"]>0 for r in qa),nominal_20day_windows=sum(r["nominal_ratio_available"] for r in windowqa),volume_reconciled_20day_windows=sum(r["volume_reconciled_20day_coverage"] for r in windowqa),full_OHLCVA_20day_windows=sum(r["full_OHLCVA_internal_and_volume_coverage"] for r in windowqa),prefix_internal_20day_windows=sum(r["prefix_internal_20day_coverage"] for r in windowqa),historical_prefix_bad_bar_slots=sum(r["history_prefix_bad_bars"] for r in windowqa),native_factor_varying_windows=sum(r["native_factor_values"]>1 for r in windowqa),native_source_varying_windows=sum(r["native_source_identities"]>1 for r in windowqa),overlap_repeat_day_frequency_checks=len(overlaps),old_cached_overlap_days=len(old_overlap),old_cached_overlap_revised=sum(not x["current_old_snapshot_rows_exact"] for x in old_overlap),physical_prefix_checks=len(causal),future_poison_checks=len(causal),economic_runs=0,new_entry_rules=0,parameter_searches=0,download=read(O/"FETCH_DONE.json"),real_time_available_at="UNKNOWN_ALL",share_capital_PIT="UNKNOWN_ALL",seconds_analysis=time.monotonic()-start)
 save(O/"SUMMARY.json",summary);save(O/"ANALYSIS_INPUT_HASHES.json",inputs)
 for p,h in inputs.items():assert sha(Path(p))==h,p
 save(O/"OUTPUT_HASHES.json",{str(p.relative_to(O)):sha(p) for p in O.rglob("*") if p.is_file() and p.name!="OUTPUT_HASHES.json" and p.suffix!=".log"})
 print(json.dumps(summary,default=str),flush=True)
if __name__=="__main__":main()

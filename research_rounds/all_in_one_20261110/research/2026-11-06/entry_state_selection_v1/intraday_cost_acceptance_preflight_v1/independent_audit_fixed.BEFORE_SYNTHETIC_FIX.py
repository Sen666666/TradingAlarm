#!/usr/bin/env python3
"""Independent raw-cache rational/Decimal audit. Does not run author main or accounts."""
from pathlib import Path
from decimal import Decimal as D, getcontext, ROUND_HALF_UP
from fractions import Fraction as F
from datetime import datetime, timedelta
from collections import Counter
import json, csv, hashlib, importlib.util, sys, copy
sys.dont_write_bytecode=True
getcontext().prec=80
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
P=R/"intraday_cost_acceptance_preflight_v1"; O=R/"opening_range_first_probe_preflight_v1"
EXPECTED_HASH="e8be017794c1c36f0d8c6b3ec256428defcb53bfc60d9666ec632c438839643e"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(),parse_float=D)
def save(name,obj):
 p=P/name
 with p.open("x") as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=str)
def eq(a,b,tag):assert a==b,(tag,a,b)
grid=[]
for start,end in [("09:35","11:30"),("13:05","15:00")]:
 t=datetime.strptime(start,"%H:%M");last=datetime.strptime(end,"%H:%M")
 while t<=last:grid.append(t.strftime("%H:%M"));t+=timedelta(minutes=5)
eq(len(grid),48,"grid")
cases=read(O/"FROZEN_CASES.json")
author=read(P/"FIXED_CASE_RESULTS.json")
abars=read(P/"PER_BAR.json")
aqa=read(P/"SOURCE_QA.json")
abar={(z["sid"],z["day"],z["bar_index"]):z for z in abars}
acase={z["case_id"]:z for z in author}
aqamap={(z["sid"],z["day"]):z for z in aqa}
eq([z["case_id"] for z in author],[z["case_id"] for z in cases],"frozen event order")
eq(len(abar),1536,"unique author bars")
sources=read(P/"SOURCE_HASHES.json")
oldseal=read(O/"OUTPUT_HASHES.json")
core_names=["PROTOCOL.md","analyze_fixed.py","PER_BAR.json","PER_BAR.csv","FIXED_CASE_RESULTS.json","FIXED_CASE_RESULTS.csv","SOURCE_QA.json","SOURCE_QA.csv","SUMMARY.json","SOURCE_HASHES.json"]
before={str(P/n):sha(P/n) for n in core_names}
eq(sha(P/"PROTOCOL.md"),EXPECTED_HASH,"protocol")
for p,h in sources.items():eq(sha(p),h,("source_hash",p))
for p,h in oldseal.items():eq(sha(O/p),h,("old_seal",p))
native=read(O/"NATIVE_SOURCE_HASHES.json")
for p,h in native.items():eq(sha(p),h,("native_hash",p))
all_days={}; independent_events=[]; comparisons=0; first_bad_days=[]; equal_signal_events=[]; exact_product_max_digits=0
numfields=("open","high","low","close","volume","amount")
def parse_raw(sid,day,freq):
 j=read(O/"raw"/(sid+"_"+day+"_"+freq+".json"))
 eq((j["sid"],j["day"],j["frequency"],j["error_code"],j["adjustflag"]),(sid,day,freq,"0","3"),"raw metadata")
 rows=[dict(zip(j["fields"],r)) for r in j["rows"]]
 return rows
for sid,day in sorted({(c["sid"],c["entry_day"]) for c in cases}):
 rows=parse_raw(sid,day,"5"); daily=parse_raw(sid,day,"d")[0]
 eq(len(rows),48,("raw bars",sid,day))
 ratio=D(".20") if sid.startswith(("300","301","688")) else D(".05") if daily["isST"]=="1" else D(".10")
 upper=(D(daily["preclose"])*(1+ratio)).quantize(D(".01"),rounding=ROUND_HALF_UP)
 lower=(D(daily["preclose"])*(1-ratio)).quantize(D(".01"),rounding=ROUND_HALF_UP)
 rational=[{k:F(D(r[k])) for k in numfields} for r in rows]
 dec=[{k:D(r[k]) for k in numfields} for r in rows]
 firstbad=None;nomidx=None;qualidx=None;badidx=[];ind=[];seenupper=False
 for i,r in enumerate(rows):
  z=abar[sid,day,i];x=rational[i];dd=dec[i];t=grid[i]
  stamp=datetime.strptime(r["time"],"%Y%m%d%H%M%S%f")
  eq(stamp.strftime("%Y-%m-%d %H:%M:%S.%f"),day+" "+t+":00.000000","exact source timestamp")
  eq(r["date"],day,"source date");eq(r["code"],sid[-2:].lower()+"."+sid[:6],"source symbol")
  va=sum((u["volume"] for u in rational[:i+1]),F(0));aa=sum((u["amount"] for u in rational[:i+1]),F(0))
  vp=sum((u["volume"] for u in rational[:i]),F(0));ap=sum((u["amount"] for u in rational[:i]),F(0))
  V=sum((u["volume"] for u in dec[:i+1]),D(0));A=sum((u["amount"] for u in dec[:i+1]),D(0))
  VP=sum((u["volume"] for u in dec[:i]),D(0));AP=sum((u["amount"] for u in dec[:i]),D(0))
  reasons=[]
  if r["adjustflag"]!="3":reasons.append("ADJUSTFLAG_NOT_3")
  if any(x[k]<=0 for k in ("open","high","low","close")) or not x["low"]<=x["open"]<=x["high"] or not x["low"]<=x["close"]<=x["high"]:reasons.append("INVALID_OHLC")
  if x["volume"]<0 or x["amount"]<0:reasons.append("NEGATIVE_VOLUME_OR_AMOUNT")
  if x["volume"]==0 and x["amount"]!=0:reasons.append("ZERO_VOLUME_NONZERO_AMOUNT")
  if x["volume"]>0 and not x["low"]<=x["amount"]/x["volume"]<=x["high"]:reasons.append("BAR_AMOUNT_VOLUME_OUTSIDE_LOW_HIGH")
  if va<=0:reasons.append("NO_POSITIVE_CUMULATIVE_VOLUME")
  if reasons:
   badidx.append(i)
   if firstbad is None:firstbad=i
  cond1=(aa/va>=ap/vp) if va>0 and vp>0 else None
  cond2=(x["close"]>=aa/va) if va>0 else None
  nq=(cond1 and cond2 and x["volume"]>0) if cond1 is not None and cond2 is not None else None
  nominal="TRUE" if nq else "FALSE" if nq is not None else "UNDEFINED"
  eligible="09:50"<=t<="14:50"
  if eligible and nq:
   if nomidx is None:nomidx=i
   if firstbad is None and qualidx is None:qualidx=i
  qual="NOT_EVALUATED" if not eligible else "UNKNOWN" if firstbad is not None else nominal
  checks={"eligible":eligible,"provider_nominal_Q":nominal,"quality_available_Q":qual,"prefix_quality":"UNKNOWN" if firstbad is not None else "COMPATIBLE","bar_quality_reasons":reasons,"first_bad_index_so_far":firstbad,"first_bad_time_so_far":grid[firstbad] if firstbad is not None else None,"nominal_tau_so_far":grid[nomidx] if nomidx is not None else None,"quality_tau_so_far":grid[qualidx] if qualidx is not None else None,"W_not_falling":cond1,"close_ge_W":cond2,"volume_positive":x["volume"]>0}
  wp=AP/VP if VP>0 else None;wk=A/V if V>0 else None;inc=dd["amount"]/dd["volume"] if dd["volume"]>0 else None
  nums={"cumulative_amount":A,"cumulative_volume":V,"previous_cumulative_amount":AP,"previous_cumulative_volume":VP,"W_previous":wp,"W_current":wk,"incremental_average":inc,"W_change":wk-wp if wp is not None and wk is not None else None,"close_minus_W":dd["close"]-wk if wk is not None else None,"incremental_average_minus_W_previous":inc-wp if inc is not None and wp is not None else None,"W_change_cross_product":A*VP-AP*V if V>0 and VP>0 else None,"incremental_equivalence_cross_product":dd["amount"]*VP-AP*dd["volume"] if dd["volume"]>0 and VP>0 else None,"close_minus_W_cross_product":dd["close"]*V-A if V>0 else None}
  for k,v in checks.items():eq(z[k],v,(sid,day,i,k));comparisons+=1
  for k,v in nums.items():eq(D(z[k]) if z[k] is not None else None,v,(sid,day,i,k));comparisons+=1
  if VP>0 and dd["volume"]>0:
   eq(nums["W_change_cross_product"],nums["incremental_equivalence_cross_product"],"algebra cross product identity")
   for k in ("W_change_cross_product","close_minus_W_cross_product"):
    eq(F(nums[k]),aa*vp-ap*va if k=="W_change_cross_product" else x["close"]*va-aa,"rational vs Decimal product")
    exact_product_max_digits=max(exact_product_max_digits,len(nums[k].as_tuple().digits))
  same=all(u["open"]==u["high"]==u["low"]==u["close"]==rational[0]["close"] for u in rational[:i+1])
  eq(z["same_price_entire_prefix"],same,"flat prefix")
  seenupper=seenupper or dd["high"]>=upper
  for k,v in {"upper_proxy_touched_in_prefix":seenupper,"below_upper_after_touch_in_prefix":seenupper and dd["low"]<upper,"close_at_upper_proxy":dd["close"]==upper,"flat_at_upper_proxy":dd["high"]==dd["low"]==upper,"bar_range_in_limit_proxy":lower<=dd["low"]<=dd["high"]<=upper,"close_plus_5bp_above_upper_illegal_proxy":dd["close"]*D("1.0005")>upper}.items():eq(z[k],v,(sid,day,i,k))
  for k in ("actual_source_available_at","publication_delay","real_execution"):eq(z[k],"UNKNOWN","independent unknown boundary")
  ind.append({"clock":t,**checks,**nums})
 qa=aqamap[sid,day]
 for k,v in {"bars":48,"grid_exact":True,"first_bad_time":grid[firstbad] if firstbad is not None else None,"incompatible_bar_count":len(badidx),"incompatible_bar_times":[grid[i] for i in badidx],"final_prefix_quality":"UNKNOWN" if firstbad is not None else "COMPATIBLE"}.items():eq(qa[k],v,("qa",sid,day,k))
 eq(D(qa["minute_daily_volume_difference_exact"]),sum((u["volume"] for u in dec),D(0))-D(daily["volume"]),"day volume difference")
 eq(D(qa["minute_daily_amount_difference_exact"]),sum((u["amount"] for u in dec),D(0))-D(daily["amount"]),"day amount difference")
 eq(D(qa["minute_daily_ohlc_maxdiff_exact"]),max(abs(a-D(daily[k])) for k,a in {"open":dec[0]["open"],"high":max(u["high"] for u in dec),"low":min(u["low"] for u in dec),"close":dec[-1]["close"]}.items()),"day OHLC difference")
 if firstbad is not None:first_bad_days.append({"sid":sid,"day":day,"first_bad":grid[firstbad],"bad_bar_count":len(badidx),"nominal_tau":grid[nomidx] if nomidx is not None else None,"quality_tau":grid[qualidx] if qualidx is not None else None})
 all_days[sid,day]={"rows":rows,"ind":ind,"nomidx":nomidx,"qualidx":qualidx,"firstbad":firstbad,"upper":upper,"lower":lower}
 for c in (x for x in cases if x["sid"]==sid and x["entry_day"]==day):
  ac=acase[c["case_id"]];ev={"case_id":c["case_id"],"sid":sid,"day":day}
  for k,v in c.items():eq(ac[k],str(v) if isinstance(v,D) else v,("case identity",k))
  for prefix,idx in (("nominal",nomidx),("quality",qualidx)):
   status="SIGNAL" if idx is not None else "UNKNOWN" if prefix=="quality" and firstbad is not None and firstbad<=45 else "NO_SIGNAL"
   tau=grid[idx] if idx is not None else None
   eq(ac[prefix+"_status"],status,"event status");eq(ac[prefix+"_tau"],tau,"event earliest tau")
   ev[prefix+"_status"]=status;ev[prefix+"_tau"]=tau
   if idx is None:continue
   b=ind[idx];now=dec[idx];nxt=dec[idx+1];nr=rows[idx+1];no=nxt["open"];oo=D(c["old_raw_open"]);floor=c["original_initial_floor_raw"]
   floor=D(floor) if floor is not None else None
   vals={"tau_close":now["close"],"tau_W":b["W_current"],"tau_incremental_average":b["incremental_average"],"tau_W_change":b["W_change"],"tau_close_minus_W":b["close_minus_W"],"next_bar_raw_open":no,"next_open_minus_tau_close":no-now["close"],"next_open_minus_old_open":no-oo,"next_open_vs_old_open_pct":D(100)*(no/oo-1),"next_open_minus_original_floor":no-floor if floor is not None else None,"next_open_plus_5bp":no*D("1.0005")}
   for k,v in vals.items():eq(D(ac[prefix+"_"+k]) if ac[prefix+"_"+k] is not None else None,v,("event numeric",c["case_id"],prefix,k))
   facts={"tau_prefix_quality":b["prefix_quality"],"next_bar_end":grid[idx+1],"next_bar_interval_start":(datetime.strptime(nr["time"],"%Y%m%d%H%M%S%f")-timedelta(minutes=5)).strftime("%H:%M"),"next_open_vs_original_floor":"UNKNOWN" if floor is None else "ABOVE" if no>floor else "EQUAL" if no==floor else "BELOW","next_open_at_upper_limit_proxy":no==upper,"next_open_in_limit_proxy":lower<=no<=upper,"next_open_plus_5bp_above_upper_illegal_proxy":no*D("1.0005")>upper,"next_bar_one_price":nxt["high"]==nxt["low"],"next_bar_flat_at_upper_proxy":nxt["high"]==nxt["low"]==upper,"next_bar_positive_volume":nxt["volume"]>0,"next_bar_price_use":"DESCRIPTION_ONLY_NOT_A_FILL","order_earliest_time":"STRICTLY_AFTER_RECEIPT_OF_COMPLETED_TAU_BAR; RECEIPT_TIME_UNKNOWN"}
   for k,v in facts.items():eq(ac[prefix+"_"+k],v,("event fact",c["case_id"],prefix,k))
   ev[prefix+"_next_bar_raw_open"]=str(no);ev[prefix+"_next_bar_start"]=facts["next_bar_interval_start"]
   if prefix=="quality" and (b["W_change_cross_product"]==0 or b["close_minus_W_cross_product"]==0):equal_signal_events.append({"case_id":c["case_id"],"sid":sid,"tau":tau,"W":str(b["W_current"]),"close":str(now["close"]),"W_cross":str(b["W_change_cross_product"]),"C_cross":str(b["close_minus_W_cross_product"])})
  expected_late=firstbad is not None and qualidx is not None and firstbad>qualidx
  eq(ac["later_bad_does_not_revoke_earlier_quality_signal"],expected_late,"late bad")
  independent_events.append(ev)
# Compare saved source identity joins without treating old outcomes as new results.
orb={z["case_id"]:z for z in csv.DictReader((O/"FIXED_CASE_RESULTS.csv").open())}
oj=read(R/"price_next_open_receipt_preflight_v1/FIXED19_INPUT_RESULT.json")["cases"]
ojmap={(z["sid"],z["day"],z["next_day"]):z for z in oj}
for c in cases:
 a=acase[c["case_id"]];b=orb[c["case_id"]]
 for k in ("signal_status","signal_time","threshold","next_bar_raw_open","proxy_price_change_vs_original_open_pct"):eq(a["original_ORB_"+k],b[k],"old ORB join")
 m=ojmap.get((c["sid"],c["signal_day"],c["entry_day"])) if c["contract"]=="PRICE_FIXED_INPUT" else None
 expected="PASS" if m and m["known"] and m["open_above_J"] else "NO_PASS" if m and m["known"] else "UNKNOWN"
 eq(a["old_O_gt_J_status"],expected,"old OJ scoped join")
# Import only reviewed pure helpers, never main. Check author function actual causality independently.
spec=importlib.util.spec_from_file_location("author_pure_audit",P/"analyze_fixed.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
physical=0;future=0;mutated_fields=list(numfields)
for (sid,day),z in all_days.items():
 rows=z["rows"];full=mod.evaluate(rows,day)
 for n in range(1,49):
  eq(mod.evaluate(rows[:n],day),full[:n],("physical prefix",sid,day,n));physical+=1
  altered=copy.deepcopy(rows)
  for rr in altered[n:]:
   rr.update(open="900.0000",high="901.0000",low="899.0000",close="900.5000",volume="17",amount="17000000.0000",adjustflag="1")
  eq(mod.evaluate(altered,day)[:n],full[:n],("future mutation",sid,day,n));future+=1
# Exact identity and limit/flat/no-flow/unknown tests with generated raw rows.
def synthetic(vals):
 rows=[]
 for i,(o,h,l,c,v,a) in enumerate(vals):
  rows.append({"date":"2024-01-02","time":"20240102"+grid[i].replace(":","")+"00000","code":"sz.000001","open":str(o),"high":str(h),"low":str(l),"close":str(c),"volume":str(v),"amount":str(a),"adjustflag":"3"})
 return rows
base=[(10,10,10,10,100,1000)]*6
tests={}
b=mod.evaluate(synthetic(base),"2024-01-02");tests["flat_positive_flow_permitted_at_0950"]=b[3]["quality_tau_so_far"]=="09:50" and b[3]["W_change_cross_product"]==0 and b[3]["close_minus_W_cross_product"]==0
z=base.copy();z[3]=(10,10,10,10,0,0);b=mod.evaluate(synthetic(z),"2024-01-02");tests["zero_new_flow_does_not_signal"]=b[3]["provider_nominal_Q"]=="FALSE" and b[3]["quality_tau_so_far"] is None
z=base.copy();z[2]=(10,10,10,10,100,2000);b=mod.evaluate(synthetic(z),"2024-01-02");tests["early_bad_prefix_remains_unknown"]=all(x["prefix_quality"]=="UNKNOWN" for x in b[2:]) and b[-1]["quality_tau_so_far"] is None
z=base.copy();z[4]=(10,10,10,10,100,2000);b=mod.evaluate(synthetic(z),"2024-01-02");tests["late_bad_keeps_earlier_permission"]=b[-1]["prefix_quality"]=="UNKNOWN" and b[-1]["quality_tau_so_far"]=="09:50"
z=synthetic(base);del z[1];b=mod.evaluate(z,"2024-01-02");tests["missing_internal_bar_unknown"]=b[1]["prefix_quality"]=="UNKNOWN" and b[-1]["quality_tau_so_far"] is None
tests["lunch_next_start_is_1300"]=(datetime.strptime("20240102130500000","%Y%m%d%H%M%S%f")-timedelta(minutes=5)).strftime("%H:%M")=="13:00"
z=base.copy();z[3]=(10,12,10,10.4,100,1100);b=mod.evaluate(synthetic(z),"2024-01-02");tests["first_condition_true_second_false"]=b[3]["W_not_falling"] and not b[3]["close_ge_W"]
z=base.copy();z[3]=(9,10,9,9.8,100,900);b=mod.evaluate(synthetic(z),"2024-01-02");tests["first_condition_false_second_true"]=not b[3]["W_not_falling"] and b[3]["close_ge_W"]
assert all(tests.values()),tests
for p,h in before.items():eq(sha(p),h,("author core changed during audit",p))
for p,h in sources.items():eq(sha(p),h,("source changed during audit",p))
for p,h in native.items():eq(sha(p),h,("native changed during audit",p))
summary=read(P/"SUMMARY.json")
eq(summary["incompatible_bars"],sum(len([b for b in z["ind"] if b["bar_quality_reasons"]]) for z in all_days.values()),"bad total")
eq(summary["unknown_prefix_bars"],sum(b["prefix_quality"]=="UNKNOWN" for z in all_days.values() for b in z["ind"]),"unknown prefix total")
result={"status":"PASS_FIXED_CACHE_AUDIT_NOT_TRADABILITY_CERTIFICATION","method":"Independent raw-string Fraction exact arithmetic plus Decimal80; no author main/account/economics execution.","protocol_sha256":EXPECTED_HASH,"events_checked":len(independent_events),"unique_stock_days":len(all_days),"bars_checked":len(abars),"exact_field_comparisons":comparisons,"source_hashes_checked":len(sources),"old_frozen_hashes_checked":len(oldseal),"native_source_hashes_checked":len(native),"author_core_hashes_before_after_unchanged":before,"direct_cross_product_max_digits":exact_product_max_digits,"all_first_nominal_quality_times_equal":all(z["nominal_tau"]==z["quality_tau"] and z["nominal_status"]==z["quality_status"] for z in independent_events),"first_bad_days":first_bad_days,"equality_signal_events":equal_signal_events,"physical_prefix_tests":physical,"future_perturbation_tests":future,"future_mutations":"All future OHLCVA and adjustflag replaced with incompatible values; prior outputs unchanged.","synthetic_tests":tests,"scope_caveats":["All fixed files have complete 48-bar grids and finite parseable values. This certifies this cache only, not arbitrary missing terminal bars, malformed/nonfinite fields or a production ingestion layer.","UNKNOWN prefixes were retained; all four affected days had their first quality permission before the first bad bar.","Ordinary flat positive-volume paths pass equality. This is not a pullback-recovery test or proof of durable cost support.","Publication time, exact trade coverage, official historical price-limit exceptions, available quotes and fills remain UNKNOWN.","The next bar open is descriptive. No new strategy return, win rate, saved loss or counterfactual economics was computed."],"new_account_runs":0,"new_economic_runs":0,"new_data_fetches":0,"author_files_modified":False}
save("INDEPENDENT_FIXED_CASE_AUDIT.json",result)
save("INDEPENDENT_RECOMPUTED_EVENTS.json",independent_events)
save("INDEPENDENT_AUDIT_HASHES.json",{str(P/n):sha(P/n) for n in ["independent_audit_fixed.py","INDEPENDENT_PROTOCOL_AUDIT.json","INDEPENDENT_FIXED_CASE_AUDIT.json","INDEPENDENT_RECOMPUTED_EVENTS.json"]})
print(json.dumps(result,ensure_ascii=False,indent=2))

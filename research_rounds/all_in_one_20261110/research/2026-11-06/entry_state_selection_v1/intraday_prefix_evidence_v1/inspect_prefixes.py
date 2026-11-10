"""Descriptive raw-prefix facts only; no trading condition or account."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter,defaultdict
import json,csv,hashlib,copy,time
getcontext().prec=70
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent
B=R/"opening_range_first_probe_preflight_v1"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def raw(sid,day):
 b=read(B/"raw"/(sid+"_"+day+"_5.json"));return [dict(zip(b["fields"],r)) for r in b["rows"]]
def calc(rows):
 z=rows[:4];assert len(z)==4
 assert [r["time"][8:12] for r in z]==["0935","0940","0945","0950"]
 nums=[{f:D(r[f]) for f in ["open","high","low","close","volume","amount"]} for r in z]
 errs=[]
 for i,r in enumerate(nums):
  if not (0<r["low"]<=min(r["open"],r["close"])<=max(r["open"],r["close"])<=r["high"]):errs.append([i+1,"OHLC"])
  if r["volume"]<=0 or r["amount"]<0:errs.append([i+1,"VOLUME_AMOUNT"])
  elif not r["low"]*r["volume"]<=r["amount"]<=r["high"]*r["volume"]:errs.append([i+1,"AMOUNT_RANGE"])
 anchor=nums[0]["open"];sign=[];last=anchor
 for r in nums:
  sign.append("U" if r["close"]>last else "D" if r["close"]<last else "F");last=r["close"]
 vv=sum(r["volume"] for r in nums);aa=sum(r["amount"] for r in nums)
 return dict(labels=[r["time"] for r in z],initial_open=str(anchor),closes=[str(r["close"]) for r in nums],volumes=[str(r["volume"]) for r in nums],amounts=[str(r["amount"]) for r in nums],OHLC=[{k:str(r[k]) for k in ["open","high","low","close"]} for r in nums],sign_sequence="".join(sign),last_close_over_initial_open=str(nums[-1]["close"]/anchor-1),volume_prefix_shares=[str(r["volume"]/vv) for r in nums] if vv else None,prefix_volume=str(vv),prefix_amount=str(aa),prefix_internal_quality="COMPATIBLE" if not errs else "UNKNOWN",quality_errors=errs,provider_complete_and_available_at="UNKNOWN",order_execution="UNKNOWN")
def main():
 start=time.monotonic();assert not (O/"RUN_COMPLETE_ATTEMPT.json").exists();save(O/"RUN_COMPLETE_ATTEMPT.json",dict(phase="DESCRIPTIVE_PREFIX_ONLY",economic_runs=0))
 cases=read(B/"FROZEN_CASES.json");assert len(cases)==33
 files=[B/"FROZEN_CASES.json",B/"SOURCE_QA.csv",B/"OUTPUT_HASHES.json",R/"intraday_cost_acceptance_preflight_v1/READOUT_EXECUTION_ADDENDUM.md",O/"PROTOCOL.json",Path(__file__)]
 files += sorted({B/"raw"/(r["sid"]+"_"+r["entry_day"]+"_5.json") for r in cases})
 hashes={str(p):sha(p) for p in files};out=[];checks=[]
 qa={(r["sid"],r["day"]):r for r in csv.DictReader((B/"SOURCE_QA.csv").open())}
 for c in cases:
  rr=raw(c["sid"],c["entry_day"]);v=calc(rr)
  assert calc(rr[:4])==v
  poison=copy.deepcopy(rr)
  for row in poison[4:]:
   for k in ["open","high","low","close","volume","amount"]:row[k]="-999999"
   row["time"]="20990101000000000";row["adjustflag"]="0"
  assert calc(poison)==v
  label="FAST_FAILURE" if "fast_failure" in c["tag"] else "PRIOR_CLOSED_TAIL30" if "closed_tail30" in c["tag"] else "PRIOR_LOSS_CONTROL" if c["contract"].startswith("NOACT") else "OLD_FAILURE" if "失败" in c["tag"] else "OLD_PROFIT" if "盈利" in c["tag"] else "CLOCK_ONLY"
  out.append(dict(**c,old_label_role=label,year=c["entry_day"][:4],**v,whole_day_QA_audit_only=qa[(c["sid"],c["entry_day"])]))
  checks.append(dict(case_id=c["case_id"],physical_prefix=True,future_poison=True))
 save(O/"PREFIX_FACTS.json",out)
 columns=["case_id","contract","sid","name","signal_day","entry_day","old_pnl","tag","old_label_role","year","sign_sequence","initial_open","closes","volumes","amounts","volume_prefix_shares","last_close_over_initial_open","prefix_internal_quality","quality_errors","provider_complete_and_available_at","order_execution"]
 with (O/"PREFIX_FACTS.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
  for r in out:w.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(list,dict)) else r[k] for k in columns})
 groups=defaultdict(list)
 for r in out:groups[(r["contract"],r["year"],r["old_label_role"],r["sign_sequence"])].append(r["case_id"])
 save(O/"COHORT_PATTERNS.json",[dict(contract=k[0],year=k[1],old_label_role=k[2],sign_sequence=k[3],n=len(v),case_ids=v) for k,v in sorted(groups.items())])
 entry={(r["sid"],r["entry_day"]) for r in cases};signal={(r["sid"],r["signal_day"]) for r in cases}
 summary=dict(status="DESCRIPTIVE_PREFIX_FACTS_COMPLETE_NO_NEW_TRADING_RULE",events=len(cases),entry_days=len(entry),signal_days=len(signal),signal_days_with_cached_minute=len(signal&entry),raw_bars=len(entry)*48,unique_prefixes=len(entry),prefix_bars=len(entry)*4,prefix_compatible_events=sum(r["prefix_internal_quality"]=="COMPATIBLE" for r in out),physical_prefix_passes=len(checks),future_poison_passes=len(checks),source_label_cutoff="09:50",economic_runs=0,parameter_searches=0,new_fetches=0,scored_candidates=0,new_entry_rules=0,seconds=time.monotonic()-start)
 save(O/"CHECKS.json",checks);save(O/"SUMMARY.json",summary);save(O/"SOURCE_HASHES.json",hashes)
 for p,h in hashes.items():assert sha(Path(p))==h,p
 save(O/"OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
 print(json.dumps(summary))
if __name__=="__main__":main()

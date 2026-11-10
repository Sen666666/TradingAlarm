import csv,json,hashlib
from decimal import Decimal
from pathlib import Path
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/opening_range_first_probe_preflight_v1")
rows=list(csv.DictReader((O/"FIXED_CASE_RESULTS.csv").open()))
checks=[]
for x in rows:
 j=json.loads((O/"raw"/(x["sid"]+"_"+x["entry_day"]+"_5.json")).read_text())
 d=[dict(zip(j["fields"],r)) for r in j["rows"]]
 h=max(Decimal(r["high"]) for r in d[:3])
 chosen=None
 for i,r in enumerate(d[3:],3):
  tm=r["time"][8:10]+":"+r["time"][10:12]
  if tm>"14:50":break
  if Decimal(r["close"])>h:chosen=(i,tm);break
 assert abs(Decimal(x["threshold"])-h)<Decimal("1e-9")
 assert bool(chosen)==(x["signal_status"]=="SIGNAL")
 if chosen:
  assert x["signal_time"]==chosen[1]
  assert Decimal(x["next_bar_raw_open"])==Decimal(d[chosen[0]+1]["open"])
 checks.append(dict(case_id=x["case_id"],decimal_rule_exact=True))
original=json.loads((O/"NATIVE_SOURCE_HASHES.json").read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in original.items())
out=dict(events=len(checks),decimal_rule_exact_all=True,source_hashes_unchanged=len(original),new_account_runs=0,new_parameter_searches=0,notes=["Rules are source-conditional, not actual execution certification.","Thirty-three events reuse 32 stock-days; different contracts are never pooled.","Full-day quality audit is not a causal entry input."])
(O/"FINAL_VERIFICATION.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
hashes={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.rglob("*")) if p.is_file() and p.name!="OUTPUT_HASHES.json"}
(O/"OUTPUT_HASHES.json").write_text(json.dumps(hashes,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False));print("files",len(hashes))

"""Supplement saved queue facts; no strategy, consumer or economics."""
from pathlib import Path
import hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent
J=O.parents[1]/"independent_channel_joint_economic_v1"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    if isinstance(v,float) and not math.isfinite(v):return None
    return v
def save(p,v):p.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
sources=json.loads((O/"SOURCE_SHA256.json").read_text())
summary=json.loads((O/"SUMMARY.json").read_text())
unknown={};exceptions=[];eq=[]
changes=pd.read_csv(O/"STATIC_SELECTION_CHANGES.csv",float_precision="round_trip")
for y in [2022,2024]:
    qp=J/f"economic_{y}/joint/RANKING_AUDIT.csv";rp=J/f"economic_{y}/COMPARISON_REPORT_RECOVERED.json"
    sources[str(rp)]=sha(rp)
    q=pd.read_csv(qp,float_precision="round_trip")
    old=q[q.owner_lane.eq("PRICE")&q.PVR_known.eq(False)]
    c=changes[changes.year.eq(y)&changes.owner_lane.eq("PRICE")&changes.PVR_known.eq(False)]
    unknown[str(y)]=dict(legal_candidates=len(old),old_selected=int(old.selected.sum()),
        added=int(c.change.eq("ADDED").sum()),removed=int(c.change.eq("REMOVED").sum()),
        role_selected=int(old.selected.sum())+int(c.change.eq("ADDED").sum())-int(c.change.eq("REMOVED").sum()),
        changed_rows=c[["day","sid","name","sector","joint_feasible_rank","change"]].to_dict("records"))
    summary[str(y)]["unknown_PRICE_boundary"]=unknown[str(y)]
    report=json.loads(rp.read_text())
    tags=pd.DataFrame(report["ab_changes"])
    m=tags[tags.result.eq("PRICE_INDUSTRY_SLOT_DISPLACEMENT")][["event_id","result"]].merge(q,on="event_id",validate="one_to_one")
    e=m[~m.original_ab_feasible_rank.le(2)].copy();e["year"]=y
    assert len(e)==1
    exceptions.append(e)
    for row in e.itertuples():
        z=q[q.day.eq(row.day)&q.sector.eq(row.sector)].copy();z["year"]=y;eq.append(z)
    summary[str(y)]["legacy_slot_label_count"]=len(m)
    summary[str(y)]["legacy_slot_label_not_strict_direct"]=e[["event_id","name","day","original_ab_feasible_rank","joint_feasible_rank","result"]].to_dict("records")
pd.concat(exceptions,ignore_index=True).to_csv(O/"LEGACY_LABEL_NOT_DIRECT.csv",index=False)
pd.concat(eq,ignore_index=True).to_csv(O/"LEGACY_LABEL_BOUNDARY_QUEUES.csv",index=False)
save(O/"UNKNOWN_PRICE_BOUNDARY.json",unknown)
save(O/"SUMMARY.json",summary)
source=J/"report_adapter.py";sources[str(source)]=sha(source)
assert all(sha(Path(p))==d for p,d in sources.items())
save(O/"SOURCE_SHA256.json",sources)
contract=json.loads((O/"CONTRACT.json").read_text())
contract["explicit_unknown_consequence"]="When both lanes exist, select top PRICE even if all PRICE PVR is unknown. This overrides cross-lane known-first priority. No new exception is added."
save(O/"CONTRACT.json",contract)
for p in O.glob("*.json"):
    if p.name!="OUTPUT_SHA256.json":save(p,json.loads(p.read_text()))
save(O/"OUTPUT_SHA256.json",{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!="OUTPUT_SHA256.json"})
print(json.dumps(unknown,ensure_ascii=False,indent=2))
print("SOURCE_UNCHANGED",len(sources))

from pathlib import Path
import json,sys,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));from experiment import calc,M,R,sha
audit={};mp={m["symbol"]:m for m in json.loads(M.read_text())};fixed=pd.read_csv(O/"FIXED_CASES.csv");reasons=[];errors=[]
for x in fixed.to_dict("records"):
 p=pd.read_parquet(next(p for p in mp[x["sid"]]["source_sha256"] if p.endswith("/signal.parquet"))).loc[:x["day"]];g=p.tail(21)
 clv=(2*g.close-g.high-g.low)/(g.high-g.low)
 if x["common_known"]:
  scalar=sum(float(a)*float(v) for a,v in zip(clv,g.raw_volume))/sum(float(v) for v in g.raw_volume)
  errors.append(abs(scalar-x["CMF21"]));assert abs(scalar-x["CMF21"])<1e-12
 else:
  reasons.append(dict(sid=x["sid"],day=x["day"],zero_range_days=";".join(str(d.date()) for d in g[g.high.eq(g.low)].index),adjustment_factor_values=";".join(map(str,g.adjustment_factor.unique())),volume_factor_values=";".join(map(str,g.volume_factor.unique())),source_count=int(g.source_path.nunique())))
pd.DataFrame(reasons).to_csv(O/"FIXED_UNKNOWN_REASONS.csv",index=False)
audit["fixed_scalar_known"]=len(errors);audit["fixed_scalar_max_error"]=max(errors)
# Independent sector-slot reconstruction from saved features. No labels used.
c=pd.read_parquet(O/"FEATURES.parquet");picks=pd.read_parquet(O/"SEALED_PICKS.parquet");moves=pd.read_parquet(O/"RANK_MOVES.parquet");recomputed=[];unknown_kept=0
for day,g in c.groupby("day"):
 base=g.sort_values(["original_priority_rank","sid"]);ks=base.head(min(20,len(base))).groupby("sector").size()
 for m in ["PVR","L21","CMF21"]:
  for sec,gs in base.groupby("sector",sort=False):
   order=list(gs.index)
   if m!="PVR":
    positions=[i for i,j in enumerate(order) if bool(c.loc[j,"common_known"])]
    known=sorted([order[i] for i in positions],key=lambda j:(-float(c.loc[j,"score_"+m]),float(c.loc[j,"original_priority_rank"]),c.loc[j,"sid"]))
    for i,j in zip(positions,known):order[i]=j
    unknown_kept+=sum(not bool(c.loc[j,"common_known"]) for j in order)
   recomputed.extend((day,m,int(c.loc[j,"row"])) for j in order[:int(ks.get(sec,0))])
actual=set(zip(picks.day,picks.method,picks.row));assert set(recomputed)==actual
audit["independent_queue_sets_exact"]=True;audit["unknown_slot_checks"]=unknown_kept
# Factor-change fixture keeps OHLC coordinates consistent, isolating stable-factor rejection.
sid="600606.SH";raw=pd.read_parquet(next(p for p in mp[sid]["source_sha256"] if p.endswith("/signal.parquet"))).loc[:"2022-03-22"].tail(120).copy()
q=raw.copy();q["adjustment_factor"]=1.
for k in ["open","high","low","close"]:q[k]=q["raw_"+k]
# Replace entire fixture with valid constant observations for deterministic boundary proof.
for k,val in [("open",100.),("high",101.),("low",99.),("close",100.)]:q[k]=q["raw_"+k]=val
q["amount"]=10000.;q["raw_volume"]=100.;q["volume_factor"]=1.;q["segment_id"]=0;q["source_kind"]="test";q["source_path"]="test"
q["volume_unit"]="shares";q["amount_unit"]="CNY"
for k in ["observed_bar","is_observed_bar","price_eligible","volume_eligible"]:q[k]=True
for k in ["source_invalid","synthetic_event_bar"]:q[k]=False
q.loc[q.index[-10]:,"adjustment_factor"]=2.
for k in ["open","high","low","close"]:q[k]=q["raw_"+k]*q.adjustment_factor
z=calc(q);assert np.isnan(z.CMF21.iloc[-1]);audit["consistent_coordinate_factor_change_unknown"]=True
q2=q.copy();q2["adjustment_factor"]=2.
for k in ["open","high","low","close"]:q2[k]=q2["raw_"+k]*q2.adjustment_factor
assert calc(q2).CMF21.iloc[-1]==0.;audit["uniform_adjustment_scale_invariant"]=True
# Single zero-range observation: valid CMF returns only after all21 valid samples.
q=q2.copy()
for k in ["open","high","low","close","raw_open","raw_high","raw_low","raw_close"]:q.loc[q.index[-22],k]=200. if not k.startswith("raw_") else 100.
z=calc(q);assert np.isnan(z.CMF21.iloc[-2]) and z.CMF21.iloc[-1]==0.;audit["zero_range_requires_21_valid_recovery"]=True
assert len(fixed)==29
a=pd.read_csv(O/"FIXED_CASE_QUEUE.csv");knownlegal=a[a.method.notna()];pv=knownlegal.pivot(index=["sid","day"],columns="method",values="selected");assert pv.PVR.eq(pv.L21).all() and pv.PVR.eq(pv.CMF21).all()
audit["fixed_legal_cases"]=len(pv);audit["fixed_selection_sets_unchanged"]=True
seal=json.loads((O/"RANK_SEAL.json").read_text());assert all(sha(O/n)==h for n,h in seal["hashes"].items());audit["original_seal_still_exact"]=True
(O/"SUPPLEMENT_QA.json").write_text(json.dumps(audit,indent=2));print(json.dumps(audit))

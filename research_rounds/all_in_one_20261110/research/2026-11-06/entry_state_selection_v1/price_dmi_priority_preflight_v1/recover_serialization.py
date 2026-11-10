
"""PRICE-only DMI priority preflight. Read frozen feasible queues, never run economics."""
import ast, hashlib, json, warnings, time
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore",category=FutureWarning)
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=R/"price_dmi_priority_preflight_v1"
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
N=14
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 with (O/name).open("x") as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def csv(name,x):x.to_csv(O/name,index=False,mode="x")

assert not (O/"SEALED_RANKS.parquet").exists()
save("SERIALIZATION_RECOVERY.json",dict(reason="Mixed int2022/string2024_924 window caused Arrow write rejection after FEATURES.parquet saved. Normalize display window to string; feature computation not repeated; formulas/protocol unchanged.",feature_sha256=sha(O/"FEATURES.parquet"),original_script_sha256=sha(O/"run_preflight.py"),future_labels_read=False))
inputs={str(p):sha(p) for p in [M,H,Path(__file__),R/"dmi_boundary_migration_v1/experiment.py",R/"independent_channel_joint_economic_v1/joint_engine.py",R/"independent_channel_joint_economic_v1/joint_policy.py"]}
frames=[]
for yr in ["2022","2024"]:
 p=R/"independent_channel_joint_economic_v1"/("economic_"+yr)/"joint/RANKING_AUDIT.csv"
 inputs[str(p)]=sha(p);x=pd.read_csv(p);x["year"]=int(yr);x["day"]=pd.to_datetime(x.day);frames.append(x)
q=pd.concat(frames,ignore_index=True);q["row_id"]=np.arange(len(q))
assert not q.duplicated(["window","day","sector","sid"]).any()
assert q.stock_state_before.eq("FLAT").all() and q.close_check.eq("PASS").all()
assert q.selected.eq(q.joint_feasible_rank.le(2)).all()
for _,g in q.groupby(["window","day","sector"],sort=False):
 g=g.sort_values("joint_feasible_rank")
 assert g.joint_feasible_rank.tolist()==list(range(1,len(g)+1))
 assert g.selected.sum()==min(2,len(g))
 known=g.PVR_known.eq(True)&np.isfinite(g.PVR_score)
 expected=pd.concat([g[known].sort_values(["PVR_score","sid"],ascending=[False,True]),g[~known].sort_values("sid")])
 assert expected.row_id.tolist()==g.row_id.tolist()
tree=ast.parse((R/"dmi_boundary_migration_v1/experiment.py").read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ("calc","rma")],type_ignores=[]),"frozen_DMI_functions_only","exec"))
mp={x["symbol"]:x for x in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]

q["window"]=q.window.astype(str)
price=q[q.owner_lane.eq("PRICE")]
f=pd.read_parquet(O/"FEATURES.parquet")
assert len(f)==len(price)==6528
assert sorted(f.row_id)==sorted(price.row_id)
check=price[["row_id","sid","day"]].merge(f[["row_id","sid","day"]],on="row_id",suffixes=("_q","_f"),validate="one_to_one")
assert check.sid_q.eq(check.sid_f).all() and check.day_q.eq(check.day_f).all()
aud=[]
for sid,g in f.groupby("sid"):
 m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 h=sha(path);assert h==m["source_sha256"][path];inputs[path]=h
 aud.append(dict(sid=sid,rows=len(g),known=int(g.d.notna().sum()),source=path,sha256=h))
q=q.merge(f[["row_id","d","dclose","plus_di","minus_di","adx","age"]],on="row_id",how="left",validate="one_to_one")
q["mutable"]=q.owner_lane.eq("PRICE")&q.PVR_known.eq(True)&np.isfinite(q.PVR_score)&np.isfinite(q.d)
q["new_rank"]=q.joint_feasible_rank.copy()
for _,g in q.groupby(["window","day","sector"],sort=False):
 use=g[g.mutable]
 ranked=use.sort_values(["d","PVR_score","sid"],ascending=[False,False,True])
 q.loc[ranked.index,"new_rank"]=sorted(use.joint_feasible_rank.tolist())
q["dmi_selected"]=q.new_rank.le(2)
q["rank_changed"]=q.new_rank.ne(q.joint_feasible_rank)
q["entered_selection"]=q.dmi_selected&~q.selected
q["lost_selection"]=q.selected&~q.dmi_selected
assert q.loc[~q.mutable,"new_rank"].equals(q.loc[~q.mutable,"joint_feasible_rank"])
assert not q.loc[q.owner_lane.eq("AB"),"rank_changed"].any()
stats=[]
for year,g in q.groupby("year"):
 p=g[g.owner_lane.eq("PRICE")]
 groups=g.groupby(["day","sector"]); pg=p.groupby(["day","sector"])
 stats.append(dict(year=int(year),all_feasible_rows=len(g),price_rows=len(p),price_stocks=p.sid.nunique(),price_days=p.day.nunique(),price_selected=int(p.selected.sum()),d_known=int(p.d.notna().sum()),d_unknown=int(p.d.isna().sum()),pvr_unknown=int((~p.PVR_known.eq(True)|~np.isfinite(p.PVR_score)).sum()),mutable=int(p.mutable.sum()),nonpositive_d=int(p.d.le(0).sum()),rank_changed=int(p.rank_changed.sum()),entered_selection=int(p.entered_selection.sum()),lost_selection=int(p.lost_selection.sum()),changed_sector_days=int(groups.entered_selection.any().sum()),changed_dates=p.loc[p.entered_selection|p.lost_selection,"day"].nunique(),ab_selected=int(g[g.owner_lane.eq("AB")].selected.sum()),ab_changed=int(g[g.owner_lane.eq("AB")].rank_changed.sum()),price_competitive_sector_days=sum(len(x)>x.selected.sum() and x.selected.sum()>0 for _,x in pg),price_no_available_slots_sector_days=sum(x.selected.sum()==0 for _,x in pg)))
# Check one-to-one slot preservation and price lane budgets.
for _,g in q.groupby(["window","day","sector"],sort=False):
 assert sorted(g.new_rank)==sorted(g.joint_feasible_rank)
 assert g.selected.sum()==g.dmi_selected.sum()
 assert g.loc[g.owner_lane.eq("PRICE"),"selected"].sum()==g.loc[g.owner_lane.eq("PRICE"),"dmi_selected"].sum()
q.to_parquet(O/"SEALED_RANKS.parquet",index=False)
csv("RANK_MOVES.csv",q[q.rank_changed]);csv("SOURCE_AUDIT.csv",pd.DataFrame(aud))
csv("SUMMARY.csv",pd.DataFrame(stats))
save("INPUT_HASHES.json",inputs)
save("FEATURE_PICK_SEAL.json",{str(p.name):sha(p) for p in [O/"PROTOCOL.json",O/"FEATURES.parquet",O/"SEALED_RANKS.parquet",Path(__file__)]})
save("QA.json",dict(feasible_original_rank_exact=True,ab_numeric_slots_exact=True,unknown_numeric_slots_exact=True,sector_day_price_quota_exact=True,price_rows=len(price),source_hashes_verified=len(aud),economic_runs=0,consumer_imports=0,future_labels_read=False))
print("SUMMARY",json.dumps(stats,ensure_ascii=False),flush=True)

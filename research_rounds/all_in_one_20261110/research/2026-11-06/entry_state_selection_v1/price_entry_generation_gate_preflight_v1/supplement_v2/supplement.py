"""Declared supplemental cases and physical-source rolling-prefix QA only."""
from pathlib import Path
import ast,json,hashlib,warnings
import pandas as pd,numpy as np
warnings.filterwarnings("ignore")
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path(__file__).resolve().parent
P=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
D=R/"independent_channel_full1709_preflight_v1/DAILY_STATES.parquet"
OV=R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet"
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze=json.loads((O/"FREEZE.json").read_text());assert sha(__file__)==freeze["code_sha256"]
if (O/"RUN_STARTED.json").exists():raise RuntimeError("Supplement already started; do not rerun.")
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
save("RUN_STARTED.json",dict(code_sha256=sha(__file__),economics=0))
sources={str(p):sha(p) for p in [M,H,D,OV,P/"diagnose.py"]}
manifest={z["symbol"]:z for z in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
nodes=[n for n in ast.parse((P/"diagnose.py").read_text()).body if isinstance(n,ast.FunctionDef) and n.name=="run_root"]
ns=dict(np=np);exec(compile(ast.Module(body=nodes,type_ignores=[]),"frozen_run_root","exec"),ns);run_root=ns["run_root"]
cases=[("300666.SZ","2026-01-05"),("300666.SZ","2026-01-15"),("603061.SH","2026-01-05"),("603061.SH","2026-01-15"),("002583.SZ","2024-09-20"),("002583.SZ","2024-09-23"),("002583.SZ","2024-09-24"),("002583.SZ","2024-09-25")]
daily=pd.read_parquet(D,columns=["sid","day","root_day","U","C","S_old","S_new","e0_raised","born","receipt","valid","active","failed","root_unknown","phase"])
daily=daily[daily.sid.isin({s for s,d in cases})].copy()
ov=pd.read_parquet(OV,columns=["sid","day","window"]);ov=ov[ov.window.isin(["2022","2024_924"])]
def inputs(raw,calendar):
 q=raw.reindex(calendar)
 valid=np.isfinite(q[["open","high","low","close"]]).all(axis=1)&q[["open","high","low","close"]].gt(0).all(axis=1)&q.high.ge(q[["open","high","low","close"]].max(axis=1))&q.low.le(q[["open","high","low","close"]].min(axis=1))
 for k in ["price_eligible","observed_bar","is_observed_bar"]:valid &= q[k].fillna(False).astype(bool)
 for k in ["source_invalid","synthetic_event_bar"]:valid &= ~q[k].fillna(True).astype(bool)
 ids=q[["source_kind","source_path","segment_id"]];valid &= ids.notna().all(axis=1)
 ident=(ids.source_kind.astype(str)+"|"+ids.source_path.astype(str)+"|"+ids.segment_id.astype(str)).to_numpy()
 contiguous=(~valid|~valid.shift(fill_value=False)|~ids.eq(ids.shift()).all(axis=1)).cumsum()
 age=valid.groupby(contiguous).cumcount()
 hi=q.high.rolling(20,min_periods=20).max().shift().where(valid&age.ge(20))
 return q,valid,ident,hi
checks=[];results=[];chains=[]
for no,sid in enumerate(sorted(set(ov.sid)|{s for s,d in cases})):
 p=Path(next(k for k in manifest[sid]["source_sha256"] if k.endswith("/signal.parquet")))
 assert sha(p)==manifest[sid]["source_sha256"][str(p)];sources[str(p)]=sha(p)
 raw=pd.read_parquet(p);q,valid,ident,hi=inputs(raw,cal)
 gg=ov[ov.sid.eq(sid)]
 if len(gg):
  cut=gg.day.sort_values().iloc[len(gg)//2];cc=cal[cal<=cut]
  qp,vp,ip,hp=inputs(raw.loc[:cut].copy(),cc)
  pd.testing.assert_series_equal(hp,hi.loc[:cut],check_exact=True)
  pd.testing.assert_series_equal(vp,valid.loc[:cut],check_exact=True)
  for source_field in ["source_kind","source_path","segment_id"]:
   left=q.loc[:cut,source_field];right=qp[source_field]
   assert np.array_equal(left.isna().to_numpy(),right.isna().to_numpy()),("SOURCE_NULL_MASK_MISMATCH",sid,cut,source_field)
   known=left.notna()
   assert np.array_equal(left[known].to_numpy(),right[known].to_numpy()),("SOURCE_KNOWN_VALUE_MISMATCH",sid,cut,source_field)
  checks.append(dict(sid=sid,cutoff=str(cut.date()),physical_source_rows=len(raw.loc[:cut]),common_prefix_rows=len(cc),rolling_prior20_exact=True,validity_exact=True,source_identity_exact=True))
 for cs,ds in cases:
  if cs!=sid:continue
  day=pd.Timestamp(ds);rows=daily[daily.sid.eq(sid)&daily.day.eq(day)]
  assert len(rows)==1,(sid,day,len(rows))
  z=rows.iloc[0].to_dict();ix=cal.get_loc(day)
  if not z["valid"] or z["root_unknown"]:g=dict(gate_status="UNKNOWN_PARENT_OR_SOURCE",entry_active=None)
  elif z["failed"] or not z["active"] or pd.isna(z["root_day"]):g=dict(gate_status="NO_ACTIVE_ORIGINAL_ROOT",entry_active=False)
  else:
   b=cal.get_loc(z["root_day"]);rr=run_root(q.close.to_numpy(),hi.to_numpy(),valid.to_numpy(),ident,b,ix,float(z["U"]),cal.strftime("%Y-%m-%d").to_numpy());g=rr[-1]
   if sid=="002583.SZ" and ds=="2024-09-25":chains=[dict(sid=sid,**r) for r in rr]
  z.update(g);z["sid"]=sid;z["day"]=ds;z["raw_close"]=None if not np.isfinite(q.raw_close.iloc[ix]) else float(q.raw_close.iloc[ix]);z["old_receipt_and_gate"]=bool(z["receipt"] and z["entry_active"]) if z["entry_active"] is not None else None
  results.append(z)
 if (no+1)%400==0:print("PHYSICAL_PREFIX",no+1,flush=True)
pd.DataFrame(results).to_csv(O/"SUPPLEMENTAL_CASES.csv",index=False)
pd.DataFrame(chains).to_csv(O/"HYTERA_GATE_CHAIN.csv",index=False)
pd.DataFrame(checks).to_csv(O/"PHYSICAL_PREFIX_CHECKS.csv",index=False)
for p,h in sources.items():assert sha(p)==h
save("SOURCE_HASHES.json",sources)
save("QA.json",dict(physical_raw_prefix_checks=len(checks),all_rolling_prior20_exact=True,all_validity_identity_exact=True,supplemental_cases=len(results),new_formula=False,economic_runs=0,pnl_columns_loaded=False,parent_FAIL_UNKNOWN_consumer_tested=False))
save("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
print("CASES",pd.DataFrame(results).to_json(orient="records",date_format="iso"),flush=True)
print("QA",json.dumps(json.loads((O/"QA.json").read_text())),flush=True)

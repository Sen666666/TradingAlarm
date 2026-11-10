from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,sys
P=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/add_signal_quality_diagnostic_v1");R=P.parents[2]
a=pd.read_csv(P/"ALL_ACTUAL_ADD_FEATURES.csv")
sd=pd.read_parquet(R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet");sd.day=pd.to_datetime(sd.day).dt.strftime("%Y-%m-%d")
z=a.merge(sd[["sid","day","score"]],left_on=["sid","signal_day"],right_on=["sid","day"],how="left",validate="many_to_one")
assert z.score.notna().all() and (z.pvr-z.score).abs().max()==0
assert (pd.to_datetime(a.signal_day)<pd.to_datetime(a.open_day)).all()
assert a.old_receipt.all() and a.qok.all()
old=pd.read_csv(P.parent/"dual_plus_half_profit_v1/ALL_ADD_LAYER_RESULTS.csv")
old=old[old.event_type.eq("FALSE_TO_TRUE")&old.window.isin(["2022","2024_924"])]
v=a.merge(old,on=["policy","event_id","sid","window"],validate="one_to_one")
assert len(v)==len(a)
assert v.add_closed.eq(v.closed).all()
err=(v.add_net-v.layer_net).abs().max();assert err<1e-7
ss=[]
for (pol,yr),g in a.groupby(["policy","window"]):
 for same,h in g.groupby("prev_cp_same_I"):
  for strong,k in h.groupby("pvr_progress"):
   c=k[k.add_closed];w=c[c.add_net>0];l=c[c.add_net<0]
   ss.append(dict(policy=pol,window=yr,previous_CP_same_I=bool(same),PVR_progress=bool(strong),n=len(k),closed=len(c),mean_net=c.add_net.mean(),sum_net=c.add_net.sum(),win=c.add_net.gt(0).mean(),payoff=w.add_net.mean()/-l.add_net.mean() if len(w)*len(l) else None))
pd.DataFrame(ss).to_csv(P/"PREVIOUS_CP_ROOT_SENSITIVITY.csv",index=False)
sys.path.insert(0,"/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
from features import original_pvr
mf=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
m={x["symbol"]:x for x in json.loads(mf.read_text())}
prefix=[]
for sid,cut in [("300059.SZ","2024-09-19"),("000158.SZ","2024-09-25"),("000833.SZ","2024-12-03")]:
 sp=next(p for p in m[sid]["source_sha256"] if p.endswith("/signal.parquet"));f=pd.read_parquet(sp)
 full=original_pvr(f);trunc=original_pvr(f.loc[:cut]);e=(full.loc[trunc.index]-trunc).abs().max().max()
 assert e==0;prefix.append(dict(sid=sid,cut=cut,max_error=e))
qa=dict(rows=len(a),policy_windows=a.groupby(["policy","window"]).size().to_dict(),PVR_matches_existing_canonical_all_rows_exact=True,PVR_max_error=0,all_signal_before_open=True,all_have_original_fresh_CP=True,all_price_mean_q_valid=True,original_layer_results_max_error=err,prefix_checks=prefix,unknown_values_not_filled=True,primary_sample="original M3 FALSE_TO_TRUE actual buy_add, not future winners; same date/industry pairs selected on covariates before checking outcomes",account_runs=0,parameter_scans=0,bootstrap="1000 crossed stock/date multinomial weighted resamples; fixed seed 48201; descriptive dependence sensitivity not causal identification",limits=["2024 event window only Sep-Dec, not full year","birth-window not execution calendar year","actual-entry conditioning uses next open; quality fields use prior signal close","finite selected fixed future membership NON-PIT; prior exposed outcomes; not out of sample","dividend/factor/source discontinuities remain UNKNOWN","not shared portfolio","extra snapshots carry exactly their own policies; not pooled with original"])
qa["policy_windows"]={str(k):int(v) for k,v in qa["policy_windows"].items()}
(P/"SIGNAL_QA.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2))
paths=[mf,R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet",R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet",Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py"),P.parent/"dual_budget_ablation_v1/baseline/ALL_SHADOW_ROUNDS.csv",P.parent/"dual_budget_ablation_v1/dual/ALL_SHADOW_ROUNDS.csv",P.parent/"dual_plus_half_profit_v1/uhalf/ALL_SHADOW_ROUNDS.csv"]
for sid in sorted(a.sid.unique()):
 paths += [Path(m[sid]["refs"]["facts"]),Path(m[sid]["refs"]["CP1"]),Path(next(p for p in m[sid]["source_sha256"] if p.endswith("/signal.parquet"))),R/"dual_frontier_cp_full_v1/states"/(sid+".parquet")]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(P/"SIGNAL_SOURCE_HASHES.json").write_text(json.dumps(hashes,indent=2))
print(json.dumps(qa,ensure_ascii=False,indent=2));print(pd.DataFrame(ss).query("policy==\"original\"").to_string(index=False))

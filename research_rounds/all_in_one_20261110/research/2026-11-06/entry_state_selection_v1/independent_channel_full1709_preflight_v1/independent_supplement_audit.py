from pathlib import Path
import json,hashlib,sys
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;V=O/"overlap";sys.path.insert(0,str(O));import engine
core={};exec((engine.P/"core.py").read_text(),core)
y=pd.read_parquet(V/"WINNER_FULL_HOLD_MARKET_STATES.parquet");r=pd.read_parquet(V/"WINNER_FULL_HOLD_RECEIPTS.parquet")
co=pd.read_csv(V/"WINNER_FULL_HOLD_FIXED_COHORT.csv");c=pd.read_csv(V/"WINNER_FULL_HOLD_COVERAGE.csv")
for f in [co,c]:
 for name in ["signal_day","entry_day","exit_day","old_signal_day","old_entry_day","old_exit_day","first_fresh_receipt_entry_to_exit","first_receipt_next_common_open"]:
  if name in f:f[name]=pd.to_datetime(f[name],format="mixed")
assert len(co)==108 and co.sid.nunique()==104 and co.round_id.is_unique
assert len(y)==9406 and len(r)==1844 and not y.duplicated(["round_id","day"]).any()
pd.testing.assert_frame_equal(r.reset_index(drop=True),y[y.receipt].reset_index(drop=True),check_exact=True)
cal=engine.full_cal;ci={d:i for i,d in enumerate(cal)};cc=c.set_index("round_id");results=[]
for z in co.itertuples():
 d=y[y.round_id.eq(z.round_id)].sort_values("day");expected=cal[(cal>=z.signal_day)&(cal<=z.exit_day)]
 np.testing.assert_array_equal(d.day.to_numpy(),expected.to_numpy())
 mask=d.day.ge(z.entry_day)&d.day.lt(z.exit_day)
 np.testing.assert_array_equal(d.in_original_entry_to_exit_close_interval,mask)
 h=d[mask];rr=h[h.receipt];out=cc.loc[z.round_id]
 assert len(h)==out.full_common_close_days and int(h.valid.sum())==out.price_known_days and len(rr)==out.fresh_receipts_entry_to_exit
 assert len(rr)>0 and rr.iloc[0].day==out.first_fresh_receipt_entry_to_exit
 assert cal[ci[rr.iloc[0].day]+1]==out.first_receipt_next_common_open<z.exit_day
 assert int(h.born.sum())==out.new_births_entry_to_exit
 assert not h.root_unknown.any() and h.valid.all()
 root=d.iloc[0].root_day;active=bool(d.iloc[0].active)
 if active:
  fails=h[h.root_day.eq(root)&h.failed];assert len(fails)==1
  assert cal[ci[fails.iloc[0].day]+1]==z.exit_day
 else:assert h.born.sum()==1
 assert out.market_exit_clock_vs_old_exit==("SAME_OPEN_AS_OLD_EXIT" if active else "NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL")
for sid in [sorted(co.sid.unique())[i] for i in [0,51,103]]:
 rows=y[y.sid.eq(sid)];cut=rows.day.max();q=engine.data(sid,cut);x=core["simulate"](q)
 for rid,g in rows.groupby("round_id"):
  pd.testing.assert_frame_equal(g.set_index("day")[x.columns],x.loc[g.day],check_exact=True,check_dtype=False,check_freq=False)
 results.append(dict(sid=sid,fullprefix_rows=len(q),saved_rows=len(rows),original_core_exact=True))
old=pd.read_parquet(O/"DAILY_STATES.parquet").set_index(["sid","day"])
shared=pd.MultiIndex.from_frame(y[["sid","day"]]).isin(old.index);yy=y[shared].copy();cols=[k for k in x.columns if k!="receipt_id"]
a=yy.set_index(["sid","day"]);b=old.loc[a.index]
pd.testing.assert_frame_equal(a[cols],b[cols],check_exact=True,check_dtype=False,check_freq=False)
summ=[]
for w,g in c.groupby("window"):
 no=g[~g.root_active_at_old_signal]
 delays=[ci[b]-ci[a] for a,b in zip(no.old_entry_day,no.first_fresh_receipt_entry_to_exit)]
 summ.append(dict(window=w,rounds=len(g),all_receipt_next_open_before_old_exit=True,signal_root_active=int(g.root_active_at_old_signal.sum()),later_new_root_from_initial_no_root=len(no),earlier_exit_clock=0,same_exit_clock=int(g.root_active_at_old_signal.sum()),no_root_first_receipt_delay_median=float(np.median(delays)),no_root_first_receipt_delay_max=int(max(delays)),entry_to_exit_receipts=int(g.fresh_receipts_entry_to_exit.sum())))
result=dict(winner_fullhold_rounds=108,unique_stocks=104,state_rows=len(y),receipt_rows_with_boundaries=len(r),shared_market_rows_exact=int(shared.sum()),independent_original_core_samples=results,summary=summ,not_economic_or_OOS=True)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.loads((V/"SUPPLEMENT_OUTPUT_HASHES.json").read_text())
assert sha(V/"OUTPUT_HASHES.json")==seal["immutable_baseline_seal_sha256"]
for name,h in seal["supplement_files"].items():assert sha(V/name)==h,("supplement hash",name)
source_checks={}
for name in ["WINNER_FULL_HOLD_QA.json","REPORTING_CLOCK_QA.json","WINNER_ENTRY_EXIT_SIZE_EXISTENCE_QA.json"]:
 qa=json.loads((V/name).read_text())
 for path,h in qa["source_hashes"].items():assert sha(path)==h,("source hash",path)
 source_checks[name]=len(qa["source_hashes"])
cache=pd.read_parquet(V/"RECEIPT_CONDITIONAL_OVERLAP.parquet")
exist=pd.read_csv(V/"WINNER_ENTRY_EXIT_SIZE_EXISTENCE.csv").set_index("round_id")
cached=[]
for z in c.itertuples():
 q=cache[cache.window.eq(z.window)&cache.sid.eq(z.sid)&cache.day.ge(z.old_entry_day)&cache.day.lt(z.old_exit_day)].sort_values("day")
 feasible=q[q.conditional_unstarted_target_feasible];assert len(feasible)>0
 first=feasible.iloc[0];saved=exist.loc[z.round_id]
 assert len(q)==saved.existing_size_cache_receipts_in_entry_exit and len(feasible)==saved.existing_size_cache_q_feasible_receipts_in_entry_exit
 assert first.day==pd.Timestamp(saved.first_observed_q_feasible_receipt_in_existing_size_cache)
 assert first.next_common_open_day==pd.Timestamp(saved.first_observed_q_feasible_next_common_open)<z.old_exit_day
 assert first.close_conditional_q==saved.first_feasible_size_Q
 cached.append(z.round_id)
dual=[]
for stage,z in [("BIRTH",cache[cache.window.eq("2022")&cache.born]),("ALL_FRONTIER_RECEIPTS",cache[cache.window.eq("2022")])]:
 m=z.conditional_unique_market_unstarted_candidate
 dual.append(dict(stage=stage,AB_unique=int(m.sum()),both_old_references_flat=int((m&z.old_fast_state_after_old_admission.eq("knownFLAT")).sum()),old_fast_held=int((m&z.old_fast_state_after_old_admission.eq("HELD")).sum()),old_fast_unknown=int((m&z.old_fast_state_after_old_admission.eq("UNKNOWN")).sum())))
result.update(supplement_sealed_files=len(seal["supplement_files"]),supplement_seal_sha256=sha(V/"SUPPLEMENT_OUTPUT_HASHES.json"),source_hash_checks=source_checks,strict_entry_to_exit_cached_size_feasible_rounds=len(cached),all_first_cached_feasible_open_before_old_exit=True,dual_reference2022=dual)
audit_path=O/"INDEPENDENT_FULL_AUDIT.json";final=json.loads(audit_path.read_text());prior_sha=sha(audit_path)
final["winner_and_exit_clock_supplement"]=result
final["design_gate"]=dict(ready_to_design_one_fixed_economic_contract=True,automatic_economic_run_permitted_by_this_audit=False,reason="Frozen market mechanics and bounded conditional opportunity are verified. This justifies specifying a single fixed economic contract, not a return improvement claim or direct execution.",must_freeze_before_any_trial=["Industry qualification and stock/sector ranking, including capital and slot competition.","Initial probe fixed-Q creation, strictly later fresh-receipt retries only for remaining Q-F, atomic consumption, terminal ACK and real responsibility reconciliation.","Exit and T+1 handling; market/source UNKNOWN never automatically sells or unlocks held responsibility.","One ADD target and conditions after actual probe completion; no receipt-based replenishment of a new 24000 budget.","Dated lot/fee/slippage/capacity policy and explicit unavailable/fill assumptions.","Cross-source bridge or isolation policy, especially the 2026-05-18 boundary.","Economic comparison universe/windows and stopping/acceptance criteria fixed before any result, with previously consumed samples and outcome-selected coverage labeled."])
final["limitations"] += ["The 108 old >=50% winner rounds are an ex-post selected diagnostic cohort across 104 stocks. Coverage, same earliest exit clock, and existence of a positive-Q receipt do not prove actual participation, same entry price, old return retention, or superiority.","All 108 have a cached positive-Q receipt in entry<=close<exit whose next OPEN is before the old exit; size was not recomputed for omitted full-hold dates, so the stored first feasible date is the first observed cached feasible date only.","Signal-time no-root cases acquire a later root. Their first hold-period receipt delay has medians 7 and 1 common sessions, maxima 18 and 10 in 2022 and 2024 respectively; no same-price inference is warranted."]
final["supplement_review_source_sha256"]=sha(Path(__file__))
final["pre_supplement_audit_sha256"]=prior_sha
final["completed_at_utc"]=str(pd.Timestamp.now(tz="UTC"))
audit_path.write_text(json.dumps(final,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,"item") else str(x))+"\n")
print(json.dumps(dict(status=final["status"],supplement=result,audit_sha256=sha(audit_path)),indent=2))

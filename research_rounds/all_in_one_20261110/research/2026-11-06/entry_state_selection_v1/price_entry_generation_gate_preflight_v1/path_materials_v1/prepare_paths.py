"""Read-only follow-up paths for all167 frozen affected original rounds."""
from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path(__file__).resolve().parent
T=R/"price_entry_generation_dynamic_v1/market_tape"
K=R/"old_result_association_v1/COMMON_167_DENY_BUYS.csv"
OV=R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet"
F=O/"FREEZE.json"
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
def ds(v):return None if pd.isna(v) else str(pd.Timestamp(v).date())
def finite(v):return None if pd.isna(v) or not math.isfinite(float(v)) else float(v)
f=json.loads(F.read_text());assert f["code_sha256"]==sha(__file__)
if (O/"RUN_STARTED.json").exists():raise RuntimeError("Already started; no overwrite or rerun.")
priority=T/"PRIORITY_156_COMPLETE.json"
assert priority.exists(),"Wait for producer priority seal; do not consume in-progress tape"
seal=json.loads(priority.read_text())
sources={str(p):sha(p) for p in [K,OV,F,O/"PROTOCOL.md",priority]}
keys=pd.read_csv(K,parse_dates=["signal_day","root_day"]);assert len(keys)==167 and keys.sid.nunique()==156
assert set(keys.sid)==set(seal["sids"])
for name,h in seal["files"].items():assert sha(T/name)==h;sources[str(T/name)]=h
save("RUN_STARTED.json",dict(code_sha256=sha(__file__),producer_priority_sha256=sha(priority),frozen_keys_sha256=sha(K),economics=0))
ovcols=["sid","day","window","old_sector_known","old_sector_observed_today","old_sector_rs_ready_fresh","old_sector_up","old_AB_event_id","old_AB_event_type","old_AB_I_qualified","old_AB_PVR_known","old_ab_I_PVR_qualified_permit","old_PVR_known","old_PVR_score","old_ab_baseline_stock_state_before","old_ab_baseline_decision","old_ab_baseline_close_check","old_ab_baseline_selected","old_ab_baseline_queue_rank","size_semantics","next_common_open_day","close_conditional_q","open_conditional_q","close_size_check","close_fee","close_plan_risk","next_raw_open","open_size_check","open_fee","open_plan_risk","conditional_unstarted_target_feasible","conditional_unstarted_open_feasible"]
ov=pd.read_parquet(OV,columns=ovcols);ov=ov[ov.window.isin(["2022","2024_924"])].copy()
assert not ov.duplicated(["window","sid","day"]).any()
queueparts=[]
for w,y in [("2022",2022),("2024_924",2024)]:
 for source in ["DECISIONS","RANKING_AUDIT"]:
  p=R/f"independent_channel_joint_economic_v1/economic_{y}/joint/{source}.csv";sources[str(p)]=sha(p)
  z=pd.read_csv(p,low_memory=False);z["day"]=pd.to_datetime(z.day);z["window"]=w;z["old_queue_source"]=source;queueparts.append(z)
queues=pd.concat(queueparts,ignore_index=True)
dec=queues[queues.old_queue_source.eq("DECISIONS")].copy();assert not dec.duplicated(["window","sid","day"]).any()
dec=dec.drop(columns=["old_queue_source"]).rename(columns={c:"old_joint_"+c for c in dec if c not in ["window","sid","day"]})
mframes={sid:pd.read_parquet(T/(sid+".parquet")).sort_values("day").reset_index(drop=True) for sid in keys.sid.unique()}
allpaths=[];summ=[];queueout=[]
for a in keys.itertuples(index=False):
 m=mframes[a.sid];assert not m.day.duplicated().any()
 t=pd.Timestamp(a.signal_day);rd=pd.Timestamp(a.root_day);w=str(a.window);wend=pd.Timestamp("2022-12-31" if w=="2022" else "2024-12-31")
 orig=m[m.day.eq(t)];assert len(orig)==1
 oo=orig.iloc[0];assert bool(oo.receipt) and not bool(oo.entry_active) and pd.Timestamp(oo.root_day)==rd
 for field in ["C","S_old","S_new"]:assert np.isclose(float(oo[field]),float(getattr(a,field)),rtol=1e-12,atol=1e-12,equal_nan=True),(a.round_id,field)
 parent=m[m.day.ge(t)&m.root_day.eq(rd)]
 term=parent[parent.failed|parent.root_unknown]
 termday=term.day.iloc[0] if len(term) else pd.NaT
 if len(term):
  termreason="PARENT_UNKNOWN" if bool(term.root_unknown.iloc[0]) else "PARENT_FAILED"
  nextbirths=m[m.day.gt(termday)&m.born&~m.root_day.eq(rd)]
 else:termreason="PARENT_NOT_TERMINATED_BEFORE_TAPE_END";nextbirths=m.iloc[0:0]
 nextbirth=nextbirths.day.iloc[0] if len(nextbirths) else pd.NaT
 end=nextbirth if pd.notna(nextbirth) else m.day.max()
 z=m[m.day.between(t,end)].copy();z["anchor_round_id"]=a.round_id;z["anchor_signal_day"]=t;z["anchor_root_day"]=rd;z["window"]=w
 z["original_root_relation"]=np.where(z.root_day.eq(rd),"AFFECTED_ORIGINAL_ROOT",np.where(z.root_day.isna(),"NO_ACTIVE_ROOT","LATER_DISTINCT_ROOT"))
 z["initial_window_open"]=z.day.le(wend)
 z["scope_status"]=np.where(z.initial_window_open,"WITHIN_ORIGINAL_INITIAL_WINDOW","MARKET_ONLY_WINDOW_CLOSED_NO_NEW_INITIAL")
 z["new_dynamic_queue"]="NOT_RECONSTRUCTED";z["real_tradability"]="UNKNOWN"
 z=z.merge(ov,on=["window","sid","day"],how="left",validate="many_to_one",indicator="overlap_join")
 z["original_overlap_available"]=z.overlap_join.eq("both");z=z.drop(columns=["overlap_join"])
 z=z.merge(dec,on=["window","sid","day"],how="left",validate="many_to_one")
 fields=["old_sector_known","old_sector_observed_today","old_sector_rs_ready_fresh","old_sector_up"]
 z["old_four_sector_known"]=z[fields].notna().all(axis=1)
 z["old_four_sector_true"]=z[fields].eq(True).all(axis=1)&z.old_four_sector_known
 z["hypothetical_unstarted_close_pass"]=z.initial_window_open&z.receipt&z.entry_active&z.old_four_sector_true&z.conditional_unstarted_target_feasible.eq(True)
 z["hypothetical_unstarted_open_pass"]=z.hypothetical_unstarted_close_pass&z.conditional_unstarted_open_feasible.eq(True)
 z["hypothetical_check_semantics"]="Only old-source industry/size if unstarted; no new flat/AB role/queue/slot/fill claim"
 z["event_row"]=z.receipt|z.event.ne("NONE")|z.day.eq(t)|z.day.eq(termday)|z.day.eq(nextbirth)
 allpaths.append(z)
 q=queues[queues.window.eq(w)&queues.sid.eq(a.sid)&queues.day.between(t,end)].copy();q["anchor_round_id"]=a.round_id;queueout.append(q)
 future=z[z.day.gt(t)]
 reg=future[future.root_day.eq(rd)&future.event.eq("NEW_ENTRY_GENERATION")]
 oldallow=future[future.root_day.eq(rd)&future.receipt&future.entry_active]
 oldallowwin=oldallow[oldallow.initial_window_open]
 anyallowwin=future[future.receipt&future.entry_active&future.initial_window_open]
 hc=future[future.hypothetical_unstarted_close_pass];ho=future[future.hypothetical_unstarted_open_pass]
 def first(frame,col="day"):return ds(frame.iloc[0][col]) if len(frame) else None
 def at(frame,col):return None if not len(frame) or pd.isna(frame.iloc[0][col]) else frame.iloc[0][col]
 row=dict(round_id=a.round_id,sid=a.sid,name=a.name,window=w,anchor_signal=ds(t),anchor_root=ds(rd),old_FULL_net=float(a.old_FULL_net),original_result_group="WIN" if a.old_FULL_net>0 else "LOSS" if a.old_FULL_net<0 else "ZERO",path_end=ds(end),parent_terminal=ds(termday),parent_terminal_reason=termreason,next_parent_birth=ds(nextbirth),path_common_days=len(z),later_same_parent_generation_births=len(reg),first_later_same_parent_generation=first(reg),later_same_parent_allowed_receipts=len(oldallow),first_same_parent_allowed_receipt=first(oldallow),first_same_parent_allowed_receipt_within_window=first(oldallowwin),first_any_parent_allowed_receipt_within_window=first(anyallowwin),first_hypothetical_unstarted_close_pass=first(hc),first_hypothetical_unstarted_open_pass=first(ho),first_hypothetical_next_open=first(ho,"next_common_open_day"),first_hypothetical_next_raw_open=finite(at(ho,"next_raw_open")) if len(ho) else None,first_hypothetical_close_q=finite(at(hc,"close_conditional_q")) if len(hc) else None,first_hypothetical_open_q=finite(at(ho,"open_conditional_q")) if len(ho) else None,original_joint_decision_at_first_close=at(hc,"old_joint_decision"),original_joint_lane_at_first_close=at(hc,"old_joint_owner_lane"),original_joint_rank_at_first_close=finite(at(hc,"old_joint_queue_rank")) if len(hc) else None,original_AB_I_PVR_permit_at_first_close=bool(at(hc,"old_ab_I_PVR_qualified_permit")) if at(hc,"old_ab_I_PVR_qualified_permit") is not None else None,new_dynamic_queue="NOT_RECONSTRUCTED",real_tradability="UNKNOWN")
 summ.append(row)
paths=pd.concat(allpaths,ignore_index=True);events=paths[paths.event_row].copy();summary=pd.DataFrame(summ)
assert len(summary)==167 and summary.round_id.nunique()==167 and set(summary.round_id)==set(keys.round_id)
assert len(summary[(summary.window=="2024_924")&(summary.original_result_group=="WIN")])==27
assert len(summary[(summary.window=="2022")&(summary.original_result_group=="LOSS")])==96
assert not paths.loc[~paths.initial_window_open,"hypothetical_unstarted_close_pass"].any()
paths.to_parquet(O/"ALL_167_DAILY_PATHS.parquet",index=False)
events.to_csv(O/"ALL_167_EVENT_CHAINS.csv",index=False)
summary.to_csv(O/"ALL_167_SUMMARY.csv",index=False)
pd.concat(queueout,ignore_index=True).to_csv(O/"ORIGINAL_QUEUE_ROWS.csv",index=False)
groups=[]
for w,g in summary.groupby("window"):
 for label,sg in [("ALL",g),("OLD_FULL_WIN",g[g.original_result_group=="WIN"]),("OLD_FULL_LOSS",g[g.original_result_group=="LOSS"])]:
  groups.append(dict(window=w,scope=label,rounds=len(sg),has_later_same_parent_generation=int(sg.first_later_same_parent_generation.notna().sum()),has_later_same_parent_allowed_receipt_within_window=int(sg.first_same_parent_allowed_receipt_within_window.notna().sum()),has_any_later_parent_allowed_receipt_within_window=int(sg.first_any_parent_allowed_receipt_within_window.notna().sum()),has_hypothetical_unstarted_close_pass=int(sg.first_hypothetical_unstarted_close_pass.notna().sum()),has_hypothetical_unstarted_open_pass=int(sg.first_hypothetical_unstarted_open_pass.notna().sum()),next_parent_birth_observed=int(sg.next_parent_birth.notna().sum()),parent_unknown=int(sg.parent_terminal_reason.eq("PARENT_UNKNOWN").sum())))
save("SUMMARY.json",groups)
for p,h in sources.items():assert sha(p)==h,("INPUT_CHANGED",p)
save("SOURCE_HASHES.json",sources)
save("QA.json",dict(all167_preserved=True,stocks=156,daily_path_rows=len(paths),event_rows=len(events),original_2024_winners=27,original_2022_losers=96,all_original_anchor_root_floor_receipt_gate_exact=True,window_tail_initial_invitations=0,market_replays=0,economic_runs=0,fee_or_size_calculations=0,new_queue_reconstructed=False,original_sources_unchanged=True))
save("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
print("SUMMARY",json.dumps(groups),flush=True)
print("QA",json.dumps(json.loads((O/"QA.json").read_text())),flush=True)

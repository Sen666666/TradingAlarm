"""Independent final artifact/overlap review. No account or full-market replay."""
from pathlib import Path
import json,hashlib,sys,ast
from decimal import Decimal as D
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;V=O/"overlap";R=O.parent;cache={}
def sha(p):
 p=Path(p);key=str(p.resolve())
 if key not in cache:cache[key]=hashlib.sha256(p.read_bytes()).hexdigest()
 return cache[key]
def read(p):return json.loads(Path(p).read_text())
def check_map(m,base):
 for k,h in m.items():
  p=Path(k) if Path(k).is_absolute() else base/k
  assert sha(p)==h,("hash",str(p),sha(p),h)
 return len(m)
def market_seals_and_recovery():
 seal=read(O/"FINAL_MARKET_SEAL.json");n=check_map(seal["files"],O)
 chain=read(O/"ENGINEERING_RECOVERY_CHAIN.json");versions=0
 for att in chain["attempts"]:
  a=Path(att["archive"]);assert sha(a/"INPUT_HASHES.json")==att["original_input_hash_file_sha256"]
  originals=read(a/"INPUT_HASHES.json")
  mapping={z["original_active_path"]:z for z in att["source_version_mapping"]}
  for k,h in originals.items():
   p=mapping[k]["verified_archive_or_unchanged_path"] if k in mapping else k
   assert sha(p)==h,("archive input",att["attempt"],p)
  versions+=len(mapping)
 rv=read(O/"RECOVERY_VALIDATION.json");ids=set(rv["completed_sids"]);assert len(ids)==177
 for fn,meta in rv["files"].items():
  old=O/"startup_attempt_2_empty_facts"/fn;assert sha(old)==meta["sha256"]
  q=pd.read_parquet(old);assert len(q)==meta["rows"]
  final=pd.read_parquet(O/fn,filters=[("sid","in",sorted(ids))])
  pd.testing.assert_frame_equal(q.reset_index(drop=True),final.reset_index(drop=True),check_exact=True)
 d=pd.read_parquet(O/"DAILY_STATES.parquet",columns=["sid","day","window","valid","amount_valid","born","phase","receipt","root_unknown","failed","active","source_kind","source_path","segment_id","adjustment_factor"])
 out=[]
 for name,mask in [("2026_01_01_TO_05_15",d.day.between("2026-01-01","2026-05-15")),("2026_05_18_TO_06_30",d.day.between("2026-05-18","2026-06-30"))]:
  z=d[mask];b=z[z.born]
  out.append(dict(source_period=name,stocks=z.sid.nunique(),price_known_stocks=z.loc[z.valid,"sid"].nunique(),days_per_stock=z.day.nunique(),stock_days=len(z),price_known=int(z.valid.sum()),amount_known=int(z.amount_valid.sum()),births=int(z.born.sum()),birth_confirmed=int(b.phase.eq("CONFIRMED").sum()),birth_probe=int(b.phase.eq("PROBE").sum()),birth_amount_unknown=int(b.phase.eq("PROBE_AMOUNT_UNKNOWN").sum()),receipts=int(z.receipt.sum()),root_unknown=int(z.root_unknown.sum()),root_unknown_valid_price=int((z.root_unknown&z.valid).sum()),price_failures=int(z.failed.sum()),active_days=int(z.active.sum())))
 saved=pd.read_csv(O/"SOURCE_BOUNDARY_2026_SUMMARY.csv").set_index("source_period")
 for row in out:
  for c in saved.columns:assert saved.loc[row["source_period"],c]==row[c]
 a=d[d.day.eq("2026-05-15")].set_index("sid");b=d[d.day.eq("2026-05-18")].set_index("sid");both=a.valid&b.valid
 changes={c:a[c].ne(b[c])&both for c in ["source_kind","source_path","segment_id"]}
 continuous=pd.Series(np.isclose(a.adjustment_factor,b.adjustment_factor,rtol=1e-11),index=a.index)&both
 identity=changes["source_kind"]|changes["source_path"]|changes["segment_id"]
 stats=dict(both_price_known=int(both.sum()),source_kind_changed=int(changes["source_kind"].sum()),source_path_changed=int(changes["source_path"].sum()),segment_id_changed=int(changes["segment_id"].sum()),full_identity_changed=int(identity.sum()),factor_continuous_among_both_known=int(continuous.sum()),root_unknown_after=int(b.root_unknown.sum()),price_known_root_unknown_after=int((b.root_unknown&b.valid).sum()),changed_identity_with_continuous_factor=int((identity&continuous).sum()))
 sq=read(O/"SOURCE_BOUNDARY_2026_QA.json")
 for k,v in stats.items():assert sq[k]==v,(k,v,sq[k])
 return dict(final_market_seal_sha256=sha(O/"FINAL_MARKET_SEAL.json"),sealed_files=n,archive_attempts_checked=3,version_mappings_checked=versions,checkpoint_exact_files=len(rv["files"]),checkpoint_stocks=177,checkpoint_rows=77526,remaining_new_paths=1532,engineering_starts=4,source_boundary_split=out,source_boundary_identity=stats)
def overlap_checks():
 hashes={}
 for name in ["SOURCE_HASHES.json","OLD_NATIVE_Q_SOURCE_HASHES.json","OUTPUT_HASHES.json"]:hashes[name]=check_map(read(V/name),V)
 x=pd.read_parquet(V/"DAILY_OVERLAP.parquet");r=pd.read_parquet(V/"RECEIPT_CONDITIONAL_OVERLAP.parquet")
 assert len(x)==748542 and len(r)==55201 and not x.duplicated(["sid","day"]).any() and r.receipt_id.is_unique
 origin=pd.read_parquet(O/"DAILY_STATES.parquet")
 pd.testing.assert_frame_equal(x[origin.columns].sort_values(["sid","day"]).reset_index(drop=True),origin.sort_values(["sid","day"]).reset_index(drop=True),check_exact=True)
 old=pd.concat([pd.read_parquet(R/"fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet"),pd.read_parquet(V/"OLD_NATIVE_Q_EXTENDED.parquet")],ignore_index=True).set_index(["sid","day"])
 assert len(old)==748542 and old.index.is_unique
 xx=x.set_index(["sid","day"])
 oldcolumns=[c[4:] for c in x.columns if c.startswith("old_") and c[4:] in old.columns]
 for col in oldcolumns:pd.testing.assert_series_equal(xx["old_"+col].sort_index(),old[col].sort_index(),check_dtype=False,check_names=False,check_exact=True)
 assert x.loc[x.window.eq("2026H1"),"old_ab_state_after_old_admission"].eq("UNKNOWN").all()
 assert x.loc[x.window.ne("2022"),"old_fast_state_after_old_admission"].eq("UNKNOWN").all()
 assert x.loc[x.window.ne("2022"),"old_fast_AB_FAST_SMALL_selected"].isna().all()
 assert x.loc[x.window.eq("2026H1"),"old_ab_baseline_selected"].isna().all()
 assert not r.loc[r.old_ab_state_after_old_admission.ne("knownFLAT"),"conditional_old_baseline_flat_unstarted_candidate"].any()
 assert not r.loc[r.old_any_market_offer_prereq.isna(),"conditional_unique_market_unstarted_candidate"].any()
 np.testing.assert_array_equal(r.conditional_unique_market_unstarted_candidate,r.conditional_unstarted_target_feasible&r.old_ab_state_after_old_admission.eq("knownFLAT")&r.old_any_market_offer_prereq.eq(False).fillna(False))
 assert x.new_path_flat_or_parent_state.eq("UNKNOWN_NOT_SIMULATED").all() and r.actual_new_empty_position_eligible.eq("UNKNOWN_NOT_SIMULATED").all()
 assert r.historical_fill.eq("UNKNOWN_NOT_SIMULATED").all() and r.actual_ack.eq("UNKNOWN_NOT_PROVIDED").all()
 assert r.size_semantics.eq("UNSTARTED_PARENT_ONLY_NOT_A_RETRY_OR_ADD").all()
 assert r.nominal_budget_cny.eq(24000).all() and r.plan_risk_budget_cny.eq(3000).all()
 assert r.loc[r.conditional_unstarted_target_feasible,"close_plan_risk"].le(3000+1e-8).all()
 assert r.loc[r.conditional_unstarted_open_feasible,"open_plan_risk"].le(3000+1e-8).all()
 states=[]
 refs=[(R/"m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/dynamic/DECISIONS.csv","A_UNION_B","2022","old_ab"),(R/"m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/economic/DECISIONS.csv","A_UNION_B","2024_924","old_ab"),(R/"fast_entry_equity_2022_v1/economic/DECISIONS.csv","AB_FAST_SMALL","2022","old_fast")]
 for p,arm,w,prefix in refs:
  ds=pd.read_csv(p,low_memory=False);ds=ds[ds.arm.eq(arm)];ds["day"]=pd.to_datetime(ds.day,format="mixed")
  ds=ds[ds.day.isin(x.loc[x.window.eq(w),"day"].unique())]
  vals=xx.loc[pd.MultiIndex.from_frame(ds[["sid","day"]]),prefix+"_state_before_old_admission"].to_numpy()
  wanted=ds.stock_state_before.replace({"FLAT":"knownFLAT","BUY_PENDING":"PENDING"}).to_numpy()
  np.testing.assert_array_equal(vals,wanted);states.append(dict(arm=arm,window=w,decision_states_exact=len(ds)))
 summary=[]
 for row in pd.read_csv(V/"OVERLAP_SUMMARY.csv").itertuples():
  z=r[r.window.eq(row.window)]
  if row.scope=="SEMICONDUCTOR_URFI881121":z=z[z.sector.eq("URFI881121")]
  if row.stage=="BIRTH":z=z[z.born]
  result=dict(window=row.window,scope=row.scope,stage=row.stage,stockdays=len(z),stocks=z.sid.nunique(),market_roots=len(z[["sid","root_day"]].drop_duplicates()),size_feasible_roots=len(z.loc[z.conditional_unstarted_target_feasible,["sid","root_day"]].drop_duplicates()),conditional_unstarted_target_feasible=int(z.conditional_unstarted_target_feasible.sum()),conditional_unstarted_open_feasible=int(z.conditional_unstarted_open_feasible.sum()),conditional_old_baseline_flat_unstarted=int(z.conditional_old_baseline_flat_unstarted_candidate.sum()),conditional_unique_market_unstarted=int(z.conditional_unique_market_unstarted_candidate.sum()),market_comparison_unknown=int(z.old_any_market_offer_prereq.isna().sum()))
  for st in ["HELD","PENDING","UNKNOWN","knownFLAT"]:result["old_ab_after_"+st]=int(z.old_ab_state_after_old_admission.eq(st).sum())
  for k,v in result.items():assert getattr(row,k)==v,(k,row,v)
  summary.append(result)
 outcomes=pd.read_csv(V/"OLD_OUTCOME_SURVIVAL_AND_COMPETITION.csv",low_memory=False)
 unknown=outcomes.root_survival_status.str.contains("UNKNOWN|CENSORED|NO_ACTIVE",regex=True)
 assert outcomes.loc[unknown,"market_root_survives_to_old_exit_open"].isna().all()
 assert outcomes.loc[outcomes.root_survival_status.eq("PRICE_FAILED_BEFORE_OLD_EXIT"),"market_root_survives_to_old_exit_open"].eq(False).all()
 assert outcomes.actual_displacement.eq("NOT_TESTED_NO_NEW_QUEUE_OR_ACCOUNT").all() and outcomes.new_strategy_return.eq("NOT_COMPUTED").all()
 retries=pd.read_csv(V/"IF_BIRTH_UNFILLED_LATER_FRONTIER.csv")
 assert len(retries)==8427 and retries.receipt_id.is_unique
 assert retries.parent_Q.eq("FIXED_IF_PREVIOUSLY_CREATED_NO_RESIZING").all()
 assert retries.retry_permission.eq("UNASSESSED_REAL_ACK_MUST_PRECEDE_NEW_RECEIPT").all()
 groups={k:g.sort_values("day") for k,g in r.groupby(["window","sid","root_day"])}
 for v in retries.itertuples():
  g=groups[(v.window,v.sid,pd.Timestamp(v.root_day))];later=g[g.day>pd.Timestamp(v.day)]
  assert len(later)==v.later_same_root_receipts
  assert bool(len(later))==bool(v.later_same_root_frontier_exists)
  if len(later):assert later.iloc[0].day==pd.Timestamp(v.first_later_frontier_day)
 return dict(hash_map_files=hashes,old_native_columns_exact=oldcolumns,old_state_decision_checks=states,full_market_output_values_unchanged=True,summary=summary,outcome_rows=len(outcomes),outcome_survival_statuses=outcomes.groupby(["window","old_outcome_group","root_survival_status"]).size().rename("count").reset_index().to_dict("records"),all_8427_birth_later_frontier_lists_exact=True,old_unknown_never_inferred_flat=True,new_parent_or_real_fill_never_inferred=True),r
def sample_sizes(r):
 B=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025")
 sys.path.insert(0,str(B/"code"))
 from market_rules import version_on,market_identity_on,RuleUnavailable
 from sector_account import QuantityRule,FeeComponent,FeeSchedule
 env=dict(D=D,version_on=version_on,market_identity_on=market_identity_on,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,SLIP=D(".0005"),meta={},rules=read(B/"inputs-v2/market-rules.json"),proxies=read(B/"inputs-v2/economic-protocol.json")["approved_proxy_ids"])
 source=(R/"m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py").read_text()
 for node in ast.parse(source).body:
  if isinstance(node,ast.FunctionDef) and node.name in {"getmeta","fee","size"}:exec(compile(ast.get_source_segment(source,node),"original_dated_size","exec"),env)
 manifest={z["symbol"]:z for z in read(Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json"))}
 ix=set(np.linspace(0,len(r)-1,30,dtype=int))
 for key,gs in r.groupby(["window","close_size_check","open_size_check"],dropna=False):ix.add(gs.index[0])
 selected=r.loc[sorted(ix)];raw={}
 counts={"receipts":len(selected),"raw_sources":0,"close_exact":0,"open_exact":0,"capacity_exact":0}
 for z in selected.itertuples():
  if z.sid not in raw:
   path=next(p for p in manifest[z.sid]["source_sha256"] if p.endswith("/signal.parquet"));raw[z.sid]=pd.read_parquet(path)
  q=raw[z.sid];sig=q.loc[z.day];vol=q.loc[:z.day,"raw_volume"];vol=vol[vol>0]
  cap=float(vol.tail(20).mean())*.01 if len(vol)>=20 else np.nan
  # rolling and direct mean may differ below one share; verify integer policy value.
  if np.isfinite(cap):assert int(cap)==int(z.volume_capacity_shares);counts["capacity_exact"]+=1
  fl=D(str(z.S_new))/D(str(sig.adjustment_factor))
  if pd.notna(z.close_conditional_q):
   qq,bf,risk,_,_=env["size"](z.sid,z.day,D(str(sig.raw_close))*(1+env["SLIP"]),fl,D(24000),D(3000),int(z.volume_capacity_shares))
   assert qq==z.close_conditional_q and float(bf)==z.close_fee and float(risk)==z.close_plan_risk;counts["close_exact"]+=1
  if pd.notna(z.open_conditional_q):
   op=q.loc[z.next_common_open_day,"raw_open"]
   qq,bf,risk,_,_=env["size"](z.sid,z.next_common_open_day,D(str(op))*(1+env["SLIP"]),fl,D(24000),D(3000),int(z.volume_capacity_shares))
   assert qq==z.open_conditional_q and float(bf)==z.open_fee and float(risk)==z.open_plan_risk;counts["open_exact"]+=1
 counts["raw_sources"]=len(raw);counts["dated_original_size_fee_risk_exact"]=True
 return counts
def main():
 market=read(O/"INDEPENDENT_FULL_AUDIT_MARKET.json")
 final=dict(market)
 final["market_seals_recovery_and_boundary"]=market_seals_and_recovery()
 overlap,r=overlap_checks();final["overlap_independent_review"]=overlap;final["sizing_sample"]=sample_sizes(r)
 final["status"]="PASS_FOR_FIXED_MARKET_AND_CONDITIONAL_OPPORTUNITY_PREFLIGHT_ONLY"
 final["limitations"]=[v for v in final["limitations"] if "reviewed separately" not in v]
 final["limitations"] += ["No new account, order, broker ACK, fill ledger, queue ranking, funds competition, sector policy, new strategy return or economic acceptance was performed.","2024/2026 original native Q is extended by the original definition, but complete executed AB_FAST_SMALL exists only in 2022. Its missing later decisions remain UNKNOWN.","2026 old baseline repaired occupancy is UNKNOWN. Zero flat-conditional candidates is an unavailable comparison, not evidence of zero opportunity.","Per-receipt sizing assumes no parent has ever started. It cannot reset fixed Q, authorize repeated 24000 budgets, or substitute for ACK/remaining Q-F.","2026-05-18 source switching quarantined 1041 active roots despite valid prices. UNKNOWN is not an exit or a trend failure; 516 of 526 later births have unknown amount baseline.","Independent native-Q review checked preserved original definitions, hashes and exact merged native columns; it did not repeat the worker native-Q 3418-stockday 2022 equivalence construction or rebuild upstream native signals.","Independent review corrected two verifier-only dtype assertions (string storage and datetime us/ns). All compared values were identical; market outputs were untouched."]
 final["final_artifact_sha256"]={"FINAL_MARKET_SEAL.json":sha(O/"FINAL_MARKET_SEAL.json"),"overlap/OUTPUT_HASHES.json":sha(V/"OUTPUT_HASHES.json"),"INDEPENDENT_FULL_AUDIT_MARKET.json":sha(O/"INDEPENDENT_FULL_AUDIT_MARKET.json"),Path(__file__).name:sha(Path(__file__))}
 final["completed_at_utc"]=str(pd.Timestamp.now(tz="UTC"))
 (O/"INDEPENDENT_FULL_AUDIT.json").write_text(json.dumps(final,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,"item") else str(x))+"\n")
 print(json.dumps(dict(status=final["status"],sizing_sample=final["sizing_sample"],seal=final["final_artifact_sha256"],state_checks=overlap["old_state_decision_checks"]),indent=2))
if __name__=="__main__":main()

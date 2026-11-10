"""Pre-economic source/interface/accounting audit. Never calls run_window or run_fixed."""
from pathlib import Path
import ast, copy, datetime, json, types
import numpy as np
import pandas as pd
import adapter as ad
import report as rp

O = Path(__file__).resolve().parent
CODE_FILES = ["prepare_features.py", "adapter.py", "report.py", "run.py", "test_non_economic.py", "CONTRACT.json"]
audited_implementation_hashes = {n: ad.sha(O / n) for n in CODE_FILES}
contract = json.loads((O / "CONTRACT.json").read_text())
for path, expected in contract["source_hashes"].items(): assert ad.sha(path) == expected
for name in CODE_FILES[:-1]: ast.parse((O / name).read_text())
assert contract["arms"] == ad.ARMS == ["A_UNION_B", "RAW_MOM11", "CH3_RM"]
assert contract["windows"] == {"2022": ["2022-01-01", "2022-12-31"], "2024_924": ["2024-09-01", "2024-12-31"]}
assert contract["management_end"] == "2026-06-30"
fa = json.loads((O / "INDEPENDENT_FULL_FEATURE_AUDIT.json").read_text())
assert fa["status"] == "PASS" and fa["feature_seal_sha256"] == ad.sha(O / "FEATURE_SEAL.json")
tests = json.loads((O / "NON_ECONOMIC_QA.json").read_text())
assert tests["synthetic_permutation_cases"] == 6000 and tests["no_economic_paths_executed"]
assert not (O / "RUN_ONCE.json").exists()

# Exercise the actual queue installation against mocked original feasibility inputs.
rows = []
features = []
for i, sid in enumerate(list("ABCDEFGH")):
    rows.append(dict(event_id=sid, window="2022", day=pd.Timestamp("2022-05-09"), sid=sid, name=sid, industry="test", sector="SEC", event_type="A_SECTOR_BIRTH", PVR_score=100-i, I_qualified=sid!="B", PVR_known=sid!="C", relative_known=False, relative_event=0, close_ok=sid!="D"))
    features.append(dict(sid=sid, month="2022-05", status=ad.KNOWN if sid!="E" else "UNKNOWN_MONTH_END_PRICE", RM={"F":-.5,"G":10,"H":-.5}.get(sid,1), RAW_MOM11={"F":1,"G":0,"H":1}.get(sid,1), max_input_date="2022-04-29"))
native_calls=[]
def native(g, states, arm):
    native_calls.append(arm)
    return ["NATIVE_QUEUE"]
s = types.SimpleNamespace(queue=native, SOURCE=ad.E/"relative_priority_v1/simulate.py", hashes={}, np=np, pd=pd, true=lambda x:bool(x), finite=lambda x:bool(np.isfinite(x)), checkclose=lambda r:{"close_check":"PASS" if r["close_ok"] else "MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE"}, ranking_audit=[])
ad.install(s, pd.DataFrame(features))
states={"A":{"state":"HELD"}}
g=pd.DataFrame(rows)
assert s.queue(g,states,"A_UNION_B")==["NATIVE_QUEUE"] and native_calls==["A_UNION_B"]
out=s.queue(g,states,"CH3_RM")
assert [r["sid"] for r in out]==list("ABCDEGFH")
audit=pd.DataFrame(s.ch3_audit)
assert set(audit[audit.new_slot_selected].sid)=={"E","G"}
assert audit.set_index("sid").loc["E","old_feasible_rank"]==audit.set_index("sid").loc["E","new_feasible_rank"]==1
s.ch3_audit=[]
out=s.queue(g,states,"RAW_MOM11")
assert [r["sid"] for r in out]==list("ABCDEFHG")
audit=pd.DataFrame(s.ch3_audit)
assert set(audit[audit.new_slot_selected].sid)=={"E","F"}
lookup={(r["sid"],r["month"]):r for r in features}
lookup.pop(("H","2022-05"))
try:
    ad.reorder_known(copy.deepcopy(rows),set("EFGH"),"CH3_RM",lookup,[])
except AssertionError as e:
    assert "MISSING_PRECOMPUTED_FEATURE_IS_FATAL" in str(e)
else:
    raise AssertionError("Missing feature cache did not stop")
interface_checks=dict(native_baseline_queue_untouched=True, live_state_I_PVR_close_feasibility_preserved=True,
                      infeasible_positions_preserved=True, unknown_feasible_slots_preserved=True,
                      fixed_min2_rule_not_equal_actual_trade_counts=True, negative_scores_eligible=True,
                      PVR_sid_tie_break_preserved=True, missing_cache_fatal=True)

# Import unchanged repaired engines for setup and financial attribution only.
# Existing source ledgers are read; no engine lifecycle method is invoked.
import_checks={}
attribution_checks={}
all_features=pd.read_csv(O/"ALL_MARKET_STOCK_MONTH_FEATURES.csv",float_precision="round_trip")
for window in ["2022","2024_924"]:
    engine=ad.load_engine(window)
    assert engine.END==pd.Timestamp("2026-06-30") and engine.NET==engine.D(".8")
    assert engine.NAV==engine.D("1200000") and engine.INIT==engine.D("24000") and engine.SLOT==engine.D("48000")
    assert engine.RISK==engine.D("3000") and engine.SLIP==engine.D(".0005")
    assert len(engine.EVENTS)==({"2022":436,"2024_924":165}[window])
    assert len(engine.ev)==({"2022":12917,"2024_924":6878}[window])
    source_text=ad.ENGINES[window].read_text()
    original=next(n for n in ast.parse(source_text).body if isinstance(n,ast.FunctionDef) and n.name=="run_window")
    if window=="2024_924":
        code=ast.get_source_segment(source_text,original)
        changed=code.replace(" assert arm=='A_UNION_B','Only unchanged A+B baseline authorized'\n"," assert arm in APPROVED_CH3_ARMS\n")
        replacement=ast.parse(changed).body[0]
        assert ast.dump(ast.Module(body=original.body[1:],type_ignores=[]))==ast.dump(ast.Module(body=replacement.body[1:],type_ignores=[]))
        assert engine.START==pd.Timestamp("2024-09-01") and engine.BIRTH_END==pd.Timestamp("2024-12-31")
    lookup=ad.install(engine,all_features)
    assert all((r.sid,str(pd.Period(r.day,freq="M"))) in lookup for r in engine.ev.itertuples())
    assert not any([engine.rounds,engine.actions,engine.decisions,engine.archives,engine.claims])
    src=ad.OLD_OUTPUTS[window]
    z,cov=rp.derive_original_report(engine,window,src)
    z=z[z.arm.eq("A_UNION_B")].copy()
    expected=pd.read_csv(ad.ENGINES[window].parent/"report/CORE_AND_FULL_ROUNDS.csv",float_precision="round_trip",low_memory=False)
    expected=expected[expected.arm.eq("A_UNION_B")]
    attribution_checks[window]=ad.compare_table(z,expected,["round_id"])
    actions=pd.read_csv(src/"ACTIONS.csv",float_precision="round_trip",low_memory=False)
    actions=actions[actions.arm.eq("A_UNION_B")]
    enriched=rp.add_gross(z,actions)
    complete=enriched[enriched.status.eq(rp.CLOSED)]
    for layer,net in [("core","core_net"),("full","net_pnl")]:
        dividends=complete["core_dividend_net80" if layer=="core" else "full_dividend_net80"]
        reconstructed=complete[layer+"_gross_raw_open_pnl"]-complete[layer+"_slippage_drag"]-complete[layer+"_fees"]+dividends
        assert np.allclose(reconstructed,complete[net],rtol=1e-12,atol=1e-7)
    assert not any([engine.rounds,engine.actions,engine.decisions,engine.archives,engine.claims])
    import_checks[window]=dict(read_only_engine_setup=True, full_potential_feature_keys=len(engine.ev),
                               finite_admitted_equity_events=len(engine.EVENTS), no_lifecycle_invoked=True,
                               original_core_and_financial_attribution_reproduced=len(z), gross_fee_dividend_identity_checked=len(complete))

# Gate shape and status distinctions reviewed against the current frozen source.
driver=(O/"run.py").read_text()
assert "(O/'RUN_ONCE.json').open('x')" in driver
assert "audit['result']=='PASS_PRE_ECONOMIC_IMPLEMENTATION'" in driver
assert "authorization['explicit_parent_start'] is True" in driver
assert "checks=bridge_compare(s,window)" in driver and "report_arm(s,window,arm,dest)" in driver
assert "s.reset(True,'FULL')" in driver
assert not (O/"RUN_ONCE.json").exists()
for path,expected in contract["source_hashes"].items():assert ad.sha(path)==expected
assert {n: ad.sha(O / n) for n in CODE_FILES} == audited_implementation_hashes, "Implementation changed during audit"
result=dict(result="PASS_PRE_ECONOMIC_IMPLEMENTATION",audited_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            implementation_hashes=audited_implementation_hashes,
            independent_full_feature_audit_sha256=ad.sha(O/"INDEPENDENT_FULL_FEATURE_AUDIT.json"),
            non_economic_qa_sha256=ad.sha(O/"NON_ECONOMIC_QA.json"),
            feature_seal_sha256=ad.sha(O/"FEATURE_SEAL.json"),source_hashes_checked=len(contract["source_hashes"]),
            interface_checks=interface_checks,engine_setup_and_accounting_checks=import_checks,
            original_report_reproduction=attribution_checks,
            execution_scope="One fixed 2022 and 2024 three-arm FULL per-stock lifecycle comparison. Parent must separately authorize start. No shared account, FAST, refit, sign flip, parameter search, or expanded equity facts.",
            required_runtime_gates=["Original PVR exact raw-table/claims/bridges and core/financial-report reproduction must pass before the other consumers in each window.",
                                    "All dynamic potential events must have precomputed features; absence is fatal.",
                                    "Each arm uses the same min(2, own current feasible count) rule. Actual feasible counts, admissions, and fills may differ.",
                                    "Post-run independent cash/receivable/inventory/fees/claims/coverage and same-stock participation audit is still required before reporting results."],
            limitations=["Current revised CH3 factors and static pool are non-PIT; historical factor release times are unknown.",
                         "Finite 436/165 equity fact sets and NET80 scenario retained unchanged; unadmitted events and nonrandom UNKNOWN remain.",
                         "Core is independent-fee attribution of initial shares on FULL entry/exit, not a separate strategy."],
            new_lifecycle_runs_by_auditor=0, execution_authorization_written_by_auditor=False, original_sources_changed=0)
prior = O / "PRE_ECONOMIC_AUDIT.json"
if prior.exists():
    old_hash = ad.sha(prior)
    archive = O / ("PRE_ECONOMIC_AUDIT_SUPERSEDED_" + old_hash[:12] + ".json")
    if not archive.exists(): archive.write_bytes(prior.read_bytes())
    result["superseded_audit_sha256"] = old_hash
(O/"PRE_ECONOMIC_AUDIT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(result,ensure_ascii=False,indent=2))

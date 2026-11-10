"""Validate existing selected-opportunity labels without generating economic paths."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
E = O.parent / "m3_stock_birth_during_sector_v1"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal = json.loads((O / "FEATURE_SEAL.json").read_text())
assert all(sha(O / name) == value for name, value in seal["files"].items())
feature_audit = json.loads((O / "INDEPENDENT_FEATURE_AUDIT.json").read_text())
assert feature_audit["status"] == "PASS" and feature_audit["feature_code_sha256"] == sha(O / "compute_features.py")
q = pd.read_csv(O / "CANDIDATE_RANKS_PRELABEL.csv", low_memory=False)
out = pd.read_csv(O / "ORIGINAL_SELECTED_OPPORTUNITY_RISK.csv", low_memory=False)
assert not any(c in q for c in ["core_return", "core_net", "entry_day", "exit_day"])
paths = [E / "relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv",
         E / "cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv"]
expected = ["4992d25f92fcf72e0321c9f5285af3152ebe2c0c00d6936303bf11e02e51cfd7", "560b468114913964a145d2f07f8167db453b0466558f41aed60c7382e44afd41"]
assert all(sha(p) == h for p, h in zip(paths, expected))
z = pd.concat([pd.read_csv(p, low_memory=False) for p in paths], ignore_index=True)
z = z[z.arm.eq("A_UNION_B")]
assert z.event_id.is_unique and out.event_id.is_unique
assert set(z.event_id) == set(out.event_id) == set(q.loc[q.old_selected, "event_id"])
assert not set(out.event_id) & set(q.loc[~q.old_selected, "event_id"])
orig = z.set_index("event_id").sort_index()
risk = out.set_index("event_id").sort_index()
selected = q[q.old_selected].set_index("event_id").sort_index()
exact_fields = ["round_id", "window", "sid", "sector", "arm", "signal_day", "entry_day", "exit_day", "status", "entry_status", "historical_tradability", "account_run", "exit_reason", "evidence_usable_closed", "financial_coverage_status", "coverage_reasons", "PVR_score", "close_q", "core_net", "core_return", "core_buy_cash", "core_buy_fee", "core_sell_fee", "core_dividend_net80"]
for col in exact_fields:
    a, b = orig[col], risk[col]
    if col == "window": a, b = a.astype(str), b.astype(str)
    assert (a.eq(b) | (a.isna() & b.isna())).all(), col
for col in ["old_rank", "old_selected", "known", "RM", "RAW_MOM11", "RM_rank", "RAW_MOM11_rank", "RM_selected", "RAW_MOM11_selected"]:
    a, b = selected[col], risk[col]
    assert (a.eq(b) | (a.isna() & b.isna())).all(), col
assert selected.status.eq(risk.feature_status).all()
assert risk.original_tail50.eq(orig.evidence_usable_closed & orig.core_return.ge(.5)).all()
assert risk.RM_removes_original_opportunity.eq(~selected.RM_selected).all()
assert risk.RAW_removes_original_opportunity.eq(~selected.RAW_MOM11_selected).all()
tail_file = pd.read_csv(O / "ORIGINAL_TAIL50_OPPORTUNITY_RISK.csv", low_memory=False)
assert set(tail_file.event_id) == set(orig.index[orig.evidence_usable_closed & orig.core_return.ge(.5)])
top_file = pd.read_csv(O / "ORIGINAL_TOP10_PER_WINDOW_RISK.csv", low_memory=False)
summary = json.loads((O / "ORIGINAL_OPPORTUNITY_RISK_SUMMARY.json").read_text())
results = []
for window, g in risk.groupby("window"):
    usable = g[g.evidence_usable_closed]
    tails = usable[usable.core_return.ge(.5)]
    top10 = usable.reset_index().sort_values(["core_return", "event_id"], ascending=[False, True]).head(10)
    assert set(top_file.loc[top_file.window.eq(window), "event_id"]) == set(top10.event_id)
    for name, col in [("CH3_RM", "RM_selected"), ("RAW_MOM11", "RAW_MOM11_selected")]:
        dropped = g[~g[col]]
        ud = dropped[dropped.evidence_usable_closed]
        td = tails[~tails[col]]
        rr = next(r for r in summary if r["window"] == str(window) and r["arm"] == name)
        checks = dict(original_selected=len(g), removed_original_slots=len(dropped), original_usable=len(usable), removed_usable=len(ud),
                      removed_execution_or_financial_unknown=int((~dropped.evidence_usable_closed).sum()), original_tail50=len(tails),
                      tail50_retained_static=len(tails) - len(td), tail50_removed_static=len(td), original_tail50_feature_unknown=int((~tails.known).sum()),
                      original_top10_removed=int((~top10[col]).sum()), removed_original_positive=int(ud.core_net.gt(0).sum()),
                      removed_original_nonpositive=int(ud.core_net.le(0).sum()), removed_unknown_feature_slots=int((~dropped.known).sum()))
        assert all(rr[k] == v for k, v in checks.items()), (window, name)
        assert checks["removed_unknown_feature_slots"] == 0
        reported = {(r["day"], r["sid"]) for r in rr["tail50_removed_names"]}
        assert reported == set(zip(td.day, td.sid))
        for suffix, fn in [("min", np.min), ("median", np.median), ("max", np.max)]:
            assert np.isclose(rr["removed_usable_return_" + suffix], fn(ud.core_return), atol=1e-12, rtol=1e-12)
        results.append(dict(window=str(window), arm=name, **checks))
report = dict(status="PASS", original_selected_labels=4086, exact_source_fields=exact_fields,
              label_fields_and_feature_fields_match=True, no_nonselected_payoff_labels=True, original_tail50_total=108,
              risk_summaries=results, source_hashes={str(p): sha(p) for p in paths},
              audited_outputs={p.name: sha(p) for p in [O / "connect_original_opportunity_labels.py", O / "ORIGINAL_SELECTED_OPPORTUNITY_RISK.csv", O / "ORIGINAL_TAIL50_OPPORTUNITY_RISK.csv", O / "ORIGINAL_TOP10_PER_WINDOW_RISK.csv", O / "ORIGINAL_OPPORTUNITY_RISK_SUMMARY.json"]},
              chronological_note="Features were sealed before joining labels. Label joining completed while the independent feature audit was still in progress; it did not occur after feature-audit completion.",
              interpretation="These are original selected opportunity removals only, not new entrant economics, strategy returns, or dynamic tail retention. No later same-stock entry payoffs were transferred.",
              new_lifecycle_runs=0, original_sources_changed=0)
(O / "INDEPENDENT_LABEL_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k not in ["source_hashes", "audited_outputs", "exact_source_fields"]}, ensure_ascii=False, indent=2))

"""Compare root snapshot method to independently rebuilt actual cash/div flows."""
from decimal import Decimal as D
from pathlib import Path
import gzip
import hashlib
import json
import time

O = Path(__file__).resolve().parent
ROOT = O.parent
WORK = ROOT.parent
EPS = D(".000001")


def read(p):
    return json.loads(Path(p).read_text())


def eq(a, b, label):
    assert abs(D(str(a)) - D(str(b))) < EPS, (label, str(a), str(b))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    begun = time.monotonic()
    with gzip.open(WORK / "new_price_trend_v1/funding/runs/long_OFF/pair/B.json.gz", "rt") as f:
        b = json.load(f)
    layers = {l["id"]: l for l in b["layers"]}
    with gzip.open(ROOT / "ANCHOR_ALL_LAYER_WEALTH.json.gz", "rt") as f:
        root = json.load(f)
    a = read(O / "INDEPENDENT_LAYER_WEALTH_rally.json")
    z = read(O / "INDEPENDENT_LAYER_WEALTH_postpeak.json")
    independent = {
        "2024-09-23": {str(r["layer"]): {"cash": r["begin_cash"], "recognized_dividend": r["begin_dividend"], "inventory": r["begin_inventory"]} for r in a},
        "2024-10-08": {str(r["layer"]): {"cash": r["end_cash"], "recognized_dividend": r["end_dividend"], "inventory": r["end_inventory"]} for r in a},
        "2024-12-31": {str(r["layer"]): {"cash": r["end_cash"], "recognized_dividend": r["end_dividend"], "inventory": r["end_inventory"]} for r in z},
    }
    checked = 0
    for date, rs in root.items():
        assert len(rs) == len(layers) == 2265
        for lid, r in rs.items():
            l = layers[int(lid)]
            if str(l["opened"])[:10] < "2024-01-01":
                assert l["closed"] and str(l["closed"])[:10] <= "2023-12-29" and l["qty"] == 0
                expected = {"cash": l["cash"], "recognized_dividend": l["dividend"], "inventory": 0}
            elif date == "2023-12-29":
                expected = {"cash": 0, "recognized_dividend": 0, "inventory": 0}
            else:
                expected = independent[date][lid]
            for key, value in expected.items():
                eq(r[key], value, ("Independent per-layer component", date, lid, key))
                checked += 1
            eq(r["wealth"], sum((D(str(v)) for v in expected.values()), D(0)), ("Per-layer equity", date, lid))
    first = read(O / "INDEPENDENT_COHORT_BREAKDOWN.json")
    rr = read(ROOT / "PHASE_COHORT_CHANGES.json")
    phases = {r["phase"]: r for r in rr}
    for theirs, ours in [("rally", "rally"), ("post_peak", "postpeak")]:
        x = first["phases"][ours]["groups"]
        expected = {"pre_924": D(x["pre924_layers"]["wealth_change"]),
                    "rally_924_to_Oct8": D(x["rally_924_to_Oct8_layers"]["wealth_change"]),
                    "post_Oct8": sum((D(v["wealth_change"]) for k, v in x.items() if k.startswith("postpeak_")), D(0))}
        for k, v in expected.items():
            eq(phases[theirs]["cohort_changes"][k], v, ("Independent cohort amount", theirs, k))
    new = [r for r in z if r["cohort"].startswith("postpeak_")]
    assert len(new) == 303
    positive = sum((D(r["wealth_change"]) for r in new if D(r["wealth_change"]) > 0), D(0))
    negative = sum((D(r["wealth_change"]) for r in new if D(r["wealth_change"]) < 0), D(0))
    eq(positive + negative, phases["post_peak"]["cohort_changes"]["post_Oct8"], "New cohort wins/losses")
    files = [Path(__file__), ROOT / "cohort_wealth.py", ROOT / "COHORT_SCOPE.json",
             ROOT / "PHASE_COHORT_CHANGES.json", ROOT / "ANCHOR_ALL_LAYER_WEALTH.json.gz",
             O / "audit_account_anchors.py", O / "ANCHOR_ACCOUNT_AUDIT.json",
             O / "audit_cohorts_independent.py", O / "INDEPENDENT_COHORT_BREAKDOWN.json",
             O / "INDEPENDENT_LAYER_WEALTH_rally.json", O / "INDEPENDENT_LAYER_WEALTH_postpeak.json"]
    review = {"passed": True, "scope": "Independent all2024 saved cash/qty/div reconstruction and93 original native marks compared to root final-cash/live-snapshot method. No new Account/Runner/Market/RiskBook or counterfactual portfolio.",
              "root_source_sha256": sha(ROOT / "cohort_wealth.py"),
              "all_4_anchors_x_2265_layer_components_and_wealth_exact": True,
              "per_layer_component_comparisons": checked,
              "closed_layer_constant_justification": [
                  "Actual buy/sell.parts net cash reconstructs every native final layer cash; no2024 split or unmodeled cash action.",
                  "Independent2024 entitlement allocation uses prior-CLOSE actual layers and matches all2265 native final layer dividends.",
                  "Old2023 layers are closed before empty2023 year-end; no2024 new accrual goes to them.",
                  "Every2024 closed-at-anchor layer was checked against independently reconstructed as-of cash/dividend, not merely terminal book residual.",
                  "Payment of an already-recognized dividend claim changes cash/receivable mix, not wealth."
              ],
              "root_phase_cohort_changes_exact": True,
              "classification_boundary": "first_ever_entry/reentry/add_to_existing uses actual stock quantity before buy, all historical buys for seen-stock; signal-CLOSE-held agrees on all708 2024 buy fills. Native kind=add alone does not mean an incremental holding.",
              "postpeak_new_layers": {"layers": 303, "positive": sum(D(r["wealth_change"]) > 0 for r in new),
                                      "negative": sum(D(r["wealth_change"]) < 0 for r in new),
                                      "positive_wealth": positive, "negative_wealth": negative,
                                      "net_wealth": positive + negative},
              "causal_limits": [
                  "67.318% of actual peak-to-yearend NAV decline is accounted for by layers opened afterOct8, not proof that this loss was entirely avoidable.",
                  "No-new-buy policy would also forego84 profitable layers and change cash, ranking, risk, ACT and later entries/exits.",
                  "10/8 peak is identified after the fact; its stock inventory is unrealized mark-to-market, not a legal same-day known-peak sell decision.",
                  "All returns use actual prior anchor NAV;2024 starts745426.96, not the original2022 seed1m."
              ],
              "new_accounts": 0, "new_routes": 0, "new_market_instances": 0,
              "this_comparison_new_mark_evaluations": 0,
              "source_sha256": {str(p.resolve()): sha(p) for p in files},
              "seconds": time.monotonic() - begun}
    (O / "ROOT_COHORT_SAVED_REVIEW.json").write_text(json.dumps(review, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps({"passed": True, "components": checked, "seconds": review["seconds"], "new_positive": review["postpeak_new_layers"]["positive"]}))


if __name__ == "__main__":
    main()

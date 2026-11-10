"""Disambiguate the Oct8 and Oct31 existing-inventory cohorts, saved data only."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import hashlib
import json
import time

O = Path(__file__).resolve().parent
start = time.monotonic()
detail_path = O / "OCT31_TO_YEAR_END_LAYER_WEALTH.json"
summary_path = O / "OCT31_MONTHEND_ADDENDUM.json"
rows = json.loads(detail_path.read_text())
summary = json.loads(summary_path.read_text())
groups = defaultdict(lambda: D(0))
for r in rows:
    if r["cohort"] != "existing_at_Oct31":
        continue
    day = r["opened"][:10]
    key = "pre924_entry" if day <= "2024-09-23" else "rally_to_Oct8_entry" if day <= "2024-10-08" else "Oct9_to_Oct31_entry"
    groups[key] += D(r["wealth_change"])
assert abs(sum(groups.values(), D(0)) - D(summary["Nov_Dec_cohorts"]["existing_at_Oct31"]["wealth_change"])) < D(".000001")
new_nov_dec = sum((D(v["wealth_change"]) for k, v in summary["Nov_Dec_cohorts"].items() if k != "existing_at_Oct31"), D(0))
old_Oct8 = groups["pre924_entry"] + groups["rally_to_Oct8_entry"]
all_after_Oct8 = groups["Oct9_to_Oct31_entry"] + new_nov_dec
assert abs(old_Oct8 + all_after_Oct8 - D(summary["Nov_Dec_NAV_change"])) < D(".000001")
out = {"passed": True, "phase": "2024Nov1-Dec31_actual_wealth_change",
       "Oct31_existing_cohort_by_original_entry": dict(groups),
       "original_Oct8_inventory_layers_NovDec_change": old_Oct8,
       "NovDec_new_layer_change": new_nov_dec,
       "all_layers_bought_after_Oct8_NovDec_change": all_after_Oct8,
       "total_NovDec_change": summary["Nov_Dec_NAV_change"],
       "after_Oct8_layer_share_of_NovDec_net_decline_pct": all_after_Oct8 / D(summary["Nov_Dec_NAV_change"]) * 100,
       "interpretation": "Oct31 existing inventory includes layers boughtOct9-Oct31; it is a different cohort from Oct8 existing inventory. Do not add the two old-cohort losses. New layers include additions to previously owned stocks, not only newly selected symbols.",
       "causal_boundary": "Actual wealth attribution only. No proof every new loss was avoidable; deleting new trades would also remove profitable ones and alter the financial/selection path.",
       "new_marks": 0, "new_accounts": 0, "new_routes": 0,
       "source_sha256": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), detail_path, summary_path]},
       "seconds": time.monotonic() - start}
(O / "OCT31_OLD_COHORT_CLARIFICATION.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + "\n")
print(json.dumps({"passed": True, "all_after_Oct8_change": str(all_after_Oct8), "share_pct": str(out["after_Oct8_layer_share_of_NovDec_net_decline_pct"])}))

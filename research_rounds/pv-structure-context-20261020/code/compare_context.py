"""Post-run diagnostics, comparing descriptors only; no trades or accounts."""
from pathlib import Path
import json
import pandas as pd
import numpy as np

base = Path(__file__).resolve().parents[1]
destination = base / "comparison.json"
if destination.exists():
    raise FileExistsError(destination)
changed = {"phase", "price_phase", "e", "s", "retrace", "phase_source"}
cases = [c for c in json.loads((base / "raw/case-index.json").read_text())
         if c["prefix"] == 1]
frames = {}
series_checks = []
for path in sorted((base / "v0").glob("*-states.csv")):
    if path.name == "checkpoint-states.csv":
        continue
    old = pd.read_csv(path, index_col="date", parse_dates=True)
    new = pd.read_csv(base / "v1" / path.name, index_col="date", parse_dates=True)
    keep = [c for c in old if c not in changed]
    pd.testing.assert_frame_equal(old[keep], new[keep])
    live = new.phase_source.eq("developing_pair") & new.valid
    assert new.loc[live, "live_end_idx"].eq(new.loc[live, "valid_idx"]).all()
    assert (new.loc[live, "live_start_idx"] < new.loc[live, "live_end_idx"]).all()
    for c in changed - {"phase_source"}:
        pd.testing.assert_series_equal(old[c], new["completed_" + c],
                                       check_names=False)
    frames[path.name.removesuffix("-states.csv")] = (old, new)
    series_checks.append({"symbol": path.stem, "unchanged_columns": len(keep),
                          "all_preserved_exactly": True,
                          "current_evidence_endpoint_verified": True})
rows = []
for case in cases:
    old, new = frames[case["symbol"]]
    old = old.loc[case["start"]:case["end"]]
    new = new.loc[case["start"]:case["end"]]
    rows.append({"case": case["id"], "symbol": case["symbol"],
                 "rows": len(new),
                 "structural_direction_changes_between_versions": 0,
                 "description_changed_rows": int(old.phase.ne(new.phase).sum()),
                 "v0_phase_switches": int(old.phase.ne(old.phase.shift()).iloc[1:].sum()),
                 "v1_phase_switches": int(new.phase.ne(new.phase.shift()).iloc[1:].sum())})
pd.DataFrame(rows).to_csv(base / "case-comparison.csv", index=False)
examples = []
for symbol, date in [("HK09618", "2024-11-20"),
                     ("USHJ512480", "2026-10-16"),
                     ("USHJ518880", "2024-12-31"),
                     ("USHJ512480", "2024-09-30")]:
    old, new = frames[symbol]
    r = new.loc[date]
    examples.append({"symbol": symbol, "date": date, "close": r.close,
                     "regime": int(r.regime), "v0_phase": old.loc[date, "phase"],
                     "v1_phase": r.phase, "e": r.e, "s": r.s,
                     "retrace_of_previous_leg_log_displacement": r.retrace,
                     "boundary_price": float(np.exp(r.structure_floor)),
                     "rank": r.rs_rank, "rank_n": int(r.rank_n)})
destination.write_text(json.dumps(
    {"account_calls": 0, "checks": series_checks, "examples": examples,
     "interpretation": "Phase switches/changed rows are diagnostics, not improvement scores."},
    ensure_ascii=False, indent=2))
print(json.dumps({"verified_series": len(series_checks), "cases": len(rows),
                  "examples": examples}, ensure_ascii=False))

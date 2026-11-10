"""Independent full potential-event feature audit. No economic engine import or run."""
from pathlib import Path
import ast, hashlib, json
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
P = O.parent
E = P.parent / "m3_stock_birth_during_sector_v1"
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal = json.loads((O / "FEATURE_SEAL.json").read_text())
for name, expected in seal["files"].items():
    assert digest(O / name) == expected, (name, "full feature seal drift")
for path, expected in seal["source_hashes"].items():
    assert digest(path) == expected, (path, "source drift")
parent_seal = json.loads((P / "FEATURE_SEAL.json").read_text())
assert digest(P / "compute_features.py") == parent_seal["files"]["compute_features.py"]
features = pd.read_csv(O / "ALL_MARKET_STOCK_MONTH_FEATURES.csv")
q = pd.read_csv(O / "ALL_MARKET_EVENT_KEYS.csv")
ev = pd.read_csv(E / "SEALED_ALL_BIRTH_EVENTS.csv", low_memory=False)
ev = ev[ev.window.astype(str).isin(["2022", "2024_924"]) & ev.event_type.isin(["A_SECTOR_BIRTH", "B_STOCK_BIRTH_DURING_SECTOR"])].copy()
ev["month"] = pd.to_datetime(ev.day).dt.to_period("M").astype(str)
assert len(q) == len(ev) == 19795 and q.event_id.is_unique and set(q.event_id) == set(ev.event_id)
assert not features.duplicated(["sid", "month"]).any() and len(features) == 14635
assert set(zip(features.sid, features.month)) == set(zip(ev.sid, ev.month))
check = q.merge(ev, on="event_id", validate="one_to_one", suffixes=("_q", "_e"))
for name in ["window", "day", "sid", "month", "sector", "event_type"]:
    assert check[name + "_q"].astype(str).eq(check[name + "_e"].astype(str)).all(), name
old = pd.read_csv(P / "STOCK_MONTH_FEATURES_PRELABEL.csv")
common = features.merge(old, on=["sid", "month"], validate="one_to_one", suffixes=("_new", "_old"))
assert len(common) == 8020 and common.status_new.eq(common.status_old).all()
for name in ["RM", "RAW_MOM11", "RAW_EXCESS_STANDARDIZED", "alpha", "beta_market", "beta_size", "beta_value", "residual_mean", "residual_sd"]:
    assert np.allclose(common[name + "_new"], common[name + "_old"], atol=1e-14, rtol=1e-12, equal_nan=True), name

manifest_path = Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
manifest = {x["symbol"]: x for x in json.loads(manifest_path.read_text())}
with np.load("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz", allow_pickle=False) as h:
    cal = pd.DatetimeIndex(h["dates"])
assert cal.is_unique and cal.is_monotonic_increasing
lastday = pd.Series(cal, index=cal.to_period("M")).groupby(level=0).max()
panel = pd.read_parquet(P.parent / "momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet", columns=["day"])
baseline_calendar = pd.DatetimeIndex(sorted(panel.day.unique()))
assert cal[(cal >= baseline_calendar.min()) & (cal <= baseline_calendar.max())].equals(baseline_calendar)
f = pd.read_excel(P / "CH3_factors_monthly_202608.xlsx", sheet_name="Returnseries")
f.index = pd.to_datetime(f.pop("mnthdt").astype(str), format="%Y%m%d").dt.to_period("M")
source = P / "compute_features.py"
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "calc")
namespace = {"np": np, "pd": pd, "lastday": lastday}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
calc = namespace["calc"]
formula_hash = hashlib.sha256(ast.get_source_segment(source.read_text(), node).encode()).hexdigest()
qa = json.loads((O / "FEATURE_QA.json").read_text())
assert qa["calc_definition_sha256"] == formula_hash

# Reuse the independent auditor's QR/difference-return implementation, not producer logic.
# This section only reads stock data and updates audit accumulators. No engine import.
auditor = P / "independent_feature_audit.py"
text = auditor.read_text()
start = text.index("# Independently derive all feature support")
end = text.index("# Deterministic numerical and data-contract synthetic tests")
exec(compile(text[start:end], str(auditor) + ":all_potential_events", "exec"), globals())

report = dict(status="PASS", market_events=len(q), stock_months=len(features), unchanged_phase1_stock_months=len(common),
              additional_stock_months=len(features) - len(common), all_event_keys_exact=True, no_missing_feature_keys=True,
              original_formula_definition_unchanged=True, source_hashes_checked=len(seal["source_hashes"]),
              known_stock_months_independently_recomputed=known_count, independent_status_counts=status_counts,
              maximum_absolute_numerical_errors=errors, physical_prefix_cases=prefix_cases,
              full_calendar_matches_baseline_dates=len(baseline_calendar), feature_seal_sha256=digest(O / "FEATURE_SEAL.json"),
              reused_independent_auditor_sha256=digest(auditor), original_calc_definition_sha256=formula_hash,
              no_economic_engine_imported=True, no_economic_runs=True,
              limitations=["Current revised factors and static stock pool remain non-PIT.", "Audit approves feature coverage, not lifecycle execution."])
(O / "INDEPENDENT_FULL_FEATURE_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "physical_prefix_cases"}, ensure_ascii=False, indent=2))

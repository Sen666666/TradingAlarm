"""Independent read-only source audit. Writes only its audit JSON in this directory."""
from pathlib import Path
import ast, hashlib, json
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
E = O.parent / "m3_stock_birth_during_sector_v1"
def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal = json.loads((O / "FEATURE_SEAL.json").read_text())
for name, expected in seal["files"].items():
    assert digest(O / name) == expected, (name, "feature seal drift")
source_hashes = json.loads((O / "SOURCE_HASHES_PRELABEL.json").read_text())
for p, expected in source_hashes.items():
    assert digest(p) == expected, (p, "source drift")

q = pd.read_csv(O / "CANDIDATE_RANKS_PRELABEL.csv", low_memory=False)
features = pd.read_csv(O / "STOCK_MONTH_FEATURES_PRELABEL.csv")
manifest_path = Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
manifest = {x["symbol"]: x for x in json.loads(manifest_path.read_text())}
calendar_path = Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
with np.load(calendar_path, allow_pickle=False) as h:
    cal = pd.DatetimeIndex(h["dates"])
assert cal.is_unique and cal.is_monotonic_increasing
lastday = pd.Series(cal, index=cal.to_period("M")).groupby(level=0).max()
f = pd.read_excel(O / "CH3_factors_monthly_202608.xlsx", sheet_name="Returnseries")
f.index = pd.to_datetime(f.pop("mnthdt").astype(str), format="%Y%m%d").dt.to_period("M")
assert digest(O / "CH3_factors_monthly_202608.xlsx") == "8d956043a1a39d10bc1b777a865fca8cf40b1b628c1d94f900ba2b23c22819a4"
assert f.index.equals(pd.period_range("2000-01", "2026-08", freq="M"))

# AST-extract only the feature function. Importing the module would write input copies.
source = O / "compute_features.py"
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "calc")
namespace = {"np": np, "pd": pd, "lastday": lastday}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
calc = namespace["calc"]

# Reconstruct eligible queue from the original repaired decisions, not derived ranks.
ds = pd.concat([pd.read_csv(E / "relative_priority_equity_run_2022_v1/dynamic/DECISIONS.csv", low_memory=False),
                pd.read_csv(E / "cash_equity_baseline_2024_v1/economic/DECISIONS.csv", low_memory=False)])
ds = ds[ds.arm.eq("A_UNION_B") & ds.decision.isin(["SELECTED_PENDING", "PASS_NOT_TOP2"])].copy()
assert len(ds) == len(q) == 9233 and set(ds.event_id) == set(q.event_id)
ds = ds.sort_values(["window", "day", "sector", "PVR_score", "sid"], ascending=[True, True, True, False, True])
ds["independent_rank"] = ds.groupby(["window", "day", "sector"]).cumcount() + 1
joined = q.merge(ds[["event_id", "independent_rank", "selected", "queue_rank"]], on="event_id", suffixes=("", "_source"), validate="one_to_one")
assert joined.old_rank.eq(joined.independent_rank).all()
assert joined.old_selected.eq(joined.selected_source).all()
assert joined.source_queue_rank.eq(joined.queue_rank_source).all()
source_rank_holes = int(joined.source_queue_rank.ne(joined.old_rank).sum())
ranked_rows = 0
for _, g in q.groupby(["window", "day", "sector"]):
    g = g.sort_values("independent_rank") if "independent_rank" in g else g.sort_values("old_rank")
    K = int(g.old_selected.sum())
    assert K == min(2, len(g)) and g.old_selected.eq(g.old_rank.le(K)).all()
    slots = g.loc[g.known, "old_rank"].to_list()
    assert g.known.eq(g.RM.notna()).all() and g.known.eq(g.RAW_MOM11.notna()).all()
    for score in ["RM", "RAW_MOM11"]:
        order = sorted(g[g.known].to_dict("records"), key=lambda r: (-r[score], -r["PVR_score"], r["sid"]))
        new = {r["event_id"]: pos for r, pos in zip(order, slots)}
        expected = np.array([new.get(r.event_id, r.old_rank) for r in g.itertuples()])
        assert np.array_equal(g[score + "_rank"], expected)
        assert np.array_equal(g[score + "_selected"], expected <= K)
        assert g.loc[~g.known, score + "_rank"].eq(g.loc[~g.known, "old_rank"]).all()
        assert int(g[score + "_selected"].sum()) == K
    ranked_rows += len(g)

# Independently derive all feature support and numerical values from raw source files.
errors = {c: 0.0 for c in ["RM", "RAW_MOM11", "RAW_EXCESS_STANDARDIZED", "alpha", "beta_market", "beta_size", "beta_value"]}
status_counts = {}
known_count = 0
prefix_cases = []
deterministic = q.sort_values(["window", "month", "sid", "day"]).groupby(["window", "month"]).head(1)
physical_targets = set(zip(deterministic.sid, deterministic.month))
for sid, group in features.groupby("sid", sort=True):
    p = pd.read_parquet(next(p for p in manifest[sid]["source_sha256"] if p.endswith("/signal.parquet"))).sort_index()
    for rr in group.itertuples():
        m = pd.Period(rr.month, freq="M")
        ms = [m - k for k in range(36, 0, -1)]
        em = [m - k for k in range(37, 0, -1)]
        ix = pd.DatetimeIndex([lastday.get(month, pd.NaT) for month in em])
        status = "CALENDAR_COMPUTABLE_RELEASE_UNKNOWN"
        if ix.isna().any():
            status = "UNKNOWN_CALENDAR"
        elif not all(x in f.index for x in ms):
            status = "UNKNOWN_FACTOR_MONTH"
        else:
            a = p.reindex(ix)
            if a.close.isna().any(): status = "UNKNOWN_MONTH_END_PRICE"
            elif not (np.isfinite(a[["close", "raw_close", "adjustment_factor"]]).all().all() and a[["close", "raw_close", "adjustment_factor"]].gt(0).all().all()): status = "UNKNOWN_PRICE_OR_FACTOR"
            else:
                for name, expected in [("observed_bar", True), ("price_eligible", True), ("source_invalid", False), ("synthetic_event_bar", False)]:
                    if not a[name].eq(expected).all():
                        status = "UNKNOWN_ENDPOINT_" + name
                        break
                if status.startswith("CALENDAR") and not np.allclose(a.raw_close * a.adjustment_factor, a.close, rtol=1e-9, atol=1e-9): status = "UNKNOWN_COORDINATE"
                span = p.loc[ix[0]:ix[-1]]
                if status.startswith("CALENDAR"):
                    for name in ["source_kind", "source_path", "segment_id"]:
                        if a[name].isna().any() or span[name].isna().any() or span[name].nunique() != 1:
                            status = "UNKNOWN_SOURCE_SEGMENT"
                            break
        if status.startswith("CALENDAR"):
            px = a.close.to_numpy()
            returns = np.diff(px) / px[:-1]
            fm = f.loc[ms]
            X = np.concatenate((np.ones((36, 1)), fm[["mktrf", "SMB", "VMG"]].to_numpy()), axis=1)
            y = returns - fm.rf_mon.to_numpy()
            if np.linalg.matrix_rank(X) != 4:
                status = "UNKNOWN_RANK"
            else:
                Q, R = np.linalg.qr(X)
                coef = np.linalg.solve(R, Q.T @ y)
                residual = y - X @ coef
                selected_residual = residual[24:35]
                sd = np.sqrt(np.sum((selected_residual - selected_residual.mean()) ** 2) / 10)
                tol = np.finfo(float).eps * max(X.shape) * (np.linalg.norm(y) + np.linalg.norm(X) * np.linalg.norm(coef))
                if not np.isfinite(sd) or sd <= tol:
                    status = "UNKNOWN_NUMERICAL_RESIDUAL_SCALE"
                else:
                    known_count += 1
                    values = dict(RM=selected_residual.mean() / sd, RAW_MOM11=px[-2] / px[24] - 1,
                                  RAW_EXCESS_STANDARDIZED=y[24:35].mean() / np.std(y[24:35], ddof=1),
                                  alpha=coef[0], beta_market=coef[1], beta_size=coef[2], beta_value=coef[3])
                    for name, value in values.items():
                        expected = getattr(rr, name)
                        assert np.isclose(value, expected, atol=1e-10, rtol=1e-10), (sid, rr.month, name, value, expected)
                        errors[name] = max(errors[name], float(abs(value - expected)))
                    assert rr.fit_first == str(m - 36) and rr.fit_last == str(m - 1)
                    assert rr.formation_first == str(m - 12) and rr.formation_last == str(m - 2)
                    assert rr.fit_n == 36 and rr.formation_n == 11
        assert rr.status == status, (sid, rr.month, rr.status, status)
        status_counts[status] = status_counts.get(status, 0) + 1
        if (sid, rr.month) in physical_targets:
            day = pd.Timestamp(rr.first_signal_day)
            original = calc(p, f, day)
            cut = (m - 1).end_time
            cl = cal[cal <= cut]
            namespace["lastday"] = pd.Series(cl, index=cl.to_period("M")).groupby(level=0).max()
            prefix = calc(p[p.index <= cut].copy(), f[f.index < m].copy(), day)
            namespace["lastday"] = lastday
            assert prefix == original
            future = p.copy()
            future.loc[future.index >= m.start_time, "close"] = np.nan
            future.loc[future.index >= m.start_time, "source_path"] = "FUTURE_CORRUPTION"
            ff = f.copy()
            ff.loc[ff.index >= m, :] = np.nan
            assert calc(future, ff, day) == original
            if status.startswith("CALENDAR"):
                assert calc(p, f.drop(m - 1), day)["status"] == "UNKNOWN_FACTOR_MONTH"
            prefix_cases.append(dict(sid=sid, month=rr.month, status=status, physical_prefix_equal=True, future_month_invariant=True))

# Deterministic numerical and data-contract synthetic tests, no historical outcome use.
rng = np.random.default_rng(20261107)
month = pd.Period("2022-01", freq="M")
months = pd.period_range(month - 36, month - 1, freq="M")
ep = pd.DatetimeIndex(lastday.loc[pd.period_range(month - 37, month - 1, freq="M")].to_numpy())
ff = pd.DataFrame(rng.normal(0, .03, (36, 3)), index=months, columns=["mktrf", "SMB", "VMG"])
ff["rf_mon"] = .001
X = np.column_stack([np.ones(36), ff[["mktrf", "SMB", "VMG"]]])
def prices(returns):
    p = pd.DataFrame(index=ep)
    p["close"] = 10 * np.r_[1, np.cumprod(1 + returns)]
    p["raw_close"] = p.close
    p["adjustment_factor"] = 1.0
    for col in ["observed_bar", "price_eligible"]: p[col] = True
    for col in ["source_invalid", "synthetic_event_bar"]: p[col] = False
    for col in ["source_kind", "source_path", "segment_id"]: p[col] = "SYNTHETIC_CONSTANT_LINEAGE"
    return p
synthetic = {}
perfect = prices(X @ np.array([.01, .3, -.2, .1]) + ff.rf_mon.to_numpy())
synthetic["perfect_factor_model_rejected"] = calc(perfect, ff, "2022-01-05")["status"] == "UNKNOWN_NUMERICAL_RESIDUAL_SCALE"
flat = prices(np.zeros(36))
synthetic["constant_price_rejected"] = calc(flat, ff, "2022-01-05")["status"] == "UNKNOWN_NUMERICAL_RESIDUAL_SCALE"
noisy = prices(X @ np.array([.01, .3, -.2, .1]) + ff.rf_mon.to_numpy() + rng.normal(0, .015, 36))
base = calc(noisy, ff, "2022-01-05")
assert base["status"] == "CALENDAR_COMPUTABLE_RELEASE_UNKNOWN"
rescaled = noisy.copy()
rescaled[["close", "raw_close"]] *= 17
alt = calc(rescaled, ff, "2022-01-05")
synthetic["price_units_invariant"] = all(np.isclose(base[k], alt[k], atol=1e-12, rtol=1e-12) for k in ["RM", "RAW_MOM11", "alpha", "beta_market", "beta_size", "beta_value"])
bad = ff.copy(); bad["VMG"] = bad["SMB"]
synthetic["rank_deficiency_rejected"] = calc(noisy, bad, "2022-01-05")["status"] == "UNKNOWN_RANK"
synthetic["missing_endpoint_unknown"] = calc(noisy.drop(ep[5]), ff, "2022-01-05")["status"] == "UNKNOWN_MONTH_END_PRICE"
bad = noisy.copy(); bad.loc[ep[8], "raw_close"] *= 2
synthetic["coordinate_mismatch_unknown"] = calc(bad, ff, "2022-01-05")["status"] == "UNKNOWN_COORDINATE"
bad = noisy.copy(); bad.loc[ep[8], "segment_id"] = "OTHER"
synthetic["source_break_unknown"] = calc(bad, ff, "2022-01-05")["status"] == "UNKNOWN_SOURCE_SEGMENT"
synthetic["missing_latest_fit_factor_unknown"] = calc(noisy, ff.drop(month - 1), "2022-01-05")["status"] == "UNKNOWN_FACTOR_MONTH"
assert all(synthetic.values()), synthetic

report = dict(status="PASS", scope="Features and fixed original queues only; no payoff labels loaded and no lifecycle executed.",
              feature_code_sha256=digest(source), feature_seal_sha256=digest(O / "FEATURE_SEAL.json"),
              checked_source_hashes=len(source_hashes), candidates=len(q), original_queue_groups=q.groupby(["window", "day", "sector"]).ngroups,
              all_candidate_ranks_independently_recomputed=ranked_rows, source_queue_rank_holes=source_rank_holes,
              stock_months=len(features), independently_recomputed_known_stock_months=known_count,
              independent_status_counts=status_counts, maximum_absolute_numerical_errors=errors,
              physical_prefix_cases=prefix_cases, synthetic_tests=synthetic,
              limitations=["Current revision CH3 factors and native adjusted-close proxies, not PIT or certified total shareholder return.",
                           "No inference about new entrant payoffs or dynamic selection effects.",
                           "Original selected outcome labels require a separate audit and cannot be transferred from later same-stock entries."])
(O / "INDEPENDENT_FEATURE_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "physical_prefix_cases"}, ensure_ascii=False, indent=2))

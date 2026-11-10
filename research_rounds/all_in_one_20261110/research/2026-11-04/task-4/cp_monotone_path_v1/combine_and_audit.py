"""Combine frozen scalar substitutions; no model, order or account imports."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def f(row, key):
    return float(row[key])


def flag(value):
    return str(value).lower() == "true"


rows = []
y_long_path = ROOT / "yingxin/ALL30_AXIS_LAMBDA_VALUES_AND_DECOMPOSITION.csv"
y_wide_path = ROOT / "yingxin/FIVE_DAYS_SIX_Q_AND_DELTA_WIDE.csv"
h_path = ROOT / "hytera/ALL16_DAYS_THREE_LAMBDAS_Q_AND_DELTAS.csv"
y_wide = {row["day"]: row for row in read_csv(y_wide_path)}
y = {}
for raw in read_csv(y_long_path):
    date = raw["day"]
    lam = f(raw, "lambda_sensitivity")
    key = (date, lam)
    row = y.setdefault(key, dict(
        case="yingxin", sid=raw["sid"], date=date,
        previous_observation=raw["previous_observation_day"],
        close_raw=f(y_wide[date], "close_raw"), lambda_value=lam,
        original_CP_receipt=flag(raw["original_CP_receipt"]),
        original_E0_event=int(f(raw, "original_E0_event")),
    ))
    axis = raw["axis"]
    for target, source in {
        "A": "A", "L": "L", "W": "excess_path_V", "sigma": "sigma",
        "Q": "Q_lambda", "Q_yesterday": "Q_yesterday",
        "Q_today_oldanchor": "Q_today_with_yesterday_anchor_and_sigma",
        "raw_delta": "delta_Q_raw", "market_delta": "delta_Q_comparable",
        "rebase_delta": "Q_rebase_component",
    }.items():
        row[f"{target}_{axis}"] = f(raw, source)
    row[f"pivot_day_{axis}"] = raw["current_anchor_pivot_day"]
    row[f"confirm_day_{axis}"] = raw["current_anchor_confirm_day"]
    row[f"anchor_changed_{axis}"] = flag(raw["anchor_changed_today"])
rows.extend(y.values())

for raw in read_csv(h_path):
    row = dict(
        case="hytera", sid=raw["sid"], date=raw["date"],
        previous_observation=raw["previous_original_observation"],
        close_raw=f(raw, "raw_close"), lambda_value=f(raw, "lambda_value"),
        original_CP_receipt=flag(raw["original_CP_receipt"]),
        original_E0_event=int(f(raw, "original_E0_event")),
    )
    for axis in ("s", "l"):
        for target, source in {
            "A": "A", "L": "L", "W": "excess_path", "sigma": "sigma",
            "Q": "Q", "Q_yesterday": "Q_yesterday",
            "Q_today_oldanchor": "Q_today_oldanchor_sigma",
            "raw_delta": "raw_dQ", "market_delta": "market_dQ",
            "rebase_delta": "rebase_dQ",
        }.items():
            row[f"{target}_{axis}"] = f(raw, f"{source}_{axis}")
        for field in ("pivot_day", "confirm_day"):
            row[f"{field}_{axis}"] = raw[f"{field}_{axis}"]
        row[f"anchor_changed_{axis}"] = flag(raw[f"anchor_changed_{axis}"])
    rows.append(row)

rows.sort(key=lambda row: (row["sid"], row["date"], row["lambda_value"]))
assert len(rows) == 63
assert len({(row["sid"], row["date"], row["lambda_value"]) for row in rows}) == 63
max_formula_error = 0.0
max_bridge_error = 0.0
min_excess = float("inf")
for row in rows:
    assert row["lambda_value"] in (0.0, 0.5, 1.0)
    assert row["previous_observation"] < row["date"]
    for axis in ("s", "l"):
        a, length, sigma = (row[f"{key}_{axis}"] for key in ("A", "L", "sigma"))
        assert sigma > 0
        assert row[f"pivot_day_{axis}"] <= row[f"confirm_day_{axis}"] <= row["date"]
        excess = length - abs(a)
        min_excess = min(min_excess, excess)
        assert excess >= -1e-12
        expected = (a - row["lambda_value"] * excess) / (math.sqrt(5) * sigma)
        max_formula_error = max(max_formula_error, abs(expected - row[f"Q_{axis}"]))
        bridge = row[f"raw_delta_{axis}"] - row[f"market_delta_{axis}"] - row[f"rebase_delta_{axis}"]
        max_bridge_error = max(max_bridge_error, abs(bridge))
        assert abs(bridge) < 1e-12
        assert abs(expected - row[f"Q_{axis}"]) < 1e-12

out_csv = ROOT / "ALL21_DAYS_THREE_LAMBDAS_COMBINED.csv"
with out_csv.open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
(ROOT / "ALL21_DAYS_THREE_LAMBDAS_COMBINED.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")

main = [row for row in rows if row["lambda_value"] == 0.5 and
        ((row["case"] == "yingxin" and row["date"] >= "2022-01-20") or
         (row["case"] == "hytera" and row["date"] >= "2024-09-24"))]
assert len(main) == 19
table = [
    "λ=.5，仅描述已知路径；Δm固定昨日锚/尺度，Δb为换锚及尺度参考变化。",
    "原CP是原策略标签，新式没有产生新凭据、订单或收益。",
    "",
    "| 股票/收盘日 | 原收盘 | Q短 | Δm短 | Δb短 | Q长 | Δm长 | Δb长 | 原CP |",
    "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
]
for row in main:
    label = "盈新" if row["case"] == "yingxin" else "海能"
    values = " | ".join(f"{row[key]:+.6f}" for key in (
        "Q_s", "market_delta_s", "rebase_delta_s", "Q_l", "market_delta_l", "rebase_delta_l"))
    table.append(f"| {label} {row['date']} | {row['close_raw']:.2f} | {values} | {'是' if row['original_CP_receipt'] else '否'} |")
(ROOT / "DEFAULT_LAMBDA_DAILY_TABLE.txt").write_text("\n".join(table) + "\n")

audit = {
    "status": "SCALAR_SUBSTITUTION_AND_BRIDGES_CHECKED_NOT_A_CP_POLICY",
    "rows_with_both_axes": len(rows), "scalar_axis_checks": len(rows) * 2,
    "main_daily_rows_at_lambda_half": len(main),
    "max_abs_formula_error": max_formula_error,
    "max_abs_raw_minus_market_minus_rebase": max_bridge_error,
    "min_L_minus_abs_A": min_excess,
    "current_pivot_confirmation_not_after_output_date": True,
    "causality_scope": "Checks stored confirmation dates, not an independent rerun of E0 or a full point-in-time data-vendor audit.",
    "no_new_CP_state_or_receipts": True,
    "new_weight_or_risk_mapping": 0, "new_accounts": 0, "new_orders": 0, "new_backtests": 0,
    "sources_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        y_long_path, y_wide_path, h_path, Path(__file__).resolve())},
}
(ROOT / "ROOT_FINITE_SUBSTITUTION_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: audit[key] for key in (
    "rows_with_both_axes", "scalar_axis_checks", "max_abs_formula_error",
    "max_abs_raw_minus_market_minus_rebase", "min_L_minus_abs_A")}, ensure_ascii=False))
print("\n".join(table))

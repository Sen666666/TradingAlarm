"""Read saved lambda-zero axes and original CP tags. No strategy execution."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK = ROOT.parent


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def true(value):
    return str(value).lower() == "true"


src = TASK / "cp_monotone_path_v1/ALL21_DAYS_THREE_LAMBDAS_COMBINED.csv"
yx_src = TASK / "cp_formula_redesign_v1/yingxin/ORIGINAL_CP_21_DAILY_INPUTS_AND_STATES.csv"
hy_src = TASK / "cp_formula_redesign_v1/hytera_924/002583.SZ_ORIGINAL_CP_DAILY.csv"
yx_counts_src = ROOT / "yingxin/JAN19_25_PARALLEL_R_B_AND_ORIGINAL_FIELDS.csv"
hy_counts_src = ROOT / "hytera_and_trend_examples/ALL16_DAILY_R_B_AND_ORIGINAL_EVENTS.csv"
down_counts = {}
for raw in read(yx_counts_src):
    down_counts[(raw["sid"], raw["day"])] = (
        float(raw["D_down_long"]), int(raw["n_down_long"]), int(raw["n_turn_long_excluding_zero"]))
for raw in read(hy_counts_src):
    down_counts[(raw["sid"], raw["date"])] = (
        float(raw["D_down_l"]), int(raw["n_down_l"]), int(raw["n_turn_l"]))
cp = {}
for raw in read(yx_src):
    cp[(raw["sid"], raw["day"])] = dict(
        frontier=float(raw["delta_frontier"]), receipt=true(raw["original_receipt"]),
        candidate=raw["candidate_a"], I=int(float(raw["original_I_target"])),
        E0=int(float(raw["original_fact_e0_target"])),
        phase=raw["phase"], reason=raw["reset_reason"],
    )
for raw in read(hy_src):
    cp[(raw["sid"], raw["date"])] = dict(
        frontier=float(raw["delta_frontier"]), receipt=true(raw["receipt"]),
        candidate=raw["candidate"], I=int(float(raw["original_I_target"])),
        E0=int(float(raw["original_E0_target"])),
        phase=raw["phase"], reason=raw["reset_reason"],
    )

out = []
for raw in read(src):
    if float(raw["lambda_value"]) != 0.0:
        continue
    original = cp[(raw["sid"], raw["date"])]
    down_log, n_down, n_turn = down_counts[(raw["sid"], raw["date"])]
    r, b = float(raw["Q_s"]), float(raw["Q_l"])
    assert math.isclose(r, float(raw["A_s"])/(math.sqrt(5)*float(raw["sigma_s"])), abs_tol=1e-12)
    assert math.isclose(b, float(raw["A_l"])/(math.sqrt(5)*float(raw["sigma_l"])), abs_tol=1e-12)
    assert original["receipt"] == true(raw["original_CP_receipt"])
    assert abs(down_log - (float(raw["L_l"])-float(raw["A_l"]))/2) < 1e-12
    fresh = original["frontier"] > 0.0
    frontier_r = fresh and r >= 1.0
    receipt_r = original["receipt"] and r >= 1.0
    row = dict(
        sid=raw["sid"], date=raw["date"], close_raw=float(raw["close_raw"]),
        R=r, B=b, down_log_distance=(float(raw["L_l"])-float(raw["A_l"]))/2,
        n_down=n_down, n_turn_zeros_removed=n_turn,
        long_total_path=float(raw["L_l"]),
        low_pivot=raw["pivot_day_s"], low_confirm=raw["confirm_day_s"], sigma_low=float(raw["sigma_s"]),
        high_pivot=raw["pivot_day_l"], high_confirm=raw["confirm_day_l"], sigma_high=float(raw["sigma_l"]),
        original_E0_event=int(raw["original_E0_event"]), original_E0_target=original["E0"],
        original_I_target=original["I"], original_CP_delta_frontier=original["frontier"],
        original_CP_receipt=original["receipt"], original_CP_candidate_a=original["candidate"],
        original_CP_phase=original["phase"], original_CP_reset_reason=original["reason"],
        static_frontier_and_R=frontier_r,
        static_frontier_R_B=frontier_r and b >= 0.0,
        static_receipt_and_R=receipt_r,
        static_receipt_R_B=receipt_r and b >= 0.0,
        new_probe_or_add_order="NOT_COMPUTED_CONSUMPTION_STATE_UNSPECIFIED",
    )
    assert row["low_confirm"] <= row["date"] and row["high_confirm"] <= row["date"]
    out.append(row)

out.sort(key=lambda row: (row["sid"], row["date"]))
assert len(out) == 21
with (ROOT / "ALL21_DAYS_R_B_ORIGINAL_CP_STATIC_QUALIFICATIONS.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(out[0]))
    writer.writeheader()
    writer.writerows(out)
(ROOT / "ALL21_DAYS_R_B_ORIGINAL_CP_STATIC_QUALIFICATIONS.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")

counts = {}
for sid in ("000620.SZ", "002583.SZ"):
    group = [row for row in out if row["sid"] == sid]
    counts[sid] = {
        "scope": [group[0]["date"], group[-1]["date"]], "observations": len(group),
        "CP_frontier_and_R": sum(row["static_frontier_and_R"] for row in group),
        "CP_receipt_and_R": sum(row["static_receipt_and_R"] for row in group),
        "frontier_R_B": sum(row["static_frontier_R_B"] for row in group),
        "receipt_R_B": sum(row["static_receipt_R_B"] for row in group),
        "frontier_only_extra_dates": [row["date"] for row in group if row["static_frontier_and_R"] and not row["static_receipt_and_R"]],
        "receipt_R_rejected_by_B_dates": [row["date"] for row in group if row["static_receipt_and_R"] and not row["static_receipt_R_B"]],
    }

main = [row for row in out if (row["sid"] == "000620.SZ" and row["date"] >= "2022-01-20") or
        (row["sid"] == "002583.SZ" and row["date"] >= "2024-09-24")]
table = [
    "R与B为各自E0锚确认日冻结CP z下的价格位置，不是风险权重。D为旧高后的累计负log路程，独立展示。",
    "原CP新前沿不等于receipt；下表只列静态条件，不模拟一次性消费或新订单。",
    "",
    "| 股票/日期 | 原收盘 | R | B | D_down | 下跌数/反复数 | 原fresh | 原receipt | B>=0 |",
    "|---|---:|---:|---:|---:|---:|---:|:---:|:---:|",
]
for row in main:
    stock = "盈新" if row["sid"] == "000620.SZ" else "海能"
    table.append(f"| {stock} {row['date']} | {row['close_raw']:.2f} | {row['R']:+.6f} | {row['B']:+.6f} | {row['down_log_distance']:.6f} | {row['n_down']}/{row['n_turn_zeros_removed']} | {row['original_CP_delta_frontier']:+.6f} | {'是' if row['original_CP_receipt'] else '否'} | {'是' if row['B'] >= 0 else '否'} |")
(ROOT / "MAIN19_DAYS_READOUT.txt").write_text("\n".join(table)+"\n")
scope = dict(
    status="STATIC_R_B_SOURCE_SUBSTITUTION_ONLY_NOT_NEW_CP_STATE_MACHINE",
    counts=counts, no_new_states=True, new_orders=0, new_accounts=0, new_backtests=0,
    no_direction_turn_counts_inferred_from_A_L=True,
    high_semantics="latest confirmed E0 high diagnostic;not a silently frozen active failed-high barrier",
    sources={str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (src, yx_src, hy_src, yx_counts_src, hy_counts_src, Path(__file__).resolve())},
)
(ROOT / "ROOT_STATIC_SCOPE_AND_COUNTS.json").write_text(json.dumps(scope, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(counts, ensure_ascii=False, indent=2))
print("\n".join(table))

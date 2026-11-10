"""Read saved V3 output only; no state-engine import, account or return calculation."""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OUT = HERE / "v3_all4"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def csv_save(name, rows):
    with (OUT / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                          for k, v in row.items()} for row in rows)


def main():
    inputs = [OUT / "RUN_RECEIPT.json", OUT / "ALL_DAILY_TRACES.json",
              OUT / "PREFIX_CHECKS.json", HERE / "signal_trace.py",
              BASE / "SIGNAL_FREEZE_V3.md",
              BASE / "signal_traces/v2_all7/ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.json"]
    bound = {str(p): sha(p) for p in inputs}
    receipt = load(inputs[0])
    assert receipt["status"] == "V3_PURE_SIGNAL_COMPLETE"
    for p in inputs[3:5]:
        assert receipt["source_sha256"][str(p)] == sha(p)
    rows = load(inputs[1])
    prefix = load(inputs[2])
    assert len(rows) == receipt["rows"] == 1026
    assert len(prefix) == receipt["prefix_checks"] == 8
    assert all(x["prefix_exact"] for x in prefix)
    groups = defaultdict(list)
    lookup = {}
    for row in rows:
        groups[row["sid"]].append(row)
        key = (row["sid"], row["day"])
        assert key not in lookup
        lookup[key] = row
    assert len(groups) == 4
    assert all(not r["source_segment_changed"] for r in rows)
    # Old P is checked before the same CLOSE can publish a new down/reset.
    # Attribute its exit by the event's preserved cycle, not the row's final cycle.
    p_exits_by_cycle = defaultdict(list)
    for row in rows:
        for event in row["support_exit_events"]:
            p_exits_by_cycle[(row["sid"], event["recovery_cycle_preserved"])].append(event)
    cycles = []
    left = []
    for sid, series in groups.items():
        assert series == sorted(series, key=lambda r: r["day"])
        downs = [i for i, r in enumerate(series) if r["down_event"] is not None]
        if not series[0]["down_event"] and series[0]["R"] is not None:
            left.append({"sid": sid, "first_display_day": series[0]["day"],
                         "carry_in_R": series[0]["R"],
                         "recovery_cycle": series[0]["recovery_cycle"],
                         "scope": "LEFT_TRUNCATED_CONTEXT; not counted as a display-period down event"})
        for n, i in enumerate(downs):
            start = series[i]
            j = downs[n + 1] if n + 1 < len(downs) else len(series)
            block = series[i:j]
            assert all(r["recovery_cycle"] == start["recovery_cycle"] for r in block)
            trial = next((r for r in block if r["trial_event"] is not None), None)
            recovered = next((r for r in block if r["I_expand"] is True), None)
            assert start["I_expand"] is False
            if recovered:
                assert trial and trial["day"] <= recovered["day"]
            terminal = series[j] if j < len(series) else series[-1]
            replacement = j < len(series)
            pivot = start["R"]
            pivot_row = lookup.get((sid, pivot["pivot_day"]))
            raw_R = None
            if pivot_row and pivot_row["C"] is not None:
                a, b = pivot_row["C"], pivot["price_adjusted"]
                gamma4 = 4 * (2 ** -53) / (1 - 4 * (2 ** -53))
                if abs(a - b) <= gamma4 * max(a, b):
                    raw_R = pivot_row["raw_C"]
            lag = lambda r: None if r is None else r["effective_CLOSE_observation_index"] - start["effective_CLOSE_observation_index"]
            cycles.append({
                "sid": sid, "recovery_cycle": start["recovery_cycle"],
                "down_confirmed_at": start["day"], "R_pivot_day": pivot["pivot_day"],
                "R_adjusted": pivot["price_adjusted"], "R_raw_from_saved_pivot_close": raw_R,
                "R_source": pivot, "down_C": start["C"], "down_raw_C": start["raw_C"],
                "previous_expand": start["down_event"]["previous_expand"],
                "P_before_down": start["P_old"], "P_after_down": start["P_new"],
                "first_new_up_at": None if trial is None else trial["day"],
                "first_new_up_C": None if trial is None else trial["C"],
                "first_new_up_raw_C": None if trial is None else trial["raw_C"],
                "first_new_up_lag_valid_close": lag(trial),
                "first_recovered_at": None if recovered is None else recovered["day"],
                "first_recovered_C": None if recovered is None else recovered["C"],
                "first_recovered_raw_C": None if recovered is None else recovered["raw_C"],
                "first_recovery_lag_valid_close": lag(recovered),
                "cycle_endpoint_at": terminal["day"],
                "endpoint_kind": "NEXT_DOWN_REPLACES_R" if replacement else "SAMPLE_END",
                "recovery_outcome": "RECOVERED" if recovered else "UNRECOVERED_RIGHT_CENSORED",
                "censor_reason": None if recovered else ("NEXT_DOWN_REPLACES_R" if replacement else "SAMPLE_END"),
                "elapsed_valid_close_to_endpoint": lag(terminal),
                "last_same_cycle_display_day": block[-1]["day"],
                "valid_close_rows_before_recovery_or_endpoint": sum(r["price_close_valid"] for r in block if not recovered or r["day"] < recovered["day"]),
                "P_exit_events_not_censors": p_exits_by_cycle[(sid, start["recovery_cycle"])],
                "price_above_R_before_up_days": [r["day"] for r in block if r["PRICE_ABOVE_R_BEFORE_UP"]],
            })
    original = load(inputs[5])
    joined = []
    for source in original:
        if source["sid"] not in groups:
            continue
        key = source["sid"], source["original_signal_at"][:10]
        row = lookup[key]
        annotation = {k: v for k, v in source.items() if k.startswith("original_") or k in ("window", "sid")}
        annotation.update({
            "signal_day": row["day"], "C": row["C"], "raw_C": row["raw_C"],
            "mode": row["mode"], "I_hold": row["I_hold"], "I_expand": row["I_expand"],
            "A_active": row["A_active"], "B_active": row["B_active"], "B_base": row["B_base"],
            "P_old": row["P_old"], "P_new": row["P_new"], "P_source": row["P_source"],
            "R": row["R"], "up_after_R": row["up_after_R"],
            "recovery_cycle": row["recovery_cycle"], "L1": row["L1"], "H12": row["H12"], "L2": row["L2"],
            "trial_event": row["trial_event"], "support_exit_events": row["support_exit_events"],
            "V2_I_expand_comparison_only": source["I_expand"],
            "current_mature_permission_withdrawn_vs_V2": source["I_expand"] is True and row["I_expand"] is False,
            "scope": "Original funded-layer signal annotation only. Not a predicted candidate order/fill/quantity or return; trial consumption, new CP and funding paths not simulated.",
        })
        joined.append(annotation)
    assert len(joined) == 20
    assert Counter(r["sid"] for r in joined) == {"000620.SZ": 6, "601019.SH": 8, "601601.SH": 3, "002583.SZ": 3}
    assert len({(r["sid"], r["original_layer"]) for r in joined}) == 20
    b_true = [r for r in rows if r["B_active"] is True]
    counterexamples = [r for r in b_true if r["A_active"] is not True]
    before_up = [{k: r[k] for k in ("sid", "day", "C", "raw_C", "R", "I_expand", "mode")} for r in rows if r["PRICE_ABOVE_R_BEFORE_UP"]]
    counts = {}
    for sid, series in groups.items():
        subset = [c for c in cycles if c["sid"] == sid]
        counts[sid] = {"display_rows": len(series), "down_logs": len(subset),
                       "down_with_previous_expand_true": sum(c["previous_expand"] is True for c in subset),
                       "recovered_cycles": sum(c["first_recovered_at"] is not None for c in subset),
                       "unrecovered_cycles": sum(c["first_recovered_at"] is None for c in subset),
                       "B_true_rows": sum(r["B_active"] is True for r in series),
                       "price_above_R_before_up_rows": sum(r["PRICE_ABOVE_R_BEFORE_UP"] for r in series)}
    summary = {"per_stock": counts, "down_logs": len(cycles),
               "down_with_previous_expand_true": sum(c["previous_expand"] is True for c in cycles),
               "B_true_rows": len(b_true), "B_true_A_not_true_rows": len(counterexamples),
               "B_true_A_not_true_examples": counterexamples,
               "price_above_R_before_up_rows": len(before_up),
               "original_actual_funded_layer_signal_rows": len(joined),
               "original_actual_signal_I_expand_counts": dict(Counter(str(r["I_expand"]) for r in joined)),
               "original_layers_with_mature_permission_withdrawn_vs_V2": [
                   {"sid": r["sid"], "layer": r["original_layer"], "signal_day": r["signal_day"]}
                   for r in joined if r["current_mature_permission_withdrawn_vs_V2"]],
               "no_state_rerun": True, "no_account_or_orders": True,
               "observation_clock": "Saved effective_CLOSE_observation_index: comparable valid close, including valid-close/missing-volume rows. Lag=start-to-end index difference; next valid close is 1.",
               "cycle_censor": "Only next down replaces R or sample end. P exits recorded separately, never cycle censors.",
               "endpoint_elapsed_note": "Next-down elapsed lag includes the replacement endpoint; old-cycle eligible rows exclude replacement. SAMPLE_END is the last saved display row.",
               "source_segment_changes_in_display": 0,
               "original_signal_annotations": "Sealed V2 original-layer annotations reused, candidate columns replaced by saved V3 values; not new account evidence."}
    save("RECOVERY_CYCLES.json", cycles)
    csv_save("RECOVERY_CYCLES.csv", cycles)
    save("LEFT_TRUNCATED_CYCLE_CONTEXT.json", left)
    sea = [c for c in cycles if c["sid"] == "002583.SZ"]
    save("SEA_ALL_DOWN_CYCLES.json", sea)
    csv_save("SEA_ALL_DOWN_CYCLES.csv", sea)
    save("SEA_MAIN_UPTREND_DOWN_CYCLES.json", [c for c in sea if "2024-09-19" <= c["down_confirmed_at"] <= "2024-11-27"])
    save("ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.json", joined)
    csv_save("ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.csv", joined)
    save("B_IMPLIES_A_AND_COUNTS.json", summary)
    save("PRICE_ABOVE_R_BEFORE_UP.json", before_up)
    points = {"000620.SZ": {"2022-01-17", "2022-01-20", "2022-01-21", "2022-01-24", "2022-01-26", "2022-02-07"},
              "002583.SZ": {"2024-09-19", "2024-09-20", "2024-09-27", "2024-09-30", "2024-10-10", "2024-10-11", "2024-11-04", "2024-11-20", "2024-11-25", "2024-11-26"},
              "601601.SH": {"2024-09-09", "2024-09-18", "2024-09-23", "2024-09-24", "2024-10-09"},
              "601019.SH": {"2022-08-31", "2022-11-07", "2022-12-12", "2023-01-03", "2023-02-10", "2023-03-10", "2023-06-19", "2023-06-26"}}
    save("FIXED_KEY_DAYS.json", [r for r in rows if r["day"] in points[r["sid"]]])
    assert all(sha(Path(p)) == expected for p, expected in bound.items())
    outputs = ["RECOVERY_CYCLES.json", "RECOVERY_CYCLES.csv", "LEFT_TRUNCATED_CYCLE_CONTEXT.json",
               "SEA_ALL_DOWN_CYCLES.json", "SEA_ALL_DOWN_CYCLES.csv", "SEA_MAIN_UPTREND_DOWN_CYCLES.json",
               "ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.json", "ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.csv",
               "B_IMPLIES_A_AND_COUNTS.json", "PRICE_ABOVE_R_BEFORE_UP.json", "FIXED_KEY_DAYS.json"]
    save("SAVED_OUTPUT_POSTPROCESS_RECEIPT.json", {
        "status": "PASS_SAVED_OUTPUT_ONLY", "script_sha256": sha(Path(__file__)),
        "input_sha256": bound, "output_sha256": {str(OUT / n): sha(OUT / n) for n in outputs},
        "original_core_and_freeze_match_runtime_receipt": True,
        "rows": len(rows), "prefix_checks_reused": 8, "cycle_rows": len(cycles),
        "original_actual_signal_join_rows": len(joined),
        "state_runs": 0, "new_accounts": 0, "new_orders": 0, "new_returns": 0})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("SEA", json.dumps([{k: c[k] for k in ("down_confirmed_at", "R_raw_from_saved_pivot_close", "first_new_up_at", "first_new_up_lag_valid_close", "first_recovered_at", "first_recovery_lag_valid_close", "endpoint_kind", "elapsed_valid_close_to_endpoint", "previous_expand")} for c in sea], ensure_ascii=False))
    print("JOIN", json.dumps([{k: r[k] for k in ("sid", "original_layer", "signal_day", "I_expand", "mode")} for r in joined], ensure_ascii=False))


if __name__ == "__main__":
    main()

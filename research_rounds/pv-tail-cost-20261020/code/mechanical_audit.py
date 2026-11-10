"""Read-only audit of saved signals and saved episodes; no account engine.

Prints diagnostic JSON to stdout. It never generates targets or simulates trades.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "TradingAlarm/research/results/pv-event-structure-20261020"
EPS = 1e-10


def audit_signals():
    summaries, exits, promotions, memory = [], [], [], []
    frames = {}
    for path in sorted(SOURCE.glob("*-signals.csv")):
        symbol = path.name.removesuffix("-signals.csv")
        f = pd.read_csv(path)
        frames[symbol] = f
        last_high = np.nan
        entry_index = None
        current_promotions = []
        symbol_exits = []
        previous_direction = np.nan
        previous_floor = np.nan
        previous_target = 0
        for i, r in f.iterrows():
            if r.entered == 1:
                entry_index = i
                current_promotions = []
            if r.event == -1:
                last_high = r.confirmed_pivot
            if (r.event == 1 and previous_target == 1 and r.exited == 0
                    and r.structure_floor > previous_floor + EPS):
                p = {
                    "symbol": symbol, "date": r.date, "index": i,
                    "structure_entry": f.iloc[entry_index].date,
                    "old_floor": float(np.exp(previous_floor)),
                    "new_floor": float(np.exp(r.structure_floor)),
                    "preceding_confirmed_high": float(np.exp(last_high)),
                    "confirmation_close": float(r.close),
                    "below_high_at_promotion": bool(np.log(r.close) <= last_high + EPS),
                }
                current_promotions.append(p)
                promotions.append(p)
            if r.exited == 1:
                q = {
                    "symbol": symbol, "date": r.date, "index": i,
                    "structure_entry": f.iloc[entry_index].date,
                    "entry_index": int(entry_index),
                    "close": float(r.close),
                    "leg_before_exit": float(previous_direction),
                    "leg_after_exit": float(r.leg_direction),
                    "event_at_exit": float(r.event),
                    "promotions_in_structure": len(current_promotions),
                    "first_structure_floor_failure": not current_promotions,
                    "last_promotion_unvalidated": False,
                    "new_floor_only_unvalidated_exit": False,
                }
                for p in current_promotions:
                    segment = f.iloc[p["index"]:i+1]
                    p["structure_exit"] = r.date
                    p["subsequently_exceeded_high"] = bool(
                        segment.close.max() > p["preceding_confirmed_high"] * (1 + EPS)
                    )
                if current_promotions:
                    p = current_promotions[-1]
                    q.update({
                        "last_promotion": p["date"],
                        "last_promotion_high": p["preceding_confirmed_high"],
                        "previous_floor": p["old_floor"],
                        "last_promotion_unvalidated": not p["subsequently_exceeded_high"],
                        "new_floor_only_unvalidated_exit":
                            not p["subsequently_exceeded_high"]
                            and r.close > p["old_floor"] * (1 + EPS),
                    })
                exits.append(q)
                symbol_exits.append(q)
                # The diagnosed window ends at the next existing entry, not a
                # hindsight-labelled new campaign or a hypothetical reset entry.
                candidates = f.index[(f.index > i) & f.entered.eq(1)]
                end = int(candidates[0]) if len(candidates) else len(f)
                gap = f.iloc[i+1:end]
                if r.leg_direction == 1:
                    memory.append({
                        "symbol": symbol, "exit": r.date,
                        "previous_leg": float(previous_direction),
                        "event_at_exit": float(r.event),
                        "next_entry": str(f.iloc[end].date) if end < len(f) else None,
                        "flat_observations": len(gap),
                        "flat_up_observations": int(gap.leg_direction.eq(1).sum()),
                        "max_close_vs_exit": float(gap.close.max() / r.close - 1)
                        if len(gap) else None,
                        "min_close_vs_exit": float(gap.close.min() / r.close - 1)
                        if len(gap) else None,
                    })
            previous_target = r.target
            previous_floor = r.structure_floor
            previous_direction = r.leg_direction
        for p in current_promotions:
            if "structure_exit" not in p:
                p["structure_exit"] = None
                p["subsequently_exceeded_high"] = bool(
                    f.iloc[p["index"]:].close.max() >
                    p["preceding_confirmed_high"] * (1 + EPS)
                )
        sx = pd.DataFrame(symbol_exits)
        sp = [p for p in promotions if p["symbol"] == symbol]
        summaries.append({
            "symbol": symbol, "rows": len(f),
            "start": f.date.iloc[0], "end": f.date.iloc[-1],
            "exits": len(sx),
            "up_leg_exit": int(sx.leg_after_exit.eq(1).sum()),
            "floor_promotions": len(sp),
            "promotions_below_prior_high": sum(p["below_high_at_promotion"] for p in sp),
            "first_floor_exits": int(sx.first_structure_floor_failure.sum()),
            "promoted_floor_exits": int((sx.promotions_in_structure > 0).sum()),
            "unvalidated_last_promotion_exits": int(sx.last_promotion_unvalidated.sum()),
            "unvalidated_new_floor_only_exits": int(sx.new_floor_only_unvalidated_exit.sum()),
        })
    return frames, summaries, exits, promotions, memory


def audit_saved_accounts(frames, exits):
    """Join existing closed episodes via saved negative order signal_date."""
    reports = {}
    joined = []
    for group in ("etf17", "hk7"):
        episodes = json.loads((SOURCE / f"{group}-pv-base-episodes.json").read_text())
        orders = json.loads((SOURCE / f"{group}-pv-base-orders.json").read_text())
        for e in episodes:
            if e["status"] != "closed":
                continue
            sales = [o for o in orders if o["symbol"] == e["symbol"]
                     and o["units"] < 0 and e["entry"] <= o["date"] <= e["exit"]]
            signal_dates = sorted({o["signal_date"] for o in sales})
            matching = [x for x in exits if x["symbol"] == e["symbol"]
                        and x["date"] <= signal_dates[-1]] if signal_dates else []
            x = matching[-1] if matching else None
            unambiguous = bool(x and signal_dates[0] <= x["date"] <= signal_dates[-1])
            if not unambiguous and x and signal_dates:
                # Some sell orders repeat an already flat market signal. Validate
                # no intervening market entry before the final order's signal.
                f = frames[e["symbol"]]
                between = f[(f.date > x["date"]) & (f.date <= signal_dates[-1])]
                unambiguous = bool(x["date"] >= e["entry"] and not between.entered.eq(1).any())
            row = dict(e)
            exits_during_episode = [
                k["date"] for k in exits
                if k["symbol"] == e["symbol"]
                and e["entry"] <= k["date"] <= signal_dates[-1]
            ] if signal_dates else []
            row.update({"group": group, "sell_signal_dates": signal_dates,
                        "mechanical_exit": x["date"] if x else None,
                        "join_valid": unambiguous,
                        "structure_exit_dates_during_episode": exits_during_episode,
                        "mixed_signal_episode": len(exits_during_episode) != 1})
            if x:
                row.update({k: v for k, v in x.items()
                            if k not in ("date", "symbol", "index", "close")})
            joined.append(row)
        relevant = [j for j in joined if j["group"] == group]
        losses = [j for j in relevant if j["label"] == "ordinary" and j["pnl"] < 0]
        early = [j for j in losses if j["signal_close_mfe"] < .05]
        groups = {}
        for name, data in (("all_closed", relevant), ("ordinary_losers", losses),
                           ("ordinary_losers_mfe_below_5pct", early),
                           ("ordinary_losers_single_exit", [j for j in losses if not j["mixed_signal_episode"]]),
                           ("ordinary_losers_mfe_below_5pct_single_exit", [j for j in early if not j["mixed_signal_episode"]])):
            groups[name] = {
                "count": len(data), "pnl": sum(j["pnl"] for j in data),
                "invalid_joins": [j["id"] for j in data if not j["join_valid"]],
                "first_floor": {"count": sum(j.get("first_structure_floor_failure", False) for j in data),
                                "pnl": sum(j["pnl"] for j in data if j.get("first_structure_floor_failure", False))},
                "promoted_floor": {"count": sum(j.get("promotions_in_structure", 0) > 0 for j in data),
                                   "pnl": sum(j["pnl"] for j in data if j.get("promotions_in_structure", 0) > 0)},
                "unvalidated_last_promotion": {
                    "count": sum(j.get("last_promotion_unvalidated", False) for j in data),
                    "pnl": sum(j["pnl"] for j in data if j.get("last_promotion_unvalidated", False))},
                "unvalidated_new_floor_only": {
                    "count": sum(j.get("new_floor_only_unvalidated_exit", False) for j in data),
                    "pnl": sum(j["pnl"] for j in data if j.get("new_floor_only_unvalidated_exit", False))},
            }
        reports[group] = groups
    return reports, joined


def main():
    frames, summaries, exits, promotions, memory = audit_signals()
    accounts, joins = audit_saved_accounts(frames, exits)
    manifest = json.loads((ROOT / "research_rounds/pv-tail-cost-20261020/inputs/source-manifest.json").read_text())
    needed = [p for p in manifest if p.endswith("-signals.csv")
              or p.endswith("-pv-base-episodes.json") or p.endswith("-pv-base-orders.json")]
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == manifest[p] for p in needed}
    assert all(hashes.values()), "Saved source changed"
    code_path = ROOT / "research_rounds/pv-tail-cost-20261020/code/baseline_event_structure.py"
    baseline_sha256 = hashlib.sha256(code_path.read_bytes()).hexdigest()
    protocol = json.loads((ROOT / "research_rounds/pv-tail-cost-20261020/protocol.json").read_text())
    assert baseline_sha256 == protocol["baseline_sha256"]
    assert sum(x["exits"] for x in summaries) == 871
    assert len(joins) == 585 and all(j["join_valid"] for j in joins)
    print(json.dumps({"baseline_sha256": baseline_sha256, "source_hash_checks": hashes, "summaries": summaries,
                      "accounts": accounts, "memory": memory,
                      "exits": exits, "promotions": promotions, "joined": joins},
                     indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

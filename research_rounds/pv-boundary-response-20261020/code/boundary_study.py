"""Frozen-boundary observation ledger and layered prefix views; no classifier.

All functions before main are import-safe. Price observations do not depend on
ordinary volume availability. Future response labels live in a separate table.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BASE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def boolean_column(frame, name, default):
    if name not in frame:
        return pd.Series(default, index=frame.index)
    return frame[name].astype(str).str.lower().isin(["true", "1", "1.0"])


def eligible_prices(frame, symbol="", exclude_dates=()):
    """Independent price clock, preserving flat ranges and unknown volume.

    Explicit source-invalid flags, source_anomaly strings, observed/synthetic
    metadata and separately audited exclusion dates are honored. Legacy `valid`
    and `geometry_valid` columns are deliberately not used.
    """
    out = frame.copy()
    if "date" in out:
        out["date"] = pd.to_datetime(out["date"])
        out = out.set_index("date")
    out.index = pd.to_datetime(out.index)
    if not out.index.is_unique or not out.index.is_monotonic_increasing:
        raise ValueError("price input must have unique increasing dates")
    ohlc = out[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    finite = np.isfinite(ohlc).all(axis=1) & ohlc.gt(0).all(axis=1)
    geometry = (
        ohlc.high.ge(ohlc.low)
        & ohlc.high.ge(ohlc[["open", "close"]].max(axis=1))
        & ohlc.low.le(ohlc[["open", "close"]].min(axis=1))
    )
    anomaly = (
        out.source_anomaly.fillna("").astype(str).str.strip().ne("")
        if "source_anomaly" in out else pd.Series(False, index=out.index)
    )
    source_invalid = boolean_column(out, "source_invalid", False)
    keep = (
        finite & geometry
        & boolean_column(out, "observed_bar", True)
        & ~boolean_column(out, "synthetic_event_bar", False)
        & ~source_invalid & ~anomaly
        & ~out.index.isin(pd.to_datetime(list(exclude_dates)))
    )
    out.loc[:, ["open", "high", "low", "close"]] = ohlc
    if "volume" not in out:
        out["volume"] = np.nan
    out["volume"] = pd.to_numeric(out.volume, errors="coerce")
    return out.loc[keep].copy()


def _date(value):
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def case_facts(frame, case, lookback=21, window=21):
    """Return a causal two-row-per-day ledger and serializable case metadata."""
    dates = frame.index
    candidate = np.flatnonzero(
        (dates >= pd.Timestamp(case["anchor_requested"]))
        & (dates >= pd.Timestamp(case["start"]))
        & (dates <= pd.Timestamp(case["end"]))
    )
    meta = {
        "case": case["id"], "symbol": case["symbol"],
        "anchor_requested": case["anchor_requested"], "status": "pending",
        "lookback": lookback, "window": window,
    }
    if not len(candidate):
        meta["status"] = "no_eligible_anchor"
        return pd.DataFrame(), meta
    anchor_idx = int(candidate[0])
    meta.update(anchor_idx=anchor_idx, effective_anchor=_date(dates[anchor_idx]))
    if anchor_idx < lookback:
        meta.update(status="insufficient_prior_price_observations",
                    prior_observations=anchor_idx)
        return pd.DataFrame(), meta
    prior = frame.iloc[anchor_idx - lookback:anchor_idx]
    end_idx = min(anchor_idx + window - 1, len(frame) - 1)
    end_idx = min(end_idx, int(np.searchsorted(dates, pd.Timestamp(case["end"]), side="right")) - 1)
    upper, lower = float(prior.high.max()), float(prior.low.min())
    known_prior_volume = prior.volume[np.isfinite(prior.volume) & prior.volume.gt(0)]
    reference = float(known_prior_volume.median()) if len(known_prior_volume) else np.nan
    meta.update(
        status="ready", prior_start_date=_date(prior.index[0]),
        prior_end_date=_date(prior.index[-1]), prior_observations=len(prior),
        upper_boundary=upper, lower_boundary=lower,
        volume_reference=reference, volume_reference_known_count=len(known_prior_volume),
        window_end_date=_date(dates[end_idx]), window_observations=end_idx - anchor_idx + 1,
        window_capped_before_21=(end_idx - anchor_idx + 1 < window),
    )
    state = {
        side: dict(touched=False, gap=0, outside_run=0, previous_outside=False,
                   first_touch_date="", touch_count=0, recontacts=0, q_values=[],
                   since_first_count=0)
        for side in ("upper", "lower")
    }
    rows = []
    for i in range(anchor_idx, end_idx + 1):
        r = frame.iloc[i]
        date = _date(dates[i])
        spread = float(r.high - r.low)
        location = float((r.close - r.low) / spread) if spread > 0 else np.nan
        volume_known = bool(np.isfinite(r.volume) and r.volume > 0)
        q = float(r.volume / reference) if volume_known and np.isfinite(reference) and reference > 0 else np.nan
        for side, boundary in (("upper", upper), ("lower", lower)):
            s = state[side]
            touch = bool(r.high >= boundary) if side == "upper" else bool(r.low <= boundary)
            outside = bool(r.close > boundary) if side == "upper" else bool(r.close < boundary)
            recontact = bool(touch and s["touched"] and s["gap"] >= 1)
            gap_before = s["gap"]
            returned = bool(s["previous_outside"] and not outside)
            s["outside_run"] = s["outside_run"] + 1 if outside else 0
            if touch:
                if not s["touched"]:
                    s["first_touch_date"] = date
                s["touched"], s["gap"] = True, 0
                s["touch_count"] += 1
                s["recontacts"] += int(recontact)
            elif s["touched"]:
                s["gap"] += 1
            if s["touched"]:
                s["since_first_count"] += 1
                if np.isfinite(q):
                    s["q_values"].append(q)
            s["previous_outside"] = outside
            direction = 1 if side == "upper" else -1
            rows.append({
                "case": case["id"], "symbol": case["symbol"], "date": date,
                "observation_in_window": i - anchor_idx,
                "effective_anchor": meta["effective_anchor"],
                "boundary": side, "boundary_value": boundary,
                "upper_boundary": upper, "lower_boundary": lower,
                "open": float(r.open), "high": float(r.high), "low": float(r.low),
                "close": float(r.close), "volume": float(r.volume),
                "volume_known": volume_known, "volume_reference": reference,
                "volume_reference_known_count": len(known_prior_volume), "q": q,
                "range": spread, "zero_range": spread == 0,
                "close_location": location, "close_location_defined": spread > 0,
                "touch": touch, "close_outside": outside,
                "close_at_boundary": bool(r.close == boundary),
                "touch_and_close_inside": bool(touch and not outside),
                "consecutive_outside": s["outside_run"],
                "return_inside_after_outside": returned,
                "recontact_after_no_touch": recontact,
                "whole_no_touch_observations_before": gap_before,
                "first_touch_date": s["first_touch_date"],
                "touch_observations_to_date": s["touch_count"],
                "recontacts_to_date": s["recontacts"],
                "close_minus_boundary": float(r.close - boundary),
                "oriented_close_distance": direction * float(r.close - boundary),
                "oriented_log_close_distance": direction * float(np.log(r.close / boundary)),
                "close_minus_upper": float(r.close - upper),
                "close_minus_lower": float(r.close - lower),
                "since_first_observations": s["since_first_count"],
                "since_first_q_known_count": len(s["q_values"]),
                "since_first_q_sum_known": float(sum(s["q_values"])) if s["q_values"] else np.nan,
                "since_first_q_mean_known": float(np.mean(s["q_values"])) if s["q_values"] else np.nan,
                "since_first_q_unknown_count": s["since_first_count"] - len(s["q_values"]),
                "same_day_order_known": False,
            })
    return pd.DataFrame(rows), meta


def select_events(ledger):
    """Earliest contact plus earliest same-side recontact; at most two dates.

    If the first day touches both boundaries, both are retained without ordering.
    The second date is the earliest recontact of either initially touched side.
    """
    if ledger.empty:
        return []
    first = ledger.iloc[0]
    contacts = ledger.loc[ledger.touch]
    if contacts.empty:
        last = ledger.iloc[-1]
        return [{
            "event_id": f"{first['case']}-E1", "case": first["case"],
            "symbol": first["symbol"], "date": last["date"],
            "selected_boundaries": [], "selection_kind": "no_contact",
            "upper_boundary": float(first.upper_boundary),
            "lower_boundary": float(first.lower_boundary),
            "effective_anchor": first.effective_anchor,
        }]
    date = contacts.date.min()
    sides = contacts.loc[contacts.date.eq(date), "boundary"].tolist()
    selections = [(date, sides, "first_contact")]
    recontacts = ledger.loc[
        ledger.date.gt(date) & ledger.boundary.isin(sides)
        & ledger.recontact_after_no_touch
    ]
    if not recontacts.empty:
        red = recontacts.date.min()
        selections.append((red, recontacts.loc[recontacts.date.eq(red), "boundary"].tolist(),
                           "first_same_boundary_recontact"))
    result = []
    for n, (date, selected_sides, kind) in enumerate(selections, 1):
        result.append({
            "event_id": f"{first['case']}-E{n}", "case": first["case"],
            "symbol": first["symbol"], "date": date,
            "selected_boundaries": selected_sides, "selection_kind": kind,
            "upper_boundary": float(first.upper_boundary),
            "lower_boundary": float(first.lower_boundary),
            "effective_anchor": first.effective_anchor,
        })
    return result


def response_outcomes(frame, selections, case, horizons=(1, 5)):
    """Future response facts only; not used by causal ledger or event selection."""
    rows = []
    for selection in selections:
        if selection["selection_kind"] == "no_contact":
            continue
        start = int(frame.index.get_loc(pd.Timestamp(selection["date"])))
        future = frame.iloc[start + 1:]
        future = future.loc[:case["end"]]
        for side in selection["selected_boundaries"]:
            boundary = selection[f"{side}_boundary"]
            direction = 1 if side == "upper" else -1
            for horizon in horizons:
                available = min(horizon, len(future))
                observed = future.iloc[:available]
                complete = available == horizon
                endpoint = observed.iloc[-1] if complete else None
                row = {
                    "event_id": selection["event_id"], "case": case["id"],
                    "symbol": case["symbol"], "event_date": selection["date"],
                    "boundary": side, "boundary_value": boundary,
                    "horizon": horizon, "available_observations": available,
                    "censored": not complete,
                    "response_date": _date(observed.index[-1]) if complete else "",
                    "response_close": float(endpoint.close) if complete else np.nan,
                    "oriented_close_distance": direction * (float(endpoint.close) - boundary) if complete else np.nan,
                    "close_outside": bool(direction * (endpoint.close - boundary) > 0) if complete else None,
                    "observed_prefix_last_date": _date(observed.index[-1]) if len(observed) else "",
                    "future_outside_count_observed": int((direction * (observed.close - boundary) > 0).sum()),
                    "label_scope": "future observed response; not an as-of fact or trading result",
                }
                rows.append(row)
    return pd.DataFrame(rows)


def prefix_data(frame, meta, selection, case, stage):
    end = pd.Timestamp(selection["date"])
    extra = 0
    if stage == "O":
        start_idx = int(frame.index.get_loc(end))
        future = frame.iloc[start_idx + 1:].loc[:case["end"]].iloc[:5]
        extra = len(future)
        if extra:
            end = future.index[-1]
    prefix = frame.loc[meta["prior_start_date"]:end].copy()
    return prefix, extra


def draw_view(frame, meta, selection, case, stage, destination):
    """Each axis is computed from shown prefix only; P/H never include volume."""
    prefix, extra = prefix_data(frame, meta, selection, case, stage)
    volume_view = stage in ("V", "O")
    fig, axes = plt.subplots(
        2 if volume_view else 1, 1, figsize=(12.5, 7 if volume_view else 5.5),
        sharex=True, squeeze=False,
        gridspec_kw={"height_ratios": [3, 1]} if volume_view else None,
    )
    ax = axes[0, 0]
    x = np.arange(len(prefix))
    anchor_x = int(prefix.index.get_loc(pd.Timestamp(meta["effective_anchor"])))
    event_x = int(prefix.index.get_loc(pd.Timestamp(selection["date"])))
    ax.axvspan(-.6, anchor_x - .5, color="#eeeeee", alpha=.85, zorder=-4)
    ax.axvline(anchor_x - .5, color="#777777", ls=":", lw=1)
    ax.text(.01, .015, "Shaded: prior 21 boundary observations | dashed divider: anchor",
            transform=ax.transAxes, fontsize=8, color="#555555")
    if stage == "P":
        ax.plot(x, prefix.close, color="#252525", lw=1.5, label="Close")
        low, high = float(prefix.close.min()), float(prefix.close.max())
    else:
        for j, row in enumerate(prefix.itertuples()):
            color = "#246b8e" if row.close >= row.open else "#b55d35"
            ax.vlines(j, row.low, row.high, color=color, lw=1)
            bottom, top = min(row.open, row.close), max(row.open, row.close)
            if top == bottom:
                ax.hlines(row.close, j - .3, j + .3, color=color, lw=1.6)
            else:
                ax.add_patch(Rectangle((j - .28, bottom), .56, top - bottom,
                                       facecolor=color, edgecolor=color, alpha=.8))
        ax.plot([], [], color="#246b8e", label="OHLC: close >= open")
        ax.plot([], [], color="#b55d35", label="OHLC: close < open")
        low, high = float(prefix.low.min()), float(prefix.high.max())
    for side, color in (("upper", "#8a426e"), ("lower", "#4b6b33")):
        value = meta[f"{side}_boundary"]
        ax.axhline(value, color=color, lw=1.1, ls="--", label=f"Fixed {side} boundary")
        low, high = min(low, value), max(high, value)
    ax.axvline(event_x, color="#8e328b", lw=1, ls=":")
    ax.scatter([event_x], [prefix.loc[selection["date"], "close"]],
               s=120, marker="*", color="#8e328b", edgecolors="white",
               zorder=8, label="Selected observation")
    if stage == "O":
        ax.axvspan(event_x + .5, len(prefix) - .4, color="#ffe7ad", alpha=.32)
    logpad = max((np.log(high) - np.log(low)) * .09, .004)
    ax.set_yscale("log")
    ax.set_ylim(np.exp(np.log(low) - logpad), np.exp(np.log(high) + logpad))
    ax.set_xlim(-.6, len(prefix) - .4)
    ax.set_ylabel("Price (log axis; source-adjusted units)")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(alpha=.16)
    if volume_view:
        vax = axes[1, 0]
        volumes = prefix.volume.where(np.isfinite(prefix.volume) & prefix.volume.gt(0))
        vax.bar(x, volumes, color="#959595", width=.65, label="Available volume")
        vmax = float(volumes.max()) if volumes.notna().any() else 1.
        vax.set_ylim(0, vmax * 1.18)
        vax.set_ylabel("Volume\nsource units")
        vax.axvspan(-.6, anchor_x - .5, color="#eeeeee", alpha=.6)
        vax.axvline(anchor_x - .5, color="#777777", ls=":", lw=1)
        vax.axvline(event_x, color="#8e328b", ls=":", lw=1)
        qax = vax.twinx()
        ref = meta["volume_reference"]
        q = volumes / ref if np.isfinite(ref) and ref > 0 else volumes * np.nan
        qax.plot(x, q, color="#b06b00", lw=1.1, marker=".", ms=3)
        qax.axhline(1, color="#b06b00", ls="--", lw=.6)
        qmax = float(q.max()) if q.notna().any() else 1.
        qax.set_ylim(0, max(qmax, 1) * 1.18)
        qax.set_ylabel("q: fixed prior-21 positive-volume median", fontsize=8)
        if volumes.isna().any():
            vax.scatter(x[volumes.isna()], np.zeros(volumes.isna().sum()),
                        color="purple", marker="x", label="Unknown volume")
        vax.legend(loc="upper left", fontsize=7)
        vax.grid(alpha=.15)
    ticks = np.unique(np.linspace(0, len(prefix) - 1, min(9, len(prefix))).round().astype(int))
    axes[-1, 0].set_xticks(ticks)
    axes[-1, 0].set_xticklabels([_date(prefix.index[t]) for t in ticks], rotation=30,
                              ha="right", fontsize=8)
    boundary_label = "/".join(selection["selected_boundaries"]) or "none (window-end review)"
    stage_label = {"P": "Close conditional on common OHLC boundaries",
                   "H": "Add OHLC", "V": "Add volume evidence",
                   "O": f"Observed response: +{extra} eligible observations (maximum +5)"}[stage]
    fig.suptitle(
        f"{selection['event_id']} | {selection['symbol']} | {selection['date']} | boundary: {boundary_label}\n"
        f"{stage}: {stage_label}", fontsize=11)
    fig.text(.5, .012, "Historical development material. Facts only; no trend, trade or account classification.",
             ha="center", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, .035, 1, .91))
    fig.savefig(destination, dpi=115)
    limits = {
        "event_id": selection["event_id"], "stage": stage,
        "prefix_first": _date(prefix.index[0]), "prefix_last": _date(prefix.index[-1]),
        "price_xlim": list(ax.get_xlim()), "price_ylim": list(ax.get_ylim()),
        "rows": len(prefix),
    }
    plt.close(fig)
    return limits


def _dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=BASE / "results" / "v0")
    args = parser.parse_args()
    out = args.output.resolve()
    if out.parent != (BASE / "results").resolve():
        raise ValueError("outputs must be a new direct child of this round's results/")
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    protocol_path = BASE / "protocol-v0.json"
    protocol = json.loads(protocol_path.read_text())
    freeze = json.loads((BASE / "protocol-freeze.json").read_text())
    assert sha(protocol_path) == freeze["sha256"]
    manifest_path = BASE / "inputs" / "manifest.json"
    assert sha(manifest_path) == protocol["input_manifest_sha256"]
    manifest = json.loads(manifest_path.read_text())
    addendum_path = BASE / "inputs" / "observation-mask-addendum.json"
    addendum = json.loads(addendum_path.read_text())
    assert addendum["manifest_sha256"] == sha(manifest_path)
    review_order_path = BASE / "review-order-addendum.json"
    review_order = json.loads(review_order_path.read_text())
    assert review_order["protocol_sha256"] == sha(protocol_path)
    exclusions = {r["symbol"]: r["exclude_price_dates"] for r in addendum["series"]}
    source_hashes = {}
    frames, mask_audit = {}, []
    for item in manifest["series"]:
        path = BASE / "inputs" / item["output"]
        digest = sha(path)
        assert digest == item["output_sha256"]
        source_hashes[str(path)] = digest
        raw = pd.read_csv(path, index_col="date", parse_dates=True)
        clean = eligible_prices(raw, item["symbol"], exclusions[item["symbol"]])
        frames[item["symbol"]] = clean
        mask_audit.append({
            "symbol": item["symbol"], "raw_rows": len(raw), "price_rows": len(clean),
            "excluded_dates": [_date(d) for d in raw.index.difference(clean.index)],
            "unknown_volume_price_dates": [_date(d) for d in clean.index[
                ~(np.isfinite(clean.volume) & clean.volume.gt(0))]],
        })
    out.mkdir(parents=True, exist_ok=False)
    for name in ("P", "H", "V", "outcome", "ledgers"):
        (out / name).mkdir()
    source_hashes.update({
        str(protocol_path): sha(protocol_path), str(manifest_path): sha(manifest_path),
        str(addendum_path): sha(addendum_path),
        str(review_order_path): sha(review_order_path),
        str(BASE / "protocol-freeze.json"): sha(BASE / "protocol-freeze.json"),
    })
    metadata = {
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path), "code_sha256": sha(__file__),
        "input_sha256": source_hashes,
        "runtime": {"python": sys.version, "platform": platform.platform(),
                    "pandas": pd.__version__, "numpy": np.__version__,
                    "matplotlib": matplotlib.__version__},
        "interpretation": {
            "simultaneous_first_contact": "preserve both sides; intraday order unknown",
            "second_date": "earliest recontact of either initially touched side; all other events remain in ledger",
            "volume_unknown": "nonfinite or nonpositive volume; never alone removes price observation",
            "no_contact": "P/H/V window-end review, no response row or outcome chart",
            "duplicate_cases": "retained with original membership; no merging needed",
            "review_order": review_order["order"],
            "index_access": "first-index.json initially; recontact-index.json only after first V lock; outcomes last",
            "axis_limits": "computed from only shown prefix and known fixed boundaries",
        },
    }
    _dump(out / "run-metadata.json", metadata)
    (out / "boundary_study.snapshot.py").write_bytes(Path(__file__).read_bytes())
    _dump(out / "price-clock-audit.json", mask_audit)
    all_ledgers, all_selections, all_outcomes, case_meta, safe_index, limits = [], [], [], [], [], []
    for case in protocol["cases"]:
        frame = frames[case["symbol"]]
        ledger, meta = case_facts(frame, case, protocol["lookback"], protocol["window"])
        case_meta.append(meta)
        if ledger.empty:
            continue
        ledger.to_csv(out / "ledgers" / f"{case['id']}-facts.csv", index=False)
        all_ledgers.append(ledger)
        selections = select_events(ledger)
        all_selections.extend(selections)
        response = response_outcomes(frame, selections, case, protocol["response_horizons"])
        if not response.empty:
            all_outcomes.append(response)
        for selected in selections:
            safe = {k: selected[k] for k in ("event_id", "case", "symbol", "date")}
            safe["boundary"] = "|".join(selected["selected_boundaries"]) or "none"
            safe["kind"] = selected["selection_kind"]
            safe["ordinal"] = int(selected["event_id"].rsplit("E", 1)[1])
            for stage, folder in (("P", "P"), ("H", "H"), ("V", "V"), ("O", "outcome")):
                if stage == "O" and selected["selection_kind"] == "no_contact":
                    safe["outcome"] = ""
                    continue
                relative = f"{folder}/{selected['event_id']}.png"
                limits.append(draw_view(frame, meta, selected, case, stage, out / relative))
                safe[folder] = relative
            safe_index.append(safe)
    pd.concat(all_ledgers, ignore_index=True).to_csv(out / "daily-facts.csv", index=False)
    (pd.concat(all_outcomes, ignore_index=True) if all_outcomes else pd.DataFrame()).to_csv(
        out / "response-outcomes.csv", index=False)
    pd.DataFrame(safe_index).to_csv(out / "selected-events.csv", index=False)
    _dump(out / "first-index.json", [s for s in safe_index if s["ordinal"] == 1])
    _dump(out / "recontact-index.json", [s for s in safe_index if s["ordinal"] == 2])
    _dump(out / "selected-events-internal.json", all_selections)
    _dump(out / "case-metadata.json", case_meta)
    _dump(out / "plot-prefix-limits.json", limits)
    counts = {
        "cases": len(case_meta), "ready_cases": sum(c["status"] == "ready" for c in case_meta),
        "selected_dates": len(safe_index), "charts": len(limits),
        "daily_boundary_rows": sum(len(f) for f in all_ledgers),
        "response_rows": sum(len(f) for f in all_outcomes),
        "no_contact_reviews": sum(s["selection_kind"] == "no_contact" for s in all_selections),
        "account_calls": 0,
    }
    _dump(out / "counts.json", counts)
    for path, digest in source_hashes.items():
        assert sha(path) == digest
    assert sha(__file__) == metadata["code_sha256"]
    _dump(out / "manifest.json", {
        str(p.relative_to(out)): sha(p)
        for p in sorted(out.rglob("*")) if p.is_file()
    })
    print(json.dumps({"output": str(out),
                      "first_index": str(out / "first-index.json"),
                      "first_review_cases": sum(s["ordinal"] == 1 for s in safe_index),
                      "account_calls": 0}))


if __name__ == "__main__":
    main()

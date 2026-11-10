"""Offline, fixed-protocol price-volume trajectories. No trading engine imports."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from progress_model import progress_frame

BASE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def draw(frame, case, out):
    q = frame.loc[case["context_start"]:case["end"]]
    fig, ax = plt.subplots(5, 1, figsize=(14, 12), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1, 1, 1.4, 1.1]})
    ax[0].plot(q.index, q.close, "k", lw=1.3, label="close (log axis)")
    for value, color in [(1, "#e8b0aa"), (-1, "#b2cbe6")]:
        ax[0].fill_between(q.index, 0, 1, where=q.primary_direction.eq(value),
                           transform=ax[0].get_xaxis_transform(), color=color, alpha=.28,
                           step="post", label=f"primary {'up' if value == 1 else 'down'}")
    for column, color, ls in [
        ("primary_origin", "#bc8f41", "--"),
        ("parent_origin", "#703c89", ":"),
        ("parent_extreme", "#703c89", "-."),
    ]:
        ax[0].plot(q.index, np.exp(q[column]), color=color, ls=ls, lw=.8, label=column)
    for direction, marker, color in [(1, "^", "firebrick"), (-1, "v", "steelblue")]:
        pts = q[q.primary_event.eq(direction)]
        ax[0].scatter(pts.index, pts.close, marker=marker, color=color, s=28)
    ax[0].set_yscale("log")
    ax[0].legend(fontsize=7, ncol=3, loc="upper left")
    ax[1].bar(q.index, q.volume, color="gray", width=1)
    ax[1].set_ylabel("raw volume\nsource units", fontsize=8)
    vax = ax[1].twinx()
    vax.plot(q.index, q.q, color="tab:orange", lw=.7)
    vax.axhline(1, color="tab:orange", lw=.4)
    vax.set_ylabel("relative volume q", fontsize=8)
    ax[2].step(q.index, q.primary_direction, where="post", label="primary sqrt21", lw=1.4)
    ax[2].step(q.index, q.local_direction, where="post", label="local sqrt5", alpha=.4)
    ax[2].step(q.index, q.comparison_regime, where="post", label="previous HHHL structure", alpha=.45, ls=":")
    ax[2].set_yticks([-1, 0, 1])
    ax[2].legend(fontsize=7, ncol=3, loc="upper left")
    ax[3].plot(q.index, q.retention, label="current progress retained", lw=1)
    ax[3].plot(q.index, q.parent_retention, label="parent progress retained", color="#703c89", lw=1.3)
    ax[3].plot(q.index, q.recovery, label="countermove recovered (position)", color="tab:green", alpha=.5)
    ax[3].axhline(0, color="gray", ls=":", lw=.5)
    ax[3].axhline(1, color="gray", ls=":", lw=.5)
    ax[3].set_ylabel("fractions\nnot probabilities", fontsize=8)
    ax[3].legend(fontsize=7, ncol=3, loc="upper left")
    ax[4].plot(q.index, q.advance_activity, label="advance activity", alpha=.65)
    ax[4].plot(q.index, q.erosion_relative, label="retreat / advance activity", alpha=.8)
    ax[4].plot(q.index, q.recovery_relative, label="recovery / peak-to-trough activity", alpha=.7)
    ax[4].axhline(1, color="gray", ls=":", lw=.5)
    ax[4].set_ylabel("volume ratios\nno health verdict", fontsize=8)
    ax[4].legend(fontsize=7, ncol=3, loc="upper left")
    dates = case.get("screen_events", [case.get("prefix1_cutoff")])
    for date in dates:
        if not date:
            continue
        for axis in ax:
            axis.axvline(pd.Timestamp(date), color="#ad6f00", ls="--", lw=.9)
        ax[0].text(pd.Timestamp(date), .76, date, transform=ax[0].get_xaxis_transform(),
                   fontsize=7, rotation=90, va="bottom", color="#785100")
    for axis in ax:
        axis.grid(alpha=.12)
    title = case.get("proxy", "fixed development case; no trade interpretation")
    ax[0].set_title(f"{case['id']} | {case['symbol']} | {out.name}\n{title}", fontsize=11)
    ax[4].set_xlabel("Confirmed as of each date. Parent may be old; retained=1 after reset is not health.")
    fig.tight_layout()
    fig.savefig(out / f"{case['id']}-trajectory.png", dpi=115)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v0"], required=True)
    args = parser.parse_args()
    out = BASE / args.version
    assert not out.exists(), f"Refuse overwrite: {out}"
    protocol_path = BASE / f"protocol-{args.version}.json"
    protocol = json.loads(protocol_path.read_text())
    for path, digest in protocol["input_sha256"].items():
        assert sha(Path(path)) == digest, path
    out.mkdir()
    dump(out / "freeze.json", {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol_sha256": sha(protocol_path),
        "code_sha256": {p.name: sha(p) for p in sorted((BASE / "code").glob("*.py"))},
        "inputs": protocol["input_sha256"], "account_calls": 0,
        "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__,
    })
    frames, checks, summary = {}, [], []
    for path in protocol["input_sha256"]:
        path = Path(path)
        symbol = path.stem.removesuffix("-signals")
        raw = pd.read_csv(path, usecols=["date", "close", "volume"],
                          index_col="date", parse_dates=True)
        assert raw.index.is_unique and raw.index.is_monotonic_increasing
        c, v = raw.close, raw.volume
        f = progress_frame(c, v)
        for n in [len(c) // 2, len(c) - 17]:
            short = progress_frame(c.iloc[:n], v.iloc[:n])
            pd.testing.assert_frame_equal(f.iloc[:n], short)
            checks.append({"symbol": symbol, "prefix_rows": n, "exact": True})
        f["close"], f["volume"] = c, v
        frames[symbol] = f
        finite = f.retention.notna()
        assert np.allclose((f.retention + f.erosion)[finite], 1)
        for key in ["primary_origin_idx", "primary_extreme_idx", "parent_origin_idx",
                    "parent_extreme_idx", "primary_origin_confirmed_idx",
                    "parent_extreme_confirmed_idx"]:
            assert (f[key].dropna() <= f.valid_idx.loc[f[key].notna()]).all()
        checks.append({"symbol": symbol, "ratios_and_indices": True})
        f.to_csv(out / f"{symbol}-states.csv", index_label="date")
        summary.append({"symbol": symbol, "rows": len(f), "valid": int(f.valid.sum()),
                        "primary_flips": int(f.primary_flip.sum()),
                        "max_parent_age": f.parent_age.max()})
    c, v = frames["HK09618"].close, frames["HK09618"].volume
    base = progress_frame(c, v)
    for name, ff in [
        ("price_units", progress_frame(c * 7, v)),
        ("volume_units", progress_frame(c, v * 11)),
    ]:
        for col in ["primary_direction", "primary_event", "local_direction", "stage",
                    "volume_context", "parent_context", "parent_resolution"]:
            pd.testing.assert_series_equal(base[col], ff[col])
        checks.append({"test": name, "passed": True})
    moved = v.copy()
    positive = np.isfinite(v) & v.gt(0)
    moved.loc[positive] = v.loc[positive].iloc[::-1].to_numpy()
    ff = progress_frame(c, moved)
    for col in ["primary_direction", "primary_event", "local_direction", "parent_context"]:
        pd.testing.assert_series_equal(base[col], ff[col])
    changed = int(base.pv_state.ne(ff.pv_state).sum())
    assert changed > 0
    checks.append({"test": "positive_volume_reordered", "price_structure_changes": 0,
                   "pv_description_changes": changed})
    snapshots, intervals = [], []
    for case in protocol["cases"] + protocol["comparison_cases"]:
        f = frames[case["symbol"]]
        draw(f, case, out)
        q = f.loc[case["start"]:case["end"]]
        dates = case.get("screen_events", [case["prefix1_cutoff"]] if "prefix1_cutoff" in case else [])
        for cp in dates + [case["end"]]:
            row = f.loc[:cp].iloc[-1]
            cols = ["close", "primary_direction", "local_direction", "comparison_regime",
                    "primary_origin_date", "primary_origin_confirmed_date", "stage",
                    "retention", "erosion", "recovery", "parent_direction",
                    "parent_origin_date", "parent_extreme_date", "parent_retention",
                    "parent_age", "erosion_relative", "recovery_relative", "volume_context", "q"]
            snapshots.append(dict(case=case["id"], symbol=case["symbol"], requested_date=cp,
                                  actual_date=str(row.name.date()), **row[cols].to_dict()))
        changes = q[q.primary_event.ne(0)]
        changes.to_csv(out / f"{case['id']}-events.csv", index_label="date")
        intervals.append({"case": case["id"], "symbol": case["symbol"],
                          "rows": len(q), "primary_events": len(changes),
                          "up_rows": int(q.primary_direction.eq(1).sum()),
                          "down_rows": int(q.primary_direction.eq(-1).sum()),
                          "local_events": int(q.local_event.ne(0).sum()),
                          "max_parent_age": q.parent_age.max()})
    pd.DataFrame(snapshots).to_csv(out / "checkpoint-states.csv", index=False)
    dump(out / "window-summary.json", intervals)
    dump(out / "summary.json", summary)
    dump(out / "validation.json", checks)
    for path, digest in protocol["input_sha256"].items():
        assert sha(Path(path)) == digest
    dump(out / "manifest.json", {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps({"series": len(frames), "charts": 18, "checks": len(checks),
                      "volume_description_changes": changed, "account_calls": 0}))


if __name__ == "__main__":
    main()

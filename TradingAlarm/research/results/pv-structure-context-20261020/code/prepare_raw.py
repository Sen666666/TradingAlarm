"""Freeze and render the 15 fixed cases as raw close/volume prefixes.

This script imports no model, order, portfolio, or account implementation.
Saved signal files are read using only the date, close, and volume columns.
An existing raw directory is never reused or overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def raw_input(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=["date", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    assert frame["date"].is_unique and frame["date"].is_monotonic_increasing
    for field in ["close", "volume"]:
        frame[field] = pd.to_numeric(frame[field], errors="raise")
    valid = (
        np.isfinite(frame["close"]) & (frame["close"] > 0)
        & np.isfinite(frame["volume"]) & (frame["volume"] > 0)
    )
    return frame.loc[valid, ["date", "close", "volume"]].copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", type=Path,
        default=Path("/Users/bytedance/Documents/ChatGPT/money/"
                     "TradingAlarm/research/results/pv-event-structure-20261020"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parents[1] / "raw"
    )
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite or reuse: {output}")

    # Only cases are interpreted from the old protocol. All other content is ignored.
    old_protocol = source / "protocol.json"
    cases = json.loads(old_protocol.read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 15 and len({c["id"] for c in cases}) == 15
    frames: dict[str, pd.DataFrame] = {}
    input_hashes: dict[str, str] = {}
    frozen_cases = []
    for case in cases:
        symbol = case["symbol"]
        input_path = source / f"{symbol}-signals.csv"
        if symbol not in frames:
            frames[symbol] = raw_input(input_path)
            input_hashes[str(input_path)] = sha256(input_path)
        frame = frames[symbol]
        start, end = pd.Timestamp(case["start"]), pd.Timestamp(case["end"])
        inside = frame.loc[(frame.date >= start) & (frame.date <= end)]
        assert not inside.empty
        if "checkpoint" in case:
            first = pd.Timestamp(case["checkpoint"])
            rule = "original fixed checkpoint; observations no later than cutoff"
        else:
            # For an even-sized interval select the earlier of its two middle rows.
            first = inside.iloc[(len(inside) - 1) // 2]["date"]
            rule = "earlier middle valid observation of the fixed interval"
        assert start <= first <= end
        frozen_cases.append({
            "id": case["id"], "symbol": symbol,
            "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
            "context_start": (start - pd.Timedelta(days=126)).strftime("%Y-%m-%d"),
            "prefix1_cutoff": first.strftime("%Y-%m-%d"),
            "prefix1_cutoff_rule": rule,
            "prefix2_cutoff": end.strftime("%Y-%m-%d"),
            "valid_observations_in_case": len(inside),
        })

    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "B: raw price-volume prefix review only",
        "history_status": "Previously seen development history; hiding future does not restore unseen status.",
        "source_protocol": str(old_protocol),
        "source_protocol_sha256": sha256(old_protocol),
        "script_sha256": sha256(Path(__file__)),
        "allowed_columns": ["date", "close", "volume"],
        "valid_observation": "finite positive close and volume; no interpolation or forward fill",
        "first_cutoff": "Original checkpoint; A3 earlier middle valid observation within case interval",
        "second_cutoff": "Original fixed end date",
        "context": "start minus 126 calendar days, truncated by available source history",
        "display": "Two axes: logarithmic closing price and raw source-unit volume. No model, future, or account.",
        "axis_limits": "Calculated independently from each visible prefix; no future-derived limits",
        "case_intent_labels": "Excluded from charts to avoid suggesting the expected answer",
        "review_order": "Record all prefix1 judgments before viewing prefix2",
        "accounts": "Forbidden in this stage; no account code imported or run",
        "input_sha256": input_hashes,
        "cases": frozen_cases,
        "environment": {
            "python": sys.version, "pandas": pd.__version__,
            "numpy": np.__version__, "matplotlib": matplotlib.__version__,
        },
    }
    # Freeze before producing or displaying any raw panel.
    save_json(output / "protocol.json", protocol)
    case_index = []
    for prefix in (1, 2):
        folder = output / f"prefix{prefix}"
        folder.mkdir()
        for case in frozen_cases:
            symbol, case_id = case["symbol"], case["id"]
            cutoff = pd.Timestamp(case[f"prefix{prefix}_cutoff"])
            lower = pd.Timestamp(case["context_start"])
            frame = frames[symbol]
            panel = frame.loc[(frame.date >= lower) & (frame.date <= cutoff)].copy()
            assert not panel.empty and panel.date.max() <= cutoff
            stem = f"{case_id}-{symbol}-through-{cutoff:%Y%m%d}"
            csv_path, png_path = folder / f"{stem}.csv", folder / f"{stem}.png"
            panel.to_csv(csv_path, index=False, date_format="%Y-%m-%d", mode="x")
            actual = panel.date.max().strftime("%Y-%m-%d")
            fig, axes = plt.subplots(
                2, 1, figsize=(11.8, 6.3), dpi=150, sharex=True,
                gridspec_kw={"height_ratios": [3, 1], "hspace": 0.10},
            )
            price_ax, volume_ax = axes
            price_ax.plot(panel.date, panel.close, color="#203B56", lw=1.5)
            price_ax.set_yscale("log")
            price_ax.yaxis.set_major_formatter(ScalarFormatter())
            price_ax.yaxis.set_minor_formatter(ScalarFormatter())
            price_ax.set_ylabel("Close (log scale)")
            # This color only encodes changes already visible in the same prefix.
            colors = np.where(panel.close.diff() >= 0, "#4A917C", "#BA7474")
            volume_ax.bar(panel.date, panel.volume, color=colors, width=1.1, alpha=.85)
            volume_ax.set_ylabel("Volume\n(source units)")
            volume_ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
            for ax in axes:
                ax.grid(axis="y", alpha=.18)
                for edge in ("top", "right"):
                    ax.spines[edge].set_visible(False)
                # Mark case start only, with no interpretation of market structure.
                ax.axvline(pd.Timestamp(case["start"]), color="#888888", ls=":", lw=.9)
            price_ax.set_title(
                f"{case_id}  {symbol} | raw prefix {prefix} | through {cutoff:%Y-%m-%d}"
                f"\nLast valid observation: {actual}", loc="left", fontsize=11
            )
            locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
            volume_ax.xaxis.set_major_locator(locator)
            volume_ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            volume_ax.set_xlim(panel.date.min(), cutoff)
            fig.text(
                .09, .02,
                "Dotted line: fixed case start. Historical development material; no model or trading outputs.",
                fontsize=8, color="#666666",
            )
            fig.subplots_adjust(left=.09, right=.97, top=.89, bottom=.105)
            fig.savefig(png_path, metadata={"Description": "Raw close-volume prefix only"})
            plt.close(fig)
            case_index.append({
                **case, "prefix": prefix, "cutoff": cutoff.strftime("%Y-%m-%d"),
                "first_visible_observation": panel.date.min().strftime("%Y-%m-%d"),
                "last_visible_observation": actual, "rows": len(panel),
                "png": str(png_path.relative_to(output)),
                "png_sha256": sha256(png_path),
                "csv": str(csv_path.relative_to(output)),
                "csv_sha256": sha256(csv_path),
            })
    assert len(case_index) == 30
    save_json(output / "case-index.json", case_index)
    save_json(output / "validation.json", {
        "panels": len(case_index),
        "all_cutoffs_respected": True,
        "input_columns": ["date", "close", "volume"],
        "account_or_model_imports": False,
        "protocol_written_before_panels": True,
        "prefix2_images_viewed_by_script": False,
        "protocol_sha256": sha256(output / "protocol.json"),
        "case_index_sha256": sha256(output / "case-index.json"),
        "source_hashes_unchanged_after_render": all(
            sha256(Path(path)) == digest for path, digest in input_hashes.items()
        ),
    })
    print(json.dumps({"output": str(output), "panels": len(case_index),
                      "first_cutoffs": {c["id"]: c["prefix1_cutoff"] for c in frozen_cases}},
                     indent=2))


if __name__ == "__main__":
    main()

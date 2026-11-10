"""Copy frozen OHLCV inputs and render complete raw case windows, once.

This prepares no model trajectories or accounts. Existing evidence is never
overwritten, including independently reviewed raw charts in the same directory.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import platform
import shutil
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from data_utils import eligible_prices, sha256


BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
SOURCE = REPO / "research_rounds/pv-boundary-response-20261020"
OLD = REPO / "TradingAlarm/research/results/pv-event-structure-20261020"
BASELINE_SHA = "b61e889e684305cbb45223e0e2dd8da324e8e8d0a2d201794e2749eb9441540e"


def write_json(path, value):
    if path.exists():
        raise FileExistsError(f"Refuse overwrite: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def draw_raw(frame, case, destination):
    """Complete case window; lagged volume reference is warmed on full history."""
    available_volume = frame.volume.where(np.isfinite(frame.volume) & frame.volume.gt(0))
    reference = available_volume.shift(1).rolling(21, min_periods=21).median()
    shown = frame.loc[case["start"]:case["end"]].copy()
    shown["lag21_volume_median"] = reference.reindex(shown.index)
    if shown.empty:
        raise ValueError(f"Empty case: {case['id']}")
    fig, axes = plt.subplots(
        2, 1, figsize=(15, 8), sharex=True,
        gridspec_kw={"height_ratios": [3.4, 1.2]},
    )
    x = np.arange(len(shown))
    price, volume = axes
    for i, row in enumerate(shown.itertuples()):
        color = "#236e8c" if row.close >= row.open else "#b45e3c"
        price.vlines(i, row.low, row.high, color=color, lw=.8)
        bottom, top = min(row.open, row.close), max(row.open, row.close)
        if top == bottom:
            price.hlines(row.close, i - .3, i + .3, color=color, lw=1.1)
        else:
            price.add_patch(Rectangle(
                (i - .29, bottom), .58, top - bottom,
                facecolor=color, edgecolor=color, alpha=.85, linewidth=.5,
            ))
    price.set_yscale("log")
    price.set_ylabel("Source-adjusted OHLC (log scale)")
    price.set_title(
        f"{case['id']} | {case['symbol']} | "
        f"{shown.index[0]:%Y-%m-%d} to {shown.index[-1]:%Y-%m-%d}\n"
        "Raw price-volume review: complete fixed window, no model overlay"
    )
    price.plot([], [], color="#236e8c", label="Close >= open")
    price.plot([], [], color="#b45e3c", label="Close < open")
    price.legend(loc="upper left", fontsize=8, ncol=2)
    price.margins(x=.01, y=.07)
    volume.bar(x, shown.volume.where(shown.volume.gt(0)), color="#8d969b", width=.7,
               label="Observed volume")
    volume.plot(x, shown.lag21_volume_median, color="#9c3f7d", lw=1.3,
                label="Median of preceding 21 price observations")
    volume.set_ylim(bottom=0)
    volume.set_ylabel("Volume\nsource units")
    volume.legend(loc="upper left", fontsize=8, ncol=2)
    ticks = np.unique(np.linspace(0, len(shown) - 1, min(11, len(shown))).astype(int))
    volume.set_xticks(ticks)
    volume.set_xticklabels(shown.index[ticks].strftime("%Y-%m-%d"), rotation=25, ha="right", fontsize=8)
    for axis in axes:
        axis.grid(alpha=.16)
    zero_ranges = shown.index[shown.high.eq(shown.low)].strftime("%Y-%m-%d").tolist()
    fig.text(
        .012, .008,
        f"Seen development history | {len(shown)} eligible price observations | "
        f"Known zero-range bars: {', '.join(zero_ranges) or 'none'} | "
        "Missing sessions not filled; volume is not signed order flow",
        fontsize=8, color="#555555",
    )
    fig.tight_layout(rect=(0, .025, 1, 1))
    if destination.exists():
        raise FileExistsError(f"Refuse overwrite: {destination}")
    fig.savefig(destination, dpi=125)
    plt.close(fig)
    return {
        "rows": len(shown),
        "first_observation": shown.index[0].strftime("%Y-%m-%d"),
        "last_observation": shown.index[-1].strftime("%Y-%m-%d"),
        "zero_range_dates": zero_ranges,
        "volume_reference": "full-history eligible price clock; volume.shift(1).rolling(21,min_periods=21).median()",
    }


def main():
    manifest_path = SOURCE / "inputs/manifest.json"
    source_manifest = json.loads(manifest_path.read_text())
    source_freeze = json.loads((SOURCE / "inputs/freeze.json").read_text())
    if sha256(manifest_path) != source_freeze["manifest_sha256"]:
        raise ValueError("Original input manifest changed")
    original_protocol = SOURCE / "protocol-v0.json"
    cases = json.loads(original_protocol.read_text())["cases"]
    if len(cases) != 18 or len(source_manifest["series"]) != 14:
        raise ValueError("Unexpected fixed coverage")
    masks = json.loads((SOURCE / "inputs/observation-mask-addendum.json").read_text())
    masks_by_symbol = {row["symbol"]: row for row in masks["series"]}
    copied_sources = {
        "source-boundary-protocol.json": original_protocol,
        "observation-mask-addendum.json": SOURCE / "inputs/observation-mask-addendum.json",
        "source-ohlcv-manifest.json": manifest_path,
        "source-input-freeze.json": SOURCE / "inputs/freeze.json",
    }
    baseline_source = OLD / "code/trend_event_structure.py"
    baseline_destination = BASE / "code/baseline_event_structure.py"
    if sha256(baseline_source) != BASELINE_SHA:
        raise ValueError("Frozen baseline changed")
    inputs, rawdir = BASE / "inputs", BASE / "raw"
    destinations = (
        [inputs / name for name in copied_sources]
        + [inputs / row["output"] for row in source_manifest["series"]]
        + [inputs / "cases.json", inputs / "manifest.json", baseline_destination, rawdir / "ohlcv-manifest.json"]
        + [rawdir / f"{case['id']}-ohlcv.png" for case in cases]
    )
    existing = [str(path) for path in destinations if path.exists()]
    if existing:
        raise FileExistsError(f"Refuse to overwrite evidence: {existing}")
    frames, records = {}, []
    for row in source_manifest["series"]:
        source = SOURCE / "inputs" / row["output"]
        if sha256(source) != row["output_sha256"]:
            raise ValueError(f"Changed frozen OHLCV: {source}")
        raw = pd.read_csv(source, index_col="date", parse_dates=True)
        frame = eligible_prices(raw, row["symbol"], masks_by_symbol[row["symbol"]]["exclude_price_dates"])
        if len(frame) != masks_by_symbol[row["symbol"]]["price_observed_rows"]:
            raise ValueError(f"Changed mask: {source.name}")
        frames[row["symbol"]] = frame
        records.append({
            "symbol": row["symbol"], "file": row["output"],
            "source": str(source.relative_to(REPO)), "sha256": sha256(source),
            "rows": len(raw), "price_observed_rows": len(frame),
            "first": raw.index[0].strftime("%Y-%m-%d"),
            "last": raw.index[-1].strftime("%Y-%m-%d"),
            "columns": ["date"] + list(raw.columns),
            "excluded_price_dates": masks_by_symbol[row["symbol"]]["exclude_price_dates"],
            "source_metadata": row["metadata"],
        })
    # All source checks and output collision checks precede the first copy.
    inputs.mkdir(parents=True, exist_ok=True)
    rawdir.mkdir(parents=True, exist_ok=True)
    for name, source in copied_sources.items():
        shutil.copyfile(source, inputs / name)
    for row in source_manifest["series"]:
        shutil.copyfile(SOURCE / "inputs" / row["output"], inputs / row["output"])
    shutil.copyfile(baseline_source, baseline_destination)
    if sha256(baseline_destination) != BASELINE_SHA:
        raise ValueError("Baseline copy changed bytes")
    write_json(inputs / "cases.json", cases)
    created = dt.datetime.now(dt.timezone.utc).isoformat()
    input_record = {
        "created_utc": created,
        "meaning": "Byte-identical existing OHLCV inputs for a new bounded mechanism study; no new data or accounts",
        "history": "Seen development history; copied case anchors are old review metadata, not candidate inputs",
        "repository_root_at_preparation": str(REPO),
        "series": records,
        "copied_files": {
            name: {"source": str(source.relative_to(REPO)), "sha256": sha256(source)}
            for name, source in copied_sources.items()
        },
        "cases_source": str(original_protocol.relative_to(REPO)),
        "cases_sha256": sha256(inputs / "cases.json"),
        "baseline": {
            "source": str(baseline_source.relative_to(REPO)),
            "copy": "code/baseline_event_structure.py", "sha256": BASELINE_SHA,
        },
        "code_sha256": {
            "code/prepare_inputs.py": sha256(Path(__file__)),
            "code/data_utils.py": sha256(Path(__file__).with_name("data_utils.py")),
        },
        "versions": {
            "python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, "matplotlib": matplotlib.__version__,
        },
        "account_runs": 0, "candidate_runs": 0, "network_requests": 0,
    }
    write_json(inputs / "manifest.json", input_record)
    images = []
    by_symbol = {row["symbol"]: row for row in records}
    for case in cases:
        destination = rawdir / f"{case['id']}-ohlcv.png"
        detail = draw_raw(frames[case["symbol"]], case, destination)
        images.append({
            "case": case["id"], "symbol": case["symbol"],
            "file": str(destination.relative_to(BASE)), "sha256": sha256(destination),
            "input_file": f"inputs/{case['symbol']}.csv",
            "input_sha256": by_symbol[case["symbol"]]["sha256"],
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            **detail,
        })
    write_json(rawdir / "ohlcv-manifest.json", {
        "created_utc": created, "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "input_manifest_sha256": sha256(inputs / "manifest.json"),
        "code_sha256": input_record["code_sha256"],
        "meaning": "Complete fixed OHLCV windows with a lagged volume median; no model, state, entry or account overlay",
        "case_count": len(cases), "series_count": len(records),
        "images": images, "account_runs": 0, "candidate_runs": 0,
    })
    print(json.dumps({
        "series": len(records), "images": len(images),
        "input_manifest_sha256": sha256(inputs / "manifest.json"),
        "raw_manifest_sha256": sha256(rawdir / "ohlcv-manifest.json"),
        "baseline_sha256": sha256(baseline_destination),
    }))


if __name__ == "__main__":
    main()

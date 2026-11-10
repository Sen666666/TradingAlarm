"""Offline input helpers; no account or legacy runner imports.

The price observation mask follows the independently audited boundary-study
addendum. Ordinary missing volume does not remove a valid price observation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def boolean_column(frame, name, default):
    if name not in frame:
        return pd.Series(default, index=frame.index)
    return frame[name].astype(str).str.lower().isin(["true", "1", "1.0"])


def eligible_prices(frame, symbol="", exclude_dates=()):
    """Return valid price observations without inferring volume or intraday order."""
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
    keep = (
        finite & geometry
        & boolean_column(out, "observed_bar", True)
        & ~boolean_column(out, "synthetic_event_bar", False)
        & ~boolean_column(out, "source_invalid", False)
        & ~anomaly
        & ~out.index.isin(pd.to_datetime(list(exclude_dates)))
    )
    out.loc[:, ["open", "high", "low", "close"]] = ohlc
    if "volume" not in out:
        out["volume"] = np.nan
    out["volume"] = pd.to_numeric(out.volume, errors="coerce")
    return out.loc[keep].copy()


def source_directory(round_root=None):
    base = Path(round_root) if round_root is not None else Path(__file__).resolve().parents[1]
    return base / "prepared/source-precision-v1"


def load_source(symbol, round_root=None, cutoff=None):
    """Frozen prepared full source, or independently rebuild an original prefix."""
    base = Path(round_root) if round_root is not None else Path(__file__).resolve().parents[1]
    directory = source_directory(base)
    manifest = json.loads((directory / "manifest.json").read_text())
    record = next(r for r in manifest["series"] if r["symbol"] == symbol)
    if sha256(base / "inputs" / record["file"]) != record["source_sha256"]:
        raise ValueError("Original source bytes changed")
    if sha256(base / "code/prepare_input.py") != manifest["code_sha256"]:
        raise ValueError("Prepared-source implementation changed")
    if cutoff is not None:
        from prepare_input import prepare_frame
        raw = pd.read_csv(base / "inputs" / record["file"], dtype=str,
                          keep_default_na=False, index_col="date")
        raw.index = pd.to_datetime(raw.index)
        return prepare_frame(raw.loc[:cutoff], symbol)
    path = directory / record["file"]
    if sha256(path) != record["sha256"]:
        raise ValueError("Prepared source changed")
    return pd.read_csv(path, index_col="date", parse_dates=True, float_precision="round_trip")


def load_inputs(round_root=None):
    """Return (eligible_frames_by_symbol, cases_list, manifest), verifying copies."""
    base = Path(round_root) if round_root is not None else Path(__file__).resolve().parents[1]
    directory = source_directory(base)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(base / "inputs/manifest.json") != manifest["source_manifest_sha256"]:
        raise ValueError("Original manifest changed")
    addendum_path = directory / "observation-mask-addendum.json"
    if sha256(addendum_path) != manifest["copied_files"]["observation-mask-addendum.json"]["sha256"]:
        raise ValueError("Observation-mask evidence changed")
    addendum = json.loads(addendum_path.read_text())
    masks = {row["symbol"]: row for row in addendum["series"]}
    cases_path = directory / "cases.json"
    if sha256(cases_path) != manifest["cases_sha256"]:
        raise ValueError("Fixed cases changed")
    cases = json.loads(cases_path.read_text())
    frames = {}
    for record in manifest["series"]:
        path = directory / record["file"]
        if sha256(path) != record["sha256"]:
            raise ValueError(f"Frozen input changed: {path.name}")
        raw = load_source(record["symbol"], base)
        frame = eligible_prices(raw, record["symbol"], masks[record["symbol"]]["exclude_price_dates"])
        if len(frame) != record["price_observed_rows"]:
            raise ValueError(f"Observation clock changed: {path.name}")
        frames[record["symbol"]] = frame
    return frames, cases, manifest

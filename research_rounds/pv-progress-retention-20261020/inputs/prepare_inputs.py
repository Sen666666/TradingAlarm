"""Offline bounded extraction of existing price/volume; no market or account imports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import numpy as np
import pandas as pd


SOURCE = Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data")
DEST = Path(__file__).resolve().parent
BATCH = SOURCE / "ths-index-history-9603-20261018"
INDEX_SYMBOLS = ["URFI881129", "UZZI000994"]
ETF_SYMBOLS = []  # Gold 518880 remains in the parent's existing 27-series inputs.


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, obj):
    with path.open("x") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def stats(frame):
    valid = (
        np.isfinite(frame.close) & (frame.close > 0)
        & np.isfinite(frame.volume) & (frame.volume > 0)
    )
    dates = pd.to_datetime(frame.date, errors="raise")
    assert dates.is_unique and dates.is_monotonic_increasing
    ohlc_bad = None
    if {"open", "high", "low"}.issubset(frame.columns):
        ohlc_bad = int((
            (frame.low > frame[["open", "close", "high"]].min(axis=1))
            | (frame.high < frame[["open", "close", "low"]].max(axis=1))
        ).sum())
    good = frame.loc[valid, ["date", "close", "volume"]].copy()
    return good, {
        "original_rows": len(frame), "valid_price_volume_rows": len(good),
        "original_first": frame.date.iloc[0], "original_last": frame.date.iloc[-1],
        "first_valid": good.date.iloc[0], "last_valid": good.date.iloc[-1],
        "dropped_invalid_price_volume_dates": frame.loc[~valid, "date"].tolist(),
        "duplicate_dates": 0, "ordered_dates": True,
        "ohlc_inconsistent_rows_not_used_by_close_volume_model": ohlc_bad,
    }


def extract(frame, symbol, metadata):
    good, quality = stats(frame)
    saved = frame[["date", "close", "volume"]].copy()
    saved.insert(0, "symbol", symbol)
    path = DEST / f"{symbol}.csv"
    saved.to_csv(path, index=False, mode="x")
    metadata.update({
        "symbol": symbol, "quality": quality,
        "output": path.name, "output_sha256": digest(path),
        "columns": ["symbol", "date", "close", "volume"],
        "transformation": "Select columns only; preserve every original row and missing value, with no rescaling, filling, or price adjustment.",
        "comparison_window": ["2025-10-01", "2026-09-30"],
        "history_for_warmup": "Complete saved history retained, not restricted to comparison window.",
        "history": "Already available historical development material; no unseen or prospective claim.",
        "volume_unit": (
            "Original source units, unchanged decoded THS field 13. "
            "Per-instrument units and historical constituent aggregation are not independently verified."
        ),
    })
    write_json(DEST / f"{symbol}.source.json", metadata)
    return metadata


def main():
    expected = [DEST / f"{s}.{ext}" for s in INDEX_SYMBOLS + ETF_SYMBOLS
                for ext in ("csv", "source.json")]
    if any(p.exists() for p in expected) or (DEST / "manifest.json").exists():
        raise FileExistsError("Extraction outputs already exist; refusing to overwrite")
    names_file = BATCH / "server-names.json"
    raw_names = json.loads(names_file.read_text())
    names = {}
    for group in raw_names.values():
        for entry in (group if isinstance(group, list) else [group]):
            names.update(entry["names"])
    protocol_file = BATCH / "protocol.json"
    protocol = json.loads(protocol_file.read_text())
    symbol_protocol = {x["symbol"]: x for x in protocol["symbols"]}
    outputs = []
    for symbol in INDEX_SYMBOLS:
        source = BATCH / "canonical" / f"{symbol}.csv"
        cp_path = BATCH / "checkpoints" / f"{symbol}.json"
        cp = json.loads(cp_path.read_text())
        assert cp["symbol"] == symbol and cp["status"] == "complete"
        assert digest(source) == cp["canonical_sha256"]
        page_checks = []
        for page in cp["pages"]:
            query = page["query"]
            assert query["market"] + query["code"] == symbol
            assert {"11", "13"}.issubset(query["datatype"].split(","))
            raw = BATCH / page["file"]
            assert digest(raw) == page["body_sha256"]
            page_checks.append({
                "file": str(raw), "sha256": digest(raw),
                "market": query["market"], "code": query["code"],
                "period": query["period"],
            })
        comparison = (
            "Communication-theme proxy only: screenshot 03 has no ETF identifier. "
            "An industry/index series is not that ETF."
            if symbol in INDEX_SYMBOLS[:3] else
            "Additional existing sector comparison; no corresponding security or semiconductor chart appears in the supplied screenshots."
        )
        metadata = {
            "name": names[symbol], "instrument": "price index, not directly tradable",
            "screenshot_match": "proxy_only" if symbol in INDEX_SYMBOLS[:3] else "not_present",
            "comparison_boundary": comparison,
            "close_unit": "provider index points; no fuquan requested",
            "source": str(source), "source_sha256": digest(source),
            "checkpoint": str(cp_path), "checkpoint_sha256": digest(cp_path),
            "server_names": str(names_file), "server_names_sha256": digest(names_file),
            "protocol": str(protocol_file), "protocol_sha256": digest(protocol_file),
            "canonical_hash_verified": True, "raw_page_hashes_verified": True,
            "original_wire_code_verified": True, "page_checks": page_checks,
            "publication_metadata_unverified": symbol_protocol[symbol]["publication"],
            "no_current_constituents_backfilled": True,
            "overlap_conflicts": cp.get("overlap_conflicts"),
        }
        outputs.append(extract(pd.read_csv(source), symbol, metadata))
    for symbol in ETF_SYMBOLS:
        source = SOURCE / f"{symbol}.json"
        saved = json.loads(source.read_text())
        assert saved["symbol"] == symbol
        bars_hash = hashlib.sha256(
            json.dumps(saved["bars"], sort_keys=True).encode()
        ).hexdigest()
        assert bars_hash == saved["bars_sha256"]
        code_checks = []
        for page in saved["pages"]:
            query = page["query"]
            assert query["market"] + query["code"] == symbol
            code_checks.append({
                "market": query["market"], "code": query["code"],
                "fuquan": query.get("fuquan"), "first": page["first"], "last": page["last"],
            })
        metadata = {
            "name": "半导体ETF（既有研究标的）" if symbol.endswith("512480") else "黄金ETF（既有研究标的）",
            "instrument": "ETF, saved THS Q price series",
            "screenshot_match": "not_present" if symbol.endswith("512480") else "proxy_only",
            "comparison_boundary": (
                "No semiconductor chart in supplied screenshots; existing ETF comparison."
                if symbol.endswith("512480") else
                "Screenshot 04 is gold commodity futures with no contract identifier. "
                "518880 is a different instrument and cannot replicate its marked returns or dates."
            ),
            "close_unit": "Q-adjusted ETF price units; Q semantics not independently verified",
            "source": str(source), "source_sha256": digest(source),
            "source_declared": saved["source"], "adjustment": saved["adjustment"],
            "fetched_at": saved["fetched_at"], "bars_sha256": bars_hash,
            "bars_hash_verified": True, "original_wire_code_verified": True,
            "page_code_checks": code_checks,
            "overlap_conflicts": saved["overlap_conflicts"],
            "raw_wire_payload_hashes": "Not available in this source JSON; no claim of raw-page verification.",
        }
        outputs.append(extract(pd.DataFrame(saved["bars"]), symbol, metadata))
    write_json(DEST / "manifest.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Offline extraction only; no signal or account computation",
        "script_sha256": digest(Path(__file__)),
        "screenshot_identity": {
            "03": "科技股 - 通信ETF; no code/adjustment identified; 2025-12-09 to 2026-07-02 marked interval",
            "04": "金融资产 > 商品期货 > 黄金; no contract/index identifier",
            "05": "全国房产 > 上海; not Shanghai equity index",
            "confirmed_same_security": [],
        },
        "series": outputs,
        "limits": [
            "None of these extracted series is verified as the exact security in a screenshot.",
            "Historical industry membership and publication availability are not independently verified.",
            "Index aggregate volume can change with composition; no current membership is backfilled.",
            "No new data download, no network, no account evaluation.",
            "The two communication proxies were specified by role, not selected to fit screenshot prices or marked returns.",
        ],
    })
    print(json.dumps([{
        "symbol": m["symbol"], "name": m["name"], **m["quality"]
    } for m in outputs], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

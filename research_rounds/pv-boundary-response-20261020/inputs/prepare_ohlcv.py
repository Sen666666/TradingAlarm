"""Bounded offline OHLCV preparation; imports no model, order, or account module."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import hashlib
import json
import re

import numpy as np
import pandas as pd

OHLC = ["open", "high", "low", "close"]
ETF = ["USHJ518880", "USHJ512480", "USHJ510300"]
HK = ["HK00002", "HK09618", "HK00700", "HK03033", "HK00101", "HK03690"]
ASHARE = ["600919.SH", "600059.SH", "600917.SH"]
INDICES = ["URFI881129", "UZZI000994"]
IN_KIND = {"2022-01-20": ("09618", 21), "2023-01-05": ("03690", 10)}
SPLIT_DATES = {
    ("512480", "2021-03-26"): "2021-03-29",
    ("512480", "2026-07-02"): "2026-07-03",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, obj):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def frame(rows):
    f = pd.DataFrame(rows)
    f["date"] = pd.to_datetime(f["date"])
    f = f.set_index("date")
    if not f.index.is_unique or not f.index.is_monotonic_increasing:
        raise ValueError("source date order/uniqueness failure")
    return f


def tencent_rows(rows):
    return frame([dict(
        date=r[0], open=float(r[1]), close=float(r[2]),
        high=float(r[3]), low=float(r[4]), volume=float(r[5]),
    ) for r in rows])


def parse_cash(text):
    """Exact cash/alternative distinction from the existing pure annotation parser."""
    number = r"(?:0|[1-9]\d*)(?:\.\d+)?"
    label = r"(?:每股)?(?:第[一二三四](?:期|次|季度))?(?:中期股息|中期息|末期股息|末期息|特别股息|特别息|股息|息)(?:每股)?"
    currencies = {"港元": "HKD", "美元": "USD", "英镑": "GBP"}
    parts = []
    for token in text.replace("；", ";").split(";"):
        if not token:
            continue
        m = re.fullmatch(label + "(" + number + r")(港元|美元)", token)
        if m:
            parts.append({"amount": float(Decimal(m[1])), "currency": currencies[m[2]], "alternatives": set()})
            continue
        m = re.fullmatch(r"相当于(" + number + r")(港元|美元|英镑)", token)
        if m and parts:
            currency = currencies[m[2]]
            if currency == parts[-1]["currency"] or currency in parts[-1]["alternatives"]:
                raise ValueError("duplicate currency alternative")
            parts[-1]["alternatives"].add(currency)
            continue
        m = re.fullmatch(r"每股美国存托股(" + number + r")(港元|美元)", token)
        if m and parts:
            continue
        raise ValueError("unsupported cash annotation: " + token)
    if not parts:
        raise ValueError("empty cash annotation")
    return [{"amount": p["amount"], "currency": p["currency"]} for p in parts]


def total_return_ohlcv(raw, dividends, splits):
    """Reconstruct the old data-layer formula independently of old signal closes."""
    div = pd.Series(0.0, index=raw.index)
    split = pd.Series(1.0, index=raw.index)
    for event in dividends:
        date = pd.Timestamp(event["ex_date"])
        if date in div.index:
            div.loc[date] += event["amount"]
    for event in splits:
        date = pd.Timestamp(event["date"])
        if date in split.index:
            split.loc[date] *= event["ratio"]
    if ((split != 1) & (div != 0)).any():
        raise ValueError("same-day cash and split need an explicit convention")
    gross = (raw.close * split + div) / raw.close.shift()
    total = raw.close.iloc[0] * gross.fillna(1).cumprod()
    factor = total / raw.close
    adjusted = raw.copy()
    for col in OHLC:
        adjusted[col] = raw[col] * factor
    # This is the existing signal-volume share-unit convention, not ample liquidity.
    adjusted["volume"] = raw.volume / split.cumprod()
    adjusted["adjustment_factor"] = factor
    adjusted["volume_factor"] = 1 / split.cumprod()
    adjusted["cash_signal_adjustment"] = div
    adjusted["split_ratio"] = split
    return adjusted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm"))
    args = parser.parse_args()
    research = args.repo.resolve() / "TradingAlarm/research"
    dest = Path(__file__).resolve().parent
    if (dest / "manifest.json").exists() or any((dest / f"{s}.csv").exists() for s in ETF + HK + ASHARE + INDICES):
        raise FileExistsError("Refusing to overwrite OHLCV evidence")
    dependencies = {}
    source_metadata = {}

    def track(path):
        path = path.resolve()
        dependencies[str(path)] = sha(path)
        return path

    def read_json(path):
        return json.loads(track(path).read_text())

    logic_files = [
        "portfolio_data.py", "run_pv_segment_round.py", "hk_cash_annotations.py",
        "hk_stock_account_pilot.py", "hk_cash_stock_campaign.py",
        "hk_foreign_stock_campaign.py", "hk_in_kind_campaign.py",
        "campaign_engine.py", "ths_signal_adjustment.py",
    ]
    # These files are hashed as the reviewed formula provenance, never imported.
    for name in logic_files:
        track(research / name)
    case_source = research / "results/pv-event-structure-20261020/protocol.json"
    cases = read_json(case_source)["cases"]
    cases += [
        dict(id="COM1", symbol="URFI881129", start="2025-10-01", end="2026-09-30"),
        dict(id="COM2", symbol="UZZI000994", start="2025-10-01", end="2026-09-30"),
    ]
    prepared = {}

    for symbol in ETF:
        code = symbol[4:]
        source = research / f"data/tencent-sh{code}-raw.json"
        raw = tencent_rows(read_json(source)["data"]["sh" + code]["day"])
        event_source = track(research / f"data/eastmoney-fhsp-{code}.html")
        dividends, splits = [], []
        found_div = found_split = False
        for table in pd.read_html(event_source):
            if "除息日" in table:
                found_div = True
                for _, row in table.iterrows():
                    if "暂无" in str(row["除息日"]):
                        continue
                    match = re.fullmatch(r"每10份派现金([0-9.]+)元", str(row["每10份分红"]))
                    if not match:
                        raise ValueError("unknown ETF dividend convention")
                    ex = pd.Timestamp(row["除息日"])
                    if ex < raw.index[0] or ex > raw.index[-1]:
                        continue
                    if ex not in raw.index:
                        raise ValueError("ETF event date lacks a raw bar")
                    dividends.append(dict(ex_date=str(ex.date()), amount=float(match[1]) / 10))
            if "拆分折算日" in table:
                found_split = True
                for _, row in table.iterrows():
                    if "暂无" in str(row["拆分折算日"]):
                        continue
                    original_date = str(row["拆分折算日"])
                    if pd.Timestamp(original_date) < raw.index[0]:
                        continue
                    date = SPLIT_DATES[(code, original_date)]
                    if pd.Timestamp(date) not in raw.index:
                        raise ValueError("ETF split date lacks a raw bar")
                    old, new = map(float, str(row["拆分折算比例"]).split(":"))
                    splits.append(dict(date=date, ratio=new / old, source_date=original_date))
        if not (found_div and found_split):
            raise ValueError("ETF cash/split source table missing")
        adjusted = total_return_ohlcv(raw, dividends, splits)
        prepared[symbol] = (raw, adjusted)
        source_metadata[symbol] = dict(
            kind="ETF", raw_source=str(source), action_source=str(event_source),
            adjustment="causal reinvested total-return price level reconstructed from raw and dated events; common positive daily factor on all four prices",
            dividends=dividends, splits=splits,
            volume_units="original Tencent source units, divided by cumulative split ratio; no conversion to share count or execution liquidity",
            unresolved="Same original action-completeness limits as prior data layer. Unknown THS Q prices are not used.",
        )

    hk_raw = {}
    hk_blobs = {}
    for symbol in HK:
        code = symbol[2:]
        if symbol == "HK03033":
            source = research / "data/tencent-hk03033.json"
            rows = read_json(source)["data"]["hk03033"]["day"]
            if any(len(row) > 6 for row in rows):
                raise ValueError("HK03033 has unmodeled action fields")
            raw = tencent_rows(rows)
            prepared[symbol] = (raw, total_return_ohlcv(raw, [], []))
            source_metadata[symbol] = dict(
                kind="HK ETF", raw_source=str(source), adjustment="no adjustments in existing data layer",
                dividends=[], splits=[], volume_units="Tencent original source units",
                unresolved="No annotations is not independent proof of no actions. Preserve existing IPO range anomaly and mark separately.",
            )
            continue
        source = research / f"data/hk-stock-raw/hk{code}.json"
        blob = read_json(source)
        hk_blobs[symbol] = blob
        hk_raw[symbol] = tencent_rows(blob["rows"]).loc["2020-01-01":]
        source_metadata[symbol] = dict(
            kind="HK stock", raw_source=str(source),
            adjustment="causal reinvested total-return price level; common positive daily OHLC factor",
            volume_units="Tencent original source units; no split in this fixed prior data treatment",
            unresolved="Vendor raw/action semantics not fully independently certified; exact reproducibility does not remove that limitation.",
        )
    fx_source = research / "data/hk-stock-pilot/usd-hkd.json"
    fx = read_json(fx_source)
    if fx["base"] != "USD":
        raise ValueError("unexpected FX base")
    rates = pd.Series({
        pd.Timestamp(day) + pd.Timedelta(days=1): rate["HKD"]
        for day, rate in fx["rates"].items()
    }).sort_index()
    for symbol, raw in hk_raw.items():
        code = symbol[2:]
        dividends = []
        for row in hk_blobs[symbol]["rows"]:
            if row[0] < "2020-01-01":
                continue
            for event in row[6:]:
                if not isinstance(event, dict):
                    continue
                if event.get("hgcgContent") or event.get("ggContent"):
                    raise ValueError("unmodeled HK share action")
                text = event.get("FHcontent", "")
                if not text or (symbol == "HK00700" and row[0] in IN_KIND):
                    continue
                ex = pd.Timestamp(event["cqr"])
                if ex != pd.Timestamp(row[0]) or pd.Timestamp(event["paixiri"]) < ex:
                    raise ValueError("invalid HK action date")
                for component in parse_cash(text):
                    amount, currency = component["amount"], component["currency"]
                    rec = dict(ex_date=str(ex.date()), source_amount=amount, source_currency=currency)
                    if currency == "USD":
                        if symbol != "HK09618":
                            raise ValueError("unexpected foreign dividend")
                        known_fx = rates.loc[:ex]
                        if known_fx.empty:
                            raise ValueError("no prior known dividend FX")
                        rate = float(known_fx.iloc[-1])
                        amount *= rate
                        rec.update(fx_rate=rate, fx_known_date=str(known_fx.index[-1].date()))
                    elif currency != "HKD":
                        raise ValueError("unsupported HK dividend currency")
                    rec["amount"] = amount
                    if ex in raw.index:
                        dividends.append(rec)
        distributions = []
        if symbol == "HK00700":
            for date, (child, denominator) in IN_KIND.items():
                history = hk_raw["HK" + child].loc[hk_raw["HK" + child].index < pd.Timestamp(date)]
                if history.empty or pd.Timestamp(date) not in raw.index:
                    raise ValueError("missing prior recipient price")
                amount = float(history.close.iloc[-1]) / denominator
                rec = dict(
                    ex_date=date, amount=amount, recipient="HK" + child,
                    denominator=denominator, reference_date=str(history.index[-1].date()),
                    reference_close=float(history.close.iloc[-1]),
                    meaning="prior recipient close adjustment for parent signal; not cash paid",
                )
                distributions.append(rec)
        adjusted = total_return_ohlcv(raw, dividends + distributions, [])
        prepared[symbol] = (raw, adjusted)
        source_metadata[symbol].update(dividends=dividends, in_kind_signal_adjustments=distributions, splits=[])
        if symbol == "HK09618":
            source_metadata[symbol]["fx_source"] = str(fx_source)

    for symbol in ASHARE:
        ths = "USHA" + symbol[:6]
        source = track(research / f"data/ths-refresh-20261018/{ths}-signal.parquet")
        raw_json = research / f"data/ths-refresh-20261018/ths-raw/{ths}.json"
        rights = track(research / f"data/ths-refresh-20261018/rights/{ths}.json")
        blob = read_json(raw_json)
        if hashlib.sha256(json.dumps(blob["bars"], sort_keys=True).encode()).hexdigest() != blob["bars_sha256"]:
            raise ValueError("A raw bars hash mismatch")
        f = pd.read_parquet(source)
        observed = frame(blob["bars"]).reindex(f.index)
        for col in OHLC + ["volume"]:
            np.testing.assert_allclose(
                f.loc[f.observed_bar, col], observed.loc[f.observed_bar, col],
                atol=1e-12, rtol=1e-12,
            )
        for col in OHLC:
            np.testing.assert_allclose(f["signal_" + col], f[col] * f.factor, atol=1e-12, rtol=1e-12)
        adjusted = f[["signal_" + col for col in OHLC]].rename(columns=lambda x: x.removeprefix("signal_"))
        adjusted["volume"] = f.volume
        adjusted["adjustment_factor"] = f.factor
        adjusted["volume_factor"] = 1.0
        adjusted["synthetic_event_bar"] = f.synthetic_event_bar
        adjusted["observed_bar"] = f.observed_bar
        prepared[symbol] = (f[OHLC + ["volume"]], adjusted)
        source_metadata[symbol] = dict(
            kind="A stock", source=str(source), raw_source=str(raw_json), rights_source=str(rights),
            adjustment="existing theoretical-ex-price causal signal factor uniformly multiplies raw OHLC; not total-return cash accounting",
            volume_units="original THS raw volume; never the A485 1e18 execution proxy",
            raw_bars_hash_verified=True, parquet_observed_raw_fields_verified=True,
            all_four_signal_prices_equal_raw_times_factor=True,
            unresolved="Rights completeness/source semantics remain bounded by prior validation.",
        )

    batch = research / "data/ths-index-history-9603-20261018"
    for symbol in INDICES:
        source = track(batch / f"canonical/{symbol}.csv")
        cp_path = batch / f"checkpoints/{symbol}.json"
        cp = read_json(cp_path)
        if sha(source) != cp["canonical_sha256"]:
            raise ValueError("index canonical hash mismatch")
        for page in cp["pages"]:
            query = page["query"]
            if query["market"] + query["code"] != symbol:
                raise ValueError("index identity mismatch")
            payload = track(batch / page["file"])
            if sha(payload) != page["body_sha256"]:
                raise ValueError("index raw page hash mismatch")
        raw = frame(pd.read_csv(source).to_dict("records"))[OHLC + ["volume"]]
        adjusted = raw.copy()
        adjusted["adjustment_factor"] = adjusted["volume_factor"] = 1.0
        prepared[symbol] = (raw, adjusted)
        source_metadata[symbol] = dict(
            kind="communication theme index proxy", raw_source=str(source), checkpoint=str(cp_path),
            adjustment="none; provider price-index points", volume_units="original THS decoded source units; independent unit/constituent-aggregation validation absent",
            original_wire_code_and_page_hashes_verified=True,
            unresolved="Not the screenshot ETF; historical publication/membership comparability unverified.",
        )

    manifests = []
    for symbol in ETF + HK + ASHARE + INDICES:
        raw, adjusted = prepared[symbol]
        result = adjusted.copy()
        for col in OHLC + ["volume"]:
            result["raw_" + col] = raw[col]
        if "synthetic_event_bar" not in result:
            result["synthetic_event_bar"] = False
            result["observed_bar"] = True
        values = result[OHLC + ["volume"]]
        finite_positive = np.isfinite(values).all(axis=1) & values.gt(0).all(axis=1)
        geometry = (
            result.low.le(result[["open", "close", "high"]].min(axis=1) + 1e-12)
            & result.high.ge(result[["open", "close", "low"]].max(axis=1) - 1e-12)
        )
        result["geometry_valid"] = finite_positive & geometry
        result["valid"] = result.geometry_valid & result.observed_bar & ~result.synthetic_event_bar
        result["zero_range"] = result.high.eq(result.low)
        result["valid_range"] = result.valid & ~result.zero_range
        result["gap_calendar_days"] = result.index.to_series().diff().dt.days
        result["gap_over_14_calendar_days"] = result.gap_calendar_days.gt(14)
        result["source_anomaly"] = ""
        if symbol == "HK03033" and pd.Timestamp("2020-08-28") in result.index:
            result.loc["2020-08-28", "source_anomaly"] = "IPO open/high range anomaly noted in prior source loader; quarantine OHLC interpretation"
            result.loc["2020-08-28", ["valid", "valid_range"]] = False
        if symbol in INDICES:
            legacy = research / f"../../research_rounds/pv-progress-retention-20261020/inputs/{symbol}.csv"
            if not legacy.exists():
                legacy = Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-progress-retention-20261020/inputs") / f"{symbol}.csv"
        else:
            legacy = research / f"results/pv-event-structure-20261020/{symbol}-signals.csv"
        old = pd.read_csv(track(legacy), usecols=["date", "close", "volume"], parse_dates=["date"]).set_index("date")
        common = result.index.intersection(old.index)
        close_match = np.isclose(result.loc[common, "close"], old.loc[common, "close"], atol=1e-10, rtol=1e-10)
        volume_match = np.isclose(result.loc[common, "volume"], old.loc[common, "volume"], atol=1e-8, rtol=1e-10)
        result["legacy_close_match"] = False
        result["legacy_volume_match"] = False
        result.loc[common, "legacy_close_match"] = close_match
        result.loc[common, "legacy_volume_match"] = volume_match
        same_dates = result.index.equals(old.index)
        exact_scope = bool(same_dates and close_match.all() and volume_match.all())
        result["can_align_legacy_state"] = exact_scope
        source_metadata[symbol].update(
            legacy_reference=str(legacy.resolve()),
            close_match_is_validation_not_construction=True,
            same_date_index=same_dates,
            common_dates=len(common),
            close_mismatch_dates=[str(d.date()) for d in common[~close_match]],
            volume_mismatch_dates=[str(d.date()) for d in common[~volume_match]],
            maximum_absolute_close_difference=float(np.abs(result.loc[common, "close"] - old.loc[common, "close"]).max()),
            legacy_alignment="verified_common_origin_reconstruction" if exact_scope else "quarantined_independent_series_do_not_mix_old_state",
        )
        path = dest / f"{symbol}.csv"
        result.to_csv(path, index_label="date", mode="x")
        record = dict(
            symbol=symbol, output=path.name, output_sha256=sha(path),
            rows=len(result), first=str(result.index[0].date()), last=str(result.index[-1].date()),
            valid_rows=int(result.valid.sum()), valid_range_rows=int(result.valid_range.sum()),
            invalid_dates=[str(d.date()) for d in result.index[~result.valid]],
            zero_range_dates=[str(d.date()) for d in result.index[result.zero_range]],
            synthetic_event_dates=[str(d.date()) for d in result.index[result.synthetic_event_bar]],
            gaps_over_14_days=[
                dict(date=str(d.date()), days=int(result.loc[d, "gap_calendar_days"]))
                for d in result.index[result.gap_over_14_calendar_days]
            ],
            metadata=source_metadata[symbol],
        )
        record["cases"] = []
        for case in cases:
            if case["symbol"] != symbol:
                continue
            part = result.loc[case["start"]:case["end"]]
            record["cases"].append(dict(
                case_id=case["id"], start=case["start"], end=case["end"],
                rows=len(part), valid_rows=int(part.valid.sum()),
                valid_range_rows=int(part.valid_range.sum()),
                zero_range_dates=[str(d.date()) for d in part.index[part.zero_range]],
                invalid_dates=[str(d.date()) for d in part.index[~part.valid]],
            ))
        save_json(dest / f"{symbol}.source.json", record)
        manifests.append(record)
    # Full historical union comparison only flags absent rows; it never fills them.
    for r in manifests:
        r["metadata"]["price_ratio_provenance"] = (
            "Each daily adjustment_factor is explicitly saved in CSV; it was obtained "
            "from dated corporate actions or the validated A-share factor, never inferred from legacy signal close."
        )
    manifest = dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        purpose="14 saved OHLCV series for 15 fixed cases plus 2 communication proxy cases; no model/account computation",
        script_sha256=sha(Path(__file__)), dependencies=dependencies,
        code_provenance="Only numpy/pandas/stdlib imported. Existing formula source files were read and hashed, never imported as account runners.",
        source_definitions=source_metadata,
        zero_range_policy="Keep true same-price bars; valid_range=false and range-dependent close location undefined. Do not replace with fabricated range.",
        invalid_policy="Keep invalid/synthetic/anomalous records and flags; exclude from observation calculations via valid. No forward filling missing sessions.",
        snapshot_comparability="All history is seen development data; no same-security claim for the two communication proxies.",
        cases=cases, series=manifests,
    )
    save_json(dest / "manifest.json", manifest)
    save_json(dest / "freeze.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha(dest / "manifest.json"),
        "script_sha256": sha(Path(__file__)),
        "all_legacy_close_volume_full_index_match": all(
            r["metadata"]["legacy_alignment"] == "verified_common_origin_reconstruction" for r in manifests
        ),
    })
    print(json.dumps([{
        "symbol": r["symbol"], "rows": r["rows"], "valid": r["valid_rows"],
        "alignment": r["metadata"]["legacy_alignment"],
        "close_mismatches": len(r["metadata"]["close_mismatch_dates"]),
        "volume_mismatches": len(r["metadata"]["volume_mismatch_dates"]),
        "case_rows": r["cases"],
    } for r in manifests], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

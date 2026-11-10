"""Offline, evidence-limited identity/unit adapter. No prices, dates, or trades created.

Only the three reviewed SZSE code transitions are admitted. This is technical
data normalization, never economic eligibility or a corporate-action model.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd


PAIRS = {"000022.SZ": ("001872.SZ", "2018-12-26"),
         "000043.SZ": ("001914.SZ", "2019-12-16"),
         "300114.SZ": ("302132.SZ", "2025-02-17")}
PRICES = ("open", "high", "low", "close")
UNKNOWN = ("historical_company_cap", "historical_industry_membership",
           "southbound_eligibility", "corporate_actions_and_adjustment",
           "historical_announcement_timestamp", "execution_and_settlement")


class EvidenceError(ValueError):
    pass


class ConflictError(EvidenceError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def decimal_value(value):
    if value is None or str(value).strip() in ("", "nan", "None", "<NA>"):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise EvidenceError("non-numeric source field") from exc
    if not result.is_finite():
        raise EvidenceError("non-finite source field")
    return result


def resolve_identity(source_symbol: str, day: str):
    """Label actual bars with dated symbols; do not infer listing or eligibility."""
    date.fromisoformat(day)
    for old, (new, effective) in PAIRS.items():
        if source_symbol in (old, new):
            return {"security_id": "SZSE_A_CONTINUITY_" + old.split(".")[0],
                    "symbol": old if day < effective else new,
                    "old_symbol": old, "new_symbol": new,
                    "code_change_effective_date": effective}
    raise EvidenceError("unreviewed security: " + source_symbol)


def normalize(raw: dict, source: dict):
    """Unit rules are restricted to the reviewed provider and three lineages."""
    symbol = raw["source_symbol"]
    day = raw["trade_date"]
    identity = resolve_identity(symbol, day)
    provider = source["provider"]
    if provider == "tushare_local_raw":
        if symbol != identity["new_symbol"] or raw.get("provider") != "tushare":
            raise EvidenceError("unverified provider/symbol combination")
        multiplier, unit = Decimal(100), "hands_100_shares"
    elif provider == "baostock_raw_adjustflag3":
        if symbol not in ("000022.SZ", "000043.SZ") or str(raw.get("adjustflag")) != "3":
            raise EvidenceError("unverified BaoStock history or adjustment flag")
        multiplier, unit = Decimal(1), "shares"
    else:
        raise EvidenceError("unverified source volume unit")
    prices = {key: decimal_value(raw.get(key)) for key in PRICES}
    volume = decimal_value(raw.get("volume"))
    if volume is not None and volume < 0:
        raise EvidenceError("negative source volume")
    volume_shares = None if volume is None else volume * multiplier
    status = str(raw.get("tradestatus", "unknown"))
    # Old-code terminal sentinels are not suspension observations of the new line.
    sentinel = (provider == "baostock_raw_adjustflag3"
                and day >= identity["code_change_effective_date"]
                and all(value is None for value in prices.values())
                and volume is None and status == "0")
    positive_prices = all(value is not None and value > 0 for value in prices.values())
    if positive_prices and not (prices["low"] <= min(prices["open"], prices["close"])
                                <= max(prices["open"], prices["close"]) <= prices["high"]):
        raise EvidenceError("inconsistent OHLC bounds")
    trend_observation = (positive_prices and volume_shares is not None
                         and volume_shares > 0 and status != "0" and not sentinel)
    return {**identity, "trade_date": day, **prices, "volume_shares": volume_shares,
            "source_symbol": symbol, "source_provider": provider,
            "source_path": source["path"], "source_sha256": source["sha256"],
            "source_volume_unit": unit, "source_volume_multiplier": str(multiplier),
            "source_trade_status": status, "terminal_symbol_sentinel": sentinel,
            "is_valid_trend_observation": bool(trend_observation),
            "economic_eligibility": False, "trade_execution_eligibility": "unknown",
            "corporate_action_adjustment_applied": False}


def coalesce(records: list[dict]):
    """Deduplicate across sources and fail closed on conflicting prices/volume."""
    groups = defaultdict(list)
    sentinels = []
    seen_source_keys = set()
    for record in records:
        source_key = (record["source_sha256"], record["source_symbol"], record["trade_date"])
        if source_key in seen_source_keys:
            raise ConflictError("duplicate row within one source: " + str(source_key[1:]))
        seen_source_keys.add(source_key)
        if record["terminal_symbol_sentinel"]:
            sentinels.append(record)
        else:
            groups[(record["security_id"], record["trade_date"])].append(record)
    output = []
    for key, peers in sorted(groups.items()):
        for field in (*PRICES, "volume_shares"):
            values = {row[field] for row in peers if row[field] is not None}
            if len(values) > 1:
                raise ConflictError(f"conflicting {field} at {key}")
        if any(row["source_trade_status"] == "0" for row in peers) and any(
                row["volume_shares"] is not None and row["volume_shares"] > 0 for row in peers):
            raise ConflictError("positive volume conflicts with suspension at " + str(key))
        # Prefer a complete existing row; never combine fields to invent a bar.
        peers.sort(key=lambda row: (not row["is_valid_trend_observation"],
                                   row["source_provider"] != "tushare_local_raw",
                                   row["source_path"]))
        chosen = dict(peers[0])
        chosen["source_count"] = len(peers)
        chosen["provenance"] = [{field: row[field] for field in (
            "source_symbol", "source_provider", "source_path", "source_sha256",
            "source_volume_unit", "source_volume_multiplier", "source_trade_status")}
                                for row in peers]
        chosen["unknown_fields"] = list(UNKNOWN)
        output.append(chosen)
    return output, sentinels


def serializable(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serializable(v) for v in value]
    return value


def verify(records, observations, sentinels):
    checks = []

    def check(name, predicate, detail=None):
        checks.append({"name": name, "passed": bool(predicate), "detail": detail})

    def rejects(name, callback):
        try:
            callback()
        except EvidenceError as exc:
            check(name, True, type(exc).__name__)
        else:
            check(name, False)

    for old, (new, effective) in PAIRS.items():
        before = str(date.fromisoformat(effective) - timedelta(days=1))
        check(old + "_dated_symbol_before", resolve_identity(new, before)["symbol"] == old)
        check(old + "_dated_symbol_on", resolve_identity(old, effective)["symbol"] == new)
        relevant = [r for r in observations if r["old_symbol"] == old]
        check(old + "_one_continuous_identity", len({r["security_id"] for r in relevant}) == 1)
        check(old + "_effective_day_from_real_source", any(r["trade_date"] == effective for r in relevant))
    input_keys = {(r["security_id"], r["trade_date"]) for r in records if not r["terminal_symbol_sentinel"]}
    output_keys = [(r["security_id"], r["trade_date"]) for r in observations]
    check("no_created_dates_or_lost_non_sentinel_dates", set(output_keys) == input_keys)
    check("one_row_per_security_day", len(output_keys) == len(set(output_keys)))
    check("dedup_real_overlap", sum(r["source_count"] - 1 for r in observations) == 4217)
    check("two_old_code_terminal_sentinels_excluded", len(sentinels) == 2)
    for day in ("2018-12-21", "2018-12-24", "2018-12-25"):
        row = next(r for r in observations if r["old_symbol"] == "000022.SZ" and r["trade_date"] == day)
        check("suspension_" + day, row["volume_shares"] == 0 and not row["is_valid_trend_observation"])
    check("all_zero_volume_excluded_from_trend_clock", all(not r["is_valid_trend_observation"] for r in observations if r["volume_shares"] == 0))
    check("economic_admission_always_false", all(r["economic_eligibility"] is False for r in observations))
    sample = next(r for r in records if r["is_valid_trend_observation"])
    peer = copy.deepcopy(sample); peer["source_sha256"] = "synthetic-second-source"; peer["close"] += Decimal("0.01")
    rejects("reject_price_conflict", lambda: coalesce([sample, peer]))
    peer = copy.deepcopy(sample); peer["source_sha256"] = "synthetic-second-source"; peer["volume_shares"] += 1
    rejects("reject_volume_conflict", lambda: coalesce([sample, peer]))
    rejects("reject_duplicate_in_one_source", lambda: coalesce([sample, sample]))
    rejects("reject_unreviewed_symbol", lambda: resolve_identity("000001.SZ", "2015-01-05"))
    rejects("reject_unknown_volume_unit", lambda: normalize(
        {"source_symbol": "001872.SZ", "trade_date": "2018-12-20"}, {"provider": "unknown"}))
    # A prefix must not depend on future observations for label/unit/dedup results.
    for cutoff in ("2018-12-25", "2019-12-16", "2025-02-17"):
        prefix, _ = coalesce([r for r in records if r["trade_date"] <= cutoff])
        check("prefix_" + cutoff, prefix == [r for r in observations if r["trade_date"] <= cutoff])
    return checks


def write_json(path, obj):
    with path.open("x") as stream:
        json.dump(serializable(obj), stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--source-parquet", type=Path, required=True)
    parser.add_argument("--identity-evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # Fail before any output if the target already exists; never overwrite evidence.
    if args.out.exists():
        raise FileExistsError(str(args.out))
    manifest_path = args.identity_evidence / "source-manifest.json"
    expected = {r["path"]: r["sha256"] for r in json.loads(manifest_path.read_text())["sources"]}
    transition_path = args.identity_evidence / "security-code-transitions.csv"
    transitions = list(csv.DictReader(transition_path.open()))
    if {(r["old_symbol"], r["new_symbol"], r["effective_date"]) for r in transitions} != {
            (old, new, day) for old, (new, day) in PAIRS.items()} or len(transitions) != 3:
        raise EvidenceError("transition evidence differs from reviewed scope")
    input_sources = []

    def source(path, provider):
        path = path.resolve()
        actual = sha256(path)
        if expected.get(str(path)) != actual:
            raise EvidenceError("input differs from reviewed identity: " + str(path))
        row = {"path": str(path), "provider": provider, "sha256": actual, "bytes": path.stat().st_size}
        input_sources.append(row)
        return row

    for transition in transitions:
        source(Path(transition["raw_pdf_path"]), "official_issuer_announcement")
    parquet_source = source(args.source_parquet, "tushare_local_raw")
    frame = pd.read_parquet(args.source_parquet, filters=[("symbol", "in", [v[0] for v in PAIRS.values()])],
                            columns=["symbol", "trade_date", *PRICES, "volume", "source"])
    records = []
    for row in frame.to_dict("records"):
        raw = {**row, "source_symbol": row["symbol"], "trade_date": str(row["trade_date"].date()), "provider": row["source"]}
        records.append(normalize(raw, parquet_source))
    for old in ("000022.SZ", "000043.SZ"):
        path = args.source_repo / "TradingAlarm/research/data/retired-pilot" / (old + ".json")
        source_info = source(path, "baostock_raw_adjustflag3")
        stored = json.loads(path.read_text())
        if stored["symbol"] != old or stored["source"] != "BaoStock public raw daily,adjustflag3":
            raise EvidenceError("unexpected saved old-code source")
        for row in stored["rows"]:
            records.append(normalize({**row, "source_symbol": old, "trade_date": row["date"]}, source_info))
    observations, sentinels = coalesce(records)
    checks = verify(records, observations, sentinels)
    for source_info in input_sources:
        if sha256(Path(source_info["path"])) != source_info["sha256"]:
            raise EvidenceError("source changed during read")
    args.out.mkdir(parents=True, exist_ok=False)
    verification = {"checks": checks, "passed": all(c["passed"] for c in checks),
                    "input_rows": len(records), "output_rows": len(observations),
                    "valid_trend_observations": sum(r["is_valid_trend_observation"] for r in observations),
                    "deduplicated_rows": sum(r["source_count"] - 1 for r in observations),
                    "excluded_terminal_sentinels": len(sentinels), "economic_admission": False,
                    "mechanism_changes": 0, "account_runs": 0, "network_requests": 0}
    write_json(args.out / "verification.json", verification)
    if not verification["passed"]:
        raise EvidenceError("verification failed; no normalized bars published")
    serialized = serializable(observations)
    for row in serialized:
        row["provenance"] = json.dumps(row["provenance"], ensure_ascii=False, sort_keys=True)
        row["unknown_fields"] = json.dumps(row["unknown_fields"])
    pd.DataFrame(serialized).to_parquet(args.out / "observations.parquet", index=False)
    boundary = [r for r in serialized if abs((date.fromisoformat(r["trade_date"]) - date.fromisoformat(r["code_change_effective_date"])).days) <= 7]
    pd.DataFrame(boundary).to_csv(args.out / "boundary-observations.csv", index=False)
    write_json(args.out / "terminal-symbol-sentinels.json", sentinels)
    write_json(args.out / "input-manifest.json", {"inputs": input_sources, "code_path": str(Path(__file__).resolve()),
        "code_sha256": sha256(Path(__file__)), "identity_evidence_manifest_sha256": sha256(manifest_path),
        "transition_csv_sha256": sha256(transition_path), "sources_unchanged_after_read": True})
    write_json(args.out / "protocol.json", {"purpose": "three_verified_code_transition_identity_and_volume_unit_adapter",
        "security_id_is": "internal_continuity_key_not_official_issuer_identifier", "economic_admission": False,
        "source_adjustment": "none_raw_prices_preserved", "price_conflict_policy": "reject_exact_decimal_conflicts",
        "volume_conflict_policy": "reject_after_explicit_unit_normalization", "new_dates_or_fills_created": False,
        "unknown_fields": UNKNOWN, "announcement_time": "unknown_no_historical_information_availability_claim",
        "quantity_conversion": "code_change_only_1_to_1_not_share_capital", "scope": PAIRS,
        "reproduce": [str(Path(__file__).resolve()), "--source-repo", str(args.source_repo.resolve()),
                      "--source-parquet", str(args.source_parquet.resolve()), "--identity-evidence",
                      str(args.identity_evidence.resolve()), "--out", "<new-unused-output-directory>"]})
    print(json.dumps({k: v for k, v in verification.items() if k != "checks"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

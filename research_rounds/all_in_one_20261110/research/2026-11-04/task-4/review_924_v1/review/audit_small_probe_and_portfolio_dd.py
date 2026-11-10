"""Saved drawdown and one-day sector movement; no new strategy or parameter test."""
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import sys
import time

sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
ROOT = O.parents[1]
BASE = ROOT / "new_price_trend_v1/funding/runs/long_OFF/pair"
Z, EPS = D(0), D(".000001")
SRC = {}


def bind(path):
    path = Path(path)
    SRC[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def read(path):
    return json.loads(bind(path).read_text())


def gz(path, lines=False):
    with gzip.open(bind(path), "rt") as f:
        return list(map(json.loads, f)) if lines else json.load(f)


def n(value):
    return D(str(value))


def day(value):
    return str(value)[:10]


def eq(a, b, label):
    assert abs(n(a) - n(b)) < EPS, (label, str(a), str(b))


def dd(rows, initial, initial_day):
    peak, peak_day, worst = n(initial), initial_day, Z
    result = None
    for r in rows:
        nav, date = n(r["nav"]), day(r["at"])
        if nav > peak:
            peak, peak_day = nav, date
        drawdown = (peak - nav) / peak
        if drawdown > worst:
            worst = drawdown
            result = {"peak_day": peak_day, "peak_NAV": peak, "trough_day": date,
                      "trough_NAV": nav, "wealth_change": nav - peak,
                      "max_CLOSE_drawdown_pct": drawdown * 100}
    return result


def main():
    begun = time.monotonic()
    bind(__file__)
    ds = gz(BASE / "daily.jsonl.gz", True)
    by = {day(r["at"]): r for r in ds}
    book = gz(BASE / "B.json.gz")
    y22 = [r for r in ds if day(r["at"]).startswith("2022")]
    draw22 = dd(y22, 1000000, "fresh_initial_cash_before2022_first_CLOSE")
    year22_end = n(y22[-1]["nav"])
    post = [r for r in ds if "2024-10-08" < day(r["at"]) <= "2024-12-31"]
    draw24 = dd(post, by["2024-10-08"]["nav"], "2024-10-08")
    first = by["2024-10-08"]
    next_day = by["2024-10-09"]
    assert first["positions"] == next_day["positions"]
    assert not [t for t in book["trades"] if day(t["at"]) == "2024-10-09"]
    for field in ["available", "dividend_receivable", "order_reserved", "sale_receivable"]:
        eq(first[field], next_day[field], ("Oct9 no actual cash/right change", field))
    change = n(next_day["nav"]) - n(first["nav"])
    eq(change, n(next_day["inventory"]) - n(first["inventory"]), "Oct9 stock mark-only NAV change")
    fills = [t for t in book["trades"] if t["side"] == "buy"]
    latest_old_buy = max(day(t["at"]) for t in fills if day(t["at"]) <= "2024-10-08")
    assert latest_old_buy == "2024-09-25"

    # Oct8 values are reused from the already independently checked root output.
    anchors = gz(ROOT / "review_924_v1/ANCHOR_ALL_LAYER_WEALTH.json.gz")
    stock8 = defaultdict(lambda: Z)
    for l in anchors["2024-10-08"].values():
        stock8[l["sid"]] += n(l["inventory"])
    stock8 = {sid: v for sid, v in stock8.items() if v}
    eq(sum(stock8.values(), Z), first["inventory"], "Saved Oct8 all stock inventory")
    meta = {x["sid"]: x for x in read(ROOT / "core_confirmed_v1/analysis/long_OFF_STOCKS.json")}
    spec = importlib.util.spec_from_file_location("native_924_single_day_sector_marks", bind(ROOT / "new_price_trend_v1/native_mark_reader.py"))
    MARK = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(MARK)
    sectors = {}
    details = []
    for sid, qty in first["positions"].items():
        assert time.monotonic() - begun < 60, "Single-day50-stock saved-mark addendum exceeded60sec"
        sector = meta[sid]["industry"]
        v8 = stock8[sid]
        v9 = D(qty) * MARK.price(sid, "2024-10-09")
        d = v9 - v8
        r = {"sid": sid, "name": meta[sid]["name"], "industry": sector, "actual_qty_both_CLOSEs": qty,
             "Oct8_inventory": v8, "Oct9_inventory": v9, "actual_inventory_wealth_change": d,
             "Oct8_NAV_weight_pct": v8 / n(first["nav"]) * 100}
        details.append(r)
        g = sectors.setdefault(sector, {"stocks": 0, "Oct8_inventory": Z, "Oct9_inventory": Z, "wealth_change": Z,
                                       "down_stocks": 0, "up_stocks": 0, "flat_stocks": 0})
        g["stocks"] += 1
        g["Oct8_inventory"] += v8
        g["Oct9_inventory"] += v9
        g["wealth_change"] += d
        g["down_stocks" if d < 0 else "up_stocks" if d > 0 else "flat_stocks"] += 1
    eq(sum((r["Oct9_inventory"] for r in details), Z), next_day["inventory"], "All50 original native Oct9 marks")
    eq(sum((r["actual_inventory_wealth_change"] for r in details), Z), change, "Sector/stock exact Oct9 NAV change")
    for v in sectors.values():
        v["Oct8_NAV_weight_pct"] = v["Oct8_inventory"] / n(first["nav"]) * 100
        v["share_of_actual_daily_net_decline_pct"] = v["wealth_change"] / change * 100
    coupled = [sectors[s] for s in ["保险", "证券"]]
    together = {"stocks": sum(x["stocks"] for x in coupled),
                "Oct8_inventory": sum((x["Oct8_inventory"] for x in coupled), Z),
                "Oct9_wealth_change": sum((x["wealth_change"] for x in coupled), Z),
                "down_stocks": sum(x["down_stocks"] for x in coupled)}
    together["Oct8_NAV_weight_pct"] = together["Oct8_inventory"] / n(first["nav"]) * 100
    together["share_of_actual_daily_net_decline_pct"] = together["Oct9_wealth_change"] / change * 100
    earlier = read(O / "INDEPENDENT_COHORT_BREAKDOWN.json")
    new = [r for r in read(O / "INDEPENDENT_LAYER_WEALTH_postpeak.json") if r["cohort"].startswith("postpeak_")]
    positive = sum((n(r["wealth_change"]) for r in new if n(r["wealth_change"]) > 0), Z)
    negative = sum((n(r["wealth_change"]) for r in new if n(r["wealth_change"]) < 0), Z)
    eq(positive + negative, D("-112457.6005694286215"), "303 actual layer net")
    SRC.update(MARK.sources)
    out = {"passed": True, "2022": {"year_end_NAV": year22_end, "year_return_pct": (year22_end / D(1000000) - 1) * 100, "max_CLOSE_DD": draw22},
           "2024_post_Oct8_max_CLOSE_DD": draw24,
           "Oct9": {"begin_NAV": first["nav"], "end_NAV": next_day["nav"], "NAV_change": change,
                      "return_pct": change / n(first["nav"]) * 100, "actual_trade_count": 0,
                      "old_inventory_latest_buy_day": latest_old_buy, "all_old_inventory_past_T_plus_1": True,
                      "sectors": sectors, "insurance_and_securities": together},
           "303_new_layers": {"positive_layers": sum(n(r["wealth_change"]) > 0 for r in new),
                              "negative_layers": sum(n(r["wealth_change"]) < 0 for r in new),
                              "positive_sum": positive, "negative_sum": negative, "net": positive + negative},
           "interpretation": [
               "Original CORE0.25% is one entry's known-price fee-inclusive protection sizing budget, not a guarantee on maximum whole-account loss; originalMobile2% is nominal buy capital, not maximum loss.",
               "Multiple entries and reentries can accumulate actual gross losses; simultaneous risky stock holdings can move down together. No statutory/single-trade cap is promoted to a portfolio drawdown guarantee.",
               "Observed sector concentration and same-day co-movement are actual inventory attribution. No statistical correlation coefficient or future filter is estimated.",
               "Oct9 original stock inventory was already pastT+1. The original CLOSE decision-to-nextOPEN clock, not T+1 alone, explains the recorded pending-exit timing; no hypothetical known-peak sale is assumed.",
               "Known-price protection risk does not guarantee realized losses under gaps, delayed fills or original execution rules. Code conditions belong the separate source-rule audit."
           ],
           "native_mark_evaluations": len(MARK.mark_cache), "native_mark_securities": len(MARK.views),
           "new_accounts": 0, "new_Market": 0, "new_routes": 0, "parameter_tests": 0,
           "seconds": time.monotonic() - begun, "source_sha256": SRC}
    (O / "SMALL_PROBE_VS_PORTFOLIO_DD_REVIEW.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + "\n")
    (O / "OCT9_ALL50_ACTUAL_INVENTORY_CHANGES.json").write_text(json.dumps(details, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps({"passed": True, "2022_DD": str(draw22["max_CLOSE_drawdown_pct"]),
                      "2024_post_DD": str(draw24["max_CLOSE_drawdown_pct"]), "Oct9_return_pct": str(out["Oct9"]["return_pct"]),
                      "insurance_securities": together, "seconds": out["seconds"]}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

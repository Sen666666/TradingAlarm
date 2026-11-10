"""Independent saved-ledger audit only; no Account, Market or strategy import."""
from collections import defaultdict, Counter
from decimal import Decimal as D
from pathlib import Path
import gzip
import hashlib
import json
import time

O = Path(__file__).resolve().parent
ROOT = O.parents[1]
BASE = ROOT / "new_price_trend_v1/funding/runs/long_OFF/pair"
Z = D(0)
EPS = D(".000001")
SOURCES = {}


def bind(path):
    path = Path(path)
    SOURCES[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def read(path):
    return json.loads(bind(path).read_text())


def gz(path, lines=False):
    with gzip.open(bind(path), "rt") as stream:
        return list(map(json.loads, stream)) if lines else json.load(stream)


def save(name, value):
    (O / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def number(value):
    return D(str(value))


def day(value):
    return str(value)[:10]


def equal(left, right, label):
    assert abs(left - right) < EPS, (label, str(left), str(right))


def main():
    begun = time.monotonic()
    bind(__file__)
    manifest = read(ROOT / "new_price_trend_v1/funding/FULL_OUTPUT_SHA256.json")
    book = gz(BASE / "B.json.gz")
    daily = gz(BASE / "daily.jsonl.gz", True)
    certs = gz(BASE / "balances.jsonl.gz", True)
    funding = gz(BASE / "funding.jsonl.gz", True)
    for path, digest in list(SOURCES.items()):
        if "/pair/" in path:
            assert manifest[path] == digest, ("Original output changed", path)
    assert len(daily) == len(certs) == 726

    trades = defaultdict(list)
    dividends = defaultdict(list)
    for row in book["trades"]:
        trades[day(row["at"])].append(row)
    for row in book["audit"]:
        if row["kind"] == "dividend_accrual":
            r = row["receivable"]
            dividends[day(r["ex_at"])].append(r)
    by_day = {day(r["at"]): r for r in daily}
    net_trade_cash = Z
    recognized_dividend = Z
    checks = []
    for row, certificate in zip(daily, certs):
        date = day(row["at"])
        assert day(certificate["at"]) == date
        net_trade_cash += sum(((-number(t["gross_cny"]) - number(t["fees_cny"]))
                               if t["side"] == "buy" else
                               (number(t["gross_cny"]) - number(t["fees_cny"]))
                              for t in trades[date]), Z)
        recognized_dividend += sum((number(d["net_local"]) for d in dividends[date]), Z)
        rebuilt_nav = D(1000000) + net_trade_cash + recognized_dividend + number(row["inventory"])
        equal(rebuilt_nav, number(row["nav"]), ("Saved cashflow+saved inventory", date))
        components = sum((number(row.get(k, 0)) for k in
                          ["available", "order_reserved", "settlement_locked", "sale_receivable",
                           "inventory", "dividend_receivable"]), Z) - number(row.get("payable", 0))
        equal(components, number(row["nav"]), ("Saved actual balance components", date))
        for key in ["independent_NAV_difference", "budget_NAV_difference", "spendable_difference",
                    "reserved_difference", "capital_occupancy_difference", "maximum_stock_quantity_difference"]:
            equal(number(certificate[key]), Z, ("Native saved certificate", date, key))
        for value in certificate["pool_occupancy_difference"].values():
            equal(number(value), Z, ("Pool certificate", date))
        if date.startswith("2024"):
            checks.append({"day": date, "NAV": row["nav"], "cashflow_NAV": rebuilt_nav,
                           "saved_components_NAV": components, "certificate_passed": True})

    anchors = {}
    for date in ["2023-12-29", "2024-09-23", "2024-10-08", "2024-12-31"]:
        r = by_day[date]
        anchors[date] = {k: r.get(k, 0) for k in ["nav", "available", "inventory", "order_reserved",
                        "sale_receivable", "dividend_receivable", "settlement_locked", "payable", "on"]}
        anchors[date].update(held_stocks=len(r["positions"]),
                            inventory_NAV_pct=number(r["inventory"]) / number(r["nav"]) * 100,
                            pending_exit_stocks=len(r["pending_sells"]))

    phases = {}
    for name, start, end in [("year", "2023-12-29", "2024-12-31"),
                             ("pre924", "2023-12-29", "2024-09-23"),
                             ("rally", "2024-09-23", "2024-10-08"),
                             ("postpeak", "2024-10-08", "2024-12-31"),
                             ("post924_total", "2024-09-23", "2024-12-31")]:
        rows = [r for r in daily if start < day(r["at"]) <= end]
        tx = [t for r in rows for t in trades[day(r["at"])]]
        dc = sum((number(d["net_local"]) for r in rows for d in dividends[day(r["at"])]), Z)
        cash = sum(((-number(t["gross_cny"]) - number(t["fees_cny"])) if t["side"] == "buy"
                    else (number(t["gross_cny"]) - number(t["fees_cny"]))) for t in tx), Z)
        inventory_change = number(by_day[end]["inventory"]) - number(by_day[start]["inventory"])
        nav_change = number(by_day[end]["nav"]) - number(by_day[start]["nav"])
        equal(cash + dc + inventory_change, nav_change, ("Phase cash/div/mark bridge", name))
        phases[name] = {"anchor_before": start, "terminal_CLOSE": end, "actual_CLOSEs": len(rows),
                        "begin_NAV": by_day[start]["nav"], "end_NAV": by_day[end]["nav"],
                        "wealth_change": nav_change,
                        "return_pct": nav_change / number(by_day[start]["nav"]) * 100,
                        "net_trade_cash": cash, "new_recognized_dividends": dc,
                        "inventory_change": inventory_change,
                        "actual_buy_fills": sum(t["side"] == "buy" for t in tx),
                        "actual_sell_fills": sum(t["side"] == "sell" for t in tx),
                        "actual_buy_cash": sum((number(t["gross_cny"]) + number(t["fees_cny"]) for t in tx if t["side"] == "buy"), Z),
                        "actual_sell_net": sum((number(t["gross_cny"]) - number(t["fees_cny"]) for t in tx if t["side"] == "sell"), Z),
                        "actual_fees": sum((number(t["fees_cny"]) for t in tx), Z),
                        "actual_trade_days": sorted({day(t["at"]) for t in tx}),
                        "close_days": [day(r["at"]) for r in rows]}
    equal(phases["pre924"]["wealth_change"] + phases["rally"]["wealth_change"] + phases["postpeak"]["wealth_change"],
          phases["year"]["wealth_change"], "Year telescoping identity")
    assert phases["rally"]["close_days"] == ["2024-09-24", "2024-09-25", "2024-09-26", "2024-09-27", "2024-09-30", "2024-10-08"]
    assert phases["postpeak"]["actual_CLOSEs"] == 60

    first_post_sell = next(t for t in book["trades"] if t["side"] == "sell" and day(t["at"]) >= "2024-10-09")
    source_index = {"passed": True, "anchors": anchors, "phases": phases,
                    "2024_CLO​​SE_cashflow_and_balance_checks": len(checks),
                    "all_726_saved_day_certificates_passed": True,
                    "first_postpeak_sell": first_post_sell,
                    "rally_unrealized_boundary": "10/8 NAV includes723064.52 inventory and17666.9092 recognized dividend receivables; not realized sale proceeds.",
                    "valuation_boundary": "Independent cash/div/balance arithmetic using authoritative saved inventory. No new mark/price evaluation; inventory valuation relies on frozen native source and saved reconciliation certificates.",
                    "scope": "Read-only saved original No60 continuous2022-2024 account. No new Account/Runner/Market/RiskBook/strategy, no counterfactual avoided-loss claim.",
                    "seconds": time.monotonic() - begun,
                    "new_accounts": 0, "new_marks": 0, "new_routes": 0,
                    "source_sha256": SOURCES}
    save("ANCHOR_ACCOUNT_AUDIT.json", source_index)
    save("ALL2024_CASHFLOW_BALANCE_CHECKS.json", checks)
    print(json.dumps({"passed": True, "CLOSE_checks": len(checks), "seconds": source_index["seconds"]}))


if __name__ == "__main__":
    O.mkdir(parents=True, exist_ok=True)
    main()

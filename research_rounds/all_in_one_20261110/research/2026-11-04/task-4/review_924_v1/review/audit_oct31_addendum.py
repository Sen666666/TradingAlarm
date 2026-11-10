"""Natural month-end saved-ledger addendum, not a new strategy window."""
from collections import defaultdict, Counter
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
EPS, Z = D(".000001"), D(0)
SRC = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path):
    path = Path(path)
    SRC[str(path.resolve())] = sha(path)
    return path


def read(path):
    return json.loads(bind(path).read_text())


def gz(path, lines=False):
    with gzip.open(bind(path), "rt") as f:
        return list(map(json.loads, f)) if lines else json.load(f)


def save(name, value):
    (O / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def day(value):
    return str(value)[:10]


def n(value):
    return D(str(value))


def eq(a, b, label):
    assert abs(n(a) - n(b)) < EPS, (label, str(a), str(b))


def cf(t):
    return -n(t["gross_cny"]) - n(t["fees_cny"]) if t["side"] == "buy" else n(t["gross_cny"]) - n(t["fees_cny"])


def main():
    begun = time.monotonic()
    bind(__file__)
    protected = [O / f for f in ["ANCHOR_ACCOUNT_AUDIT.json", "ALL2024_CASHFLOW_BALANCE_CHECKS.json",
                 "INDEPENDENT_COHORT_BREAKDOWN.json", "ROOT_COHORT_SAVED_REVIEW.json"]]
    before_hashes = {str(p): sha(p) for p in protected}
    b = gz(BASE / "B.json.gz")
    ds = gz(BASE / "daily.jsonl.gz", True)
    by = {day(r["at"]): r for r in ds}
    r = by["2024-10-31"]
    end = by["2024-12-31"]
    layers = {l["id"]: l for l in b["layers"]}
    assert not by["2023-12-29"]["positions"] and not end["positions"]
    assert not any(a["kind"] == "split" and day(a["at"]).startswith("2024") for a in b["audit"])
    classifications = read(O / "INDEPENDENT_ACTUAL_BUY_CLASSIFICATIONS.json")
    cash = defaultdict(lambda: Z)
    for t in b["trades"]:
        if day(t["at"]) > "2024-10-31":
            continue
        if t["side"] == "buy":
            cash[t["layer"]] -= n(t["gross_cny"]) + n(t["fees_cny"])
        else:
            for p in t["parts"]:
                cash[p["layer"]] += n(p["net_cash"])
    div = defaultdict(lambda: Z, {lid: n(l["dividend"]) for lid, l in layers.items() if day(l["opened"]) < "2024-01-01"})
    div_by_day = defaultdict(lambda: Z)
    for a in b["audit"]:
        if a["kind"] != "dividend_accrual":
            continue
        rec = a["receivable"]
        date = day(rec["ex_at"])
        if not date.startswith("2024"):
            continue
        div_by_day[date] += n(rec["net_local"])
        if date > "2024-10-31":
            continue
        prev = next(x for x in reversed(ds) if day(x["at"]) < date)
        entitled = [x for x in prev["layers"] if x["sid"] == rec["security_id"] and x["qty"]]
        q = sum(x["qty"] for x in entitled)
        assert q and rec["entitlement_basis"] == "protocol_previous_close_inventory_and_explicit_net_factor"
        for l in entitled:
            div[l["id"]] += n(rec["net_local"]) * D(l["qty"]) / D(q)

    mark_path = bind(ROOT / "new_price_trend_v1/native_mark_reader.py")
    spec = importlib.util.spec_from_file_location("independent_924_oct31_native_mark", mark_path)
    MARK = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(MARK)
    inventory = {}
    for l in r["layers"]:
        assert time.monotonic() - begun < 60, "Saved Oct31 anchor addendum exceeded60s"
        inventory[l["id"]] = D(l["qty"]) * MARK.price(l["sid"], "2024-10-31")
    eq(sum(inventory.values(), Z), r["inventory"], "Oct31 native inventory")
    start_wealth = {lid: cash[lid] + div[lid] + inventory.get(lid, Z) for lid in layers}
    eq(D(1000000) + sum(start_wealth.values(), Z), r["nav"], "Oct31 independent layer equity")

    groups = {}
    detail = []
    for lid, l in layers.items():
        opened = day(l["opened"])
        g = "existing_at_Oct31" if opened <= "2024-10-31" else "Nov_Dec_" + classifications[str(lid)]["classification"]
        terminal = n(l["cash"]) + n(l["dividend"])
        delta = terminal - start_wealth[lid]
        if delta or inventory.get(lid, Z):
            detail.append({"layer": lid, "sid": l["sid"], "opened": l["opened"], "closed": l["closed"],
                           "cohort": g, "kind": l["kind"], "begin_cash": cash[lid], "begin_dividend": div[lid],
                           "begin_inventory": inventory.get(lid, Z), "begin_wealth": start_wealth[lid],
                           "end_wealth": terminal, "wealth_change": delta})
        v = groups.setdefault(g, {"wealth_change": Z, "begin_inventory": Z, "new_layers": 0,
                                   "positive_layers": 0, "negative_layers": 0, "positive_sum": Z, "negative_sum": Z})
        v["wealth_change"] += delta
        v["begin_inventory"] += inventory.get(lid, Z)
        if opened > "2024-10-31":
            v["new_layers"] += 1
        if delta > 0:
            v["positive_layers"] += 1
            v["positive_sum"] += delta
        elif delta < 0:
            v["negative_layers"] += 1
            v["negative_sum"] += delta
    delta_nav = n(end["nav"]) - n(r["nav"])
    eq(sum((v["wealth_change"] for v in groups.values()), Z), delta_nav, "Nov-Dec cohort delta")

    months = []
    prior = by["2023-12-29"]
    for month in range(1, 13):
        rows = [x for x in ds if day(x["at"]).startswith(f"2024-{month:02d}")]
        terminal = rows[-1]
        start_day, end_day = day(prior["at"]), day(terminal["at"])
        ts = [t for t in b["trades"] if start_day < day(t["at"]) <= end_day]
        cash_delta = sum((cf(t) for t in ts), Z)
        new_div = sum((amount for date, amount in div_by_day.items() if start_day < date <= end_day), Z)
        inv_delta = n(terminal["inventory"]) - n(prior["inventory"])
        change = n(terminal["nav"]) - n(prior["nav"])
        eq(cash_delta + new_div + inv_delta, change, ("Actual month cash/div/inventory bridge", month))
        months.append({"month": f"2024-{month:02d}", "begin_NAV_day": start_day, "end_NAV_day": end_day,
                       "begin_NAV": prior["nav"], "end_NAV": terminal["nav"], "wealth_change": change,
                       "return_pct": change / n(prior["nav"]) * 100,
                       "CLOSEs": len(rows), "available": terminal["available"], "inventory": terminal["inventory"],
                       "inventory_NAV_pct": n(terminal["inventory"]) / n(terminal["nav"]) * 100,
                       "dividend_receivable": terminal["dividend_receivable"], "ACT_after_CLOSE": terminal["on"],
                       "actual_buy_fills": sum(t["side"] == "buy" for t in ts),
                       "actual_sell_fills": sum(t["side"] == "sell" for t in ts),
                       "net_trade_cash": cash_delta, "new_recognized_dividend": new_div, "inventory_change": inv_delta})
        prior = terminal
    eq(sum((x["wealth_change"] for x in months), Z), n(end["nav"]) - n(by["2023-12-29"]["nav"]), "12 natural month sum")
    assert before_hashes == {str(p): sha(p) for p in protected}, "Existing four-anchor audit changed"
    SRC.update(MARK.sources)
    report = {"passed": True, "anchor": "2024-10-31", "anchor_NAV": r["nav"],
              "anchor_available": r["available"], "anchor_inventory": r["inventory"],
              "anchor_dividend_receivable": r["dividend_receivable"],
              "anchor_vs_year_start": n(r["nav"]) - n(by["2023-12-29"]["nav"]),
              "Oct8_to_Oct31_NAV_change": n(r["nav"]) - n(by["2024-10-08"]["nav"]),
              "Nov_Dec_NAV_change": delta_nav, "Nov_Dec_return_pct": delta_nav / n(r["nav"]) * 100,
              "Nov_Dec_cohorts": groups, "month_end_NAV_table": months,
              "cohort_boundary": "Existing_at_Oct31 uses actual entry <=Oct31. New Nov-Dec layers split using actual before-fill quantity and prior actual buys, not native kind.",
              "causal_boundary": "Natural month-end descriptive split, not a signal/strategy change. New-layer losses are actual attribution, not fully avoidable counterfactual gains; positive new layers also exist.",
              "preserved_original_audits": before_hashes,
              "native_mark_evaluations": len(MARK.mark_cache), "native_mark_securities": len(MARK.views),
              "new_accounts": 0, "new_Market": 0, "new_routes": 0,
              "seconds": time.monotonic() - begun, "source_sha256": SRC}
    save("OCT31_MONTHEND_ADDENDUM.json", report)
    save("OCT31_TO_YEAR_END_LAYER_WEALTH.json", detail)
    print(json.dumps({"passed": True, "NAV": r["nav"], "Nov_Dec_delta": str(delta_nav),
                      "cohorts": {k: str(v["wealth_change"]) for k, v in groups.items()},
                      "marks": len(MARK.mark_cache), "seconds": report["seconds"]}, ensure_ascii=False))


if __name__ == "__main__":
    O.mkdir(parents=True, exist_ok=True)
    main()

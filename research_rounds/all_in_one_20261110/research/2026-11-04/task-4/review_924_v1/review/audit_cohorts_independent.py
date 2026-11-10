"""Saved actual-fill arithmetic plus original native marks at two anchors only."""
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


def n(value):
    return D(str(value))


def day(value):
    return str(value)[:10]


def eq(a, b, label):
    assert abs(a - b) < EPS, (label, str(a), str(b))


def main():
    begun = time.monotonic()
    bind(__file__)
    book = gz(BASE / "B.json.gz")
    daily = gz(BASE / "daily.jsonl.gz", True)
    by_day = {day(x["at"]): x for x in daily}
    rows2024 = [x for x in daily if day(x["at"]).startswith("2024")]
    assert not by_day["2023-12-29"]["positions"], "This audit explicitly assumes verified empty year-start inventory"
    assert not any(x["kind"] == "split" and day(x["at"]).startswith("2024") for x in book["audit"])
    layers = {x["id"]: x for x in book["layers"]}
    buys = [x for x in book["trades"] if x["side"] == "buy"]
    assert len(buys) == len({x["layer"] for x in buys}) == len(layers), "Do not silently classify partial fills as independent entries"
    tx = defaultdict(list)
    for t in book["trades"]:
        tx[day(t["at"])].append(t)
    known_before2024 = {x["security_id"] for x in buys if day(x["at"]) < "2024-01-01"}
    seen = set(known_before2024)
    quantities = defaultdict(int)
    classes = {}
    mismatches = []
    for r in rows2024:
        date = day(r["at"])
        for t in tx[date]:
            sid = t["security_id"]
            if t["side"] == "buy":
                before = quantities[sid]
                label = "add_to_existing" if before else "reentry" if sid in seen else "first_ever_entry"
                signal_day = day(t["signal_at"])
                signal_held = bool(by_day[signal_day]["positions"].get(sid, 0))
                classes[t["layer"]] = {"classification": label, "actual_quantity_before_fill": before,
                                        "signal_CLOSE_held": signal_held, "signal_day": signal_day,
                                        "opened": date, "role_kind": t["kind"]}
                if signal_held != bool(before):
                    mismatches.append({"layer": t["layer"], **classes[t["layer"]]})
                quantities[sid] += t["shares"]
                seen.add(sid)
            else:
                assert quantities[sid] >= t["shares"], ("Saved actual sell overdraw", date, sid)
                assert sum(p["shares"] for p in t["parts"]) == t["shares"]
                quantities[sid] -= t["shares"]
        actual = {sid: q for sid, q in quantities.items() if q}
        assert actual == r["positions"], ("Saved actual quantity bridge", date)

    # All older layers are closed at the verified empty 2023 year-end anchor.
    # Their recognized dividends remain baseline rights and must not be counted
    # again merely because a later payment/settlement occurs.
    old_seed_div = {lid: n(l["dividend"]) for lid, l in layers.items() if day(l["opened"]) < "2024-01-01"}
    div_events = defaultdict(list)
    for a in book["audit"]:
        if a["kind"] != "dividend_accrual":
            continue
        rec = a["receivable"]
        date = day(rec["ex_at"])
        if not date.startswith("2024"):
            continue
        prev = next(r for r in reversed(daily) if day(r["at"]) < date)
        entitled = [l for l in prev["layers"] if l["sid"] == rec["security_id"] and l["qty"]]
        qty = sum(l["qty"] for l in entitled)
        assert qty and rec["entitlement_basis"] == "protocol_previous_close_inventory_and_explicit_net_factor"
        for l in entitled:
            assert day(l["opened"]).startswith("2024")
            div_events[date].append((l["id"], n(rec["net_local"]) * D(l["qty"]) / D(qty)))
    reconstructed_div = defaultdict(lambda: Z, old_seed_div)
    for events in div_events.values():
        for lid, amount in events:
            reconstructed_div[lid] += amount
    for lid, l in layers.items():
        eq(reconstructed_div[lid], n(l["dividend"]), ("Per-layer recognized dividends", lid))

    reader_path = bind(ROOT / "new_price_trend_v1/native_mark_reader.py")
    spec = importlib.util.spec_from_file_location("independent_924_native_mark", reader_path)
    MARK = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(MARK)
    anchors = {}
    for date in ["2023-12-29", "2024-09-23", "2024-10-08", "2024-12-31"]:
        assert time.monotonic() - begun < 60, "Bounded saved-mark audit exceeded60sec"
        cash = defaultdict(lambda: Z)
        for t in book["trades"]:
            if day(t["at"]) > date:
                continue
            if t["side"] == "buy":
                cash[t["layer"]] -= n(t["gross_cny"]) + n(t["fees_cny"])
            else:
                for part in t["parts"]:
                    cash[part["layer"]] += n(part["net_cash"])
        div = defaultdict(lambda: Z, old_seed_div)
        for d, events in div_events.items():
            if d <= date:
                for lid, amount in events:
                    div[lid] += amount
        inventory = {l["id"]: D(l["qty"]) * MARK.price(l["sid"], date)
                     for l in by_day[date]["layers"] if l["qty"]}
        eq(sum(inventory.values(), Z), n(by_day[date]["inventory"]), ("Native mark over saved shares", date))
        wealth = {lid: cash[lid] + div[lid] + inventory.get(lid, Z) for lid in layers}
        eq(D(1000000) + sum(wealth.values(), Z), n(by_day[date]["nav"]), ("Per-layer total equity anchor", date))
        anchors[date] = {"cash": dict(cash), "dividend": dict(div), "inventory": inventory, "wealth": wealth}

    def cohort(lid):
        opened = day(layers[lid]["opened"])
        if opened <= "2024-09-23":
            return "pre924_layers"
        if opened <= "2024-10-08":
            return "rally_924_to_Oct8_layers"
        return "postpeak_" + classes[lid]["classification"]

    breakdown = {}
    for phase, start, end in [("rally", "2024-09-23", "2024-10-08"),
                               ("postpeak", "2024-10-08", "2024-12-31"),
                               ("post924_total", "2024-09-23", "2024-12-31")]:
        groups = {}
        detail = []
        for lid in layers:
            group = cohort(lid)
            change = anchors[end]["wealth"][lid] - anchors[start]["wealth"][lid]
            if not change and day(layers[lid]["opened"]) < "2024-01-01":
                continue
            row = {"layer": lid, "sid": layers[lid]["sid"], "cohort": group,
                   "opened": layers[lid]["opened"], "kind": layers[lid]["kind"],
                   "wealth_change": change,
                   "begin_cash": anchors[start]["cash"].get(lid, Z), "end_cash": anchors[end]["cash"].get(lid, Z),
                   "begin_dividend": anchors[start]["dividend"].get(lid, Z), "end_dividend": anchors[end]["dividend"].get(lid, Z),
                   "begin_inventory": anchors[start]["inventory"].get(lid, Z), "end_inventory": anchors[end]["inventory"].get(lid, Z)}
            detail.append(row)
            g = groups.setdefault(group, {"wealth_change": Z, "begin_inventory": Z, "end_inventory": Z,
                                          "buy_layers_in_phase": 0, "all_layer_ids": []})
            for k in ["wealth_change", "begin_inventory", "end_inventory"]:
                g[k] += row[k]
            if start < day(layers[lid]["opened"]) <= end:
                g["buy_layers_in_phase"] += 1
            g["all_layer_ids"].append(lid)
        total = sum((g["wealth_change"] for g in groups.values()), Z)
        eq(total, n(by_day[end]["nav"]) - n(by_day[start]["nav"]), ("Independent cohort conservation", phase))
        breakdown[phase] = {"anchor": start, "end": end, "total_NAV_change": total, "groups": groups}
        save("INDEPENDENT_LAYER_WEALTH_" + phase + ".json", detail)

    SOURCES.update(MARK.sources)
    result = {"passed": True, "scope": "Independent saved actual-fill quantities/cash/dividends and original native marks at two invested anchors; no new Account/Market/Runner/RiskBook.",
              "phases": breakdown, "all2024_actual_quantity_days_exact": len(rows2024),
              "all_native_layer_recognized_dividends_exact": len(layers),
              "actual_buy_classification_count": dict(Counter(x["classification"] for x in classes.values())),
              "signal_held_vs_actual_before_fill_mismatches": mismatches,
              "native_mark_evaluations": len(MARK.mark_cache), "native_mark_securities": len(MARK.views),
              "new_accounts": 0, "new_Market_instances": 0, "new_routes": 0,
              "evaluation_not_counterfactual": True, "seconds": time.monotonic() - begun,
              "source_sha256": SOURCES}
    save("INDEPENDENT_COHORT_BREAKDOWN.json", result)
    save("INDEPENDENT_ACTUAL_BUY_CLASSIFICATIONS.json", classes)
    print(json.dumps({"passed": True, "seconds": result["seconds"], "marks": len(MARK.mark_cache),
                      "phases": {k: {g: str(r["wealth_change"]) for g, r in v["groups"].items()} for k, v in breakdown.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    O.mkdir(parents=True, exist_ok=True)
    main()

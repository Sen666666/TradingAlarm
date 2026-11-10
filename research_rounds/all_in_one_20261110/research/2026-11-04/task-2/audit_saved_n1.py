#!/usr/bin/env python3
"""Read-only adapter to the EXISTING N1 independent account checker. No execution."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time
from research_flow import sha, save, verify_identity, ensure_assertions


def main():
    ensure_assertions()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root = args.project_root.resolve()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError("Use a new receipt outside the active project")
    started = time.monotonic()
    round_dir = root / "research_rounds/n1-structural-finite-20261029"
    source = root / "research_rounds/broad-stage-reentry-20261029"
    old = root / "research_rounds/rs-h1-execution-20261025"
    observed = {}

    def observe(file):
        file = Path(file).resolve()
        current = dict(path=str(file), sha256=sha(file))
        if str(file) in observed and current != observed[str(file)]:
            raise ValueError(f"Input changed during audit: {file}")
        observed[str(file)] = current
        return file

    def read(file):
        return json.loads(observe(file).read_text())

    def rows(file):
        with gzip.open(observe(file), "rt") as f:
            return [json.loads(line) for line in f]

    # Reuse audit_account and Prices unchanged; never import finish.py (it writes).
    sys.path.insert(0, str(old / "code"))
    for file in (old / "code").glob("*.py"):
        observe(file)
    sp = importlib.util.spec_from_file_location("saved_n1_native_audit", old / "code/analyze_accounts.py")
    q = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(q)
    import pandas as pd
    from decimal import Decimal as D
    from sector_account import FeeSchedule, FeeComponent
    from market_rules import market_identity_on, version_on

    meta = pd.read_csv(observe(root / "research_rounds/tech-compound-design-20261026/proposed-pool.csv")).set_index("symbol").to_dict("index")
    rules = read(root / "research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json")
    protocol = read(old / "inputs-v2/economic-protocol.json")
    prices = q.Prices.__new__(q.Prices)
    prices.records = {r["series_id"]: r for r in read(root / "research_rounds/pvr-act-comparison-20261027/input/manifest.json")["series"]}
    prices.cache = {}
    run = read(round_dir / "full/RUN_META.json")
    aliases = read(round_dir / "full/ALIASES.json")
    expected = read(round_dir / "ACCOUNTING.json")
    objects = {"R_base_orig": read(source / "results/N1.json")}
    daily = {"R_base_orig": [r for r in rows(source / "results/daily.jsonl.gz") if r["account"] == "N1"]}
    for r in rows(round_dir / "full/daily.jsonl.gz"):
        daily.setdefault(r.pop("path"), []).append(r)
    for name in set(run["paths"]) | set(aliases):
        objects[name] = read(round_dir / "full" / (name + ".json"))
    for name, record in aliases.items():
        daily[name] = daily[record["economic_source"]]
    if set(objects) != set(daily) or len(objects) != 8:
        raise ValueError("Incomplete saved N1 paths")
    names = [r["path"] for r in expected["receipts"]]
    if expected.get("passed") is not True or len(names) != 8 or len(set(names)) != 8 or set(names) != set(objects):
        raise ValueError("Native receipts must pass and cover exactly all eight distinct paths")
    sids = {e["receipt"]["security_id"] for obj in objects.values() for e in obj["audit"] if e["kind"] == "fill"}
    for sid in sids:
        record = prices.records[sid]
        observe(record["raw"]["path"])
        observe(record["adjustment"]["actions"]["path"])
    calendar = sorted({pd.Timestamp(t) for t in rules["calendars"]["A"]} |
                      {pd.Timestamp("2026-10-" + d + "T09:30:00+08:00") for d in ["27", "28", "29", "30"]})
    receipts = []
    fee_checks = 0
    for saved in expected["receipts"]:
        name = saved["path"]
        obj, ds = objects[name], daily[name]
        if len(ds) != 681:
            raise ValueError(f"Partial daily path: {name}")
        cost = 2 if "cost2" in name else 1
        state = {}
        for e in obj["audit"]:
            if e["kind"] != "fill":
                continue
            r = e["receipt"]
            day = pd.Timestamp(r["at"]).date()
            venue = market_identity_on(rules, r["security_id"], day, protocol["approved_proxy_ids"])["venue"]
            contract = version_on(rules["fee_versions"][venue], str(day), protocol["approved_proxy_ids"])["schedule"]
            fs = FeeSchedule(contract["schedule_id"], tuple(FeeComponent(**c) for c in contract["components"]))
            if fs.schedule_id != e["fee_schedule"]:
                raise ValueError("Fee schedule differs")
            paid, accrual = state.get(e["order_id"], ({}, {}))
            kwargs = dict(shares=r["shares"], par_value=rules.get("security_metadata", {}).get(r["security_id"], {}).get("par_value"))
            components = fs.incremental(r["side"], D(r["gross_cny"]), paid, accrual, cost, **kwargs)
            if components != {k: D(v) for k, v in e["fee_components"].items()}:
                raise ValueError("Fee components differ")
            rates = fs.rate_accrual(r["side"], D(r["gross_cny"]), cost, **kwargs)
            state[e["order_id"]] = ({k: paid.get(k, D(0)) + v for k, v in components.items()},
                                    {k: accrual.get(k, D(0)) + v for k, v in rates.items()})
            fee_checks += 1
        _, receipt = q.audit_account("B0_" + name + ("_cost2" if cost == 2 else "_base"),
                                     dict(audit_log=obj["audit"]), ds, prices, meta, calendar)
        actual = dict(path=name, **receipt)
        if actual != saved:
            raise ValueError(f"Native accounting receipt differs: {name}")
        receipts.append(actual)
        print(json.dumps(dict(path=name, audited_days=len(ds), passed=True)), flush=True)
    verify_identity(list(observed.values()))
    save(output, dict(passed=True, adapter="existing_N1_native_checker", new_economic_paths=0,
         historical_paths=8, daily_rows=8 * 681, independent_fee_fills=fee_checks,
         receipts_exactly_match_saved=True, receipts=receipts, observed_inputs=list(observed.values()),
         seconds=time.monotonic() - started,
         scope="native money/share/NAV/campaign/slippage/fee/T+1 checks; existing corporate-action handling unchanged"))


if __name__ == "__main__":
    main()

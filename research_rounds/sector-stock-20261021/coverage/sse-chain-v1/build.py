"""Offline source normalization. Never imports/evaluates saved JavaScript."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
ANCHOR = "2026-10-22"
END = "2026-10-23"
START = "2014-12-08"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(name, obj):
    (OUT / name).open("x").write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def table(name, rows, fields=None):
    with (OUT / name).open("x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def parse(p):
    m = re.fullmatch(r"\s*metadataProbe\((.*)\);?\s*", p.read_text(), re.S)
    if not m:
        raise ValueError(f"Unexpected JSONP wrapper: {p}")
    return json.loads(m.group(1))


protocol = json.loads((OUT / "protocol.json").read_text())
for row in protocol["source_manifest"]:
    p = Path(row["path"])
    assert p.stat().st_size == row["bytes"] and sha(p) == row["sha256"], p

receipts = {}
for sub in ["public-01-sse-pagination07", "public-02-sse-chain01"]:
    receipt = json.loads((BASE / sub / "results.json").read_text())
    for r in receipt["requests"]:
        p = BASE / sub / r["response"]
        assert r["status"] == 200 and sha(p) == r["sha256"]
        assert p.stat().st_size == r["bytes"]
        receipts[p] = r

ap = [BASE / "public-01-sse-pagination07/01.body"] + [BASE / f"public-02-sse-chain01/{i:02}.body" for i in range(1, 14)]
cp = [BASE / "public-01-sse-pagination07/02.body"] + [BASE / f"public-02-sse-chain01/{i:02}.body" for i in range(14, 20)]
checks = []


def pages(paths, total, key, sql):
    allrows = []
    for page, p in enumerate(paths, 1):
        d = parse(p)
        h = d["pageHelp"]
        rows = d["result"]
        assert not d["actionErrors"] and not d["fieldErrors"]
        assert d["sqlId"] == sql
        assert h["pageNo"] == h["beginPage"] == h["endPage"] == page
        assert h["total"] == total and h["pageCount"] == len(paths)
        assert h["pageSize"] == 100 and h["data"] == rows
        assert len(rows) == min(100, total - (page - 1) * 100)
        assert [int(r["NUM"]) for r in rows] == list(range((page - 1) * 100 + 1, min(page * 100, total) + 1))
        assert {r[key] for r in rows} == {ANCHOR}
        for localrow, r in enumerate(rows, 1):
            assert re.fullmatch(r"\d{5}", r["SECURITY_CODE"])
            allrows.append((r, p, page, localrow))
        checks.append({"kind": "adjustment" if key == "FILE_DATE" else "current", "page": page,
                       "rows": len(rows), "total": total, "snapshot_date": ANCHOR,
                       "first_num": rows[0]["NUM"], "last_num": rows[-1]["NUM"], "passed": True})
    assert len(allrows) == total
    return allrows


ar = pages(ap, 1307, "FILE_DATE", "COMMON_SSE_JYFW_HGT_XXPL_BDZQTZXX_L")
cr = pages(cp, 698, "UPDATE_DATE", "COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L")
assert len({r[0]["SECURITY_CODE"] for r in cr}) == 698
assert len({(r[0]["SECURITY_CODE"], r[0]["VALID_DATE"], r[0]["ADJUST_TYPE"]) for r in ar}) == 1307
assert len({(r[0]["SECURITY_CODE"], r[0]["VALID_DATE"]) for r in ar}) == 1307

events = []
for r, p, page, localrow in ar:
    assert r["ADJUST_TYPE"] in {"调进", "调出"}
    datetime.strptime(r["VALID_DATE"], "%Y-%m-%d")
    events.append({"event_id": f"sse-adjustment-num-{r['NUM']}", "num": int(r["NUM"]),
                   "code": r["SECURITY_CODE"], "symbol": r["SECURITY_CODE"] + ".HK", "route": "SSE_southbound",
                   "effective_date": r["VALID_DATE"], "event": {"调进": "add", "调出": "remove"}[r["ADJUST_TYPE"]],
                   "action_raw": r["ADJUST_TYPE"], "security_type_raw": r["SECURITY_TYPE"],
                   "name_cn_raw": r["SECURITY_ABBR"], "name_en_raw": r["ABBR_EN"],
                   "source_file_date": r["FILE_DATE"], "source_page": page, "source_page_row": localrow,
                   "source_path": str(p), "source_sha256": sha(p), "source_url": receipts[p]["url"],
                   "future_effective_at_anchor": r["VALID_DATE"] > ANCHOR,
                   "announced_at": "", "known_at": "", "eligible_for_account_input": False})
events.sort(key=lambda r: (r["effective_date"], r["code"], r["num"]))
current = []
for r, p, page, localrow in cr:
    current.append({"num": int(r["NUM"]), "code": r["SECURITY_CODE"], "symbol": r["SECURITY_CODE"] + ".HK",
                    "route": "SSE_southbound", "security_type_raw": r["SECURITY_TYPE"], "trade_flag_raw": r["TRADE_FLAG"],
                    "name_cn_raw": r["ABBR_CN"], "name_en_raw": r["ABBR_EN"], "source_update_date": r["UPDATE_DATE"],
                    "source_page": page, "source_page_row": localrow, "source_path": str(p),
                    "source_sha256": sha(p), "source_url": receipts[p]["url"],
                    "announced_at": "", "known_at": "", "eligible_for_account_input": False})
table("adjustments.csv", events)
table("current-list.csv", current)
table("page-validation.csv", checks)

anchor = {r["code"] for r in current}
happened = [r for r in events if r["effective_date"] <= ANCHOR]
future = [r for r in events if r["effective_date"] > ANCHOR]
state = set(anchor)
conflicts = []
for r in reversed(happened):
    code, action = r["code"], r["event"]
    if action == "add":
        if code not in state:
            conflicts.append({"direction": "reverse", "event_id": r["event_id"], "code": code, "effective_date": r["effective_date"], "problem": "add_missing_in_later_state"})
        state.discard(code)
    else:
        if code in state:
            conflicts.append({"direction": "reverse", "event_id": r["event_id"], "code": code, "effective_date": r["effective_date"], "problem": "remove_already_present_in_later_state"})
        state.add(code)
baseline = set(state)
bydate = defaultdict(list)
for r in happened:
    bydate[r["effective_date"]].append(r)
counts = []
states = {}
for date, rows in sorted(bydate.items()):
    for r in rows:
        code = r["code"]
        if r["event"] == "add":
            if code in state:
                conflicts.append({"direction": "forward", "event_id": r["event_id"], "code": code, "effective_date": date, "problem": "duplicate_add"})
            state.add(code)
        else:
            if code not in state:
                conflicts.append({"direction": "forward", "event_id": r["event_id"], "code": code, "effective_date": date, "problem": "remove_missing"})
            state.discard(code)
    counts.append({"effective_date": date, "adds": sum(r["event"] == "add" for r in rows), "removes": sum(r["event"] == "remove" for r in rows), "conditional_list_members": len(state)})
    states[date] = set(state)
table("conflicts.csv", conflicts, ["direction", "event_id", "code", "effective_date", "problem"])
table("effective-date-member-counts.csv", counts)
chain_valid = not conflicts and state == anchor

intervals = []
if chain_valid:
    table("inferred-baseline-before-2014-12-08.csv", [{"code": c, "symbol": c + ".HK", "route": "SSE_southbound", "boundary": "immediately_before_first_saved_event_2014-12-08", "basis": "reverse_1306_events_from_2026-10-22_anchor_conditional_on_chain_completeness", "official_initial_list_verified": False, "announced_at": "", "known_at": "", "eligible_for_account_input": False} for c in sorted(baseline)])
    universe = baseline | anchor | {r["code"] for r in events}
    bycode = defaultdict(list)
    for r in happened:
        bycode[r["code"]].append(r)
    for c in sorted(universe):
        left, present, evidence = START, c in baseline, "inferred_pre_first_event_baseline"
        for r in bycode[c]:
            if r["effective_date"] > left:
                intervals.append({"code": c, "symbol": c + ".HK", "route": "SSE_southbound", "effective_from_inclusive": left, "effective_to_exclusive": r["effective_date"], "conditional_list_state": "listed" if present else "not_listed", "evidence": evidence, "announced_at": "", "known_at": "", "issuer_identity_verified": False, "complete_southbound_union": False, "eligible_for_account_input": False})
            left, present, evidence = r["effective_date"], r["event"] == "add", r["event_id"]
        intervals.append({"code": c, "symbol": c + ".HK", "route": "SSE_southbound", "effective_from_inclusive": left, "effective_to_exclusive": END, "conditional_list_state": "listed" if present else "not_listed", "evidence": evidence, "announced_at": "", "known_at": "", "issuer_identity_verified": False, "complete_southbound_union": False, "eligible_for_account_input": False})
    table("conditional-list-state-intervals.csv", intervals)
    with (BASE / "revalidation-20261022/southbound/conditional-list-state-intervals.csv").open() as f:
        sz = list(csv.DictReader(f))
    comparison = []
    differences = []
    for date in ["2016-12-05", "2020-01-02", "2026-10-20", "2026-10-21"]:
        sse = {r["code"] for r in intervals if r["effective_from_inclusive"] <= date < r["effective_to_exclusive"] and r["conditional_list_state"] == "listed"}
        szse = {r["code"] for r in sz if r["effective_from_inclusive"] <= date < r["effective_to_exclusive"] and r["reconstructed_list_state"] == "listed"}
        comparison.append({"date": date, "sse_all_security_types": len(sse), "sz_source_codes": len(szse), "code_intersection": len(sse & szse), "sse_only_codes": len(sse - szse), "sz_only_codes": len(szse - sse), "descriptive_code_union": len(sse | szse), "same_security_type_population": False, "eligible_for_account_input": False})
        for route, codes in [("SSE_only", sse - szse), ("SZ_only", szse - sse)]:
            differences.extend({"date": date, "code": c, "difference": route, "reason_not_inferred": "route_and_security_type_differences_not_errors_or_executable_union", "eligible_for_account_input": False} for c in sorted(codes))
    table("sz-condition-comparison.csv", comparison)
    table("sz-condition-differences.csv", differences)

summary = {"created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "offline": True, "protocol_sha256": sha(OUT / "protocol.json"), "builder_sha256": sha(Path(__file__)), "source_files_verified": len(protocol["source_manifest"]), "source_response_hashes_verified": len(receipts), "adjustment_pages": len(ap), "current_pages": len(cp), "adjustments": len(events), "current_members": len(current), "current_types": dict(Counter(r["security_type_raw"] for r in current)), "current_trade_flags": dict(Counter(r["trade_flag_raw"] for r in current)), "adjustment_types": dict(Counter(r["security_type_raw"] for r in events)), "adjustment_actions": dict(Counter(r["event"] for r in events)), "effective_min": events[0]["effective_date"], "effective_max": events[-1]["effective_date"], "anchor_date": ANCHOR, "happened_events": len(happened), "future_events_preserved": future, "inferred_pre_first_event_baseline_size": len(baseline), "chain_conflicts": len(conflicts), "forward_recovers_anchor": state == anchor, "chain_arithmetic_consistent": chain_valid, "effective_dates": len(counts), "intervals": len(intervals), "official_historical_initial_list_verified": False, "source_event_chain_complete_proven": False, "known_at_values_populated": 0, "account_runs": 0, "algorithm_changes": 0, "economic_admission": False}
dump("verification.json", summary)
dump("source-manifest.json", {"protocol_sha256": sha(OUT / "protocol.json"), "sources": protocol["source_manifest"], "after_processing_hashes_unchanged": all(sha(Path(r["path"])) == r["sha256"] for r in protocol["source_manifest"])})
print(json.dumps({k: v for k, v in summary.items() if k not in {"future_events_preserved"}}, ensure_ascii=False, indent=2))

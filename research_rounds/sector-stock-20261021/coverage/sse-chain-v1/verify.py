"""Independent verifier: direct next-event state inference from raw JSON."""
import csv
import hashlib
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read_csv(name):
    with (HERE / name).open() as f:
        return list(csv.DictReader(f))


def raw(path):
    # No import of builder/parser and no JavaScript execution.
    text = path.read_text().strip()
    assert text.startswith("metadataProbe(")
    payload, consumed = json.JSONDecoder().raw_decode(text[len("metadataProbe("):])
    assert text[len("metadataProbe(") + consumed:] in {")", ");"}
    return payload


event_paths = [ROOT / "public-01-sse-pagination07/01.body"] + [ROOT / f"public-02-sse-chain01/{n:02}.body" for n in range(1, 14)]
current_paths = [ROOT / "public-01-sse-pagination07/02.body"] + [ROOT / f"public-02-sse-chain01/{n:02}.body" for n in range(14, 20)]
events = [x for p in event_paths for x in raw(p)["pageHelp"]["data"]]
current = [x for p in current_paths for x in raw(p)["pageHelp"]["data"]]
assert len(events) == 1307 and len(current) == 698
assert {int(r["NUM"]) for r in events} == set(range(1, 1308))
assert {int(r["NUM"]) for r in current} == set(range(1, 699))
normalized_events = read_csv("adjustments.csv")
normalized_current = read_csv("current-list.csv")
event_index = {r["num"]: r for r in normalized_events}
current_index = {r["num"]: r for r in normalized_current}
assert len(event_index) == len(events) and len(current_index) == len(current)
for r in events:
    n = event_index[r["NUM"]]
    for source, dest in [("SECURITY_CODE", "code"), ("VALID_DATE", "effective_date"), ("ADJUST_TYPE", "action_raw"), ("SECURITY_TYPE", "security_type_raw"), ("FILE_DATE", "source_file_date"), ("SECURITY_ABBR", "name_cn_raw"), ("ABBR_EN", "name_en_raw")]:
        assert r[source] == n[dest], (r, n)
    assert n["event"] == {"调进": "add", "调出": "remove"}[r["ADJUST_TYPE"]]
    assert n["future_effective_at_anchor"] == str(r["VALID_DATE"] > "2026-10-22")
for r in current:
    n = current_index[r["NUM"]]
    for source, dest in [("SECURITY_CODE", "code"), ("SECURITY_TYPE", "security_type_raw"), ("UPDATE_DATE", "source_update_date"), ("TRADE_FLAG", "trade_flag_raw"), ("ABBR_CN", "name_cn_raw"), ("ABBR_EN", "name_en_raw")]:
        assert r[source] == n[dest]
for r in normalized_events + normalized_current:
    assert r["announced_at"] == r["known_at"] == ""
    assert r["eligible_for_account_input"] == "False"

bycode = defaultdict(list)
for r in events:
    if r["VALID_DATE"] <= "2026-10-22":
        bycode[r["SECURITY_CODE"]].append(r)
for rows in bycode.values():
    rows.sort(key=lambda r: r["VALID_DATE"])
anchor = {r["SECURITY_CODE"] for r in current}
universe = anchor | set(bycode)
inferred_baseline = {c for c in universe if (bycode[c][0]["ADJUST_TYPE"] == "调出" if bycode[c] else c in anchor)}
assert inferred_baseline == {r["code"] for r in read_csv("inferred-baseline-before-2014-12-08.csv")}
intervals = read_csv("conditional-list-state-intervals.csv")
byinterval = defaultdict(list)
for r in intervals:
    byinterval[r["code"]].append(r)
    assert r["announced_at"] == r["known_at"] == ""
    assert r["eligible_for_account_input"] == "False"
    assert r["effective_from_inclusive"] < r["effective_to_exclusive"]
assert set(byinterval) == universe
for c, rows in byinterval.items():
    rows.sort(key=lambda r: r["effective_from_inclusive"])
    assert rows[0]["effective_from_inclusive"] == "2014-12-08"
    assert rows[-1]["effective_to_exclusive"] == "2026-10-23"
    assert all(a["effective_to_exclusive"] == b["effective_from_inclusive"] for a, b in zip(rows, rows[1:]))

dates = sorted({r["VALID_DATE"] for r in events if r["VALID_DATE"] <= "2026-10-22"} | {"2026-10-22", "2016-12-05", "2020-01-02", "2026-10-20", "2026-10-21"})
checks = 0
for date in dates:
    # A code is present just before its next removal; absent just before its next addition.
    # No remaining event means it equals the dated anchor. This does not use a reconstructed baseline.
    expected = set()
    for c in universe:
        next_event = next((r for r in bycode[c] if r["VALID_DATE"] > date), None)
        present = next_event["ADJUST_TYPE"] == "调出" if next_event else c in anchor
        if present:
            expected.add(c)
        rows = [r for r in byinterval[c] if r["effective_from_inclusive"] <= date < r["effective_to_exclusive"]]
        assert len(rows) == 1
        assert (rows[0]["conditional_list_state"] == "listed") == present, (c, date)
        checks += 1
    if date == "2026-10-22":
        assert expected == anchor and "02555" in expected
assert len([r for r in normalized_events if r["future_effective_at_anchor"] == "True"]) == 1

manifest = json.loads((HERE / "source-manifest.json").read_text())
for r in manifest["sources"]:
    assert hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() == r["sha256"]
result = {"source_rows_compared": len(events) + len(current), "event_NUM_complete": True, "current_NUM_complete": True, "boundary_dates": len(dates), "independent_code_date_states": checks, "inferred_baseline_count": len(inferred_baseline), "intervals_contiguous": True, "future_event_preserved_not_applied": True, "all_raw_type_values_preserved": True, "unknown_timestamps_stay_empty": True, "source_hashes_unchanged": True, "economic_admission": False, "all_checks_passed": True, "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(HERE / "verification-independent.json").open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""Independent mechanical checks of the frozen boundary observer, not a strategy.

Imports only the observer's pure functions. Does not read charts, review notes,
account outputs, or run the observer's CLI. Synthetic assertions establish
representation properties, not predictive value of price or volume.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path):
    spec = importlib.util.spec_from_file_location("boundary_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def json_value(value):
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def same(left, right):
    assert_frame_equal(
        left.reset_index(drop=True), right.reset_index(drop=True),
        check_exact=False, rtol=1e-12, atol=1e-12, check_dtype=True,
    )


def price_columns(frame):
    """Explicit exclusion of observed-volume evidence, never price facts."""
    return [c for c in frame if not (
        c == "volume" or c == "q" or "volume" in c.lower()
        or c.startswith("q_") or "_q_" in c
    )]


def fixture(bars, *, end_at=None):
    """bars are (open, high, low, close, volume); valid gaps are permitted."""
    prior = [(100., 110., 90., 100., 100.)] * 21
    values = prior + list(bars)
    dates = pd.bdate_range("2020-01-01", periods=len(values))
    frame = pd.DataFrame(values, columns=["open", "high", "low", "close", "volume"])
    frame.insert(0, "date", dates.strftime("%Y-%m-%d"))
    frame["observed_bar"] = True
    frame["synthetic_event_bar"] = False
    frame["valid"] = True
    case = {
        "id": "SYN", "symbol": "SYN",
        "start": frame.iloc[0]["date"],
        "anchor_requested": frame.iloc[21]["date"],
        "end": frame.iloc[-1 if end_at is None else 21 + end_at]["date"],
        "selection": "synthetic property fixture",
    }
    return frame, case


def independent_eligible(frame, excluded=()):
    """Price-only mask independently rebuilt from frozen protocol."""
    x = frame.copy()
    a = x[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    ok = np.isfinite(a).all(axis=1) & (a > 0).all(axis=1)
    ok &= a["low"].le(a["open"]) & a["open"].le(a["high"])
    ok &= a["low"].le(a["close"]) & a["close"].le(a["high"])
    if "observed_bar" in x:
        ok &= x["observed_bar"].fillna(False).astype(bool)
    if "synthetic_event_bar" in x:
        ok &= ~x["synthetic_event_bar"].fillna(False).astype(bool)
    if "source_invalid" in x:
        ok &= ~x["source_invalid"].fillna(False).astype(bool)
    if "source_anomaly" in x:
        ok &= x["source_anomaly"].fillna("").astype(str).str.strip().eq("")
    ok &= ~x["date"].astype(str).isin(set(excluded))
    return x.loc[ok].sort_values("date").reset_index(drop=True)


def independent_timeline(frame, case, lookback=21, window=21):
    """Oracle emits only independently defined touch episode facts."""
    x = frame.reset_index(drop=True)
    indices = x.index[
        (x["date"] >= max(case["start"], case["anchor_requested"]))
        & (x["date"] <= case["end"])
    ]
    if len(indices) == 0 or int(indices[0]) < lookback:
        return None
    anchor = int(indices[0])
    prior = x.iloc[anchor-lookback:anchor]
    bounds = {"upper": float(prior["high"].max()),
              "lower": float(prior["low"].min())}
    view = x.iloc[anchor:anchor+window]
    view = view.loc[view["date"] <= case["end"]]
    facts = []
    for side, boundary in bounds.items():
        touched = False
        gap = 0
        previous_outside = False
        for _, row in view.iterrows():
            contact = bool(row["high"] >= boundary if side == "upper"
                           else row["low"] <= boundary)
            outside = bool(row["close"] > boundary if side == "upper"
                           else row["close"] < boundary)
            first = contact and not touched
            retest = contact and touched and gap >= 1
            facts.append({
                "date": row["date"], "boundary": side,
                "touch": contact, "close_outside": outside,
                "first_touch": first, "recontact": retest,
                "consecutive_outside": outside and previous_outside,
            })
            if contact:
                touched = True
                gap = 0
            else:
                gap += 1
            previous_outside = outside
    return {"anchor": anchor, "prior": prior, "window": view,
            "bounds": bounds, "facts": pd.DataFrame(facts)}


def independent_selections(oracle):
    facts = oracle["facts"]
    touched = facts.loc[facts["touch"]]
    if touched.empty:
        return []
    first = touched["date"].min()
    sides = sorted(touched.loc[touched["date"] == first, "boundary"])
    result = [(first, sides)]
    later = facts.loc[
        (facts["date"] > first)
        & facts["boundary"].isin(sides)
        & facts["recontact"]
    ]
    if not later.empty:
        date = later["date"].min()
        result.append((date, sorted(later.loc[later["date"] == date, "boundary"])))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=Path(__file__).with_name("boundary_study.py"))
    parser.add_argument("--round", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.round.resolve()
    output = args.output or root / "validation.json"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing validation: {output}")
    mod = load_module(args.module.resolve())
    protocol = json.loads((root / "protocol-v0.json").read_text())
    checks = []

    def run(name, fn):
        try:
            detail = fn()
            checks.append({"name": name, "passed": True, "detail": json_value(detail)})
        except Exception as exc:
            checks.append({"name": name, "passed": False, "error": str(exc),
                           "traceback": traceback.format_exc()})

    # Concrete field assertions and test groups are below. They intentionally
    # use independent mathematical oracles rather than copied observer code.
    run("protocol_frozen", lambda: check_protocol(root, protocol))
    run("synthetic_order_is_not_net_displacement", lambda: check_order(mod))
    run("synthetic_same_prices_different_volume", lambda: check_volume(mod))
    run("synthetic_flat_range_and_price_clock", lambda: check_clock(mod))
    run("synthetic_simultaneous_two_sides", lambda: check_dual(mod))
    run("synthetic_persistence_recontact_and_gap", lambda: check_recontact(mod))
    run("synthetic_outcome_censoring_and_no_contact", lambda: check_censor(mod))
    run("synthetic_prefix_branch_causality", lambda: check_branch(mod))
    run("real_18_case_price_time_and_prefix_properties", lambda: check_real(mod, root, protocol))
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Independent mechanical validation; no subjective case conclusions, accounts, or predictive claims",
        "module": str(args.module.resolve()),
        "module_sha256": sha256(args.module),
        "test_sha256": sha256(__file__),
        "protocol_sha256": sha256(root / "protocol-v0.json"),
        "input_manifest_sha256": sha256(root / "inputs/manifest.json"),
        "price_mask_addendum_sha256": sha256(root / "inputs/observation-mask-addendum.json"),
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "limitations": [
            "Synthetic order and volume tests establish representation properties only.",
            "No assertion that volume must change a direction or improve prediction.",
            "Terminal no-contact review cards and whole-window metadata are not causal event records.",
            "Chart pixels, human review discipline, and subjective interpretations are not validated by these tests.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(json_value(report), indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"passed": report["passed"], "groups": len(checks),
                      "failed": [c["name"] for c in checks if not c["passed"]],
                      "output": str(output), "module_sha256": report["module_sha256"]},
                     ensure_ascii=False))
    return 0 if report["passed"] else 1


def check_protocol(root, protocol):
    freeze = json.loads((root / "protocol-freeze.json").read_text())
    assert freeze["sha256"] == sha256(root / "protocol-v0.json")
    assert protocol["lookback"] == protocol["window"] == 21
    assert protocol["response_horizons"] == [1, 5]
    assert len(protocol["cases"]) == 18
    assert len({c["id"] for c in protocol["cases"]}) == 18
    assert sum(c["selection"] == "known-failure-directed development probe"
               for c in protocol["cases"]) == 3
    return {"cases": 18, "lookback": 21, "window": 21, "directed_probes": 3}


def extract(mod, frame, case):
    eligible = mod.eligible_prices(frame, case["symbol"])
    ledger, meta = mod.case_facts(eligible, case)
    return eligible, ledger, meta, mod.select_events(ledger)


def selection_pairs(selections):
    return [(s["date"], sorted(s["selected_boundaries"])) for s in selections
            if s["selection_kind"] != "no_contact"]


def compare_oracle(ledger, oracle, selections):
    actual = ledger.sort_values(["date", "boundary"]).reset_index(drop=True)
    expected = oracle["facts"].sort_values(["date", "boundary"]).reset_index(drop=True)
    for field in ("date", "boundary", "touch", "close_outside"):
        assert actual[field].tolist() == expected[field].tolist(), field
    assert actual["recontact_after_no_touch"].tolist() == expected["recontact"].tolist()
    assert ((actual["first_touch_date"] == actual["date"]) & actual["touch"]).tolist() \
        == expected["first_touch"].tolist()
    assert actual["consecutive_outside"].gt(1).tolist() == expected["consecutive_outside"].tolist()
    assert selection_pairs(selections) == independent_selections(oracle)
    assert len(selections) <= 2
    assert not actual["same_day_order_known"].any()


def check_order(mod):
    # Exactly the same OHLCV bar multiset and same final price; only order differs.
    # Bars may open with gaps, as daily data permit. They are not intraday paths.
    peak = (111., 120., 110., 115., 300.)
    inside = (106., 109., 104., 106., 100.)
    current = (110., 113., 108., 112., 200.)
    a, case = fixture([peak, inside, current])
    b, _ = fixture([inside, peak, current])
    assert sorted(map(tuple, a[["open", "high", "low", "close", "volume"]].to_numpy())) \
        == sorted(map(tuple, b[["open", "high", "low", "close", "volume"]].to_numpy()))
    assert a["close"].iloc[-1] == b["close"].iloc[-1] == 112
    assert a["high"].max() == b["high"].max()
    assert a["low"].min() == b["low"].min()
    ea, la, _, sa = extract(mod, a, case)
    eb, lb, _, sb = extract(mod, b, case)
    compare_oracle(la, independent_timeline(a, case), sa)
    compare_oracle(lb, independent_timeline(b, case), sb)
    assert len(sa) == 2 and len(sb) == 1
    assert sa[1]["date"] == a.iloc[-1]["date"]
    # Same O/E/T/current under a fixed peak, but recovery order differs too.
    origin = (100., 101., 99., 100., 100.)
    high = (120., 120., 120., 120., 300.)
    low = (105., 105., 105., 105., 200.)
    recross = (115., 115., 115., 115., 100.)
    finish = (108., 108., 108., 108., 100.)
    x, cx = fixture([origin, high, low, recross, finish])
    y, _ = fixture([origin, high, low, finish, recross, finish])
    cy = {**cx, "end": y.iloc[-1]["date"]}
    _, lx, _, sx = extract(mod, x, cx)
    _, ly, _, sy = extract(mod, y, cy)
    for raw in (x, y):
        observed = raw.iloc[21:]
        assert observed.iloc[0]["close"] == 100
        assert observed["close"].max() == 120
        assert observed.loc[observed.index > observed["close"].idxmax(), "close"].min() == 105
        assert observed.iloc[-1]["close"] == 108
    assert selection_pairs(sx) != selection_pairs(sy)
    return {
        "same_bar_multiset_different_event_chain": True,
        "same_origin_peak_post_peak_trough_current_different_event_timing": True,
        "claim": "The observer records order lost by endpoint and extreme summaries; no prediction claim",
    }


def check_volume(mod):
    bars = [(100., 112., 99., 111., 300.),
            (108., 109., 104., 106., 100.),
            (106., 113., 105., 112., 100.),
            (112., 114., 111., 113., 100.)]
    a, case = fixture(bars)
    b = a.copy()
    b.loc[21:, "volume"] = [100., 300., 100., 100.]
    ea, la, ma, sa = extract(mod, a, case)
    eb, lb, mb, sb = extract(mod, b, case)
    same(la[price_columns(la)], lb[price_columns(lb)])
    assert sa == sb
    same(mod.response_outcomes(ea, sa, case), mod.response_outcomes(eb, sb, case))
    assert la["q"].tolist() != lb["q"].tolist()
    assert a["volume"].sum() == b["volume"].sum()
    assert ma["volume_reference"] == mb["volume_reference"] == 100
    return {"same_prices_same_events_same_responses": True,
            "same_total_volume_different_event_volume": True,
            "forced_direction_change_asserted": False}


def check_clock(mod):
    bars = [(100., 100., 100., 100., 0.)] * 9
    raw, case = fixture(bars)
    raw.loc[21, "valid"] = False
    raw.loc[21, "volume"] = np.nan
    raw.loc[22, "volume"] = 0
    raw.loc[23, "observed_bar"] = False
    raw.loc[24, "synthetic_event_bar"] = True
    raw.loc[25, "open"] = 101
    raw.loc[26, "close"] = np.nan
    raw["source_invalid"] = False
    raw.loc[27, "source_invalid"] = True
    raw["source_anomaly"] = ""
    raw.loc[28, "source_anomaly"] = "quarantined"
    excluded = [raw.loc[29, "date"]]
    eligible = mod.eligible_prices(raw, "SYN", excluded)
    assert eligible.index.strftime("%Y-%m-%d").tolist() == raw.loc[:22, "date"].tolist()
    ledger, _ = mod.case_facts(eligible, case)
    assert ledger["zero_range"].all()
    assert ledger["close_location"].isna().all()
    assert not ledger["close_location_defined"].any()
    assert not ledger["volume_known"].any()
    assert ledger["q"].isna().all()
    assert ledger["date"].nunique() == 2
    # Empty reference volume does not erase price facts or invent q=0.
    nov = raw.loc[:22].copy()
    nov["volume"] = np.nan
    _, nl, nm, _ = extract(mod, nov, case)
    assert np.isnan(nm["volume_reference"])
    assert nl["q"].isna().all()
    return {"flat_range_retained": True, "missing_volume_price_clock_preserved": True,
            "invalid_rows_do_not_emit_events": True, "undefined_location_is_nan": True}


def check_dual(mod):
    raw, case = fixture([(100., 115., 85., 100., 100.),
                         (100., 105., 95., 100., 100.),
                         (100., 116., 84., 100., 100.)])
    _, ledger, _, selections = extract(mod, raw, case)
    compare_oracle(ledger, independent_timeline(raw, case), selections)
    assert len(selections) == 2
    assert all(sorted(s["selected_boundaries"]) == ["lower", "upper"] for s in selections)
    assert not ledger["same_day_order_known"].any()
    assert ledger["date"].nunique() == 3
    return {"both_sides_preserved": True, "intraday_order_remains_unknown": True}


def check_recontact(mod):
    # The first three bars are wholly outside U: no false gap reset.
    raw, case = fixture([
        (112., 114., 111., 113., 100.),
        (113., 116., 112., 115., 100.),
        (115., 117., 113., 114., 100.),
        (108., 109., 105., 107., 100.),
        (109., 110., 106., 110., 100.),
        (110., 112., 109., 111., 100.),
    ])
    _, ledger, _, selections = extract(mod, raw, case)
    compare_oracle(ledger, independent_timeline(raw, case), selections)
    upper = ledger.loc[ledger["boundary"] == "upper"].reset_index(drop=True)
    assert upper["recontact_after_no_touch"].tolist() == [False, False, False, False, True, False]
    assert upper["consecutive_outside"].tolist() == [1, 2, 3, 0, 0, 1]
    assert upper.loc[4, "close_at_boundary"] and not upper.loc[4, "close_outside"]
    assert selections[1]["date"] == raw.loc[25, "date"]
    # Another side's first contact must not replace selected-side recontact.
    mixed, cm = fixture([(100., 112., 99., 111., 100.),
                         (95., 105., 85., 95., 100.),
                         (105., 113., 104., 112., 100.)])
    _, lm, _, sm = extract(mod, mixed, cm)
    assert [s["selected_boundaries"] for s in sm] == [["upper"], ["upper"]]
    assert lm.loc[lm["boundary"] == "lower", "touch"].any()
    return {"continuous_outside_not_repeated": True,
            "gap_crossing_counts_as_outside_contact_not_literal_execution": True,
            "equality_separate_from_strict_close_break": True,
            "other_side_facts_retained_without_manual_reselection": True}


def check_censor(mod):
    raw, case = fixture([(100., 112., 99., 111., 100.)]
                        + [(100., 105., 95., 100., 100.)] * 8, end_at=2)
    eligible, ledger, meta, selections = extract(mod, raw, case)
    out = mod.response_outcomes(eligible, selections, case)
    assert len(out) == 2
    one = out.loc[out["horizon"] == 1].iloc[0]
    five = out.loc[out["horizon"] == 5].iloc[0]
    assert not one["censored"] and one["available_observations"] == 1
    assert five["censored"] and five["available_observations"] == 2
    assert pd.isna(five["response_close"]) and five["response_date"] == ""
    assert five["observed_prefix_last_date"] <= case["end"]
    assert meta["window_observations"] == 3
    assert ledger["date"].max() <= case["end"]
    no, cn = fixture([(100., 105., 95., 100., 100.)] * 30)
    en, ln, mn, sn = extract(mod, no, cn)
    assert mn["window_observations"] == 21 and len(ln) == 42
    assert len(sn) == 1 and sn[0]["selection_kind"] == "no_contact"
    assert sn[0]["date"] == no.iloc[41]["date"]
    assert sn[0]["selected_boundaries"] == []
    assert mod.response_outcomes(en, sn, cn).empty
    # Requested non-observation date must advance once, without using anchor bar
    # in the prior bounds. An extreme anchor therefore cannot move its boundary.
    shifted = no.drop(index=21).reset_index(drop=True)
    shifted.loc[21, ["open", "high", "low", "close"]] = [100., 1000., 1., 100.]
    _, sl, sm, _ = extract(mod, shifted, cn)
    assert sm["effective_anchor"] == shifted.loc[21, "date"]
    assert sm["upper_boundary"] == 110 and sm["lower_boundary"] == 90
    too_short = raw.iloc[10:].copy()
    et = mod.eligible_prices(too_short)
    lt, mt = mod.case_facts(et, case)
    assert lt.empty and mt["status"] == "insufficient_prior_price_observations"
    return {"censoring_retained": True, "no_contact_not_a_future_label": True,
            "prior_excludes_anchor": True, "insufficient_history_not_replaced": True}


def check_branch(mod):
    raw, case = fixture([(100., 112., 99., 111., 100.)]
                        + [(100., 105., 95., 100., 100.)] * 8)
    altered = raw.copy()
    altered.loc[22:, ["open", "high", "low", "close", "volume"]] = [
        200., 1000., 1., 200., 100000.
    ]
    ea, la, ma, sa = extract(mod, raw, case)
    eb, lb, mb, sb = extract(mod, altered, case)
    cutoff = raw.loc[21, "date"]
    same(la.loc[la["date"] <= cutoff], lb.loc[lb["date"] <= cutoff])
    assert sa[0] == sb[0]
    oa = mod.response_outcomes(ea, [sa[0]], case)
    ob = mod.response_outcomes(eb, [sb[0]], case)
    assert not oa.equals(ob)
    # Rendering data accessor must stop at event for P/H/V, and at case-capped
    # fifth later price observation for O. No pixels or charts are generated.
    for stage in ("P", "H", "V"):
        pa, extra = mod.prefix_data(ea, ma, sa[0], case, stage)
        pb, extra_b = mod.prefix_data(eb, mb, sb[0], case, stage)
        same(pa, pb)
        assert extra == extra_b == 0 and pa.index[-1] == pd.Timestamp(cutoff)
    po, extra = mod.prefix_data(ea, ma, sa[0], case, "O")
    assert extra == 5 and po.index[-1] == ea.index[26]
    return {"identical_event_prefix_distinct_future": True,
            "future_outcomes_separate": True, "render_data_cutoffs_checked": True}


def check_real(mod, root, protocol):
    manifest = json.loads((root / "inputs/manifest.json").read_text())
    masks = json.loads((root / "inputs/observation-mask-addendum.json").read_text())
    exclude = {s["symbol"]: s["exclude_price_dates"] for s in masks["series"]}
    sources = {}
    for entry in manifest["series"]:
        source = root / "inputs" / entry["output"]
        assert sha256(source) == entry["output_sha256"]
        sources[entry["symbol"]] = pd.read_csv(source)
    prefix_count = 0
    for case in protocol["cases"]:
        raw = sources[case["symbol"]]
        excluded = exclude[case["symbol"]]
        expected = independent_eligible(raw, excluded)
        eligible = mod.eligible_prices(raw, case["symbol"], excluded)
        assert eligible.index.strftime("%Y-%m-%d").tolist() == expected["date"].tolist()
        ledger, meta = mod.case_facts(eligible, case, protocol["lookback"], protocol["window"])
        selections = mod.select_events(ledger)
        oracle = independent_timeline(expected, case)
        assert oracle is not None and meta["status"] == "ready"
        compare_oracle(ledger, oracle, selections)
        assert meta["upper_boundary"] == oracle["bounds"]["upper"]
        assert meta["lower_boundary"] == oracle["bounds"]["lower"]
        assert meta["prior_start_date"] == oracle["prior"].iloc[0]["date"]
        assert meta["prior_end_date"] == oracle["prior"].iloc[-1]["date"]
        assert meta["effective_anchor"] == oracle["window"].iloc[0]["date"]
        assert meta["window_end_date"] == oracle["window"].iloc[-1]["date"]
        assert ledger["date"].nunique() == len(oracle["window"]) <= 21
        assert len(ledger) == 2 * len(oracle["window"])
        known = oracle["prior"]["volume"]
        known = known.loc[np.isfinite(known) & known.gt(0)]
        assert np.isclose(meta["volume_reference"], known.median(), equal_nan=True)
        # Every observed prefix, including before a later first/recontact.
        for cutoff in oracle["window"]["date"]:
            before = raw.loc[raw["date"] <= cutoff]
            ep = mod.eligible_prices(before, case["symbol"], excluded)
            lp, mp = mod.case_facts(ep, case)
            same(ledger.loc[ledger["date"] <= cutoff], lp)
            assert selection_pairs(mod.select_events(lp)) == [
                (date, sides) for date, sides in selection_pairs(selections) if date <= cutoff
            ]
            for key in ("upper_boundary", "lower_boundary", "volume_reference",
                        "volume_reference_known_count", "prior_start_date", "prior_end_date"):
                assert mp[key] == meta[key] or (pd.isna(mp[key]) and pd.isna(meta[key]))
            prefix_count += 1
        shuffled = raw.copy()
        positive = np.isfinite(shuffled["volume"]) & shuffled["volume"].gt(0)
        shuffled.loc[positive, "volume"] = shuffled.loc[positive, "volume"].to_numpy()[::-1]
        ev = mod.eligible_prices(shuffled, case["symbol"], excluded)
        assert ev.index.equals(eligible.index)
        lv, _ = mod.case_facts(ev, case)
        same(ledger[price_columns(ledger)], lv[price_columns(lv)])
        sv = mod.select_events(lv)
        assert selections == sv
        outcomes = mod.response_outcomes(eligible, selections, case)
        same(outcomes, mod.response_outcomes(ev, sv, case))
        # Check every response against its actual valid-observation position,
        # without disclosing event/date/outcome details in this validation report.
        for row in outcomes.to_dict("records"):
            event_i = eligible.index.get_loc(pd.Timestamp(row["event_date"]))
            future = eligible.iloc[event_i + 1:].loc[:case["end"]]
            available = min(row["horizon"], len(future))
            assert row["available_observations"] == available
            assert row["censored"] == (available < row["horizon"])
            if row["censored"]:
                assert pd.isna(row["response_close"]) and not row["response_date"]
            else:
                endpoint = future.iloc[row["horizon"] - 1]
                assert row["response_close"] == endpoint["close"]
                assert row["response_date"] == future.index[row["horizon"] - 1].strftime("%Y-%m-%d")
                assert row["response_date"] <= case["end"]
    return {"cases_checked": len(protocol["cases"]),
            "source_hashes_checked": len(sources),
            "prefix_checks": prefix_count,
            "volume_reorder_price_ledger_checks": len(protocol["cases"]),
            "response_clock_and_censoring_checked": True,
            "real_event_details_deliberately_omitted_until_review_locks": True}


if __name__ == "__main__":
    raise SystemExit(main())

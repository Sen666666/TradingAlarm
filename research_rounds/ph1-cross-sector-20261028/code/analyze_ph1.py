"""Frozen descriptive PH1 factorial analysis; never executes a trading account.

Only run after explicit human/parent authorization and admission/accounting gates.
The output directory is exclusive, so a failed analysis remains available.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import math

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
O = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "research_rounds/s-amount-cross-sector-20261028"
OUT = O / "analysis-ph1"
SECTORS = ("TECH", "DRUG")
MODES = ("A_E0", "A_F", "A_PH", "R_E0", "R_F", "R_PH")
SCENARIOS = ("base", "cost2", "delay1")
PAIR_DEFINITIONS = (
    ("risk_sizing", "A_E0", "R_E0"),
    ("risk_sizing", "A_F", "R_F"),
    ("risk_sizing", "A_PH", "R_PH"),
    ("stage_increment_over_full_F", "A_F", "A_PH"),
    ("stage_increment_over_full_F", "R_F", "R_PH"),
    ("full_F_over_E0", "A_E0", "A_F"),
    ("full_F_over_E0", "R_E0", "R_F"),
    ("stage_over_E0", "A_E0", "A_PH"),
    ("stage_over_E0", "R_E0", "R_PH"),
)
METRICS = ("net_return", "max_drawdown", "net_profit", "mean_exposure", "fees",
           "closed", "tail_profit", "ordinary_profit", "open_profit",
           "all_closed_losses", "buy_fills")


def read(path):
    return json.loads(Path(path).read_text())


def native(value):
    if isinstance(value, dict):
        return {str(k): native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [native(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    return value


def save(path, value):
    with Path(path).open("x") as f:
        json.dump(native(value), f, ensure_ascii=False, indent=2, allow_nan=False)


def rows(path):
    with gzip.open(path, "rt") as f:
        return [json.loads(line) for line in f]


def aid(scenario):
    return f"S__S0_{scenario}"


def selected(frame, scenario):
    return frame.loc[frame.account.eq(aid(scenario))]


def boolean_column(frame, name):
    s = frame[name]
    if pd.api.types.is_bool_dtype(s):
        return s
    assert set(s.dropna()) <= {"True", "False"}, (name, "not Boolean")
    return s.eq("True")


def load_run(sector, mode, prior_version=None):
    path = (PRIOR / sector / prior_version) if prior_version else O / sector / mode
    accounting = read(path / "analysis/accounting.json")
    assert accounting["passed"] and float(accounting["max_nav_difference"]) == 0, path
    summary = pd.read_csv(path / "analysis/summary.csv")
    assert len(summary) == 3 and set(summary.scenario) == set(SCENARIOS), path
    campaigns = pd.read_csv(path / "analysis/campaigns.csv")
    for k in ("closed", "tail_closed"):
        campaigns[k] = boolean_column(campaigns, k)
    return dict(path=path, summary=summary, campaigns=campaigns,
                stocks=pd.read_csv(path / "analysis/stocks.csv"),
                curves=pd.read_csv(path / "analysis/curves.csv"),
                daily=rows(path / "accounts-v2/daily.jsonl.gz"),
                decisions=rows(path / "accounts-v2/decisions.jsonl.gz"),
                accounts={s: read(path / "accounts-v2" / f"{aid(s)}.json") for s in SCENARIOS})


def day_map(run, scenario, kind="daily"):
    return {r["at"][:10]: r for r in run[kind] if r["account"] == aid(scenario)}


def risk_map(run, scenario):
    return {r["at"][:10]: r for r in run["accounts"][scenario]["audit_log"]
            if r["kind"] == "risk_checkpoint"}


def entry_key(symbol, at):
    """Campaign CSV uses a space; runner ISO timestamps use T."""
    return symbol, pd.Timestamp(at).isoformat()


def cost_row(sector, mode, scenario, summary, campaigns):
    closed = campaigns.loc[campaigns.closed]
    tail = closed.loc[closed.tail_closed]
    ordinary = closed.loc[~closed.tail_closed]
    opened = campaigns.loc[~campaigns.closed]
    fees = float((campaigns.buy_fees + campaigns.sell_fees).sum())
    assert abs(fees - summary.fees) < 1e-5, (sector, mode, scenario, "fees")
    total = float(tail.net_pnl.sum() + ordinary.net_pnl.sum() + opened.net_pnl.sum())
    assert abs(total - summary.net_profit) < 1e-5, (sector, mode, scenario, "cycle pnl")
    loss = float(-closed.loc[closed.net_pnl.lt(0), "net_pnl"].sum())
    return dict(sector=sector, mode=mode, scenario=scenario,
                closed_cycles=len(closed), negative_closed_cycles=int(closed.net_pnl.lt(0).sum()),
                tail_cycles=len(tail), tail_net_pnl=tail.net_pnl.sum(),
                ordinary_closed_net_pnl=ordinary.net_pnl.sum(),
                all_negative_closed_loss=loss,
                ordinary_positive_net_pnl=ordinary.loc[ordinary.net_pnl.gt(0), "net_pnl"].sum(),
                open_net_pnl=opened.net_pnl.sum(),
                open_marked_losses=-opened.loc[opened.net_pnl.lt(0), "net_pnl"].sum(),
                all_fees=fees, net_profit=total,
                tail_over_all_closed_losses=float(tail.net_pnl.sum()) / loss if loss else None)


def cycle_phase_rows(sector, mode, scenario, run, campaigns):
    """Join phase records to every actual campaign, never only successful M cases.

    Missing optional Loss_fill stays null with an explicit availability flag.
    Phase PnL buckets are descriptive cohort totals, not causal stage attribution.
    """
    logs = run["accounts"][scenario]["audit_log"]
    starts = [r for r in logs if r["kind"] == "ph_cycle_start"]
    by_entry = {entry_key(r["sid"], r["entry_at"]): r for r in starts}
    assert len(by_entry) == len(starts), (sector, mode, scenario, "duplicate cycle start")
    checkpoints = {}
    ends = {}
    fill_updates = {}
    contracts = {r["order_id"]: r for r in logs if r["kind"] == "entry_contract"}
    filled_contracts = {}
    for row in logs:
        if row["kind"] == "ph_checkpoint":
            checkpoints.setdefault(row["cycle_id"], []).append(row)
        elif row["kind"] == "ph_cycle_fill":
            fill_updates.setdefault(row["cycle_id"], []).append(row)
        elif row["kind"] == "ph_cycle_end":
            assert row["cycle_id"] not in ends, ("duplicate cycle end", row)
            ends[row["cycle_id"]] = row
        elif row["kind"] == "fill" and row["receipt"]["side"] == "buy":
            receipt = row["receipt"]
            filled_contracts[entry_key(receipt["security_id"], receipt["at"])] = contracts[row["order_id"]]
    if mode != "A_E0":
        assert len(starts) == len(campaigns), (sector, mode, scenario, "missing managed cycles")
    else:
        assert not starts and not checkpoints, "A_E0 remains the exact prior control"
    if mode == "R_E0":
        assert not checkpoints, "R_E0 has E0 lifecycle records, no stage checkpoints"
    daily_dates = sorted(day_map(run, scenario))
    out = []
    for _, c in campaigns.iterrows():
        key = entry_key(c.symbol, c.entry_at)
        start = by_entry.get(key)
        contract = filled_contracts.get(key)
        if mode != "A_E0":
            assert start is not None, (sector, mode, scenario, "unmatched cycle", key)
        assert contract is not None, (sector, mode, scenario, "unmatched entry contract", key)
        history = sorted(checkpoints.get(start["cycle_id"], []), key=lambda r: r["at"]) if start else []
        mature = [r for r in history if r.get("mature")]
        assert all(bool(r["mature"]) == bool(r["handoff"]) for r in history)
        assert len(mature) <= 1, (sector, mode, scenario, "multiple M events", key)
        if not mode.endswith("PH"):
            assert not mature, (sector, mode, scenario, "M outside PH", key)
        first_m = mature[0] if mature else None
        exiting = [r for r in history if r.get("exit_reason")]
        first_exit = exiting[0] if exiting else None
        bridge = [r for r in history if r.get("phase_after") == "BRIDGE"]
        trend = [r for r in history if r.get("phase_after") == "TREND"]
        end = ends.get(start["cycle_id"]) if start else None
        if mode != "A_E0" and c.closed:
            assert end is not None, (sector, mode, scenario, "missing cycle end", key)
        r_budget = float(start["R_a"] if start else contract["risk_budget"])
        # A runner-provided total for all actual buys at frozen initial support.
        updates = sorted(fill_updates.get(start["cycle_id"], []), key=lambda r: r["at"]) if start else []
        loss_record = end or (updates[-1] if updates else start)
        loss_fill = float(loss_record["Loss_fill"]) if loss_record is not None else None
        negative = max(0., -float(c.net_pnl))
        entry_day = str(c.entry_at)[:10]
        m_day = first_m["at"][:10] if first_m else None
        out.append(dict(sector=sector, mode=mode, scenario=scenario, symbol=c.symbol,
                        name=c["name"], entry_at=c.entry_at, exit_at=c.exit_at,
                        closed=bool(c.closed), net_pnl=c.net_pnl, tail_closed=bool(c.tail_closed),
                        buy_gross=c.buy_gross, all_fees=float(c.buy_fees+c.sell_fees),
                        phase_records_available=start is not None,
                        cycle_id=start["cycle_id"] if start else None,
                        initial_support=start["E_entry"] if start else contract["floor_signal"],
                        R_a=r_budget, Loss_fill=loss_fill, Loss_fill_available=loss_fill is not None,
                        Loss_fill_source="end" if end else "last_partial_fill" if updates else "start" if start else None,
                        partial_fill_updates=len(updates),
                        buy_notional_over_entry_nav=float(c.buy_gross)/(100*r_budget) if r_budget else None,
                        initial_nominal_budget_use=loss_fill/r_budget if r_budget and loss_fill is not None else None,
                        negative_closed_loss_over_R=negative/r_budget if c.closed and r_budget else None,
                        realized_loss_exceeds_R=bool(c.closed and r_budget and negative > r_budget + 1e-8),
                        M_observed=first_m is not None, M_at=first_m["at"] if first_m else None,
                        M_direct_trend=bool(first_m and first_m.get("phase_after") == "TREND"),
                        ever_bridge=bool(bridge), bridge_checkpoint_days=len({r["at"][:10] for r in bridge}),
                        ever_trend=bool(trend), first_trend_at=trend[0]["at"] if trend else None,
                        entry_to_M_observations=sum(entry_day <= d <= m_day for d in daily_dates) if m_day else None,
                        exit_requested_at=first_exit["at"] if first_exit else None,
                        exit_phase=first_exit.get("phase_before") if first_exit else None,
                        exit_reason=first_exit.get("exit_reason") if first_exit else None,
                        no_M_closed=bool(c.closed and not first_m),
                        no_M_negative_closed=bool(c.closed and not first_m and c.net_pnl < 0),
                        checkpoint_count=len(history)))
    return out


def phase_summary(frame):
    out = []
    for key, f in frame.groupby(["sector", "mode", "scenario"], sort=False):
        sector, mode, scenario = key
        closed = f.loc[f.closed]
        no_m = closed.loc[~closed.M_observed]
        has_m = closed.loc[closed.M_observed]
        is_ph = mode.endswith("PH")
        out.append(dict(sector=sector, mode=mode, scenario=scenario,
                        campaigns=len(f), phase_records=int(f.phase_records_available.sum()),
                        PH_mechanism_applicable=is_ph,
                        M_cycles=int(f.M_observed.sum()) if is_ph else None,
                        M_coverage=float(f.M_observed.mean()) if is_ph and len(f) else None,
                        direct_trend_cycles=int(f.M_direct_trend.sum()) if is_ph else None,
                        bridge_cycles=int(f.ever_bridge.sum()) if is_ph else None,
                        reached_trend_cycles=int(f.ever_trend.sum()) if is_ph else None,
                        bridge_checkpoint_days=int(f.bridge_checkpoint_days.sum()) if is_ph else None,
                        entry_to_M_median_observations=f.entry_to_M_observations.median() if is_ph else None,
                        no_M_closed_cycles=len(no_m) if is_ph else None,
                        no_M_negative_closed_cycles=int(no_m.net_pnl.lt(0).sum()) if is_ph else None,
                        no_M_closed_net_pnl=no_m.net_pnl.sum() if is_ph else None,
                        no_M_all_negative_closed_loss=-no_m.loc[no_m.net_pnl.lt(0), "net_pnl"].sum() if is_ph else None,
                        no_M_all_fees=no_m.all_fees.sum() if is_ph else None,
                        M_closed_net_pnl=has_m.net_pnl.sum() if is_ph else None,
                        M_closed_negative_loss=-has_m.loc[has_m.net_pnl.lt(0), "net_pnl"].sum() if is_ph else None,
                        bridge_without_trend_closed_cycles=int((closed.ever_bridge & ~closed.ever_trend).sum()) if is_ph else None,
                        bridge_without_trend_closed_net_pnl=closed.loc[closed.ever_bridge & ~closed.ever_trend, "net_pnl"].sum() if is_ph else None,
                        buy_notional_over_entry_nav_median=f.buy_notional_over_entry_nav.median(),
                        initial_nominal_budget_use_median=f.initial_nominal_budget_use.median(),
                        initial_Loss_fill_available=int(f.Loss_fill_available.sum()),
                        realized_loss_exceeds_R=int(f.realized_loss_exceeds_R.sum()),
                        negative_closed_loss_R_max=closed.negative_closed_loss_over_R.max(),
                        negative_closed_loss_R_median=closed.loc[closed.net_pnl.lt(0), "negative_closed_loss_over_R"].median()))
    return out


def main():
    assert read(O / "admission.json")["passed"], "admission gate"
    data = {(s, m): load_run(s, m) for s in SECTORS for m in MODES}
    refs = {(s, v): load_run(s, v, v) for s in SECTORS for v in ("AMT", "OLD")}
    OUT.mkdir(exist_ok=False)
    summaries, costs, phases, risk_rows, risk_paths = [], [], [], [], []
    winners, coverage, pairs, stock_deltas, checks, interactions, paths = [], [], [], [], [], [], []
    reference_rows, phase_events = [], []
    for sector in SECTORS:
        # Pre-existing S-AMT1 base, not PH1 outcomes, determines winner reference.
        ref = refs[sector, "AMT"]
        tails = selected(ref["campaigns"], "base").loc[lambda f: f.tail_closed]
        ref_dates = sorted(day_map(ref, "base"))
        fixed = [(i, c, [d for d in ref_dates if str(c.entry_at)[:10] <= d < str(c.exit_at)[:10]])
                 for i, (_, c) in enumerate(tails.iterrows())]
        fixed_symbols = set(tails.symbol)
        for version in ("OLD", "AMT"):
            for scenario in SCENARIOS:
                r = selected(refs[sector, version]["summary"], scenario).iloc[0]
                reference_rows.append(dict(sector=sector, reference=f"prior_{version}", **r.to_dict()))
        for mode in MODES:
            run = data[sector, mode]
            for scenario in SCENARIOS:
                s = selected(run["summary"], scenario).iloc[0]
                c = selected(run["campaigns"], scenario)
                summaries.append(dict(sector=sector, mode=mode, **s.to_dict()))
                costs.append(cost_row(sector, mode, scenario, s, c))
                phases.extend(cycle_phase_rows(sector, mode, scenario, run, c))
                rm = risk_map(run, scenario)
                dm = day_map(run, scenario)
                transitions = [r for r in rm.values() if r.get("event")]
                risk_paths.append(dict(sector=sector, mode=mode, scenario=scenario, transitions=transitions))
                risk_rows.append(dict(sector=sector, mode=mode, scenario=scenario,
                                      risk_checkpoints=len(rm), active_days=sum(bool(r["on"]) for r in rm.values()),
                                      inactive_days=sum(not bool(r["on"]) for r in rm.values()),
                                      pause_count=sum(r.get("event") == "pause" for r in rm.values()),
                                      mean_exposure=s.mean_exposure,
                                      mean_positive_holdings=np.mean([sum(int(q)>0 for q in r["positions"].values()) for r in dm.values()])))
                possible, held = set(), set()
                for wid, w, days in fixed:
                    h = [d for d in days if int(dm.get(d, {}).get("positions", {}).get(w.symbol, 0)) > 0]
                    possible.update((w.symbol, d) for d in days)
                    held.update((w.symbol, d) for d in h)
                    winners.append(dict(sector=sector, mode=mode, scenario=scenario, window_id=wid,
                                        symbol=w.symbol, name=w["name"], reference_entry=w.entry_at,
                                        reference_exit=w.exit_at, possible_days=len(days), held_days=len(h)))
                coverage.append(dict(sector=sector, mode=mode, scenario=scenario,
                                     reference="prior_AMT_base", fixed_tail_windows=len(fixed),
                                     fixed_tail_stocks=len(fixed_symbols), possible_stock_days=len(possible),
                                     held_stock_days=len(held), held_fraction=len(held)/len(possible) if possible else None,
                                     fixed_tail_stocks_full_period_net=c.loc[c.symbol.isin(fixed_symbols), "net_pnl"].sum()))
                # Preserve all events, including failed trials and unfinished bridge.
                phase_events.append(dict(sector=sector, mode=mode, scenario=scenario,
                                         events=[r for r in run["accounts"][scenario]["audit_log"] if r["kind"].startswith("ph_")]))
        for scenario in SCENARIOS:
            for family, before, after in PAIR_DEFINITIONS:
                a, b = data[sector, before], data[sector, after]
                sa, sb = (selected(x["summary"], scenario).iloc[0] for x in (a, b))
                pairs.append(dict(sector=sector, scenario=scenario, family=family, before=before, after=after,
                                  **{f"before_{k}": sa[k] for k in METRICS},
                                  **{f"after_{k}": sb[k] for k in METRICS},
                                  **{f"delta_{k}": sb[k]-sa[k] for k in METRICS}))
                aa, bb = (selected(x["stocks"], scenario).set_index("symbol") for x in (a, b))
                local = []
                for sid in sorted(set(aa.index) | set(bb.index)):
                    av = float(aa.loc[sid, "net_profit"]) if sid in aa.index else 0.
                    bv = float(bb.loc[sid, "net_profit"]) if sid in bb.index else 0.
                    name = aa.loc[sid, "name"] if sid in aa.index else bb.loc[sid, "name"]
                    item = dict(sector=sector, scenario=scenario, family=family, before=before, after=after,
                                symbol=sid, name=name, before_net=av, after_net=bv, delta_net=bv-av,
                                prior_AMT_fixed_tail_stock=sid in fixed_symbols)
                    local.append(item); stock_deltas.append(item)
                delta_sum = sum(r["delta_net"] for r in local)
                error = delta_sum - (sb.net_profit-sa.net_profit)
                assert abs(error) < 1e-5, (sector, scenario, before, after, "stock delta", error)
                checks.append(dict(sector=sector, scenario=scenario, before=before, after=after,
                                   stock_delta_sum=delta_sum, account_net_delta=sb.net_profit-sa.net_profit, difference=error))
                adm, bdm = day_map(a, scenario), day_map(b, scenario)
                assert set(adm) == set(bdm), (sector, scenario, "daily clocks")
                first_fin = next((d for d in sorted(adm) if any(adm[d][k] != bdm[d][k] for k in ("nav", "positions", "available"))), None)
                ad, bd = day_map(a, scenario, "decisions"), day_map(b, scenario, "decisions")
                first_dec = next((d for d in sorted(ad) if any(ad[d][k] != bd[d][k] for k in ("accepted", "exits"))), None)
                extremes = sorted(local, key=lambda r: r["delta_net"])
                selected_symbols = list(dict.fromkeys(r["symbol"] for r in extremes[:3]+extremes[-3:]))
                paths.append(dict(sector=sector, scenario=scenario, before=before, after=after,
                                  first_financial_divergence=first_fin, first_admission_or_exit_divergence=first_dec,
                                  first_decision_snapshots={before: ad.get(first_dec), after: bd.get(first_dec)},
                                  representative_campaigns={m: selected(data[sector, m]["campaigns"], scenario).loc[
                                      lambda f: f.symbol.isin(selected_symbols)].to_dict("records") for m in (before, after)}))
            def metric(mode, key):
                return selected(data[sector, mode]["summary"], scenario).iloc[0][key]
            interactions.append(dict(sector=sector, scenario=scenario,
                                     **{f"difference_in_differences_{k}": (metric("R_PH", k)-metric("R_F", k))-(metric("A_PH", k)-metric("A_F", k))
                                        for k in ("net_profit", "net_return", "max_drawdown", "mean_exposure")}))
    phase_frame = pd.DataFrame(phases)
    tables = {"summary": summaries, "cost-decomposition": costs, "paired-summary": pairs,
              "stock-differences": stock_deltas, "cycle-phases": phases,
              "phase-summary": phase_summary(phase_frame), "risk-exposure": risk_rows,
              "fixed-winner-windows": winners, "fixed-winner-coverage": coverage,
              "descriptive-interactions": interactions, "prior-reference-summary": reference_rows}
    for name, table in tables.items():
        pd.DataFrame(table).to_csv(OUT / f"{name}.csv", index=False)
    save(OUT / "paired-attribution-checks.json", dict(passed=True, comparisons=checks))
    save(OUT / "risk-transitions.json", risk_paths)
    save(OUT / "phase-events.json", phase_events)
    save(OUT / "path-contexts.json", paths)
    save(OUT / "definitions.json", DEFINITIONS)
    graphs(data)
    verify_outputs(data, tables, checks)
    print(pd.DataFrame(summaries)[["sector", "mode", "scenario", "net_return", "max_drawdown", "mean_exposure"]].to_string(index=False))


def verify_outputs(data, tables, checks):
    """Independent output shape/coverage/reconciliation gate, no account actions.

    Reopen emitted CSVs so successful in-memory calculation alone cannot pass.
    This gate does not replace the independent trading/account/prefix audits.
    """
    expected_paths = {(s, m, c) for s in SECTORS for m in MODES for c in SCENARIOS}
    expected_pairs = {(s, c, f, a, b) for s in SECTORS for c in SCENARIOS
                      for f, a, b in PAIR_DEFINITIONS}
    assert len(expected_paths) == 36 and len(expected_pairs) == 54
    frames = {name: pd.read_csv(OUT / f"{name}.csv") for name in tables}
    required = {
        "summary": {"sector", "mode", "scenario", "net_return", "max_drawdown", "net_profit", "mean_exposure", "fees"},
        "cost-decomposition": {"sector", "mode", "scenario", "tail_net_pnl", "ordinary_closed_net_pnl", "open_net_pnl", "all_negative_closed_loss", "all_fees", "net_profit"},
        "paired-summary": {"sector", "scenario", "family", "before", "after", "delta_net_profit", "delta_net_return", "delta_max_drawdown"},
        "stock-differences": {"sector", "scenario", "family", "before", "after", "symbol", "before_net", "after_net", "delta_net"},
        "cycle-phases": {"sector", "mode", "scenario", "symbol", "entry_at", "closed", "net_pnl", "all_fees", "R_a", "Loss_fill", "Loss_fill_available", "M_observed", "ever_bridge", "ever_trend", "no_M_closed", "exit_reason"},
        "phase-summary": {"sector", "mode", "scenario", "campaigns", "M_cycles", "bridge_cycles", "no_M_closed_cycles", "initial_Loss_fill_available"},
        "risk-exposure": {"sector", "mode", "scenario", "active_days", "inactive_days", "mean_exposure"},
        "fixed-winner-windows": {"sector", "mode", "scenario", "window_id", "symbol", "possible_days", "held_days"},
        "fixed-winner-coverage": {"sector", "mode", "scenario", "reference", "possible_stock_days", "held_stock_days", "held_fraction"},
        "descriptive-interactions": {"sector", "scenario", "difference_in_differences_net_profit"},
        "prior-reference-summary": {"sector", "reference", "scenario", "net_return", "max_drawdown"},
    }
    table_evidence = {}
    for name, columns in required.items():
        assert columns <= set(frames[name].columns), (name, "required fields", columns-set(frames[name].columns))
        assert len(frames[name]) == len(tables[name]), (name, "roundtrip rows")
        table_evidence[name] = dict(rows=len(frames[name]), required_columns=sorted(columns), columns_present=True)
    for name in ("summary", "cost-decomposition", "phase-summary", "risk-exposure", "fixed-winner-coverage"):
        frame = frames[name]
        keys = list(frame[["sector", "mode", "scenario"]].itertuples(index=False, name=None))
        assert len(keys) == 36 and len(set(keys)) == 36 and set(keys) == expected_paths, (name, "36 unique paths")
    pair_frame = frames["paired-summary"]
    pair_keys = list(pair_frame[["sector", "scenario", "family", "before", "after"]].itertuples(index=False, name=None))
    assert len(pair_keys) == 54 and len(set(pair_keys)) == 54 and set(pair_keys) == expected_pairs
    assert len(checks) == 54 and max(abs(r["difference"]) for r in checks) < 1e-5
    assert len(frames["descriptive-interactions"]) == 6
    assert len(frames["prior-reference-summary"]) == 12
    assert set(frames["fixed-winner-coverage"].reference) == {"prior_AMT_base"}
    coverage = frames["fixed-winner-coverage"]
    assert (coverage.held_stock_days <= coverage.possible_stock_days).all()
    windows = frames["fixed-winner-windows"]
    assert (windows.held_days <= windows.possible_days).all() and windows.held_days.ge(0).all()
    for col in ("net_return", "max_drawdown", "net_profit", "mean_exposure", "fees"):
        assert np.isfinite(frames["summary"][col]).all(), ("summary finite", col)
    cycle = frames["cycle-phases"]
    for col in ("closed", "M_observed", "ever_bridge", "ever_trend", "Loss_fill_available"):
        cycle[col] = boolean_column(cycle, col)
    cycle_keys = [(r.sector, r.mode, r.scenario, *entry_key(r.symbol, r.entry_at)) for r in cycle.itertuples()]
    assert len(cycle_keys) == len(set(cycle_keys)), "duplicate campaign keys"
    assert cycle.R_a.gt(0).all() and np.isfinite(cycle.R_a).all(), "frozen R_a metadata"
    expected_cycles = sum(len(run["campaigns"]) for run in data.values())
    assert len(cycle) == expected_cycles, "all 36 paths' campaigns included"
    tracked = cycle["mode"].ne("A_E0")
    assert cycle.loc[tracked, "Loss_fill_available"].all(), "Loss_fill missing for managed cycles"
    assert cycle.loc[tracked, "Loss_fill"].ge(0).all(), "negative nominal loss"
    assert not cycle.loc[~tracked, "Loss_fill_available"].any(), "A_E0 exact control has no added loss log"
    ph = cycle["mode"].str.endswith("PH")
    assert not (cycle.loc[ph, "ever_bridge"] & ~cycle.loc[ph, "M_observed"]).any()
    assert not cycle.loc[~ph, "M_observed"].any()
    path_checks = []
    sums = frames["summary"].set_index(["sector", "mode", "scenario"])
    cost = frames["cost-decomposition"].set_index(["sector", "mode", "scenario"])
    for key in sorted(expected_paths):
        sub = cycle.loc[cycle.sector.eq(key[0]) & cycle["mode"].eq(key[1]) & cycle.scenario.eq(key[2])]
        account_profit = float(sums.loc[key, "net_profit"])
        cycle_error = float(sub.net_pnl.sum())-account_profit
        fee_error = float(sub.all_fees.sum())-float(sums.loc[key, "fees"])
        d = cost.loc[key]
        cost_error = float(d.tail_net_pnl+d.ordinary_closed_net_pnl+d.open_net_pnl)-account_profit
        loss_error = float(-sub.loc[sub.closed & sub.net_pnl.lt(0), "net_pnl"].sum())-float(d.all_negative_closed_loss)
        assert max(abs(cycle_error), abs(fee_error), abs(cost_error), abs(loss_error)) < 1e-5, (key, "cycle/cost reconciliation")
        source_count = len(selected(data[key[0], key[1]]["campaigns"], key[2]))
        assert len(sub) == source_count, (key, "campaign coverage")
        path_checks.append(dict(sector=key[0], mode=key[1], scenario=key[2], campaigns=len(sub),
                                cycle_pnl_difference=cycle_error, fee_difference=fee_error,
                                decomposition_difference=cost_error, negative_loss_difference=loss_error))
    stock_rechecks = []
    stocks = frames["stock-differences"]
    for row in pair_frame.itertuples():
        sub = stocks.loc[stocks.sector.eq(row.sector) & stocks.scenario.eq(row.scenario) & stocks.family.eq(row.family)
                         & stocks.before.eq(row.before) & stocks.after.eq(row.after)]
        assert not sub.symbol.duplicated().any(), (row.sector, row.before, row.after, "duplicate stock")
        error = float(sub.delta_net.sum())-float(row.delta_net_profit)
        assert abs(error) < 1e-5, (row.sector, row.scenario, row.before, row.after, "persisted stock delta", error)
        stock_rechecks.append(dict(sector=row.sector, scenario=row.scenario, family=row.family,
                                   before=row.before, after=row.after, difference=error))
    artifacts = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            assert path.stat().st_size > 0, path
            artifacts[path.name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    assert {"tech-equity-drawdown.png", "drug-equity-drawdown.png"} <= set(artifacts)
    save(OUT / "verification.json", dict(passed=True, completed_at_utc=datetime.now(timezone.utc).isoformat(),
         scope="Output completeness and accounting/attribution checks; independent economic/causal audits remain separate",
         paths=36, pairs=54, campaign_rows=expected_cycles, tables=table_evidence,
         path_checks=path_checks, stock_delta_checks=stock_rechecks,
         max_stock_difference=max(abs(r["difference"]) for r in stock_rechecks),
         required_fields_passed=True, phase_log_contract_passed=True, figures_generated=True,
         actual_visual_review_pending=True, artifacts=artifacts,
         analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


DEFINITIONS = {
    "purpose": "Separate risk sizing from PH1 incremental effect over full F, without parameter selection",
    "period": "2024-01-02 through 2026-10-27; one common initial start",
    "paired_design": PAIR_DEFINITIONS,
    "primary_stage_question": "Within A and within R separately compare PH against full F, including normal and delay",
    "sizing_question": "Within each identical protection compare R against A; do not credit lower exposure entirely to protection quality",
    "fixed_winners": "Prior S-AMT1 base closed cycles >=30%, fixed before PH1 outcomes; old S shown as reference only",
    "coverage": "End-of-day positive quantity in fixed [entry date, final exit date), deduplicated symbol/date",
    "all_negative_closed_loss": "All losing closed cycles, including fees; not only initial failures",
    "fees": "Already in net PnL; separate disclosure must not be subtracted again",
    "M_groups": "All cycles including no-M failures; M-conditioned profits describe cohorts, not causality",
    "bridge_days": "Number of distinct ph_checkpoint dates whose resulting phase is BRIDGE",
    "initial_R": "Frozen 1% decision NAV; distinct from actual-filled nominal Loss_fill; neither guarantees realized loss",
    "open_cycles": "Marked separately from realized closed-cycle losses",
    "interaction": "Descriptive difference-in-differences of complete path metrics, not an additive isolated causal effect",
    "causality": "Check previous holdings, resources, phase exit and actual ACT state before blaming rank or a current buy signal",
    "no_promotion_by_maximum_return": True,
    "no_new_start_or_parameter_search": True,
}


def graphs(data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    colors = {"E0": "#747474", "F": "#bc6415", "PH": "#14639c"}
    for sector in SECTORS:
        fig, axes = plt.subplots(2, 3, figsize=(17, 8), sharex="col")
        for j, scenario in enumerate(SCENARIOS):
            for mode in MODES:
                frame = selected(data[sector, mode]["curves"], scenario).sort_values("date")
                dates = pd.to_datetime(frame.date, utc=True)
                nav = frame.nav.astype(float)
                color = colors[mode.split("_")[1]]
                style = "-" if mode.startswith("A") else "--"
                axes[0, j].plot(dates, nav/1_000_000, label=mode, color=color, linestyle=style, linewidth=1.3)
                axes[1, j].plot(dates, 100*frame.drawdown.astype(float), label=mode, color=color, linestyle=style, linewidth=1.3)
            axes[0, j].set_title(scenario)
            axes[0, j].legend(fontsize=8, ncol=2)
            axes[0, j].set_ylabel("净值 / 初始100万元")
            axes[1, j].set_ylabel("回撤 %")
            for ax in axes[:, j]:
                ax.grid(alpha=.2)
                ax.tick_params(axis="x", rotation=20)
        fig.suptitle(f"{sector} | 同 S-AMT1：金额仓位 A / 风险仓位 R × E0 / F / PH1")
        fig.tight_layout()
        fig.savefig(OUT / f"{sector.lower()}-equity-drawdown.png", dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()

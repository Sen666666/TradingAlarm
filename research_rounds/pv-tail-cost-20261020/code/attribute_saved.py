"""Read-only attribution of saved episodes; never imports an account/model runner.

All return labels, quantities, fees and executions remain the saved ones.
MFE groups are the protocol's diagnostic bins, not trading rules.
"""
from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ROUND = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "TradingAlarm/research/results/pv-event-structure-20261020"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROUND/"attribution",
                    help="New output directory; finalized output is never overwritten.")
OUT = parser.parse_args().output.resolve()
if (OUT/"summary.json").exists():
    raise SystemExit(f"Refusing to overwrite finalized attribution: {OUT}; use --output with a new directory.")
OUT.mkdir(parents=True, exist_ok=True)
INITIAL = 1_000_000.0
INPUTS = {}


def file(name):
    path = SOURCE / name
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def read_json(name):
    return json.loads(file(name).read_text())


def band(v):
    if not np.isfinite(v):
        return "missing"
    if v <= 1e-12:
        return "0"
    if v < .05:
        return "(0,5%)"
    if v < .15:
        return "[5%,15%)"
    return ">=15%"


def summarize(frame, keys):
    return frame.groupby(keys, dropna=False, observed=True).agg(
        episodes=("id", "size"), net_pnl=("pnl", "sum"),
        gross_same_labels=("gross_same_labels", "sum"), fees=("fees", "sum"),
        buy_cash=("buy_cash", "sum"), median_return=("ret", "median"),
        median_close_mfe=("signal_close_mfe", "median"),
        median_close_mae=("signal_close_mae", "median"),
        median_sessions=("sessions", "median"),
        median_calendar_days=("calendar_days", "median"),
        median_gap_sessions=("prior_exit_to_entry_sessions", "median"),
    ).reset_index().assign(
        net_pp=lambda f: f.net_pnl / INITIAL * 100,
        gross_same_labels_pp=lambda f: f.gross_same_labels / INITIAL * 100,
        fees_pp=lambda f: f.fees / INITIAL * 100,
    )


def serial(value):
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


accounts = {r["case"]: r for r in read_json("accounts.json")}
signals = {}
for path in sorted(SOURCE.glob("*-signals.csv")):
    signals[path.name.removesuffix("-signals.csv")] = pd.read_csv(
        file(path.name), index_col="date", parse_dates=True
    ).sort_index()

all_rows, all_orders, all_decisions, all_daily, loss_runs = [], [], [], [], []
checks, controls = {}, []
for market in ["etf17", "hk7"]:
    case = f"{market}-pv-base"
    episodes = pd.DataFrame(read_json(f"{case}-episodes.json"))
    orders = pd.DataFrame(read_json(f"{case}-orders.json"))
    decisions = read_json(f"{case}-decisions.json")
    daily = pd.read_csv(file(f"{case}-daily-episodes.csv"), parse_dates=["date"])
    path = pd.read_parquet(file(f"{case}-path.parquet")).sort_index()
    last = path.index[-1]
    assert not episodes.id.duplicated().any()
    orders["owner"] = -1
    orders["market"] = market
    rows = []
    for ep in episodes.sort_values(["symbol", "entry", "id"]).to_dict("records"):
        symbol = ep["symbol"]
        s = signals[symbol]
        start = pd.Timestamp(ep["entry"])
        has_exit = isinstance(ep["exit"], str)
        finish = pd.Timestamp(ep["exit"]) if has_exit else last
        match = (
            (orders.symbol == symbol) &
            (orders.date >= ep["entry"]) &
            (orders.date <= finish.strftime("%Y-%m-%d"))
        )
        assert (orders.loc[match, "owner"] == -1).all()
        orders.loc[match, "owner"] = ep["id"]
        fills = orders.loc[match]
        buys = fills[fills.units > 0]
        sells = fills[fills.units < 0]
        assert len(buys)
        buy_cash = (buys.units * buys.raw_open * buys.fx + buys.fee).sum()
        assert abs(buy_cash - ep["buy_cash"]) < 1e-6
        prices = s.close.loc[start:finish]
        rel = prices / prices.iloc[0] - 1
        assert abs(rel.max() - ep["signal_close_mfe"]) < 1e-10
        assert abs(rel.min() - ep["signal_close_mae"]) < 1e-10
        assert len(prices) == ep["sessions"]
        held_prices = prices[prices.index < finish] if has_exit else prices
        held_rel = held_prices / prices.iloc[0] - 1
        sigdate = pd.Timestamp(buys.iloc[0].signal_date)
        signal = s.loc[sigdate] if sigdate in s.index else None
        floor = float(signal.structure_floor) if signal is not None else np.nan
        close = float(signal.close) if signal is not None else np.nan
        prior_state_entries = s.loc[:sigdate].index[s.loc[:sigdate].entered > 0]
        state_start = prior_state_entries[-1] if len(prior_state_entries) else None
        state_floor = float(s.loc[state_start, "structure_floor"]) if state_start is not None else np.nan
        last_signal_date = pd.Timestamp(sells.iloc[-1].signal_date) if len(sells) else finish
        structure_path = s.loc[sigdate:last_signal_date]
        full_state_path = s.loc[state_start:last_signal_date] if state_start is not None else structure_path
        active_floors = structure_path.loc[structure_path.target > 0, "structure_floor"].dropna()
        additional_states = int((structure_path.iloc[1:].entered > 0).sum())
        raised = (
            bool((active_floors > floor + abs(floor)*1e-12).any())
            if np.isfinite(floor) else None
        )
        whole_state_raised = (
            bool((full_state_path.structure_floor > state_floor+abs(state_floor)*1e-12).any())
            if np.isfinite(state_floor) else None
        )
        record = dict(ep)
        record.update(
            market=market, case=case, key=f"{market}:{ep['id']}",
            entry_year=start.year, exit_year=finish.year if has_exit else None,
            gross_same_labels=ep["pnl"] + ep["fees"],
            net_pp=ep["pnl"] / 10000, fees_pp=ep["fees"] / 10000,
            outcome=("ordinary_loss" if ep["pnl"] < 0 else
                     "ordinary_win" if ep["pnl"] > 0 else "ordinary_flat")
                    if ep["label"] == "ordinary" else ep["label"],
            mfe_band=band(ep["signal_close_mfe"]),
            calendar_days=(finish-start).days,
            price_first=float(prices.iloc[0]), price_last=float(prices.iloc[-1]),
            close_terminal_return=float(rel.iloc[-1]),
            close_peak_to_terminal_pp=float(100*(rel.max()-rel.iloc[-1])),
            close_peak_date=rel.idxmax().strftime("%Y-%m-%d"),
            close_trough_date=rel.idxmin().strftime("%Y-%m-%d"),
            held_close_mfe_excluding_exit=float(held_rel.max()) if len(held_rel) else np.nan,
            held_close_mae_excluding_exit=float(held_rel.min()) if len(held_rel) else np.nan,
            held_close_mfe_band=band(float(held_rel.max())) if len(held_rel) else "missing",
            buy_fills=len(buys), sell_fills=len(sells),
            order_fees=float(fills.fee.sum()),
            non_order_fees=float(ep["fees"] - fills.fee.sum()),
            first_buy_signal_date=buys.iloc[0].signal_date,
            last_sell_signal_date=sells.iloc[-1].signal_date if len(sells) else None,
            entry_signal_close=close, entry_signal_floor_log=floor,
            entry_signal_floor=float(np.exp(floor)),
            entry_signal_floor_distance=(close-np.exp(floor))/close
                if np.isfinite(floor) and close > 0 else np.nan,
            state_entry_signal_date=state_start.strftime("%Y-%m-%d") if state_start is not None else None,
            inherited_active_state=state_start is not None and state_start < sigdate,
            state_initial_floor_log=state_floor,
            state_initial_floor=float(np.exp(state_floor)),
            floor_already_raised_before_first_buy_signal=(
                floor > state_floor+abs(state_floor)*1e-12
                if np.isfinite(state_floor) and np.isfinite(floor) else None
            ),
            floor_raised_after_first_buy_signal=raised,
            floor_raised_anytime_in_structure=whole_state_raised,
            floor_raise_count_after_first_buy_signal=int(
                (active_floors.diff() > active_floors.abs()*1e-12).sum()
            ),
            additional_structure_entries_in_episode=additional_states,
            structure_attribution=("multiple_states_execution_overlap" if additional_states else
                                   "floor_raised_after_entry" if raised else
                                   "floor_not_raised_after_entry" if raised is False else "unknown"),
            original_position_open=not has_exit,
            position_closed_claim_open=has_exit and ep["status"] == "open_or_claim",
            prior_episode_id=None, prior_exit_date=None, prior_exit_to_entry_sessions=np.nan,
            prior_exit_to_entry_calendar_days=np.nan, preceding_ordinary_loss=False,
            consecutive_ordinary_loss_number=0,
        )
        rows.append(record)
    assert (orders.owner >= 0).all()
    frame = pd.DataFrame(rows)
    for symbol, symbol_episodes in frame.groupby("symbol", sort=True):
        previous = None
        streak = []
        for index, ep in symbol_episodes.sort_values(["entry", "id"]).iterrows():
            if previous is not None and isinstance(previous["exit"], str):
                exit_date = pd.Timestamp(previous["exit"])
                entry_date = pd.Timestamp(ep.entry)
                frame.at[index, "prior_episode_id"] = previous["id"]
                frame.at[index, "prior_exit_date"] = previous["exit"]
                frame.at[index, "prior_exit_to_entry_sessions"] = int(
                    ((signals[symbol].index > exit_date) &
                     (signals[symbol].index <= entry_date)).sum()
                )
                frame.at[index, "prior_exit_to_entry_calendar_days"] = (entry_date-exit_date).days
                frame.at[index, "preceding_ordinary_loss"] = previous["outcome"] == "ordinary_loss"
            if ep.outcome == "ordinary_loss":
                streak.append(ep.to_dict())
                frame.at[index, "consecutive_ordinary_loss_number"] = len(streak)
            else:
                if streak:
                    loss_runs.append(dict(
                        market=market, symbol=symbol, first_entry=streak[0]["entry"],
                        final_exit=streak[-1]["exit"], count=len(streak),
                        ids="|".join(str(v["id"]) for v in streak),
                        net_pp=sum(v["net_pp"] for v in streak),
                        fees_pp=sum(v["fees_pp"] for v in streak),
                        next_episode_id=ep.id, next_outcome=ep.outcome,
                    ))
                streak = []
            previous = ep.to_dict()
        if streak:
            loss_runs.append(dict(
                market=market, symbol=symbol, first_entry=streak[0]["entry"],
                final_exit=streak[-1]["exit"], count=len(streak),
                ids="|".join(str(v["id"]) for v in streak),
                net_pp=sum(v["net_pp"] for v in streak),
                fees_pp=sum(v["fees_pp"] for v in streak),
                next_episode_id=None, next_outcome=None,
            ))
    # Flatten all saved decisions; no invented cause for a missing or partial fill.
    for decision in decisions:
        date = decision["date"]
        for symbol, score in decision["scores"].items():
            on_day = orders[(orders.date == date) & (orders.symbol == symbol)]
            previous_day = path.index[path.index < pd.Timestamp(date)]
            prior_weight = float(path.loc[previous_day[-1], f"w_{symbol}"]) if len(previous_day) else 0.0
            end_weight = float(path.loc[pd.Timestamp(date), f"w_{symbol}"])
            all_decisions.append(dict(
                market=market, date=date, symbol=symbol, score=score,
                target_units=decision["targets"][symbol], prior_weight=prior_weight,
                end_weight=end_weight, fills=len(on_day), buy_fills=int((on_day.units>0).sum()),
                sell_fills=int((on_day.units<0).sum()),
                positive_score_flat_before=score>0 and prior_weight<=1e-12,
                positive_score_still_flat_after=score>0 and end_weight<=1e-12,
                date_present_in_saved_signal=pd.Timestamp(date) in signals[symbol].index,
                prior_nav=decision["prior_nav"],
                cause="not inferred; saved decisions have no rejection reason",
            ))
    daily["market"] = market
    daily["year"] = daily.date.dt.year
    daily["symbol"] = daily.id.map(frame.set_index("id").symbol)
    sums = daily.groupby("id").pnl.sum()
    max_daily_episode_error = float((frame.set_index("id").pnl-sums).abs().max())
    assert max_daily_episode_error < 1e-6
    label_check = {}
    for label in ["ordinary", "tail", "open_or_claim"]:
        part = frame[frame.label == label]
        saved = accounts[case]["episodes"][label]
        assert len(part) == saved["n"]
        assert abs(part.pnl.sum()-saved["net_pnl"]) < 1e-6
        assert abs(part.fees.sum()-saved["fees"]) < 1e-6
        assert abs(part.gross_same_labels.sum()-saved["gross_pnl_same_labels"]) < 1e-6
        label_check[label] = dict(
            n=len(part), net_pp=part.pnl.sum()/10000,
            gross_same_labels_pp=part.gross_same_labels.sum()/10000,
            fees_pp=part.fees.sum()/10000,
        )
    assert abs(frame.pnl.sum()/INITIAL-accounts[case]["total_return"]) < 1e-10
    assert abs(frame.fees.sum()-accounts[case]["fees"]) < 1e-6
    checks[market] = dict(
        episodes=len(frame), orders=len(orders), decisions=len(decisions),
        all_orders_assigned_once=True, all_buy_cash_reconciled=True,
        saved_mfe_mae_sessions_reproduced=True, labels_reconciled=label_check,
        daily_episode_max_error=max_daily_episode_error,
        original_positions_open=int(frame.original_position_open.sum()),
        closed_positions_with_open_claims=int(frame.position_closed_claim_open.sum()),
    )
    all_rows.append(frame)
    all_orders.append(orders)
    all_daily.append(daily)
    for model in ["pv", "price", "momentum"]:
        saved = accounts[f"{market}-{model}-base"]
        for label in ["ordinary", "tail", "open_or_claim"]:
            item = saved["episodes"][label]
            controls.append(dict(
                market=market, model=model, label=label, n=item["n"],
                net_pp=item["net_pnl"]/10000,
                gross_same_labels_pp=item["gross_pnl_same_labels"]/10000,
                fees_pp=item["fees"]/10000,
                total_return_pct=saved["total_return"]*100,
                dd_pct=abs(saved["max_drawdown"])*100,
            ))

full = pd.concat(all_rows, ignore_index=True).sort_values(["market", "id"])
orders = pd.concat(all_orders, ignore_index=True)
daily = pd.concat(all_daily, ignore_index=True)
decision_frame = pd.DataFrame(all_decisions)
full.to_csv(OUT/"all-episodes.csv", index=False)
orders.to_csv(OUT/"all-order-ownership.csv", index=False)
decision_frame.to_csv(OUT/"all-decision-opportunities.csv", index=False)
full[full.label=="open_or_claim"].to_csv(OUT/"open-or-claim.csv", index=False)
for name, keys in [
    ("market-label", ["market", "label"]),
    ("market-outcome", ["market", "outcome"]),
    ("market-mfe-outcome", ["market", "mfe_band", "outcome"]),
    ("asset-outcome", ["market", "symbol", "outcome"]),
    ("asset-entry-year-outcome", ["market", "symbol", "entry_year", "outcome"]),
    ("entry-year-outcome", ["market", "entry_year", "outcome"]),
    ("exit-year-outcome", ["market", "exit_year", "outcome"]),
    ("prior-loss-overlap", ["market", "preceding_ordinary_loss", "outcome"]),
    ("floor-change-outcome", ["market", "structure_attribution", "outcome"]),
    ("whole-structure-floor-outcome", ["market", "floor_raised_anytime_in_structure", "outcome"]),
    ("floor-change-mfe-loss", ["market", "structure_attribution", "mfe_band", "outcome"]),
]:
    summarize(full, keys).to_csv(OUT/f"{name}.csv", index=False)
daily.groupby(["market", "year", "label"], as_index=False).pnl.sum().assign(
    net_pp=lambda f:f.pnl/10000
).to_csv(OUT/"daily-year-label-attribution.csv", index=False)
daily.groupby(["market", "symbol", "year", "label"], as_index=False).pnl.sum().assign(
    net_pp=lambda f:f.pnl/10000
).to_csv(OUT/"daily-asset-year-label-attribution.csv", index=False)
pd.DataFrame(loss_runs).sort_values("net_pp").to_csv(OUT/"consecutive-loss-runs.csv", index=False)
pd.DataFrame(controls).to_csv(OUT/"saved-controls.csv", index=False)
risk_rows = []
for keys,g in full.groupby(["market", "outcome", "structure_attribution"]):
    v=g.entry_signal_floor_distance.dropna()
    risk_rows.append(dict(
        market=keys[0],outcome=keys[1],structure_attribution=keys[2],n=len(g),
        finite_risk_n=len(v),min=float(v.min()),p10=float(v.quantile(.1)),
        p25=float(v.quantile(.25)),median=float(v.median()),p75=float(v.quantile(.75)),
        p90=float(v.quantile(.9)),max=float(v.max()),
        spearman_distance_vs_net_return=float(g.entry_signal_floor_distance.rank().corr(g.ret.rank()))
            if len(g)>2 else None,
    ))
pd.DataFrame(risk_rows).to_csv(OUT/"entry-floor-distance-distributions.csv",index=False)
decision_frame.groupby("market").agg(
    asset_days=("date","size"),
    positive_score_flat_before=("positive_score_flat_before","sum"),
    positive_score_still_flat_after=("positive_score_still_flat_after","sum"),
    buy_fills=("buy_fills","sum"), sell_fills=("sell_fills","sum"),
).to_csv(OUT/"decision-opportunity-summary.csv")
loss = full[full.outcome=="ordinary_loss"]
summary = dict(
    task="Read-only saved-account attribution; no model or account engine executed",
    initial_capital_per_market=INITIAL,
    checks=checks,
    loss_findings={},
    participation_checks={
        market: dict(
            positive_signal_still_flat_asset_days=int(g.positive_score_still_flat_after.sum()),
            of_these_with_saved_signal_observation=int(
                (g.positive_score_still_flat_after & g.date_present_in_saved_signal).sum()
            ),
            interpretation="No capital-blockage conclusion; verify calendar/raw tradability if needed.",
        )
        for market,g in decision_frame.groupby("market")
    },
    limitations=[
        "Saved MFE/MAE uses adjusted signal CLOSE relative to execution-day CLOSE, includes exit-day CLOSE after actual opening sale, excludes entry-day open-to-close move and all intraday extremes.",
        "MFE/MAE is not executed account PNL: raw fills, FX, fees, dividends and multiple fills differ. Peak-to-terminal close giveback is diagnostic, never foregone executable profit.",
        "An extra held-close field excludes exit-day close. It still excludes entry-day open-to-close and intraday extremes and is not a corrected true MFE.",
        "Gross same-label PNL only adds recorded fees to same trades. It is not a no-cost counterfactual account, and tail labels stay net labels.",
        "Entry/exit-year tables assign a whole episode to one year. Daily-year-label table uses saved daily PNL with final hindsight episode labels; it is the calendar-year attribution.",
        "Reentry and preceding-loss flags overlap MFE groups and are not additive. Consecutive-loss runs terminate on any non-loss or open/claim episode, not on hindsight market troughs.",
        "Saved decisions contain no rejection reason. Positive score while flat is a participation observation, not proof of capital blockage; holidays, pending fills, lots and liquidity may matter.",
        "ETF17 contains five Hong Kong ETF symbols; ETF17/HK7 are saved portfolios, not currency or pure exchange partitions.",
        "Floor-change attribution uses saved causal floors from first buy signal through final sale signal. States already active before first buy are marked inherited; multiple state entries during a still-open execution episode are marked separately.",
        "Entry floor distance is (signal close - signal floor)/signal close, not actual initial risk or guaranteed loss. Gaps, costs, FX and delayed execution can exceed it. Correlations are exploratory, not causal effects.",
        "All history was previously seen. Fixed MFE bins are descriptive and not candidate trading thresholds.",
    ],
)
for market,g in loss.groupby("market"):
    low=g[g.signal_close_mfe<.05]
    high=g[g.signal_close_mfe>=.15]
    f=full[(full.market==market)&(full.label=="ordinary")]
    summary["loss_findings"][market] = dict(
        ordinary_loss_count=len(g), ordinary_loss_net_pp=g.pnl.sum()/10000,
        ordinary_winner_count=int((f.pnl>0).sum()),
        ordinary_winner_net_pp=f.loc[f.pnl>0,"pnl"].sum()/10000,
        below_5_close_mfe_loss_count=len(low),
        below_5_close_mfe_loss_net_pp=low.pnl.sum()/10000,
        below_5_close_mfe_share_of_all_losing_pnl=float(low.pnl.sum()/g.pnl.sum()),
        at_least_15_close_mfe_loss_count=len(high),
        at_least_15_close_mfe_loss_net_pp=high.pnl.sum()/10000,
        median_loss_return=float(g.ret.median()),
        median_loss_sessions=float(g.sessions.median()),
        losses_following_ordinary_loss_count=int(g.preceding_ordinary_loss.sum()),
        losses_following_ordinary_loss_net_pp=float(g.loc[g.preceding_ordinary_loss,"pnl"].sum()/10000),
        mfe_band_changes_if_exit_day_excluded=int((g.mfe_band!=g.held_close_mfe_band).sum()),
    )
summary["code_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
summary["protocol_sha256"]=hashlib.sha256((ROUND/"protocol.json").read_bytes()).hexdigest()
(OUT/"input-hashes.json").write_text(json.dumps(INPUTS, indent=2, ensure_ascii=False)+"\n")
(OUT/"summary.json").write_text(json.dumps(serial(summary), indent=2, ensure_ascii=False, allow_nan=False)+"\n")
print(json.dumps(serial(summary), indent=2, ensure_ascii=False, allow_nan=False))

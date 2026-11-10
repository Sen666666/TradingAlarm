"""One account per group. New entries split cash. Existing holds are not trimmed.

The trend state stays frozen. 2018-2021 has already been seen.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from trend_background_hold import path_scores
from trend_positive_connect import positive_state
from trend_cycle_fit import load_full
from market_state_phase2 import load_symbol

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-cash-book'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
WINDOWS = (('2006-2008', '2006-01-01', '2008-06-30'),
           ('2008-2010', '2008-07-01', '2010-06-30'),
           ('2013-2016', '2013-07-01', '2016-06-30'),
           ('2018-2021', '2018-01-01', '2021-12-31'),
           ('2022-2026', '2022-01-01', '2026-10-16'))
LOT = 1e-6
COST = 0.0015
MINIMUM = 5.
CAPITAL = 1e6


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def window_stats(nav, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    base_rows = nav.index[nav.index <= start]
    if not len(base_rows):
        return None
    sample = nav[(nav.index >= base_rows.max()) & (nav.index <= end)].dropna()
    if len(sample) < 2:
        return None
    rel = sample / sample.iloc[0]
    return dict(start=str(sample.index[0].date()), end=str(sample.index[-1].date()),
                total_return=float(rel.iloc[-1] - 1),
                peak_return=float(rel.max() - 1),
                max_drawdown=float((rel / rel.cummax() - 1).min()))


def simulate(frames, states, starts, ledger=None, lot=None, exit_days=None, *,
             budget_after_sells=True, orders=None, snapshots=None):
    """exit_days limits a new buy so the position can be sold in that many sessions at the participation cap.

    Sell-first allocation is an explicit policy change. Set budget_after_sells=False
    for the original pre-sale budget/pending-order policy; one-lot and terminal accounting stay fixed.
    This proxy has no corporate actions/FX and is not a real execution certification.
    """
    lot = LOT if lot is None else lot
    calendar = pd.DatetimeIndex(sorted(set().union(*(frame.index for frame in frames.values()))))
    cash = float(CAPITAL)
    qty = {symbol: 0.0 for symbol in frames}
    basis = {symbol: 0.0 for symbol in frames}
    taken = {symbol: 0.0 for symbol in frames}
    opened = {symbol: None for symbol in frames}
    pending = {}
    signal = {symbol: 0.0 for symbol in frames}
    nav = []
    peak = cash
    for i, day in enumerate(calendar):
        prior = calendar[i-1] if i else None
        today = {}
        for symbol, frame in frames.items():
            if prior is None or prior < starts[symbol] or prior not in frame.index:
                sig = 0.0
            else:
                sig = float(states[symbol].loc[prior])
            today[symbol] = sig
        sells = [symbol for symbol, sig in today.items() if sig < signal[symbol] or (symbol in pending and pending[symbol][0] == 'sell')]
        buys = [symbol for symbol, sig in today.items() if sig > signal[symbol]]
        for symbol in sells:
            if qty[symbol] > max(1e-12, lot*1e-9) or not budget_after_sells:
                pending[symbol] = ('sell', None)
            else:
                pending.pop(symbol, None)
        if buys:
            budget = None if budget_after_sells else (cash / len(buys) if cash > MINIMUM else 0.0)
            for symbol in buys:
                pending[symbol] = ('buy', budget)
        # Sales execute before buys. New unfunded orders retain an unassigned
        # budget until cash is available or an exit signal cancels them.
        sequence = sorted(pending, key=lambda s: pending[s][0] != 'sell') if budget_after_sells else list(pending)
        allocated = False
        for symbol in sequence:
            if budget_after_sells and pending[symbol][0] == 'buy' and not allocated:
                for s, (kind, budget) in list(pending.items()):
                    if kind == 'buy' and qty[s] == 0: pending[s] = ('buy', None)
                unassigned = [s for s, (kind, budget) in pending.items() if kind == 'buy' and budget is None]
                reserved = sum(b for kind, b in pending.values() if kind == 'buy' and b is not None)
                free = max(0., cash-reserved)
                if unassigned and free > MINIMUM*len(unassigned):
                    for s in unassigned: pending[s] = ('buy', free/len(unassigned))
                allocated = True
            frame = frames[symbol]
            if day not in frame.index:
                continue
            bar = frame.loc[day]
            if not (bar.volume > 0 and bar.high > bar.low and bar.open > 0):
                continue
            kind, budget = pending[symbol]
            if kind == 'buy' and budget is None:
                continue
            history = frame.loc[:prior, 'volume'] if prior is not None else frame.iloc[0:0]['volume']
            cap = float(history.tail(20).mean()) * 0.01 if len(history) else 0.0
            cap = math.floor(cap / lot) * lot
            if cap <= 0:
                continue
            price = float(bar.open)
            if kind == 'sell':
                delta = -min(qty[symbol], cap)
            else:
                room = math.floor(max(0.0, cash - MINIMUM) / (price * (1 + COST)) / lot) * lot
                affordable = math.floor(budget / (price * (1 + COST)) / lot) * lot
                delta = min(cap, room, affordable)
                if exit_days is not None:
                    ceiling = math.floor(max(0.0, exit_days * cap - qty[symbol]) / lot) * lot
                    delta = min(delta, ceiling)
            if not delta:
                continue
            fee = max(abs(delta) * price * COST, MINIMUM)
            if delta > 0 and cash < delta * price + fee:
                continue
            cash -= delta * price + fee
            qty[symbol] += delta
            if orders is not None:
                orders.append(dict(date=str(day.date()), symbol=symbol, units=float(delta), price=price, fee=fee))
            if kind == 'buy':
                spent = delta * price + fee
                if basis[symbol] <= 0:
                    opened[symbol] = day
                    taken[symbol] = 0.0
                basis[symbol] += spent
                pending[symbol] = ('buy', max(0.0, budget - spent))
                if pending[symbol][1] <= MINIMUM or qty[symbol] <= 0:
                    pending.pop(symbol, None)
            else:
                taken[symbol] += -delta * price - fee
                if qty[symbol] <= max(1e-12, lot*1e-9):
                    qty[symbol] = 0.0
                    if ledger is not None and basis[symbol] > 0:
                        ledger.append(dict(symbol=symbol, entry=str(opened[symbol].date()), exit=str(day.date()),
                                           ret=taken[symbol]/basis[symbol] - 1, pnl=taken[symbol] - basis[symbol], open=False, hypothetical_exit_fee=0.))
                    basis[symbol] = 0.0
                    taken[symbol] = 0.0
                    opened[symbol] = None
                    pending.pop(symbol, None)
        signal = today
        market = 0.0
        for symbol, frame in frames.items():
            if qty[symbol] <= 0:
                continue
            closes = frame.loc[:day, 'close']
            if not len(closes):
                continue
            market += qty[symbol] * float(closes.iloc[-1])
        level = cash + market
        peak = max(peak, level)
        nav.append((day, level))
        if snapshots is not None:
            snapshots.append(dict(date=str(day.date()), cash=cash, nav=level, quantities=dict(qty), pending={s:list(v) for s,v in pending.items()}))
    if ledger is not None:
        for symbol, frame in frames.items():
            if qty[symbol] <= max(1e-12, lot*1e-9) or basis[symbol] <= 0:
                continue
            price = float(frame.loc[:calendar[-1], 'close'].iloc[-1])
            fee = max(qty[symbol] * price * COST, MINIMUM)
            mark = qty[symbol] * price
            ledger.append(dict(symbol=symbol, entry=str(opened[symbol].date()), exit=str(calendar[-1].date()),
                               ret=(taken[symbol] + mark)/basis[symbol] - 1, pnl=taken[symbol] + mark - basis[symbol], open=True, hypothetical_exit_fee=fee))
    series = pd.Series(dict(nav), dtype=float).sort_index()
    return series


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256'] or freeze.get('results_viewed') is not False:
        raise SystemExit('cash-book protocol changed after freeze')
    phase2 = json.loads((PHASE2/'protocol.json').read_text())
    coverage = {r['symbol']: r for r in json.loads((BATCH/'coverage.json').read_text())['per_symbol']}
    groups = {}
    for symbol in phase2['index_sets']['decisive_broad']:
        groups[symbol] = 'broad'
    for symbol in phase2['index_sets']['decisive_sector']:
        groups[symbol] = 'sector'
    loaded = {name: {} for name in ('broad', 'sector')}
    for symbol, group in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        full, start = load_full(symbol, launch)
        _, cut_start = load_symbol(symbol, launch)
        if start != cut_start or full.index.max() < pd.Timestamp('2026-10-01'):
            raise SystemExit(f'{symbol} history is not the extended sample')
        scores = path_scores(full.close, full.amount)
        state = pd.Series(positive_state(scores.fast.to_numpy(), scores.slow.to_numpy()), index=full.index)
        loaded[group][symbol] = (full, state, start)
    summary = dict(protocol_sha256=digest, not_out_of_sample=True, not_a_pass=True, windows={})
    for group, items in loaded.items():
        frames = {symbol: item[0] for symbol, item in items.items()}
        states = {symbol: item[1] for symbol, item in items.items()}
        starts = {symbol: item[2] for symbol, item in items.items()}
        nav = simulate(frames, states, starts)
        if nav.index.max() < pd.Timestamp('2026-10-01'):
            raise SystemExit(f'{group} account stopped early')
        summary['windows'][group] = {}
        for name, begin, stop in WINDOWS:
            got = window_stats(nav, begin, stop)
            if got:
                summary['windows'][group][name] = got
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

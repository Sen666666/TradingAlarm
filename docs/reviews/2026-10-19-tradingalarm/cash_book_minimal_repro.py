"""Read-only minimal probes of the transferred repository's cash-book engine.

Does not run historical experiments or write anything in the transferred tree.
Run with the existing money research venv; JSON is emitted to stdout.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

sys.dont_write_bytecode = True
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/tradingalarm-audit-mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp/tradingalarm-audit-cache")
SOURCE = Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research")
sys.path.insert(0, str(SOURCE))

import numpy as np
import pandas as pd
from trend_cash_book import simulate


def frame(prices, volume=1e9):
    index = pd.bdate_range("2020-01-01", periods=len(prices))
    close = pd.Series(prices, index=index, dtype=float)
    return pd.DataFrame(dict(open=close, high=close + 1, low=close - 0.5,
                             close=close, volume=volume), index=index)


def probe(frames, state_values):
    states = {s: pd.Series(v, index=frames[s].index, dtype=float)
              for s, v in state_values.items()}
    ledger = []
    nav = simulate(frames, states, {s: f.index[0] for s, f in frames.items()},
                   ledger, lot=100)
    return dict(dates=[str(x.date()) for x in nav.index], nav=nav.to_list(),
                ledger=ledger, nav_profit=float(nav.iloc[-1] - 1e6),
                ledger_profit=sum(x["pnl"] for x in ledger))


result = dict(
    purpose="Synthetic accounting/execution probes only; no historical strategy rerun",
    runtime=dict(executable=sys.executable, version=platform.python_version(),
                 numpy=np.__version__, pandas=pd.__version__),
    source=str(SOURCE / "trend_cash_book.py"),
    source_sha256=hashlib.sha256((SOURCE / "trend_cash_book.py").read_bytes()).hexdigest(),
    cases={},
)
cases = result["cases"]
cases["same_day_rotation"] = probe(
    {"A": frame([10] * 7), "B": frame([10, 10, 10, 10, 20, 30, 40])},
    {"A": [0, 1, 0, 0, 0, 0, 0], "B": [0, 0, 1, 1, 1, 1, 1]},
)
cases["same_day_rotation"]["interpretation"] = (
    "B's buy budget is fixed before A's sale; B never buys after cash is released, "
    "although its state remains on and its price rises from 10 to 40."
)
cases["partial_sell_erases_one_lot"] = probe(
    {"A": frame([10] * 7, 10000)}, {"A": [0, 1, 1, 0, 0, 0, 0]}
)
cases["partial_sell_erases_one_lot"]["interpretation"] = (
    "Two 100-share buys and one 100-share sale cost 15 in fees. The remaining "
    "100 shares worth 1000 are set to zero by qty <= lot, causing a fictitious "
    "1015 loss at constant price."
)
cases["open_one_lot_missing_from_ledger"] = probe(
    {"A": frame([10] * 4, 10000)}, {"A": [0, 0, 1, 1]}
)
cases["open_one_lot_missing_from_ledger"]["interpretation"] = (
    "An open position of exactly one lot remains in NAV but is omitted from "
    "the terminal ledger because qty <= lot is skipped."
)
cases["pending_buy_cancelled_on_exit"] = probe(
    {"A": frame([10] * 6, 10000)}, {"A": [0, 1, 0, 0, 0, 0]}
)
cases["pending_buy_cancelled_on_exit"]["interpretation"] = (
    "Control that passes: an unfilled buy remainder is replaced by the sell "
    "signal, and the one purchased lot exits; no later rebuy occurs."
)
cases["terminal_mark_fee_only"] = probe(
    {"A": frame([10] * 5, 10000)}, {"A": [0, 0, 1, 1, 1]}
)
cases["terminal_mark_fee_only"]["interpretation"] = (
    "NAV marks the two open lots gross; the terminal ledger subtracts a "
    "hypothetical 5 liquidation fee. This is a valuation-basis difference, "
    "not a second fee charged to NAV."
)
assert cases["same_day_rotation"]["nav"][-1] == 997006
assert [x["symbol"] for x in cases["same_day_rotation"]["ledger"]] == ["A"]
assert cases["partial_sell_erases_one_lot"]["nav_profit"] == -1015
assert cases["open_one_lot_missing_from_ledger"]["ledger"] == []
assert cases["pending_buy_cancelled_on_exit"]["nav_profit"] == -10
assert cases["terminal_mark_fee_only"]["nav_profit"] == -10
assert cases["terminal_mark_fee_only"]["ledger_profit"] == -15
print(json.dumps(result, ensure_ascii=False, indent=2))

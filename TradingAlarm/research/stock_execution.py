"""Conservative next-open guard using dated raw-price state, never guessed limits.

Passing this guard is necessary, not sufficient: fees, quantity, cash, lots,
liquidity and corporate-action accounting remain the portfolio ledger's job.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Optional


@dataclass(frozen=True)
class OpenState:
    date: str
    raw_open: float
    trading: Optional[bool]
    limits_date: Optional[str] = None
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    explicitly_unlimited: bool = False
    state_verified: bool = False
    tick: float = .01


@dataclass(frozen=True)
class FillDecision:
    allowed: bool
    reason: str
    price: Optional[float] = None


def next_open_guard(state, side, decision_date, slippage_bps=0., sellable_quantity=None):
    """Caller supplies prior-close signal date and T+1-settled sellable shares.

    At a buy-side limit-up open or sell-side limit-down open, skip this open
    entirely. Daily bars cannot establish queue priority or a later fill.
    """
    if side not in {'buy', 'sell'}:
        raise ValueError('side must be buy or sell')
    if not isfinite(slippage_bps) or slippage_bps < 0:
        raise ValueError('invalid slippage')
    if decision_date >= state.date:
        return FillDecision(False, 'signal_not_before_execution')
    if state.trading is False:
        return FillDecision(False, 'suspended')
    if state.trading is not True or not state.state_verified:
        return FillDecision(False, 'unknown_trading_state')
    if not isfinite(state.raw_open) or state.raw_open <= 0 or not isfinite(state.tick) or state.tick<=0:
        return FillDecision(False, 'invalid_raw_open_or_tick')
    if side == 'sell' and (sellable_quantity is None or not isfinite(sellable_quantity) or sellable_quantity <= 0):
        return FillDecision(False, 'no_verified_sellable_inventory')
    if state.limits_date != state.date:
        return FillDecision(False, 'missing_or_stale_price_limit_state')
    if state.explicitly_unlimited:
        if state.upper_limit is not None or state.lower_limit is not None:
            return FillDecision(False, 'conflicting_limit_state')
    else:
        limits=(state.lower_limit,state.upper_limit)
        if any(x is None or not isfinite(x) or x<=0 for x in limits) or limits[0]>=limits[1]:
            return FillDecision(False, 'missing_or_invalid_price_limits')
        tolerance=state.tick/2
        if not state.lower_limit-tolerance <= state.raw_open <= state.upper_limit+tolerance:
            return FillDecision(False, 'open_outside_price_limits')
        if side=='buy' and state.raw_open>=state.upper_limit-tolerance:
            return FillDecision(False, 'limit_up_queue_unknown')
        if side=='sell' and state.raw_open<=state.lower_limit+tolerance:
            return FillDecision(False, 'limit_down_queue_unknown')
    price=state.raw_open*(1+slippage_bps/10000*(1 if side=='buy' else -1))
    if price<=0:
        return FillDecision(False, 'invalid_slipped_price')
    if not state.explicitly_unlimited and not state.lower_limit<=price<=state.upper_limit:
        return FillDecision(False, 'slipped_price_outside_limits')
    return FillDecision(True, 'open_passes_state_guard', price)

"""Process-local 1.5x fee and adverse-slippage stress for the frozen native book.

No on-disk native source is changed. Native account/route/order/settlement code
continues to run. apply_cost_stress(V) precedes runner construction; then call
configure_runner(r) before the first financial event. One fresh process per run.
"""
from dataclasses import replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
import hashlib, inspect

MULTIPLIER = Decimal('1.5')
SLIPPAGE = Decimal('0.00075')
VERSION = 'ALL_COMPONENT_FEES_AND_SLIPPAGE_X1_5_V1'
_ORIGINAL_INCREMENTAL = None
_ORIGINAL_ACCRUAL = None
_ORIGINAL_WINDOW = None
_FEE_CLASS = None
_MARKET_CLASS = None
_V = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def scaled_schedule(schedule):
    """Scale the entire original fee function, including caps/minima/rounding.

    Scaling its rounding quantum as well makes each component exactly 1.5x
    the base function for fixed notional/fills, rather than creating a second
    rounding convention. Native paid/accrued maps stay in the scaled domain.
    All original amount bases and per-order/per-fill semantics are retained.
    """
    cs = tuple(replace(c,
        rate=Decimal(c.rate) * MULTIPLIER,
        minimum_local=Decimal(c.minimum_local) * MULTIPLIER,
        maximum_local=None if c.maximum_local is None else Decimal(c.maximum_local) * MULTIPLIER,
        rounding_unit=None if c.rounding_unit is None else Decimal(c.rounding_unit) * MULTIPLIER)
        for c in schedule.components)
    return replace(schedule, components=cs)


def stressed_incremental(self, side, local_notional, paid, accrued, multiplier,
                         *, shares=None, par_value=None):
    if Decimal(str(multiplier)) == MULTIPLIER:
        return _ORIGINAL_INCREMENTAL(scaled_schedule(self), side, local_notional,
            paid, accrued, 1, shares=shares, par_value=par_value)
    return _ORIGINAL_INCREMENTAL(self, side, local_notional, paid, accrued,
        multiplier, shares=shares, par_value=par_value)


def stressed_rate_accrual(self, side, local_notional, multiplier,
                          *, shares=None, par_value=None):
    if Decimal(str(multiplier)) == MULTIPLIER:
        return _ORIGINAL_ACCRUAL(scaled_schedule(self), side, local_notional, 1,
            shares=shares, par_value=par_value)
    return _ORIGINAL_ACCRUAL(self, side, local_notional, multiplier,
        shares=shares, par_value=par_value)


def stressed_window(self, sid, at, side, cost_multiplier):
    """Preserve original fill eligibility/capacity; change execution price only.

    The native joint runner passes 1 here unconditionally. Its base cached
    window (including the original slow/fast identity check) remains intact.
    The new returned frozen dataclass differs only in adverse execution_price.
    """
    assert Decimal(str(cost_multiplier)) in (Decimal(1), MULTIPLIER)
    w = _ORIGINAL_WINDOW(self, sid, at, side, 1)
    if w is None:
        return None
    market = self.lines[sid].market
    policy = self.protocol['daily_execution'][market]
    assert Decimal(str(policy['slippage_bps'])) == Decimal(5)
    assert policy['stress_slippage'] is True
    return replace(w, execution_price=w.raw_open *
        (Decimal(1) + SLIPPAGE if side == 'buy' else Decimal(1) - SLIPPAGE))


def apply_cost_stress(V):
    """Install only this process's original FeeSchedule and FastMarket hooks.

    Return JSON-safe metadata/source binding. This is not a runner constructor,
    does not load new data, and does not create or restore a financial account.
    """
    global _ORIGINAL_INCREMENTAL, _ORIGINAL_ACCRUAL, _ORIGINAL_WINDOW
    global _FEE_CLASS, _MARKET_CLASS, _V
    assert _V is None, 'Apply once in a fresh process; never stack multipliers'
    _V = V
    _MARKET_CLASS = V.J.C.E.FastMarket
    _FEE_CLASS = _MARKET_CLASS.__mro__[1].fees.__globals__['FeeSchedule']
    _ORIGINAL_INCREMENTAL = _FEE_CLASS.incremental
    _ORIGINAL_ACCRUAL = _FEE_CLASS.rate_accrual
    _ORIGINAL_WINDOW = _MARKET_CLASS.window
    assert _ORIGINAL_INCREMENTAL.__module__ == 'sector_account'
    assert _ORIGINAL_WINDOW.__module__ == 'tech_fast_market'
    native_paths = {
        'native_fee_schedule': inspect.getsourcefile(_FEE_CLASS),
        'native_market': inspect.getsourcefile(_MARKET_CLASS),
        'native_lr_sizing': inspect.getsourcefile(V.J.LR.resize_core),
        'native_activate': inspect.getsourcefile(V.J.C.activate),
        'native_ledger': inspect.getsourcefile(V.J.BP.L.SectorAccount),
        'native_opening': inspect.getsourcefile(V.J.Runner.opening)}
    _FEE_CLASS.incremental = stressed_incremental
    _FEE_CLASS.rate_accrual = stressed_rate_accrual
    _MARKET_CLASS.window = stressed_window
    return dict(version=VERSION, multiplier=str(MULTIPLIER),
        adverse_slippage_bps='7.5', original_adverse_slippage_bps='5',
        all_fee_components_scaled=True, minimum_scaled=True,
        maximum_and_rounding_quantum_scaled=True,
        cumulative_partial_order_semantics='native paid/accrued in scaled domain',
        native_class_names_unchanged=True,
        on_disk_native_sources_unchanged=True,
        configure_runner_required_before_first_event=True,
        source_freeze={str(Path(__file__).resolve()): sha(__file__),
            **{str(Path(p).resolve()):sha(p) for p in native_paths.values()}},
        native_paths=native_paths,
        checkpoint_note='Account cost_multiplier is serialized. Reapply this '
            'same module in a fresh process before restoring this stress run; '
            'retain adapter SHA and stress version in RUN_METADATA/source_freeze. '
            'Do not restore a base-cost checkpoint into a stress account.')


def configure_runner(r):
    """Use native activation to synchronize fee estimation and LR risk/slip."""
    assert _V is not None
    assert not r.daily, 'Cost stress must precede first financial event'
    assert type(r.market) is _MARKET_CLASS
    for a in r.accounts.values():
        assert not a.trades and not a.layers and not a.buys and not a.exits
        assert a.cost_multiplier == 1
        a.cost_multiplier = MULTIPLIER
        _V.J.C.activate(a)
        assert _V.J.C.CURRENT['cost'] == MULTIPLIER
        assert _V.J.LR.SLIP == SLIPPAGE
        assert a.market is r.market
    r.cost_stress_version = VERSION
    r.cost_stress_multiplier = MULTIPLIER
    return dict(version=VERSION, accounts=list(r.accounts),
                multiplier=str(MULTIPLIER), first_event_not_started=True)


def assert_cost_stress_runner(r):
    assert _V is not None
    assert type(r.market) is _MARKET_CLASS
    assert _FEE_CLASS.incremental is stressed_incremental
    assert _FEE_CLASS.rate_accrual is stressed_rate_accrual
    assert _MARKET_CLASS.window is stressed_window
    assert r.cost_stress_version == VERSION
    assert r.cost_stress_multiplier == MULTIPLIER
    assert all(a.cost_multiplier == MULTIPLIER for a in r.accounts.values())
    return True

"""Explicit current-pool selection for historical development, not PIT evidence.

Pure adapter: no prices, trends, accounts, files or network are evaluated here.
Import the unchanged sector_stock_admission from the sibling 20261021 code dir
(put both code directories on PYTHONPATH). The selection manifest authenticates
current fields separately; this module cannot authenticate source truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
import re
from typing import Any, Literal, Sequence

import sector_stock_admission as admission

RESEARCH_BASIS = 'current_pool_historical_development'
SELECTION_LIMIT = (
    'Current surviving stocks, current cap/southbound/industry selection; '
    'survivorship and current-classification bias retained; not PIT or unseen.'
)


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware snapshot timestamp required')


def _bool(value: bool | None) -> None:
    if value is not None and type(value) is not bool:
        raise ValueError('Selection flags must be bool or None')


def _and_known(*values: bool | None) -> bool | None:
    # Match admission's unknown-first semantics, including false + unknown.
    return None if any(v is None for v in values) else all(values)


@dataclass(frozen=True)
class SelectionEvidence:
    """Frozen manifest identity, never relabelled as a historical known_at."""
    snapshot_id: str
    snapshot_sha256: str
    observed_at: datetime
    source_id: str
    research_basis: str = field(default=RESEARCH_BASIS, init=False)

    def __post_init__(self):
        _aware(self.observed_at)
        if not self.snapshot_id or not self.source_id:
            raise ValueError('Snapshot and source IDs are required')
        if not re.fullmatch(r'[0-9a-f]{64}', self.snapshot_sha256):
            raise ValueError('Expected lowercase SHA256 of the selection manifest')


@dataclass(frozen=True)
class PoolLine:
    """Current selection constants; A/H identifies stock markets, not an ETF."""
    security_id: str
    market: Literal['A', 'H']
    issuer_id: str | None
    sector_id: str | None
    company_cap_cny: float | None
    current_stock: bool | None
    southbound_selected: bool | None = None

    def __post_init__(self):
        if not self.security_id or self.market not in ('A', 'H'):
            raise ValueError('Stable security ID and A/H stock market required')
        for value in (self.issuer_id, self.sector_id):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError('Issuer/sector IDs must be nonempty or unknown')
        cap = self.company_cap_cny
        if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float))
                                or not math.isfinite(cap) or cap < 0):
            raise ValueError('Company cap must be finite, nonnegative CNY or unknown')
        _bool(self.current_stock)
        _bool(self.southbound_selected)

    @property
    def selected_market(self) -> bool | None:
        """Cap and industry are still evaluated by the unchanged admission."""
        return (_and_known(self.current_stock, self.southbound_selected)
                if self.market == 'H' else self.current_stock)


@dataclass(frozen=True)
class SelectionFact:
    """Only fixed selection fields may bypass the historical knowledge clock."""
    field: Literal['issuer_id', 'sector_id', 'company_cap_cny']
    value: Any
    evidence: SelectionEvidence

    def __post_init__(self):
        if self.field not in ('issuer_id', 'sector_id', 'company_cap_cny'):
            raise ValueError('Only fixed identity/classification/cap selection fields allowed')

    def read(self, clock: admission.Clock, *, for_execution: bool = False):
        # Deliberate research assumption; observed_at is retained, not backdated.
        return self.value


def _market_fact(value: admission.Fact) -> None:
    # Reject SelectionFact and subclasses overriding read for dynamic fields.
    if type(value) is not admission.Fact:
        raise ValueError('Historical market/state fields require unchanged admission.Fact')


@dataclass(frozen=True)
class HistoricalInputs:
    security_id: str
    common_ready: admission.Fact
    market_buyable: admission.Fact
    trend_up: admission.Fact
    rank: admission.Rank | None = None

    def __post_init__(self):
        for fact in (self.common_ready, self.market_buyable, self.trend_up):
            _market_fact(fact)
        if self.rank is not None and type(self.rank) is not admission.Rank:
            raise ValueError('Historical rank requires unchanged admission.Rank')


@dataclass(frozen=True)
class FixedSelectionBuyAllowed:
    """Current eligibility combined with causal listing/trading availability.

    market_buyable must describe historical listing and market availability,
    without requiring historical cap, industry or southbound membership chains.
    The executor must still enforce its separately frozen actual/proxy rules.
    """
    selected_market: bool | None
    market_buyable: admission.Fact
    evidence: SelectionEvidence

    def __post_init__(self):
        _bool(self.selected_market)
        _market_fact(self.market_buyable)

    def read(self, clock: admission.Clock, *, for_execution: bool = False):
        available = self.market_buyable.read(clock, for_execution=for_execution)
        _bool(available)
        return _and_known(self.selected_market, available)


def build_security(line: PoolLine, historical: HistoricalInputs,
                   evidence: SelectionEvidence) -> admission.Security:
    """Build a compatibility view; never alter original Fact or algorithm state."""
    if line.security_id != historical.security_id:
        raise ValueError('Fixed pool and historical observation IDs must match')
    return admission.Security(
        security_id=line.security_id,
        issuer_id=SelectionFact('issuer_id', line.issuer_id, evidence),
        sector_id=SelectionFact('sector_id', line.sector_id, evidence),
        common_ready=historical.common_ready,
        buy_allowed=FixedSelectionBuyAllowed(line.selected_market,
                                              historical.market_buyable, evidence),
        company_cap_cny=SelectionFact('company_cap_cny', line.company_cap_cny, evidence),
        trend_up=historical.trend_up,
        rank=historical.rank,
    )


@dataclass(frozen=True)
class CurrentPoolDecision:
    evidence: SelectionEvidence
    decision: admission.Decision
    research_basis: str = field(default=RESEARCH_BASIS, init=False)
    selection_limit: str = field(default=SELECTION_LIMIT, init=False)


def decide_current_pool(*, evidence: SelectionEvidence, lines: Sequence[PoolLine],
                        historical: Sequence[HistoricalInputs],
                        clock: admission.Clock, variant: admission.Variant,
                        sectors: Sequence[admission.Sector],
                        previous: Sequence[admission.Memory] = (),
                        occupied: Sequence[admission.Occupancy] = (),
                        bootstrap: bool = False,
                        completed_exits: Sequence[admission.ExitCompletion] = ()) -> CurrentPoolDecision:
    """Return labelled current-pool historical recommendations, never orders.

    Every fixed line needs an explicit historical input (unknown Facts allowed).
    Do not shrink the pool silently when data is unavailable or for T0.
    """
    fixed = {line.security_id: line for line in lines}
    dynamic = {item.security_id: item for item in historical}
    if len(fixed) != len(lines) or len(dynamic) != len(historical):
        raise ValueError('Duplicate fixed/historical security ID')
    if fixed.keys() != dynamic.keys():
        raise ValueError('Every fixed line needs historical inputs; preserve unknown lines')
    for sector in sectors:
        _market_fact(sector.trend_up)
        if sector.rank is not None and type(sector.rank) is not admission.Rank:
            raise ValueError('Historical sector rank requires unchanged admission.Rank')
    securities = [build_security(fixed[sid], dynamic[sid], evidence) for sid in sorted(fixed)]
    result = admission.decide(clock=clock, variant=variant, securities=securities,
                              sectors=sectors, previous=previous, occupied=occupied,
                              bootstrap=bootstrap, completed_exits=completed_exits)
    return CurrentPoolDecision(evidence, result)

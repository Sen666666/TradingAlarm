# Research-only copy. Exact original reservation arithmetic; only explicit purpose whitelist extended.
def reserve_budget(self, *, quote: DecisionQuote, clock: admission.Clock, gross_budget_cny,
                   purpose='initial', target_shares_cap: int | None = None,
                   candidate_id: str | None = None,
                   reservation_at: datetime | None = None) -> tuple[bool, str]:
    """Freeze gross budget and share cap; fees are a separate cash reservation.

    B0 may call this with explicit annual_rebalance targets; this function
    neither creates B0 targets nor imposes strategy 6-slot allocation on B0.
    """
    at = clock.decision_at
    if reservation_at is not None:
        aware(reservation_at)
        if purpose != 'annual_rebalance' or reservation_at < at:
            raise ValueError('Only frozen annual targets may wait for later funding')
    self._time(reservation_at or at)
    sid = quote.security_id
    if purpose not in ('initial', 'annual_rebalance', 'risk_restore'):
        raise ValueError('Unsupported order purpose')
    if sid in self.positions:
        pos = self.positions[sid]
        if (quote.issuer_id, quote.sector_id, quote.currency) != (pos.issuer_id, pos.sector_id, pos.currency):
            raise ValueError('Order identity/currency disagrees with existing inventory')
    if sid in self.buys or sid in self.exits or (purpose == 'initial' and self.quantity(sid)):
        return False, 'existing_position_or_order'
    price, fx = quote.read_price(at), quote.fx.read(at)
    cap = max(ZERO, min(dec(gross_budget_cny), self.available))
    # Solve gross cash + explicit estimated fees <= available, to one CNY cent.
    low, high = 0, int((cap*100).to_integral_value(rounding=ROUND_FLOOR))
    while low < high:
        mid = (low+high+1)//2
        budget = Decimal(mid)/100
        fee = sum(quote.fees.incremental('buy', budget/fx, {}, {}, self.cost_multiplier,
                  shares=budget/(price*fx), par_value=quote.par_value).values(), ZERO)*fx
        if budget+fee <= self.available:
            low = mid
        else:
            high = mid-1
    budget = Decimal(low)/100
    maximum = int(budget/(price*fx))
    if target_shares_cap is not None:
        if type(target_shares_cap) is not int or target_shares_cap < 0:
            raise ValueError('Explicit nonnegative integer target cap required')
        maximum = min(maximum, target_shares_cap)
    target = quote.quantity.buy_floor(maximum)
    if not target:
        return False, 'insufficient_budget_or_quantity'
    fee = sum(quote.fees.incremental('buy', budget/fx, {}, {}, self.cost_multiplier,
              shares=budget/(price*fx), par_value=quote.par_value).values(), ZERO)*fx
    order = BuyOrder(self._id('buy', sid), quote, at, clock.earliest_execution_at,
                     budget, budget, fee, target, target, self.delay_events, purpose)
    if sid in self.daily_delay_credit:
        order.delay_remaining = 0
    order.candidate_id = candidate_id or f'{purpose}:{sid}:{at.isoformat()}'
    self.available -= budget+fee
    self.buys[sid] = order
    self.audit_log.append(dict(kind='reserve', at=reservation_at or at, decision_at=at,
                              sid=sid, order_id=order.order_id,
                              gross_budget_cny=budget, fee_reserved_cny=fee,
                              target_shares=target, purpose=purpose,
                              candidate_id=order.candidate_id,
                              quote_source=quote.source_id, fee_schedule=quote.fees.schedule_id))
    return True, order.order_id

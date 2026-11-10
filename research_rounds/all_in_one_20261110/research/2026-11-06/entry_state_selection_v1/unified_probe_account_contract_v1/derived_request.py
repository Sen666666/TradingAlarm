def request(self, oid, stock, sector, qty, limit, floor, stock_token=None,
            bar=0, fee_per_share=0., *, probe_request=False, role='core',
            order_expiry_bar=None,
            core_epoch_locked=False):
    assert qty > 0 and limit > 0 and 0 <= floor <= limit and fee_per_share >= 0
    assert role in ('core', 'mobile')
    if order_expiry_bar is None: order_expiry_bar = bar
    assert order_expiry_bar >= bar
    if oid in self.orders or oid in self.stock_requests:
        return 'duplicate_request'
    self.stock_requests.add(oid)  # Failed request is not silently replayed every day.
    s = self.sectors[sector]
    if not s.active: return 'industry_invalidated'
    if probe_request and role == 'core' and core_epoch_locked: return 'core_epoch_locked'
    pool = 'probe' if probe_request else 'confirmed'
    if not probe_request and s.level == 0: return 'explicit_probe_request_required'
    if not probe_request and role != 'mobile': return 'mobile_role_required'
    if role == 'mobile':
        if stock_token is None:
            return 'no_fresh_stock_signal'
        if not self.valid(stock_token, 'stock_cp1', bar) or stock_token.confirmed_time != bar or stock_token.sector != sector or stock_token.stock != stock or stock_token.event_id in self.consumed:
            return 'no_fresh_stock_signal'
        self.consumed.add(stock_token.event_id)
    if pool == 'confirmed':
        if not self.confirmed_stock_ready(stock, sector, stock_token, bar):
            return 'confirmed_unfunded'
    if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget and (pool == 'probe' or self.exhausted_policy == 'all_new_risk'):
        if pool == 'confirmed': s.status = 'confirmed_unfunded'
        return 'shared_loss_exhausted'
    cap, risk = qty*limit, qty*(limit-floor)
    pc, pr, _ = self.resources(pool)
    sc, sr, _ = self.resources(sector=sector)
    _, ar, reserve = self.resources()
    pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
                       if o.status in ('open', 'cancel_pending'))
    # Known execution fees cannot make an at-cap reservation violate its own cap on fill.
    budget_nav = self.nav - pending_fees - qty*fee_per_share
    failures = []
    if reserve + qty*(limit+fee_per_share) > self.cash + 1e-9: failures.append('cash')
    if pool == 'probe' and pc+cap > 0.10*budget_nav + 1e-9: failures.append('pool_capital')
    if pool == 'probe' and pr+risk > .005*budget_nav + 1e-9: failures.append('probe_risk')
    sector_fraction = .02 if probe_request else (0.02, 0.10, 0.20)[s.level]
    if sc+cap > sector_fraction*budget_nav + 1e-9: failures.append('sector_capital')
    if sr+risk > .01*budget_nav + 1e-9: failures.append('sector_risk')
    if failures:
        if pool == 'confirmed': s.status = 'confirmed_unfunded'
        return ','.join(failures)
    self.prices.setdefault(stock, limit)
    self.orders[oid] = Order(oid, stock, sector, s.episode, pool, qty, limit, floor, fee_per_share)
    self.orders[oid].role = role
    self.orders[oid].created_bar, self.orders[oid].expiry_bar = bar, order_expiry_bar
    self.orders[oid].attempt = s.attempt
    return 'reserved'


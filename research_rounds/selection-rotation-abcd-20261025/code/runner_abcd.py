"""Finite first10 historical event loop over one frozen shared data package.

No download, algorithm calculation, search, or live order capability. Production
requires the declared closeout/protocol receipts. Synthetic tests use the same
event loop with an explicitly synthetic Bundle and market provider.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, is_dataclass, fields, replace
from datetime import datetime, time, timedelta
from decimal import Decimal
import hashlib
import gzip
import json
import math
from pathlib import Path

import pandas as pd

from current_pool_bridge import (TZ, checked_ref, load_bundle, load_prepared_states,
                                 read_raw, read_actions, eligible_prices, boolean_column, sha256)
import sector_stock_admission as admission
from selection_abcd import decide_current_pool
import selection_abcd
from rotation_abcd import Controller
from sector_account import (SectorAccount, DecisionQuote, Mark, FillWindow, FXQuote,
                            QuantityRule, FeeComponent, FeeSchedule, commit_cutoff, dec)
from b0_rebalance import B0Controller
from run_first10 import validate
from specs_abcd import first10_specs
from market_rules import version_on, market_identity_on, RuleUnavailable


def iso(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Execution calendar timestamps must include timezone')
    return result


def encoded(value):
    if is_dataclass(value):
        return {field.name: encoded(getattr(value,field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(k): encoded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [encoded(v) for v in value]
    if isinstance(value, (datetime, Decimal, Path)):
        return str(value)
    return value


def validate_calendar(cutoffs, sessions):
    if len(set(cutoffs)) != len(cutoffs):
        raise ValueError('Duplicate decision cutoffs')
    for market, opens in sessions.items():
        days = [x.astimezone(TZ).date() for x in opens]
        if len(set(opens)) != len(opens) or len(set(days)) != len(days):
            raise ValueError('Calendar requires one unique open per local day: '+market)


def prepared_directory(manifest_path):
    path = Path(manifest_path).resolve()
    if path.name != 'manifest.json':
        raise ValueError('Prepared manifest must be the exact manifest.json loaded by the bridge')
    return path.parent


class FrozenMarket:
    """Thin explicit manifest provider; rules/proxies are supplied, never inferred."""
    def __init__(self, bundle, rules, fx_rows, protocol):
        self.bundle, self.rules, self.protocol = bundle, rules, protocol
        self.lines = {x.security_id: x for x in bundle.lines}
        self.cutoffs = tuple(sorted(iso(x) for x in rules['decision_cutoffs']))
        self.sessions = {m: tuple(sorted(iso(x) for x in times)) for m, times in rules['calendars'].items()}
        validate_calendar(self.cutoffs, self.sessions)
        self.fx = {}
        for row in fx_rows:
            q = FXQuote(dec(row['cny_per_local']), iso(row['known_at']), row['source_id'])
            self.fx.setdefault(row['currency'], []).append(q)
        for currency in self.fx:
            self.fx[currency].sort(key=lambda q: q.known_at)
        self._fx_times = {c: [q.known_at for q in rows] for c, rows in self.fx.items()}
        self._fx_cache = {}
        self.raw, self.actions, self.notices = {}, {}, []
        self._notice_keys = {}
        for sid, line in self.lines.items():
            record = bundle.series[sid].record
            if record.get('status') != 'ready':
                self.notices.append(dict(sid=sid, reason=record.get('blocked_reason', 'raw_not_ready')))
                continue
            path = checked_ref(record['raw'], bundle.manifest_path.parent)
            frame = read_raw(path, record)
            # Keep the source rows for execution diagnostics; marks use valid prices.
            valid = eligible_prices(frame)
            frame['valid_price'] = frame.index.isin(valid.index)
            frame['observed_bar'] = boolean_column(frame, 'observed_bar', True)
            self.raw[sid] = frame
            if record['kind'] == 'stock':
                events, _ = read_actions(record, bundle.manifest_path.parent)
                self.actions[sid] = events

    def notice(self, row):
        key = row.get('sid'), row.get('side'), row['reason']
        if key in self._notice_keys:
            saved = self._notice_keys[key]
            saved['count'] += 1
            saved['last_at'] = row.get('at')
        else:
            row = dict(row, count=1, first_at=row.get('at'), last_at=row.get('at'))
            self._notice_keys[key] = row
            self.notices.append(row)

    def currency(self, sid):
        return self.bundle.series[sid].record['currency']

    def rate(self, currency, at):
        if currency == 'CNY':
            return FXQuote(dec(1), at, 'CNY-unit-identity')
        if (currency, at) in self._fx_cache:
            return self._fx_cache[currency, at]
        rows = self.fx.get(currency, ())
        i = bisect_right(self._fx_times.get(currency, ()), at)-1
        if i < 0:
            raise RuleUnavailable('No already-known ' + currency + ' FX')
        quote = rows[i]
        if at-quote.known_at > timedelta(days=self.protocol['fx_max_age_days']):
            raise RuleUnavailable('Stale ' + currency + ' FX')
        self._fx_cache[currency, at] = quote
        return quote

    def currency_fx(self, at):
        result = {'CNY': self.rate('CNY', at)}
        for currency in self.fx:
            try:
                result[currency] = self.rate(currency, at)
            except RuleUnavailable:
                pass
        return result

    def _version(self, key, identity, at):
        date = at.astimezone(TZ).date().isoformat()
        return version_on(self.rules.get(key, {}).get(identity, ()), date,
                          self.protocol['approved_proxy_ids'])

    def source_available(self, sid, at):
        record = self.bundle.series[sid].record
        day = at.astimezone(TZ).date().isoformat()
        if record.get('unavailable_from') and day >= record['unavailable_from']:
            raise RuleUnavailable('Declared source unavailable from '+record['unavailable_from']+': '+sid)
        parts = record.get('segments', ())
        if any(left['end'] < day < right['start'] for left, right in zip(parts, parts[1:])):
            raise RuleUnavailable('Declared source discontinuity: '+sid)

    def quantity(self, sid, at):
        return QuantityRule(**self._version('quantity_versions', sid, at)['rule'])

    def fees(self, sid, at):
        identity = market_identity_on(self.rules, sid, at.astimezone(TZ).date(),
                                      self.protocol['approved_proxy_ids'])
        # A/H is not a fee venue. No broad-market fallback can erase historical
        # SSE/SZSE/BSE differences or turn today's suffix into historical identity.
        schedule = self._version('fee_versions', identity['venue'], at)['schedule']
        return FeeSchedule(schedule['schedule_id'], tuple(FeeComponent(**x) for x in schedule['components']))

    def market_buyable(self, at):
        result = {}
        for sid in self.lines:
            try:
                self.source_available(sid, at)
                market_identity_on(self.rules, sid, at.astimezone(TZ).date(),
                                   self.protocol['approved_proxy_ids'])
                row = self._version('availability_versions', sid, at)
                value = row['buy_allowed']
                if value is not None and type(value) is not bool:
                    raise ValueError('Availability must be a boolean or unknown')
                source = row['source_id']
            except RuleUnavailable as exc:
                value, source = None, str(exc)
            result[sid] = admission.Fact(value, at, at, source_id=source)
        return result

    def latest_mark(self, sid, at):
        self.source_available(sid, at)
        frame = self.raw.get(sid)
        if frame is None:
            raise RuleUnavailable('Raw mark unavailable: ' + sid)
        record = self.bundle.series[sid].record
        cutoff = at.astimezone(TZ).date()
        pos = frame.index.searchsorted(pd.Timestamp(cutoff), side='right')-1
        for i in range(pos, -1, -1):
            date, row = frame.index[i], frame.iloc[i]
            if not bool(row.get('observed_bar', True)):
                continue
            close_at = datetime.combine(date.date(), time.fromisoformat(record['close_available_time']), TZ)
            if close_at <= at:
                if not bool(row.valid_price):
                    continue
                price, known = dec(row.close), close_at
            else:
                opens = [x for x in self.sessions[self.lines[sid].market]
                         if x.astimezone(TZ).date() == date.date() and x <= at]
                # The current open is observable independently of future H/L/C.
                if not opens or not pd.notna(row.open) or not math.isfinite(row.open) or row.open <= 0:
                    continue
                price, known = dec(row.open), opens[0]
            source = record['raw']['sha256']
            intervening = [e for e in self.actions.get(sid, ())
                if date.date().isoformat() < e['effective_date'] <= cutoff.isoformat()]
            if intervening:
                if self.protocol.get('stale_action_mark_policy') != 'theoretical_ex_reference':
                    raise RuleUnavailable('Stale pre-action price requires an explicit valuation policy: '+sid)
                for event in sorted(intervening, key=lambda e:e['effective_date']):
                    price = (price-dec(event.get('signal_cash_per_old_share',event['cash_per_old_share'])))/dec(event.get('signal_split_ratio',event['split_ratio']))
                    source += ':derived_ex_reference:'+event['effective_date']+':'+event['source_id']
                if price <= 0:
                    raise RuleUnavailable('Nonpositive derived ex-action valuation reference: '+sid)
                # Keep the actual raw observation time. The source explicitly
                # records the subsequent unit transforms, never a tradable quote.
            return Mark(price, known, self.rate(record['currency'], at), source)
        raise RuleUnavailable('No already-observed price prefix: ' + sid)

    def marks(self, at, ids):
        return {sid: self.latest_mark(sid, at) for sid in ids}

    def quotes(self, at, ids=None):
        result = {}
        for sid in ids if ids is not None else self.lines:
            line = self.lines[sid]
            if ids is None and not (line.current_stock is True and line.company_cap_cny is not None
                    and line.company_cap_cny > 10_000_000_000
                    and (line.market == 'A' or line.southbound_selected is True)):
                continue
            if line.issuer_id is None or line.sector_id is None:
                continue
            try:
                mark = self.latest_mark(sid, at)
                meta = self.rules.get('security_metadata', {}).get(sid, {})
                result[sid] = DecisionQuote(sid, line.issuer_id, line.sector_id, self.currency(sid),
                    mark.raw_price, mark.known_at, mark.fx, self.quantity(sid, at), self.fees(sid, at),
                    mark.source_id, meta.get('par_value'))
            except RuleUnavailable as exc:
                self.notice(dict(at=at, sid=sid, reason=str(exc)))
        return result

    def lag(self, market, at, count):
        if type(count) is not int or count < 0:
            raise ValueError('Explicit nonnegative session lag required')
        if count == 0:
            return at
        # Corporate actions can occur before this market's open; a session lag
        # counts later trading dates, not a later opening on the same date.
        later = [x for x in self.sessions[market]
                 if x.astimezone(TZ).date() > at.astimezone(TZ).date()]
        if count > len(later):
            raise RuleUnavailable('Execution calendar does not cover settlement/sellability')
        return later[count-1]

    def window(self, sid, at, side, cost_multiplier):
        market = self.lines[sid].market
        if at not in self.sessions[market]:
            return None
        try:
            self.source_available(sid, at)
        except RuleUnavailable as exc:
            self.notice(dict(at=at, sid=sid, side=side, reason=str(exc)))
            return None
        frame = self.raw.get(sid)
        date = pd.Timestamp(at.astimezone(TZ).date())
        if frame is None or date not in frame.index:
            return None
        row = frame.loc[date]
        if not bool(row.valid_price) or not pd.notna(row.volume) or row.volume <= 0:
            return None
        prior = frame.loc[frame.index < date, 'volume'].dropna()
        prior = prior[prior > 0].tail(20)
        if len(prior) < 20:
            return None
        try:
            market_identity_on(self.rules, sid, at.astimezone(TZ).date(),
                               self.protocol['approved_proxy_ids'])
            availability = self._version('availability_versions', sid, at)
            buy, sell = availability.get('buy_allowed'), availability.get('sell_allowed')
            policy = self.protocol['daily_execution'][market]
            guard = policy['price_limit_policy']
            if guard == 'external_columns':
                if pd.isna(row.get('limit_up')) or pd.isna(row.get('limit_down')):
                    buy = sell = None
                else:
                    buy = bool(buy and row.open < row.limit_up)
                    sell = bool(sell and row.open > row.limit_down)
            elif guard not in ('no_price_limits', 'conservative_hl_proxy'):
                raise ValueError('Unknown frozen price-limit policy')
            if policy['reject_flat_day'] and row.high <= row.low:
                buy = sell = False
            capacity = int(min(prior.mean()*float(self.protocol['participation_rate']), row.volume))
            slip = dec(policy['slippage_bps'])/10000
            if cost_multiplier == 2 and policy['stress_slippage']:
                slip *= 2
            price = dec(row.open)*(1+slip if side == 'buy' else 1-slip)
            return FillWindow(f'{sid}:{at.isoformat()}:{side}', sid, at, dec(row.open), price,
                self.rate(self.currency(sid), at), self.quantity(sid, at), self.fees(sid, at),
                capacity, True, buy, sell,
                self.lag(market, at, self.protocol['sellable_lag_sessions'][market]),
                self.lag(market, at, self.protocol['settlement_lag_sessions'][market]),
                self.bundle.series[sid].record['raw']['sha256'],
                'explicit_daily_bar_proxy_past20_capacity_same_day_hlv_postcheck',
                self.rules.get('security_metadata', {}).get(sid, {}).get('par_value'))
        except RuleUnavailable as exc:
            self.notice(dict(at=at, sid=sid, side=side, reason=str(exc)))
            return None


def passive_eligible(inputs, quotes):
    """Same fixed/data universe as strategies, with no stock/sector trend gate."""
    historical = {x.security_id: x for x in inputs.historical}
    result = {}
    for line in inputs.lines:
        h = historical[line.security_id]
        selected = (line.current_stock is True and line.company_cap_cny is not None
                    and line.company_cap_cny > 10_000_000_000 and line.issuer_id is not None
                    and line.sector_id is not None
                    and (line.market == 'A' or line.southbound_selected is True))
        if (selected and h.common_ready.read(inputs.clock) is True
                and h.market_buyable.read(inputs.clock, for_execution=True) is True
                and line.security_id in quotes):
            result[line.security_id] = quotes[line.security_id]
    return result


class HistoryRunner:
    def __init__(self, bundle, market, *, start, end, synthetic=False, sink=None):
        self.bundle, self.market, self.start, self.end = bundle, market, start, end
        self.synthetic = synthetic
        self.sink = sink
        self.specs = first10_specs()
        self.accounts = {s.account_id: SectorAccount(initial_cash=s.initial_capital_cny,
             cost_multiplier=s.stress.variable_components_multiplier,
             delay_events=s.stress.extra_executable_events,
             max_sectors=s.allocation.max_sectors if s.variant!="B0" else 3,
             max_issuers_per_sector=s.allocation.max_issuers_per_sector if s.variant!="B0" else 2,
             fractional_split_policy=market.protocol.get('fractional_split_policy','reject')) for s in self.specs}
        self.memory = {s.account_id: () for s in self.specs if s.variant != 'B0'}
        self.started, self.exit_cursor, self.priority = set(), {}, {}
        self.controllers = {s.account_id: Controller() for s in self.specs if s.account_id.startswith(("C__","D__"))}
        self.b0 = B0Controller()
        self.b0_year = None
        self.daily, self.decisions, self.limitations = [], [], []
        self.last_daily, self.daily_rows = {}, 0
        self.applied_actions = set()
        self.actions_by_date = {}
        for sid, events in self.market.actions.items():
            for n, event in enumerate(events):
                self.actions_by_date.setdefault(event['effective_date'], []).append((sid, n, event))

    def _actions(self, at):
        for sid, n, event in self.actions_by_date.get(at.astimezone(TZ).date().isoformat(), ()):
                day = event['effective_date']
                key = sid, n
                if day != at.astimezone(TZ).date().isoformat() or key in self.applied_actions:
                    continue
                cash, ratio = dec(event['cash_per_old_share']), dec(event['split_ratio'])
                for account_id, account in self.accounts.items():
                    old = account.quantity(sid)
                    if old and event.get('classification') in ('rights_issue_no_subscription','targeted_non_pro_rata_issuance'):
                        account.audit_log.append(dict(kind=event['classification'],at=at,sid=sid,
                            source_id=event['source_id'],holder_shares_unchanged=old,
                            no_cash_or_extra_shares_invented=True,terms=event))
                    if old and cash:
                        currency = self.market.currency(sid)
                        # Required, named protocol proxy; not silently gross==net.
                        factor = dec(self.market.protocol['dividend_net_factor'][self.market.lines[sid].market])
                        paid = iso(event['paid_at']) if event.get('paid_at') else None
                        account.accrue_dividend(event_id=f'dividend:{sid}:{day}', sid=sid, currency=currency,
                            net_local=old*cash*factor, ex_at=at, paid_at=paid, source_id=event['source_id'],
                            entitlement_basis='protocol_previous_close_inventory_and_explicit_net_factor')
                    if ratio != 1 and (old or sid in account.buys or sid in account.exits):
                        sellable = (iso(event['new_shares_sellable_at']) if event.get('new_shares_sellable_at')
                            else self.market.lag(self.market.lines[sid].market, at,
                                self.market.protocol['bonus_sellable_lag_sessions'][self.market.lines[sid].market]))
                        account.split(event_id=f'split:{sid}:{day}', sid=sid, ratio=ratio,
                                      at=at, new_shares_sellable_at=sellable)
                if ratio != 1:
                    self.b0.apply_split(sid, ratio,fractional_policy=self.market.protocol.get('fractional_split_policy','reject'))
                self.applied_actions.add(key)

    def _payments(self, account, at):
        for event_id, entitlement in list(account.dividends.items()):
            if entitlement.paid_at is not None and entitlement.paid_at <= at:
                account.pay_dividend(event_id, at=at, fx=self.market.rate(entitlement.currency, at),
                    payment_evidence_id=entitlement.source_id+':declared-payment-field',
                    payment_known_at=entitlement.paid_at)

    def _advance_b0(self, account, at, buyable):
        now_clock = admission.Clock(at, at+timedelta(microseconds=1), at.astimezone(TZ).date())
        values = {sid: fact.read(now_clock) for sid, fact in buyable.items()}
        return self.b0.advance(account, at, values, marks=self.market.marks(at, account.positions),
                               currency_fx=self.market.currency_fx(at))

    def run(self):
        if not self.synthetic and self.sink is None:
            raise ValueError('Production requires a streaming result sink')
        cutoffs = [x for x in self.market.cutoffs if self.start <= x <= self.end]
        opens = {x for sessions in self.market.sessions.values() for x in sessions if self.start <= x <= self.end}
        action_times = {datetime.combine(datetime.fromisoformat(day).date(), time.min, TZ)
                        for day in self.actions_by_date}
        all_events = sorted(set(cutoffs) | opens |
                            {x for x in action_times if self.start <= x <= self.end})
        if not cutoffs:
            raise ValueError('No common decision cutoffs in the account interval')
        if self.end != cutoffs[-1]:
            raise ValueError('Account end must be the final common decision cutoff')
        all_opens = sorted({x for values in self.market.sessions.values() for x in values})
        for at in all_events:
            for account in self.accounts.values():
                account.settle_due(at)
            self._actions(at)
            for account in self.accounts.values():
                self._payments(account, at)
            if at in opens:
                for spec in self.specs:
                    account = self.accounts[spec.account_id]
                    for sid in tuple(sorted(account.exits)):
                        window = self.market.window(sid, at, 'sell', account.cost_multiplier)
                        if window:
                            account.fill_exit(sid, window)
                    account.settle_due(at)
                    if spec.variant == 'B0' and self.b0_year is not None:
                        self._advance_b0(account, at, self.market.market_buyable(at))
                    priority = self.priority.get(spec.account_id, ())
                    queue = sorted(account.buys, key=lambda sid: (
                        not bool(account.buys[sid].filled_shares),
                        priority.index(sid) if sid in priority else len(priority), sid))
                    for sid in queue:
                        window = self.market.window(sid, at, 'buy', account.cost_multiplier)
                        if window:
                            account.fill_buy(sid, window)
                    account.settle_due(at)
            if at not in cutoffs:
                continue
            nxt = bisect_right(all_opens, at)
            # The last decision may retain positions; require a declared future
            # calendar event, never invent a final forced liquidation.
            if nxt >= len(all_opens):
                raise ValueError('Calendar must extend beyond last decision cutoff')
            clock = admission.Clock(at, all_opens[nxt], at.astimezone(TZ).date())
            buyable = self.market.market_buyable(at)
            inputs = self.bundle.at_decision(clock, market_buyable=buyable)
            if clock.session_date.month == 1 and clock.session_date.day <= 7:
                print(json.dumps({'progress_date':str(clock.session_date),'accounts':len(self.specs)},ensure_ascii=False),flush=True)
            quotes = self.market.quotes(at)
            # Include disposal-only lines that no longer satisfy the fixed pool.
            held_ids = {sid for account in self.accounts.values() for sid in account.positions}
            quotes.update(self.market.quotes(at, held_ids))
            currency_fx = self.market.currency_fx(at)
            for spec in self.specs:
                account = self.accounts[spec.account_id]
                marks = self.market.marks(at, account.positions)
                if spec.variant == 'B0':
                    if self.b0_year != clock.session_date.year:
                        self.b0.begin_year(account, clock, passive_eligible(inputs, quotes), marks,
                                           currency_fx=currency_fx, holding_quotes=quotes)
                        self.b0_year = clock.session_date.year
                    self._advance_b0(account, at, buyable)
                else:
                    expired = account.expire_day_buys(at)
                    self.memory[spec.account_id] = tuple(replace(m, waiting=True, created_at=at, origin='expired_unfilled_recompetition') if m.security_id in expired else m for m in self.memory[spec.account_id])
                    mode = spec.account_id.split('__',1)[0]
                    selection_abcd.set_account(mode)
                    rotation = None
                    if spec.account_id in self.controllers:
                        ctrl = self.controllers[spec.account_id]
                        rotation = ctrl.advance(account, inputs, clock, mode, quotes, marks, currency_fx)
                        selection_abcd.set_account(mode, ctrl.banned_stocks, ctrl.banned_sectors)
                    def factory(**kwargs):
                        return decide_current_pool(evidence=inputs.evidence, lines=inputs.lines,
                            historical=inputs.historical, sectors=inputs.sectors,
                            clock=clock, variant=spec.variant, entry_mode=spec.account_id.split("__",1)[0], **kwargs).decision
                    cursor = self.exit_cursor.get(spec.account_id, 0)
                    ack = commit_cutoff(account, decision_factory=factory, clock=clock, quotes=quotes,
                        marks=marks, currency_fx=currency_fx, previous=self.memory[spec.account_id],
                        bootstrap=spec.account_id not in self.started,
                        completed_exits=tuple(account.completed[cursor:]))
                    self.exit_cursor[spec.account_id] = len(account.completed)
                    self.memory[spec.account_id] = ack.memories
                    account.daily_delay_credit.clear()
                    self.started.add(spec.account_id)
                    self.priority[spec.account_id] = tuple(dict.fromkeys(
                        tuple(ack.decisions[-1].continue_buys)+ack.accepted))
                    decision_row = dict(account=spec.account_id, at=at, ack=ack, rotation=rotation)
                    if self.sink:
                        self.sink.emit('decisions', decision_row)
                    else:
                        self.decisions.append(decision_row)
                balance = account.balance(at, marks, currency_fx)
                daily_row = dict(account=spec.account_id, at=at, **balance,
                    positions={sid: p.shares for sid, p in account.positions.items()},
                    mark_observed_at={sid: m.known_at for sid, m in marks.items()},
                    mark_source_id={sid: m.source_id for sid, m in marks.items()},
                    pending_buys=tuple(account.buys), pending_sells=tuple(account.exits))
                self.last_daily[spec.account_id] = daily_row
                self.daily_rows += 1
                if self.sink:
                    self.sink.emit('daily', daily_row)
                else:
                    self.daily.append(daily_row)
        return dict(research_basis='current_pool_historical_development',
            synthetic=self.synthetic, historical_account_runs=0 if self.synthetic else len(self.specs),
            technical_accounts=len(self.specs) if self.synthetic else 0, initial_capital_cny=1000000,
            accounts=[s.account_id for s in self.specs], daily_rows=self.daily_rows,
            final_nav={s.account_id: str(self.last_daily[s.account_id]['nav']) for s in self.specs},
            limitations=self.limitations+self.market.notices,
            execution_basis='explicit_daily_proxy_and_frozen_known_fx_settlement',
            final_positions_closed=False)

    def write(self, output, summary, provenance):
        output = Path(output)
        if self.sink is None:
            output.mkdir(parents=True, exist_ok=False)
            for name, rows in [('daily', self.daily), ('decisions', self.decisions)]:
                with (output/(name+'.jsonl')).open('w') as stream:
                    for row in rows:
                        stream.write(json.dumps(encoded(row), ensure_ascii=False, allow_nan=False)+'\n')
        for account_id, account in self.accounts.items():
            data = dict(fills=account.fills, audit_log=account.audit_log,
                        outstanding_dividends=account.dividends, settlements=account.settlements,
                        completed_exits=account.completed)
            (output/(account_id+'.json')).write_text(json.dumps(encoded(data), ensure_ascii=False, indent=2)+'\n')
        (output/'summary.json').write_text(json.dumps(encoded(summary), ensure_ascii=False, indent=2)+'\n')
        (output/'provenance.json').write_text(json.dumps(encoded(provenance), ensure_ascii=False, indent=2)+'\n')
        (output/'B0_annual_targets.json').write_text(json.dumps(encoded(self.b0.audit_log), ensure_ascii=False, indent=2)+'\n')


class StreamingSink:
    def __init__(self, output):
        self.path = Path(output)
        self.path.mkdir(parents=True, exist_ok=False)
        self.streams = {name:gzip.open(self.path/(name+'.jsonl.gz'),'wt',encoding='utf-8',compresslevel=1)
                        for name in ('daily','decisions')}

    def emit(self, name, row):
        self.streams[name].write(json.dumps(encoded(row),ensure_ascii=False,allow_nan=False)+'\n')

    def close(self):
        for stream in self.streams.values():
            stream.close()


def run_frozen_package(path, output):
    """Production entry: all explicit frozen inputs must exist and match hashes."""
    path = Path(path).resolve()
    if Path(output).exists():
        raise ValueError('A new result directory is required; existing evidence cannot be overwritten')
    package = json.loads(path.read_text())
    base = path.parent
    if package.get('schema_version') != 1 or package.get('mode') != 'frozen_A13_historical':
        raise ValueError('Explicit frozen first10 package required')
    scope = checked_ref(package['scope'], base)
    data_closeout = checked_ref(package['data_closeout'], base)
    protocol_receipt = checked_ref(package['economic_protocol_frozen'], base)
    validate(data_closeout=data_closeout, economic_protocol_frozen=protocol_receipt, scope=scope)
    protocol_path = checked_ref(package['economic_protocol'], base)
    receipt = json.loads(protocol_receipt.read_text())
    bound = {str((protocol_receipt.parent/p).resolve()): h for p, h in receipt['artifacts'].items()}
    if bound.get(str(protocol_path.resolve())) != sha256(protocol_path):
        raise ValueError('Economic receipt must explicitly bind this exact protocol')
    protocol = json.loads(protocol_path.read_text())
    if protocol.get('status') != 'frozen' or protocol.get('algorithm_changes') != 0:
        raise ValueError('Frozen unchanged-algorithm protocol required')
    inputs = {name: checked_ref(package[name], base) for name in
              ('bridge_manifest','prepared_manifest','market_rules','fx_quotes')}
    for name, file in inputs.items():
        if bound.get(str(file.resolve())) != sha256(file):
            raise ValueError('Economic freeze receipt does not bind actual '+name)
    # Source data closes before bridge/state production. The later economic
    # freeze binds the prepared artifacts, avoiding a circular content hash.
    bridge_declaration = json.loads(inputs['bridge_manifest'].read_text())
    bridge_closeout = checked_ref(bridge_declaration['data_pool_closeout'],
                                 inputs['bridge_manifest'].parent)
    if bridge_closeout.resolve() != data_closeout.resolve():
        raise ValueError('Bridge and runner must use the same data closeout receipt')
    if (iso(package['start']) != iso(protocol['account_start'])
            or iso(package['end']) != iso(protocol['account_end'])):
        raise ValueError('Account dates differ from the frozen economic protocol')
    for filename in ('history_runner.py','sector_account.py','current_fixed_pool.py',
                     'run_first10.py','b0_rebalance.py','market_rules.py'):
        if protocol['code_sha256'].get(filename) != sha256(Path(__file__).parent/filename):
            raise ValueError('Execution code differs from freeze: '+filename)
    bundle = load_bundle(inputs['bridge_manifest'])
    prepared = prepared_directory(inputs['prepared_manifest'])
    load_prepared_states(bundle, prepared)
    if not bundle.signal_ready and not protocol.get('allow_explicit_unknown_series', False):
        raise ValueError('Unresolved series require an explicit common coverage limitation in the protocol')
    rules = json.loads(inputs['market_rules'].read_text())
    fx_rows = json.loads(inputs['fx_quotes'].read_text())['quotes']
    market = FrozenMarket(bundle, rules, fx_rows, protocol)
    sink = StreamingSink(output)
    runner = HistoryRunner(bundle, market, start=iso(package['start']), end=iso(package['end']),sink=sink)
    provenance = dict(package=str(path), package_sha256=sha256(path),
        runner_sha256=sha256(__file__), protocol_sha256=sha256(protocol_path),
        shared_bridge_manifest_sha256=sha256(bundle.manifest_path),
        shared_prepared_manifest_sha256=sha256(prepared/'manifest.json'),
        account_specs=[asdict(x) for x in runner.specs])
    try:
        summary = runner.run()
    except Exception as exc:
        runner.write(output, dict(status='failed_partial_run',error=type(exc).__name__+': '+str(exc),
            historical_account_runs_started=len(runner.specs), completed_accounts=0),provenance)
        raise
    else:
        runner.write(output, summary, provenance)
    finally:
        sink.close()
    return summary

"""Persistent, isolated ACT20 paper account. Execution is at the next raw open.

Close decisions are immutable. Open executions and their outcomes commit in one
SQLite transaction, so crashes/restarts cannot duplicate or change a fill.
"""
import copy
import json
import threading
import time
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import pandas as pd

from .data import clean, TZ
from .store import Store, journal, lot_sellable, now
from .strategy import build_report


class PaperStore(Store):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS paper_days(day TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_executions(decision_day TEXT PRIMARY KEY, execution_day TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_quotes(day TEXT NOT NULL, symbol TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(day,symbol));
            ''')

    def days(self):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute('SELECT payload FROM paper_days ORDER BY day')]

    def executions(self):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute('SELECT payload FROM paper_executions ORDER BY execution_day')]

    def quote(self, day, symbol):
        with self.connect() as c:
            r = c.execute('SELECT payload FROM paper_quotes WHERE day=? AND symbol=?', (day, symbol)).fetchone()
            return json.loads(r[0]) if r else None

    def put_quotes(self, day, quotes):
        with self.connect() as c:
            for sid, quote in quotes.items():
                if quote['day'] != day or quote['symbol'] != sid:
                    raise ValueError('开盘资料的日期或股票不匹配')
                c.execute('INSERT OR IGNORE INTO paper_quotes VALUES(?,?,?)', (day, sid, json.dumps(clean(quote), ensure_ascii=False, allow_nan=False)))


class Paper:
    def __init__(self, runtime, get_data, *, live=False, provider=None):
        self.runtime = Path(runtime)
        self.store = PaperStore(self.runtime/'simulation.sqlite3')
        self.get_data = get_data
        self.live = live
        self.provider = provider
        self.lock = threading.RLock()
        self.job = dict(state='idle', message='等待自动模拟')
        self.last_attempt = 0
        self.signals = {}

    def start(self):
        with self.lock:
            data = self.get_data()
            if not data.integrity['passed']:
                raise ValueError('策略完整性核验未通过，不能启动模拟仓')
            if not self.store.account():
                # The user requested the same current close guidance, not a
                # historical account. The start date is explicit in the UI.
                self.store.initialize('1000000', data.as_of)
                self.store.set_setting('execution_contract', dict(
                    version='PAPER-OPEN-1', strategy='ACT20_BREAK', initial_cash='1000000',
                    price='next_session_unadjusted_open', slippage_bps=0,
                    fees='frozen_reference_schedule', started_from=data.as_of,
                    created_at=now(), fill_assumption='有效开盘即按开盘价模拟；不验证排队成交'))
        self.request_sync()
        return self.view()

    def request_sync(self):
        with self.lock:
            if not self.store.account():
                return dict(state='idle', message='模拟仓尚未建立')
            if self.job['state'] in ('queued', 'running'):
                return dict(self.job)
            self.job = dict(state='queued', message='准备处理收盘决策与下一开盘成交')
            self.last_attempt = time.monotonic()
            threading.Thread(target=self._worker, daemon=True, name='paper-open-sync').start()
            return dict(self.job)

    def _worker(self):
        try:
            self.job = dict(state='running', message='正在核对开盘资料与模拟账本')
            self.sync()
            self.job = dict(state='complete', message='模拟账本已更新', finished_at=now())
        except Exception as exc:
            self.job = dict(state='failed', message='模拟处理暂未完成，将自动重试', error=str(exc)[:300], finished_at=now())
        self.store.set_setting('last_sync', self.job)

    def tick(self):
        if self.store.account() and time.monotonic()-self.last_attempt >= 300:
            self.request_sync()

    def _bar(self, data, sid, day):
        key = (str(data.signals_dir), sid)
        if key not in self.signals:
            self.signals[key] = pd.read_parquet(data.signals_dir/f'{sid}.parquet')
        frame = self.signals[key]
        if pd.Timestamp(day) not in frame.index:
            return None
        r = frame.loc[day]
        if not bool(r.get('observed_bar', True)) or not bool(r.get('price_eligible', True)) or bool(r.get('synthetic_event_bar', False)):
            return None
        px = D(str(r.get('raw_open', r.open)))
        if not px.is_finite() or px <= 0 or not float(r.get('raw_volume', r.volume)) > 0:
            return None
        return dict(symbol=sid, day=day, open=str(px), source='已发布同花顺未复权日线', source_path=str(data.signals_dir/f'{sid}.parquet'), fetched_at=now(), actions=data.actions.get(sid, []))

    def _quotes(self, data, day, symbols, current):
        quotes = {}
        for sid in sorted(symbols):
            cached = self.store.quote(day, sid)
            if cached:
                quotes[sid] = cached
                continue
            if day <= data.as_of:
                bar = self._bar(data, sid, day)
                # A completed, fully published session with no valid observed
                # bar is non-executable. An incomplete fetch is never expiry.
                quotes[sid] = bar or dict(symbol=sid, day=day, open=None, unavailable=True, source='完整收盘资料无有效交易日线', actions=data.actions.get(sid, []))
        missing = sorted(set(symbols)-quotes.keys())
        if missing and (day < current.date().isoformat() or (day == current.date().isoformat() and current.strftime('%H:%M') >= '09:35')):
            if self.provider:
                quotes.update(self.provider(data, day, missing))
            elif self.live:
                from .paper_quotes import fetch_opens
                quotes.update(fetch_opens(data, day, missing, self.runtime))
        self.store.put_quotes(day, quotes)
        return quotes

    @staticmethod
    def _events(c):
        return [dict(r) | {'payload': json.loads(r['payload'])} for r in c.execute('SELECT * FROM events ORDER BY at,created_at,id')]

    def _execute(self, data, report, current):
        day = report['execution_day']
        if not day or day > current.date().isoformat() or (day == current.date().isoformat() and current.strftime('%H:%M') < '09:35'):
            return False
        guides = [g for g in report['instructions'] if g['action'] in ('BUY', 'SELL')]
        account = self.store.account()
        positions = journal(account, self.store.events(), day)['positions']
        symbols = {g['symbol'] for g in guides} | set(positions)
        quotes = self._quotes(data, day, symbols, current)
        if set(symbols)-quotes.keys():
            self.store.set_setting('waiting', dict(day=day, symbols=sorted(set(symbols)-quotes.keys()), reason='等待对应交易日的有效开盘资料；不会改用其他日期价格'))
            return False
        actions = {sid: quotes[sid].get('actions', data.actions.get(sid, [])) for sid in symbols}
        outcomes = []
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM paper_executions WHERE decision_day=?', (report['day'],)).fetchone():
                return True
            events = self._events(c)
            def append(eid, at, kind, payload):
                if any(e['id'] == eid for e in events):
                    return
                e = dict(id=eid, at=at, kind=kind, payload=payload, created_at=datetime.now(TZ).isoformat(timespec='microseconds'))
                journal(account, events+[e])
                c.execute('INSERT INTO events VALUES(?,?,?,?,?)', (eid, at, kind, json.dumps(payload, sort_keys=True, ensure_ascii=False), e['created_at']))
                events.append(e)
            # Ordinary source entitlements are kept as receivables until an
            # actual source payment date is known. Never invent available cash.
            for sid, position in positions.items():
                for a in actions.get(sid, []):
                    if a['effective_date'] != day:
                        continue
                    kind = a['classification']
                    if kind not in ('ordinary_cash_and_pro_rata_bonus', 'rights_issue_no_subscription', 'targeted_non_pro_rata_issuance', 'public_holder_consideration_share_proxy'):
                        raise ValueError('模拟持仓存在尚未支持的权益类型：'+sid)
                    qty = position['shares']; added = int(D(qty)*D(a['split_ratio']))-qty
                    due = D(qty)*D(a['cash_per_old_share'])
                    paid = a.get('paid_at') == day
                    append('corporate:'+sid+':'+day, day+'T08:00:00+08:00', 'corporate', dict(symbol=sid, shares_delta=added, cash_delta=str(due if paid else 0), receivable_delta=str(0 if paid else due), sellable_on=a.get('new_shares_sellable_at') or ('9999-12-31' if added else day), action_key=sid+':'+day, note='模拟源权益；未知到账现金记待收，未知上市日新增股暂不可卖', terms=a))
            for guide in sorted(enumerate(guides), key=lambda x: (x[1]['action'] != 'SELL', x[0])):
                g = guide[1]; sid = g['symbol']; side = g['action'].lower(); quote = quotes[sid]
                result = dict(symbol=sid, name=g['name'], side=side, decision_day=report['day'], execution_day=day, status='skipped', shares=0, price=quote.get('open'), fee='0', reason='', source=quote['source'])
                if quote.get('open') is None:
                    result['reason'] = '无有效开盘，买单到期；卖出等待后续指引' if side == 'buy' else '无有效开盘，退出保留'
                    outcomes.append(result); continue
                price = D(quote['open']); ledger = journal(account, events, day)
                fees = data.rulebook.fees(sid, day)
                if side == 'buy':
                    support = D(str(g['support']))
                    for a in actions.get(sid, []):
                        if a['effective_date'] == day:
                            support = (support-D(a.get('signal_cash_per_old_share', a['cash_per_old_share'])))/D(a.get('signal_split_ratio', a['split_ratio']))
                    result['support'] = str(support)
                    if price <= support:
                        result['reason'] = '开盘价不高于保护位，放弃买入'; outcomes.append(result); continue
                    qty, _, _ = data.rulebook.size(sid, day, price, D(g['max_gross']), D(ledger['cash']))
                    qty = min(qty, g['shares'])
                else:
                    p = ledger['positions'].get(sid, {})
                    qty = sum(l['shares'] for l in p.get('lots', []) if lot_sellable(l, day))
                    qty = data.rulebook.quantity(sid, day).sell_floor(qty, p.get('shares', 0)) if qty else 0
                if not qty:
                    result['reason'] = '预算/现金/最小股数不足' if side == 'buy' else '没有T+1可卖股数'
                    outcomes.append(result); continue
                fee = sum(fees.incremental(side, price*qty, {}, {}, 1, shares=qty, par_value=D(1)).values(), D(0))
                eid = 'paper:'+report['day']+':'+side+':'+sid
                payload = dict(symbol=sid, price=str(price), shares=qty, fee=str(fee), guide_day=report['day'], note='下一交易日实际开盘价自动模拟；零滑点；费用另计', source=quote['source'])
                append(eid, day+'T09:30:00+08:00', side, payload)
                result.update(status='filled', shares=qty, fee=str(fee), gross=str(price*qty), event_id=eid, reason=g['reason'])
                outcomes.append(result)
            receipt = dict(decision_day=report['day'], execution_day=day, processed_at=now(), outcomes=outcomes)
            c.execute('INSERT INTO paper_executions VALUES(?,?,?)', (report['day'], day, json.dumps(clean(receipt), ensure_ascii=False, allow_nan=False)))
        self.store.set_setting('waiting', None)
        return True

    def sync(self, current=None):
        current = current or datetime.now(TZ)
        with self.lock:
            account = self.store.account()
            if not account:
                return
            data = self.get_data()
            if not data.integrity['passed']:
                raise ValueError('策略完整性核验失败，暂停新增模拟成交')
            # Completed closes alone may generate decisions. Intraday opens
            # cannot update rankings, signals, or the close account-risk state.
            cutoff = data.expected_close(current)
            completed = [str(d.date()) for d in data.recovery.index if account['started_on'] <= str(d.date()) <= min(data.as_of, cutoff or '')]
            saved = {r['day']: r for r in self.store.days()}
            executed = {r['decision_day'] for r in self.store.executions()}
            for day in completed:
                previous = max((r for d, r in saved.items() if d < day), key=lambda r: r['day'], default=None)
                if previous and previous['day'] not in executed:
                    if not self._execute(data, previous, current):
                        return
                    executed.add(previous['day'])
                if day not in saved:
                    sliced = copy.copy(data); sliced.as_of = day; sliced.recovery = data.recovery.loc[:day]
                    report = build_report(sliced, account, self.store.events())
                    report['paper'] = True
                    with self.store.connect() as c:
                        c.execute('INSERT OR IGNORE INTO paper_days VALUES(?,?)', (day, json.dumps(clean(report), ensure_ascii=False, allow_nan=False)))
                    saved[day] = report
            if saved:
                last = saved[max(saved)]
                if last['day'] not in executed:
                    self._execute(data, last, current)

    def view(self):
        # Reads use separate WAL connections; polling never waits on the
        # network worker, and never starts network activity itself.
        # One SQLite read transaction provides a coherent snapshot while an
        # open batch is committing. Never mix old cash with new fill receipts.
        with self.store.connect() as c:
            c.execute('BEGIN')
            r = c.execute('SELECT * FROM account WHERE id=1').fetchone()
            account = dict(r) if r else None
            events = self._events(c)
            days = [json.loads(r[0]) for r in c.execute('SELECT payload FROM paper_days ORDER BY day')]
            executions = [json.loads(r[0]) for r in c.execute('SELECT payload FROM paper_executions ORDER BY execution_day')]
            quotes = {(r['day'], r['symbol']): json.loads(r['payload']) for r in c.execute('SELECT * FROM paper_quotes')}
        if not account:
            return dict(account=None, job=self.job, days=[], executions=[], events=[])
        data = self.get_data(); ledger = journal(account, events)
        report = days[-1] if days else None
        holdings = []; inventory = D(0); marks = []
        for sid, p in ledger['positions'].items():
            row = data.row(sid, data.as_of); mark_day = row['observed_on']; price = D(str(row['raw_close'])); basis = '收盘'
            for rec in executions:
                if rec['execution_day'] > mark_day:
                    quote = quotes.get((rec['execution_day'], sid))
                    if quote and quote.get('open'):
                        price = D(quote['open']); mark_day = rec['execution_day']; basis = '开盘'
            value = price*p['shares']; inventory += value; marks.append(mark_day)
            holdings.append(dict(**row, **p, mark_price=str(price), mark_day=mark_day, mark_basis=basis, market_value=str(value), unrealized=str(value-D(p['cost'])), sellable_shares=sum(l['shares'] for l in p['lots'] if lot_sellable(l, datetime.now(TZ).date().isoformat()))))
        nav = D(ledger['cash'])+D(ledger['receivable'])+inventory
        peak = max([D(account['initial_cash']), nav]+[D(r['nav']) for r in days])
        curve = [dict(day=r['day'], nav=r['nav'], cash=r['cash'], market_value=r['market_value'], risk=r['risk'], basis='收盘') for r in days]
        latest_execution = executions[-1]['execution_day'] if executions else None
        if latest_execution and (not days or latest_execution > days[-1]['day']):
            curve.append(dict(day=latest_execution, nav=str(nav), cash=ledger['cash'], market_value=str(inventory), basis='开盘，待收盘'))
        return clean(dict(account=account, contract=self.store.setting('execution_contract'), job=self.job if self.job['state'] != 'idle' else self.store.setting('last_sync', self.job), waiting=self.store.setting('waiting'), report=report, days=days, curve=curve, executions=executions, events=events, holdings=holdings, cash=ledger['cash'], receivable=ledger['receivable'], realized=ledger['realized'], fees=ledger['fees'], market_value=str(inventory), nav=str(nav), profit=str(nav-D(account['initial_cash'])), total_return=str(nav/D(account['initial_cash'])-1), drawdown=str(1-nav/peak), mark_day=max(marks+[data.as_of]), market_status=data.status(), database=str(self.store.path)))

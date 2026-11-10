"""Local actual-account journal. Decimal cash, immutable events, atomic writes."""
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')
D = Decimal


def money(value, *, zero=False):
    if isinstance(value, bool):
        raise ValueError('金额必须是有效数字')
    try:
        x = D(str(value))
    except InvalidOperation:
        raise ValueError('金额必须是有效数字') from None
    if not x.is_finite() or x < 0 or (not zero and x == 0) or x > D('1e12'):
        raise ValueError('金额超出有效范围')
    return x


def now():
    return datetime.now(TZ).isoformat(timespec='seconds')


def effective_events(events):
    """Corrections append evidence; the original journal rows remain intact."""
    active={}
    for e in sorted(events,key=lambda r:(r['created_at'],r['id'])):
        if e['kind']=='amend':
            target=e['payload']['target_id']
            if target not in active:raise ValueError('要修正的记录已被修正或不存在')
            del active[target]
            replacement=e['payload'].get('replacement')
            if replacement:
                active[e['id']]=dict(e,kind=replacement['kind'],at=replacement['at'],payload=replacement['payload'])
        else:active[e['id']]=e
    return sorted(active.values(),key=lambda r:(r['at'],r['created_at'],r['id']))


def lot_sellable(lot,day):
    return (lot.get('corporate',False) or lot['day']<day) and lot.get('sellable_on',day)<=day


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1), initial_cash TEXT NOT NULL, started_on TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reports(day TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS report_versions(day TEXT NOT NULL,fingerprint TEXT NOT NULL,snapshot TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(day,fingerprint,snapshot));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        try:
            with c:
                yield c
        finally:
            c.close()

    def account(self):
        with self.connect() as c:
            r = c.execute('SELECT * FROM account WHERE id=1').fetchone()
            return dict(r) if r else None

    def initialize(self, cash, started_on, *, initial_participation=None):
        amount = money(cash)
        if initial_participation not in (None,'ACTIVE','INACTIVE'):
            raise ValueError('账户初始参与状态无效')
        datetime.strptime(started_on, '%Y-%m-%d')
        if started_on > now()[:10]:
            raise ValueError('账户起始日不能在未来')
        with self.connect() as c:
            if c.execute('SELECT 1 FROM account').fetchone():
                raise ValueError('真实账户已建立，不能重复初始化')
            c.execute('INSERT INTO account VALUES(1,?,?,?)', (str(amount), started_on, now()))
            if initial_participation is not None:
                c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', ('initial_participation',json.dumps(initial_participation)))
        return self.account()

    def events(self):
        with self.connect() as c:
            return [dict(r) | {'payload': json.loads(r['payload'])} for r in c.execute('SELECT * FROM events ORDER BY at,created_at,id')]

    def record(self, event_id, at, kind, payload, validate):
        if not isinstance(event_id, str) or len(event_id) > 80 or not event_id:
            raise ValueError('缺少成交唯一标识')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if old:
                if old['at'] != at or old['kind'] != kind or old['payload'] != body:
                    raise ValueError('重复标识对应不同成交，请检查')
                return event_id
            rows = [dict(r) | {'payload': json.loads(r['payload'])} for r in c.execute('SELECT * FROM events')]
            proposed = dict(id=event_id, at=at, kind=kind, payload=payload, created_at=datetime.now(TZ).isoformat(timespec='microseconds'))
            validate(sorted(rows + [proposed], key=lambda r: (r['at'], r['created_at'], r['id'])))
            c.execute('INSERT INTO events VALUES(?,?,?,?,?)', (event_id, at, kind, body, proposed['created_at']))
            c.execute('DELETE FROM reports')
        return event_id

    def setting(self, key, default=None):
        with self.connect() as c:
            r = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(r['value']) if r else default

    def set_setting(self, key, value):
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value)))

    def fingerprint(self):
        return hashlib.sha256(json.dumps([self.account(), self.events()], sort_keys=True).encode()).hexdigest()

    def save_report(self, day, fingerprint, payload):
        with self.connect() as c:
            text=json.dumps(payload, ensure_ascii=False, allow_nan=False)
            c.execute('INSERT OR REPLACE INTO reports VALUES(?,?,?,?)', (day, fingerprint, text, now()))
            c.execute('INSERT OR IGNORE INTO report_versions VALUES(?,?,?,?,?)',(day,fingerprint,payload['snapshot_id'],text,now()))

    def latest_report(self):
        with self.connect() as c:
            r = c.execute('SELECT payload FROM reports ORDER BY day DESC LIMIT 1').fetchone()
            return json.loads(r['payload']) if r else None


def journal(account, events, through=None):
    """Rebuild actual cash and FIFO lots. Never infer a fill from a suggestion."""
    cash = D(account['initial_cash'])
    lots = {}
    realized = D(0)
    fees = D(0); receivable=D(0)
    for event in effective_events(events):
        if through and event['at'][:10] > through:
            continue
        p = event['payload']; symbol = p.get('symbol'); day = event['at'][:10]
        if day < account['started_on']:
            raise ValueError('成交早于账户起始日')
        if event['kind'] == 'cash':
            cash += D(p['amount'])
        elif event['kind'] == 'buy':
            price, fee, shares = D(p['price']), D(p['fee']), p['shares']
            cash -= price * shares + fee; fees += fee
            lots.setdefault(symbol, []).append(dict(shares=shares, price=price, fee=fee, day=day))
        elif event['kind'] == 'sell':
            price, fee, shares = D(p['price']), D(p['fee']), p['shares']
            sellable = sum(l['shares'] for l in lots.get(symbol, []) if lot_sellable(l,day))
            if shares > sellable:
                raise ValueError('卖出数量超过可卖持仓（A股T+1）')
            remaining = shares; basis = D(0)
            for lot in lots[symbol]:
                if not remaining: break
                if not lot_sellable(lot,day): continue
                qty = min(remaining, lot['shares']); fraction = D(qty) / lot['shares']
                allocated_fee = lot['fee'] * fraction
                basis += lot['price'] * qty + allocated_fee
                lot['fee'] -= allocated_fee; lot['shares'] -= qty; remaining -= qty
            lots[symbol] = [l for l in lots[symbol] if l['shares']]
            realized += price * shares - fee - basis
            cash += price * shares - fee; fees += fee
        elif event['kind'] == 'corporate':
            delta=p['shares_delta'];ls=lots.get(symbol,[]);before=sum(l['shares'] for l in ls)
            if delta and (not before or before+delta<=0):raise ValueError('权益变更后的持仓数量无效')
            if delta:
                after=before+delta;left=after;bonus=[]
                for i,l in enumerate(ls):
                    qty=left if i==len(ls)-1 else int(D(l['shares'])*after/before)
                    if qty<=0:raise ValueError('权益数量无法分配到现有批次，请分笔核对')
                    old_qty=l['shares'];new_price=l['price']*old_qty/qty;old_fee=l['fee'];left-=qty
                    if qty>old_qty:
                        added=qty-old_qty;bonus_fee=old_fee*D(added)/qty
                        bonus.append(dict(shares=added,price=new_price,fee=bonus_fee,day=day,corporate=True,sellable_on=p.get('sellable_on',day)))
                        l['price']=new_price;l['fee']=old_fee-bonus_fee
                    else:l['price']=new_price;l['shares']=qty
                lots[symbol]=ls+bonus
            cash+=D(p['cash_delta']);receivable+=D(p['receivable_delta']);realized+=D(p['cash_delta'])
            if receivable<0:raise ValueError('待收权益余额不能为负')
        else:
            raise ValueError('不支持的账务事件')
        if cash < 0:
            raise ValueError('成交导致可用现金为负，请核对资金、费用和时间顺序')
    positions = {}
    for s, ls in lots.items():
        qty = sum(l['shares'] for l in ls)
        if qty:
            basis = sum((l['price'] * l['shares'] + l['fee'] for l in ls), D(0))
            positions[s] = dict(shares=qty, cost=str(basis), average_cost=str(basis/qty), lots=[dict(l, price=str(l['price']), fee=str(l['fee'])) for l in ls])
    return dict(cash=str(cash), positions=positions, realized=str(realized), fees=str(fees),receivable=str(receivable))

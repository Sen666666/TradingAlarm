"""Read-only market snapshot; research files are never mutated by the app."""
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'research_rounds/tech-finite-compound-20261026'
NR = ROOT/'research_rounds/e0-reclaim-accounts-20261026/prepared'
TZ = ZoneInfo('Asia/Shanghai')


def finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def clean(obj):
    if isinstance(obj, dict): return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)): return [clean(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)): return bool(obj)
    if isinstance(obj, (float, np.floating)): return finite(obj)
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, (datetime, pd.Timestamp)): return obj.isoformat()
    return obj


class MarketData:
    def __init__(self, runtime):
        self.runtime = Path(runtime)
        pointer = self.runtime/'market/current.json'
        self.published = json.loads(pointer.read_text()) if pointer.exists() else None
        folder = Path(self.published['path']) if self.published else None
        self.signals_dir = folder/'signals' if folder else BASE/'prepared-v2/signals'
        self.facts_dir = folder/'facts' if folder else NR/'facts'
        self.h1_path = folder/'h1.npz' if folder else BASE/'prepared-v2/h1.npz'
        with (ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').open() as f:
            self.roster = list(csv.DictReader(f))
        for r in self.roster:
            r['name'] = r['name'] or r['symbol'].split('.')[0]
        self.meta = {x['symbol']: x for x in self.roster}
        self.sectors = {x['sector_id']: x['industry'] for x in self.roster}
        self.facts = {p.stem: pd.read_parquet(p) for p in self.facts_dir.glob('*.parquet')}
        self.signals = {}
        with np.load(self.h1_path) as z:
            self.dates = pd.DatetimeIndex(z['dates']); self.columns = {str(s): j for j, s in enumerate(z['symbols'])}; self.scores = z['score']
        recovery = folder/'recovery.csv' if folder else ROOT/'research_rounds/actual-risk-recovery-20261027/recovery.csv'
        self.recovery = pd.read_csv(recovery, index_col=0, parse_dates=True)
        self.as_of = str(self.recovery.index.max().date())
        self.identity = hashlib.sha256(recovery.read_bytes()+self.h1_path.read_bytes()).hexdigest()
        rules = json.loads((BASE/'execution-rules-v2.json').read_text())
        from .execution import RuleBook
        self.rulebook = RuleBook(rules)
        calendar = json.loads((Path(__file__).parent/'calendar.json').read_text())
        self.calendar = sorted({d[:10] for d in rules['calendars']['A'] if d[:10] < '2026-01-01'} | set(calendar['sessions']))
        self.integrity = self.check_identity()
        manifest=folder/'manifest.json' if folder else BASE/'data/core-v3/manifest.json'
        self.actions={}
        for rec in json.loads(manifest.read_text())['series']:
            sid=rec['series_id']
            if sid in self.meta and 'actions' in rec['adjustment']:
                self.actions[sid]=json.loads(Path(rec['adjustment']['actions']['path']).read_text())['events']

    def check_identity(self):
        selected = json.loads((ROOT/'research_rounds/strategy-choice-20261027/SELECTED_STRATEGY.json').read_text())
        bad = []
        for path, h in selected['frozen_dependencies'].items():
            file = Path(path)
            if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest() != h: bad.append(str(file))
        admission = ROOT/'TradingAlarm/desk/admission.py'
        source = ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py'
        if admission.read_bytes() != source.read_bytes(): bad.append('admission identity')
        contract=Path(__file__).parent/'contract.json'
        if not contract.exists():bad.append('product contract missing')
        else:
            for name,digest in json.loads(contract.read_text())['files'].items():
                file=ROOT/name
                if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:bad.append(name)
        if self.published:
            folder=Path(self.published['path']);manifest=json.loads((folder/'manifest.json').read_text())
            for fact in manifest.get('facts',[]):
                if hashlib.sha256((folder/'facts'/f"{fact['symbol']}.parquet").read_bytes()).hexdigest()!=fact['sha256']:bad.append('published fact '+fact['symbol'])
        return dict(passed=not bad, errors=bad, strategy='ACT20_BREAK')

    def expected_close(self, current=None):
        current = current or datetime.now(TZ)
        # Known trading calendar is explicit; never invent a future holiday.
        if current.date().isoformat() > self.calendar[-1]: return None
        cutoff = current.strftime('%Y-%m-%d')
        eligible = [d for d in self.calendar if d < cutoff or (d == cutoff and current.strftime('%H:%M') >= '15:10')]
        return eligible[-1] if eligible else None

    def status(self):
        expected = self.expected_close()
        return dict(as_of=self.as_of, expected_close=expected, current=expected == self.as_of and self.integrity['passed'], stock_count=len(self.meta), sector_count=len(self.sectors), reference_count=len(self.columns), source='同花顺日线＋权益', published_at=self.published.get('published_at') if self.published else None, bootstrap=not bool(self.published), integrity=self.integrity, calendar_through=self.calendar[-1])

    def row(self, symbol, day):
        f = self.facts[symbol]; a = f.loc[:day]
        if a.empty: return None
        r = a.iloc[-1]; observed = str(a.index[-1].date())
        j = self.dates.get_indexer([pd.Timestamp(day)])[0]
        score = finite(self.scores[j,self.columns[symbol]]) if j >= 0 and symbol in self.columns else None
        floor = finite(r.i_floor) if symbol in self.meta else finite(r.e0_floor)
        factor = finite(r.factor)
        return dict(symbol=symbol, name=self.meta[symbol]['name'] if symbol in self.meta else self.sectors[symbol], industry=self.meta[symbol]['industry'] if symbol in self.meta else self.sectors[symbol], sector_id=self.meta[symbol]['sector_id'] if symbol in self.meta else symbol, observed_on=observed, fresh=observed == day, raw_close=finite(r.raw_close), factor=factor, floor_raw=floor/factor if floor is not None and factor else None, e0_up=bool(r.e0_target), trend_up=bool(r.i_target) if symbol in self.meta else bool(r.e0_target), buy_event=bool(r.i_buy) if symbol in self.meta and observed == day else False, grade=finite(r.g_grade), ready=bool(r.e0_ready), strength_ready=bool(r.g_ready), rs_h1=score)

    def stocks(self, day=None):
        return [self.row(s,day or self.as_of) for s in self.meta]

    def chart(self, symbol):
        if symbol not in self.meta: raise ValueError('请选择科技股票池内的股票')
        if symbol not in self.signals: self.signals[symbol] = pd.read_parquet(self.signals_dir/f'{symbol}.parquet')
        f = self.signals[symbol].loc['2024':].copy(); a = self.facts[symbol].reindex(f.index)
        # Latest-price coordinate for display only. Actual orders always raw prices.
        last_factor = float(a.factor.dropna().iloc[-1]); result=[]
        for t,r in f.iterrows():
            q = a.loc[t]; floor = finite(q.i_floor)
            result.append(dict(date=str(t.date()),open=finite(r.open/last_factor),high=finite(r.high/last_factor),low=finite(r.low/last_factor),close=finite(r.close/last_factor),raw_close=finite(r.raw_close),volume=finite(r.raw_volume),amount=finite(r.amount),support=floor/last_factor if floor is not None else None,buy=bool(q.i_buy) if pd.notna(q.i_buy) else False,up=bool(q.i_target) if pd.notna(q.i_target) else False,grade=finite(q.g_grade)))
        return dict(**self.meta[symbol], bars=clean(result),as_of=self.as_of,price_basis='因果复权信号缩放到最新原价坐标；成交输入用未复权价格',volume_unit='股',amount_unit='元')

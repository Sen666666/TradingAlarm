"""Read-only CLOSE valuation oracle matching original stale-action mark policy.

No strategy/Account/Runner import. Source rows remain actual observed quotes;
intervening declared actions transform a stale reference, never make a quote.
"""
from pathlib import Path
from decimal import Decimal as D
import ast,hashlib,json
import numpy as np
import pandas as pd

MANIFEST=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
PROTOCOL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')
UTIL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py')
NATIVE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/history_runner.py')
FAST=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
src=UTIL.read_text();tree=ast.parse(src)
for name in ['boolean_column','eligible_prices']:
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(UTIL)+':pure_price_mask','exec'),globals())


class NativeCloseMarks:
    def __init__(self):
        self.records={r['series_id']:r for r in json.loads(MANIFEST.read_text())['series']}
        assert json.loads(PROTOCOL.read_text())['stale_action_mark_policy']=='theoretical_ex_reference'
        self.source_sha256={str(p):sha(p) for p in [MANIFEST,PROTOCOL,UTIL,NATIVE,FAST,Path(__file__)]}
        self.cache={};self.actions={};self.queries={}
    def checked(self,ref):
        p=Path(ref['path']);p=p if p.is_absolute() else MANIFEST.parent/p
        assert sha(p)==ref['sha256'];self.source_sha256[str(p)]=ref['sha256'];return p
    def load(self,sid):
        r=self.records[sid];p=self.checked(r['raw']);f=pd.read_parquet(p)
        if 'trade_date' in f:f=f.rename(columns={'trade_date':'date'})
        if 'date' in f:f=f.set_index('date')
        f.index=pd.DatetimeIndex(pd.to_datetime(f.index),name='date')
        assert f.index.is_unique and f.index.is_monotonic_increasing
        if 'is_observed_bar' in f:f['observed_bar']=f.is_observed_bar
        valid=eligible_prices(f)
        self.cache[sid]=valid[['close']]
        ap=self.checked(r['adjustment']['actions']);a=json.loads(ap.read_text())
        assert a['series_id']==sid and not a.get('unresolved')
        self.actions[sid]=a['events']
    def at(self,sid,day):
        key=(sid,day)
        if key in self.queries:return self.queries[key]
        if sid not in self.cache:self.load(sid)
        f=self.cache[sid];j=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert j>=0
        observed=f.index[j].date().isoformat();raw=D(str(f.iloc[j].close));price=raw
        events=sorted([e for e in self.actions[sid] if observed<e['effective_date']<=day],key=lambda e:e['effective_date'])
        for e in events:
            price=(price-D(e.get('signal_cash_per_old_share',e['cash_per_old_share'])))/D(e.get('signal_split_ratio',e['split_ratio']))
            assert price>0
        q=dict(sid=sid,day=day,raw_observed_day=observed,raw_observed_close=str(raw),valuation_reference=str(price),applied_actions=events,is_current_observed_quote=observed==day)
        self.queries[key]=(price,q);return price,q

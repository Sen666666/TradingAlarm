"""Bounded raw-open/rights reads using the existing authorized THS collector."""
import csv
import json
from datetime import datetime, timedelta

from .data import ROOT, TZ
from .refresh import module


def fetch_opens(data, day, symbols, runtime):
    import sys
    sys.path.insert(0, str(ROOT/'TradingAlarm/research'))
    import ths_readonly as ths
    import ths_readonly_fu as fu
    collector = module('paper_history_batch', ROOT/'research_rounds/current-pool-20261022/code/history_batch.py')
    collector.PAGE = 12
    master = {r['symbol']: r['ths_symbol'] for r in csv.DictReader((ROOT/'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv').open())}
    if not symbols or len(symbols) > 12 or any(s not in data.meta for s in symbols):
        raise ValueError('模拟开盘查询范围无效')
    earliest = (datetime.fromisoformat(day)-timedelta(days=5)).date().isoformat()
    items = [dict(symbol=master[s], node='9602', end=day, earliest=earliest, mode='tail', rights=True, max_pages=2) for s in symbols]
    plan = dict(schema_version=1, items=items, max_requests=len(items)*4+2, request_interval_seconds=.3, read_timeout_seconds=15, session_preference='auto')
    folder = runtime/'paper-quotes'/datetime.now(TZ).strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    collector.immutable(folder/'protocol.json', collector.encoded(plan))
    col = collector.Collector(plan, folder, ths, fu, collector.digest(collector.encoded(plan)))
    col.run()
    if col.stopped_nodes:
        raise ValueError('同花顺开盘查询未完成，请检查本人客户端登录状态')
    normal = module('paper_action_normalizer', ROOT/'research_rounds/a-share-selection-e0-20261024/code/normalize_actions.py')
    result = {}
    for sid, item in zip(symbols, items):
        symbol = item['symbol']
        cp = collector.read_json(folder/'checkpoints'/f'{symbol}.json')
        if not cp or cp['history_status'] != 'complete' or cp['rights_status'] != 'received':
            raise ValueError('开盘或权益资料尚未完整取得：'+sid)
        history_path = folder/'history'/f'{symbol}.json'
        history = collector.read_json(history_path)
        rights_path = folder/cp['rights']['attempt']/'decoded.json'
        # The collector stores raw decoded records without authentication data.
        records = collector.read_json(rights_path)
        actions, _, unresolved = normal.normalize(records, str(rights_path), earliest, day)
        if unresolved:
            raise ValueError('开盘前权益资料无法解释：'+sid)
        bars = [r for r in history['bars'] if r['date'] == day and (r.get('open') or 0) > 0 and (r.get('volume') or 0) > 0]
        if len(bars) != 1:
            # Absence during an incomplete session is still unknown, not a
            # failed order. The full close publication later decides expiry.
            continue
        result[sid] = dict(symbol=sid, day=day, open=str(bars[0]['open']), source='同花顺9602未复权日线开盘', source_path=str(history_path), fetched_at=datetime.now(TZ).isoformat(), actions=actions)
    return result

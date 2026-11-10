"""Rebuild credential-free app data from local evidence; never opens a socket."""
import json
from collections import Counter
from urllib.parse import parse_qs
from market import EVIDENCE, frames, decode, bars, minutes
from pathlib import Path

stocks = {}
errors = Counter()
def stock(symbol):
    return stocks.setdefault(symbol, {'symbol':symbol, 'code':symbol[4:], 'market':symbol[:4], 'name':symbol[4:], 'quote':{}, 'bars':{}, 'intraday':[]})

sources = [(EVIDENCE, json.loads((EVIDENCE/'stream-summary.json').read_text()), '2026-10-16 13:58'),
           (EVIDENCE/'handshake', json.loads((EVIDENCE/'handshake/reassembly-manifest.json').read_text())['streams'], '2026-10-16 14:04')]
for root, streams, captured_at in sources:
    requests = {}
    for stream in streams:
        if 'client' not in stream['file']:
            continue
        for body in frames((root/stream['file']).read_bytes()):
            if not body.startswith((b'id=200&', b'id=207&', b'id=210&')):
                continue
            query = {k:v[0] for k,v in parse_qs(body.decode()).items()}
            requests[(stream['key'][0], int(query['instance']))] = query
    for stream in streams:
        if 'server' not in stream['file']:
            continue
        for body in frames((root/stream['file']).read_bytes()):
            try:
                result = decode(body)
                if not result:
                    continue
                kind, instance, records = result
                query = requests.get((stream['key'][0], instance), {})
                if kind == 200:
                    for record in records:
                        symbol = record.get('5')
                        if not isinstance(symbol,str) or len(symbol) < 5:
                            continue
                        s = stock(symbol)
                        s['quote'].update(record)
                        if record.get('55'):
                            s['name'] = record['55']
                        s['capturedAt'] = captured_at
                elif query.get('code') and query.get('market'):
                    s = stock(query['market'] + query['code'])
                    if kind == 207:
                        rows = minutes(records)
                        if rows:
                            s['intraday'] = rows
                    elif kind == 210 and query.get('period') == '16384':
                        for bar in bars(records):
                            s['bars'][bar['date']] = bar
            except (ValueError, IndexError, KeyError, AssertionError, UnicodeError) as exc:
                errors[type(exc).__name__] += 1

for s in stocks.values():
    s['bars'] = sorted(s['bars'].values(),key=lambda x:x['date'])
    s.setdefault('capturedAt', '2026-10-16 14:04')
    s['aliases'] = {'USHA688008':'lqkj lanqikeji','USHJ518850':'hjetf huangjin','USZA300750':'ndsd ningdeshidai', 'USHI1A0001':'szzs shangzheng', 'USHI1B0688':'kc50 kechuang', 'USZI399001':'szcz shenzheng','USZI399006':'cybz chuangyeban'}.get(s['symbol'],'')
    if s['name'] == '399001':s['name'] = '深证成指'
    if s['name'] == '399006':s['name'] = '创业板指'
output = {'source':'capture', 'capturedAt':'2026-10-16 13:56–14:04', 'stocks':list(stocks.values()), 'decodeSkipped':dict(errors)}
path = Path(__file__).parent/'data/market.json'
path.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')))
print(json.dumps({'stocks':len(stocks),'withBars':sum(bool(s['bars']) for s in stocks.values()),'withIntraday':sum(bool(s['intraday']) for s in stocks.values()),'skipped':dict(errors)},ensure_ascii=False))

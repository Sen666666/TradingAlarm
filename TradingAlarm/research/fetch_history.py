"""Bounded, read-only history collection from the already authorized THS node.

Writes market bars and provenance only; never persists handshake credentials.
Paging uses the observed id=210 end-date boundary, retaining one overlapping bar.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
import urllib.parse

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from market import decode, bars
from sessions import SessionManager, validate_handshake_reply, DEFAULT_PREFERENCES

OUT = Path(__file__).resolve().parent / 'data'

def receive(sock):
    def exact(n):
        out = bytearray()
        while len(out) < n:
            part = sock.recv(n - len(out))
            if not part:
                raise ConnectionError('行情连接关闭')
            out.extend(part)
        return bytes(out)
    header = exact(13)
    if header[:4] != b'\xfd'*4 or header[12] != 9:
        raise ValueError('Unknown frame')
    n = int(header[4:12], 16)
    if n > 4*1024*1024:
        raise ValueError('Oversized frame')
    return exact(n)

def fetch(symbol, end, earliest, max_pages, adjustment='Q'):
    if adjustment not in ('Q','B','raw'):
        raise ValueError('Unknown adjustment mode')
    if len(symbol) < 5 or not symbol.isalnum():
        raise ValueError('Invalid symbol')
    manager = SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin', preferences_path=DEFAULT_PREFERENCES)
    records, pages, conflicts = {}, [], []
    auxiliary = {}
    endpoint = ('119.3.43.91', 9602)
    with socket.create_connection(endpoint, timeout=8) as sock:
        sock.settimeout(20)
        sock.sendall(manager.prepare())
        server_time = validate_handshake_reply(receive(sock))
        for page in range(max_pages):
            instance = 890001 + page
            query = dict(id=210, instance=instance, zipversion=3, code=symbol[4:], market=symbol[:4], start=-749, end=end, fuquan='Q', datatype='1,7,8,9,11,13,19,74', period=16384)
            if adjustment == 'raw':
                query.pop('fuquan')
            else:
                query['fuquan'] = adjustment
            payload = urllib.parse.urlencode(query, safe=',').encode()
            sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
            for _ in range(16):
                decoded = decode(receive(sock))
                if decoded and decoded[:2] == (210, instance):
                    break
            else:
                raise ValueError('No matching history response')
            for row in decoded[2]:
                if row.get('1') is not None:
                    auxiliary[str(row['1'])] = {k:v for k,v in row.items() if k not in ('1','7','8','9','11','13','19')}
            batch = sorted(bars(decoded[2]), key=lambda r:r['date'])
            pages.append({'query':query, 'count':len(batch), 'first':batch[0]['date'] if batch else None, 'last':batch[-1]['date'] if batch else None})
            added = 0
            for row in batch:
                date = row['date']
                if date in records and records[date] != row:
                    conflicts.append({'date':date, 'new':row, 'previous':records[date]})
                if date not in records:
                    records[date] = row
                    added += 1
            print(symbol, 'page',page+1,'rows',len(batch),'added',added, 'first',pages[-1]['first'], flush=True)
            if not batch or not added or batch[0]['date'] <= earliest or len(batch)<750:
                break
            new_end = batch[0]['date'].replace('-','')
            if str(end) == new_end:
                break
            end = new_end
            time.sleep(.3)
        manager.success(server_time)
    result = {'symbol':symbol, 'source':'THS id=210', 'endpoint':f'{endpoint[0]}:{endpoint[1]}', 'fetched_at':datetime.now().astimezone().isoformat(), 'adjustment':'Q; semantics not independently verified', 'pages':pages, 'overlap_conflicts':conflicts, 'bars':sorted(records.values(),key=lambda r:r['date'])}
    result['adjustment'] = {'Q':'Q; adjusted signal data, not raw fills','B':'B; adjusted signal data, not raw fills','raw':'fuquan omitted; raw-price semantics cross-checked on688008, require per-source validation'}[adjustment]
    result['auxiliary_fields_by_date'] = auxiliary
    result['auxiliary_semantics'] = 'Uninterpreted wire fields, not certified historical trading state or price limits.'
    result['requested_earliest'] = earliest
    result['reached_requested_earliest'] = bool(result['bars'] and result['bars'][0]['date'] <= earliest)
    result['page_budget_exhausted'] = len(pages) == max_pages and bool(pages and pages[-1]['count'] == 750) and not result['reached_requested_earliest']
    result['bars_sha256'] = hashlib.sha256(json.dumps(result['bars'],sort_keys=True).encode()).hexdigest()
    folder = OUT if adjustment == 'Q' else OUT / ('ths-'+adjustment)
    folder.mkdir(parents=True,exist_ok=True)
    path = folder / f'{symbol}.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    temp.replace(path)
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('symbols',nargs='+')
    parser.add_argument('--end',default='20261016')
    parser.add_argument('--earliest',default='2010-01-01')
    parser.add_argument('--max-pages',type=int,default=8)
    parser.add_argument('--adjustment',choices=['Q','B','raw'],default='Q')
    args = parser.parse_args()
    for symbol in args.symbols:
        result = fetch(symbol,args.end,args.earliest,min(args.max_pages,12),args.adjustment)
        print(json.dumps({'symbol':symbol,'rows':len(result['bars']),'conflicts':len(result['overlap_conflicts'])}))

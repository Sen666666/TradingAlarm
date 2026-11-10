"""Public adjustment-factor pilot; factors are not a cash/share event ledger."""
import argparse
import json
import signal
import socket
from datetime import datetime
from pathlib import Path
import baostock as bs

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--budget-seconds', type=int, default=180)
    args = parser.parse_args()
    out = ROOT / 'data/retired-factors'
    out.mkdir(exist_ok=True)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('factor pilot time budget')))
    socket.setdefaulttimeout(60)
    signal.alarm(args.budget_seconds)
    try:
        login = bs.login()
        if login.error_code != '0':
            raise RuntimeError(login.error_msg)
        for path in sorted((ROOT / 'data/retired-pilot').glob('*.json'))[:args.limit]:
            record = json.loads(path.read_text())
            master = record['master_record']
            target = out / path.name
            if target.exists():
                try:
                    saved = json.loads(target.read_text())
                    entries = saved.get('rows', [])
                    valid = saved.get('symbol') == record['symbol'] and bool(entries)
                    valid = valid and all(float(x['backAdjustFactor']) > 0 and x['code'] == master['code'] for x in entries)
                    if valid:
                        continue
                except (ValueError, KeyError, TypeError):
                    pass
            result = bs.query_adjust_factor(master['code'], start_date='1990-01-01', end_date=master['outDate'])
            if result.error_code != '0':
                raise RuntimeError(result.error_msg)
            rows = []
            while result.next():
                rows.append(dict(zip(result.fields, result.get_row_data())))
            if result.error_code != '0':
                raise RuntimeError(result.error_msg)
            payload = dict(symbol=record['symbol'], source='BaoStock public query_adjust_factor',
                           fetched_at=datetime.now().astimezone().isoformat(), rows=rows,
                           limitation='No dividend pay dates, split share quantities, merger or terminal proceeds; empty result does not prove no events.')
            temp = target.with_suffix('.tmp')
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            temp.replace(target)
            print(record['symbol'], len(rows), result.fields, flush=True)
    finally:
        bs.logout()
        signal.alarm(0)


if __name__ == '__main__':
    main()

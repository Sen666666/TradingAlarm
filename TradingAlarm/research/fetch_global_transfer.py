"""Fetch frozen public ETF history, no account/session credentials."""
import datetime
import hashlib
import json
import requests
from build_stock_features import ROOT


def main():
    protocol=json.loads((ROOT/'results/global-transfer-freeze/protocol.json').read_text())
    out=ROOT/'data/global-transfer';out.mkdir(exist_ok=True);records=[]
    for symbol in protocol['universe']:
        path=out/f'{symbol}-yahoo.json'
        record=dict(symbol=symbol,requested_start='2005-01-01',requested_end_exclusive='2026-01-01')
        if not path.exists():
            try:
                response=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
                    params=dict(period1=1104537600,period2=1767225600,interval='1d',events='div,splits,capitalGains'),
                    headers={'User-Agent':'Mozilla/5.0'},timeout=25)
                record['http_status']=response.status_code
                response.raise_for_status();data=response.json()
                if data['chart'].get('error') or not data['chart'].get('result'):raise ValueError('No chart result')
                path.write_text(json.dumps(data))
                record['fetched_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            except (requests.RequestException,ValueError) as exc:
                record['error_type']=type(exc).__name__;records.append(record)
                (out/'fetch-manifest.json').write_text(json.dumps(records,indent=2));print(record,flush=True)
                continue
        data=json.loads(path.read_text())['chart']['result'][0]
        record.update(bars=len(data.get('timestamp',[])),currency=data['meta'].get('currency'),
            events={k:len(v) for k,v in data.get('events',{}).items()},sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        records.append(record);(out/'fetch-manifest.json').write_text(json.dumps(records,indent=2));print(record,flush=True)


if __name__=='__main__':main()

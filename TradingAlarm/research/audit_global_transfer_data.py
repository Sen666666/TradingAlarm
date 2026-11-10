"""Validate public prices/events without inventing dividend settlement dates."""
import hashlib
import json
import numpy as np
import pandas as pd
from build_stock_features import ROOT


def local_date(timestamp,zone):
    return pd.Timestamp(timestamp,unit='s',tz='UTC').tz_convert(zone).tz_localize(None).normalize()


def main():
    protocol=json.loads((ROOT/'results/global-transfer-freeze/protocol.json').read_text())
    source=ROOT/'data/global-transfer';records=[]
    for symbol in protocol['universe']:
        file=source/f'{symbol}-yahoo.json';x=json.loads(file.read_text())['chart']['result'][0]
        assert x['meta']['currency']=='USD' and x['meta']['symbol']==symbol
        zone=x['meta']['exchangeTimezoneName']
        dates=pd.DatetimeIndex([local_date(t,zone) for t in x['timestamp']])
        raw=pd.DataFrame(x['indicators']['quote'][0],index=dates).sort_index()
        assert raw.index.is_unique and raw.index.max()<=pd.Timestamp('2025-12-31')
        assert np.isfinite(raw[['open','high','low','close','volume']].to_numpy()).all()
        assert raw[['open','high','low','close']].gt(0).all().all() and raw.volume.gt(0).all()
        assert raw.high.ge(raw[['open','low','close']].max(axis=1)).all()
        assert raw.low.le(raw[['open','high','close']].min(axis=1)).all()
        assert set(x.get('events',{})).issubset({'dividends','splits','capitalGains'})
        split_events=[]
        for event in x.get('events',{}).get('splits',{}).values():
            date=local_date(event['date'],zone)
            split_events.append(dict(date=str(date.date()),ratio=event['numerator']/event['denominator'],
                quoted_close_ratio=float(raw.loc[date,'close']/raw.loc[raw.index<date,'close'].iloc[-1])))
            # Use a uniform post2005 warm-up interval; do not apply a historical
            # split to quotes already adjusted by the vendor.
            assert date<pd.Timestamp('2006-01-01'),'Trading-period split requires raw-price reconstruction'
        used=raw.loc['2006-01-01':].copy();used.index.name='date'
        assert len(used.loc[:'2006-12-31'])>=200
        events=[];ignored_events=[]
        for kind in ('dividends','capitalGains'):
            for event in x.get('events',{}).get(kind,{}).values():
                date=local_date(event['date'],zone)
                assert event['amount']>=0
                if date<used.index[0]:
                    ignored_events.append(str(date.date()));continue
                assert date in raw.index
                events.append(dict(symbol=symbol,ex_date=str(date.date()),
                    amount=float(event['amount']),kind=kind,pay_date=None,settlement_verified=False))
        used.to_parquet(source/f'{symbol}-ohlcv.parquet')
        (source/f'{symbol}-distributions.json').write_text(json.dumps(events,indent=2))
        records.append(dict(symbol=symbol,asset_class=protocol['universe'][symbol],raw_rows=len(raw),
            usable_rows=len(used),first=str(used.index[0].date()),last=str(used.index[-1].date()),
            warmup_rows_before2007=len(used.loc[:'2006-12-31']),split_events=split_events,
            distributions=len(events),missing_payment_dates=len(events),
            excluded_pre_warmup_events=ignored_events,
            max_abs_raw_close_return=float(used.close.pct_change().abs().max()),
            sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    result=dict(records=records,total_raw_rows=sum(x['raw_rows'] for x in records),
        total_usable_rows=sum(x['usable_rows'] for x in records),
        price_gate='OHLCV/date/positivevolume/warmup checks pass;no split inuniform2006+usedwindow. Currentvendorrevision,notPITprice archive.',
        cash_gate='Distributionpaymentdates absent for5funds. Do not substituteexdate or silentlyassumereinvestment. GLDhasnovendordistributions;issuerconfirmationstillneededforaccountuse.',
        evidence=[dict(topic='SPY2025Decdistribution',source='https://links.sgx.com/1.0.0/corporate-announcements/16ETHGOSVMS2TAW4/68fec87094fb02499708a6cac8bba8714c9434bc6a26ca1bb81f8b49b0c24cea',
            observation='IssuerannouncementlistsUSD1.993368 andpayment2026-01-30;vendoramount1.993 on2025-12-19. Roundingandsettlementtimingrequireverification. Notcashreceivedin2025.'),
            dict(topic='EFA2005split',source='https://www.sec.gov/Archives/edgar/data/1100663/000119312507106290/d497.htm',
            observation='Filingreports3-for-1effectiveJune9,2005. Eventisbeforeuniform2006+warmupwindow;do notapplysplitagain.')])
    (ROOT/'results/global-transfer-freeze/data-audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

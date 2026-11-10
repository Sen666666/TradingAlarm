"""Frozen-model transfer and common causal volatility sizing; no parameter fit.

This is retrospective research, not a fresh holdout or Trend Animal replication.
HK raw execution includes vendor dividend annotations; mainland adjusted prices
use fractional units only and are not a verified corporate-action cash ledger.
"""
import json
import re
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from trend_engine import frame, baselines, signals, structure_change_v2
from cash_ledger import run_ledger, total_return_signal_frame

ROOT = Path(__file__).resolve().parent

def candidates(df):
    out = baselines(df)
    out['trend_v1'] = signals(df).target
    out['structure_change_v2'] = structure_change_v2(df).target
    return out

def volatility_size(df):
    # Today's close only; ledger shifts the complete target to tomorrow's open.
    annual = np.log(df.close).diff().rolling(60).std() * np.sqrt(252)
    return (0.15 / annual.replace(0, np.nan)).clip(upper=1).fillna(0)

def load_hk():
    source = ROOT/'data/tencent-hk02800.json'
    rows = json.loads(source.read_text())['data']['hk02800']['day']
    raw = frame([dict(date=r[0],open=float(r[1]),close=float(r[2]),
                      high=float(r[3]),low=float(r[4]),volume=float(r[5])) for r in rows])
    events=[]
    for e in json.loads((ROOT/'hongkong-dividend-events.json').read_text()):
        if any(e.get(k) for k in ['HGcontent','hgcgContent','ggContent']):
            raise ValueError('Non-cash corporate action needs explicit handling')
        match=re.fullmatch(r'(?:中期|末期)息([0-9.]+)港元',e['FHcontent'])
        if not match: raise ValueError('Unrecognized dividend description')
        events.append(dict(ex_date=e['cqr'],pay_date=e['paixiri'],amount=float(match[1])))
    return raw,events,hashlib.sha256(source.read_bytes()).hexdigest()

def main():
    protocol={
        'status':'Retrospective exploratory transfer; all variants retained; no fitting',
        'strategies':['buy_hold','sma200','momentum252','donchian55_20','trend_v1','structure_change_v2'],
        'sizing':['binary','vol15_cap1'], 'volatility_window':60,
        'execution':'prior close target at next open; no leverage; zero cash interest',
        'cost_bps_per_side':[5,15,30], 'hk_initial_HKD':1000000,'hk_board_lot':500,
        'periods':{'2022_2023':['2022-01-01','2023-12-31'],'2024_plus':['2024-01-01',None]},
        'limits':['Common volatility sizing is not equal realized portfolio risk.',
                  'HK dividends rely on vendor annotations; full official event audit pending.',
                  'Mainland adjusted-price simulation uses fractional units; raw cash flows not verified.',
                  'No FX conversion, historical minimum commissions, cash interest, or executable quote spread.',
                  'Selected surviving ETFs are not a point-in-time investment universe.']}
    (ROOT/'results/cross-market-protocol.json').write_text(json.dumps(protocol,indent=2))
    raw,events,digest=load_hk()
    signal=total_return_signal_frame(raw,events)
    assets=[('HK02800',raw,signal,events,500)]
    for source in sorted((ROOT/'data').glob('USHJ*.json')):
        df=frame(json.loads(source.read_text())['bars'])
        assets.append((source.stem,df,df,[],1e-6))
    records=[]
    for symbol,prices,signal,dividends,lot in assets:
        targets=candidates(signal)
        scale=volatility_size(signal)
        for period,(start,end) in protocol['periods'].items():
            for sizing in protocol['sizing']:
                for strategy in targets:
                    target=targets[strategy]*(scale if sizing=='vol15_cap1' else 1)
                    for cost in protocol['cost_bps_per_side']:
                        m,path=run_ledger(prices,target,dividends,start,end,lot=lot,cost_bps=cost)
                        records.append(dict(symbol=symbol,strategy=strategy,sizing=sizing,period=period,**m))
                        if cost==15 and period=='2024_plus':
                            path.to_csv(ROOT/'results'/f'{symbol}-{strategy}-{sizing}-ledger.csv')
        print(symbol,'complete',flush=True)
    payload=dict(protocol=protocol,hk_source_sha256=digest,hk_dividends=events,records=records)
    (ROOT/'results/cross-market.json').write_text(json.dumps(payload,indent=2,allow_nan=False))
    table=pd.DataFrame(records)
    table.to_csv(ROOT/'results/cross-market.csv',index=False)
    print(table[(table.symbol.isin(['HK02800','USHJ512480']))&(table.period=='2024_plus')&(table.cost_bps_per_side==15)][['symbol','strategy','sizing','cagr','max_drawdown','realized_vol','sharpe']].to_string(index=False))

if __name__=='__main__': main()

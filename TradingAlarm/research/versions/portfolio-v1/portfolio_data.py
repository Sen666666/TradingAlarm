"""Raw ETF prices, explicit corporate actions, causal total-return signals and FX."""
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
from trend_engine import frame
from cross_market import load_hk

ROOT=Path(__file__).resolve().parent
# Verified registration vs exchange-effective date differences. These cannot
# be inferred by treating the F10 split column as an ex-date.
SPLIT_EFFECTIVE={('512480','2021-03-26'):'2021-03-29',
                 ('512480','2026-07-02'):'2026-07-03',
                 ('512010','2021-06-25'):'2021-06-28',
                 ('512800','2025-07-04'):'2025-07-07'}

def total_return_frame(raw,dividends,splits):
    div=pd.Series(0.,index=raw.index); ratio=pd.Series(1.,index=raw.index)
    for e in dividends:
        if pd.Timestamp(e['ex_date']) in raw.index: div.loc[e['ex_date']]+=e['amount']
    for e in splits:
        if pd.Timestamp(e['date']) in raw.index: ratio.loc[e['date']]*=e['ratio']
    if ((ratio!=1)&(div!=0)).any(): raise ValueError('Same-day split and dividend need explicit unit convention')
    gross=(raw.close*ratio+div)/raw.close.shift()
    total=raw.close.iloc[0]*gross.fillna(1).cumprod()
    out=raw.copy()
    for c in ['open','high','low','close']: out[c]=raw[c]*total/raw.close
    return out

def load_assets():
    protocol=json.loads((ROOT/'portfolio-protocol.json').read_text())
    assets={}; audit=[]
    for symbol,(sector,kind) in protocol['universe'].items():
        if symbol=='HK02800':
            raw,divs,_=load_hk(); splits=[]; lot=500; currency='HKD'
        else:
            code=symbol[4:]
            rows=json.loads((ROOT/f'data/tencent-sh{code}-raw.json').read_text())['data']['sh'+code]['day']
            raw=frame([dict(date=r[0],open=float(r[1]),close=float(r[2]),high=float(r[3]),low=float(r[4]),volume=float(r[5])) for r in rows])
            divs=[]; splits=[]; found_div=found_split=False
            for table in pd.read_html(ROOT/f'data/eastmoney-fhsp-{code}.html'):
                if '除息日' in table:
                    found_div=True
                    for _,r in table.iterrows():
                        if '暂无' in str(r['除息日']): continue
                        match=re.fullmatch(r'每10份派现金([0-9.]+)元',str(r['每10份分红']))
                        if not match: raise ValueError('Unknown dividend units')
                        ex=pd.Timestamp(r['除息日'])
                        if ex<raw.index[0] or ex>raw.index[-1]: continue
                        if ex not in raw.index: raise ValueError('Dividend ex date missing raw bar')
                        divs.append(dict(ex_date=str(ex.date()),pay_date=str(r['分红发放日']),amount=float(match[1])/10))
                if '拆分折算日' in table:
                    found_split=True
                    for _,r in table.iterrows():
                        if '暂无' in str(r['拆分折算日']): continue
                        date=str(r['拆分折算日'])
                        if pd.Timestamp(date)<raw.index[0]: continue
                        if (code,date) not in SPLIT_EFFECTIVE: raise ValueError('Unverified split effective date')
                        effective=SPLIT_EFFECTIVE[(code,date)]
                        if pd.Timestamp(effective) not in raw.index: raise ValueError('Missing split date')
                        a,b=map(float,str(r['拆分折算比例']).split(':'))
                        splits.append(dict(date=effective,ratio=b/a,source_date=date))
            if not(found_div and found_split): raise ValueError('Missing corporate-action tables')
            lot=100;currency='CNY'
        signal=total_return_frame(raw,divs,splits)
        if signal.close.pct_change().abs().max()>.40: raise ValueError('Large unexplained adjusted price jump')
        assets[symbol]=dict(raw=raw,signal=signal,dividends=divs,splits=splits,
                            lot=lot,currency=currency,sector=sector,kind=kind)
        audit.append(dict(symbol=symbol,first=str(raw.index[0].date()),last=str(raw.index[-1].date()),
                          rows=len(raw),dividends=divs,splits=splits,
                          max_abs_total_return=float(signal.close.pct_change().abs().max())))
    return assets,audit

def fx_series(index):
    x=json.loads((ROOT/'data/hkd-cny-frankfurter.json').read_text())
    if x['base']!='HKD': raise ValueError('Wrong FX base')
    fx=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):r['CNY'] for d,r in x['rates'].items()}).sort_index()
    # ECB reference is published after Asian close; use from next calendar day.
    aligned=fx.reindex(fx.index.union(index)).ffill().reindex(index)
    if aligned.isna().any() or (aligned<=0).any(): raise ValueError('FX history incomplete')
    return aligned

if __name__=='__main__':
    assets,audit=load_assets()
    (ROOT/'results/portfolio-data-audit.json').write_text(json.dumps(audit,indent=2))
    for r in audit: print(r['symbol'],r['rows'],'dividends',len(r['dividends']),'splits',len(r['splits']), 'max daily',round(r['max_abs_total_return'],4))

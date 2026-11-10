"""Ablation after the first results: exploratory, NOT a fresh holdout test.

Tests whether the ATR exit or the entry threshold explains missed trends.
No winner is silently promoted. All tested variants are retained.
"""
import json
from pathlib import Path
import pandas as pd
from trend_engine import frame,signals,backtest

ROOT=Path(__file__).resolve().parent
rows=[]
for file in sorted((ROOT/'data').glob('USHJ*.json')):
    df=frame(json.loads(file.read_text())['bars'])
    variants={
        'original':signals(df).target,
        'remove_ATR_stop':signals(df,variant='no_stop').target,
        'entry_0.5_no_stop':signals(df,variant='no_stop',entry=.5).target,
        'entry_0.25_no_stop':signals(df,variant='no_stop',entry=.25).target,
        'EMA20_60':(df.close.ewm(span=20,adjust=False).mean()>df.close.ewm(span=60,adjust=False).mean()).astype(float)
    }
    for name,target in variants.items():
        for period,start,end in [('validation','2022-01-01','2023-12-31'),('posthoc_2024_plus','2024-01-01',None)]:
            metrics,_=backtest(df,target,start,end,15)
            rows.append({'symbol':file.stem,'variant':name,'period':period,**metrics})
result={'status':'exploratory ablation after viewing initial holdout; not unbiased OOS selection','records':rows}
(ROOT/'results/ablation-v1.json').write_text(json.dumps(result,indent=2,allow_nan=False))
t=pd.DataFrame(rows)
print(t[t.symbol=='USHJ512480'][['variant','period','cagr','max_drawdown','sharpe','entries','exposure']].to_string(index=False))
print('Cross-asset median Sharpe by variant/period')
print(t.groupby(['period','variant']).sharpe.median().to_string())

"""Transparent exploratory comparison: earlier holdout already viewed."""
import json
from pathlib import Path
import pandas as pd
from trend_engine import frame,structure_change_v2,backtest

ROOT=Path(__file__).resolve().parent
records=[]
for file in sorted((ROOT/'data').glob('USHJ*.json')):
    df=frame(json.loads(file.read_text())['bars'])
    sig=structure_change_v2(df)
    sig.to_csv(ROOT/'results'/f'{file.stem}-v2-signals.csv')
    for name,start,end in [('validation','2022-01-01','2023-12-31'),('exploratory_2024_plus','2024-01-01',None),('full',None,None)]:
        for cost in [5,15,30]:
            m,path=backtest(df,sig.target,start,end,cost)
            records.append({'symbol':file.stem,'strategy':'structure_change_v2','period':name,**m})
            if name=='full' and cost==5:
                path.to_csv(ROOT/'results'/f'{file.stem}-structure_change_v2-path.csv')
(ROOT/'results/revision-v2.json').write_text(json.dumps({'status':'Exploratory; previous evaluation sample already observed. Do not call this fresh OOS performance.','records':records},indent=2,allow_nan=False))
t=pd.DataFrame(records)
print(t[(t.period=='exploratory_2024_plus')&(t.cost_bps_per_side==15)][['symbol','cagr','max_drawdown','sharpe','entries','exposure']].to_string(index=False))

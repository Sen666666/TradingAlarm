"""Reproducible baseline experiment; outputs are provisional pending data audit."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from trend_engine import frame,signals,baselines,backtest

ROOT=Path(__file__).resolve().parent

def run(symbols):
    records=[]
    out=ROOT/'results'
    out.mkdir(exist_ok=True)
    periods={'development':(None,'2021-12-31'),'validation':('2022-01-01','2023-12-31'),'historical_holdout':('2024-01-01',None),'full':(None,None)}
    for symbol in symbols:
        raw=json.loads((ROOT/'data'/f'{symbol}.json').read_text())
        if raw['overlap_conflicts']:
            raise ValueError('Paging conflict: '+symbol)
        df=frame(raw['bars'])
        f=signals(df)
        candidates=baselines(df)
        candidates['trend_change_v1']=f.target
        f.to_csv(out/f'{symbol}-signals.csv',float_format='%.9g')
        for strategy in candidates:
            for period,(start,end) in periods.items():
                for cost in [5,15,30]:
                    try:
                        metrics,path=backtest(df,candidates[strategy],start,end,cost)
                    except ValueError:
                        continue
                    records.append({'symbol':symbol,'strategy':strategy,'period':period,**metrics,'data_sha256':raw['bars_sha256']})
                    if period=='full' and cost==5:
                        path.to_csv(out/f'{symbol}-{strategy}-path.csv',float_format='%.9g')
    result={'status':'provisional; Q adjustment not independently verified','engine_sha256':hashlib.sha256((ROOT/'trend_engine.py').read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),'records':records}
    (out/'baseline-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    pd.DataFrame(records).to_csv(out/'baseline-results.csv',index=False)
    table=pd.DataFrame(records)
    if not table.empty:
        view=table[(table.period=='historical_holdout')&(table.cost_bps_per_side==5)]
        print(view[['symbol','strategy','cagr','max_drawdown','sharpe','entries','exposure']].to_string(index=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('symbols',nargs='*')
    args=parser.parse_args()
    run(args.symbols or [p.stem for p in sorted((ROOT/'data').glob('*.json')) if json.loads(p.read_text()).get('bars')])

"""One-factor stress audit of an existing baseline, not parameter optimization."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from cross_market import load_hk
from trend_engine import frame
from cash_ledger import run_ledger,total_return_signal_frame

ROOT=Path(__file__).resolve().parent
BASE=dict(ma=200,vol_window=60,risk=.15,cost=15,extra_delay=0)
CASES={'baseline':BASE}
for key,values in [('ma',[150,250]),('vol_window',[40,120]),('risk',[.10,.20]),
                   ('cost',[5,30]),('extra_delay',[1,2])]:
    for value in values: CASES[f'{key}_{value}']={**BASE,key:value}

def target_for(df,settings):
    signal=(df.close>df.close.rolling(settings['ma']).mean()).astype(float)
    vol=np.log(df.close).diff().rolling(settings['vol_window']).std()*np.sqrt(252)
    target=signal*(settings['risk']/vol.replace(0,np.nan)).clip(upper=1).fillna(0)
    return target.shift(settings['extra_delay']).fillna(0)

def main():
    protocol={'created':'2026-10-17','status':'Exploratory, all histories already observed',
              'purpose':'Detect fragility; do not select the best-performing setting',
              'cases':CASES,'start':'2022-01-01',
              'scope':'Independent single-asset sleeves, not a multi-asset portfolio',
              'risk_note':'Annual volatility target is not a maximum drawdown limit',
              'no_claims':['Not proof against overfitting','Not fresh out-of-sample','Not a strategy recommendation'],
              'revised_user_scope':'Remove Trend Animal comparison. Develop durable A-share/HK trend and position management strategy.'}
    (ROOT/'results/robustness-protocol.json').write_text(json.dumps(protocol,indent=2))
    raw,events,_=load_hk()
    assets=[('HK02800',raw,total_return_signal_frame(raw,events),events,500)]
    for source in sorted((ROOT/'data').glob('USHJ*.json')):
        df=frame(json.loads(source.read_text())['bars'])
        assets.append((source.stem,df,df,[],1e-6))
    records=[]
    for symbol,raw,signal,events,lot in assets:
        for case,settings in CASES.items():
            m,p=run_ledger(raw,target_for(signal,settings),events,start=protocol['start'],
                           lot=lot,cost_bps=settings['cost'])
            records.append(dict(symbol=symbol,case=case,**settings,**m))
        print(symbol,'complete',flush=True)
    (ROOT/'results/robustness.json').write_text(json.dumps(dict(protocol=protocol,records=records),indent=2,allow_nan=False))
    x=pd.DataFrame(records)
    x.to_csv(ROOT/'results/robustness.csv',index=False)
    print(x[x.symbol.isin(['HK02800','USHJ512480'])][['symbol','case','cagr','max_drawdown','sharpe']].to_string(index=False))

if __name__=='__main__': main()

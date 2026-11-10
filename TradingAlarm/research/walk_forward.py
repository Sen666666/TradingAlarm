"""Retrospective annual model selection, strictly using prior-year observations.

The rule itself is post-hoc research, not a new out-of-sample claim. Training
scores use continuous standalone accounts, not reset accounts at each window.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from cross_market import candidates, volatility_size, load_hk
from cash_ledger import run_ledger, total_return_signal_frame
from trend_engine import frame

ROOT=Path(__file__).resolve().parent

def choose_models(returns, years, minimum=600):
    choices=[]
    for year in years:
        train=returns.loc[(returns.index>=pd.Timestamp(year-3,1,1)) &
                          (returns.index<pd.Timestamp(year,1,1))].dropna()
        if len(train)<minimum: continue
        sd=train.std(ddof=1)
        score=(train.mean()/sd.replace(0,np.nan)*np.sqrt(252)).dropna()
        if score.empty: continue
        # Alphabetical stable tie break; never look at evaluation-year returns.
        winner=sorted(score.index,key=lambda s:(-float(score[s]),s))[0]
        choices.append(dict(year=int(year),strategy=winner,training_days=len(train),
                            training_end=str(train.index[-1].date()),
                            scores={k:float(v) for k,v in score.items()}))
    return choices

def year_stats(path):
    result=[]
    for year,p in path.groupby(path.index.year):
        r=p['return']; nav=(1+r).cumprod()
        dd=nav.to_numpy()/np.maximum.accumulate(np.r_[1.,nav.to_numpy()])[1:]-1
        result.append(dict(year=int(year),return_total=float(nav.iloc[-1]-1),
                           max_drawdown_within_year=float(dd.min()),days=len(p),
                           sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std()>0 else None))
    return result

def main():
    protocol=dict(status='Retrospective exploratory selection; not fresh holdout',
                  selection='Highest trailing three calendar years net Sharpe; stable alphabetical ties',
                  minimum_training_days=600,first_evaluation_year=2024,
                  cost_bps_per_side=15,sizing='causal vol15 cap1, 60 days',
                  timing='Choose at prior year final close, execute at next year first open',
                  caveats=['Training accounts are continuous, not reset per window.',
                           'No model or parameter selection uses evaluation-year prices.',
                           'Model definitions and this evaluation design were chosen after observing historical results.',
                           'Inherited cross-market data, execution and survivor-selection limitations apply.'])
    (ROOT/'results/walk-forward-protocol.json').write_text(json.dumps(protocol,indent=2))
    raw,events,_=load_hk()
    assets=[('HK02800',raw,total_return_signal_frame(raw,events),events,500)]
    for source in sorted((ROOT/'data').glob('USHJ*.json')):
        df=frame(json.loads(source.read_text())['bars'])
        assets.append((source.stem,df,df,[],1e-6))
    records=[]; selections=[]; overall=[]
    for symbol,raw,signal,events,lot in assets:
        targets=candidates(signal).mul(volatility_size(signal),axis=0)
        train_returns={}
        for name in targets:
            _,p=run_ledger(raw,targets[name],events,lot=lot,cost_bps=15)
            train_returns[name]=p['return']
        choices=choose_models(pd.DataFrame(train_returns),range(2024,raw.index[-1].year+1))
        if not choices: continue
        # Map each close decision to the year of its next execution session.
        next_year=pd.Series(raw.index,index=raw.index).shift(-1).dt.year
        adaptive=pd.Series(0.,index=raw.index)
        for c in choices:
            mask=next_year==c['year']
            adaptive.loc[mask]=targets.loc[mask,c['strategy']]
            selections.append(dict(symbol=symbol,**c))
        start=f"{choices[0]['year']}-01-01"
        evaluation=targets.copy(); evaluation['annual_selected']=adaptive
        for name in evaluation:
            m,p=run_ledger(raw,evaluation[name],events,start=start,lot=lot,cost_bps=15)
            overall.append(dict(symbol=symbol,strategy=name,**m))
            records.extend(dict(symbol=symbol,strategy=name,**r) for r in year_stats(p))
            if name=='annual_selected': p.to_csv(ROOT/'results'/f'{symbol}-walk-forward-path.csv')
        print(symbol,'complete',flush=True)
    (ROOT/'results/walk-forward.json').write_text(json.dumps(dict(protocol=protocol,selections=selections,overall=overall,yearly=records),indent=2,allow_nan=False))
    pd.DataFrame(records).to_csv(ROOT/'results/yearly-stability.csv',index=False)
    pd.DataFrame(overall).to_csv(ROOT/'results/walk-forward-overall.csv',index=False)
    print(pd.DataFrame(overall).query("strategy in ['sma200','structure_change_v2','annual_selected']")[['symbol','strategy','cagr','max_drawdown','sharpe']].to_string(index=False))

if __name__=='__main__': main()

"""Mechanism ablations, all observed history is exploratory. No live routing."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from portfolio_data import load_assets, ROOT
from portfolio_engine import run_portfolio, allocate, clusters
OUT=ROOT/'results/sector-v1'

def fast_gate(frame):
    c=frame.close
    return (c>c.rolling(60).mean()) & (c.pct_change(21)>0)

def rotation_allocator(returns, eligible, assets, passive=False):
    # Three equal strategic sleeves: top three eligible equities share 60%;
    # gold/bonds each 20% when eligible. Missing sleeves remain cash.
    w=pd.Series(0.,index=sorted(assets))
    if len(returns)<126:return w,[]
    r=returns.tail(126)
    score=sum(np.log1p(r.tail(h)).sum()/np.sqrt(h) for h in [21,63,126])/3
    equity=[n for n,a in assets.items() if a['kind']=='equity' and eligible[n]]
    selected=[]; seen=set()
    for n in sorted(equity,key=lambda n:(-score[n],n)):
        sector=assets[n]['sector']
        if sector in seen:continue
        selected.append(n);seen.add(sector)
        if len(selected)==3:break
    for n in selected:w[n]=.20
    for n,a in assets.items():
        if a['kind']!='equity' and eligible[n]:w[n]=.20
    hk=[n for n,a in assets.items() if a['currency']=='HKD']
    if w[hk].sum()>.30:w[hk]*=.30/w[hk].sum()
    groups=clusters(r.tail(60).corr().fillna(0))
    for g in groups:
        if w[g].sum()>.40:w[g]*=.40/w[g].sum()
    cov=r.tail(60).cov()*252
    cov=.5*cov+.5*np.diag(np.diag(cov))
    vol=np.sqrt(max(0,float(w@cov@w)))
    if vol>.12:w*=.12/vol
    return w,groups

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    cases={
      'old_rules_20pct':{},
      'fast_gate_only':{'gate_fn':fast_gate},
      'sector_selection_only':{'allocator_fn':rotation_allocator},
      'fast_sector_selection':{'gate_fn':fast_gate,'allocator_fn':rotation_allocator},
      'fast_sector_high_cost':{'gate_fn':fast_gate,'allocator_fn':rotation_allocator,'cost_bps':30,'fx_bps':30},
      'fast_sector_delay':{'gate_fn':fast_gate,'allocator_fn':rotation_allocator,'extra_delay':2},
    }
    protocol={'status':'exploratory; all existing history previously seen','target_drawdown':.20,
      'cases':list(cases),'fast_gate':'close>SMA60 and return21>0',
      'rotation':'Equal 20% slots, top 3 equity sectors by equal mean log-return/sqrt(h) for h=21,63,126; no duplicate named sector; gold and bonds 20% each if eligible. HK cap30%, correlated cluster40%, volatility12%. Unused slots cash.',
      'limitations':['Allocation ablation changes weighting and concentration assumptions together; does not isolate pure ranking alpha','Survivor universe of 11 ETFs, incomplete sector coverage','No fresh time holdout; cannot claim validated future profitability'],
      'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'references':['https://onlinelibrary.wiley.com/doi/full/10.1111/0022-1082.00146'],
      'selection':'Retain every case; no parameter search or winner deployment'}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    assets,_=load_assets();results=[]
    for name,kw in cases.items():
        m,p,trades,decisions=run_portfolio(assets,minimum_fees=True,participation=.01,scenario_budget=True,drawdown_target=.20,**kw)
        p.to_csv(OUT/(name+'-path.csv'))
        (OUT/(name+'-orders.json')).write_text(json.dumps(trades))
        (OUT/(name+'-decisions.json')).write_text(json.dumps(decisions))
        annual={str(y):float((1+g.return_daily).prod()-1) for y,g in p.groupby(p.index.year)}
        m.update(case=name,annual_returns=annual)
        results.append(m)
        (OUT/'results.json').write_text(json.dumps(results,indent=2))
        print(name, 'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'fees',round(m['fees']),flush=True)
if __name__=='__main__':main()

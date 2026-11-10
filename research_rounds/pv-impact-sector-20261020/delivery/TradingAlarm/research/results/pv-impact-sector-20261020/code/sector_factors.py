"""Small declared family: ranking factors, breakout gating, concentration."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from portfolio_data import ROOT,load_assets
from portfolio_engine import run_portfolio,trend_gate,clusters
from sector_extension import EXTENSION
OUT=ROOT/'results/sector-v3'
def breakout_gate(frame):
    enter=frame.close>frame.high.shift().rolling(55).max()
    leave=frame.close<frame.low.shift().rolling(20).min()
    held=False;states=[]
    for buy,sell in zip(enter,leave):
        if sell:held=False
        elif buy:held=True
        states.append(held)
    return pd.Series(states,index=frame.index)
def scores(returns,method):
    log=np.log1p(returns)
    if method=='short':return sum(log.tail(h).sum()/np.sqrt(h) for h in [21,63,126])/3
    # Exclude latest month to distinguish medium-term persistence from short
    # reversal. Equal horizon ranks avoid fitting coefficients to returns.
    a=log.tail(126).iloc[:-21].sum();b=log.tail(252).iloc[:-21].sum()
    if method=='long':return (a.rank(pct=True)+b.rank(pct=True))/2
    if method=='risk_adjusted':
        vol=returns.tail(60).std().clip(lower=.003)
        return ((a/vol).rank(pct=True)+(b/vol).rank(pct=True))/2
    if method=='breadth':return (returns.tail(126)>0).mean()
    if method=='none':return pd.Series(0.,index=returns.columns)
    raise ValueError(method)
def allocator_factory(method='long',top=3,retain_rank=None):
 previous_selection=[]
 def allocator(returns,eligible,assets,passive=False):
    nonlocal previous_selection
    names=sorted(assets);w=pd.Series(0.,index=names)
    if len(returns)<252:return w,[]
    score=scores(returns,method)
    selected=[];seen=set()
    eq=[n for n in names if assets[n]['kind']=='equity' and (eligible[n] or passive)]
    ranked=sorted(eq,key=lambda n:(-score[n],n))
    if retain_rank is not None:
        for n in previous_selection:
            if n in ranked[:retain_rank] and assets[n]['sector'] not in seen:
                selected.append(n);seen.add(assets[n]['sector'])
    for n in ranked:
        if top and len(selected)>=top:break
        sector=assets[n]['sector']
        if sector in seen:continue
        seen.add(sector);selected.append(n)
        if top and len(selected)==top:break
    previous_selection=selected.copy()
    slots=top or len(selected)
    if slots:
        for n in selected:w[n]=min(.20,.60/slots)
    for n,a in assets.items():
        if a['kind']!='equity' and (eligible[n] or passive):w[n]=.20
    hk=[n for n,a in assets.items() if a['currency']=='HKD']
    if w[hk].sum()>.30:w[hk]*=.30/w[hk].sum()
    r=returns.tail(60);groups=clusters(r.corr().fillna(0))
    for g in groups:
        if w[g].sum()>.40:w[g]*=.40/w[g].sum()
    cov=r.cov()*252;cov=.5*cov+.5*np.diag(np.diag(cov))
    vol=np.sqrt(max(0,float(w@cov@w)))
    if vol>.12:w*=.12/vol
    return w,groups
 return allocator
CASES=[('short',3,'slow'),('long',3,'slow'),('risk_adjusted',3,'slow'),('breadth',3,'slow'),
       ('long',6,'slow'),('none',0,'slow'),('long',3,'breakout'),('none',0,'breakout'),('none',0,'passive')]
def expanded_assets():
 u=json.loads((ROOT/'portfolio-protocol.json').read_text())['universe'];u.update(EXTENSION)
 return load_assets(u)[0]
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol={'scope':'15 surviving A/HK ETFs,2022+, exploratory not untouched OOS','cases':CASES,
 'rules':{'long':'equal percentile ranks of 126-21 and252-21 log returns','risk_adjusted':'same but divide horizon returns by lagged60day volatility before ranking','breadth':'fraction positive returns over126 sessions; price-path persistence hypothesis, not independent fundamental quality','breakout':'close above previous55high enters; close below previous20low exits; next-open execution, no pyramiding, not a full Turtle replication','position':'equity60% split3 or6 slots,or all eligible named sectors; gold20%,bond20%; perasset20%,HK30%,corrcluster40%,estimatedvol12%,20% target scenario budget,2% resizing band'},
 'tradeoff':'Top6 uses smaller fixed slots and may leave more cash. Equal risk target does not mean identical realized risk; report ex-post risk-matched diagnostics separately.',
 'sources':['https://www.tradingblox.com/originalturtles/originalturtlerules.pdf','https://onlinelibrary.wiley.com/doi/full/10.1111/0022-1082.00146'],
 'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 assets=expanded_assets();records=[]
 for method,top,gate in CASES:
    name=f'{method}-top{top}-{gate}'
    m,p,t,d=run_portfolio(assets,gate_fn=breakout_gate if gate=='breakout' else trend_gate,
      allocator_fn=allocator_factory(method,top),passive=gate=='passive',drawdown_target=.20,
      scenario_budget=True,rebalance_band=.02,minimum_fees=True,participation=.01)
    m.update(case=name,annual_returns={str(y):float((1+g.return_daily).prod()-1) for y,g in p.groupby(p.index.year)})
    records.append(m);p.to_csv(OUT/(name+'-path.csv'))
    (OUT/(name+'-orders.json')).write_text(json.dumps(t));(OUT/(name+'-decisions.json')).write_text(json.dumps(d))
    (OUT/'results.json').write_text(json.dumps(records,indent=2))
    print(name,'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'Sharpe',round(m['sharpe'],2),flush=True)
if __name__=='__main__':main()

"""Rank hysteresis and geographic transfer; never choose optimal threshold."""
import json,hashlib
from pathlib import Path
from sector_factors import expanded_assets,allocator_factory
from portfolio_engine import run_portfolio
from portfolio_data import ROOT
OUT=ROOT/'results/sector-v4'
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 cases=[('pooled_no_buffer','pooled',None,{}),('pooled_rank_buffer','pooled',6,{}),
 ('buffer_high_cost','pooled',6,{'cost_bps':30,'fx_bps':30}),('buffer_delay','pooled',6,{'extra_delay':2}),
 ('a_share_transfer','CN',6,{}),('hk_transfer','HK',6,{})]
 protocol={'cases':[(n,u,b,k) for n,u,b,k in cases],
 'rule':'Enter top3 eligible equity names; retain prior selected names while still eligible and ranked top6; fill vacant slots by ranking. Trend exit unchanged. Selection state means desired list, not executed inventory. Fresh state per simulation.',
 'scope':'Same short21/63/126 rank,slow200MA gate,15ETF pool. Research20% drawdown target,all costs and prior volume constraint retained.',
 'transfer_limit':'CN uses CN equity plus CN gold/bond;HK uses3 HK equities plus CN gold/bond,keepsHK30% cap. HK breadth insufficient to test top3 vs top6; tests cash/defensive implementation only, not independent sector selection proof.',
 'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 allassets=expanded_assets();records=[]
 for name,universe,rank,kw in cases:
    assets={n:a for n,a in allassets.items() if universe=='pooled' or a['kind']!='equity' or (a['currency']=='HKD')==(universe=='HK')}
    m,p,t,d=run_portfolio(assets,allocator_fn=allocator_factory('short',3,rank),drawdown_target=.20,
      scenario_budget=True,rebalance_band=.02,minimum_fees=True,participation=.01,**kw)
    m.update(case=name,annual_returns={str(y):float((1+g.return_daily).prod()-1) for y,g in p.groupby(p.index.year)})
    records.append(m);p.to_csv(OUT/(name+'-path.csv'))
    (OUT/(name+'-orders.json')).write_text(json.dumps(t));(OUT/(name+'-decisions.json')).write_text(json.dumps(d))
    (OUT/'results.json').write_text(json.dumps(records,indent=2))
    print(name,'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'orders',m['orders'],flush=True)
if __name__=='__main__':main()

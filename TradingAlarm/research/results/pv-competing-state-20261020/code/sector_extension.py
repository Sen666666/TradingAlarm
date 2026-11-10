"""Expanded exposure and turnover mechanism checks, all variants retained."""
import json,hashlib
from pathlib import Path
from portfolio_data import ROOT,load_assets
from portfolio_engine import run_portfolio,trend_gate
from sector_experiment import fast_gate,rotation_allocator
OUT=ROOT/'results/sector-v2'
EXTENSION={'USHJ512690':['alcohol','equity'],'USHJ512980':['media','equity'],
           'USHJ512400':['metals','equity'],'USHJ515220':['coal','equity']}
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 universe=json.loads((ROOT/'portfolio-protocol.json').read_text())['universe'];universe.update(EXTENSION)
 protocol={'status':'exploratory, no fresh holdout','added_universe':EXTENSION,
 'reason':'Add consumer, communication and commodity cyclicals absent from the initial technology/health/finance-heavy list. Selected existing funds; not full point-in-time universe.',
 'band':.02,'band_rule':'Skip normal resizing smaller than2% of NAV; do not suppress first entries, full exits, guard or scenario-budget reductions.',
 'cases':'Original and extended universe, each slow/fast gate and band0/2%; fixed rotation allocator,20% drawdown research target.',
 'sources':{'coal_split':'https://pdf.dfcfw.com/pdf/H2_AN202404071630035002_1.pdf','alcohol_split':'https://finance.sina.com.cn/roll/2021-05-11/doc-ikmxzfmm1691646.shtml'},
 'source_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 original,_=load_assets();expanded,audit=load_assets(universe)
 (OUT/'expanded-data-audit.json').write_text(json.dumps(audit,indent=2))
 results=[]
 for label,assets in [('original',original),('expanded',expanded)]:
  for speed,gate in [('slow',trend_gate),('fast',fast_gate)]:
   for band in [0,.02]:
    name=f'{label}-{speed}-band{band}'
    m,p,t,d=run_portfolio(assets,gate_fn=gate,allocator_fn=rotation_allocator,drawdown_target=.20,
      scenario_budget=True,rebalance_band=band,minimum_fees=True,participation=.01)
    m.update(case=name,annual_returns={str(y):float((1+g.return_daily).prod()-1) for y,g in p.groupby(p.index.year)})
    results.append(m);p.to_csv(OUT/(name+'-path.csv'))
    (OUT/(name+'-orders.json')).write_text(json.dumps(t))
    (OUT/'results.json').write_text(json.dumps(results,indent=2))
    print(name,'CAGR',round(m['cagr']*100,2),'MDD',round(m['max_drawdown']*100,2),'orders',m['orders'],flush=True)
if __name__=='__main__':main()

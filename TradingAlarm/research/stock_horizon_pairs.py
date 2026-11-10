"""Same-entry, paired horizon diagnostics; not an executable account simulation."""
import json
import pandas as pd
from stock_entry_diagnostic import ROOT,select
OUT=ROOT/'results/stock-horizon-pairs'
H=[10,21,63,126]

def summarize(g):
 cols=[f'forward_{h}' for h in H];paired=g.dropna(subset=cols)
 result={'selected':len(g),'paired':len(paired),'excluded_missing_any':len(g)-len(paired),'dates':int(paired.date.nunique())}
 for h in H:
  col=f'forward_{h}';dates=paired.groupby('date')[col].mean()
  result[f'mean_{h}']=float(dates.mean());result[f'fraction80_{h}']=float(paired[col].ge(.8).mean())
 for short in [10,21]:
  delta=paired.assign(delta=paired.forward_126-paired[f'forward_{short}']).groupby('date').delta.mean()
  result[f'long_minus_{short}']=float(delta.mean())
  result[f'long_beats_{short}_dates']=float(delta.gt(0).mean())
 tails=paired[paired.forward_126.ge(.8)]
 result['retrospective_126_tail_count']=len(tails)
 result['tail_unique_symbols']=int(tails.symbol.nunique())
 result['tail_unique_dates']=int(tails.date.nunique())
 for h in H:result[f'tail_subset_mean_{h}']=float(tails[f'forward_{h}'].mean()) if len(tails) else None
 return result

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'selection':'Existing continuous20 monthly breakout/SMA200 candidates; fixed lowATR and RS top10, no label-based refilling','maturity':'All cohorts restricted to t+127 <= observed calendar end; pair only stocks with all four labels','labels':'Adjusted close t+1 to close t+1+horizon; not next-open fills','horizons':H,'warning':'21 is one trading month, not the HK 20-day rule; no trend-triggered exits simulated','limitations':['Paired complete cases can exclude terminal events; report exclusion counts','Overlapping observations; not independent trades or deployable return','No costs, dated limits, cash ledger or full universe certification','Tail subset chosen retrospectively for diagnosis only; cannot select it at entry','Longer horizons have mechanically more time; mean horizon returns are not comparable annualized strategies']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 d=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');d=d[d.active20.eq(20)]
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
 rows=[];annual=[];chosen=[]
 for strategy,key in [('low_atr','atr_fraction'),('rs','rs_order')]:
  g=select(d,key);g=g[g.date.le(cal[-128])].copy();g['strategy']=strategy;chosen.append(g)
  for period,part in [('2015-2021',g[g.date.dt.year<2022]),('2022+',g[g.date.dt.year>=2022])]:rows.append(dict(strategy=strategy,period=period,**summarize(part)))
  for year,part in g.groupby(g.date.dt.year):annual.append(dict(strategy=strategy,year=int(year),**summarize(part)))
 pd.concat(chosen).to_parquet(OUT/'selected.parquet',index=False)
 (OUT/'summary.json').write_text(json.dumps(rows,indent=2,allow_nan=False));pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False)
 print(pd.DataFrame(rows)[['strategy','period','selected','paired','mean_10','mean_21','mean_63','mean_126','retrospective_126_tail_count','tail_subset_mean_10','tail_subset_mean_21','tail_subset_mean_126']].to_string(index=False))
if __name__=='__main__':main()

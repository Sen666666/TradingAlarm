"""Contemporaneous matching; labels never participate in pair selection."""
import json
import numpy as np
import pandas as pd
from stock_entry_diagnostic import ROOT,select
from stock_entry_robustness import bootstrap_year_means
OUT=ROOT/'results/stock-smooth-matched'
FEATURES=['momentum126_21','atr_fraction','turnover60']

def match_date(g,caliper=.2):
 g=g.copy().set_index('symbol',drop=False)
 ranks=g[FEATURES].rank(method='average',pct=True)
 chosen=select(g.reset_index(drop=True),'smooth_score');remaining=set(g.symbol)-set(chosen.symbol);pairs=[]
 for s in chosen.itertuples():
  candidates=sorted(c for c in remaining if g.at[c,'smooth_score']>s.smooth_score)
  if not candidates:continue
  distances=(ranks.loc[candidates]-ranks.loc[s.symbol]).abs()
  valid=distances.index[distances.le(caliper).all(axis=1)]
  if len(valid)==0:continue
  nearest=distances.loc[valid].pow(2).sum(axis=1).sort_values(kind='stable').index[0]
  remaining.remove(nearest)
  pairs.append({'symbol':s.symbol,'control':nearest,'max_rank_gap':float(distances.loc[nearest].max()),'score_gap':float(g.at[nearest,'smooth_score']-s.smooth_score)})
 return pairs,len(chosen)

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'features':FEATURES,'caliper':.2,'matching':'Within-date percentile ranks, each absolute gap<=.2; minimum squared distance; greedy fixed smooth-score order, symbol tie-break, no replacement','control':'Outside top10, strictly less continuous score; matching never uses future labels','limitations':['Matching is observational and incomplete, not causal identification','No control for sectors, marketcap, momentum252 or omitted variables','Only matchable selections covered; no refilling after missing future prices','Dependent monthly labels; annual bootstrap descriptive with few blocks','Previously inspected history, price-only outcome without execution or cost model']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 d=pd.read_parquet(ROOT/'results/stock-smooth-momentum/candidate-pool.parquet');rows=[];coverage=[]
 for dt,g in d.groupby('date'):
  pairs,n=match_date(g);coverage.append(dict(date=dt,selected=n,matched=len(pairs),pool=len(g)))
  lookup=g.set_index('symbol')
  for p in pairs:
   p['date']=dt
   for h in [10,21,63,126]:
    p[f'selected_{h}']=lookup.at[p['symbol'],f'forward_{h}'];p[f'control_{h}']=lookup.at[p['control'],f'forward_{h}']
   rows.append(p)
 pairs=pd.DataFrame(rows);pairs.to_parquet(OUT/'pairs.parquet',index=False);pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False)
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();summary=[]
 for h in [10,21,63,126]:
  m=pairs[pairs.date.le(cal[-(h+2)])]
  for name,g in [('early',m[m.date.dt.year<2022]),('recent',m[m.date.dt.year>=2022])]:
   valid=g.dropna(subset=[f'selected_{h}',f'control_{h}']);delta=(valid[f'selected_{h}']-valid[f'control_{h}']).groupby(valid.date).mean()
   summary.append(dict(period=name,horizon=h,matched=len(g),priced=len(valid),dates=len(delta),difference=float(delta.mean()),positive_dates=float(delta.gt(0).mean()),mean_score_gap=float(valid.score_gap.mean()),year_bootstrap=bootstrap_year_means(delta)))
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(pd.DataFrame(summary).drop(columns='year_bootstrap').to_string(index=False));print('coverage',sum(x['matched'] for x in coverage),sum(x['selected'] for x in coverage))
if __name__=='__main__':main()

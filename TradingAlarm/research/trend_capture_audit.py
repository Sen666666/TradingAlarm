"""Exact additive log-relative-return attribution on passive up/down days; hindsight diagnostic."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
OUT=Path('results/trend-capture-audit')
def decompose(strategy,benchmark):
    if not strategy.index.equals(benchmark.index):raise ValueError('Calendar mismatch')
    if (strategy<=-1).any() or (benchmark<=-1).any():raise ValueError('Invalid simple return')
    a=np.log1p(strategy);b=np.log1p(benchmark);out=[]
    for label,mask in [('up',benchmark.gt(0)),('down',benchmark.lt(0)),('flat',benchmark.eq(0))]:
        x=float(a.loc[mask].sum());y=float(b.loc[mask].sum());out.append(dict(day_type=label,days=int(mask.sum()),strategy_log_return=x,benchmark_log_return=y,relative_log_contribution=x-y,participation=x/y if abs(y)>1e-12 else None))
    error=abs(sum(r['relative_log_contribution'] for r in out)-float((a-b).sum()))
    assert error<1e-10
    return out,error

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(method='Classify days by samepoolpassive netdailyreturn sign. Sum log1p(actualaccountdailyreturn) by category; strategy-minus-passive adds exactly to logrelativewealth. No returnnormalization ornewstrategy.',scope='ETF17/HK7 2022-2026Oct16; adaptivevolume, pairwisevolume, symmetricpairwisevolume allnames, plus symmetric3slots; basecostonly',interpretation='Retrospective dailyup/down attribution,not causal explanation orbull/bearregimes. Differentexposures,costs,holdingsandclaims combined; ratiosnotindependent performance statistics. Flat benchmarkdaysseparate.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2));rows=[];errors=[];hashes={}
 for group in ['etf17','hk7']:
  bp=Path('results/trend-pool-benchmark')/f'{group}-passive-base-path.parquet';benchmark=pd.read_parquet(bp);hashes[str(bp)]=hashlib.sha256(bp.read_bytes()).hexdigest()
  paths={'adaptive_all':Path('results/strength-symmetric-exit')/f'{group}-adaptive_geometry_price_volume_split_units-daily-base-path.parquet','pairwise_all':Path('results/trend-slot-workbench')/f'{group}-pairwise_volume-equal_capital-base-path.parquet','symmetric_all':Path('results/trend-slot-workbench')/f'{group}-symmetric_pairwise_volume-equal_capital-base-path.parquet','symmetric_three':Path('results/trend-slot-workbench')/f'{group}-symmetric_pairwise_volume-rank_slots-base-path.parquet'}
  for name,p in paths.items():
   f=pd.read_parquet(p);hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();assert f.index.equals(benchmark.index)
   for year in ['all']+list(sorted(f.index.year.unique())):
    mask=np.ones(len(f),dtype=bool) if year=='all' else f.index.year==year
    result,error=decompose(f.return_daily.loc[mask],benchmark.return_daily.loc[mask]);errors.append(error)
    for row in result:rows.append(dict(group=group,model=name,year=str(year),**row))
   assert abs(np.log(f.nav.iloc[-1]/benchmark.nav.iloc[-1])-sum(r['relative_log_contribution'] for r in rows if r['group']==group and r['model']==name and r['year']=='all'))<1e-10
 data=pd.DataFrame(rows);data.to_csv(OUT/'attribution.csv',index=False);(OUT/'validation.json').write_text(json.dumps(dict(attribution_checks=len(errors),max_error=max(errors),source_hashes=hashes),indent=2));print(data.loc[data.year.isin(['all','2026'])].to_string(index=False))
if __name__=='__main__':main()

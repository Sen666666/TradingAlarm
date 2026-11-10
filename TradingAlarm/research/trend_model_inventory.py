"""Deduplicate comparable strategy experiments and audit recorded paths; not new selection."""
import json,hashlib
from pathlib import Path
import pandas as pd
OUT=Path('results/trend-model-inventory')
def digest(frame):
 return hashlib.sha256(pd.util.hash_pandas_object(frame,index=True).values.tobytes()+json.dumps(list(frame.columns)).encode()).hexdigest()
def main():
 OUT.mkdir(exist_ok=True,parents=True);unique={};sources=[];duplicates=0;conflicts=[];maxerr=0.
 for p in sorted(Path('results').glob('*/results.json')):
  q=p.parent/'protocol.json'
  if not q.exists():continue
  protocol=json.loads(q.read_text())
  if not isinstance(protocol,dict) or 'strategies' not in protocol:continue
  data=json.loads(p.read_text())
  if not isinstance(data,list):continue
  for r in data:
   if not isinstance(r,dict) or r.get('group') not in ['etf17','hk7'] or r.get('cadence')!='daily' or r.get('allocation')!='equal_capital':continue
   pathfile=p.parent/(r['case']+'-path.parquet');ordersfile=p.parent/(r['case']+'-orders.json');f=pd.read_parquet(pathfile);orders=json.loads(ordersfile.read_text())
   nav=f.nav;dd=nav/nav.cummax().clip(lower=1)-1
   err=max(abs(float(nav.iloc[-1]-1)-r['total_return']),abs(float(dd.min())-r['max_drawdown']));assert err<1e-10,(p,r['case'],err);maxerr=max(maxerr,err)
   assert nav.index.min().year==2022 and nav.index.max()==pd.Timestamp('2026-10-16')
   assert len(orders)==r['orders']
   key=(r['strategy'],r['group'],r['scenario']);signature=digest(f);orderhash=hashlib.sha256(json.dumps(orders,sort_keys=True).encode()).hexdigest()
   source=dict(result=str(p),case=r['case'],path_hash=hashlib.sha256(pathfile.read_bytes()).hexdigest(),order_hash=hashlib.sha256(ordersfile.read_bytes()).hexdigest());sources.append(source)
   if key in unique:
    old=unique[key]
    if signature!=old['value_digest'] or orderhash!=old['order_digest']:conflicts.append(dict(key=key,first=old['source'],second=str(p)))
    else:duplicates+=1
    continue
   unique[key]=dict(strategy=r['strategy'],group=r['group'],scenario=r['scenario'],total_return=r['total_return'],max_drawdown=r['max_drawdown'],year2026=r['year2026']['return_fraction'],maximum_hindsight_interval_gain=float((nav/nav.cummin().clip(upper=1)-1).max()),average_cash_weight=r['average_cash_weight'],source=str(p),case=r['case'],value_digest=signature,order_digest=orderhash)
 (OUT/'conflicts.json').write_text(json.dumps(conflicts,indent=2));assert not conflicts,conflicts
 table=pd.DataFrame(unique.values());table.to_parquet(OUT/'unique-cases.parquet',index=False);families=[]
 for model,g in table.groupby('strategy'):
  assert len(g)==6 and set(g.group)=={'etf17','hk7'} and set(g.scenario)=={'base','cost2','delay1'}
  positives=bool(g.total_return.gt(0).all());risk=bool(g.max_drawdown.ge(-.2).all());base=g[g.scenario.eq('base')]
  families.append(dict(strategy=model,all_six_positive=positives,all_six_mdd_within20=risk,both_conditions=positives and risk,worst_case_return=float(g.total_return.min()),maximum_hindsight_interval_gain=float(g.maximum_hindsight_interval_gain.max()),etf_base=float(base[base.group.eq('etf17')].total_return.iloc[0]),hk_base=float(base[base.group.eq('hk7')].total_return.iloc[0]),base_case_sources=base[['group','source','case']].to_dict('records')))
 footprints={}
 for model,g in table.groupby('strategy'):
  signature=tuple((r.group,r.scenario,r.value_digest,r.order_digest) for r in g.sort_values(['group','scenario']).itertuples())
  footprints.setdefault(signature,[]).append(model)
 aliases=list(footprints.values());(OUT/'equivalent-observed-paths.json').write_text(json.dumps(aliases,indent=2))
 report=pd.DataFrame(families);report.to_json(OUT/'model-summary.json',orient='records',indent=2)
 distinct=report[report.strategy.isin([x[0] for x in aliases])]
 validation=dict(raw_case_rows=len(sources),unique_cases=len(table),distinct_models=len(report),exact_duplicate_cases=duplicates,distinct_observed_path_sets=len(aliases),distinct_path_sets_passing_both=int(distinct.both_conditions.sum()),conflicts=len(conflicts),max_recorded_metric_error=maxerr,all_six_positive=int(report.all_six_positive.sum()),all_six_mdd20=int(report.all_six_mdd_within20.sum()),both_conditions=int(report.both_conditions.sum()),any_path_interval80=int(table.maximum_hindsight_interval_gain.ge(.8).sum()),sources=sources,limits=['Scope only ETF17/HK7 daily equal-capital experiments with explicit allocation field; excludes other universes, allocations and missing older schemas.','Path metrics and repeated controls reconciled; not a new full corporate-action ledger audit for all historical experiments.','No Sharpe/CAGR ranking or chosen best model. Positive net PNL and20percentMDD screen is insufficient for requested ordinary-PNL and account-cycle objectives.','Maximum trough-to-later-peak return is hindsight descriptive bound on observed close NAV intervals, not predefined cycle performance.','63 versions on reused selected-survivor data are multiple development attempts, not63 independent validations.'])
 (OUT/'validation.json').write_text(json.dumps(validation,indent=2));print({k:v for k,v in validation.items() if k not in ['sources','limits']});print(report[report.both_conditions][['strategy','etf_base','hk_base','worst_case_return','maximum_hindsight_interval_gain']].to_string(index=False))
if __name__=='__main__':main()

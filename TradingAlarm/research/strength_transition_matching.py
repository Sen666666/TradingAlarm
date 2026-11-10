"""Outcome-blind same-date greedy score matching; fixed0.1caliper."""
import json
from pathlib import Path
import pandas as pd
from strength_transition_audit import changes,ROOT

def main():
 out=ROOT/'results/strength-transition-audit';scores=pd.read_parquet(ROOT/'results/broad-exit-disagreement/all-observed-signals.parquet');scores['date']=pd.to_datetime(scores.date);rows=[]
 for lag in [1,5]:
  f=changes(scores,lag);f=f.loc[f.strength.gt(6)];f['bin']=f.strength.le(8).map({True:'6-8',False:'8-10'})
  for (date,band),g in f.groupby(['date','bin']):
   rising=g[g.direction.eq('rising')].sort_values(['strength','symbol']);falling=g[g.direction.eq('falling')].sort_values(['strength','symbol']);available=falling.to_dict('records')
   for r in rising.to_dict('records'):
    if not available:break
    i=min(range(len(available)),key=lambda i:(abs(available[i]['strength']-r['strength']),available[i]['symbol']))
    d=available[i]
    if abs(d['strength']-r['strength'])>.1:continue
    available.pop(i);rows.append(dict(lag=lag,date=date,bin=band,rising=r['symbol'],falling=d['symbol'],strength_difference=r['strength']-d['strength']))
 pairs=pd.DataFrame(rows)
 for side in ['rising','falling']:assert not pairs.duplicated(['lag','date',side]).any()
 assert pairs.strength_difference.abs().max()<=.1
 labels=pd.read_parquet(ROOT/'results/strength-calibration-audit/labeled-scores.parquet')[['date','symbol','horizon','forward_return','tail30']]
 p=pairs.merge(labels.rename(columns={'symbol':'rising','forward_return':'up_return','tail30':'up_tail'}),on=['date','rising'],validate='many_to_many')
 p=p.merge(labels.rename(columns={'symbol':'falling','forward_return':'down_return','tail30':'down_tail'}),on=['date','falling','horizon'],validate='many_to_one')
 assert not p.duplicated(['lag','date','rising','horizon']).any()
 p['difference']=p.up_return-p.down_return;p['tail_difference']=p.up_tail.astype(float)-p.down_tail.astype(float);p['year']=p.date.dt.year;p.to_parquet(out/'score-matched-pairs.parquet',index=False)
 daily=p.groupby(['lag','year','date','bin','horizon']).agg(n=('rising','size'),difference=('difference','mean'),tail_difference=('tail_difference','mean'),strength_difference=('strength_difference','mean')).reset_index();daily=daily[daily.n.ge(5)]
 s=daily.groupby(['lag','year','bin','horizon']).agg(dates=('date','size'),pairs=('n','sum'),mean_difference=('difference','mean'),tail_difference=('tail_difference','mean'),mean_strength_difference=('strength_difference','mean')).reset_index();s.to_csv(out/'score-matched-summary.csv',index=False)
 (out/'matching-validation.json').write_text(json.dumps(dict(pair_rows=len(pairs),mature_pair_horizon_rows=len(p),caliper=.1,no_reuse_within_date_lag=True,pairing_uses_outcomes=False,limitations='Greedynearestmatchingdependsascendingrising-scoreorder;fixedcaliper,minimum5pairsperdate,highscoreonly. Not randomizedcausaleffect orindependentobservations. Secondcheckmotivatedbyinitialscoreimbalance; developmentonly.'),indent=2));print(s.loc[s.horizon.eq(21)].to_string(index=False))
if __name__=='__main__':main()

import json
import pandas as pd
from stock_walkforward_rank import OUT
from stock_entry_robustness import bootstrap_year_means

def main():
 c=pd.read_csv(OUT/'coefficients.csv',parse_dates=['date','max_label_end'])
 if not c.max_label_end.lt(c.date).all():raise AssertionError('training leakage')
 d=pd.read_csv(OUT/'by-date.csv',parse_dates=['date']);rows=[]
 for (period,h),g in d.groupby(['period','horizon']):
  for coverage,part in [('available',g),('complete_dates',g[g.selected.eq(g.labels)])]:
   w=part.pivot(index='date',columns='strategy',values='mean')
   for comparator in ['all','low_atr']:
    p=w[['ridge',comparator]].dropna();v=p.ridge-p[comparator]
    if len(v)==0:continue
    annual=v.groupby(v.index.year).mean()
    rows.append(dict(period=period,horizon=int(h),coverage=coverage,comparator=comparator,dates=len(v),mean=float(v.mean()),without_best5=float(v.sort_values().iloc[:-5].mean()),positive_years=int(annual.gt(0).sum()),years=len(annual),year_bootstrap=bootstrap_year_means(v)))
 report={'first_prediction':str(c.date.min().date()),'last_prediction':str(c.date.max().date()),'all_training_labels_mature':True,'comparisons':rows,'limitations':['No pristine holdout despite chronological fitting; historical research reuse remains','Annual blocks few, overlapping horizon labels may cross blocks; bootstrap descriptive','Complete-date restriction changes dates and can select liquid survivors']}
 (OUT/'audit.json').write_text(json.dumps(report,indent=2));print(pd.DataFrame(rows).query('horizon==21').to_string(index=False))
if __name__=='__main__':main()

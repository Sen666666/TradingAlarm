"""Known-at-entry repeat classifications; not a cooldown counterfactual."""
import json
import pandas as pd
from build_stock_features import ROOT


def main():
 out=ROOT/'results/a-stock-reentry-audit';out.mkdir(exist_ok=True)
 d=pd.read_parquet(ROOT/'results/a-stock-zero-range-stress/campaigns.parquet').sort_values(['symbol','entry_date'])
 g=d.groupby('symbol');d['prior_exit']=g.exit_date.shift();d['prior_R']=g.R_cost15.shift()
 d['gap_calendar_days']=(pd.to_datetime(d.entry_date)-pd.to_datetime(d.prior_exit)).dt.days
 d['entry_kind']='first_in_test';d.loc[d.prior_exit.notna(),'entry_kind']='after_win';d.loc[d.prior_R.lt(0),'entry_kind']='after_loss'
 assert d.loc[d.prior_exit.notna(),'gap_calendar_days'].gt(0).all()
 d['gap_band']=pd.cut(d.gap_calendar_days,[-1,5,20,60,100000],labels=['1-5','6-20','21-60','61+']).astype('object').fillna('first_in_test')
 metadata=d[['symbol','entry_date','entry_kind','gap_band','gap_calendar_days']]
 s=pd.read_parquet(ROOT/'results/a-stock-zero-range-stress/cutoffs/snapshots.parquet').merge(metadata,on=['symbol','entry_date'],validate='many_to_one')
 rows=[]
 for keys,group in s.groupby(['cutoff','entry_kind','gap_band']):
  known=group[group.status.ne('stale_unknown')]
  rows.append(dict(cutoff=keys[0],kind=keys[1],gap_calendar_days=keys[2],count=len(group),unknown=len(group)-len(known),mean_R15=float(known.R_cost15.mean()),mean_R30=float(known.R_cost30.mean()),sum_R15=float(known.R_cost15.sum())))
 metadata.to_parquet(out/'entry-context.parquet',index=False)
 summary=dict(interpretation='Classification uses only prior exited campaign; first means first since2022,not first ever. Cumulative overlapping cutoffs,not independent samples. Dropping rows cannot simulate a cooldown rule because alternate entries change paths.',records=rows)
 (out/'summary.json').write_text(json.dumps(summary,indent=2))
 for r in rows:
  if r['cutoff']==s.cutoff.max():print(r)

if __name__=='__main__':main()

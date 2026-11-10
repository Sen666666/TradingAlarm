"""Separate indicator lock from the independent E0 eligibility requirement."""
from common_m1 import *
import pandas as pd
def main():
 verify();a=pd.read_parquet(HERE/'gate-audit/all-blocked-cold-with-warm-proposal-recent.parquet');a=a.loc[~a.profile.isin(['unknown_long','invalid_observation'])];pieces=[]
 for sid,g in a.groupby('symbol'):
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet',columns=['e0_target','ix_target','IX','fresh_up'])
  f['date']=f.index.strftime('%Y-%m-%d');pieces.append(g.merge(f.reset_index(drop=True),on='date',how='left',validate='one_to_one'))
 b=pd.concat(pieces,ignore_index=True);assert len(b)==110098
 b.to_parquet(HERE/'gate-audit/blocked-with-E0-context.parquet',index=False)
 summary=[]
 for name,flag in [('all_blocked',pd.Series(True,index=b.index)),('slow_blocked',b.profile.eq('slow_up'))]:
  c=b.loc[flag];summary.append(dict(group=name,stock_days=len(c),stocks=c.symbol.nunique(),e0_unknown_days=int(c.e0_target.isna().sum()),e0_also_up_days=int(c.e0_target.eq(1).sum()),positive_close_days=int(c.r.gt(0).sum()),positive_close_and_volume_above_median_days=int((c.r.gt(0)&c.relative_volume.ge(1)).sum()),e0_up_and_positive_close_and_volume_above_median_days=int((c.e0_target.eq(1)&c.r.gt(0)&c.relative_volume.ge(1)).sum()),old_IX_entry_events=int(c.IX.sum())))
 write(HERE/'gate-audit/E0-context-summary.json',summary);print(summary,flush=True)
if __name__=='__main__':main()

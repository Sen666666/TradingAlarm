from common_m1 import *
from model_m1 import describe
import pandas as pd

def main():
 verify();out=HERE/'gate-audit';out.mkdir(exist_ok=False)
 pool=sorted(x['security_id'] for x in read(OLD/'inputs-v2/selection.json')['lines'] if (x.get('company_cap_cny') or 0)>1e10);assert len(pool)==1709
 rows=[];stocks=[]
 for n,sid in enumerate(pool):
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet');m=describe(f)
  flag=f.promotion_blocked.fillna(False).astype(bool)&f.proposal.ge(2)&f.grade.le(-2)
  positive=m.r.gt(0);activity=f.volume/f.volume.shift().rolling(21).median()
  for scope,start in [('full','2015-01-01'),('recent','2023-01-01')]:
   valid=(f.index>=pd.Timestamp(start))&m.full_ready
   b=flag&valid;slow=b&m.profile.eq('slow_up')
   stocks.append(dict(symbol=sid,scope=scope,observations=int(valid.sum()),blocked_warm_proposal_cold=int(b.sum()),slow_blocked=int(slow.sum()),slow_blocked_positive_close=int((slow&positive).sum()),slow_blocked_positive_close_above_median_volume=int((slow&positive&activity.ge(1)).sum())))
  a=f.loc[flag&f.index.to_series().ge('2023-01-01'),['grade','proposal','promotion_blocked','phase','close','volume']].copy()
  a=a.join(m[['profile','r','mu21','mu63','mu126','short_score','long_score']]);a['relative_volume']=activity.reindex(a.index);a['symbol']=sid;a['date']=a.index.strftime('%Y-%m-%d');rows.append(a.reset_index(drop=True))
  if (n+1)%500==0:print(dict(stocks=n+1),flush=True)
 pd.concat(rows,ignore_index=True).to_parquet(out/'all-blocked-cold-with-warm-proposal-recent.parquet',index=False)
 df=pd.DataFrame(stocks);df.to_csv(out/'stock-summary.csv',index=False);summary=[]
 for scope,a in df.groupby('scope'):
  summary.append(dict(scope=scope,stocks=len(a),stocks_with_blocked=int(a.blocked_warm_proposal_cold.gt(0).sum()),**{c:int(a[c].sum()) for c in a.select_dtypes('number').columns}))
 write(out/'summary.json',summary);write(out/'receipt.json',dict(recorded_at=now(),passed=True,stocks=1709,diagnostic_after_M1_figures=True,algorithm_revisions=0,new_future_labels=0,new_accounts=0))
 print(summary,flush=True)
if __name__=='__main__':main()

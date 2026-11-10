"""Descriptive diagnostics of the frozen accounts; never defines trading rules."""
from pathlib import Path
import sys,json,gzip,collections
import pandas as pd
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE/'code'))
from util_ix import *

def main():
 out=HERE/'post/metrics';out.mkdir(exist_ok=False)
 s=pd.read_csv(HERE/'analysis/summary.csv');old=pd.DataFrame(read(OLD/'analysis-v2/summary.json'));old['entry_scheme']='E0';old['allocation']=old.account.str.split('_').str[0];old['scenario']=old.account.str.split('_').str[1];old.account='E0__'+old.account
 a=pd.concat([old,s],ignore_index=True);a.to_csv(out/'comparison.csv',index=False)
 c=pd.read_csv(HERE/'analysis/campaigns.csv');original=pd.read_csv(OLD/'analysis-v2/campaigns.csv');original.account='E0__'+original.account;c=pd.concat([original,c],ignore_index=True)
 profiles=pd.read_csv(HERE/'analysis/entry-profiles.csv');op=pd.read_csv(OLD/'entry-profiles/profiles.csv').rename(columns={'e0_age_observations':'e0_age','close_to_support_fraction':'support_distance'});op.account='E0__'+op.account;profiles=pd.concat([op,profiles],ignore_index=True)
 p=[]
 for aid,f in c.groupby('account'):
  if not aid.endswith('_base'):continue
  mode,alloc=aid.split('__');alloc=alloc.split('_')[0];closed=f.loc[f.closed];ordinary=closed.loc[~closed.tail_closed];pf=profiles.loc[profiles.account.eq(aid)]
  p.append(dict(account=aid,entry_scheme=mode,allocation=alloc,cycles=len(f),closed=len(closed),tail_closed=int(closed.tail_closed.sum()),ordinary_closed=len(ordinary),ordinary_pnl=float(ordinary.net_pnl.sum()),ordinary_investment=float((ordinary.buy_gross+ordinary.buy_fees).sum()),ordinary_pnl_to_investment=float(ordinary.net_pnl.sum()/(ordinary.buy_gross+ordinary.buy_fees).sum()) if len(ordinary) else None,median_entry_e0_age=float(pf.e0_age.median()),p90_entry_e0_age=float(pf.e0_age.quantile(.9)),median_entry_support_distance=float(pf.support_distance.median()),p90_entry_support_distance=float(pf.support_distance.quantile(.9))))
 pd.DataFrame(p).to_csv(out/'entry-quality.csv',index=False);write(out/'entry-quality.json',p)
 daily=[]
 with gzip.open(HERE/'accounts/decisions.jsonl.gz','rt') as f:
  for line in f:
   d=json.loads(line)
   if not d['account'].endswith('_base'):continue
   daily.append(dict(account=d['account'],date=d['at'][:10],events=len(d['event_eligibility']),qualified=len(d['eligible']),selected=len(d['first_selected']),accepted=len(d['accepted']),unknown=d['unknown_eligibility']))
 df=pd.DataFrame(daily);df['year']=df.date.str[:4].astype(int);df.to_csv(out/'daily-opportunities.csv',index=False)
 av=df.groupby('account').agg(mean_events=('events','mean'),mean_qualified=('qualified','mean'),p90_qualified=('qualified',lambda x:x.quantile(.9)),zero_qualified_days=('qualified',lambda x:int(x.eq(0).sum())),mean_accepted=('accepted','mean')).reset_index();av.to_csv(out/'opportunity-summary.csv',index=False)
 cv=pd.read_csv(HERE/'analysis/curves.csv');cv=cv.loc[cv.account.str.endswith('_base')];cv['year']=cv.date.str[:4].astype(int);cv.groupby(['account','year']).exposure.mean().reset_index().to_csv(out/'annual-exposure.csv',index=False)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,posthoc_descriptive_only=True,base_account_daily_decisions=len(df),rules_or_accounts_added=0))
 print(a.query("scenario=='base'")[['entry_scheme','allocation','net_return','max_drawdown','mean_exposure','closed_campaigns','win_rate']].to_string(index=False),flush=True)
 print(pd.DataFrame(p).query("allocation=='S0'").to_string(index=False),flush=True)

if __name__=='__main__':main()

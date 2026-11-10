from pathlib import Path
import json,hashlib,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));from run import score_one
c=pd.read_parquet(O/'SEALED_SCORES.parquet')
s=pd.read_parquet(O/'SELECTED_WITH_LABELS.parquet')
p=pd.read_csv(O/'PAIRED_RESULTS_WITH_LABELS.csv')
aud={}
aud['risk_quantiles_PVR']=c[c.account=='PVR'].risk.quantile([0,.01,.5,.99,1]).to_dict()
aud['Q_quantiles_PVR']=c[c.account=='PVR'].Q.quantile([0,.01,.5,.99,1]).to_dict()
aud['PVR_counts']=dict(total=int(c.account.eq('PVR').sum()),known=int(c[c.account=='PVR'].known.sum()))
aud['unknown_reasons']=dict(invalid_floor=int(((c.floor_num<=0)|(c.floor_num>=c.close)).sum()),missing_beta=int(c.beta.isna().sum()),missing_PVR=int(c.original_PVR.isna().sum()))
aud['all_source_hashes_known']=bool(pd.read_csv(O/'NATIVE_SOURCE_AUDIT.csv').manifest_hash_known.all())
# Independent closed-form vs np.polyfit on fixed case windows, no alternative ranking.
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');sm={r['symbol']:r for r in json.loads(U.read_text())}
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False);dates=pd.DatetimeIndex(h['dates'])
cases=[('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('600606.SH','2022-03-22'),('688582.SH','2024-07-29'),('600056.SH','2022-03-03'),('600056.SH','2022-03-30'),('300666.SZ','2026-01-15'),('301611.SZ','2026-01-15'),('300085.SZ','2024-09-24'),('002583.SZ','2024-09-19')]
checks=[]
for sid,day in cases:
 f=pd.read_parquet(sm[sid]['refs']['facts']).reindex(dates);t=dates.get_loc(day);pp=np.log(f.close.iloc[t-21:t].to_numpy(float));coef=np.polyfit(np.arange(21),pp,1)
 z=score_one(f,dates).loc[day]
 assert np.isclose(coef[0],z.beta,atol=1e-13,rtol=0)
 assert np.isclose(np.polyval(coef,21),z.pred_t,atol=1e-13,rtol=0)
 checks.append(dict(sid=sid,day=day,beta_error=abs(coef[0]-z.beta),pred_error=abs(np.polyval(coef,21)-z.pred_t)))
aud['independent_polyfit_checks']=checks
ss={strategy:set(g.row_id) for strategy,g in s.groupby('strategy')}
f=pd.read_csv(O/'ORIGINAL_FIRST_ROUND_MEMBERSHIP.csv')
ww=[]
for(a,y),g in f[f.first_kind=='add'].groupby(['account','year']):
 closed=g[g.closed];b=closed[closed.selected_PVR];lost=b[~b.selected_STR]
 ww.append(dict(account=a,year=y,baseline_selected_original_closed=len(b),baseline_winners=int(b.round_pnl.gt(0).sum()),lost=len(lost),lost_winners=int(lost.round_pnl.gt(0).sum()),lost_large_round_winners=int(lost.round_return_on_cumulative_cost.ge(.3).sum())))
pd.DataFrame(ww).to_csv(O/'ORIGINAL_MOBILE_WINNER_COST.csv',index=False)
# All final closed rounds remain only descriptive, never labels for new-strategy win rate.
cols=['account','sid','signal_day','entry_day','closed_day','round_pnl','round_return_on_cumulative_cost','selected_PVR','selected_STR']
f[(f.first_kind=='add')&f.closed&f.selected_PVR&~f.selected_STR&f.round_pnl.gt(0)][cols].to_csv(O/'LOST_ORIGINAL_MOBILE_WINNERS.csv',index=False)
cr=[]
for sid,day in cases:
 q=c[(c.sid==sid)&(c.day==day)&c.account.eq('PVR')]
 if len(q):
  r=q.iloc[0];cr.append(dict(sid=sid,day=day,eligible_MOBILE=True,Q=r.Q,beta=r.beta,extension=r.extension,risk=r.risk,selected_PVR=r.name in ss['PVR'],selected_STR=r.name in ss['STR']))
 else:cr.append(dict(sid=sid,day=day,eligible_MOBILE=False))
pd.DataFrame(cr).to_csv(O/'FIXED_CASES.csv',index=False)
# Full-year cost proxies and positive/negative payoff distribution; not actual fee or round results.
rows=[]
for(a,y,st),g in s.groupby(['account','year','strategy']):
 for H in [5,20,60]:
  x=g.loc[g['complete'+str(H)],'ret'+str(H)]
  for cost in [0,.003]:
   z=x-cost;win=z[z>0];loss=z[z<0]
   rows.append(dict(account=a,year=y,strategy=st,horizon=H,cost_proxy=cost,n=len(z),positive_fraction=z.gt(0).mean(),avg_win=win.mean(),avg_loss=loss.mean(),payoff_ratio=win.mean()/abs(loss.mean()),mean=z.mean()))
pd.DataFrame(rows).to_csv(O/'PATH_PAYOFF_AND_COST_PROXY.csv',index=False)
# Date-block sensitivity after dropping single largest absolute date contribution, not changing original ranking.
d=pd.read_csv(O/'COMMON_COMPLETE_DATE_DETAILS.csv');dd=[]
for(a,H),g in d[d.year<=2025].groupby(['account','horizon']):
 i=g['diff'].abs().idxmax();h=g.drop(index=i);dd.append(dict(account=a,horizon=H,removed_day=g.loc[i,'day'],removed_delta=g.loc[i,'diff'],remaining_mean=h['diff'].mean()))
pd.DataFrame(dd).to_csv(O/'LEAVE_LARGEST_DATE_OUT_DIAGNOSTIC.csv',index=False)
aud['policy_frozen_no_parameter_change']=True
aud['paired_known']=int((p.f_known&p.r_known).sum());aud['paired_swaps']=int(p.swap.sum())
aud['paired_floor_role_counts']=p.role.value_counts().to_dict()
aud['no_accounts']=True
(O/'FINAL_QA.json').write_text(json.dumps(aud,ensure_ascii=False,indent=2,default=str))
print('WINNER_COST');print(pd.DataFrame(ww).to_string(index=False));print('FIXED_CASES');print(pd.DataFrame(cr).to_string(index=False));print('QUALITY');print(json.dumps(aud,ensure_ascii=False,default=str))

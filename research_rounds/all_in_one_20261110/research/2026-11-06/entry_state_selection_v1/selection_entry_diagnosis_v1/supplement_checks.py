
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1')
f=pd.read_csv(O/'ALL_FIRST_ENTRIES.csv')
# Native facts are original account source, not canonical5517 inference.
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
manifest={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
for sid,idx in f.groupby('sid').groups.items():
 q=pd.read_parquet(manifest[sid]['refs']['facts'])
 ds=pd.DatetimeIndex(f.loc[idx,'signal_day'])
 for col in ['e0_target','e0_ready','i_target','i_buy','g_grade','g_ready']:
  f.loc[idx,'original_'+col]=q[col].reindex(ds).to_numpy()
 for col in ['close','factor','raw_close','i_floor']:
  f.loc[idx,'original_'+col]=q[col].reindex(ds).to_numpy()
f['quarter']=pd.to_datetime(f.entry_day).dt.to_period('Q').astype(str)
f['PVR_gt85']=f.PVR_decision.gt(85)
f['industry_H1_gt75']=f.industry_H1.gt(75)
f['stock_H1_gt90']=f.stock_H1.gt(90)
for flag,source in [('below_resistance','prior20_resistance'),('above_resistance','prior20_resistance'),('rebound_under_resistance','prior20_resistance'),('stretched_rebound_under_resistance','z5'),('old_H1_carries_positive','ret63')]:
 f[flag]=f[flag].astype('boolean').mask(f[source].isna())
f['industry_both_ret_nonpositive']=f.industry_not_diffusing
f=f.drop(columns=['industry_not_diffusing'])
# Historical membership unknown: this is explicitly the fixed original roster, not PIT.
sel=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/selection.json').read_text())
mapping={r['security_id']:r['sector_id']for r in sel['lines']}
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)
dates=pd.DatetimeIndex(h['dates']);syms=list(h['symbols']);cl=pd.DataFrame(h['close'],index=dates,columns=syms);seg=pd.DataFrame(h['segment'],index=dates,columns=syms)
cl=cl.where(np.isfinite(cl)&cl.gt(0));ma=cl.rolling(20,min_periods=20).mean().where(seg.eq(seg.shift(19)));known=cl.notna()&ma.notna();above=cl.gt(ma)
sb={}
for sector in sorted(set(f.sector)):
 ids=[s for s in syms if mapping.get(s)==sector];k=known[ids];a=above[ids];pair=k&k.shift(5,fill_value=False)
 sb[sector]=pd.DataFrame({'industry_breadth20':(a&k).sum(axis=1)/k.sum(axis=1).replace(0,np.nan),'industry_delta5':((a.astype(int)-a.shift(5,fill_value=False).astype(int))*pair).sum(axis=1)/pair.sum(axis=1).replace(0,np.nan),'industry_known_n':k.sum(axis=1)})
for sector,idx in f.groupby('sector').groups.items():
 ds=pd.DatetimeIndex(f.loc[idx,'signal_day']);q=sb[sector].reindex(ds)
 for col in q:f.loc[idx,col]=q[col].to_numpy()
f['industry_weak_diffusion']=((f.industry_breadth20<.5)&(f.industry_delta5<=0)).astype('boolean').mask(f.industry_breadth20.isna()|f.industry_delta5.isna())
b=pd.read_csv(O/'MARKET_5517_EXISTING_WITH_UNKNOWN_FIXED.csv').set_index('day')
f['broad5517_regime']=f.signal_day.map(b.regime);f['broad5517_B20']=f.signal_day.map(b.breadth20)
f.to_csv(O/'ALL_FIRST_ENTRIES.csv',index=False)
def metric(g,closed2022=False):
 c=g[g.closed_in_entry_year]if closed2022 else g[g.closed]
 r=dict(n=len(g),closed_n=len(c),closed_win_n=int(c.round_pnl.gt(0).sum()),closed_winrate=c.round_pnl.gt(0).mean()if len(c)else np.nan,closed_pnl=c.round_pnl.sum(),big60_n=int(g.big60_posthoc.sum()),complete60_n=int(g.complete60.sum()))
 for n in [1,3,5,10,20]:
  z=g[g['complete'+str(n)]]
  r.update({f'complete{n}_n':len(z),f'mean_ret{n}':z[f'ret{n}_forward'].mean(),f'positive_ret{n}':z[f'ret{n}_forward'].gt(0).mean(),f'mean_close_MFE{n}':z[f'close_MFE{n}'].mean(),f'mean_close_MAE{n}':z[f'close_MAE{n}'].mean()})
 return r
rows=[]
for(a,y),g in f.groupby(['account','year']):
 for dim in ['market_regime','industry_weak_diffusion','broad5517_regime','above_resistance','rebound_under_resistance','old_H1_carries_positive','PVR_gt85','industry_H1_gt75']:
  for v,z in g.groupby(dim,dropna=False):
   rows.append(dict(account=a,year=y,dimension=dim,value=str(v),**metric(z,y==2022)))
 for regime,z in g.groupby('market_regime'):
  for dim in ['PVR_gt85','industry_H1_gt75','stock_H1_gt90','industry_weak_diffusion']:
   for v,w in z.groupby(dim,dropna=False):rows.append(dict(account=a,year=y,dimension=regime+'|'+dim,value=str(v),**metric(w,y==2022)))
pd.DataFrame(rows).to_csv(O/'CORRECTED_STRATIFIED_GROUPS.csv',index=False)
qr=[]
for(a,q),g in f.groupby(['account','quarter']):
 for dim in ['market_regime','PVR_gt85','industry_H1_gt75']:
  for v,z in g.groupby(dim,dropna=False):qr.append(dict(account=a,quarter=q,dimension=dim,value=str(v),**metric(z,q.startswith('2022'))))
pd.DataFrame(qr).to_csv(O/'QUARTER_STRATIFIED.csv',index=False)
diag=[]
for(a,y),g in f.groupby(['account','year']):
 for rule,mask in [('exclude_weak_market',g.weak_market),('exclude_industry_weak_diffusion',g.industry_weak_diffusion),('exclude_rebound_under_resistance',g.rebound_under_resistance),('exclude_old_H1_carry',g.old_H1_carries_positive),('require_above_prior20close',~g.above_resistance),('exclude_PVR_gt85',g.PVR_gt85)]:
  total=int(g.big60_posthoc.sum())
  for side,z in [('removed',g[mask.fillna(False)]),('retained',g[(~mask).fillna(False)]),('unknown',g[mask.isna()])]:
   diag.append(dict(account=a,year=y,rule=rule,side=side,total_big60=total,big60_share=int(z.big60_posthoc.sum())/total if total else np.nan,**metric(z,y==2022)))
pd.DataFrame(diag).to_csv(O/'CORRECTED_SINGLE_RULE_DIAGNOSTICS.csv',index=False)
# The five examples: exact original PVR daily, trades and original E0/I, same dates.
cases=pd.read_csv(O/'FIVE_CASES_ENTRY.csv')
daily=pd.read_csv(O/'FIVE_CASES_DAILY.csv')
pvr=json.load(__import__('gzip').open(O.parent/'account_comparison_continuous_v1/run_1200000/pair/PVR.json.gz','rt'))
for sid,idx in daily.groupby('sid').groups.items():
 ds=pd.DatetimeIndex(daily.loc[idx,'day']);q=pd.read_parquet(manifest[sid]['refs']['facts'])
 sc=pd.read_parquet(Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/scores')/(sid+'.parquet'))
 daily.loc[idx,'original_PVR']=sc.score.reindex(ds).to_numpy()
 for col in ['e0_target','i_target','i_buy','g_grade','raw_close','factor']:
  daily.loc[idx,'original_'+col]=q[col].reindex(ds).to_numpy()
 for j in idx:
  d=daily.at[j,'day'][:10];tr=[t for t in pvr['trades']if t['security_id']==sid and t['at'][:10]==d]
  daily.loc[j,'actual_buy_gross']=sum(float(t['gross_cny'])for t in tr if t['side']=='buy')
  daily.loc[j,'actual_sell_gross']=sum(float(t['gross_cny'])for t in tr if t['side']=='sell')
  daily.loc[j,'actual_sell_reasons']='|'.join(sorted(set(t['reason']for t in tr if t['side']=='sell')))
daily.to_csv(O/'FIVE_CASES_DAILY.csv',index=False)
# Additional no-upside vs round-loss counts avoid treating final loss as immediate entry error.
cc=[]
for(a,y),g in f.groupby(['account','year']):
 c=g[g.closed_in_entry_year]if y==2022 else g[g.closed]
 for n in [5,20]:
  z=c[c['complete'+str(n)]]
  cc.append(dict(account=a,year=y,horizon=n,closed=len(z),losses=int(z.round_pnl.lt(0).sum()),losers_never_positive_close=int((z.round_pnl.lt(0)&z['close_MFE'+str(n)].eq(0)).sum()),losers_MFE_ge10pct=int((z.round_pnl.lt(0)&z['close_MFE'+str(n)].ge(.1)).sum()),losers_MFE_ge20pct=int((z.round_pnl.lt(0)&z['close_MFE'+str(n)].ge(.2)).sum())))
pd.DataFrame(cc).to_csv(O/'LOSERS_FORWARD_UPSIDE.csv',index=False)
print('PVR2022_QUARTERS')
print(pd.DataFrame(qr).query("account=='PVR' and quarter.str.startswith('2022')")[['quarter','dimension','value','n','closed_n','closed_winrate','closed_pnl','mean_ret5','mean_ret20']].to_string(index=False))
print('STRATA');print(pd.DataFrame(rows).query("account=='PVR' and year==2022 and (dimension.str.contains('PVR_gt85') or dimension=='industry_weak_diffusion' or dimension=='broad5517_regime')")[['dimension','value','n','closed_n','closed_winrate','closed_pnl','mean_ret5','mean_ret20']].to_string(index=False))
print('UPSIDE');print(pd.DataFrame(cc).query("account=='PVR' and year==2022").to_string(index=False))
print('BIG_MISS');print(pd.DataFrame(diag).query("account=='PVR' and rule=='exclude_weak_market' and side=='removed'")[['year','n','big60_n','total_big60','big60_share','closed_pnl']].to_string(index=False))
print('NATIVE_COMPARE',f.groupby('account').apply(lambda z:dict(n=len(z),i_target_diff=int(z.original_i_target.ne(z.i_target).sum()),i_buy_diff=int(z.original_i_buy.ne(z.i_buy).sum())),include_groups=False).to_dict())

from pathlib import Path
import importlib.util,sys,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('momentum_analysis',O/'analyze.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
checks=[]
cal=pd.bdate_range('2020-01-01',periods=240)
f=pd.DataFrame(dict(close=np.exp(np.arange(240)*.01),volume=100.,segment_id=0,valid_strength_observation=True),index=cal)
z=A.calc(f,cal);assert z.known.iloc[:66].sum()==0 and z.right.iloc[66:].all();checks.append('First usable mu at return64, right at return66')
fzero=f.copy();fzero.close=100;zz=A.calc(fzero,cal);assert zz.known.iloc[66:].all() and not zz.right.any() and (zz.mu5.dropna()==0).all();checks.append('Exact zero does not satisfy strictly positive')
fg=f.drop(cal[100]);zg=A.calc(fg,cal);assert not zg.known.iloc[100:167].any() and zg.right.iloc[167];assert np.isnan(zg.mu5.iloc[100:165]).all();checks.append('Missing common date resets EMA and 64+3 warm-up; no bridging or forward fill')
fs=f.copy();fs.loc[cal[100]:,'segment_id']=1;zs=A.calc(fs,cal);assert not zs.known.iloc[100:166].any() and zs.right.iloc[166];checks.append('Source identity change restarts warm-up even without missing price')
fi=f.copy();fi.loc[cal[100],'valid_strength_observation']=False;zi=A.calc(fi,cal);pd.testing.assert_frame_equal(zg,zi,check_exact=True);checks.append('Invalid observation identical to absent bar')
fl=f.copy();fl.loc[cal[100],'volume']=0;zl=A.calc(fl,cal);pd.testing.assert_frame_equal(zg,zl,check_exact=True);checks.append('Zero volume is UNKNOWN and reset, not silent price-only bridge')
fd=f.copy();fd.loc[cal[100]:,'close']*=.5;zd=A.calc(fd,cal);assert zd.known.iloc[100] and not zd.right.iloc[100] and zd.mu5.iloc[100]<0;checks.append('Any nonpositive day immediately removes right, no 2-day exit hysteresis')
poison=f.copy();poison.loc[cal[170]:,'close']=1e20;zp=A.calc(poison,cal);pd.testing.assert_frame_equal(zp.iloc[:170],z.iloc[:170],check_exact=True);checks.append('Future poison cannot alter prior mu or status')
k=pd.DataFrame({'a':[True,True,True,True],'b':[True,True,True,False]},index=cal[:4]);r=pd.DataFrame({'a':[True,True,True,True],'b':[False,False,False,False]},index=cal[:4]);bb=A.breadth('test',['a','b'],k,r);assert bb.right_known.iloc[0]==.5 and bb.right_known.iloc[3]==1 and bb.delta3.iloc[3]==0;assert bb.right_fixed_lower.iloc[3]==.5 and bb.right_fixed_upper.iloc[3]==1;checks.append('Unknown member loss raises naive ratio but paired diffusion stays zero and fixed range widens')
A.dump('SYNTHETIC_CHECKS.json',dict(passed=True,checks=checks,tests=len(checks)))
known=pd.read_parquet(O/'KNOWN3.parquet');right=pd.read_parquet(O/'RIGHT3.parquet');mu=pd.read_parquet(O/'MU5.parquet');valid=pd.read_parquet(O/'SOURCE_VALID.parquet');age=pd.read_parquet(O/'WARM_RETURNS.parquet');block=pd.read_parquet(O/'BLOCK.parquet');roster=pd.read_csv(O/'FIXED_ROSTER.csv');stockcols=known.columns.tolist();dateidx=known.index
# Reasons are exhaustive and mutually exclusive; valid but <64 warm, or warm64/65 still awaiting three published mu.
reason=pd.DataFrame({'absent_or_invalid':(~valid).sum(axis=1),'rewarm_or_initial64':(valid&(age<64)).sum(axis=1),'await_three_published_mu':(valid&(age>=64)&~known).sum(axis=1),'known':known.sum(axis=1)},index=dateidx);assert (reason.sum(axis=1)==1709).all();reason.index.name='day';reason.to_csv(O/'UNKNOWN_REASONS_DAILY.csv')
# Fresh onset is definitely observed only if yesterday known and false. First known positive is separate.
onset=right&known.shift(fill_value=False)&~right.shift(fill_value=False);fresh_known=right&~known.shift(fill_value=False)
close=pd.DataFrame({sid:pd.read_parquet(A.IX/(sid+'.parquet'),columns=['close']).close.reindex(dateidx)for sid in stockcols});forward=[];labels=[]
for h in [5,20,60]:
 complete=valid.copy()&(block.eq(block.shift(-h)))
 for j in range(1,h+1):complete &= valid.shift(-j,fill_value=False)
 ret=(close.shift(-h)/close-1).where(complete)
 for year in sorted(dateidx.year.unique()):
  iy=dateidx.year==year
  for group,mask in [('right3',right),('known_not_right3',known&~right),('right3_new_onset',onset)]:
   x=ret.where(mask).loc[iy];v=x.stack().to_numpy();daily=x.mean(axis=1).dropna()
   forward.append(dict(year=int(year),h=h,group=group,signal_rows=int(mask.loc[iy].values.sum()),complete_paths=len(v),incomplete_paths=int(mask.loc[iy].values.sum())-len(v),mean_close_return=float(np.mean(v))if len(v)else None,median_close_return=float(np.median(v))if len(v)else None,positive_price_fraction=float(np.mean(v>0))if len(v)else None,equal_date_mean_return=float(daily.mean()),observed_dates=len(daily)))
 # Stock case paths, all preselected examples retained.
 for sid,day in [('000620.SZ','2022-01-11'),('002911.SZ','2022-07-25'),('000029.SZ','2022-12-01')]:
  ix=dateidx.get_loc(day);end=ix+h
  labels.append(dict(sid=sid,day=day,h=h,right=bool(right.at[day,sid]),mu5=float(mu.at[day,sid]),complete=bool(complete.at[day,sid]),close_to_close_return=ret.at[day,sid],endpoint=str(dateidx[end].date())if end<len(dateidx)else None))
pd.DataFrame(forward).to_csv(O/'FORWARD_PRICE_CONDITIONS.csv',index=False);pd.DataFrame(labels).to_csv(O/'FIXED_2022_PRICE_PATHS.csv',index=False)
# Joined legacy failures for context only; no account execution or relabelling as a signal win rate.
old=pd.read_csv(A.R/'selection_entry_diagnosis_v1/FIVE_CASES_ENTRY.csv');snap=pd.read_csv(O/'FIXED_DATE_ALL_STOCKS.csv');old=old.merge(snap[['sid','day','known','right','mu5']],left_on=['sid','signal_day'],right_on=['sid','day'],how='left');b=pd.read_parquet(O/'SECTOR_DAILY.parquet');b['day']=b.day.dt.strftime('%Y-%m-%d');old=old.merge(b,left_on=['sector','signal_day'],right_on=['sector','day'],how='left',suffixes=('','_breadth'));old[['sid','signal_day','known','right','mu5','round_pnl','round_return_on_cumulative_cost','sector','N','K','n','U','right_known','delta3','sector_stage','sector_action']].to_csv(O/'FIXED_2022_LEGACY_CONTEXT.csv',index=False)
# No hidden gating: all existing fast launch states continue to be reported even when the three-day condition is false.
fast=pd.read_parquet(O/'G_FAST_LAUNCH.parquet');rr=[]
for year in sorted(dateidx.year.unique()):
 q=dateidx.year==year;rr.append(dict(year=int(year),existing_fast_launch_stockdays=int(fast.loc[q].values.sum()),already_right3=int((fast&right).loc[q].values.sum()),known_not_right3=int((fast&known&~right).loc[q].values.sum()),unknown3=int((fast&~known).loc[q].values.sum())))
pd.DataFrame(rr).to_csv(O/'PRESERVED_FAST_LAUNCH_COUNTS.csv',index=False)
A.dump('SUPPLEMENT_SUMMARY.json',dict(synthetic_tests=len(checks),all_passed=True,forward_price_clock='t close to t+h common-session close, all path source-valid and same block; no execution, costs or portfolio; overlapping and correlated',account_runs=0,first_known_right_stockdays=int(fresh_known.values.sum()),verified_new_onset_stockdays=int(onset.values.sum())))
print(pd.DataFrame(labels).to_string(index=False));print(old[['sid','signal_day','right','N','K','n','right_known','delta3','sector_stage']].to_string(index=False));print(pd.DataFrame(rr).to_string(index=False));print('SUPPLEMENT COMPLETE')

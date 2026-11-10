from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
c=pd.read_csv(R/'entry_current_downside_unsaturation_v1/FEATURES_AND_SELECTIONS.csv',dtype={'window':str},low_memory=False)
base=pd.read_csv(R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv',dtype={'window':str},low_memory=False)
full=pd.read_csv(R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',dtype={'window':str},low_memory=False)
cols=['event_id','sid','label','core_net','net_pnl','net_return_on_buy_cash','entry_day','exit_day','entry_price','entry_q','entry_fee','tail30']
p=c.merge(full[cols],on=['event_id','sid'],validate='one_to_one')
p=p.merge(base[['event_id','sid','never_profitable']],on=['event_id','sid'],how='left',validate='one_to_one')
tar=p[p.never_profitable.eq(True)&p.r.gt(0)].copy();assert tar.baseline_selected.all()
pairs=[];cover=[];allrows=set(tar.index)
for _,a in tar.sort_values(['window','core_net','sid']).iterrows():
 winners=p[p.event_id.eq(a.event_id)&p.label.eq('W')&p.core_net.gt(0)].copy()
 exact=winners[winners.I_buy_today.eq(a.I_buy_today)&winners.CP1_today.eq(a.CP1_today)]
 cover.append(dict(window=a.window,day=a.day,event_id=a.event_id,sid=a.sid,all_event_candidates=int(p.event_id.eq(a.event_id).sum()),event_positive_count=len(winners),exact_state_positive_count=len(exact)))
 for scope,g in [('SAME_EVENT',winners),('SAME_EVENT_AND_STATE',exact)]:
  if g.empty:continue
  g=g.assign(PVR_distance=abs(g.PVR_score-a.PVR_score));b=g.sort_values(['PVR_distance','sid']).iloc[0];allrows.add(b.name)
  pairs.append(dict(scope=scope,window=a.window,day=a.day,event_id=a.event_id,industry=a.industry,loss_idx=a.name,win_idx=b.name,loss_sid=a.sid,win_sid=b.sid,PVR_distance=b.PVR_distance))
pairs=pd.DataFrame(pairs);coverage=pd.DataFrame(cover);coverage.to_csv(O/'TARGET_MATCH_COVERAGE.csv',index=False)
sm={r['symbol']:r for r in json.load(open(U/'STOCK_MANIFEST.json'))};im=json.load(open(U/'INDUSTRY_MANIFEST.json'))
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(r['refs']['CP1_input']).index) for r in im])));cal=cal[cal<=pd.Timestamp('2026-06-30')]
hashes={str(f):sha(f) for f in [R/'entry_current_downside_unsaturation_v1/FEATURES_AND_SELECTIONS.csv',R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv',R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',Path(__file__),O/'PROTOCOL.json']+[Path(r['refs']['CP1_input']) for r in im]}
x=p.loc[sorted(allrows)].copy();w0=1/sum(.9**np.arange(21))
metrics=['ret_t','day_body','day_open_gap','range_log','close_location','A_relative21','V_relative21','close_vs_prev20H','close_vs_prev20C','next_open_gap_DIAGNOSTIC_ONLY','next_open_vs_signal_high_DIAGNOSTIC_ONLY','PVR_E_current','PVR_E_history','original_PVR_rank','I_floor_distance']
for col in metrics:x[col]=np.nan
daily=[]
for sid,g in x.groupby('sid'):
 sp=Path(next(z for z in sm[sid]['source_sha256'] if z.endswith('/signal.parquet')));raw=pd.read_parquet(sp).reindex(cal);hashes[str(sp)]=sha(sp)
 valid=raw.observed_bar.eq(True)&raw.price_eligible.eq(True)&~raw.source_invalid.eq(True)&~raw.synthetic_event_bar.eq(True)&raw.raw_close.gt(0)&raw.raw_high.gt(0)&raw.raw_low.gt(0)&raw.raw_open.gt(0)
 ident=raw[['source_kind','source_path','segment_id']];same=ident.eq(ident.shift()).all(axis=1)&raw.adjustment_factor.eq(raw.adjustment_factor.shift());known21=valid.rolling(21,min_periods=21).sum().eq(21)&same.rolling(20,min_periods=20).sum().eq(20)
 H=raw.raw_high.shift().rolling(20,min_periods=20).max();CH=raw.raw_close.shift().rolling(20,min_periods=20).max()
 known22=valid.rolling(22,min_periods=22).sum().eq(22)&same.rolling(21,min_periods=21).sum().eq(21)&raw.raw_volume.gt(0).rolling(22,min_periods=22).sum().eq(22)
 Aref=raw.amount.shift().rolling(21,min_periods=21).median();Vref=raw.raw_volume.shift().rolling(21,min_periods=21).median()
 for ii,r in g.iterrows():
  t=pd.Timestamp(r.day);k=cal.get_loc(t);z=raw.loc[t];pr=raw.iloc[k-1];hknown=bool(known21.at[t]);nextop=r.entry_price/1.0005
  vals=[np.expm1(r.r),np.log(z.raw_close/z.raw_open),np.log(z.raw_open/pr.raw_close),np.log(z.raw_high/z.raw_low),(z.raw_close-z.raw_low)/(z.raw_high-z.raw_low) if z.raw_high>z.raw_low else np.nan,r.amount/r.amount_ref if r.amount_ref>0 else np.nan,z.raw_volume/Vref.at[t] if known22.at[t] and Vref.at[t]>0 else np.nan,np.log(z.raw_close/H.at[t]) if hknown else np.nan,np.log(z.raw_close/CH.at[t]) if hknown else np.nan,np.log(nextop/z.raw_close),np.log(nextop/z.raw_high),w0*r.e,r.E-w0*r.e,r.baseline_rank,np.log(r.known_close_raw/r.close_floor_raw)]
  x.loc[ii,metrics]=vals
  x.at[ii,'raw_signal_open']=z.raw_open;x.at[ii,'raw_signal_high']=z.raw_high;x.at[ii,'raw_signal_low']=z.raw_low;x.at[ii,'raw_signal_close']=z.raw_close;x.at[ii,'raw_next_open_DIAGNOSTIC_ONLY']=nextop;x.at[ii,'prior20_high']=H.at[t] if hknown else np.nan;x.at[ii,'history20_known']=hknown
  for kk in range(max(0,k-10),k+1):
   zz=raw.iloc[kk];daily.append(dict(event_id=r.event_id,sid=sid,name=r['name'],day=cal[kk],raw_open=zz.raw_open,raw_high=zz.raw_high,raw_low=zz.raw_low,raw_close=zz.raw_close,raw_volume=zz.raw_volume,amount=zz.amount,is_signal=kk==k))
x.to_csv(O/'FEATURES_TARGETS_AND_MATCHES.csv',index=False);pd.DataFrame(daily).to_csv(O/'PRE_SIGNAL_DAILY.csv',index=False)
fields=['name','PVR_score','r','s','q','u','b','m','e','E','G_grade','I_buy_today','CP1_today','core_net','net_pnl','net_return_on_buy_cash','entry_day','exit_day','tail30']+metrics
for side,idx in [('loss','loss_idx'),('win','win_idx')]:
 rows=x.loc[pairs[idx]].reset_index(drop=True)
 for col in fields:pairs[side+'_'+col]=rows[col].to_numpy()
for col in metrics:pairs['delta_'+col]=pairs['win_'+col]-pairs['loss_'+col]
pairs.to_csv(O/'PAIRED_FEATURES.csv',index=False)
summ=[]
for key,g in pairs.groupby(['scope','window']):
 for col in metrics:
  d=g[['day','loss_'+col,'win_'+col,'delta_'+col]].dropna()
  date=d.groupby('day')['delta_'+col].mean()
  summ.append(dict(scope=key[0],window=key[1],metric=col,pairs=len(d),dates=d.day.nunique(),loss_median=d['loss_'+col].median(),win_median=d['win_'+col].median(),median_difference=d['delta_'+col].median(),mean_difference=d['delta_'+col].mean(),date_equal_difference=date.mean(),winner_larger_fraction=d['delta_'+col].gt(0).mean()))
pd.DataFrame(summ).to_csv(O/'PAIR_DESCRIPTIVE_SUMMARY.csv',index=False)
co=coverage.groupby('window').agg(targets=('sid','size'),any_winner=('event_positive_count',lambda s:(s>0).sum()),exact_state_winner=('exact_state_positive_count',lambda s:(s>0).sum()),no_winner=('event_positive_count',lambda s:(s==0).sum()));co.to_csv(O/'COVERAGE_SUMMARY.csv')
assert all(sha(p)==h for p,h in hashes.items());save('SOURCE_HASHES.json',hashes)
save('QA.json',dict(targets=len(tar),unique_features=len(x),pairs=len(pairs),source_hashes_unchanged=True,targets_all_positive_signal_return=True,no_formula_proposed=True,no_new_rank=True,no_new_economic_simulation=True,warning='Outcome-conditioned retrospective matches, winners may repeat; descriptive only. Next-open gap excluded from any t-day feature design.'))
print('COVERAGE\n',co.to_string())
s=pd.DataFrame(summ);print('EXACT_STATE\n',s[s.scope.eq('SAME_EVENT_AND_STATE')].to_string(index=False))
fixed=[('2022-07-20','002182.SZ'),('2022-09-28','601021.SH'),('2022-07-28','000997.SZ'),('2022-08-23','000564.SZ'),('2022-12-05','688425.SH'),('2024-12-12','600521.SH'),('2024-12-12','688484.SH'),('2024-10-22','600456.SH'),('2024-10-22','300364.SZ'),('2024-09-05','300699.SZ')]
cc=pairs[pairs.scope.eq('SAME_EVENT_AND_STATE')&pairs.apply(lambda r:(r.day,r.loss_sid) in fixed,axis=1)];cc.to_csv(O/'FIXED_CASE_PAIRS.csv',index=False)
dis=['day','loss_name','win_name','loss_PVR_score','win_PVR_score','loss_core_net','win_core_net']+[s+'_'+k for k in ['ret_t','close_location','A_relative21','close_vs_prev20H','next_open_gap_DIAGNOSTIC_ONLY','PVR_E_current','PVR_E_history'] for s in ['loss','win']]
print('FIXED_CASES\n',cc[dis].to_string(index=False))

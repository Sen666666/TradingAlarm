"""Frozen descriptive information study. No Account/Runner/score fusion imports.

Default invocation prints the schema only. --execute needs the completed pure
export manifest and a separately authorized single bounded run. Outputs never
overwrite an earlier attempt. Future labels cannot alter feature ranks/groups.
"""
from pathlib import Path
from decimal import Decimal
import argparse,hashlib,json,signal,time,sys
import numpy as np
import pandas as pd
from label_clock import build_labels,KEY,HORIZONS

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;ENTRY=ROOT.parent;S=ENTRY/'structural_failure_v1'
CONT=['sign_persistence21_w09','logreturn_std20','close_gap_prior_high20','close_location_in_day_range','return5','return20','positive_effective_observations21_w09','sector_return20','sector_sign_persistence21_w09','relative_return20']
ORIGINAL=['r','scale','amount_ref','u','b','e','E','score']
SIGN=['sign_persistence21_w09','sector_sign_persistence21_w09','sector_return20']
PERIODS=[('FULL_2022_2024','2022_2024','2022-01-01','2024-12-31'),('Y2022','2022_2024','2022-01-01','2022-12-31'),('Y2023','2022_2024','2023-01-01','2023-12-31'),('Y2024','2022_2024','2024-01-01','2024-12-31'),('FROM_924','2022_2024','2024-09-24','2024-12-31'),('AFTER_OCT8','2022_2024','2024-10-09','2024-12-31'),('STRONG','strong','2025-07-01','2026-06-30'),('Y2025_H2','strong','2025-07-01','2025-12-31'),('Y2026_H1','strong','2026-01-01','2026-06-30')]
SRC={};OUT=None
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def save(n,z):
 with (OUT/n).open('x') as f:json.dump(z,f,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v));f.write('\n')
def parquet(n,d):
 p=OUT/n;assert not p.exists();d.to_parquet(p,index=False,compression='zstd')
def canonical(x):return json.dumps([x['sid'],x['role'],x.get('receipt'),pd.Timestamp(x['decision_at']).isoformat(),pd.Timestamp(x['opened']).isoformat()],ensure_ascii=False,separators=(',',':'))
def booln(x):return np.asarray(pd.Series(x).fillna(False),dtype=bool)
def pctbins(frame,values,k,labels):
 known=pd.to_numeric(values,errors='coerce').where(np.isfinite(pd.to_numeric(values,errors='coerce')))
 pct=known.groupby([frame.window,frame.day],sort=False).rank(method='average',pct=True)
 result=pd.Series('UNKNOWN',index=frame.index,dtype=object)
 good=pct.notna();codes=np.ceil(pct[good].to_numpy()*k).clip(1,k).astype(int)-1;result.loc[good]=np.asarray(labels,dtype=object)[codes]
 return result
def make_groups(primary,feature_rows):
 x=primary.merge(feature_rows,on=KEY,how='left',validate='one_to_one',indicator=True);assert x._merge.eq('both').all();x=x.drop(columns='_merge')
 ready=x.original_PVR_ready.astype(bool);known=np.isfinite(x.score.to_numpy(float));assert np.array_equal(ready,known)
 assert np.array_equal(x.loc[ready,'score'].to_numpy(float).view(np.uint64),x.loc[ready,'original_PVR'].to_numpy(float).view(np.uint64))
 x['PVR_quartile']=pctbins(x,x.original_PVR.where(ready),4,['Q1','Q2','Q3','Q4']);axes={};pairs={}
 for f in CONT:
  col='G__'+f;x[col]=pctbins(x,x[f].where(x[f+'_status'].eq('KNOWN')),3,['LOW','MID','HIGH']);axes[f]=col;pairs[f]=('HIGH','LOW')
 for f in SIGN:
  name=f+'__sign';col='G__'+name;known=x[f+'_status'].eq('KNOWN')&np.isfinite(x[f]);x[col]=np.select([booln(known&x[f].lt(0)),booln(known&x[f].eq(0)),booln(known&x[f].gt(0))],['NEG','ZERO','POS'],default='UNKNOWN');axes[name]=col;pairs[name]=('POS','NEG')
 k='breakout_prior_high20';col='G__'+k;known=x[k+'_status'].eq('KNOWN')&x[k].notna();x[col]=np.select([booln(known&x[k].fillna(False).astype(bool)),booln(known&~x[k].fillna(False).astype(bool))],['TRUE','FALSE'],default='UNKNOWN');axes[k]=col;pairs[k]=('TRUE','FALSE')
 name='CLV_half';col='G__'+name;known=x.close_location_in_day_range_status.eq('KNOWN')&np.isfinite(x.close_location_in_day_range);x[col]=np.select([booln(known&x.close_location_in_day_range.ge(.5)),booln(known&x.close_location_in_day_range.lt(.5))],['GE_HALF','LT_HALF'],default='UNKNOWN');axes[name]=col;pairs[name]=('GE_HALF','LT_HALF')
 for name,a,b in [('persistence_sign_x_volatility','G__sign_persistence21_w09__sign','G__logreturn_std20'),('stock_x_sector_persistence_sign','G__sign_persistence21_w09__sign','G__sector_sign_persistence21_w09__sign')]:
  col='G__'+name;x[col]=np.where(x[a].eq('UNKNOWN')|x[b].eq('UNKNOWN'),'UNKNOWN',x[a].astype(str)+'|'+x[b].astype(str));axes[name]=col
 return x,axes,pairs
def views(x):
 yield 'stock_day',x
 for role in ['CORE','mobile']:
  has=x.roles.map(lambda a:role.lower() in a if role=='CORE' else role in a);key=role+'_source_event_key';flag=role+'_event_firstseen_in_PRIMARY';unknown=has&x[key].isna();mask=has&(x[flag].eq(True)|unknown)
  y=x.loc[mask].copy();y['event_role']=role;y['source_event_status']=np.where(y[key].isna(),'UNKNOWN_NOT_DEDUPLICATED','KNOWN_PREFIX_FIRSTSEEN')
  yield role+'_source_event_firstseen',y
def periodmask(x,period):
 _,w,start,end=period;return x.window.eq(w)&x.day.between(start,end)
def economic_inputs():
 actual=[];fixed=[]
 rawfixed=read(ENTRY/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json')
 for win in ['2022_2024','strong']:
  state=read(S/'state_semantics'/f'{win}_ROWS.json');money=read(ENTRY/'dec2022_authorization_v1/account_comparison/results_v1'/f'BASELINE_{win}_LAYERS.json');by={x['layer_in_this_book']:x for x in money};oldkeys={x['key'] for x in money};assert len(state)==len(money)
  fk={canonical(t['original']) for t in rawfixed[win]};assert len(fk&oldkeys)=={'2022_2024':45,'strong':67}[win]
  for x in state:
   m=by[x['layer']];assert canonical(x)==m['key'];assert abs(Decimal(x['net'])-Decimal(m['net']))<Decimal('0.000001')
   actual.append(dict(window=win,day=str(x['decision_at'])[:10],sid=x['sid'],key=m['key'],layer=x['layer'],name=x['name'],role=x['role'],actual_action=m['actual_entry_action'],source_action=x['action'],opened=x['opened'],closed=x['closed'],industry=x['industry'],industry_stage=x['industry_stage'],actual_exit_reasons='|'.join(m['actual_exit_reasons']),held_CLOSE_observations=m['held_close_observations'],posterior_short_hold_le5=m['held_close_observations']<=5,cost=float(x['cost']),net=float(x['net']),net_source=x['net'],cost_source=x['cost'],buy_fee=float(x['buy_fee']),sell_fee=float(x['sell_fee']),planned_reference_risk_pct_NAV=float(x['frozen_plan_reference_risk_pct_decisionNAV']),actual_initial_nominal_risk_pct_NAV=float(x['actual_initial_risk_pct_decisionNAV']),own_terminal_tail_ge30=Decimal(x['net'])/Decimal(x['cost'])>=Decimal('.3'),fixed_current_tail=m['key'] in fk,is_postOct8_303=win=='2022_2024' and str(x['opened'])[:10]>='2024-10-09',economic_scope='Original lifecycle terminal net/cost including cutoff mark/recognized AR; holding<=5 is posterior diagnostic, never feature or eligibility'))
  for i,t in enumerate(rawfixed[win]):
   x=t['original'];k=canonical(x);fixed.append(dict(window=win,day=str(x['decision_at'])[:10],sid=x['sid'],original_fixed_member=i,key=k,original_role=x['role'],original_opened=x['opened'],original_cost_source=x['cost'],original_net_source=x['net'],current_No60_exact_key=k in oldkeys))
 a=pd.DataFrame(actual);f=pd.DataFrame(fixed);assert len(a)==3436 and len(f)==177 and a.is_postOct8_303.sum()==303 and a.loc[a.window.eq('strong'),'own_terminal_tail_ge30'].sum()==123
 return a,f
def forecast_summaries(x,axes,pairs):
 pooled=[];daily_pairs=[];coverage=[];saturation=[]
 for view,y in views(x):
  for period in PERIODS:
   covcols=['window','day','u','score']+[c for c in y if c.startswith(('current_','next_','h5_','h20_','h60_'))];d=y.loc[periodmask(y,period),covcols]
   if d.empty:continue
   for h in HORIZONS:
    tag=f'h{h}_';r=d[tag+'next_OPEN_return'];flags={c:int(d[c].fillna(False).sum()) for c in d if c.startswith((tag,'current_','next_')) and pd.api.types.is_bool_dtype(d[c])};coverage.append(dict(view=view,period=period[0],window=period[1],horizon=h,mother=len(d),primary_known=int(r.notna().sum()),close_known=int(d[tag+'decision_CLOSE_return'].notna().sum()),status_counts=d[tag+'status'].value_counts(dropna=False).to_dict(),flags=flags,halt_status='NOT_RECORDED_UNKNOWN'))
   if view=='stock_day':
    u=d.u.to_numpy(float);known=np.isfinite(u);score=d.score.to_numpy(float);ties=d.loc[np.isfinite(score)].assign(_round=np.round(score[np.isfinite(score)],12)).groupby(['day','_round'],sort=False).size()
    saturation.append(dict(period=period[0],window=period[1],mother=len(d),known_u=int(known.sum()),abs_u_ge099=int((np.abs(u[known])>=.99).sum()),abs_u_exact1=int((np.abs(u[known])==1).sum()),known_score=int(np.isfinite(score).sum()),round12_tied_stockdays=int(ties[ties>1].sum()),round12_tie_groups=int((ties>1).sum())))
  for axis,col in axes.items():
   for h in HORIZONS:
    ret=f'h{h}_next_OPEN_return';d=y[['window','day','sid','PVR_quartile',col,'E','original_PVR',ret]].copy();d['_R']=y[ret];d['_win']=np.where(y[ret].notna(),y[ret].gt(0).astype(float),np.nan);d['_Em']=y.E.where(y[ret].notna());d['_Pm']=y.original_PVR.where(y[ret].notna())
    rawaxis=axis if axis in CONT else axis.removesuffix('__sign') if axis.endswith('__sign') else 'close_location_in_day_range' if axis=='CLV_half' else None
    d['_feature_value']=y[rawaxis].where(y[rawaxis+'_status'].eq('KNOWN')) if rawaxis is not None else np.nan
    if h==60:
     d['_tail']=y.h60_future_tail_ge30.astype('Float64').to_numpy(float,na_value=np.nan);d['_peak']=y.h60_max_CLOSE_from_next_OPEN;d['_trough']=y.h60_min_CLOSE_from_next_OPEN
    for period in PERIODS:
     z=d.loc[periodmask(d,period)]
     if z.empty:continue
     gb=z.groupby(['PVR_quartile',col],observed=True,sort=False,dropna=False)
     st=gb.agg(mother=('sid','size'),label_count=('_R','count'),return_mean=('_R','mean'),return_median=('_R','median'),win_fraction=('_win','mean'),PVR_count=('original_PVR','count'),PVR_mean=('original_PVR','mean'),PVR_median=('original_PVR','median'),E_count=('E','count'),E_mean=('E','mean'),E_median=('E','median'),mature_label_E_mean=('_Em','mean'),mature_label_PVR_mean=('_Pm','mean'))
     st['feature_value_count']=gb['_feature_value'].count();st['feature_value_mean']=gb['_feature_value'].mean();st['feature_value_median']=gb['_feature_value'].median()
     if h==60:
      st['fullpath_tail_evaluation_count']=gb['_tail'].count();st['fullpath_tail_ge30_count']=gb['_tail'].sum(min_count=1);st['fullpath_tail_ge30_fraction']=gb['_tail'].mean();st['fullpath_max_CLOSE_return_median']=gb['_peak'].median();st['fullpath_min_CLOSE_return_median']=gb['_trough'].median()
     st['return_p10']=gb['_R'].quantile(.1);st['PVR_p10']=gb['original_PVR'].quantile(.1);st['PVR_p90']=gb['original_PVR'].quantile(.9);st['E_p10']=gb['E'].quantile(.1);st['E_p90']=gb['E'].quantile(.9);st=st.reset_index().rename(columns={col:'feature_group'});st['view']=view;st['axis']=axis;st['horizon']=h;st['period']=period[0];st['window']=period[1];pooled.append(st)
    if axis not in pairs:continue  # interactions have no extra contrasts
    hi,lo=pairs[axis];z=d.loc[d.PVR_quartile.ne('UNKNOWN')&d[col].isin([hi,lo])];gb=z.groupby(['window','day','PVR_quartile',col],observed=True,sort=False)
    dg=gb.agg(mother=('sid','size'),label_count=('_R','count'),return_median=('_R','median'),return_mean=('_R','mean'),win_fraction=('_win','mean'),E_mean=('_Em','mean'),PVR_mean=('_Pm','mean')).unstack(col)
    if hi not in dg.columns.get_level_values(1) or lo not in dg.columns.get_level_values(1):continue
    r=pd.DataFrame(index=dg.index);r['source_pair_available']=dg['mother'][hi].gt(0)&dg['mother'][lo].gt(0);r['label_pair_available']=dg['label_count'][hi].gt(0)&dg['label_count'][lo].gt(0);r['high_mother']=dg['mother'][hi];r['low_mother']=dg['mother'][lo];r['high_label_count']=dg['label_count'][hi];r['low_label_count']=dg['label_count'][lo]
    for k in ['return_median','return_mean','win_fraction','E_mean','PVR_mean']:r['delta_'+k]=(dg[k][hi]-dg[k][lo]).where(r.label_pair_available)
    r=r.reset_index();r['view']=view;r['axis']=axis;r['horizon']=h;r['high_group']=hi;r['low_group']=lo;daily_pairs.append(r)
 summary=pd.concat(pooled,ignore_index=True);dp=pd.concat(daily_pairs,ignore_index=True);pair_summary=[]
 for period in PERIODS:
  z=dp.loc[periodmask(dp,period)]
  if z.empty:continue
  gb=z.groupby(['view','axis','horizon','PVR_quartile'],observed=True,sort=False);p=gb.agg(stockday_quartile_cells=('day','size'),source_pair_days=('source_pair_available','sum'),label_pair_days=('label_pair_available','sum'),mean_day_equal_median_return_difference=('delta_return_median','mean'),mean_day_equal_mean_return_difference=('delta_return_mean','mean'),mean_day_equal_win_fraction_difference=('delta_win_fraction','mean'),mean_day_equal_E_difference=('delta_E_mean','mean'),mean_day_equal_PVR_difference=('delta_PVR_mean','mean')).reset_index();p['period']=period[0];p['window']=period[1];p['pair_day_coverage']=p.label_pair_days/p.source_pair_days.replace(0,np.nan);pair_summary.append(p)
 return summary,dp,pd.concat(pair_summary,ignore_index=True),coverage,saturation
def economics_tables(actual,fixed,x,labels,features,axes):
 a=actual.merge(x.drop(columns=['roles','original_funding_diagnostic'],errors='ignore'),on=KEY,how='left',validate='many_to_one',indicator=True);assert a._merge.eq('both').all();a=a.drop(columns='_merge')
 # Every original identity remains even when h60 has no complete future path.
 f=fixed.merge(features,on=KEY,how='left',validate='many_to_one').merge(labels,on=KEY,how='left',validate='many_to_one');f=f.merge(x[KEY+['PVR_quartile']+list(axes.values())],on=KEY,how='left',validate='many_to_one');f['in_original_PRIMARY']=f.PVR_quartile.notna();f['PVR_quartile']=f.PVR_quartile.fillna('NOT_IN_PRIMARY')
 assert len(a)==3436 and len(f)==177 and f.current_No60_exact_key.sum()==112
 a['contribution_sign']=np.select([a.net.gt(0),a.net.lt(0)],['positive','negative'],default='zero');a['signal_year']=a.day.str[:4];a['positive_contribution']=a.net.clip(lower=0);a['negative_contribution']=a.net.clip(upper=0);a['tail_contribution']=a.net.where(a.own_terminal_tail_ge30,0)
 reports=[]
 for scope,mask in [('ALL3436',pd.Series(True,index=a.index)),('POST_OCT8_303',a.is_postOct8_303),('POST_OCT8_SHORT_LE5_POSTERIOR',a.is_postOct8_303&a.posterior_short_hold_le5),('STRONG_ORDINARY_SHORT_LE5_POSTERIOR',a.window.eq('strong')&a.posterior_short_hold_le5&~a.own_terminal_tail_ge30),('OWN_TERMINAL_TAIL_GE30',a.own_terminal_tail_ge30),('FIXED_CURRENT45_67',a.fixed_current_tail)]:
  z=a.loc[mask]
  for dimension in ['role','actual_action','signal_year','industry_stage','actual_exit_reasons']:
   q=z.groupby(['window',dimension],sort=False,dropna=False).agg(layers=('layer','size'),cost=('cost','sum'),original_net=('net','sum'),positive_contribution=('positive_contribution','sum'),negative_contribution=('negative_contribution','sum'),own_tail_count=('own_terminal_tail_ge30','sum'),own_tail_contribution=('tail_contribution','sum'),buy_fee=('buy_fee','sum'),sell_fee=('sell_fee','sum'),planned_risk_pct_NAV_mean=('planned_reference_risk_pct_NAV','mean'),h60_mature=('h60_mature','sum'),h60_full_future_path=('h60_entire_future_path_valid','sum')).reset_index().rename(columns={dimension:'group'});q['scope']=scope;q['dimension']=dimension;reports.append(q)
  for axis,col in axes.items():
   q=z.groupby(['window','PVR_quartile',col],sort=False,dropna=False).agg(layers=('layer','size'),cost=('cost','sum'),original_net=('net','sum'),positive_contribution=('positive_contribution','sum'),negative_contribution=('negative_contribution','sum'),own_tail_count=('own_terminal_tail_ge30','sum'),own_tail_contribution=('tail_contribution','sum'),planned_risk_pct_NAV_mean=('planned_reference_risk_pct_NAV','mean'),h60_mature=('h60_mature','sum'),h60_full_future_path=('h60_entire_future_path_valid','sum')).reset_index().rename(columns={col:'group'});q['scope']=scope;q['dimension']=axis;reports.append(q)
 return a,f,pd.concat(reports,ignore_index=True)
def execute(seconds,out_name):
 global OUT
 assert 0<seconds<=120;assert out_name in ['results_v1','results_v2'];OUT=HERE/out_name;assert not OUT.exists();OUT.mkdir();started=time.monotonic();save('RUN_STARTED.json',dict(start_epoch=time.time(),budget_seconds=seconds,no_finance=True,no_score=True,single_authorized_execution=True))
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Bounded analysis budget exceeded')));signal.setitimer(signal.ITIMER_REAL,seconds)
 try:
  for p in [ROOT/'ANALYSIS_FREEZE.json',ROOT/'PRE_EXPORT_INTERVAL_AND_PRICE_DOMAIN.json',ROOT/'PRE_LABEL_CLOCK_AND_WEIGHT_CLARIFICATION.json',ROOT/'PRE_LABEL_MASS_CONCENTRATION_SUPPLEMENT.json',HERE/'ANALYSIS_SCHEMA.json']:read(p)
  mf=read(ROOT/'export/FEATURE_MANIFEST_PRE_LABEL.json');assert mf['status']=='COMPLETE_PURE_FEATURE_EXPORT_BEFORE_ANY_LABEL_OR_PNL' and mf['no_future_labels'] and mf['no_original_PnL_imported']
  for name in ['features.parquet','reference_quotes.parquet']:
   p=ROOT/'export'/name;assert sha(p)==mf['outputs'][name]['sha256'];SRC[str(p.resolve())]=sha(p)
  pm=read(ROOT/'universe_audit/PRIMARY_CANDIDATES_MANIFEST.json');pp=Path(pm['file']);assert sha(pp)==pm['file_sha256'];SRC[str(pp.resolve())]=sha(pp)
  primary=pd.read_json(pp,lines=True,convert_dates=False,precise_float=True);assert len(primary)==133713 and not primary.duplicated(KEY).any()
  feature=pd.read_parquet(ROOT/'export/features.parquet');quotes=pd.read_parquet(ROOT/'export/reference_quotes.parquet');assert len(feature)==len(quotes)==1709*968 and feature[KEY].equals(quotes[KEY]);assert not feature.duplicated(KEY).any()
  actual,fixed=economic_inputs();keys=pd.concat([primary[KEY],actual[KEY],fixed[KEY]],ignore_index=True).drop_duplicates(KEY).reset_index(drop=True)
  fr=feature.set_index(KEY).reindex(pd.MultiIndex.from_frame(keys)).reset_index();x,axes,pairs=make_groups(primary,fr)
  parquet('PRIMARY_FEATURE_GROUPS_PRE_LABEL.parquet',x.drop(columns=['original_funding_diagnostic'],errors='ignore'));print('FEATURE_GROUPS_FROZEN',len(x),round(time.monotonic()-started,2),flush=True)
  label_start=time.time();assert (ROOT/'export/FEATURE_MANIFEST_PRE_LABEL.json').stat().st_mtime<=label_start
  labels,clockchecks=build_labels(feature,quotes,keys,mf['calendars']);parquet('LABELS.parquet',labels);save('LABEL_CLOCK_CHECKS.json',clockchecks)
  x=x.merge(labels,on=KEY,how='left',validate='one_to_one');assert len(x)==133713;print('LABELS_COMPLETE',len(labels),round(time.monotonic()-started,2),flush=True)
  a,f,eg=economics_tables(actual,fixed,x,labels,fr,axes)
  for n,d in [('ALL3436_ORIGINAL_ECONOMIC_ASSOCIATIONS.parquet',a),('FIXED_ORIGINAL83_94_IDENTITIES.parquet',f),('ORIGINAL_ECONOMIC_GROUP_SUMMARIES.parquet',eg)]:parquet(n,d)
  eg.to_csv(OUT/'ORIGINAL_ECONOMIC_GROUP_SUMMARIES.csv',index=False)
  save('ECONOMIC_COHORT_CLOCKS.json',dict(postOct8_303='Original actual opened date>=2024-10-09, not the signal-day AFTER_OCT8 view.',post303_layers=int(a.is_postOct8_303.sum()),post303_signal_dates=a.loc[a.is_postOct8_303,'day'].value_counts().sort_index().to_dict(),post303_short_hold_le5_posterior=int((a.is_postOct8_303&a.posterior_short_hold_le5).sum()),strong_ordinary_short_hold_le5_posterior=int((a.window.eq('strong')&a.posterior_short_hold_le5&~a.own_terminal_tail_ge30).sum()),own_tail_counts=a.groupby('window').own_terminal_tail_ge30.sum().to_dict(),posterior_hold_and_net_not_inputs=True))
  print('CORE_ECONOMICS_SAVED',len(a),len(f),round(time.monotonic()-started,2),flush=True)
  summary,dp,ps,coverage,saturation=forecast_summaries(x,axes,pairs)
  for n,d in [('POOLED_GROUP_SUMMARIES.parquet',summary),('DAILY_PAIRED_CONTRASTS.parquet',dp),('DAY_EQUAL_PAIRED_SUMMARY.parquet',ps)]:parquet(n,d)
  ps.to_csv(OUT/'DAY_EQUAL_PAIRED_SUMMARY.csv',index=False);save('LABEL_AND_MOTHER_COVERAGE.json',coverage);save('SATURATION_AND_ROUND12_TIES.json',saturation)
  save('VALIDATION.json',dict(status='COMPLETE_FROZEN_DESCRIPTIVE_INFORMATION_ANALYSIS',primary_stockdays=len(x),original_layers=len(a),postOct8_layers=int(a.is_postOct8_303.sum()),own_terminal_tail_counts=a.groupby('window').own_terminal_tail_ge30.sum().to_dict(),fixed_original_mother=len(f),fixed_current_matches=int(f.current_No60_exact_key.sum()),horizons=list(HORIZONS),label_keys=len(labels),group_rows=len(summary),daily_pair_rows=len(dp),day_equal_summary_rows=len(ps),new_financial_paths=0,new_score_or_fusion=False,elapsed_seconds=time.monotonic()-started,no_iid_significance=True,year_groups_do_not_retruncate_horizons=True,event_groups_inherit_primary_quantiles=True,interactions_have_no_extra_pairs=True,original_economics_not_new_account_benefit=True,halt_status='NOT_RECORDED_UNKNOWN',label_calculation_started_epoch=label_start))
  print('ANALYSIS_COMPLETE',round(time.monotonic()-started,2),flush=True)
 except BaseException as e:save('STOPPED_PRESERVE_PARTIAL_NO_AUTOMATIC_RETRY.json',dict(error=repr(e),elapsed_seconds=time.monotonic()-started,new_accounts=0));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);SRC[str(Path(__file__).resolve())]=sha(__file__);SRC[str(HERE/'label_clock.py')]=sha(HERE/'label_clock.py');save('SOURCE_SHA256.json',SRC);save('DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--budget-seconds',type=float,default=115);p.add_argument('--out',default='results_v1');a=p.parse_args()
 if a.execute:execute(a.budget_seconds,a.out)
 else:print((HERE/'ANALYSIS_SCHEMA.json').read_text())

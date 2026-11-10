"""One frozen ranking/path evaluation. No accounts, new price labels, or score fits."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
import pandas as pd
from evaluation_core import (PATH_VALUES,TAIL_TARGETS,study_window,future_tail_columns,
                             distribution,list_pair,true_weekends,observed_true_runs,daily_tail_rows)

BASE=Path(__file__).resolve().parent;V3=BASE.parent
LABEL=V3.parent/'industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.parquet'
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
METHODS={'USER_NATIVE_A5_E3':'native_UNION_selected','USER_COMMON_A5_E3':'common_UNION_selected','H1_COMMON_MATCHED_N':'common_H1_selected','D_COMMON_MATCHED_N':'common_D_selected'}
sha={}
def bind(p):
 p=Path(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def save(out,name,f):
 f.to_parquet(out/(name+'.parquet'),index=False);f.to_csv(out/(name+'.csv'),index=False)
def dump(out,name,x):(out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def tags(f,scope):
 f=f.copy();f['study_window']=f.date.map(study_window) if scope=='PRIMARY_FULL' else scope
 f['year']=f.date.str[:4];f['month']=f.date.str[:7];return f

def run_scope(panel,methods,scope,calendar,out):
 out.mkdir(parents=True,exist_ok=True);p=tags(panel,scope).sort_values(['date','sector_id_static']).reset_index(drop=True)
 assert not p.duplicated(['date','sector_id_static']).any()
 for col in methods.values():p[col]=p[col].astype('boolean')
 tails=future_tail_columns(p);assert tails[['date','sector_id_static']].equals(p[['date','sector_id_static']])
 save(out,'FUTURE_TAIL_REFERENCE_EVALUATION_ONLY',tails)
 # Descriptive membership attribution inside the already-fixed union, not another strategy.
 attrib=[]
 union=p.common_UNION_selected.eq(True)
 mode=pd.Series('UNKNOWN',index=p.index,dtype=object)
 mode.loc[p.common_A_selected.eq(True)&p.common_E_selected.eq(False)]='A_ONLY'
 mode.loc[p.common_A_selected.eq(False)&p.common_E_selected.eq(True)]='E_ONLY'
 mode.loc[p.common_A_selected.eq(True)&p.common_E_selected.eq(True)]='BOTH'
 if 'common_channel_label' in p:
  assert p.loc[union,'common_channel_label'].astype(str).equals(mode.loc[union].astype(str))
 for grouping in ['study_window','year','month']:
  for period in sorted(p[grouping].unique()):
   for label in ['A_ONLY','E_ONLY','BOTH']:
    q=p[union & mode.eq(label) & p[grouping].eq(period)];valid=q.label_valid20.eq(True)
    rel=q.loc[valid,'final20_rel_log'].dropna();ab=q.loc[valid,'final20_abs_log'].dropna()
    hit=int(tails.loc[q.index,'REL_MFE20_PRIMARY_tail'].sum())
    daily_rates=q.loc[valid].groupby('date').final20_abs_log.apply(lambda v:v.le(0).mean())
    attrib.append({'grouping':grouping,'period':period,'existing_T_union_membership_group':label,'selected_industry_days':len(q),'signal_days':q.date.nunique(),
     'label20_known':int(valid.sum()),'final20_relative_mean':float(rel.mean()) if len(rel) else np.nan,
     'final20_absolute_nonpositive_count':int(ab.le(0).sum()),'final20_absolute_known_denominator':len(ab),
     'final20_absolute_pooled_nonpositive_rate':float(ab.le(0).mean()) if len(ab) else np.nan,
     'final20_absolute_mean_daily_nonpositive_rate':float(daily_rates.mean()) if len(daily_rates) else np.nan,
     'primary_relMFE20_tail_hits':hit,'scope':'existing_union_T_member_attribution_not_new_model_or_causal_marginal_effect'})
 save(out,'EXISTING_UNION_A_ONLY_E_ONLY_BOTH_ATTRIBUTION',pd.DataFrame(attrib))
 diff=[]
 for date,g in p.groupby('date'):
  n=g.native_UNION_selected.eq(True);c=g.common_UNION_selected.eq(True)
  diff.append({'date':date,'native_N':int(n.sum()),'common_N':int(c.sum()),'both':int((n&c).sum()),'native_only':int((n&~c).sum()),'common_only':int((~n&c).sum()),'C_t_N':int(g.C_t_member.eq(True).sum())})
 save(out,'NATIVE_COMMON_LIST_DIFFERENCES',pd.DataFrame(diff))
 daily=daily_tail_rows(p,methods,tails);daily=tags(daily,scope);save(out,'DAILY_TAIL_COVERAGE_PRECISION',daily)
 selected=[];pathdaily=[];coverage=[]
 for method,col in methods.items():
  z=p[p[col].eq(True)].copy();z['method']=method
  for h in [5,20]:
   for v in [q for q in PATH_VALUES if str(h)+'_' in q]:z.loc[~z[f'label_valid{h}'].eq(True),v]=np.nan
  selected.append(z[['date','sector_id_static','study_window','year','month','method','label_valid5','label_valid20','label_end5','label_end20']+PATH_VALUES])
  for date,g in p.groupby('date',sort=True):
   sm=g[col].eq(True);s=g[sm];r={'date':date,'method':method,'selection_day_known':bool(g[col].notna().any()),'selected':int(sm.sum()),'selection_unknown_industries':int(g[col].isna().sum()),'C_t_N':int(g.C_t_member.eq(True).sum())}
   for h in [5,20]:
    valid=s[f'label_valid{h}'].eq(True)
    r[f'selected_label_known{h}']=int(valid.sum());r[f'selected_label_missing{h}']=int((~valid).sum())
    for tag in ['abs','rel']:
     v=s.loc[valid,f'final{h}_{tag}_log'].dropna();r[f'nonpositive{h}_{tag}_count']=int(v.le(0).sum());r[f'nonpositive{h}_{tag}_rate']=float(v.le(0).mean()) if len(v) else np.nan
   pathdaily.append(r)
   coverage.append({'date':date,'method':method,'industries':len(g),'C_t_N':r['C_t_N'],'selection_day_known':r['selection_day_known'],'selected':r['selected'],'selection_unknown_industries':r['selection_unknown_industries']})
 sd=pd.concat(selected,ignore_index=True);pdaily=tags(pd.DataFrame(pathdaily),scope);cv=tags(pd.DataFrame(coverage),scope)
 save(out,'SELECTED_EXISTING_PRICE_LABELS',sd);save(out,'DAILY_FINAL_NONPOSITIVE_EXPOSURE',pdaily);save(out,'DAILY_METHOD_COVERAGE',cv)
 pathstats=[];tailstats=[];exposure=[]
 for grouping in ['study_window','year','month']:
  for period in sorted(p[grouping].unique()):
   for method in methods:
    z=sd[(sd[grouping]==period)&(sd.method==method)];base={'grouping':grouping,'period':period,'method':method,'selected_industry_days':len(z),'distinct_industries':int(z.sector_id_static.nunique()),'signal_days':int(z.date.nunique())}
    rr=dict(base)
    for value in PATH_VALUES:
     for stat,val in distribution(z[value]).items():rr[value+'_'+stat]=val
    for h in [5,20]:rr[f'selected_label_known{h}']=int(z[f'label_valid{h}'].eq(True).sum());rr[f'selected_label_missing{h}']=int(z[f'label_valid{h}'].ne(True).sum())
    rr['label20_cross_calendar_year']=int((z.label_end20.fillna('').str[:4]!=z.year).sum());pathstats.append(rr)
    dz=pdaily[(pdaily[grouping]==period)&(pdaily.method==method)]
    er=dict(base)
    for h in [5,20]:
     denominator=int(dz[f'selected_label_known{h}'].sum())
     for tag in ['abs','rel']:
      count=int(dz[f'nonpositive{h}_{tag}_count'].sum());er[f'final{h}_{tag}_nonpositive_count']=count;er[f'final{h}_{tag}_known_denominator']=denominator
      er[f'final{h}_{tag}_pooled_exposure_rate']=count/denominator if denominator else np.nan;er[f'final{h}_{tag}_mean_daily_exposure_rate']=float(dz[f'nonpositive{h}_{tag}_rate'].mean())
    exposure.append(er)
    for target in TAIL_TARGETS:
     q=daily[(daily[grouping]==period)&(daily.method==method)&(daily.target==target)];hit=int(q.hits.sum());tailN=int(q.tailN.sum());selN=int(q.selected_label_known.sum())
     tailstats.append(dict(grouping=grouping,period=period,method=method,target=target,days=len(q),tail_empty_days=int(q.tail_empty.sum()),coverage_defined_days=int(q.coverage.notna().sum()),
      total_hits=hit,total_tail=tailN,total_selected_target_label_known=selN,coverage_total_hits_over_total_tail=hit/tailN if tailN else np.nan,
      coverage_mean_daily=float(q.coverage.mean()),precision_total_hits_over_total_selected_label_known=hit/selN if selN else np.nan,precision_mean_daily=float(q.precision.mean())))
 save(out,'PRICE_PATH_DISTRIBUTIONS',pd.DataFrame(pathstats));save(out,'TAIL_COVERAGE_BY_PERIOD',pd.DataFrame(tailstats));save(out,'FINAL_NONPOSITIVE_EXPOSURE_BY_PERIOD',pd.DataFrame(exposure))
 # Actual list snapshots: never use future labels for membership or remake an incomplete quota.
 snapshots={};date_to_window=dict(zip(p.date,p.study_window));decision_dates=sorted(p.date.unique());all_weekends=true_weekends(calendar)
 all_weekends['date']=all_weekends.date.dt.strftime('%Y-%m-%d');weekend_set=set(all_weekends.date)
 transitions=[];weekly_right=[]
 for method,col in methods.items():
  ss={date:(set(g.loc[g[col].eq(True),'sector_id_static']) if g[col].notna().any() else None) for date,g in p.groupby('date')};snapshots[method]=ss
  for win,wg in p[['date','study_window']].drop_duplicates().groupby('study_window',sort=True):
   dates=sorted(wg.date);previous=None;previous_date=None
   for date in dates:
    pair=list_pair(previous,ss[date]);transitions.append(dict(frequency='DAILY',method=method,study_window=win,date=date,previous_date=previous_date,**pair));previous=ss[date];previous_date=date
   trueends=[date for date in dates if date in weekend_set];previous=None;previous_date=None
   for date in trueends:
    pair=list_pair(previous,ss[date]);transitions.append(dict(frequency='TRUE_ISO_WEEK_END',method=method,study_window=win,date=date,previous_date=previous_date,**pair));previous=ss[date];previous_date=date
   last=pd.Timestamp(dates[-1]);iso=last.isocalendar();actual=all_weekends[(all_weekends.ISO_year==iso.year)&(all_weekends.ISO_week==iso.week)]
   if len(actual) and actual.date.iloc[0]>dates[-1]:
    weekly_right.append({'method':method,'study_window':win,'last_administrative_decision_day':dates[-1],'true_weekend':actual.date.iloc[0],
     'status':'ADMINISTRATIVE_WINDOW_END_BEFORE_TRUE_WEEKEND_RIGHT_CENSORED','true_weekend_in_another_study_window':actual.date.iloc[0] in date_to_window})
 tr=pd.DataFrame(transitions);save(out,'DAILY_AND_TRUE_WEEKEND_LIST_TURNOVER',tr);pd.DataFrame(weekly_right).to_csv(out/'ADMINISTRATIVE_LAST_WEEK_RIGHT_CENSORING.csv',index=False)
 turnover=[]
 for (freq,win,method),g in tr.groupby(['frequency','study_window','method']):
  z={'frequency':freq,'study_window':win,'method':method,'snapshot_count':len(g),'pair_known_count':int(g.pair_known.sum()),'pair_unknown_count':int((~g.pair_known).sum()),'entered_total':float(g.entered.sum()),'left_total':float(g.left.sum())}
  for v in ['symmetric_turnover','jaccard']:
   for k,val in distribution(g[v]).items():z[v+'_'+k]=val
  turnover.append(z)
 save(out,'LIST_TURNOVER_BY_WINDOW',pd.DataFrame(turnover))
 # Daily list persistence is clipped at study boundaries; C_t outsiders stay unknown.
 allsp=[];duration=[]
 for method,col in methods.items():
  sp=observed_true_runs(p,col);sp['method']=method;allsp.append(sp)
  for win,g in sp.groupby('study_window'):
   complete=g[g.complete_uncensored];mass=int(complete.length.sum());totalmass=int(g.length.sum())
   expected=int(p.loc[p.study_window.eq(win),col].eq(True).sum());assert totalmass==expected
   z={'study_window':win,'method':method,'observed_runs':len(g),'left_censored':int(g.left_censored.sum()),'right_censored':int(g.right_censored.sum()),'complete_uncensored_runs':len(complete),'all_selected_industry_days':totalmass,'complete_selected_industry_days':mass}
   for k,val in distribution(complete.length).items():z['complete_duration_'+k]=val
   z['complete_duration_max']=int(complete.length.max()) if len(complete) else np.nan
   for h in [1,3,5]:
    short=complete[complete.length.le(h)];z[f'complete_duration_le{h}_count']=len(short);z[f'complete_duration_le{h}_fraction']=len(short)/len(complete) if len(complete) else np.nan
    z[f'duration_le{h}_complete_active_day_fraction']=float(short.length.sum()/mass) if mass else np.nan
   duration.append(z)
 save(out,'DAILY_SELECTED_LIST_RUNS',pd.concat(allsp,ignore_index=True));save(out,'LIST_DURATION_AND_CENSORING_BY_WINDOW',pd.DataFrame(duration))
 # A/E mode handoffs are not union exits; no new score or selection rule.
 switches=[]
 for prefix in ['native','common']:
  a=prefix+'_A_selected';e=prefix+'_E_selected';u=prefix+'_UNION_selected'
  if not all(c in p for c in [a,e,u]):continue
  for (sector,win),g in p.groupby(['sector_id_static','study_window']):
   g=g.sort_values('date');old=None
   for r in g[['date',a,e,u]].to_dict('records'):
    known=not(pd.isna(r[a]) or pd.isna(r[e]));mode=('BOTH' if r[a] and r[e] else 'A_ONLY' if r[a] else 'E_ONLY' if r[e] else 'NONE') if known else 'UNKNOWN'
    if old is not None:switches.append({'date':r['date'],'scope':prefix,'sector_id_static':sector,'study_window':win,'previous_mode':old,'current_mode':mode,'mode_change_union_stays_selected':old in ['BOTH','A_ONLY','E_ONLY'] and mode in ['BOTH','A_ONLY','E_ONLY'] and old!=mode})
    old=mode
 save(out,'AE_MODE_HANDOFFS_NOT_UNION_EXITS',pd.DataFrame(switches))
 summary={'scope':scope,'industry_rows':len(p),'sessions':p.date.nunique(),'methods':methods,'candidate_set_never_uses_future_labels':True,
          'weekly_uses_full_CSI_true_weekends':True,'phase_first_week_unknown':True,'accounts_or_new_labels_or_optimized_parameters':0}
 dump(out,'SUMMARY.json',summary)
 return p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('ranking_file');ap.add_argument('--att-file');args=ap.parse_args();begun=time.monotonic()
 bind(V3/'FROZEN_DESIGN.txt');bind(V3/'ATT_ORIGINAL_BASELINE_ADDENDUM.txt');bind(BASE/'EXECUTION_CONTRACT.txt')
 rank=pd.read_parquet(bind(args.ranking_file));assert len(rank)==97650 and not rank.duplicated(['date','sector_id_static']).any()
 for prefix in ['native','common']:
  assert rank[prefix+'_UNION_selected'].astype('boolean').equals(rank[prefix+'_A_selected'].astype('boolean')|rank[prefix+'_E_selected'].astype('boolean'))
 for _,g in rank.groupby('date'):
  n=int(g.common_UNION_selected.eq(True).sum());assert int(g.common_H1_selected.eq(True).sum())==n==int(g.common_D_selected.eq(True).sum())
 assert rank.loc[~rank.C_t_member.eq(True),list(METHODS.values())[1:]].isna().all().all()
 lab=pd.read_parquet(bind(LABEL));assert len(lab)==97650 and not lab.duplicated(['date','sector_id_static']).any()
 p=rank.merge(lab,on=['date','sector_id_static'],how='left',validate='one_to_one');assert len(p)==97650
 cal=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(bind(MARKET),usecols=['date']).date))
 run_scope(p,METHODS,'PRIMARY_FULL',cal,BASE/'primary');print('PRIMARY_COMPLETE',round(time.monotonic()-begun,2),flush=True)
 # Original ATT is an optional availability-limited supplement; main outputs already saved.
 if args.att_file:
  att=pd.read_parquet(bind(args.att_file));assert not att.duplicated(['date','sector_id_static']).any()
  av=sorted(att.date.unique());assert len(av)==242 and av[0]=='2025-07-01' and av[-1]=='2026-06-30'
  sup=p[p.date.isin(av)].merge(att,on=['date','sector_id_static'],how='left',validate='one_to_one');assert len(sup)==242*90
  if not sup.loc[sup.C_t_member.eq(True),'ATT_known'].eq(True).all():
   dump(BASE,'ATT_SUPPLEMENT_SOURCE_GAP.json',{'status':'Need_ranker_C_ATT_compare_panel; no ATT fill and no main changes','rows':len(sup)})
  else:
   sup['ATT_common_matched_selected']=pd.Series(pd.NA,index=sup.index,dtype='boolean');sup.loc[sup.C_t_member.eq(True),'ATT_common_matched_selected']=False
   for _,g in sup.groupby('date'):
    n=int(g.common_UNION_selected.eq(True).sum());g=g[g.C_t_member.eq(True)].sort_values(['ATT_original','sector_id_static'],ascending=[False,True]);sup.loc[g.head(n).index,'ATT_common_matched_selected']=True
   mm={k:v for k,v in METHODS.items() if k!='USER_NATIVE_A5_E3'};mm['ATT_ORIGINAL_MATCHED_N']='ATT_common_matched_selected'
   run_scope(sup,mm,'ATT_AVAILABLE_2025H2_2026H1',cal,BASE/'att_available')
   dump(BASE/'att_available','ATT_SOURCE_LIMITATION.json',{'dates':['2025-07-01','2026-06-30'],'sessions':242,'not_the_full_main_2025_26H1_359_day_window':True,
    'ATT_amount_source':'old_Oct30_runtime_raw','A_D_amount_source':'Oct22_prepared_signal','cross_source_amount_value_identity_verified':False,
    'no_ATT_gt1_filter':True,'main_candidate_C_unchanged_in_this_all_known_supplement':True})
   print('ATT_AVAILABLE_COMPLETE',round(time.monotonic()-begun,2),flush=True)
 bind(__file__);bind(BASE/'evaluation_core.py');dump(BASE,'SOURCE_SHA256.json',sha);dump(BASE,'RUN_STATUS.json',{'status':'COMPLETED','seconds':time.monotonic()-begun,'new_accounts_or_labels_or_weight_variants':0})
if __name__=='__main__':main()

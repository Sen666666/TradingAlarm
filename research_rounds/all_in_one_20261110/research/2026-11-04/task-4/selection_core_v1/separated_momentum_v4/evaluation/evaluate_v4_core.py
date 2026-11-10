"""Strict frozen v4 signal evaluation. Consume state; never regenerate it or its ranks."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
import pandas as pd
from reuse_v3_helpers import load_frozen_helpers

O=Path(__file__).resolve().parent;V4=O.parent;S=V4.parent
H=load_frozen_helpers()
LABEL=S/'industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.parquet'
V3=S/'continuous_rank_v3/ranking/DAILY_RANKINGS.parquet'
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
METHODS={'V4_UNION':'UNION_selected','H1_MATCH_N4':'main_H1_selected','D_MATCH_N4':'main_D_selected',
         'V3_NATIVE_UNCHANGED':'v3_native_UNION_selected','H1_MATCH_N3_OLD':'v3_H1_sameN3_selected',
         'P_MATURE_EXPLANATORY':'P_mature','T3_EXPLANATORY':'T_selected'}
MAIN=['V4_UNION','H1_MATCH_N4','D_MATCH_N4','V3_NATIVE_UNCHANGED','H1_MATCH_N3_OLD']
sha={}
def bind(p):
 p=Path(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def dump(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(name,f):f.to_parquet(O/(name+'.parquet'),index=False);f.to_csv(O/(name+'.csv'),index=False)
def total(s):return float(s.sum(min_count=1))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('state_file');a=ap.parse_args();begun=time.monotonic()
 bind(V4/'FROZEN_DESIGN.txt');bind(O/'EXECUTION_CONTRACT.txt');bind(V4/'ranking/SCHEMA.json')
 d=pd.read_parquet(bind(a.state_file)).rename(columns={'v3_common_H1_selected':'v3_H1_sameN3_selected'})
 assert len(d)==97650 and not d.duplicated(['date','sector_id_static']).any()
 assert d.groupby('date').size().eq(90).all()
 old=pd.read_parquet(bind(V3));old=old[['date','sector_id_static','A_score','E_score','D_score','H1_cache_same_date_score','native_UNION_selected','common_H1_selected']].rename(columns={c:'old_'+c for c in ['A_score','E_score','D_score','H1_cache_same_date_score','native_UNION_selected','common_H1_selected']})
 d=d.merge(old,on=['date','sector_id_static'],validate='one_to_one');assert len(d)==97650
 assert d.v3_native_UNION_selected.astype('boolean').equals(d.old_native_UNION_selected.astype('boolean'))
 assert d.v3_H1_sameN3_selected.astype('boolean').equals(d.old_common_H1_selected.astype('boolean'))
 # The startup score is frozen v3 E; this checks isolation, not a new score calculation.
 pd.testing.assert_series_equal(d.T_score,d.old_E_score,check_names=False,check_dtype=False,check_exact=True)
 assert d.P_known.eq(np.isfinite(pd.to_numeric(d.P_score,errors='coerce'))).all()
 assert d.T_known.eq(np.isfinite(pd.to_numeric(d.T_score,errors='coerce'))).all()
 for c in set(METHODS.values()):d[c]=d[c].astype('boolean')
 assert d.UNION_selected.equals(d.P_mature|d.T_selected)
 d['computed_day90known']=False;counts=[]
 for date,g in d.groupby('date'):
  known=(len(g)==90 and all(np.isfinite(pd.to_numeric(g[c],errors='coerce')).all() for c in ['P_score','T_score','old_A_score','old_E_score','old_D_score','old_H1_cache_same_date_score']) and g.P_mature.notna().all())
  assert g.main_day90known.eq(known).all(),('day90 producer mismatch',date)
  d.loc[g.index,'computed_day90known']=known
  if known:
   n=int(g.UNION_selected.eq(True).sum());ns=g.N_union_actual.dropna().unique();assert len(ns)==1 and int(ns[0])==n
   assert g.main_H1_selected.notna().all() and g.main_D_selected.notna().all()
   assert int(g.main_H1_selected.eq(True).sum())==n==int(g.main_D_selected.eq(True).sum())
  else:
   n=None;assert g.N_union_actual.isna().all() and g[['main_H1_selected','main_D_selected']].isna().all().all()
  counts.append({'date':date,'main_day90known':known,'N4_actual':n,'N4_true_lower_bound_only':int(g.UNION_selected.eq(True).sum()),'N4_unknown_industries':int(g.UNION_selected.isna().sum()),
   'N3_native_original':int(g.v3_native_UNION_selected.eq(True).sum()),'native_v3_not_requota':True})
 cv=pd.DataFrame(counts);save('DAY90_KNOWN_AND_ACTUAL_N',cv)
 lab=pd.read_parquet(bind(LABEL));d=d.merge(lab,on=['date','sector_id_static'],validate='one_to_one').sort_values(['date','sector_id_static']).reset_index(drop=True)
 d['study_window']=d.date.map(H.study_window);d['year']=d.date.str[:4];d['month']=d.date.str[:7]
 # All90 label oracle is audit knowledge; unknown comparison days never enter evaluation denominators.
 d['oracle_reference_all90']=True;tails=H.future_tail_columns(d,reference_column='oracle_reference_all90');assert tails[['date','sector_id_static']].equals(d[['date','sector_id_static']])
 save('ALL90_FUTURE_TAIL_EVALUATION_ONLY',tails)
 daily=[];selected=[]
 for date,g in d.groupby('date',sort=True):
  complete=bool(g.computed_day90known.iloc[0]);win=H.study_window(date)
  for method,col in METHODS.items():
   src=g[col];sm=src.eq(True);rawN=int(sm.sum());z=g[sm & complete].copy();z['method']=method
   selected.append(z[['date','sector_id_static','study_window','year','month','method','label_valid5','label_valid20']+H.PATH_VALUES])
   for target,val in H.TAIL_TARGETS.items():
    oracle=tails.loc[g.index,target+'_tail'];tailN=int(oracle.sum());hit=int((sm&oracle).sum())
    lk=sm&g.label_valid20.eq(True)&np.isfinite(g[val]);den=int(lk.sum())
    daily.append({'date':date,'study_window':win,'year':date[:4],'month':date[:7],'method':method,'target':target,'comparison_known':complete,
     'source_true_count_lower_bound_only':rawN,'actual_N':rawN if complete else np.nan,'oracle_tailN_all90_audit':tailN,
     'hits':hit if complete else np.nan,'tailN_evaluation':tailN if complete else np.nan,'selected_target_label_known':den if complete else np.nan,
     'tail_empty':tailN==0,'coverage':hit/tailN if complete and tailN else np.nan,'precision':hit/den if complete and den else np.nan})
 dt=pd.DataFrame(daily);save('DAILY_TAIL_COVERAGE_PRECISION_N',dt);sel=pd.concat(selected,ignore_index=True);save('SELECTED_EXISTING_LABELS_MAIN_COMPARABLE_DAYS',sel)
 # Summary periods never change the continuous source states.
 ps=[];ts=[]
 for grouping in ['study_window','year','month']:
  for period in sorted(d[grouping].unique()):
   for method in METHODS:
    z=sel[sel[grouping].eq(period)&sel.method.eq(method)];base={'grouping':grouping,'period':period,'method':method,'selected_industry_days':len(z),'selected_days':z.date.nunique(),
     'main_comparable_days':int(cv[cv.date.str.slice(0,4 if grouping=='year' else 7).eq(period)].main_day90known.sum()) if grouping!='study_window' else int(cv[cv.date.map(H.study_window).eq(period)].main_day90known.sum())}
    rr=dict(base)
    for value in H.PATH_VALUES:
     horizon=20 if '20_' in value else 5
     for stat,val in H.distribution(z.loc[z[f'label_valid{horizon}'].eq(True),value]).items():rr[value+'_'+stat]=val
    for h in [5,20]:
     valid=z[f'label_valid{h}'].eq(True);rr[f'label{h}_known']=int(valid.sum());rr[f'label{h}_missing']=int((~valid).sum())
     for tag in ['abs','rel']:
      vv=z.loc[valid,f'final{h}_{tag}_log'].dropna();rr[f'final{h}_{tag}_nonpositive_count']=int(vv.le(0).sum());rr[f'final{h}_{tag}_pooled_nonpositive_rate']=float(vv.le(0).mean()) if len(vv) else np.nan
      daily_rate=z.loc[valid].groupby('date')[f'final{h}_{tag}_log'].apply(lambda q:q.le(0).mean());rr[f'final{h}_{tag}_mean_daily_nonpositive_rate']=float(daily_rate.mean()) if len(daily_rate) else np.nan
    ps.append(rr)
    for target in H.TAIL_TARGETS:
     q=dt[dt[grouping].eq(period)&dt.method.eq(method)&dt.target.eq(target)];hit=total(q.hits);tailN=total(q.tailN_evaluation);n=total(q.selected_target_label_known)
     ts.append(dict(**base,target=target,comparison_unknown_days=int((~q.comparison_known).sum()),total_hits=hit,total_tail=tailN,total_selected_label_known=n,
      pooled_coverage=hit/tailN if tailN and np.isfinite(tailN) else np.nan,mean_daily_coverage=float(q.coverage.mean()),pooled_precision=hit/n if n and np.isfinite(n) else np.nan,mean_daily_precision=float(q.precision.mean())))
 path=pd.DataFrame(ps);tail=pd.DataFrame(ts);save('PRICE_PATH_AND_EXPOSURE_BY_PERIOD',path);save('TAIL_COVERAGE_BY_PERIOD',tail)
 # Core same-width expectation is an analytic diagnostic, not a new chosen list.
 expected=[]
 for (date,target),g in dt[dt.method.isin(MAIN)].groupby(['date','target']):
  by=g.set_index('method');ok=bool(g.comparison_known.all());n4=by.at['V4_UNION','actual_N'];n3=by.at['V3_NATIVE_UNCHANGED','actual_N'];m=min(n4,n3) if ok else np.nan
  for method,r in by.iterrows():
   valid=ok and np.isfinite(m) and m>0 and np.isfinite(r.actual_N) and r.actual_N>0
   eh=m*r.hits/r.actual_N if valid else np.nan
   expected.append({'date':date,'study_window':H.study_window(date),'year':date[:4],'month':date[:7],'method':method,'target':target,'comparison_known':ok,'original_N':r.actual_N,
    'N4':n4,'N3':n3,'m_min_N4_N3':m,'original_hits':r.hits,'expected_hits_uniform_m':eh,'tailN':r.tailN_evaluation if valid else np.nan,
    'expected_coverage':eh/r.tailN_evaluation if valid and r.tailN_evaluation>0 else np.nan,'actual_subsample_or_new_strategy':False})
 ex=pd.DataFrame(expected);save('EQUAL_WIDTH_EXPECTED_HITS_DAILY_NOT_A_STRATEGY',ex)
 es=[]
 for grouping in ['study_window','year','month']:
  for keys,g in ex.groupby([grouping,'method','target']):
   period,method,target=keys;hit=total(g.expected_hits_uniform_m);den=total(g.tailN)
   es.append({'grouping':grouping,'period':period,'method':method,'target':target,'total_expected_hits':hit,'total_tail':den,'pooled_expected_coverage':hit/den if den and np.isfinite(den) else np.nan,'mean_daily_expected_coverage':float(g.expected_coverage.mean()),'no_actual_random_subsample':True})
 save('EQUAL_WIDTH_EXPECTED_COVERAGE_BY_PERIOD_NOT_A_STRATEGY',pd.DataFrame(es))
 gain=[]
 for grouping in ['study_window','year','month']:
  for period in sorted(d[grouping].unique()):
   for label,user,base in [('V4_MINUS_ITS_H1_N4','V4_UNION','H1_MATCH_N4'),('V3_MINUS_ITS_H1_N3','V3_NATIVE_UNCHANGED','H1_MATCH_N3_OLD')]:
    u=path[path.grouping.eq(grouping)&path.period.eq(period)&path.method.eq(user)].iloc[0];b=path[path.grouping.eq(grouping)&path.period.eq(period)&path.method.eq(base)].iloc[0]
    ut=tail[tail.grouping.eq(grouping)&tail.period.eq(period)&tail.method.eq(user)&tail.target.eq('REL_MFE20_PRIMARY')].iloc[0];bt=tail[tail.grouping.eq(grouping)&tail.period.eq(period)&tail.method.eq(base)&tail.target.eq('REL_MFE20_PRIMARY')].iloc[0]
    assert u.selected_industry_days==b.selected_industry_days
    gain.append({'grouping':grouping,'period':period,'comparison':label,'selected_industry_days_each':u.selected_industry_days,
     'relative_final20_mean_gain':u.final20_rel_log_mean-b.final20_rel_log_mean,'main_tail_pooled_coverage_gain':ut.pooled_coverage-bt.pooled_coverage,
     'main_tail_pooled_precision_gain':ut.pooled_precision-bt.pooled_precision,'absolute_final20_nonpositive_rate_difference':u.final20_abs_pooled_nonpositive_rate-b.final20_abs_pooled_nonpositive_rate})
 save('GAIN_VERSUS_EACH_OWN_MATCHED_H1',pd.DataFrame(gain))
 cal=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(bind(MARKET),usecols=['date']).date));ends=H.true_weekends(cal);ends.date=ends.date.dt.strftime('%Y-%m-%d');endset=set(ends.date)
 tr=[];censor=[]
 for method,col in METHODS.items():
  states=d[['date','sector_id_static','study_window',col,'computed_day90known']].copy();states.loc[~states.computed_day90known,col]=pd.NA
  snap={date:(set(g.loc[g[col].eq(True),'sector_id_static']) if bool(g.computed_day90known.iloc[0]) else None) for date,g in states.groupby('date')}
  for win,g in states[['date','study_window']].drop_duplicates().groupby('study_window'):
   dates=sorted(g.date)
   for frequency,dd in [('DAILY',dates),('TRUE_ISO_WEEK_END',[v for v in dates if v in endset])]:
    prev=None;pd0=None
    for date in dd:tr.append(dict(date=date,study_window=win,method=method,frequency=frequency,previous_date=pd0,**H.list_pair(prev,snap[date])));prev=snap[date];pd0=date
   last=pd.Timestamp(dates[-1]);iso=last.isocalendar();e=ends[(ends.ISO_year==iso.year)&(ends.ISO_week==iso.week)]
   if len(e) and e.date.iloc[0]>dates[-1]:censor.append({'method':method,'study_window':win,'administrative_last_day':dates[-1],'true_weekend':e.date.iloc[0],'right_censored_week':True})
 turns=pd.DataFrame(tr);save('DAILY_AND_TRUE_WEEKEND_TURNOVER',turns);pd.DataFrame(censor).to_csv(O/'ADMINISTRATIVE_LAST_WEEK_CENSORING.csv',index=False)
 summary=[]
 for (win,method,freq),g in turns.groupby(['study_window','method','frequency']):
  z={'study_window':win,'method':method,'frequency':freq,'snapshots':len(g),'known_pairs':int(g.pair_known.sum())}
  for v in ['symmetric_turnover','jaccard']:
   for k,val in H.distribution(g[v]).items():z[v+'_'+k]=val
  summary.append(z)
 save('TURNOVER_BY_WINDOW',pd.DataFrame(summary))
 # Preserve source public states for supplemental duration/attribution/focal reporting.
 d.to_parquet(O/'PUBLIC_STATE_AND_LABEL_PANEL.parquet',index=False)
 bind(__file__);bind(O/'reuse_v3_helpers.py');dump('SOURCE_SHA256.json',sha);dump('CORE_RUN_STATUS.json',{'status':'CORE_COMPLETE','rows':len(d),'main_day90known_days':int(cv.main_day90known.sum()),'main_unknown_days':int((~cv.main_day90known).sum()),'seconds':time.monotonic()-begun,'accounts_or_new_labels_or_new_state_computations':0})
 print('CORE_COMPLETE',round(time.monotonic()-begun,2),flush=True)
 print(path[path.grouping.eq('study_window')&path.method.isin(MAIN)][['period','method','selected_industry_days','final20_rel_log_mean','final20_abs_pooled_nonpositive_rate']].to_string(index=False),flush=True)
if __name__=='__main__':main()

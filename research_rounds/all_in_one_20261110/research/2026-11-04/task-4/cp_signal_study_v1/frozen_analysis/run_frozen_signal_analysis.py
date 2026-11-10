"""Execute the preregistered CP signal study once; no market/account/native imports.

Only saved event, feature and label tables enter. Lambda/families/targets/splits,
threshold boundaries and evaluation definitions are fixed in FROZEN_DESIGN.txt.
"""
from pathlib import Path
import argparse, hashlib, json, time, collections
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
SEED=20261105
NBOOT=200
RIDGE=.01
TARGETS=['mfe20_log','mae20_log','final20_log']
FAMILIES={
 'G1_RS':['sm5','sm20','im5','im20','d5_sm5','d5_sm20','d5_im5','d5_im20'],
 'G2_PRICE':['channel20','ema20_slope5','ema60_slope5','dd20'],
 'G3_AMOUNT':['ln_amount_ratio21','up_frac5','down_frac5','up_amount_frac5','down_amount_frac5'],
}
FAMILIES['ALL17']=sum(list(FAMILIES.values()),[])
PHASES=['DEV','V2024','V2025','V2026H1']
VALIDATION=PHASES[1:]


def hashfile(p):
 return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def finite_json(v):
 if isinstance(v,dict):return {str(k):finite_json(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [finite_json(x) for x in v]
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(float,np.floating)):
  return float(v) if np.isfinite(v) else None
 return v


def dump(path,value):
 Path(path).write_text(json.dumps(finite_json(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def ratio(a,b):return float(a/b) if b else np.nan


def q(a,p):
 a=np.asarray(a,dtype=float)
 return float(np.quantile(a,p,method='linear')) if len(a) else np.nan


def weighted_empirical_quantile(values,weights,p):
 """Stable order, first observed value whose cumulative weight reaches pW."""
 order=np.argsort(values,kind='stable')
 idx=np.searchsorted(np.cumsum(weights[order]),p*np.sum(weights),side='left')
 return float(values[order[min(int(idx),len(order)-1)]])


def fit_equal_stock_ridge(frame,columns):
 """Min weighted MSE + lambda||beta||² in dev-standardized X; free intercept."""
 X=frame[columns].to_numpy(float);Y=frame[TARGETS].to_numpy(float)
 counts=frame.groupby('sid').sid.transform('size').to_numpy(float)
 w=1/counts;W=w.sum()
 mu=np.sum(w[:,None]*X,axis=0)/W
 variance=np.sum(w[:,None]*(X-mu)**2,axis=0)/W
 constant=(np.ptp(X,axis=0)==0)|(variance==0)
 sd=np.sqrt(variance);sd[constant]=0
 divisor=np.where(constant,1.,sd)
 Z=(X-mu)/divisor;Z[:,constant]=0
 ymean=np.sum(w[:,None]*Y,axis=0)/W
 gram=Z.T@(w[:,None]*Z)/W
 cross=Z.T@(w[:,None]*(Y-ymean))/W
 beta=np.linalg.solve(gram+RIDGE*np.eye(len(columns)),cross)
 beta[constant,:]=0
 fitted=Z@beta+ymean
 cutoff=weighted_empirical_quantile(fitted[:,1],w,.20)
 rawbeta=beta/divisor[:,None];rawbeta[constant,:]=0
 rawintercept=ymean-mu@rawbeta
 residual=fitted-Y
 stationarity=(gram+RIDGE*np.eye(len(columns)))@beta-cross
 assert np.max(np.abs(stationarity))<1e-9
 assert not frame.sid.isna().any() and np.all(np.isfinite(fitted))
 assert frame.date.max()<='2023-12-31' and frame.label_end.max()<='2023-12-31'
 return {
  'columns':columns,'lambda':RIDGE,'training_events':len(frame),'training_stocks':int(frame.sid.nunique()),
  'training_signal_min':frame.date.min(),'training_signal_max':frame.date.max(),
  'training_label_end_max':frame.label_end.max(),'weight_definition':'1 / model-specific complete purged DEV event count of same sid',
  'weight_sum':float(W),'weighted_mu':mu,'weighted_population_sd':sd,'constant_feature':constant,
  'standardized_beta':beta,'intercept_at_weighted_mean_X':ymean,'raw_beta':rawbeta,'raw_intercept':rawintercept,
  'weighted_train_mse':np.sum(w[:,None]*residual**2,axis=0)/W,
  'penalty_per_target':RIDGE*np.sum(beta**2,axis=0),
  'normal_equation_max_abs_residual':float(np.max(np.abs(stationarity))),
  'predMAE_cutoff':cutoff,'remove_boundary':'predMAE < cutoff; equality retained',
  'weighted_train_removed_fraction':float(np.sum(w[fitted[:,1]<cutoff])/W),
  'unweighted_train_removed_fraction':float(np.mean(fitted[:,1]<cutoff)),
  'train_prediction_cutoff_tie_events':int(np.sum(fitted[:,1]==cutoff)),
  'training_sid_weight_max_minus_min':float(pd.Series(w).groupby(frame.sid.to_numpy()).sum().max()-pd.Series(w).groupby(frame.sid.to_numpy()).sum().min()),
 }


def predict(frame,model):
 X=frame[model['columns']].to_numpy(float)
 mu=np.asarray(model['weighted_mu']);sd=np.asarray(model['weighted_population_sd'])
 constant=np.asarray(model['constant_feature'],bool)
 Z=(X-mu)/np.where(constant,1.,sd);Z[:,constant]=0
 return Z@np.asarray(model['standardized_beta'])+np.asarray(model['intercept_at_weighted_mean_X'])


def describe(a):
 a=np.asarray(a,float)
 if not len(a):return {k:np.nan for k in ['mean','median','q10','q90','min','max','zero_fraction']}
 return {'mean':float(a.mean()),'median':q(a,.5),'q10':q(a,.1),'q90':q(a,.9),'min':float(a.min()),'max':float(a.max()),'zero_fraction':float(np.mean(a==0))}


def paired_stock_bootstrap(base,kept):
 """Paired event means from stock-cluster multinomial resamples, no refitting."""
 ids=sorted(base.sid.unique());n=len(ids)
 if n==0:return None,[]
 b=base.groupby('sid')[TARGETS].agg(['sum','count']).reindex(ids,fill_value=0)
 k=kept.groupby('sid')[TARGETS].agg(['sum','count']).reindex(ids,fill_value=0)
 bs=np.column_stack([b[(t,'sum')].to_numpy(float) for t in TARGETS]);bc=b[(TARGETS[0],'count')].to_numpy(float)
 ks=np.column_stack([k[(t,'sum')].to_numpy(float) for t in TARGETS]);kc=k[(TARGETS[0],'count')].to_numpy(float)
 rng=np.random.default_rng(SEED)
 multiplicity=rng.multinomial(n,np.full(n,1/n),size=NBOOT)
 denom_b=multiplicity@bc;denom_k=multiplicity@kc
 with np.errstate(invalid='ignore',divide='ignore'):
  delta=(multiplicity@ks)/denom_k[:,None]-(multiplicity@bs)/denom_b[:,None]
 result={};draws=[]
 for j,t in enumerate(TARGETS):
  z=delta[:,j];good=z[np.isfinite(z)]
  result[t]={'cluster_stocks':n,'bootstrap_draws':NBOOT,'valid_draws':len(good),'seed':SEED,
   'observed_mean_delta':float(kept[t].mean()-base[t].mean()) if len(kept) else np.nan,
   'ci_low':q(good,.025),'ci_high':q(good,.975)}
 for b0 in range(NBOOT):draws.append({'draw':b0,'mfe_mean_delta':delta[b0,0],'mae_mean_delta':delta[b0,1],'final_mean_delta':delta[b0,2]})
 return result,draws


def prediction_diagnostics(base,family):
 result=[]
 for t in TARGETS:
  a=base[t].to_numpy(float);p=base[family+'__pred_'+t].to_numpy(float)
  if len(a):
   corr=float(np.corrcoef(a,p)[0,1]) if np.std(a)>0 and np.std(p)>0 else np.nan
   ar=pd.Series(a).rank(method='average').to_numpy();pr=pd.Series(p).rank(method='average').to_numpy()
   spearman=float(np.corrcoef(ar,pr)[0,1]) if np.std(ar)>0 and np.std(pr)>0 else np.nan
   result.append({'target':t,'events':len(a),'stocks':int(base.sid.nunique()),'mse':float(np.mean((p-a)**2)),'rmse':float(np.sqrt(np.mean((p-a)**2))),'mae':float(np.mean(np.abs(p-a))),'pearson':corr,'spearman':spearman,'prediction_mean':float(np.mean(p)),'prediction_min':float(p.min()),'prediction_max':float(p.max()),'physically_out_of_range_fraction':float(np.mean(p<0)) if t==TARGETS[0] else float(np.mean(p>0)) if t==TARGETS[1] else np.nan})
  else:result.append({'target':t,'events':0,'stocks':0})
 if len(base):
  mfe=base[family+'__pred_'+TARGETS[0]].to_numpy();mae=base[family+'__pred_'+TARGETS[1]].to_numpy();final=base[family+'__pred_'+TARGETS[2]].to_numpy()
  joint=float(np.mean((final>mfe)|(final<mae)|(mfe<mae)))
 else:joint=np.nan
 for r in result:r['joint_predicted_label_order_violation_fraction']=joint
 return result


def evaluate(frame,family,identity,tail,do_boot=False):
 """All coverage is against the explicitly named original CP subpopulation."""
 n=len(frame);valid=frame.label_valid.to_numpy(bool)&np.isfinite(frame[TARGETS].to_numpy(float)).all(axis=1)
 # No 2024 outcomes are used in any DEV summary, fit, tail or regime threshold.
 valid&=~frame.phase.eq('DEV').to_numpy()|frame.label_end.fillna('').le('2023-12-31').to_numpy()
 fc=frame[family+'__feature_complete'].to_numpy(bool)
 all_label=frame[valid];base=frame[valid&fc]
 keepmask=base[family+'__pred_'+TARGETS[1]].ge(tail['model_cutoffs'][family]).to_numpy()
 kept=base[keepmask];removed=base[~keepmask];unknown=frame[valid&~fc]
 stats=[];summary=dict(identity)
 summary.update(CP_events=n,CP_stocks=int(frame.sid.nunique()),label_available_events=len(all_label),feature_complete_events=int(fc.sum()),complete_base_events=len(base),complete_base_stocks=int(base.sid.nunique()),retained_events=len(kept),retained_stocks=int(kept.sid.nunique()),removed_events=len(removed),removed_stocks=int(removed.sid.nunique()),feature_unknown_label_available_events=len(unknown),label_unavailable_events=int((~valid).sum()),feature_coverage=ratio(fc.sum(),n),retained_full_CP_coverage=ratio(len(kept),n),conditional_retained_fraction=ratio(len(kept),len(base)),label_coverage=ratio(len(all_label),n),joint_coverage=ratio(len(base),n),crossyear_label_events=int(all_label.label_cross_calendar_year.eq(True).sum()),label_outside_phase_events=int(all_label.label_within_phase.eq(False).sum()))
 for group,g in [('ALL_CP_LABEL_AVAILABLE',all_label),('MODEL_COMPLETE_BASE',base),('RETAINED',kept),('REMOVED',removed),('FEATURE_UNKNOWN_LABEL_AVAILABLE',unknown)]:
  for t in TARGETS:stats.append(dict(identity,group=group,target=t,events=len(g),stocks=int(g.sid.nunique()),**describe(g[t].to_numpy())))
 upbase=base.mfe20_log.ge(tail['MFE90']).sum();upkeep=kept.mfe20_log.ge(tail['MFE90']).sum()
 badbase=base.mae20_log.le(tail['MAE10']).sum();badkeep=kept.mae20_log.le(tail['MAE10']).sum()
 upall=all_label.mfe20_log.ge(tail['MFE90']).sum();badall=all_label.mae20_log.le(tail['MAE10']).sum()
 summary.update(upper_tail_base_events=int(upbase),upper_tail_retained_events=int(upkeep),adverse_tail_base_events=int(badbase),adverse_tail_retained_events=int(badkeep),upper_tail_all_label_events=int(upall),adverse_tail_all_label_events=int(badall),upper_tail_lost_to_feature_unknown=int(upall-upbase),adverse_tail_lost_to_feature_unknown=int(badall-badbase),upper_tail_retention=ratio(upkeep,upbase),adverse_tail_reduction=1-ratio(badkeep,badbase),signal_reduction=1-ratio(len(kept),len(base)),upper_tail_retention_vs_all_label=ratio(upkeep,upall))
 summary['upper_tail_retention_minus_conditional_keep']=summary['upper_tail_retention']-summary['conditional_retained_fraction']
 summary['upper_tail_retention_lift']=ratio(summary['upper_tail_retention'],summary['conditional_retained_fraction'])
 summary['adverse_tail_reduction_beyond_signal_reduction']=summary['adverse_tail_reduction']-summary['signal_reduction']
 for t in TARGETS:
  summary[t+'__mean_delta']=kept[t].mean()-base[t].mean()
  summary[t+'__median_delta']=q(kept[t],.5)-q(base[t],.5)
  summary[t+'__q10_delta']=q(kept[t],.1)-q(base[t],.1)
  summary[t+'__q90_delta']=q(kept[t],.9)-q(base[t],.9)
 draws=[];diag=[]
 if do_boot:
  boots,draws=paired_stock_bootstrap(base,kept)
  if boots:
   for t,z in boots.items():
    summary[t+'__mean_delta_ci_low']=z['ci_low'];summary[t+'__mean_delta_ci_high']=z['ci_high'];summary[t+'__bootstrap_valid_draws']=z['valid_draws']
  draws=[dict(identity,**r) for r in draws]
  diag=[dict(identity,**r) for r in prediction_diagnostics(base,family)]
 return summary,stats,draws,diag


def boolean_pass(value,test):return bool(np.isfinite(value) and test(value))


def gates(summary):
 results=[]
 for family in FAMILIES:
  for phase in VALIDATION:
   main=next(r for r in summary if r['family']==family and r['sample']=='ALL_CP' and r['axis']=='PHASE' and r['level']==phase)
   non=next(r for r in summary if r['family']==family and r['sample']=='NONOVERLAP20' and r['axis']=='PHASE' and r['level']==phase)
   g={'family':family,'phase':phase,
    'main_feature_coverage_80':boolean_pass(main['feature_coverage'],lambda x:x>=.8),
    'main_retained_full_CP_coverage_70':boolean_pass(main['retained_full_CP_coverage'],lambda x:x>=.7),
    'main_mae_q10_delta_001':boolean_pass(main['mae20_log__q10_delta'],lambda x:x>=.01),
    'main_final_median_not_lower':boolean_pass(main['final20_log__median_delta'],lambda x:x>=0),
    'main_upper_tail_retention_not_below_conditional_keep':boolean_pass(main['upper_tail_retention_minus_conditional_keep'],lambda x:x>=0),
    'main_mean_mae_delta_cluster95_lower_gt0':boolean_pass(main.get('mae20_log__mean_delta_ci_low',np.nan),lambda x:x>0),
    'nonoverlap_feature_coverage_80':boolean_pass(non['feature_coverage'],lambda x:x>=.8),
    'nonoverlap_retained_full_CP_coverage_70':boolean_pass(non['retained_full_CP_coverage'],lambda x:x>=.7),
    'nonoverlap_mae_q10_positive':boolean_pass(non['mae20_log__q10_delta'],lambda x:x>0),
    'nonoverlap_mean_mae_positive':boolean_pass(non['mae20_log__mean_delta'],lambda x:x>0),
    'nonoverlap_final_median_not_lower':boolean_pass(non['final20_log__median_delta'],lambda x:x>=0),
    'nonoverlap_upper_tail_retention_not_below_conditional_keep':boolean_pass(non['upper_tail_retention_minus_conditional_keep'],lambda x:x>=0)}
   g['phase_pass']=all(v for k,v in g.items() if k not in ['family','phase'])
   results.append(g)
 overall={f:all(r['phase_pass'] for r in results if r['family']==f) for f in FAMILIES}
 return {'phase_gates':results,'all_three_validation_phases_pass':overall,'any_family_passed':any(overall.values()),'nonoverlap_CI_is_reported_not_an_additional_gate':True}


def main(args):
 started=time.monotonic()
 guard=OUT/'RUN_ONCE_GUARD.json'
 with guard.open('x') as fp:json.dump({'started_utc':pd.Timestamp.now(tz='UTC').isoformat(),'status':'STARTED','fit_executions_requested':1},fp)
 design=ROOT/'FROZEN_DESIGN.txt'
 inputs={'design':str(design),'features':str(Path(args.features).resolve()),'labels':str(Path(args.labels).resolve()),'events':str(ROOT/'universe_audit/CP_EVENT_INDEX_2022_2026H1.csv')}
 hashes={k:hashfile(p) for k,p in inputs.items()}
 (OUT/'FROZEN_DESIGN_USED.txt').write_text(design.read_text())
 F=pd.read_parquet(inputs['features']);L=pd.read_parquet(inputs['labels'])
 E=pd.read_csv(inputs['events'],usecols=['sid','date','canonical_receipt_id','canonical_receipt_status','sector_static','industry_static','segment'])
 for name,d in [('features',F),('labels',L),('events',E)]:
  assert len(d)==99031 and not d.duplicated(['sid','date']).any(),(name,len(d))
  d['date']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d')
 assert set(zip(F.sid,F.date))==set(zip(E.sid,E.date))==set(zip(L.sid,L.date))
 assert set(FAMILIES['ALL17']).issubset(F.columns) and 'market20_log' in F
 neededL=['sid','date','label_valid','label_status','label_end','phase','dev_fit_eligible','nonoverlap20','label_within_phase','label_cross_calendar_year']+TARGETS
 D=E.merge(L[neededL],on=['sid','date'],validate='one_to_one').merge(F[['sid','date']+FAMILIES['ALL17']+['market20_log']],on=['sid','date'],validate='one_to_one').sort_values(['date','sid']).reset_index(drop=True)
 D['label_end']=pd.to_datetime(D.label_end).dt.strftime('%Y-%m-%d')
 for b in ['label_valid','dev_fit_eligible','nonoverlap20']:
  assert D[b].notna().all() and D[b].isin([True,False]).all(),b
 assert set(D.phase).issubset(PHASES)
 labelgood=D.label_valid.to_numpy(bool)&np.isfinite(D[TARGETS].to_numpy(float)).all(axis=1)
 dev=D.phase.eq('DEV').to_numpy()&labelgood&D.label_end.fillna('').le('2023-12-31').to_numpy()
 assert np.array_equal(dev,D.dev_fit_eligible.to_numpy(bool))
 assert (D.loc[labelgood,'mfe20_log']>=0).all() and (D.loc[labelgood,'mae20_log']<=0).all()
 assert (D.loc[labelgood,'final20_log']<=D.loc[labelgood,'mfe20_log']+1e-14).all() and (D.loc[labelgood,'final20_log']>=D.loc[labelgood,'mae20_log']-1e-14).all()
 td=D.loc[dev]
 tails={'MFE90':q(td.mfe20_log,.9),'MAE10':q(td.mae20_log,.1),'global_purged_development_label_events':len(td),'tail_quantile':'numpy linear unweighted; all valid purged DEV labels independent of feature availability','MFE_tail_boundary':'>=','MAE_tail_boundary':'<=','dev_MFE_tail_actual_event_fraction':float(td.mfe20_log.ge(q(td.mfe20_log,.9)).mean()),'dev_MAE_tail_actual_event_fraction':float(td.mae20_log.le(q(td.mae20_log,.1)).mean()),'dev_MFE_threshold_ties':int(td.mfe20_log.eq(q(td.mfe20_log,.9)).sum()),'dev_MAE_threshold_ties':int(td.mae20_log.eq(q(td.mae20_log,.1)).sum()),'model_cutoffs':{}}
 market=td.loc[np.isfinite(td.market20_log),'market20_log'].to_numpy(float)
 regime=[q(market,1/3),q(market,2/3)]
 models={};coef=[]
 for family,columns in FAMILIES.items():
  complete=np.isfinite(D[columns].to_numpy(float)).all(axis=1);D[family+'__feature_complete']=complete
  train=D.loc[dev&complete]
  assert len(train)>len(columns)+1
  model=fit_equal_stock_ridge(train,columns);models[family]=model;tails['model_cutoffs'][family]=model['predMAE_cutoff']
  P=np.full((len(D),3),np.nan);P[complete]=predict(D.loc[complete],model)
  for j,t in enumerate(TARGETS):D[family+'__pred_'+t]=P[:,j]
  D[family+'__kept_by_predMAE']=pd.Series(pd.NA,index=D.index,dtype='boolean');D.loc[complete,family+'__kept_by_predMAE']=P[complete,1]>=model['predMAE_cutoff']
  for j,t in enumerate(TARGETS):
   for k,col in enumerate(columns):coef.append({'family':family,'target':t,'feature':col,'weighted_dev_mean':model['weighted_mu'][k],'weighted_dev_population_sd':model['weighted_population_sd'][k],'constant':model['constant_feature'][k],'standardized_beta':model['standardized_beta'][k,j],'raw_beta':model['raw_beta'][k,j],'intercept_at_weighted_mean_X':model['intercept_at_weighted_mean_X'][j],'raw_intercept':model['raw_intercept'][j]})
 frozen={'models':models,'tails':tails,'market20_dev_terciles':{'q1':regime[0],'q2':regime[1],'events':len(market),'weight':'unweighted CP events with all valid unpurged DEV labels and finite market20; independent of model feature coverage','boundaries':'LOW <= q1; MIDDLE q1 < value <= q2; HIGH > q2; UNKNOWN missing'},'input_paths':inputs,'input_SHA256':hashes,'targets':TARGETS,'families':FAMILIES,'seed':SEED,'bootstrap_draws':NBOOT,'account_runs':0,'numeric_CP_or_indicator_models_recomputed':0,'fitted_model_families':4,'ridge_output_predictors':12,'development_purged_crossboundary_events':int((D.phase.eq('DEV')&D.label_valid&~pd.Series(dev,index=D.index)).sum()),'freeze_written_before_validation_metrics':True}
 dump(OUT/'FROZEN_FITS_AND_CUTOFFS.json',frozen);pd.DataFrame(coef).to_csv(OUT/'COEFFICIENTS.csv',index=False)
 print('FROZEN_FIT_SAVED',{'events':len(D),'dev_fit_global':int(dev.sum()),'model_train_events':{k:m['training_events'] for k,m in models.items()}},flush=True)
 D['market_regime']=np.select([~np.isfinite(D.market20_log),D.market20_log.le(regime[0]),D.market20_log.le(regime[1])],['UNKNOWN','LOW','MIDDLE'],default='HIGH')
 summary=[];distributions=[];draws=[];diagnostics=[]
 def run_group(g,family,sample,axis,level,phase,boot=False):
  identity={'family':family,'sample':sample,'axis':axis,'level':str(level),'phase':phase}
  s,st,dr,di=evaluate(g,family,identity,tails,boot);summary.append(s);distributions.extend(st);draws.extend(dr);diagnostics.extend(di)
  if sample=='ALL_CP' and axis=='PHASE' and phase in VALIDATION:
   keys=['feature_coverage','retained_full_CP_coverage','conditional_retained_fraction','mae20_log__q10_delta','final20_log__median_delta','upper_tail_retention','upper_tail_retention_minus_conditional_keep','mae20_log__mean_delta_ci_low','mae20_log__mean_delta_ci_high']
   print('PRIMARY_PHASE',json.dumps(finite_json(dict(family=family,phase=phase,**{k:s.get(k) for k in keys}))),flush=True)
 for family in FAMILIES:
  for phase in PHASES:
   ph=D[D.phase.eq(phase)]
   for sample,g in [('ALL_CP',ph),('NONOVERLAP20',ph[ph.nonoverlap20]),('WITHIN_PHASE',ph[ph.label_valid&ph.label_within_phase.eq(True)])]:run_group(g,family,sample,'PHASE',phase,phase,True)
   for month,g in ph.groupby(ph.date.str[:7],sort=True):run_group(g,family,'ALL_CP','MONTH',month,phase)
   for rg,g in ph.groupby('market_regime',sort=True):run_group(g,family,'ALL_CP','MARKET20_DEV_TERCILE',rg,phase)
   for sector,g in ph.groupby('sector_static',dropna=False,sort=True):run_group(g,family,'ALL_CP','STATIC_INDUSTRY',sector,phase)
  run_group(D[D.date.between('2024-09-24','2024-10-31')],family,'ALL_CP','FIXED_SEGMENT','RALLY_924_20240924_20241031','V2024')
  run_group(D[D.phase.eq('V2026H1')&D.sector_static.eq('URFI881121')],family,'ALL_CP','FIXED_SEGMENT','STATIC_SEMICONDUCTOR_2026H1','V2026H1')
  print('EVALUATED',family,'seconds',round(time.monotonic()-started,2),flush=True)
 S=pd.DataFrame(summary);ST=pd.DataFrame(distributions);DR=pd.DataFrame(draws);DI=pd.DataFrame(diagnostics)
 S.to_csv(OUT/'COVERAGE_TAILS_AND_DISTRIBUTION_DIFFERENCES.csv',index=False);ST.to_csv(OUT/'PATH_DISTRIBUTIONS.csv',index=False);DR.to_csv(OUT/'STOCK_CLUSTER_BOOTSTRAP_DRAWS.csv',index=False);DI.to_csv(OUT/'PREDICTION_DIAGNOSTICS.csv',index=False)
 result=gates(summary);dump(OUT/'PREREGISTERED_DECISION.json',result);pd.DataFrame(result['phase_gates']).to_csv(OUT/'PREREGISTERED_PHASE_GATES.csv',index=False)
 selected=['sid','date','canonical_receipt_id','canonical_receipt_status','sector_static','industry_static','segment','phase','label_end','label_valid','label_status','label_within_phase','label_cross_calendar_year','dev_fit_eligible','nonoverlap20']+TARGETS+['market20_log','market_regime']+[col for col in D if '__' in col]
 D[selected].to_parquet(OUT/'EVENT_PREDICTIONS.parquet',index=False)
 D[selected].to_csv(OUT/'EVENT_PREDICTIONS.csv',index=False)
 D.groupby(['phase','label_status'],dropna=False).agg(events=('sid','size'),stocks=('sid','nunique')).to_csv(OUT/'LABEL_MATURITY_AND_CENSOR_BY_PHASE.csv')
 pd.DataFrame([dict(family=f,phase=p,**{k:v for k,v in next(z for z in summary if z['family']==f and z['sample']=='ALL_CP' and z['axis']=='PHASE' and z['phase']==p).items() if k not in ['family','phase']}) for f in FAMILIES for p in VALIDATION]).to_csv(OUT/'PRIMARY_VALIDATION_SUMMARY.csv',index=False)
 assert hashes=={k:hashfile(p) for k,p in inputs.items()},'Frozen input modified while fitting/evaluating'
 metadata={'status':'COMPLETE','events':len(D),'development_label_events_after_purge':int(dev.sum()),'development_crossboundary_purged':frozen['development_purged_crossboundary_events'],'families':list(FAMILIES),'ridge_output_predictors':12,'lambda':RIDGE,'model_refits_after_dev':0,'candidate_rules_tested':1,'bootstrap_seed':SEED,'bootstrap_draws_per_phase_sample_family':NBOOT,'cluster_bootstrap_only_mean_differences':True,'common_date_dependence_not_removed':True,'event_weighted_primary_evaluation':True,'predictions_clipped':False,'static_pool_conditioning':True,'historical_sector_PIT_verified':False,'account_runs':0,'new_strategy_runs':0,'any_family_passed_all_frozen_gates':result['any_family_passed'],'seconds':time.monotonic()-started,'input_SHA256':hashes}
 dump(OUT/'RUN_SUMMARY.json',metadata)
 create_readout(metadata,models,tails,S,result)
 dump(guard,{'started_utc':json.loads(guard.read_text())['started_utc'],'completed_utc':pd.Timestamp.now(tz='UTC').isoformat(),'status':'COMPLETE','fit_executions_requested':1})
 dump(OUT/'OUTPUT_SHA256.json',{str(p):hashfile(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['OUTPUT_SHA256.json','run.log']})
 print('COMPLETE',json.dumps(finite_json(metadata),ensure_ascii=False),flush=True)


def create_readout(meta,models,tails,S,result):
 lines=['冻结原CP信号级评估：完整4族×3输出结果，非账户/交易结果。',
 '2026静态池条件母体；当前行业映射PIT未证。2024/2026此前已研究，仅时间留出复核。',
 '所有系数/标准化/MAE切点只用2022—23、实际label_end不晚于2023-12-31开发集。验证不重fit、不选新窗/方向/阈值，不clip线性预测。',
 '开发fit每股总权重相等；主评价是未加权原CP事件。标签MFE/MAE/FINAL为后20有效股票观察的收盘自然log价格路径，不是可实现回报。',
 f"全母体{meta['events']}，purged开发标签{meta['development_label_events_after_purge']}，跨开发边界purge {meta['development_crossboundary_purged']}。",
 f"全purged开发标签一次固定尾阈：MFE90={tails['MFE90']:.12g}，MAE10={tails['MAE10']:.12g}；含等号、保留ties。",'']
 for family,model in models.items():
  lines.append(f"{family}: train {model['training_events']}事件/{model['training_stocks']}股；predMAE20%加权经验切点 {model['predMAE_cutoff']:.12g}；低于才去除，等于保留。")
  for p in VALIDATION:
   r=S[(S.family==family)&(S['sample']=='ALL_CP')&(S.axis=='PHASE')&(S.level==p)].iloc[0]
   lines.append(f"  {p}: feature/fullCP={r.feature_coverage:.4%}, kept/fullCP={r.retained_full_CP_coverage:.4%}, conditionalKeep={r.conditional_retained_fraction:.4%}; MAE q10差={r.mae20_log__q10_delta:.6f}, FINAL中位差={r.final20_log__median_delta:.6f}, 上尾保留−条件保留={r.upper_tail_retention_minus_conditional_keep:.6f}; meanMAE差95%股票CI=[{r.mae20_log__mean_delta_ci_low:.6f},{r.mae20_log__mean_delta_ci_high:.6f}]。")
  lines.append('  全三验证期所有预注册门：'+str(result['all_three_validation_phases_pass'][family]))
 lines+=['', '结论仅依照PREREGISTERED_DECISION.json全部原子门；无因失败追加候选或更换参数。',
 '非重叠：原全母体按每股最早完整标签CP贪心，随后date>前次label_end才选；直接消费独立标签线程已存nonoverlap20。固定模型/标准化/切点完全复用，非重叠CI照报且不另加硬门。',
 'within-phase只选label_valid且label_within_phase子母体，作为固定敏感性，不加新coverage门。',
 '环境三分位来自purged开发完整标签事件的market20_log未加权linear分位，按事件计数；不是对验证重新分位。',
 '95%区间为固定seed20261105、200次股票multinomial cluster重采样；同一draw内比较kept与同完整母体均值。没有重新拟合，也没有消除共同日期市场冲击，不称独立市场时段显著性。',
 '主要覆盖分母：features/fullCP、kept且特征标签完整/fullCP。路径和尾部比较均用同模型特征+标签完整母体；另列未知特征丢失的母体与尾部，不暗算为弱信号。',
 '未确认真实停牌/限价/T+1可卖/排队/流动性、费用、账户或资金可行性；没有账户收益或新CP权限。',
 '文件：FROZEN_FITS_AND_CUTOFFS.json、COEFFICIENTS.csv、PRIMARY_VALIDATION_SUMMARY.csv、COVERAGE_TAILS_AND_DISTRIBUTION_DIFFERENCES.csv、PATH_DISTRIBUTIONS.csv、PREDICTION_DIAGNOSTICS.csv、EVENT_PREDICTIONS.parquet/csv、STOCK_CLUSTER_BOOTSTRAP_DRAWS.csv、PREREGISTERED_PHASE_GATES.csv、PREREGISTERED_DECISION.json、RUN_SUMMARY.json。']
 (OUT/'READOUT.txt').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--features',default=str(ROOT/'feature_contract/FEATURES.parquet'));ap.add_argument('--labels',default=str(ROOT/'labels/LABELS.parquet'));args=ap.parse_args();main(args)

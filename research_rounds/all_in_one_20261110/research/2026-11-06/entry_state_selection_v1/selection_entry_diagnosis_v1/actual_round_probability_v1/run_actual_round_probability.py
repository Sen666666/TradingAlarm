"""One actual-filled-round probability diagnostic. No account execution; no five-day target."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,gzip,math,time
O=Path(__file__).resolve().parent;P=O.parent;B=P.parent
SRC=P/'ALL_FIRST_ENTRIES.csv';ACCOUNT=B/'account_comparison_continuous_v1/run_1200000/pair/PVR.json.gz';CLOCK=P/'entry_probability_signal_v1/MARKET_CLOCK.csv'
COLS=['PVR_decision','protected_distance_over_prior_sigma','sigma20_prior','market_breadth20','market_delta5','mobile_first','original_i_buy_numeric']
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
start=time.monotonic();freeze=read(O/'FREEZE.json')
assert sha(O/'FREEZE.json')=='70ff2166e42d348d8c0beb12dcb32ce512bf36422bd3b6daeae9b9e8e5279b6f'
assert sha(SRC)==freeze['source_sha256'];assert not (O/'SUMMARY.json').exists()
sources={str(p):sha(p) for p in [SRC,ACCOUNT,CLOCK,O/'FREEZE.json',Path(__file__)]};dump('SOURCE_FREEZE.json',sources)
f=pd.read_csv(SRC);f=f[f.account.eq('PVR')].copy().reset_index(drop=True);assert len(f)==2693
days=pd.read_csv(CLOCK,index_col=0,parse_dates=True).index
f['t']=days.get_indexer(pd.to_datetime(f.signal_day));assert f.t.ge(0).all()
f['close_t']=days.get_indexer(pd.to_datetime(f.closed_day));assert f.loc[f.closed,'close_t'].ge(0).all()
f['entry_t']=days.get_indexer(pd.to_datetime(f.entry_day))
assert f.loc[f.closed,'close_t'].ge(f.loc[f.closed,'entry_t']).all()
f['y']=np.where(f.closed,f.round_pnl.gt(0).astype(float),np.nan)
valid=(f.original_close>f.first_role_floor)&f.first_role_floor.gt(0)&f.sigma20_prior.gt(0)
f['protected_distance_over_prior_sigma']=(np.log(f.original_close/f.first_role_floor)/f.sigma20_prior).where(valid)
f['mobile_first']=f.first_kind.eq('add').astype(float);f['original_i_buy_numeric']=f.original_i_buy.astype(float)
f['features_known']=np.isfinite(f[COLS]).all(axis=1)
account=json.load(gzip.open(ACCOUNT,'rt'));ds=account['decisions'];restart=[r['at'][:10] for i,r in enumerate(ds) if r['on'] and (i==0 or not ds[i-1]['on'])]
f['context']=np.where(f.signal_day.eq(ds[0]['at'][:10]),'INITIAL',np.where(f.signal_day.isin(restart[1:]),'ACT_RESUME','NORMAL'))
f['holding_sessions']=(f.close_t-f.entry_t+1).where(f.closed)
for c in ['probability','historical_mean','all_mature_mean','quintile','model_cut_t']:f[c]=np.nan
def sigmoid(z):return 1/(1+np.exp(-np.clip(z,-35,35)))
def fit(train):
 x=train[COLS].to_numpy(float);y=train.y.to_numpy(float);mu=x.mean(0);sd=x.std(0);sd=np.where(sd>1e-12,sd,1.)
 X=np.column_stack([np.ones(len(x)),np.clip((x-mu)/sd,-5,5)]);b=np.zeros(X.shape[1]);b[0]=np.log((y.sum()+.5)/(len(y)-y.sum()+.5));pen=np.r_[0.,np.repeat(4.,len(COLS))]
 def obj(b):
  z=X@b
  return np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(pen*b*b)
 for it in range(100):
  p=sigmoid(X@b);g=X.T@(p-y)+pen*b;H=X.T@((p*(1-p))[:,None]*X)+np.diag(pen)+np.eye(len(b))*1e-10
  step=np.linalg.solve(H,g);old=obj(b);scale=1.
  while scale>1e-8 and obj(b-scale*step)>old+1e-9:scale*=.5
  b-=scale*step
  if np.max(np.abs(scale*step))<1e-9:break
 assert np.max(np.abs(X.T@(sigmoid(X@b)-y)+pen*b))<1e-5
 return mu,sd,b,it+1
def predict(g,m):
 mu,sd,b,_=m;X=np.column_stack([np.ones(len(g)),np.clip((g[COLS].to_numpy()-mu)/sd,-5,5)])
 return sigmoid(X@b)
models=[];delay=[];poisons=[]
for month in sorted({str(d.to_period('M')) for d in days if d.year>=2023}):
 dt=next(d for d in days if str(d.to_period('M'))==month);cut=days.get_loc(dt)
 prior=f[f.t.lt(cut)&f.t.ge(cut-504)]
 mature=prior[prior.closed&prior.close_t.lt(cut)]
 pending=prior[~(prior.closed&prior.close_t.lt(cut))]
 train=mature[mature.features_known];test=f[f.signal_day.str.startswith(month)&f.features_known]
 ok=len(train)>=300 and train.y.sum()>=50 and train.y.eq(0).sum()>=50 and train.signal_day.nunique()>=60
 rec=dict(month=month,cutoff=str(dt.date()),window_first_day=str(days[max(0,cut-504)].date()),all_prior_rows=len(prior),mature_rows=len(mature),pending_rows=len(pending),feature_complete_train=len(train),train_wins=int(train.y.sum()),train_dates=train.signal_day.nunique(),test_feature_complete=len(test),known=bool(ok),baseline_mean=train.y.mean(),all_mature_mean=mature.y.mean(),max_closed_day=mature.closed_day.max() if len(mature) else None)
 # Eventual labels below are DESCRIPTIVE AFTER FIT AUDIT ONLY, never passed to fit or prediction.
 delay.append(dict(month=month,mature_n=len(mature),mature_winrate=mature.y.mean(),pending_at_cutoff_n=len(pending),pending_eventually_closed_by_source=int(pending.closed.sum()),pending_eventual_observed_winrate=pending.loc[pending.closed,'y'].mean(),pending_still_open_at_source=int((~pending.closed).sum()),mature_median_holding=mature.holding_sessions.median()))
 if ok:
  m=fit(train);tp=predict(train,m);edges=np.quantile(tp,[.2,.4,.6,.8]);pp=predict(test,m)
  f.loc[test.index,'probability']=pp;f.loc[test.index,'historical_mean']=train.y.mean();f.loc[test.index,'all_mature_mean']=mature.y.mean();f.loc[test.index,'quintile']=np.searchsorted(edges,pp,side='right')+1;f.loc[test.index,'model_cut_t']=cut
  rec.update(intercept=m[2][0],coefficients=dict(zip(COLS,m[2][1:])),means=dict(zip(COLS,m[0])),scales=dict(zip(COLS,m[1])),quintile_edges=edges.tolist(),iterations=m[3])
  if month in ['2023-01','2024-01','2025-01','2026-01']:
   z=f.copy();z.loc[~(z.closed&z.close_t.lt(cut)),'y']=1-z.loc[~(z.closed&z.close_t.lt(cut)),'y'].fillna(0)
   tr=z[z.t.lt(cut)&z.t.ge(cut-504)&z.closed&z.close_t.lt(cut)&z.features_known];mm=fit(tr)
   assert np.array_equal(mm[2],m[2]);poisons.append(dict(month=month,unavailable_label_poison_exact=True))
 models.append(rec)
assert f.loc[f.signal_day.lt('2023-01-01'),'probability'].isna().all()
f['prediction_known']=f.probability.notna()
f.to_csv(O/'ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv',index=False)
dump('MONTHLY_MODELS.json',models);pd.DataFrame(delay).to_csv(O/'TRAINING_LABEL_DELAY_AUDIT.csv',index=False);dump('FUTURE_UNAVAILABLE_LABEL_POISON.json',poisons)
def auc(g,col,target='y'):
 z=g[[col,target]].dropna();y=z[target].astype(bool);a=int(y.sum());b=len(y)-a
 return float((z[col].rank(method='average')[y].sum()-a*(a+1)/2)/(a*b)) if a and b else np.nan
def cluster(g,values):
 z=g[['sid','t']].copy();v=np.asarray(values,float);n=len(v);mu=v.mean();z['u']=(v-mu)/n;z['block']=z.t//20
 def cv(keys):
  sums=z.groupby(keys).u.sum();k=len(sums)
  return (k/(k-1)*np.square(sums).sum() if k>1 else np.nan),k
 vb,nb=cv('block');vs,ns=cv('sid');vi,ni=cv(['block','sid']);v2=vb+vs-vi
 se=math.sqrt(max(0.,vb,vs,v2)) if n else np.nan
 return dict(n=n,mean=mu,blocks=nb,stocks=ns,block_se=math.sqrt(max(0.,vb)),stock_se=math.sqrt(max(0.,vs)),two_way_variance=v2,conservative_se=se,approx95_low=mu-1.96*se,approx95_high=mu+1.96*se)
def auc_jackknife(g):
 base=auc(g,'probability')
 valsb=[auc(g[g.t.floordiv(20).ne(b)],'probability') for b in sorted(g.t.floordiv(20).unique())]
 valss=[auc(g[g.sid.ne(s)],'probability') for s in g.sid.unique()]
 def se(v):
  v=np.asarray([x for x in v if np.isfinite(x)]);G=len(v)
  return math.sqrt((G-1)/G*np.square(v-v.mean()).sum()) if G>1 else np.nan
 sb,ss=se(valsb),se(valss);s=max(sb,ss)
 return dict(auc=base,block_jackknife_se=sb,stock_jackknife_se=ss,approx95_low=base-1.96*s,approx95_high=base+1.96*s)
scores=[];aucs=[];cal=[];groups=[];coverage=[]
pred=f[f.signal_day.ge('2023-01-01')].copy()
def outcomes(g):
 z=g[g.closed];w=z[z.y.eq(1)];l=z[z.y.eq(0)]
 rw=w.round_return_on_cumulative_cost.mean();rl=l.round_return_on_cumulative_cost.mean()
 return dict(n=len(g),scored=int(g.prediction_known.sum()),closed=len(z),still_open=int((~g.closed).sum()),wins=int(z.y.sum()),winrate=z.y.mean(),all_births_win_lower=float(z.y.sum()/len(g)) if len(g) else np.nan,all_births_win_upper=float((z.y.sum()+(~g.closed).sum())/len(g)) if len(g) else np.nan,mean_prediction=g.probability.mean(),mean_round_return=z.round_return_on_cumulative_cost.mean(),mean_win_return=rw,mean_loss_return=rl,return_payoff_ratio=float(rw/abs(rl)) if np.isfinite(rl) and rl<0 else np.nan,cny_payoff_ratio=float(w.round_pnl.mean()/abs(l.round_pnl.mean())) if len(l) and l.round_pnl.mean()<0 else np.nan,original_path_net=z.round_pnl.sum(),original_profit_factor=float(w.round_pnl.sum()/abs(l.round_pnl.sum())) if len(l) and l.round_pnl.sum()<0 else np.nan,median_holding_sessions=z.holding_sessions.median())
for scope in ['2023_2025']+[str(y) for y in sorted(pred.year.unique())]:
 g=pred[pred.year.between(2023,2025)] if scope=='2023_2025' else pred[pred.year.eq(int(scope))]
 for context,gg in [('ALL',g),('NORMAL',g[g.context.eq('NORMAL')])]:
  coverage.append(dict(scope=scope,context=context,**outcomes(gg)))
  z=gg[gg.prediction_known&gg.closed].copy()
  if not len(z):continue
  aucs.append(dict(scope=scope,context=context,known_closed=len(z),baseline_auc=auc(z,'historical_mean'),same_date_eligible_dates=sum(np.isfinite(auc(a,'probability')) for _,a in z.groupby('signal_day')),mean_same_date_auc=np.nanmean([auc(a,'probability') for _,a in z.groupby('signal_day')]),**auc_jackknife(z)))
  for metric in ['brier','logloss']:
   p=np.clip(z.probability,1e-12,1-1e-12);b=np.clip(z.historical_mean,1e-12,1-1e-12)
   loss=(p-z.y)**2 if metric=='brier' else -z.y*np.log(p)-(1-z.y)*np.log(1-p)
   base=(b-z.y)**2 if metric=='brier' else -z.y*np.log(b)-(1-z.y)*np.log(1-b)
   scores.append(dict(scope=scope,context=context,metric=metric,model_mean=loss.mean(),baseline_mean=base.mean(),**cluster(z,loss-base)))
  for q in range(1,6):
   qq=gg[gg.prediction_known&gg.quintile.eq(q)]
   row=dict(scope=scope,context=context,group='Q'+str(q),**outcomes(qq))
   if qq.closed.any():row.update({'winrate_'+k:v for k,v in cluster(qq[qq.closed],qq.loc[qq.closed,'y']).items() if k not in ['n','mean']})
   groups.append(row)
  zz=gg[gg.prediction_known]
  for band,a in zz.groupby(pd.cut(zz.probability,[0,.1,.2,.3,.4,.5,1],include_lowest=True),observed=True):
   cal.append(dict(scope=scope,context=context,bin=str(band),**outcomes(a)))
pd.DataFrame(scores).to_csv(O/'PAIRED_PROPER_SCORE_CLUSTER_RESULTS.csv',index=False)
pd.DataFrame(aucs).to_csv(O/'AUC_CLUSTER_DIAGNOSTIC.csv',index=False)
pd.DataFrame(groups).to_csv(O/'CAUSAL_TRAIN_QUINTILE_OUTCOMES.csv',index=False)
pd.DataFrame(cal).to_csv(O/'FIXED_PROBABILITY_BIN_CALIBRATION.csv',index=False)
pd.DataFrame(coverage).to_csv(O/'COHORT_COVERAGE_AND_CENSORING.csv',index=False)
# Separate year-end closure from eventual complete-to-source labels; never silently mix denominators.
endyear=[]
for (year,context),g in pred.groupby(['year','context']):
 for clock,z in [('complete_by_source',g[g.closed]),('closed_in_entry_year',g[g.closed_in_entry_year])]:
  endyear.append(dict(year=year,context=context,completion_clock=clock,**outcomes(z)))
pd.DataFrame(endyear).to_csv(O/'CLOSURE_CLOCK_OUTCOMES.csv',index=False)
summary=dict(status='ACTUAL_PVR_FILLED_ROUND_FORWARD_PROBABILITY_DIAGNOSTIC_NOT_NEW_POLICY',account_runs=0,model_specifications=1,parameter_searches=0,first_year_predictions=0,earliest_prediction=f.loc[f.prediction_known,'signal_day'].min(),latest_prediction=f.loc[f.prediction_known,'signal_day'].max(),monthly_fits=len(models),fit_months_known=sum(x['known'] for x in models),original_rounds=len(f),eligible_2023_onward=len(pred),known_predictions=int(pred.prediction_known.sum()),known_closed_labels=int((pred.prediction_known&pred.closed).sum()),still_open_predicted=int((pred.prediction_known&~pred.closed).sum()),ACT_context_signal_dates=restart,poison_checks=len(poisons),frozen_source_sha256=freeze['source_sha256'],freeze_sha256=sha(O/'FREEZE.json'),seconds=time.monotonic()-start,limitations=freeze['history_limits'],label_delay_limitation=freeze['label_delay_warning'])
dump('SUMMARY.json',summary);dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('SUMMARY',json.dumps(clean(summary)),flush=True)
print('AUC',pd.DataFrame(aucs).query("context=='ALL'").to_string(index=False),flush=True)
print('SCORES',pd.DataFrame(scores).query("context=='ALL'").to_string(index=False),flush=True)
print('QUINTILES',pd.DataFrame(groups).query("context=='ALL'")[['scope','group','n','closed','wins','winrate','mean_prediction','return_payoff_ratio','original_path_net']].to_string(index=False),flush=True)

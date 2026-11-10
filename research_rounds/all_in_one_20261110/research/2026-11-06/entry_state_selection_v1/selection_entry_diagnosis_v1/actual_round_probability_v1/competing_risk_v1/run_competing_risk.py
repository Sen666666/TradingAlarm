"""Frozen original-filled-round competing-risk audit. No account execution."""
from pathlib import Path
import json,hashlib,time,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
SRC=P/'ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv'
CLOCK=P.parent/'entry_probability_signal_v1/MARKET_CLOCK.csv'
COLS=['PVR_decision','protected_distance_over_prior_sigma','sigma20_prior','market_breadth20','market_delta5','mobile_first','original_i_buy_numeric']
ENDS=np.array([5,20,60,120]);STARTS=np.array([1,6,21,61]);H=120
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.integer):return int(v)
 if isinstance(v,np.bool_):return bool(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False))
assert sha(O/'FREEZE.json')=='edf47841afcb3f980c31e4856db4f997dbea8416f23a2688d0bce0e2ac319991'
freeze=json.loads((O/'FREEZE.json').read_text())
assert sha(SRC)==freeze['source_sha256']
assert not (O/'SUMMARY.json').exists(),'Do not repeat completed run'
start=time.monotonic()
f=pd.read_csv(SRC);f['round_id']=np.arange(len(f))
days=pd.read_csv(CLOCK,index_col=0,parse_dates=True).index;end=days.get_loc(pd.Timestamp('2026-05-15'))
f['signal_year']=pd.to_datetime(f.signal_day).dt.year;f['entry_year']=f.year
f['T']=np.where(f.closed,f.close_t-f.entry_t+1,np.nan)
f['potential_followup']=end-f.entry_t+1
f['horizon_mature']=f.potential_followup.ge(H)
f['state120']=np.where(f.closed&f['T'].le(H),np.where(f.y.eq(1),0,1),np.where(f.horizon_mature,2,np.nan))
f['complete_features']=np.isfinite(f[COLS]).all(axis=1)
assert np.array_equal(f.complete_features,f.features_known)
assert len(f)==2693 and f.entry_t.ge(0).all() and f.loc[f.closed,'T'].ge(1).all()
for name in ['p_positive120','p_nonpositive120','p_survive120','base_positive120','base_nonpositive120','base_survive120','causal_band','cutoff_index']:f[name]=np.nan
f['prediction_available']=False
dump('SOURCE_FREEZE.json',{str(p):sha(p) for p in [SRC,CLOCK,O/'FREEZE.json',Path(__file__)]})
def risk_data(frame,cut):
 g=frame[frame.t.ge(cut-504)&frame.t.lt(cut)&frame.entry_t.lt(cut)&frame.complete_features].copy()
 closed_known=g.closed&g.close_t.lt(cut)
 T=(g.close_t-g.entry_t+1).to_numpy()
 observed=np.minimum(H,cut-g.entry_t.to_numpy())
 observed=np.minimum(observed,np.where(closed_known,T,10**9)).astype(int)
 event=(closed_known.to_numpy()&(T<=H))
 expo=np.maximum(0,np.minimum(observed[:,None],ENDS)-STARTS+1)
 evbin=(T[:,None]>=STARTS)&(T[:,None]<=ENDS)&event[:,None]
 win=evbin&g.y.eq(1).to_numpy()[:,None];loss=evbin&g.y.eq(0).to_numpy()[:,None]
 counts=np.stack([expo-win-loss,win,loss],axis=2).astype(float)
 assert (counts>=0).all() and np.array_equal(counts.sum(2),expo)
 ri,bi=np.where(expo>0)
 return g,ri,bi,counts[ri,bi],observed,event
def matrices(g,ri,bi,features):
 if features:
  mu=g[COLS].to_numpy().mean(0);sd=g[COLS].to_numpy().std(0);sd=np.where(sd>1e-12,sd,1)
  z=np.clip((g[COLS].to_numpy()-mu)/sd,-5,5)
  X=np.column_stack([np.eye(4)[bi],z[ri]])
 else:mu=np.zeros(7);sd=np.ones(7);X=np.eye(4)[bi]
 p=X.shape[1];pen=np.zeros((p,p))
 for j in range(3):
  v=np.zeros(p);v[j]=-1;v[j+1]=1;pen+=4*np.outer(v,v)
 if features:pen[4:,4:]+=4*np.eye(7)
 return X,pen,mu,sd
def probabilities(X,b):
 z=X@b.T;m=np.maximum(0,z.max(1))
 ez=np.exp(z-m[:,None]);ec=np.exp(-m);den=ec+ez.sum(1)
 return ez/den[:,None],ec/den,m+np.log(den)
def derivatives(X,C,pen,b,hessian=True):
 p,q,ld=probabilities(X,b);n=C.sum(1);Y=C[:,1:];eta=X@b.T
 val=float(np.sum(n*ld-(Y*eta).sum(1))+.5*np.sum((b@pen)*b))
 grad=((n[:,None]*p-Y).T@X+b@pen)
 if not hessian:return val,grad
 d=X.shape[1];hess=np.zeros((2*d,2*d))
 for a in range(2):
  for c in range(2):
   w=n*p[:,a]*((1 if a==c else 0)-p[:,c])
   hess[a*d:(a+1)*d,c*d:(c+1)*d]=X.T@(w[:,None]*X)+(pen if a==c else 0)
 return val,grad,hess
def fit(g,ri,bi,C,features):
 X,pen,mu,sd=matrices(g,ri,bi,features);d=X.shape[1];b=np.zeros((2,d))
 b[:,:4]=np.log((C[:,1:].sum(0)+.5)/(C[:,0].sum()+.5))[:,None]
 for it in range(100):
  val,grad,hess=derivatives(X,C,pen,b)
  if np.max(np.abs(grad))<1e-7:break
  step=np.linalg.solve(hess+np.eye(2*d)*1e-10,grad.ravel()).reshape(2,d)
  scale=1.
  while scale>1e-12:
   newval,_=derivatives(X,C,pen,b-scale*step,False)
   if newval<=val+1e-10:break
   scale*=.5
  assert scale>1e-12,'Newton line search failed'
  b-=scale*step
  if np.max(np.abs(scale*step))<1e-10:break
 val,grad=derivatives(X,C,pen,b,False)
 assert np.max(np.abs(grad))<1e-5,(features,it,np.max(np.abs(grad)))
 return dict(b=b,mu=mu,sd=sd,features=features,iterations=it+1,objective=val,max_gradient=np.max(np.abs(grad)))
def predict(g,m):
 n=len(g)
 if not n:return np.zeros((0,3))
 z=np.clip((g[COLS].to_numpy()-m['mu'])/m['sd'],-5,5)
 result=np.zeros((n,3));S=np.ones(n)
 for j,length in enumerate([5,15,40,60]):
  A=np.repeat(np.eye(4)[j:j+1],n,axis=0)
  X=np.column_stack([A,z]) if m['features'] else A
  hazards,q,_=probabilities(X,m['b'])
  for k in range(length):
   result[:,:2]+=S[:,None]*hazards;S*=q
 result[:,2]=S
 assert np.max(np.abs(result.sum(1)-1))<1e-10 and (result>=0).all()
 return result
# Derivative finite differences on deterministic artificial counts, before any historical fit.
X=np.array([[1.,0.,.2],[0.,1.,-.4],[1.,0.,.6]])
C=np.array([[4.,1.,0.],[9.,0.,1.],[3.,1.,0.]])
pen=np.eye(3)*4;b=np.array([[-2.,-2.3,.1],[-1.7,-2.,-.2]])
v,g,h=derivatives(X,C,pen,b);eps=1e-5;numeric=[];hn=[]
for j in range(b.size):
 delta=np.zeros(b.size);delta[j]=eps
 va,ga=derivatives(X,C,pen,b+delta.reshape(b.shape),False)
 vb,gb=derivatives(X,C,pen,b-delta.reshape(b.shape),False)
 numeric.append((va-vb)/(2*eps));hn.append(((ga-gb)/(2*eps)).ravel())
assert np.max(np.abs(g.ravel()-numeric))<1e-7
assert np.max(np.abs(h-np.array(hn).T))<1e-7
models=[];audits=[];poisons=[];ages=[]
months=sorted({str(d.to_period('M')) for d in days if 2023<=d.year<=2025})
for month in months:
 dt=next(d for d in days if str(d.to_period('M'))==month);cut=days.get_loc(dt)
 g,ri,bi,C,obs,event=risk_data(f,cut)
 nw=int(C[:,1].sum());nl=int(C[:,2].sum())
 ok=len(g)>=300 and nw>=50 and nl>=50 and g.signal_day.nunique()>=60
 test=f[(pd.to_datetime(f.signal_day).dt.to_period('M').astype(str)==month)&f.complete_features]
 a=dict(month=month,first_signal_session=str(dt.date()),information_through=str(days[cut-1].date()),rounds=len(g),dates=g.signal_day.nunique(),stocks=g.sid.nunique(),observed_person_days=int(C.sum()),positive_exits=nw,nonpositive_exits=nl,right_censored_before_H=int((~event&(obs<H)).sum()),survived_H_observed=int((~event&(obs==H)).sum()),test_complete_features=len(test),allowed=ok)
 audits.append(a)
 for j in range(4):
  c=C[bi==j].sum(0);ages.append(dict(month=month,age_bin=j+1,continue_days=c[0],positive_exits=c[1],nonpositive_exits=c[2],at_risk_days=c.sum()))
 if not ok:models.append(dict(month=month,allowed=False));continue
 m=fit(g,ri,bi,C,True);base=fit(g,ri,bi,C,False)
 pp=predict(test,m);pb=predict(test,base);trainpred=predict(g,m)
 edges=np.quantile(trainpred[:,0],[.2,.4,.6,.8])
 f.loc[test.index,['p_positive120','p_nonpositive120','p_survive120']]=pp
 f.loc[test.index,['base_positive120','base_nonpositive120','base_survive120']]=pb
 f.loc[test.index,'causal_band']=np.searchsorted(edges,pp[:,0],side='left')+1
 f.loc[test.index,'cutoff_index']=cut;f.loc[test.index,'prediction_available']=True
 models.append(dict(month=month,allowed=True,feature=m,baseline=base,band_edges=edges))
 if month in ['2023-01','2024-01','2025-01','2025-12']:
  z=f.copy();unavailable=~(z.closed&z.close_t.lt(cut))
  z.loc[unavailable,'closed']=True;z.loc[unavailable,'close_t']=cut+777
  z.loc[unavailable,'y']=0
  gz,riz,biz,Cz,oz,ez=risk_data(z,cut)
  assert np.array_equal(g.round_id,gz.round_id) and np.array_equal(C,Cz) and np.array_equal(ri,riz) and np.array_equal(bi,biz)
  poisons.append(dict(month=month,future_exit_changed=True,training_counts_exactly_unchanged=True))
 print('FIT',month,len(g),nw,nl,len(test),flush=True)
assert not f.loc[f.signal_year.lt(2023),'prediction_available'].any()
assert (f.loc[f.prediction_available,'cutoff_index']<=f.loc[f.prediction_available,'t']).all()
assert (f.loc[f.prediction_available,'cutoff_index']-1<f.loc[f.prediction_available,'t']).all()
f.to_csv(O/'ALL_ROUNDS_COMPETING_RISK_PREDICTIONS.csv',index=False)
pd.DataFrame(audits).to_csv(O/'MONTHLY_RISK_SET_AUDIT.csv',index=False)
pd.DataFrame(ages).to_csv(O/'AGE_BIN_EVENT_SUPPORT.csv',index=False)
dump('MONTHLY_MODELS.json',models);dump('FUTURE_EXIT_POISON_AUDIT.json',poisons)
PRED=['p_positive120','p_nonpositive120','p_survive120'];BASE=['base_positive120','base_nonpositive120','base_survive120']
pred=f[f.signal_year.between(2023,2025)].copy()
pred['date_block']=(pred.entry_t//20).astype(int)
def crit(df):
 z=1.959963984540054
 return z+(z**3+z)/(4*df)+(5*z**5+16*z**3+3*z)/(96*df**2)+(3*z**7+19*z**5+17*z**3-15*z)/(384*df**3)
def mean_interval(g,values):
 v=np.asarray(values,float);n=len(v)
 if n==0:return dict(estimate=np.nan,lower=np.nan,upper=np.nan,n=0,blocks=0,stocks=0)
 est=v.mean();r=v-est
 def variance(keys):
  sums=pd.Series(r).groupby(np.asarray(keys)).sum();G=len(sums)
  return (G/(G-1)*np.sum(sums.to_numpy()**2)/n**2 if G>1 else np.nan),G
 vd,nd=variance(g.date_block.to_numpy());vs,ns=variance(g.sid.to_numpy())
 vc,nc=variance((g.date_block.astype(str)+'|'+g.sid.astype(str)).to_numpy())
 vv=np.nanmax([vd,vs,vd+vs-vc]);df=min(nd,ns)-1
 se=np.sqrt(max(0,vv))
 half=crit(df)*se if df>=5 else np.nan
 return dict(estimate=est,lower=est-half,upper=est+half,se=se,n=n,blocks=nd,stocks=ns,df=df,variance_date=vd,variance_stock=vs,variance_two_way=vd+vs-vc)
def auc_if(y,s):
 y=np.asarray(y,int);s=np.asarray(s,float);pos=np.sort(s[y==1]);neg=np.sort(s[y==0])
 if not len(pos) or not len(neg):return np.nan,np.full(len(y),np.nan)
 vp=(np.searchsorted(neg,s[y==1],side='left')+np.searchsorted(neg,s[y==1],side='right'))/(2*len(neg))
 vn=1-(np.searchsorted(pos,s[y==0],side='left')+np.searchsorted(pos,s[y==0],side='right'))/(2*len(pos))
 a=vp.mean();infl=np.zeros(len(y));pi=y.mean();infl[y==1]=(vp-a)/pi;infl[y==0]=(vn-a)/(1-pi)
 return a,infl
metrics=[];cal=[];groups=[];coverage=[];aucs=[];monthly=[]
def actual_group(g):
 z=g[g.closed];w=z[z.y.eq(1)];l=z[z.y.eq(0)]
 rw=w.round_return_on_cumulative_cost.mean();rl=l.round_return_on_cumulative_cost.mean()
 out=dict(n=len(g),closed=len(z),still_open=int((~g.closed).sum()),wins=int(z.y.sum()),mean_predicted_positive120=g.p_positive120.mean(),mean_predicted_survive120=g.p_survive120.mean(),original_net_CNY=z.round_pnl.sum(),mean_normalized_round_return=z.round_return_on_cumulative_cost.mean(),payoff_ratio=rw/abs(rl) if np.isfinite(rl) and rl<0 else np.nan)
 ci=mean_interval(z,z.y)
 out.update({('actual_win_'+k):v for k,v in ci.items()})
 out['all_round_win_lower']=z.y.sum()/len(g) if len(g) else np.nan
 out['all_round_win_upper']=(z.y.sum()+(~g.closed).sum())/len(g) if len(g) else np.nan
 return out
for scope in ['2023_2025','2023','2024','2025']:
 gg=pred if scope=='2023_2025' else pred[pred.signal_year.eq(int(scope))]
 for context in ['ALL','NORMAL']:
  g=gg if context=='ALL' else gg[gg.context.eq('NORMAL')]
  q=g[g.prediction_available&g.horizon_mature].copy()
  coverage.append(dict(scope=scope,context=context,actual_starts=len(g),missing_features=int((~g.complete_features).sum()),predictions=int(g.prediction_available.sum()),horizon_mature=int(g.horizon_mature.sum()),paired_primary=len(q),mature_still_open_at_source=int((~q.closed).sum()),immature_predicted=int((g.prediction_available&~g.horizon_mature).sum()),immature_exit_known=int((g.prediction_available&~g.horizon_mature&g.closed).sum())))
  if not len(q):continue
  y=q.state120.astype(int).to_numpy();oh=np.eye(3)[y];pp=q[PRED].to_numpy();bb=q[BASE].to_numpy()
  brier=((pp-oh)**2).sum(1);bbase=((bb-oh)**2).sum(1)
  ll=-np.log(np.maximum(pp[np.arange(len(q)),y],1e-15));lbase=-np.log(np.maximum(bb[np.arange(len(q)),y],1e-15))
  for metric,v,bv in [('Brier_sum',brier,bbase),('Log_loss',ll,lbase)]:
   metrics.append(dict(scope=scope,context=context,metric=metric,model_mean=v.mean(),baseline_mean=bv.mean(),**mean_interval(q,v-bv)))
  for arm,arr in [('FEATURE',pp),('BASELINE',bb)]:
   for c,name in enumerate(['positive120','nonpositive120','survive120']):
    cal.append(dict(scope=scope,context=context,arm=arm,state=name,bin='ALL',predicted=arr[:,c].mean(),observed=oh[:,c].mean(),**mean_interval(q,oh[:,c]-arr[:,c])))
    bins=np.digitize(arr[:,c],[.1,.2,.3,.4,.5,.75])
    for bi in sorted(set(bins)):
     mask=bins==bi;z=q.iloc[np.where(mask)[0]]
     cal.append(dict(scope=scope,context=context,arm=arm,state=name,bin=int(bi),predicted=arr[mask,c].mean(),observed=oh[mask,c].mean(),**mean_interval(z,oh[mask,c]-arr[mask,c])))
  yy=(y==0).astype(int);a,ia=auc_if(yy,pp[:,0]);ab,ib=auc_if(yy,bb[:,0])
  same=[auc_if(z.state120.eq(0),z.p_positive120)[0] for _,z in q.groupby('signal_day')]
  valid=[x for x in same if np.isfinite(x)]
  ci=mean_interval(q,ia+a)
  aucs.append(dict(scope=scope,context=context,auc=a,baseline_auc=ab,auc_lower=ci['lower'],auc_upper=ci['upper'],same_date_equal_weight_auc=np.mean(valid) if valid else np.nan,same_date_eligible_dates=len(valid),same_date_excluded_dates=len(same)-len(valid),**{'delta_'+k:v for k,v in mean_interval(q,ia-ib+a-ab).items()}))
  for band in [1,2,3,4,5]:
   z=q[q.causal_band.eq(band)]
   if len(z):groups.append(dict(scope=scope,context=context,band=band,observed_positive120=z.state120.eq(0).mean(),observed_nonpositive120=z.state120.eq(1).mean(),observed_survive120=z.state120.eq(2).mean(),**actual_group(z)))
  for mo,z in q.groupby(pd.to_datetime(q.signal_day).dt.to_period('M').astype(str)):
   for c,name in enumerate(['positive120','nonpositive120','survive120']):
    monthly.append(dict(scope=scope,context=context,month=mo,state=name,n=len(z),predicted=z[PRED[c]].mean(),baseline=z[BASE[c]].mean(),observed=z.state120.eq(c).mean()))
for name,data in [('PAIRED_PROPER_SCORE_CLUSTER.csv',metrics),('PROBABILITY_CALIBRATION.csv',cal),('HORIZON_COVERAGE.csv',coverage),('POSITIVE120_AUC_CLUSTER.csv',aucs),('CAUSAL_BAND_ACTUAL_ROUND_OUTCOMES.csv',groups),('MONTHLY_HORIZON_CALIBRATION.csv',monthly)]:
 pd.DataFrame(data).to_csv(O/name,index=False)
summary=dict(status='ONE_FIXED_ORIGINAL_FILLED_COHORT_COMPETING_RISK_AUDIT',H=H,monthly_fits=len(models),feature_model_parameters=22,baseline_parameters=8,account_runs=0,parameter_searches=0,source_rounds=len(f),signal_2023_2025_starts=len(pred),predictions=int(pred.prediction_available.sum()),mature_paired=int((pred.prediction_available&pred.horizon_mature).sum()),first_year_predictions=int(f.loc[f.signal_year.eq(2022),'prediction_available'].sum()),poison_checks=len(poisons),derivative_checks=True,elapsed_seconds=time.monotonic()-start,freeze_sha256=sha(O/'FREEZE.json'),notes=['Annual cohorts use SIGNAL year, entry_year also preserved.','Intervals condition on fitted models and omit refitting uncertainty; no multiplicity correction.','Same-date AUC positive by H vs both other states, equal weight among eligible dates.','Quintile-like bands use contemporaneous TRAINING reference, not five equally sized future test groups.','Feature/baseline trained on exact same feature-complete original starts and exposures.','No result here is a new account return or final winrate achievement.'])
dump('SUMMARY.json',summary)
dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('SUMMARY',json.dumps(clean(summary)),flush=True)
print('COVERAGE',pd.DataFrame(coverage).to_string(index=False),flush=True)
print('SCORES',pd.DataFrame(metrics).query("context=='ALL'").to_string(index=False),flush=True)
print('AUC',pd.DataFrame(aucs).query("context=='ALL'").to_string(index=False),flush=True)
print('CAL',pd.DataFrame(cal).query("context=='ALL' and bin=='ALL'")[['scope','arm','state','predicted','observed','lower','upper']].to_string(index=False),flush=True)
print('GROUPS',pd.DataFrame(groups).query("context=='ALL'")[['scope','band','n','closed','wins','actual_win_estimate','actual_win_lower','actual_win_upper','mean_predicted_positive120','observed_positive120','observed_survive120','payoff_ratio','original_net_CNY']].to_string(index=False),flush=True)

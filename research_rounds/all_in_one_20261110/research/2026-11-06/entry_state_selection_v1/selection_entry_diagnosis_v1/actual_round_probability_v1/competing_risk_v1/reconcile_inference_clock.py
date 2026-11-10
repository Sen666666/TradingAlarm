from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
H=120
before={n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ['MONTHLY_MODELS.json','ALL_ROUNDS_COMPETING_RISK_PREDICTIONS.csv']}
f=pd.read_csv(O/'ALL_ROUNDS_COMPETING_RISK_PREDICTIONS.csv')
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

after={n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in before}
assert before==after
(O/'INFERENCE_RECONCILIATION.json').write_text(json.dumps({'refits':0,'prediction_changes':0,'date_block':'entry_t//20 per frozen design','unchanged_hashes':after},indent=2))
s=json.loads((O/'SUMMARY.json').read_text());s['inference_date_block']='entry_t//20';s['inference_only_correction']=True
(O/'SUMMARY.json').write_text(json.dumps(s,indent=2))
(O/'OUTPUT_SHA256.json').write_text(json.dumps({x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in O.iterdir() if x.is_file() and x.name!='OUTPUT_SHA256.json'},indent=2))
print('Inference-only correction completed; model and prediction hashes unchanged')

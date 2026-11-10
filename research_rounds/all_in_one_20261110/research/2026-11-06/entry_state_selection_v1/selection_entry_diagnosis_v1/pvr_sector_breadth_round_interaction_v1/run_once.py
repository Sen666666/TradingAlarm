"""One frozen PVR x sector breadth round-label diagnostic; no account imports."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent; B=O.parent
S=B/'ALL_FIRST_ENTRIES.csv'; C=B/'entry_probability_signal_v1/MARKET_CLOCK.csv'
MODELS={'constant':0,'pvr':1,'additive':2,'interaction':3}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v)for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2))
def sigmoid(z):return 1/(1+np.exp(-np.clip(z,-35,35)))
def design(g,mu,sd,im,isd):
 z=np.clip((g[['PVR_decision','industry_breadth20']].to_numpy(float)-mu)/sd,-5,5)
 inter=(z[:,0]*z[:,1]-im)/isd
 return np.c_[np.ones(len(g)),z,inter]
def fit(X,y,pen):
 b=np.zeros(X.shape[1]);b[0]=math.log(y.mean()/(1-y.mean()))
 def obj(b):
  z=X@b
  return (np.logaddexp(0,z)-y*z).sum()+.5*np.sum(pen*b*b)
 for it in range(100):
  p=sigmoid(X@b);grad=X.T@(p-y)+pen*b
  if np.abs(grad).max()<1e-7:break
  h=X.T@((p*(1-p))[:,None]*X)+np.diag(pen)
  step=np.linalg.solve(h,grad);rate=1;old=obj(b)
  while rate>1e-10 and obj(b-rate*step)>old+1e-10:rate*=.5
  b-=rate*step
 gmax=np.abs(X.T@(sigmoid(X@b)-y)+pen*b).max()
 assert gmax<1e-6,(gmax,it)
 return b,gmax,it+1
def auc(y,p):
 y=np.asarray(y)==1;p=np.asarray(p);n=y.sum();m=len(y)-n
 return (pd.Series(p).rank().to_numpy()[y].sum()-n*(n+1)/2)/(n*m) if n and m else np.nan
def cluster(g,v):
 v=np.asarray(v);n=len(v);mu=v.mean();q=pd.DataFrame({'u':(v-mu)/n,'block':g.t.to_numpy()//20,'sid':g.sid.to_numpy()})
 def cv(keys):
  a=q.groupby(keys).u.sum();k=len(a)
  return k/(k-1)*np.square(a).sum() if k>1 else np.nan
 vb=cv('block');vs=cv('sid');vi=cv(['block','sid']);v2=vb+vs-vi
 se=math.sqrt(max(0,vb,vs,v2))
 return dict(n=n,mean=mu,date_blocks=q.block.nunique(),stocks=q.sid.nunique(),block_se=math.sqrt(vb),stock_se=math.sqrt(vs),two_way_variance=v2,conservative_se=se,low95=mu-1.96*se,high95=mu+1.96*se)
def outcome(g):
 q=g[g.closed];r=q.round_return_on_cumulative_cost;w=q[q.round_pnl>0];l=q[q.round_pnl<=0]
 avw=w.round_return_on_cumulative_cost.mean();avl=l.round_return_on_cumulative_cost.mean()
 return dict(n=len(g),closed=len(q),open=len(g)-len(q),wins=len(w),winrate=len(w)/len(q) if len(q) else np.nan,
  all_birth_win_lower=len(w)/len(g) if len(g) else np.nan,all_birth_win_upper=(len(w)+len(g)-len(q))/len(g) if len(g) else np.nan,
  mean_return=r.mean(),mean_win_return=avw,mean_loss_return=avl,payoff=avw/abs(avl) if avl<0 else np.nan,
  original_net=q.round_pnl.sum(),profit_factor=w.round_pnl.sum()/abs(l.round_pnl.sum()) if l.round_pnl.sum()<0 else np.nan,
  return_q05=r.quantile(.05),return_q95=r.quantile(.95),return_worst05=r[r<=r.quantile(.05)].mean(),
  positive20_count=int((r>=.2).sum()),complete60=int(g.complete60.sum()),big60_count=int(g.big60_posthoc.sum()))
def scopes(g):
 yield '2023_2025',g[g.signal_year.between(2023,2025)]
 for y,z in g.groupby('signal_year'):yield str(y),z
assert sha(O/'FREEZE.json')=='c2c31baf100097855e0c2556bfec0be22ad1d0b1ee1a24fca8c00114c2ba2a9c'
assert not (O/'FIT_STARTED.json').exists()
sources={str(p):sha(p)for p in [S,C,O/'FREEZE.json',Path(__file__)]}
f=pd.read_csv(S);f=f[f.account.eq('PVR')&f.first_kind.eq('add')].copy().reset_index(drop=True)
assert len(f)==1814
days=pd.read_csv(C,index_col=0,parse_dates=True).index;end=days.get_loc(pd.Timestamp('2026-05-15'))
for n,col in [('t','signal_day'),('entry_t','entry_day'),('close_t','closed_day')]:f[n]=days.get_indexer(pd.to_datetime(f[col]))
f['signal_year']=f.signal_day.str[:4].astype(int)
f['mature120']=end-f.entry_t+1>=120
f['W']=f.closed&f.close_t.lt(f.entry_t+120)&f.round_pnl.gt(0)
f['U']=~(f.closed&f.close_t.lt(f.entry_t+120))
f['y']=f.W.astype(int)
f['feature_known']=np.isfinite(f[['PVR_decision','industry_breadth20']]).all(axis=1)
f['side']=np.where(f.industry_breadth20.ge(.5),'B_ge_half','B_lt_half')
f['known']=False;f['unknown_reason']='FIRST_YEAR_NO_BACKFILL';support=[];models=[];aud=[]
for m in MODELS:f[m]=np.nan;f[m+'_q']=np.nan
dump('FIT_STARTED.json',dict(sources=sources,new_models=1,controls=3,accounts=0,parameter_scans=0))
for month in sorted(set(days[days.year>=2023].to_period('M').astype(str))):
 cut=next(i for i,d in enumerate(days)if str(d.to_period('M'))==month)
 tr=f[(f.t>=cut-504)&(f.entry_t<=cut-120)&f.feature_known].copy()
 te=f[f.signal_day.str.startswith(month)&f.feature_known]
 sr=dict(month=month,cut=cut,cutoff=str(days[cut].date()),n=len(tr),dates=tr.signal_day.nunique(),stocks=tr.sid.nunique(),W=int(tr.W.sum()),L=int((~tr.W&~tr.U).sum()),U=int(tr.U.sum()),test_n=len(te))
 ok=len(tr)>=300 and tr.W.sum()>=50 and (~tr.W&~tr.U).sum()>=50 and tr.signal_day.nunique()>=60
 for side in ['B_ge_half','B_lt_half']:
  q=tr[tr.side.eq(side)]
  sr.update({side+'_n':len(q),side+'_dates':q.signal_day.nunique(),side+'_W':int(q.W.sum()),side+'_L':int((~q.W&~q.U).sum()),side+'_PVR_sd':q.PVR_decision.std()})
  ok=ok and q.W.sum()>=20 and (~q.W&~q.U).sum()>=20 and q.signal_day.nunique()>=30
 sr['support']=bool(ok);support.append(sr)
 f.loc[f.signal_day.str.startswith(month),'unknown_reason']='MINIMUM_STATE_SUPPORT' if not ok else 'MISSING_FEATURE'
 if not ok:continue
 assert not tr.U.any(),('MATURE_PENDING_NOT_ALLOWED_TO_DROP',month)
 assert (tr.close_t<cut).all() and (tr.entry_t+119<cut).all()
 mu=tr[['PVR_decision','industry_breadth20']].mean().to_numpy();sd=tr[['PVR_decision','industry_breadth20']].std(ddof=0).to_numpy()
 assert (sd>1e-12).all()
 z=np.clip((tr[['PVR_decision','industry_breadth20']].to_numpy()-mu)/sd,-5,5);inter=z[:,0]*z[:,1];im=inter.mean();isd=inter.std()
 assert isd>1e-12
 X=design(tr,mu,sd,im,isd);XX=design(te,mu,sd,im,isd);y=tr.y.to_numpy()
 rank=np.linalg.matrix_rank(X);cond=np.linalg.cond(X);assert rank==4 and cond<1e8
 out=dict(**sr,mu=mu,sd=sd,interaction_mean=im,interaction_sd=isd,rank=rank,condition=cond,models={})
 for name,n in MODELS.items():
  pen=np.array([0.,4.,4.,16.])[:n+1];b,gm,it=fit(X[:,:n+1],y,pen);pp=sigmoid(XX[:,:n+1]@b);tp=sigmoid(X[:,:n+1]@b)
  edges=np.quantile(tp,[.2,.4,.6,.8])
  f.loc[te.index,name]=pp;f.loc[te.index,name+'_q']=np.searchsorted(edges,pp,side='right')+1
  out['models'][name]=dict(beta=b,gradient=gm,iterations=it,training_edges=edges)
 badd=np.array(out['models']['additive']['beta'])
 assert np.array_equal(sigmoid(X[:,:3]@badd),sigmoid(X@np.r_[badd,0.]))
 # Unavailable/late labels cannot change the actual training target or ids.
 poison=f.copy();poison.loc[(~poison.closed)|(poison.close_t>=cut)|(poison.close_t>=poison.entry_t+120),'round_pnl']=1e9
 yp=poison.closed&poison.close_t.lt(poison.entry_t+120)&poison.round_pnl.gt(0)
 assert np.array_equal(yp.loc[tr.index].astype(int),y)
 bb=np.array(out['models']['interaction']['beta']);out['PVR_slope_B25']=float((bb[1]+bb[3]*((.25-mu[1])/sd[1])/isd)/sd[0]);out['PVR_slope_B75']=float((bb[1]+bb[3]*((.75-mu[1])/sd[1])/isd)/sd[0])
 f.loc[te.index,'known']=True;f.loc[te.index,'unknown_reason']=''
 models.append(out);aud.append(dict(month=month,uniform_maturity=True,label_poison_equal=True,zero_interaction_recovers_additive=True))
pd.DataFrame(support).to_csv(O/'MONTHLY_SUPPORT.csv',index=False);dump('MONTHLY_MODELS.json',models);dump('CLOCK_NESTING_AUDIT.json',aud)
# Seal scores and membership before reporting any test-outcome statistics.
f.to_csv(O/'ORIGINAL_FIRST_MOBILE_PREDICTIONS.csv',index=False)
sel=[]
for day,g in f[f.known].groupby('signal_day'):
 K=(len(g)+1)//2
 for name in list(MODELS)+['rawPVR']:
  col='PVR_decision'if name=='rawPVR'else name
  order=g.sort_values([col,'PVR_decision','sid'],ascending=[False,False,True],kind='stable')
  for idx in order.index[:K]:sel.append(dict(index=int(idx),signal_day=day,model=name,K=K))
selected=pd.DataFrame(sel);selected.to_csv(O/'SAME_DATE_TOP_HALF_SELECTIONS.csv',index=False)
dump('PREDICTION_SEAL.json',dict(prediction_sha256=sha(O/'ORIGINAL_FIRST_MOBILE_PREDICTIONS.csv'),selection_sha256=sha(O/'SAME_DATE_TOP_HALF_SELECTIONS.csv'),accounts=0,new_unbought_predictions=0))
known=f[f.known].copy();main=known[known.mature120&known.signal_year.between(2023,2025)].copy()
assert not main.U.any()
quality=[];paired=[];same=[];cal=[];quant=[];coverage=[]
for scope,g in scopes(f[f.signal_year>=2023]):
 coverage.append(dict(scope=scope,total=len(g),known=int(g.known.sum()),mature=int(g.mature120.sum()),known_mature=int((g.known&g.mature120).sum()),unknown_features=int((~g.feature_known).sum()),**outcome(g)))
for scope,g in scopes(main):
 for name in MODELS:
  pp=g[name].to_numpy();y=g.y.to_numpy();bs=(pp-y)**2;ll=np.logaddexp(0,np.log(pp/(1-pp)))-y*np.log(pp/(1-pp))
  quality.append(dict(scope=scope,model=name,n=len(g),wins=int(y.sum()),prediction_mean=pp.mean(),winrate=y.mean(),brier=bs.mean(),logloss=ll.mean(),auc=auc(y,pp)))
  for groupcols,label in [(['signal_day'],'same_day'),(['signal_day','sector'],'same_day_sector')]:
   vals=[];nr=0
   for _,q in g.groupby(groupcols):
    v=auc(q.y,q[name])
    if np.isfinite(v):vals.append(v);nr+=len(q)
   same.append(dict(scope=scope,model=name,domain=label,eligible_groups=len(vals),eligible_rows=nr,all_groups=g.groupby(groupcols).ngroups,mean_auc=np.mean(vals)if vals else np.nan))
  for b in range(6):
   edges=[0,.1,.2,.3,.4,.5,1];q=g[(g[name]>=edges[b])&(g[name]<(edges[b+1]if b<5 else 1.000001))]
   cal.append(dict(scope=scope,model=name,bin_lo=edges[b],bin_hi=edges[b+1],mean_p=q[name].mean(),**outcome(q)))
  for n in range(1,6):
   q=g[g[name+'_q'].eq(n)];quant.append(dict(scope=scope,model=name,quintile=n,mean_p=q[name].mean(),**outcome(q)))
 for base in ['additive','pvr','constant']:
  y=g.y.to_numpy();p1=g.interaction.to_numpy();p0=g[base].to_numpy()
  for metric,v in [('brier',(p1-y)**2-(p0-y)**2),('logloss',-y*np.log(p1/p0)-(1-y)*np.log((1-p1)/(1-p0)))]:
   paired.append(dict(scope=scope,baseline=base,metric=metric,**cluster(g,v)))
pd.DataFrame(quality).to_csv(O/'PROBABILITY_QUALITY.csv',index=False);pd.DataFrame(paired).to_csv(O/'PAIRED_CLUSTER_SCORES.csv',index=False)
pd.DataFrame(same).to_csv(O/'SAME_DATE_AUC.csv',index=False);pd.DataFrame(cal).to_csv(O/'CALIBRATION.csv',index=False)
pd.DataFrame(quant).to_csv(O/'TRAIN_QUINTILE_OUTCOMES.csv',index=False);pd.DataFrame(coverage).to_csv(O/'COVERAGE.csv',index=False)
# Paired rank uncertainty, conditioned on fitted models.
jack=[]
g=main
for name in ['interaction','additive','pvr','rawPVR']:
 col='PVR_decision'if name=='rawPVR'else name;base=auc(g.y,g[col]);se={}
 for label,group in [('block',g.t//20),('stock',g.sid)]:
  vals=[auc(g.loc[group.ne(v),'y'],g.loc[group.ne(v),col])for v in group.unique()];vals=np.array([v for v in vals if np.isfinite(v)]);G=len(vals)
  se[label]=math.sqrt((G-1)/G*np.square(vals-vals.mean()).sum())
 ss=max(se.values());jack.append(dict(model=name,auc=base,block_se=se['block'],stock_se=se['stock'],low95=base-1.96*ss,high95=base+1.96*ss))
pd.DataFrame(jack).to_csv(O/'AUC_CLUSTER.csv',index=False)
rankout=[];retention=[];major=[];state=[]
for scope,g in scopes(main):
 for name in list(MODELS)+['rawPVR']:
  ids=set(selected[selected.model.eq(name)]['index']);q=g[g.index.isin(ids)]
  rankout.append(dict(scope=scope,model=name,dates=q.signal_day.nunique(),**outcome(q)))
  for base in ['rawPVR','additive']:
   old=set(selected[selected.model.eq(base)]['index'])&set(g.index);new=ids&set(g.index)
   for tail,mask in [('positive20',g.round_return_on_cumulative_cost.ge(.2)),('big60',g.complete60&g.big60_posthoc)]:
    tailids=set(g.index[mask]);oldtail=old&tailids;newtail=new&tailids
    retention.append(dict(scope=scope,model=name,baseline=base,tail=tail,old=len(oldtail),new=len(newtail),retained=len(oldtail&newtail),lost=len(oldtail-newtail),added=len(newtail-oldtail)))
 for side,q in g.groupby('side'):
  for name in MODELS:state.append(dict(scope=scope,side=side,model=name,n=len(q),dates=q.signal_day.nunique(),mean_p=q[name].mean(),brier=np.square(q[name]-q.y).mean(),auc=auc(q.y,q[name]),**{k:v for k,v in outcome(q).items()if k!='n'}))
for period,lo,hi in [('924','2024-09-19','2024-10-08'),('2026Q1','2026-01-01','2026-03-31')]:
 g=f[f.signal_day.between(lo,hi)]
 for name in list(MODELS)+['rawPVR']:
  ids=set(selected[selected.model.eq(name)]['index']);q=g[g.index.isin(ids)]
  major.append(dict(period=period,model=name,total_original=len(g),known=int(g.known.sum()),mature=int(g.mature120.sum()),**outcome(q)))
pd.DataFrame(rankout).to_csv(O/'SAME_DATE_TOP_HALF_OUTCOMES.csv',index=False)
pd.DataFrame(retention).to_csv(O/'RIGHT_TAIL_RETENTION.csv',index=False);pd.DataFrame(major).to_csv(O/'MAJOR_PERIODS.csv',index=False);pd.DataFrame(state).to_csv(O/'STATE_DIAGNOSTICS.csv',index=False)
assert all(sha(p)==h for p,h in sources.items())
summary=dict(status='COMPLETE_ONE_FROZEN_INTERACTION_TEST_NOT_NEW_POLICY',births=len(f),feature_known=int(f.feature_known.sum()),months=len(support),fit_months=len(models),first_prediction=known.signal_day.min(),known_predictions=len(known),main_rows=len(main),main_wins=int(main.y.sum()),main_stocks=main.sid.nunique(),main_dates=main.signal_day.nunique(),main_blocks=(main.t//20).nunique(),condition_max=max(m['condition']for m in models),interaction_sign_flip_months=sum(m['PVR_slope_B25']*m['PVR_slope_B75']<0 for m in models),accounts=0,parameter_scans=0,new_unbought_predictions=0,sources_unchanged=True)
dump('SUMMARY.json',summary);dump('OUTPUT_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
print(json.dumps(clean(summary),indent=2));print(pd.DataFrame(quality).to_string(index=False));print(pd.DataFrame(paired).query("scope=='2023_2025'").to_string(index=False));print(pd.DataFrame(same).query("model=='interaction'").to_string(index=False));print(pd.DataFrame(rankout).to_string(index=False))

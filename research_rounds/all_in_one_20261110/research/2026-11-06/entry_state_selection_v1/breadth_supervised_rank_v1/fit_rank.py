from pathlib import Path
import json,hashlib,time
import numpy as np,pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
O=Path(__file__).resolve().parent;R=O.parent;F=['pvr','persistence','diffusion','risk_distance','fresh_CP','relative_volume','strength_diffusion'];CL=['W','U','L']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.item() if isinstance(a,np.generic) else str(a))+'\n')
def weights(t):
 ns=t.groupby('day').sector.transform('nunique');ne=t.groupby(['day','sector']).event_id.transform('nunique');nc=t.groupby('event_id').sid.transform('size');w=1/(ns*ne*nc);assert np.allclose(w.groupby(t.day).sum(),1);return w.to_numpy(float)
assert not (O/'MODEL.json').exists();start=time.monotonic();sources=json.load(open(O/'SOURCE_HASHES.json'));assert all(sha(p)==h for p,h in sources.items())
c=pd.read_parquet(O/'FEATURES.parquet');labels=pd.read_parquet(O/'LABELS_120.parquet');train=c.merge(labels[['event_id','sid','label','horizon_day','net_pnl']],on=['event_id','sid'],validate='one_to_one');train=train[train.window.eq('2022')&train.feature_known&train.label.isin(CL)].copy();assert train.horizon_day.max()<pd.Timestamp('2023-07-05')
w=weights(train);train['_joint_weight']=w;a=train[F].to_numpy(float);mu=np.average(a,axis=0,weights=w);sd=np.sqrt(np.average((a-mu)**2,axis=0,weights=w));assert (sd>1e-12).all();X=np.column_stack([np.ones(len(a)),np.clip((a-mu)/sd,-5,5)]);assert np.linalg.matrix_rank(X)==X.shape[1];y=np.array([CL.index(v)for v in train.label]);Y=np.eye(3)[y];P=X.shape[1];pen=np.ones((P,2));pen[0]=0
# Freeze actual feature/transformation/training identities before the first fit.
dump('FIT_SEAL.json',dict(protocol_sha256=sha(O/'PROTOCOL.json'),script_sha256=sha(Path(__file__)),feature_sha256=sha(O/'FEATURES.parquet'),label_sha256=sha(O/'LABELS_120.parquet'),training_identity_sha256=hashlib.sha256(train[['event_id','sid','label']].to_csv(index=False).encode()).hexdigest(),training_rows=len(train),dates=train.day.nunique(),weight_sum=w.sum(),weighted_class_mass=dict(zip(CL,w@Y)),feature_mean=dict(zip(F,mu)),feature_sd=dict(zip(F,sd)),matrix_rank=int(np.linalg.matrix_rank(X)),matrix_condition=float(np.linalg.cond(X)),already_seen_history=True,fit_before2024=True))
def prob(B,x):
 v=np.column_stack([x@B,np.zeros(len(x))]);return np.exp(v-logsumexp(v,axis=1)[:,None])
def objective(b):
 B=b.reshape(P,2);v=np.column_stack([X@B,np.zeros(len(X))]);p=np.exp(v-logsumexp(v,axis=1)[:,None]);value=np.sum(w*(logsumexp(v,axis=1)-v[np.arange(len(y)),y]))+2*np.sum(pen*B*B);g=X.T@(w[:,None]*(p-Y)[:,:2])+4*pen*B;return value,g.ravel()
b0=np.zeros((P,2));tot=w@Y;b0[0]=np.log(tot[:2]/tot[2]);fit=minimize(objective,b0.ravel(),jac=True,method='L-BFGS-B',options=dict(maxiter=1000,ftol=1e-12,gtol=1e-8));B=fit.x.reshape(P,2);grad=np.max(np.abs(objective(fit.x)[1]));assert fit.success and grad<1e-5,(fit.message,grad)
# Analytic gradient central finite difference on initial and final states.
errs=[]
for bb in [b0.ravel(),fit.x]:
 gg=objective(bb)[1]
 for k in range(len(bb)):
  hi=bb.copy();lo=bb.copy();hi[k]+=1e-5;lo[k]-=1e-5;fd=(objective(hi)[0]-objective(lo)[0])/2e-5;errs.append(abs(fd-gg[k]))
assert max(errs)<1e-5
models={}
for cl in ['W','L']:
 t=train[train.label.eq(cl)].copy();tw=t['_joint_weight'].to_numpy(float);x=np.column_stack([np.ones(len(t)),np.clip((t.risk_distance.to_numpy()-mu[F.index('risk_distance')])/sd[F.index('risk_distance')],-5,5)]);v=np.abs(t.net_pnl.to_numpy());assert (v>0).all()
 def gamma(b):
  eta=np.clip(x@b,-30,30);mean=np.exp(eta);loss=np.sum(tw*(v/mean+eta))+2*b[1]**2;g=x.T@(tw*(1-v/mean));g[1]+=4*b[1];return loss,g
 ff=minimize(gamma,np.array([np.log(np.average(v,weights=tw)),0.]),jac=True,method='L-BFGS-B',options=dict(maxiter=1000,ftol=1e-12,gtol=1e-8));assert ff.success and max(abs(gamma(ff.x)[1]))<1e-5,(ff.message,gamma(ff.x));models[cl]=dict(coefficients=ff.x.tolist(),rows=len(t),dates=t.day.nunique(),weighted_mean=float(np.average(v,weights=tw)),gradient_max=float(max(abs(gamma(ff.x)[1]))))
model=dict(features=F,classes=CL,mean=mu.tolist(),sd=sd.tolist(),coefficients=B.tolist(),magnitude=models,optimizer_success=bool(fit.success),gradient_max=float(grad),gradient_finite_difference_max=max(errs),training_rows=len(train),training_dates=train.day.nunique(),ridge=2,parameter_searches=0,accounts=0)
dump('MODEL.json',model)
known=c.feature_known;cx=np.column_stack([np.ones(known.sum()),np.clip((c.loc[known,F].to_numpy()-mu)/sd,-5,5)]);pred=prob(B,cx)
for k,cl in enumerate(CL):c.loc[known,'p'+cl]=pred[:,k]
rx=np.column_stack([np.ones(known.sum()),cx[:,1+F.index('risk_distance')]])
for cl in ['W','L']:c.loc[known,'mean_'+cl]=np.exp(np.clip(rx@np.array(models[cl]['coefficients']),-30,30))
c['pClosure']=c.pW+c.pL;c['win_component']=c.pW*c.mean_W;c['loss_component']=c.pL*c.mean_L;c['conditional_net']=(c.win_component-c.loss_component)/c.pClosure;c['score_known']=c.feature_known&np.isfinite(c.conditional_net)&c.pClosure.gt(0)
c.to_parquet(O/'SCORED_CANDIDATES.parquet',index=False)
base=pd.read_csv(R/'breadth_pvr3_priority_v1/SEALED_CLOSE_SELECTED.csv');base=base[base.ranking_strategy.eq('PVR_DESC')];K=base.groupby('event_id').size();out=[]
for event,g in c.groupby('event_id',sort=False):
 order=g.sort_values(['PVR_score','sid'],ascending=[False,True],kind='stable');k=int(K.get(event,0));ind=list(order.index);good=order.score_known.to_numpy();slots=np.flatnonzero(good)
 for name,col in [('PVR_DESC','PVR_score'),('PWIN','pW'),('CONDITIONAL_NET','conditional_net')]:
  ix=ind.copy()
  if name!='PVR_DESC':
   repl=order[order.score_known].sort_values([col,'PVR_score','sid'],ascending=[False,False,True],kind='stable').index.tolist()
   for sl,j in zip(slots,repl):ix[sl]=j
  v=c.loc[ix[:k],['event_id','sid','day','window','arm','event_type','sector','PVR_score','pW','pL','pU','pClosure','mean_W','mean_L','win_component','loss_component','conditional_net','score_known']].copy();v['method']=name;v['selected_rank']=range(1,len(v)+1);out.append(v)
s=pd.concat(out,ignore_index=True);s.to_parquet(O/'SEALED_SELECTIONS.parquet',index=False);counts=s.groupby(['event_id','method']).size().unstack();assert counts.nunique(axis=1).eq(1).all();keys=lambda d:set(map(tuple,d[['event_id','sid']].to_numpy()));assert keys(s[s.method.eq('PVR_DESC')])==keys(base)
coef=pd.DataFrame(B,index=['intercept']+F,columns=['W_vs_L','U_vs_L']);coef.to_csv(O/'COEFFICIENTS.csv')
dump('RANK_SEAL.json',dict(created=str(pd.Timestamp.now(tz='UTC')),rows=len(s),all_K_equal=True,PVR_baseline_exact=True,model_unknown_slots_fixed=True,no_next_open_backfill=True,no2024_labels_in_fit=True,future_label_poison='training selects2022 only and cutoff2023-07-05, no2024 features or labels enter scaling, coefficients or magnitude fitting',hashes={str(p):sha(p)for p in [O/'PROTOCOL.json',O/'FIT_SEAL.json',O/'MODEL.json',O/'SCORED_CANDIDATES.parquet',O/'SEALED_SELECTIONS.parquet',Path(__file__)]}))
print(coef.to_string());print(json.dumps(models,indent=2));print('RANK SEALED',len(s),'seconds',time.monotonic()-start,flush=True)

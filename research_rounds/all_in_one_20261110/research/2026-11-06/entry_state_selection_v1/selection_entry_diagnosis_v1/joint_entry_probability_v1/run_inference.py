from pathlib import Path
import json,hashlib,time,math,warnings
import numpy as np,pandas as pd
from scipy.special import logsumexp,gammaln,digamma
from scipy.optimize import minimize
from scipy.stats import rankdata,norm
O=Path(__file__).resolve().parent;B=O.parent
ROUND=B/"actual_round_probability_v1/ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv"
CLOCK=B/"entry_probability_signal_v1/MARKET_CLOCK.csv"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def simplex(z):
 z=np.asarray(z);zz=np.concatenate([z.reshape(-1,2),np.zeros((len(z)//2,1))],axis=1);lp=zz-logsumexp(zz,axis=1)[:,None];return np.exp(lp),lp
def logits(p):return np.log(p[:,:2]/p[:,2:])
def Xmat(g,model):
 w=g.w.to_numpy();T=g["T"].to_numpy()
 if model=="constant":return np.ones((len(g),1))
 if model=="speed":return np.column_stack([1-w,w])
 return np.column_stack([1-w,w*(T==1),w*(T==-1)])
def lpgrad(z,X,y,gradient=False):
 pi,lg=simplex(z); nc=len(pi)-1;p=X@pi; chosen=p[np.arange(len(y)),y]
 if np.any(chosen<=0) or np.any(pi[0]<=0):return (-np.inf,np.zeros_like(z)) if gradient else -np.inf
 val=float(np.log(chosen).sum()+.5*lg[0].sum()+20*np.sum(pi[0]*lg[1:])-nc*gammaln(20*pi[0]).sum())
 if not gradient:return val
 d=np.zeros_like(pi)
 for cc in range(3):
  mask=y==cc
  if mask.any():d[:,cc]=np.sum(X[mask]/chosen[mask,None],axis=0)
 d[0]+=.5/pi[0]+20*(lg[1:].sum(0)-nc*digamma(20*pi[0]))
 d[1:]+=20*pi[0]/pi[1:]
 grad=(pi*(d-(pi*d).sum(1)[:,None]))[:,:2].ravel()
 return val,grad
def diag_stat(chain):
 # chain: chains, draws, variables. Split rank-normalized Rhat and bulk ESS.
 m,n,d=chain.shape;half=n//2;x=np.concatenate([chain[:,:half],chain[:,-half:]],axis=0);M,N,_=x.shape
 rh=[];ess=[]
 for k in range(d):
  q=x[:,:,k];rk=rankdata(q.ravel(),method="average");z=norm.ppf((rk-.375)/(len(rk)+.25)).reshape(M,N)
  W=np.mean(np.var(z,axis=1,ddof=1));BB=N*np.var(z.mean(1),ddof=1);vp=(N-1)/N*W+BB/N
  if W<=0 or vp<=0:rh.append(np.inf);ess.append(0);continue
  rh.append(math.sqrt(vp/W));center=z-z.mean(1)[:,None];nfft=1<<((2*N-1).bit_length())
  ff=np.fft.rfft(center,n=nfft,axis=1);ac=np.fft.irfft(ff*np.conjugate(ff),n=nfft,axis=1)[:,:N]/N
  rho=1-(W-ac.mean(0))/vp;rho[0]=1;pair=rho[:N//2*2:2]+rho[1:N//2*2:2];kept=[]
  for a in pair:
   if a<0:break
   kept.append(min(float(a),kept[-1] if kept else float(a)))
  tau=max(1.,-1+2*sum(kept));ess.append(M*N/tau)
 return dict(max_rhat=max(rh),min_bulk_ess=min(ess),rhat=rh,bulk_ess=ess,passed=max(rh)<=1.01 and min(ess)>=400)
def run_posterior(X,y,model,seed):
 counts=np.bincount(y,minlength=3);k=X.shape[1];base=(counts+.5)/(len(y)+1.5)
 if model=="constant":
  rng=np.random.default_rng(seed);s=rng.dirichlet(counts+.5,size=16000)[:,None,:]
  return s,dict(passed=True,exact_conjugate=True,counts=counts)
 # Exact categorical allocations and exact child Dirichlet draws avoid the
 # rare-U hierarchical funnel. The only MH block is the collapsed 2-D pi0.
 def base_lp(z,N):
  pi,lg=simplex(z);p=pi[0];l=lg[0]
  if np.any(p<=0):return -np.inf
  return float((N[0]+.5)@l+np.sum(gammaln(20*p+N[1:])-gammaln(20*p)))
 pseudo=X.T@np.eye(3)[y];z0=np.log(base[:2]/base[2])
 opt=minimize(lambda z:-base_lp(z,pseudo),z0,method="L-BFGS-B",bounds=[(-25,25)]*2,options=dict(maxiter=500,ftol=1e-13,gtol=1e-7))
 mode=opt.x;assert opt.success and np.max(np.abs(mode))<24,(model,opt.message,mode)
 eps=1e-3;H=np.zeros((2,2));f0=base_lp(mode,pseudo)
 for i in range(2):
  e=np.zeros(2);e[i]=eps;H[i,i]=-(base_lp(mode+e,pseudo)-2*f0+base_lp(mode-e,pseudo))/eps**2
 e=np.array([eps,0.]);v=np.array([0.,eps]);H[0,1]=H[1,0]=-(base_lp(mode+e+v,pseudo)-base_lp(mode+e-v,pseudo)-base_lp(mode-e+v,pseudo)+base_lp(mode-e-v,pseudo))/(4*eps**2)
 eig,U=np.linalg.eigh(H);L=np.linalg.cholesky((U*(1/np.maximum(eig,1e-6)))@U.T)
 def stable_dirichlet(alpha,rng):
  # Gamma(a)=Gamma(a+1)*U**(1/a), evaluated in log coordinates.
  lg=np.log(rng.gamma(alpha+1.))-rng.exponential(size=len(alpha))/alpha
  lg-=logsumexp(lg);return np.exp(lg),lg
 def step(state,scale):
  z,pi,lg,rng=state;pr=X*pi[:,y].T;pr/=pr.sum(1)[:,None]
  alloc=(rng.random(len(y))[:,None]>np.cumsum(pr,axis=1)[:,:-1]).sum(1)
  N=np.bincount(alloc*3+y,minlength=k*3).reshape(k,3);lp=base_lp(z,N);acc=0
  for _ in range(2):
   prop=z+scale*(L@rng.normal(size=2));new=base_lp(prop,N)
   if np.log(rng.random())<new-lp:z=prop;lp=new;acc+=1
  pp,ll=simplex(z);pi[0]=pp[0];lg[0]=ll[0]
  for j in range(1,k):pi[j],lg[j]=stable_dirichlet(20*pi[0]+N[j],rng)
  zz=(lg[:,:2]-lg[:,2:]).ravel()
  return [z,pi,lg,rng],pi.copy(),zz,acc
 states=[];chains=[];zchains=[];scales=[];acceptance=[]
 for ci in range(4):
  rng=np.random.default_rng(seed+ci*100003);z=mode+L@rng.normal(size=2)*.3;pp,ll=simplex(z);pi=np.tile(pp,(k,1));lg=np.tile(ll,(k,1));state=[z,pi,lg,rng];scale=2.38/math.sqrt(2);ac=0
  for it in range(2000):
   state,p,zz,aa=step(state,scale);ac+=aa
   if (it+1)%100==0:
    scale*=math.exp(.5*(ac/200-.30));scale=float(np.clip(scale,.05,5.));ac=0
  ps=[];zs=[];ac=0
  for it in range(4000):
   state,p,zz,aa=step(state,scale);ps.append(p);zs.append(zz);ac+=aa
  states.append(state);chains.append(np.asarray(ps));zchains.append(np.asarray(zs));scales.append(scale);acceptance.append(ac/8000)
 chain=np.asarray(chains);zc=np.asarray(zchains)
 def dg_fn():return diag_stat(np.concatenate([zc,chain.reshape(chain.shape[0],chain.shape[1],-1)],axis=2))
 dg=dg_fn();extension=False
 if not dg["passed"]:
  extension=True;pcs=[];zcs=[]
  for ci in range(4):
   state=states[ci];ps=[];zs=[];ac=0
   for it in range(4000):
    state,p,zz,aa=step(state,scales[ci]);ps.append(p);zs.append(zz);ac+=aa
   pcs.append(np.asarray(ps));zcs.append(np.asarray(zs));acceptance[ci]=(acceptance[ci]+ac/8000)/2
  chain=np.concatenate([chain,np.asarray(pcs)],axis=1);zc=np.concatenate([zc,np.asarray(zcs)],axis=1);dg=dg_fn()
 samples=chain.reshape(-1,k,3)
 dg.update(model=model,algorithm="partially_collapsed_Gibbs_exact_children_2D_base_MH",mode_success=bool(opt.success),proposal_hessian_eigenvalues=eig,mode=mode,acceptance=acceptance,scales=scales,draws=len(samples),fixed_extension=extension)
 return samples,dg
def label_at_H(g,cut):
 known=g.closed & g.close_t.lt(cut);by=known & g.close_t.le(g.entry_t+119)
 return np.where(by,np.where(g.round_pnl.to_numpy()>0,0,1),2).astype(int)
def audit_gradient():
 X=np.array([[.2,.8,0],[.3,0,.7],[.8,.2,0],[.7,0,.3],[.6,.4,0],[.4,0,.6]]);y=np.array([0,1,2,1,0,1]);z=np.array([.5,2.,.3,2.2,-.2,2.5]);v,g=lpgrad(z,X,y,True);num=[]
 for j in range(len(z)):
  e=np.zeros(len(z));e[j]=1e-6;num.append((lpgrad(z+e,X,y)-lpgrad(z-e,X,y))/(2e-6))
 err=float(np.max(np.abs(g-num)));assert err<1e-5
 return dict(max_abs_gradient_error=err,passed=True)
def main():
 start=time.monotonic();assert not (O/"INFERENCE_STARTED.json").exists()
 fs=json.loads((O/"FEATURE_AUDIT_SUMMARY.json").read_text());assert sha(O/"FEATURES.csv")==fs["feature_sha256"] and sha(O/"FREEZE.json")==fs["freeze_sha256"]
 sources={str(p):sha(p) for p in [ROUND,CLOCK,O/"FEATURES.csv",O/"FREEZE.json",Path(__file__)]};dump("INFERENCE_STARTED.json",dict(sources=sources,models=["constant","speed","joint"],account_runs=0,parameter_searches=0))
 dump("GRADIENT_AUDIT.json",audit_gradient())
 a=pd.read_csv(O/"FEATURES.csv");rr=pd.read_csv(ROUND,usecols=["sid","first_layer","entry_day","closed_day","closed","close_t","round_pnl","round_cost","round_return_on_cumulative_cost","holding_sessions","layers"])
 a=a.merge(rr,on=["sid","first_layer","entry_day"],how="left",validate="one_to_one");assert len(a)==1814 and a.closed.notna().all()
 days=pd.read_csv(CLOCK,index_col=0,parse_dates=True).index;end=days.get_loc(pd.Timestamp("2026-05-15"));a["potential_H"]=end-a.entry_t+1>=120
 a["y_H"]=label_at_H(a,end+1);a["y_final"]=np.where(a.closed,(a.round_pnl>0).astype(float),np.nan)
 a["signal_year"]=a.signal_day.str[:4].astype(int);a["score_known"]=False;a["unknown_reason"]=np.where(a.signal_year<2023,"FIRST_YEAR_NO_BACKFILL","NO_ELIGIBLE_MODEL")
 for model in ["constant","speed","joint"]:
  for suffix in ["W","L","U","ultimate_low","ultimate_high","W_q05","W_q95","upper_q05","upper_q95","train_group"]:a[model+"_"+suffix]=np.nan
 fitmeta=[];poisons=[];ident=pd.read_csv(O/"MONTHLY_IDENTIFIABILITY.csv");all_diagnostics=[]
 for no,row in enumerate(ident.to_dict("records")):
  month=row["month"];cut=int(row["cut"]);tr=a[(a.t>=cut-504)&(a.entry_t<=cut-120)].copy();te=a[a.signal_day.str.startswith(month)].copy();y=label_at_H(tr,cut);counts=np.bincount(y,minlength=3)
  # Scrub every label unavailable at the cutoff; late-after-H outcomes also cannot change H labels.
  poison=a.copy();unavailable=~(poison.closed & (poison.close_t<cut));late=poison.close_t>poison.entry_t+119
  poison.loc[unavailable|late,"round_pnl"]=999999999.
  pt=poison[(poison.t>=cut-504)&(poison.entry_t<=cut-120)];yp=label_at_H(pt,cut)
  assert np.array_equal(tr.index.to_numpy(),pt.index.to_numpy()) and np.array_equal(y,yp)
  for model in ["speed","joint"]:
   xx=Xmat(tr,model);z=logits(np.tile((counts+.5)/(len(tr)+1.5),(xx.shape[1],1))).ravel()
   assert lpgrad(z,xx,y,True)[0]==lpgrad(z,Xmat(pt,model),yp,True)[0]
   assert np.array_equal(lpgrad(z,xx,y,True)[1],lpgrad(z,Xmat(pt,model),yp,True)[1])
  poisons.append(dict(month=month,train_rows=len(tr),unavailable_poisoned=int(unavailable.sum()),late_H_poisoned=int(late.sum()),same_training_ids=True,same_H_labels=True,same_posterior_function=True))
  ok=len(tr)>=300 and tr.signal_day.nunique()>=60 and counts[0]>=50 and counts[1]>=50 and row["rank"]==3 and row["condition"]<=1e8
  meta=dict(month=month,cutoff=row["cutoff"],train_rows=len(tr),train_dates=tr.signal_day.nunique(),train_stocks=tr.sid.nunique(),W=int(counts[0]),L=int(counts[1]),U=int(counts[2]),test_rows=len(te),eligible=ok,models={})
  if not ok:
   a.loc[te.index,"unknown_reason"]="MINIMUM_SAMPLE_OR_IDENTIFICATION";fitmeta.append(meta);print("SKIP",month,len(tr),counts.tolist(),flush=True);continue
  outputs={};successful=True
  for mi,model in enumerate(["constant","speed","joint"]):
   X=Xmat(tr,model);samples,dg=run_posterior(X,y,model,20261106+no*1009+mi*313)
   dg.update(month=month);all_diagnostics.append(dg)
   mean=samples.mean(0);xp=Xmat(te,model);pred=xp@mean;trainpred=X@mean;edges=np.quantile(trainpred[:,0],[.2,.4,.6,.8])
   pick=samples[::max(1,len(samples)//2000)];drawpred=np.einsum("ik,skc->sic",xp,pick)
   qw=np.quantile(drawpred[:,:,0],[.05,.95],axis=0) if len(te) else np.empty((2,0))
   qu=np.quantile(drawpred[:,:,0]+drawpred[:,:,2],[.05,.95],axis=0) if len(te) else np.empty((2,0))
   outputs[model]=(pred,qw,qu,edges)
   meta["models"][model]=dict(endpoint_mean=mean,endpoint_q05=np.quantile(samples,.05,axis=0),endpoint_q95=np.quantile(samples,.95,axis=0),training_quintile_edges=edges,diagnostics_passed=bool(dg["passed"]))
   if model=="joint":
    contrast=samples[:,1,0]-samples[:,2,0]
    meta["joint_background_endpoint_contrast"]=dict(mean=contrast.mean(),q05=np.quantile(contrast,.05),q95=np.quantile(contrast,.95),posterior_positive_fraction=np.mean(contrast>0))
   if not dg["passed"]:successful=False
   print("FIT",month,model,"n",len(tr),"passed",dg["passed"],"Rhat",round(dg.get("max_rhat",1.),5),"ESS",round(dg.get("min_bulk_ess",len(samples)),1),"seconds",round(time.monotonic()-start,1),flush=True)
  meta["all_models_converged"]=successful
  if successful:
   a.loc[te.index,"score_known"]=True;a.loc[te.index,"unknown_reason"]=""
   for model,(pred,qw,qu,edges) in outputs.items():
    for j,cc in enumerate(["W","L","U"]):a.loc[te.index,model+"_"+cc]=pred[:,j]
    a.loc[te.index,model+"_ultimate_low"]=pred[:,0];a.loc[te.index,model+"_ultimate_high"]=pred[:,0]+pred[:,2]
    a.loc[te.index,model+"_W_q05"]=qw[0];a.loc[te.index,model+"_W_q95"]=qw[1]
    a.loc[te.index,model+"_upper_q05"]=qu[0];a.loc[te.index,model+"_upper_q95"]=qu[1]
    a.loc[te.index,model+"_train_group"]=np.searchsorted(edges,pred[:,0],side="right")+1
  else:a.loc[te.index,"unknown_reason"]="POSTERIOR_CONVERGENCE_UNKNOWN"
  fitmeta.append(meta);dump("MONTHLY_MODELS.partial.json",fitmeta);dump("POSTERIOR_DIAGNOSTICS.partial.json",all_diagnostics)
 a.to_csv(O/"ORIGINAL_MOBILE_FORWARD_PREDICTIONS.csv",index=False)
 dump("MONTHLY_MODELS.json",fitmeta);dump("POSTERIOR_DIAGNOSTICS.json",all_diagnostics);dump("FUTURE_LABEL_POISON_AUDIT.json",poisons)
 for p,h in sources.items():assert sha(p)==h
 summary=dict(status="ONE_FROZEN_FORWARD_INFERENCE_COMPLETE",births=len(a),predicted=int(a.score_known.sum()),first_prediction=a.loc[a.score_known,"signal_day"].min(),model_months=len(fitmeta),eligible_months=sum(z["eligible"] for z in fitmeta),converged_months=sum(z.get("all_models_converged",False) for z in fitmeta),prefix_checks=1814,future_poison_checks=len(poisons),account_runs=0,parameter_searches=0,candidate_reorders=0,seconds=time.monotonic()-start)
 dump("INFERENCE_SUMMARY.json",summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()

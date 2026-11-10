"""PVS-B1: one forward Gaussian-sum update, moment-matched each observation.
No trade/hold/exit thresholds. Model-internal weights are not market probabilities.
"""
import numpy as np,pandas as pd
RHO=2**(-1/5);PRIOR=np.array([19/21,1/21,1/21]);F=np.array([[1.,1.,0.],[0.,1.,0.],[0.,0.,RHO]]);H=np.array([1.,0.,1.]);I=np.eye(3)
COLS=['strength','drift','drift_sigma','drift_sd','temporary','temporary_sigma','level','normal_weight','persistent_weight','transient_weight','activity','sigma','innovation_z','cov_min_eigenvalue','init']
def update(m,P,y,sigma,a):
 pred=F@m;cov=F@P@F.T
 qs=np.array([[.01,1/21**2,.01],[a,a/5**2,.01],[.01,1/21**2,4*a]])*sigma**2
 means=[];covs=[];ll=[];zs=[]
 for q in qs:
  p=cov+np.diag(q);res=y-H@pred;s=float(H@p@H+sigma**2*.25);k=p@H/s
  mean=pred+k*res;A=I-np.outer(k,H);post=A@p@A.T+np.outer(k,k)*(.25*sigma**2)
  means.append(mean);covs.append(post);ll.append(-.5*(np.log(2*np.pi*s)+res*res/s));zs.append(res/np.sqrt(s))
 logw=np.log(PRIOR)+np.array(ll);w=np.exp(logw-logw.max());w/=w.sum();means=np.array(means);m=w@means
 P=sum(weight*(p+np.outer(x-m,x-m)) for weight,x,p in zip(w,means,covs));P=(P+P.T)/2
 return m,P,w,float(w@zs)
def run_valid(close,volume,joint=True):
 y=np.log(np.asarray(close,float)/float(close.iloc[0]));v=np.asarray(volume,float);r=np.r_[np.nan,np.diff(y)];n=len(y);out=np.full((n,len(COLS)),np.nan);m=P=None
 for t in range(64,n):
  sigma=max(float(np.sqrt(np.mean(r[t-63:t]**2))),1e-8);a=float(np.clip(v[t]/np.median(v[t-21:t]),.25,4)) if joint else 1.
  if m is None:
   m=np.array([y[t],0.,0.]);P=sigma**2*np.diag([1.,1/21**2,1.]);out[t,-1]=1.;continue
  m,P,w,z=update(m,P,y[t],sigma,a);sd=np.sqrt(max(P[1,1],0));eigen=float(np.linalg.eigvalsh(P).min())
  out[t]=[100*np.tanh(np.sqrt(21)*m[1]/sigma),m[1],m[1]/sigma,sd,m[2],m[2]/sigma,m[0],*w,a,sigma,z,eigen,0.]
 df=pd.DataFrame(out,index=close.index,columns=COLS);df['drift_21_pct']=100*np.expm1(21*df.drift);df['drift_z']=df.drift/df.drift_sd
 # Total model-implied next21 displacement includes temporary-state relaxation.
 df['total_21_log_forecast']=21*df.drift+(RHO**21-1)*df.temporary
 df['total_21_strength']=100*np.tanh(df.total_21_log_forecast/(np.sqrt(21)*df.sigma))
 return df

def strength_frame(f,joint=True):
 result=pd.DataFrame(np.nan,index=f.index,columns=COLS+['drift_21_pct','drift_z','total_21_log_forecast','total_21_strength'])
 for _,g in f.groupby('segment_id',sort=False):
  good=g.loc[g.valid_strength_observation]
  if len(good):result.loc[good.index]=run_valid(good.close,good.volume,joint)
 return result

"""One pre-specified marked observation-event tilt; no economic replay."""
from pathlib import Path
import ast, hashlib, json, sys
import numpy as np
import pandas as pd
from scipy.special import logsumexp
O=Path(__file__).resolve().parent; R=O.parent
D=R/'distribution_objective_feasibility_v1'
E=R/'missing_price_cohort_feasibility_v1/execution_v1'
HFILE=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
CUTS=pd.to_datetime(['2024-09-02','2024-10-08','2024-11-01','2024-12-02'])
EDGES=np.array([0,5,20,60,120,1000000]); PEN=np.array([4.,4.,4.,16.,16.]); H=120
BIN_EDGES=np.array([-np.inf,-1,0,1,3,np.inf]); CATS=['Y_le_minus1','Y_minus1_to_0','Y_0_to_1','Y_1_to_3','Y_gt_3','U','M','S']
TEMPLATE='ORIGINAL_2024_AB_PRICE_165_NET80_STRICT_UNKNOWN_V1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,(pd.Timestamp,)):return str(x)
 return x

def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def csv(n,x):
 assert not (O/n).exists(),n
 pd.DataFrame(x).to_csv(O/n,index=False)
def pq(n,x):
 assert not (O/n).exists(),n
 x.to_parquet(O/n,index=False)
def cal():
 x=pd.DatetimeIndex(np.load(HFILE,allow_pickle=False)['dates']);return x[(x>='2013-01-01')&(x<='2026-05-15')]
CAL=cal()
# Extract precisely the old design and binary optimizer; never invoke old prepare/fit/evaluate.
OLD=R/'closed_price_supervised_pilot_support_v1/run_pilot.py'
_tree=ast.parse(OLD.read_text());exec(compile(ast.Module(body=[n for n in _tree.body if isinstance(n,ast.FunctionDef) and n.name in ['sigmoid','scale','design','fit_logit']],type_ignores=[]),str(OLD),'exec'))

def load_sources():
 frames=[];actions=[];freezes=[];paths=[HFILE,OLD,O/'PROTOCOL.md',Path(__file__),D/'EXTENDED_ALL_COHORT_IDENTITIES.parquet']
 for cohort in ['2023','2024JanAug','old2024SepDec']:
  if cohort=='old2024SepDec':
   p=R/'closed_price_supervised_pilot_support_v1/ALL_ORIGINAL_PRICE_ROWS.parquet';x=pd.read_parquet(p);x=x[x.window_label.eq('2024')].copy();base=R/'independent_channel_joint_economic_v1/economic_2024'
   x['ordinary_known_at']=pd.to_datetime(x.label_known_at_proxy);x['ordinary_value']=x.net_pnl.where(x.ordinary)
   x['scenario_known_at']=pd.NaT;x['scenario_value']=np.nan;x['scenario_label_available']=False
  else:
   base=E/('economic_'+cohort);p=base/'PRICE_LABELS.csv';x=pd.read_csv(p,float_precision='round_trip')
   fp=D/('EXTENDED_'+cohort+'_PDC_FEATURES.parquet');paths.append(fp)
   f=pd.read_parquet(fp);x=x.merge(f[['round_id','P','D','C','root_known','feature_known']],on='round_id',validate='one_to_one')
   assert x.template_id.eq(TEMPLATE).all()
   x['ordinary']=x.ordinary_label_mature;x['ordinary_known_at']=pd.to_datetime(x.label_usable_proxy_at);x['ordinary_value']=x.label_net_cny
   x['scenario_known_at']=pd.to_datetime(x.financial_settlement_proxy_at);x['scenario_value']=x.financial_scenario_net_cny;x['scenario_label_available']=x.financial_settled_label_mature
   x['complete']=x.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND');x['eval_financial_known']=x.financial_reconciled_closed
  paths.append(p);x['cohort_id']=cohort;x['template_id']=TEMPLATE
  for c in ['signal_day','entry_day','exit_day','status_day']:x[c]=pd.to_datetime(x[c])
  x['t']=CAL.get_indexer(x.signal_day);assert x.t.ge(0).all();frames.append(x)
  ap=base/'joint/ACTIONS.csv';fp=base/'FROZEN_RESPONSIBILITIES.json';paths.extend([ap,fp])
  a=pd.read_csv(ap,float_precision='round_trip');a=a[a.round_id.isin(x.round_id)].copy();a['day']=pd.to_datetime(a.day);actions.append(a)
  u=pd.DataFrame(json.loads(fp.read_text()));u=u[u.round_id.isin(x.round_id)].copy();u['day']=pd.to_datetime(u.day);freezes.append(u)
 r=pd.concat(frames,ignore_index=True,sort=False);r['window']=r.window.astype(str);a=pd.concat(actions,ignore_index=True);u=pd.concat(freezes,ignore_index=True)
 ids=pd.read_parquet(D/'EXTENDED_ALL_COHORT_IDENTITIES.parquet');r=r.merge(ids[['round_id','root_cluster','normalized_decision_key']],on='round_id',validate='one_to_one')
 assert r.round_id.is_unique and r.normalized_decision_key.is_unique and u.round_id.is_unique
 return r,a,u,{str(p):sha(p) for p in paths}

def snapshot(r,a,u,cut):
 """Risk membership and endpoints are built from actual as-of action/freeze ledgers."""
 ct=CAL.get_loc(cut);prior=r[r.t.ge(ct-504)&r.t.lt(ct)].copy()
 ap=a[a.day.lt(cut)&a.round_id.isin(prior.round_id)].copy();up=u[u.day.lt(cut)&u.round_id.isin(prior.round_id)]
 buys=ap[ap.side.eq('buy_core')&ap.q.gt(0)].set_index('round_id').day
 sells=ap[ap.side.eq('sell_all')].set_index('round_id').day
 assert buys.index.is_unique and sells.index.is_unique
 ap['dq']=np.where(ap.side.str.startswith('buy'),ap.q,-ap.q);qty=ap.groupby('round_id').dq.sum()
 assert qty.reindex(sells.index).eq(0).all()
 assert qty.loc[~qty.index.isin(sells.index)].gt(0).all()
 obs=prior[prior.round_id.isin(buys.index)].copy();obs['entry_asof']=obs.round_id.map(buys)
 obs['exit_asof']=obs.round_id.map(sells);obs['freeze_asof']=obs.round_id.map(up.set_index('round_id').day)
 assert not (obs.exit_asof.notna()&obs.freeze_asof.notna()).any()
 obs['end_asof']=CAL[ct-1];obs['event']='S';obs['Y']=np.nan
 exited=obs.exit_asof.notna();unknown=obs.freeze_asof.notna()
 obs.loc[exited,'end_asof']=obs.loc[exited,'exit_asof'];obs.loc[exited,'event']='M'
 obs.loc[unknown,'end_asof']=obs.loc[unknown,'freeze_asof'];obs.loc[unknown,'event']='U'
 known=exited&obs.ordinary&obs.ordinary_known_at.lt(cut)
 assert obs.loc[known,'exit_day'].equals(obs.loc[known,'exit_asof'])
 assert (obs.loc[known,'ordinary_known_at']==obs.loc[known,'exit_asof']+pd.Timedelta(hours=15)).all()
 obs.loc[known,'event']='O';obs.loc[known,'Y']=obs.loc[known,'ordinary_value']/3000
 obs['age_end']=CAL.get_indexer(obs.end_asof)-CAL.get_indexer(obs.entry_asof)+1
 assert obs.age_end.ge(1).all() and obs.end_asof.lt(cut).all() and obs.loc[~known,'Y'].isna().all()
 obs['event_g']=np.searchsorted(EDGES[1:],obs.age_end.to_numpy(),side='left')
 for g in range(5):obs['n'+str(g)]=np.maximum(np.minimum(obs.age_end.to_numpy(),EDGES[g+1])-EDGES[g],0)
 assert (obs[[f'n{g}' for g in range(5)]].sum(axis=1)==obs.age_end).all()
 safe=['round_id','cohort_id','sid','signal_day','root_cluster','normalized_decision_key','P','D','C','feature_known','entry_asof','exit_asof','freeze_asof','end_asof','age_end','event','event_g','Y']+[f'n{g}' for g in range(5)]
 obs=obs[safe].sort_values('round_id').reset_index(drop=True);obs['cut']=cut
 cov=dict(cut=str(cut.date()),registered=len(prior),confirmed_bought=len(obs),feature_known=int(obs.feature_known.sum()),feature_unknown=int((~obs.feature_known).sum()),not_bought_before_cut=len(prior)-len(obs),**{f'all_{e}':int(obs.event.eq(e).sum()) for e in ['O','U','M','S']})
 return obs,cov

def base_hazards(obs):
 n=obs[[f'n{g}' for g in range(5)]].to_numpy(float);bs=[]
 for g in range(5):
  N=float(n[:,g].sum());assert N>0
  e=obs[obs.event_g.eq(g)&~obs.event.eq('S')];ys=e.loc[e.event.eq('O'),'Y'].to_numpy(float)
  ys,cnt=np.unique(ys,return_counts=True);q=cnt/N;qU=float(e.event.eq('U').sum()/N);qM=float(e.event.eq('M').sum()/N);q0=1-len(e)/N
  assert q0>=0 and abs(q0+qU+qM+q.sum()-1)<1e-12
  bs.append(dict(N=N,Y=ys,q=q,q0=q0,qU=qU,qM=qM))
 return bs,n

def moments(eta,b,detail=False):
 ys=b['Y'];base=b['q0']+b['qU']+b['qM'];v=np.r_[0.,ys]
 logw=np.r_[np.log(base) if base>0 else -np.inf,np.log(b['q'])]
 scores=eta[:,None]*v[None,:]+logw[None,:];L=logsumexp(scores,axis=1);prob=np.exp(scores-L[:,None]);mu=prob@v
 var=np.sum(prob*(v[None,:]-mu[:,None])**2,axis=1)
 if detail:return L,mu,var,prob[:,1:]
 return L,mu,var

def objective(beta,Z,n,obs,bs,hess=True):
 eta=Z@beta;v=obs.Y.fillna(0).to_numpy(float);f=.5*np.dot(PEN*beta,beta)-np.dot(eta,v);gr=PEN*beta-Z.T@v;hh=np.diag(PEN)
 for g,b in enumerate(bs):
  L,mu,var=moments(eta,b);f+=np.dot(n[:,g],L);gr+=Z.T@(n[:,g]*mu)
  if hess:hh+=Z.T@((n[:,g]*var)[:,None]*Z)
 assert np.isfinite(f) and np.isfinite(gr).all() and np.isfinite(hh).all()
 return f,gr,hh

def fit_marked(Z,n,obs,bs):
 beta=np.zeros(5);hist=[]
 for it in range(100):
  f,g,h=objective(beta,Z,n,obs,bs);hist.append(dict(iteration=it,objective=f,gradient_max=max(abs(g)),min_hessian_eigenvalue=np.linalg.eigvalsh(h)[0]))
  if max(abs(g))<1e-6:break
  step=np.linalg.solve(h,g);alpha=1.
  while alpha>2**-40:
   fn,_,_=objective(beta-alpha*step,Z,n,obs,bs,hess=False)
   if fn<=f+1e-10:break
   alpha*=.5
  if alpha<=2**-40:raise ValueError('MARKED_LINE_SEARCH_FAILURE')
  beta-=alpha*step
 f,g,h=objective(beta,Z,n,obs,bs)
 if max(abs(g))>=1e-6:raise ValueError('MARKED_GRADIENT_NOT_CONVERGED')
 return beta,dict(iterations=it+1,objective=f,gradient_max=max(abs(g)),hessian_eigenvalues=np.linalg.eigvalsh(h),trace=hist)

def forecast(Z,beta,bs):
 eta=Z@beta;surv=np.ones(len(Z));prob=np.zeros((len(Z),8));amount=np.zeros(len(Z));tailmax=np.zeros(len(Z));tailtop5=np.zeros(len(Z));max_etaY=0.;max_atom_mass=np.zeros(len(Z));min_atom_mass=np.zeros(len(Z));all_y=np.concatenate([b['Y'] for b in bs]);ymax=float(all_y.max());ymin=float(all_y.min())
 for age in range(1,H+1):
  g=int(np.searchsorted(EDGES[1:],age,side='left'));b=bs[g];L,_,_,p=moments(eta,b,detail=True)
  h0=np.exp(np.log(b['q0'])-L) if b['q0']>0 else np.zeros(len(Z));hu=np.exp(np.log(b['qU'])-L) if b['qU']>0 else np.zeros(len(Z));hm=np.exp(np.log(b['qM'])-L) if b['qM']>0 else np.zeros(len(Z))
  cat=np.searchsorted(BIN_EDGES[1:],b['Y'],side='left')
  for k in range(5):prob[:,k]+=surv*p[:,cat==k].sum(axis=1)
  prob[:,5]+=surv*hu;prob[:,6]+=surv*hm;amount+=surv*(p@b['Y'])
  if len(b['Y']):
   cp=p/np.maximum(p.sum(axis=1)[:,None],np.finfo(float).tiny)
   tailmax=np.maximum(tailmax,cp.max(axis=1));tailtop5=np.maximum(tailtop5,np.sort(cp,axis=1)[:,-5:].sum(axis=1));max_etaY=max(max_etaY,float(np.max(abs(eta[:,None]*b['Y'][None,:]))))
  max_atom_mass+=surv*p[:,b['Y']==ymax].sum(axis=1);min_atom_mass+=surv*p[:,b['Y']==ymin].sum(axis=1)
  surv*=h0
 prob[:,7]=surv;mass=prob[:,:5].sum(axis=1);Q=np.divide(amount,mass,out=np.full(len(Z),np.nan),where=mass>0)
 assert np.max(abs(prob.sum(axis=1)-1))<1e-10 and np.isfinite(prob).all()
 return dict(Q=Q,ordinary_mass=mass,amount_submoment=amount,prob=prob,eta=eta,top1_age_conditional_atom_mass=tailmax,top5_age_conditional_atom_mass=tailtop5,max_abs_etaY=max_etaY,global_maxY_conditional_mass=max_atom_mass/np.maximum(mass,np.finfo(float).tiny),global_minY_conditional_mass=min_atom_mass/np.maximum(mass,np.finfo(float).tiny))

def influence_diagnostic(beta,Z,n,obs,bs):
 """Fixed q/scaler local data-loss influence; does NOT remove/rebuild empirical atoms."""
 eta=Z@beta;res=-obs.Y.fillna(0).to_numpy(float);info=np.zeros(len(Z))
 for g,b in enumerate(bs):
  _,mu,var=moments(eta,b);res+=n[:,g]*mu;info+=n[:,g]*var*np.sum(Z*Z,axis=1)
 gi=res[:,None]*Z;_,_,hh=objective(beta,Z,n,obs,bs);ix=int(np.nanargmax(obs.Y.to_numpy(float)));delta=np.linalg.solve(hh,gi[ix]);gradnorm=np.linalg.norm(gi,axis=1)
 fc=forecast(Z,beta,bs);clusters={}
 for col in ['sid','root_cluster','signal_day']:
  rows=pd.DataFrame({'cluster':obs[col].astype(str).to_numpy(),'gradient_norm':gradnorm,'information_trace':info})
  agg=rows.groupby('cluster')[['gradient_norm','information_trace']].sum();clusters[col]=dict(clusters=len(agg),gradient_norm_top1_share=agg.gradient_norm.nlargest(1).sum()/agg.gradient_norm.sum(),gradient_norm_top5_share=agg.gradient_norm.nlargest(5).sum()/agg.gradient_norm.sum(),information_trace_top1_share=agg.information_trace.nlargest(1).sum()/agg.information_trace.sum(),information_trace_top5_share=agg.information_trace.nlargest(5).sum()/agg.information_trace.sum())
 def qs(v):return dict(zip(['min','p50','p90','p99','max'],np.quantile(v,[0,.5,.9,.99,1]).tolist()))
 return dict(maxY_round_id=obs.iloc[ix].round_id,maxY=float(obs.iloc[ix].Y),maxY_data_gradient=gi[ix],maxY_fixed_q_scaler_delete_direction_delta=delta,delta_L2=float(np.linalg.norm(delta)),delta_over_beta_L2=float(np.linalg.norm(delta)/max(np.linalg.norm(beta),1e-15)),limitation='Local beta_delete approx beta+H^-1 g_i with q/scaler fixed. Does not account for empirical atom, N or scaler changes. Not complete leave-one-out robustness.',clusters=clusters,train_top1_age_atom_mass=qs(fc['top1_age_conditional_atom_mass']),train_top5_age_atom_mass=qs(fc['top5_age_conditional_atom_mass']),train_global_maxY_mass=qs(fc['global_maxY_conditional_mass']),train_global_minY_mass=qs(fc['global_minY_conditional_mass']),train_fraction_global_maxY_mass_ge95pct=float(np.mean(fc['global_maxY_conditional_mass']>=.95)))

def selftest():
 rng=np.random.default_rng(31017);Z=rng.normal(size=(17,5));n=rng.integers(1,12,size=(17,5)).astype(float)
 obs=pd.DataFrame({'Y':np.r_[[-2.,-.2,0,1.,28.577407931152464],np.full(12,np.nan)]})
 bs=[dict(N=100,Y=np.array([-2.,-.2,0.,1.,28.577407931152464]),q=np.array([.01,.02,.01,.03,.01]),q0=.89,qU=.02,qM=.01) for _ in range(5)]
 b=np.array([.008,-.004,.003,-.002,.001]);f,g,h=objective(b,Z,n,obs,bs);eps=1e-6;fd=[];hd=[]
 for k in range(5):
  e=np.eye(5)[k]*eps;fp,gp,_=objective(b+e,Z,n,obs,bs);fm,gm,_=objective(b-e,Z,n,obs,bs);fd.append((fp-fm)/(2*eps));hd.append((gp-gm)/(2*eps))
 err=float(np.max(abs(g-np.array(fd))));herr=float(np.max(abs(h-np.array(hd).T)));assert err<1e-5 and herr<1e-3
 stress=[]
 for eta in [-1e6,-1000.,0.,1000.,1e6]:
  L,mu,var,p=moments(np.array([eta]),bs[0],True);assert np.isfinite(L).all() and np.isfinite(mu).all() and np.isfinite(var).all();stress.append(dict(eta=eta,logZ=L[0],mu=mu[0],variance=var[0],ordinary_mass=p.sum()))
 zero=dict(N=10,Y=np.array([]),q=np.array([]),q0=.8,qU=.1,qM=.1);L,mu,var=moments(np.array([1e6]),zero);assert L[0]==mu[0]==var[0]==0
 fc=forecast(Z,np.zeros(5),bs);p=fc['prob'][0];assert np.max(abs(fc['prob']-p))<1e-14
 _,_,_,q=moments(np.array([0.]),bs[0],True);assert np.allclose(q[0],bs[0]['q'],atol=1e-15,rtol=0)
 stress_forecast=forecast(np.array([[1e6,0,0,0,0],[-1e6,0,0,0,0]]),np.array([1.,0,0,0,0]),bs);assert np.max(abs(stress_forecast['prob'].sum(axis=1)-1))<1e-10
 onlyatom=[dict(N=1,Y=np.array([1.]),q=np.array([1.]),q0=0.,qU=0.,qM=0.) for _ in range(5)];zero_base_forecast=forecast(np.array([[-1e6,0,0,0,0]]),np.array([1.,0,0,0,0]),onlyatom);assert zero_base_forecast['prob'][0,2]==1
 return dict(gradient_max_error=err,hessian_max_error=herr,min_hessian_eigenvalue=np.linalg.eigvalsh(h)[0],stress=stress,beta0_reproduces_q=True,zero_ordinary_atoms_supported=True,H_mass_error=float(np.max(abs(fc['prob'].sum(axis=1)-1))),full_forecast_extreme_eta_pass=True,zero_base_full_forecast_pass=True,real_data_fits=0)

def prepare():
 assert not (O/'PREPARE_SEAL.json').exists()
 r,a,u,hashes=load_sources();allobs=[];coverage=[];support=[];poison=[];ages=[];tops=[]
 for cut in CUTS:
  ob,cov=snapshot(r,a,u,cut);allobs.append(ob);coverage.append(cov)
  # Physical prefix and future poison must produce exactly equal model input projection.
  pref,_=snapshot(r[r.signal_day.lt(cut)],a[a.day.lt(cut)],u[u.day.lt(cut)],cut);pd.testing.assert_frame_equal(ob,pref)
  rp=r.copy();future=~(rp.ordinary&rp.ordinary_known_at.lt(cut));rp.loc[future,'ordinary_value']=1e100;rp.loc[future,'ordinary']=~rp.loc[future,'ordinary'];rp.loc[rp.ordinary_known_at.ge(cut),'ordinary_known_at']=pd.Timestamp('2035-01-04')
  for col in ['status','execution_status','failure_phase','financial_reason','financial_coverage_reason']:
   if col in rp:rp[col]='POISON_FINAL_STATUS'
  for col in ['entered','complete','rights_touched','financial_covered','eval_financial_known']:rp[col]=~rp[col].fillna(False).astype(bool)
  rp.loc[rp.entry_day.ge(cut),'entry_day']=pd.Timestamp('2035-01-01');rp.loc[rp.exit_day.ge(cut),'exit_day']=pd.Timestamp('2035-01-02');rp.loc[rp.status_day.ge(cut),'status_day']=pd.Timestamp('2035-01-03')
  ap=a.copy();ap['q']=ap.q.astype(float);ap.loc[ap.day.ge(cut),'q']=1e50;ap.loc[ap.day.ge(cut),'side']='sell_all';up=u.copy();up.loc[up.day.ge(cut),'reason']='FUTURE_POISON'
  pois,_=snapshot(rp,ap,up,cut);pd.testing.assert_frame_equal(ob,pois);poison.append(dict(cut=str(cut.date()),physical_prefix_equal=True,future_amount_status_flags_actions_equal=True))
  tr=ob[ob.feature_known].copy();mat=tr[tr.event.eq('O')];X,sc=design(mat);T,_=design(tr,sc);Z=T[:,1:];bs,n=base_hazards(tr)
  rec=dict(cut=str(cut.date()),risk_n=len(tr),ordinary_n=len(mat),W=int(mat.Y.gt(0).sum()),L=int(mat.Y.le(0).sum()),dates=mat.signal_day.nunique(),stocks=mat.sid.nunique(),roots=mat.root_cluster.nunique(),rank=int(np.linalg.matrix_rank(X)),condition=float(np.linalg.cond(X)),risk_rank=int(np.linalg.matrix_rank(Z)),risk_condition=float(np.linalg.cond(Z)),Y_min=mat.Y.min(),Y_max=mat.Y.max(),tail_n=int(mat.Y.gt(3).sum()),scaling=[s.tolist() for s in sc])
  rec['support_ok']=bool(rec['ordinary_n']>=300 and rec['W']>=50 and rec['L']>=50 and rec['dates']>=60 and rec['stocks']>=100 and rec['roots']>=200 and rec['rank']==6 and rec['condition']<1e6 and rec['risk_rank']==5 and rec['risk_condition']<1e6)
  support.append(rec)
  for g,b in enumerate(bs):
   e=tr[tr.event_g.eq(g)&~tr.event.eq('S')];tail=e[e.event.eq('O')&e.Y.gt(3)]
   ages.append(dict(cut=str(cut.date()),age_group=g,N=b['N'],ordinary=int(e.event.eq('O').sum()),U=int(e.event.eq('U').sum()),M=int(e.event.eq('M').sum()),q0=b['q0'],qU=b['qU'],qM=b['qM'],tail_n=len(tail),tail_sids=tail.sid.nunique(),tail_dates=tail.signal_day.nunique()))
  tail=mat[mat.Y.gt(3)].sort_values('Y',ascending=False);v=tail.Y
  tops.append(dict(cut=str(cut.date()),tail_n=len(tail),tail_amount_CNY=v.sum()*3000,top1_fraction=v.head(1).sum()/v.sum(),top5_fraction=v.head(5).sum()/v.sum(),tail_stocks=tail.sid.nunique(),tail_dates=tail.signal_day.nunique(),tail_roots=tail.root_cluster.nunique()))
 assert all(sha(p)==h for p,h in hashes.items())
 pq('ALL_ROWS.parquet',r);pq('ASOF_OBSERVATIONS.parquet',pd.concat(allobs,ignore_index=True));csv('TRAIN_COVERAGE.csv',coverage);csv('AGE_SUPPORT.csv',ages);csv('TAIL_SUPPORT.csv',tops)
 dump('TRAIN_SUPPORT.json',support);dump('SYNTHETIC_QA.json',selftest());dump('PREFIX_POISON_QA.json',poison);dump('INPUT_HASHES.json',hashes)
 dump('PREPARE_QA.json',dict(status='PREPARED_NOT_FITTED',cuts=len(CUTS),all_support_pass=all(x['support_ok'] for x in support),no_final_outcome_risk_filter=True,mature_ordinary_scaler_shared=True,source_unchanged=True,model_fits=0,economic_runs=0))
 names=['ALL_ROWS.parquet','ASOF_OBSERVATIONS.parquet','TRAIN_SUPPORT.json','SYNTHETIC_QA.json','PREFIX_POISON_QA.json','INPUT_HASHES.json','PROTOCOL.md','run_pilot.py']
 dump('PREPARE_SEAL.json',{n:sha(O/n) for n in names});print(json.dumps(clean(support),indent=2),flush=True)

def fit():
 seal=json.loads((O/'PREPARE_SEAL.json').read_text());assert all(sha(O/n)==h for n,h in seal.items())
 review=json.loads((O/'PRE_FIT_INDEPENDENT_REVIEW.json').read_text());assert review['status']=='PASS' and review['code_sha256']==sha(__file__) and review['protocol_sha256']==sha(O/'PROTOCOL.md')
 assert not (O/'FIT_STARTED.json').exists()
 hashes=json.loads((O/'INPUT_HASHES.json').read_text());assert all(sha(p)==h for p,h in hashes.items())
 dump('FIT_STARTED.json',dict(utc=str(pd.Timestamp.now(tz='UTC')),code_sha256=sha(__file__),protocol_sha256=sha(O/'PROTOCOL.md'),candidate_count=1,parameter_scan=False))
 obs=pd.read_parquet(O/'ASOF_OBSERVATIONS.parquet');r=pd.read_parquet(O/'ALL_ROWS.parquet');pred=r[r.cohort_id.eq('old2024SepDec')][['round_id','sid','signal_day','P','D','C','feature_known','root_cluster']].copy()
 models=[];pieces=[];support=json.loads((O/'TRAIN_SUPPORT.json').read_text())
 for cut,sp in zip(CUTS,support):
  tr=obs[obs.cut.eq(cut)&obs.feature_known].copy();mat=tr[tr.event.eq('O')];X,sc=design(mat);T,_=design(tr,sc);Z=T[:,1:];bs,n=base_hazards(tr)
  p=pred[pred.signal_day.dt.to_period('M')==cut.to_period('M')].copy();p['cut']=cut;p['p0']=mat.Y.gt(0).mean();known=p.feature_known
  for k in ['Q','Q0','p_pvr','p_binary','ordinary_mass','amount_submoment','eta','top1_age_conditional_atom_mass','top5_age_conditional_atom_mass']+['F_'+x for x in CATS]:p[k]=np.nan
  model=dict(cut=str(cut.date()),support=sp,scaling=sc,baselines=bs);reason='SUPPORT_UNKNOWN'
  if sp['support_ok']:
   try:
    bm,qa=fit_marked(Z,n,tr,bs);y=mat.Y.gt(0).to_numpy(float);bi,qi=fit_logit(X,y,np.array([0.,4,4,4,16,16]));bp,qp=fit_logit(X[:,:2],y,np.array([0.,4]))
    V,_=design(p.loc[known],sc);fc=forecast(V[:,1:],bm,bs);f0=forecast(np.zeros((1,5)),np.zeros(5),bs)
    for k in ['Q','ordinary_mass','amount_submoment','eta','top1_age_conditional_atom_mass','top5_age_conditional_atom_mass']:p.loc[known,k]=fc[k]
    p['Q0']=f0['Q'][0]
    for j,k in enumerate(CATS):p.loc[known,'F_'+k]=fc['prob'][:,j]
    p.loc[known,'p_pvr']=sigmoid(V[:,:2]@bp);p.loc[known,'p_binary']=sigmoid(V@bi)
    model.update(influence=influence_diagnostic(bm,Z,n,tr,bs),marked_beta=bm,marked_QA=qa,binary_beta=bi,binary_QA=qi,pvr_beta=bp,pvr_QA=qp,beta0_forecast=f0,max_abs_etaY_validation=fc['max_abs_etaY'],max_abs_etaY_training=max(float(np.max(abs((Z@bm)[:,None]*b['Y'][None,:]))) if len(b['Y']) else 0 for b in bs));reason='KNOWN'
   except (ValueError,np.linalg.LinAlgError,FloatingPointError) as ex:model['failure']=str(ex);reason='MODEL_FAILURE_'+str(ex)
  p['model_reason']=reason;p['select_original']=True;p['select_beta0']=True;p['select_marked']=p.Q.isna()|p.Q.ge(p.Q0);p['select_pvr']=p.p_pvr.isna()|p.p_pvr.ge(p.p0);p['select_binary']=p.p_binary.isna()|p.p_binary.ge(p.p0)
  pieces.append(p);models.append(model);print('MONTH',str(cut.date()),reason,flush=True)
 out=pd.concat(pieces,ignore_index=True);assert len(out)==len(pred) and out.round_id.is_unique
 pq('PREDICTIONS.parquet',out);dump('MONTHLY_MODELS.json',models);dump('PREDICTION_SEAL.json',dict(predictions_sha256=sha(O/'PREDICTIONS.parquet'),models_sha256=sha(O/'MONTHLY_MODELS.json'),all_predictions_saved_before_outcome_reports=True,code_sha256=sha(__file__),protocol_sha256=sha(O/'PROTOCOL.md')))
 assert all(sha(p)==h for p,h in hashes.items())

def outcome(g):
 v=g.net_pnl;w=v[v>0];l=v[v<0];t3=g[v>9000];t30=g[g.net_return_on_buy_cash>=.3]
 return dict(n=len(g),W=len(w),L=len(l),Z=int(v.eq(0).sum()),winrate=float(v.gt(0).mean()) if len(g) else None,mean_win=w.mean(),mean_loss=l.mean(),payoff=w.mean()/abs(l.mean()) if len(w) and len(l) else None,profit_factor=w.sum()/abs(l.sum()) if len(l) else None,old_static_subset_net_CNY=v.sum(),tail3_n=len(t3),tail3_net_CNY=t3.net_pnl.sum(),tail30_n=len(t30),tail30_net_CNY=t30.net_pnl.sum(),stocks=g.sid.nunique(),roots=g.root_cluster.nunique(),signal_dates=g.signal_day.nunique())

def evaluate():
 seal=json.loads((O/'PREDICTION_SEAL.json').read_text());assert seal['predictions_sha256']==sha(O/'PREDICTIONS.parquet') and seal['models_sha256']==sha(O/'MONTHLY_MODELS.json')
 p=pd.read_parquet(O/'PREDICTIONS.parquet');r=pd.read_parquet(O/'ALL_ROWS.parquet');extra=[c for c in r if c not in p or c=='round_id'];x=p.merge(r[extra],on='round_id',validate='one_to_one');x['month']=x.signal_day.dt.to_period('M').astype(str)
 rows=[];coverage=[];tails=[];lossdates=[]
 for key,g in [('ALL',x)]+list(x.groupby('month')):
  for arm in ['original','beta0','pvr','binary','marked']:
   take=g['select_'+arm];s=g[take];cov=dict(month=key,arm=arm,births=len(g),selected_births=len(s),entered=int(g.entered.sum()),selected_entered=int(s.entered.sum()),known_score=int(g.Q.notna().sum()),unknown_score=int(g.Q.isna().sum()),selected_unclosed=int((s.entered&~s.complete).sum()),selected_closed_mark_unavailable=int((s.entered&s.complete&~s.ordinary).sum()),selected_entry_unknown=int((~s.entered&s.status.str.contains('UNKNOWN')).sum()),selected_Q0=int(s.status.eq('PRECHECK_Q0_NO_SUBMIT').sum()),selected_feature_unknown=int((~s.feature_known).sum()),mean_pred_ordinary_mass=s.ordinary_mass.mean(),mean_pred_U=s.F_U.mean(),mean_pred_M=s.F_M.mean(),mean_pred_S=s.F_S.mean());coverage.append(cov)
   for scope,mask in [('STRICT_ORDINARY',g.ordinary),('NONORDINARY_FINANCIAL_KNOWN_FINAL_ONLY',~g.ordinary&g.eval_financial_known)]:
    base=g[g.entered&mask];z=g[take&g.entered&mask];v=outcome(z);rows.append(dict(month=key,arm=arm,scope=scope,**v))
    tt=outcome(base);tails.append(dict(month=key,arm=arm,scope=scope,tail3_count_retention=v['tail3_n']/tt['tail3_n'] if tt['tail3_n'] else None,tail3_amount_retention=v['tail3_net_CNY']/tt['tail3_net_CNY'] if tt['tail3_net_CNY'] else None,tail30_count_retention=v['tail30_n']/tt['tail30_n'] if tt['tail30_n'] else None,tail30_amount_retention=v['tail30_net_CNY']/tt['tail30_net_CNY'] if tt['tail30_net_CNY'] else None))
  if key!='ALL':
   for day,q in g[g.ordinary&~g.select_marked].groupby('signal_day'):lossdates.append(dict(month=key,day=str(day.date()),**outcome(q)))
 csv('OUTCOMES.csv',rows);csv('COVERAGE.csv',coverage);csv('TAIL_RETENTION.csv',tails);csv('MARKED_REJECTED_BY_DATE.csv',lossdates)
 pq('PREDICTIONS_WITH_FINAL_DIAGNOSTICS.parquet',x)
 # H-state calibration is measured from saved true action/freeze endpoints; no force exit.
 rr,aa,uu,hashes=load_sources()
 buys=aa[aa.side.eq('buy_core')].set_index('round_id').day;sells=aa[aa.side.eq('sell_all')].set_index('round_id').day;fr=uu.set_index('round_id').day
 hrows=[];admin_H=0
 for _,z in x.iterrows():
  if z.round_id not in buys:continue
  entry=buys[z.round_id];et=CAL.get_indexer([entry])[0];hday=CAL[et+H-1];end=sells.get(z.round_id,pd.NaT);uday=fr.get(z.round_id,pd.NaT);cat='S'
  source_end=end if pd.notna(end) else (uday if pd.notna(uday) else pd.to_datetime(z.last_known_mark_day));assert hday<=CAL[-1]
  if pd.isna(source_end) or source_end<hday:
   if pd.isna(end) and pd.isna(uday):admin_H+=1;continue
  if pd.notna(uday) and uday<=hday:cat='U'
  elif pd.notna(end) and end<=hday:
   if z.ordinary and z.ordinary_known_at<=hday+pd.Timedelta(hours=15):cat=CATS[np.searchsorted(BIN_EDGES[1:],z.net_pnl/3000,side='left')]
   else:cat='M'
  hrows.append(dict(round_id=z.round_id,month=z.month,H_day=hday,observed_H_category=cat,feature_known=z.feature_known))
 dump('H120_OBSERVABILITY_QA.json',dict(H=H,original_entered=int(x.entered.sum()),observed_H_rows=len(hrows),administrative_before_H=admin_H,calendar_end=str(CAL[-1]),nonterminal_S_requires_observed_source_through_H=True));assert len(hrows)+admin_H==int(x.entered.sum())
 hdf=pd.DataFrame(hrows);hdf=hdf.merge(p,on=['round_id','feature_known'],validate='one_to_one');models=json.loads((O/'MONTHLY_MODELS.json').read_text());qs=[]
 for month,g in [('ALL',hdf)]+list(hdf.groupby('month')):
  for arm in ['beta0','marked']:
   known=g[g.Q.notna()];observed=np.array([CATS.index(v) for v in known.observed_H_category]);probs=[]
   for _,v in known.iterrows():
    if arm=='marked':probs.append([v['F_'+c] for c in CATS])
    else:probs.append(next(m['beta0_forecast']['prob'][0] for m in models if pd.Timestamp(m['cut'])==v.cut))
   pp=np.array(probs);yy=np.eye(8)[observed]
   qs.append(dict(month=month,arm=arm,n=len(known),Brier=float(np.mean(np.sum((pp-yy)**2,axis=1))) if len(known) else None,logloss_probability_floor_1e12=float(np.mean(-np.log(np.maximum(pp[np.arange(len(pp)),observed],1e-12)))) if len(known) else None,zero_predicted_observed_category=int((pp[np.arange(len(pp)),observed]==0).sum()) if len(known) else 0,**{f'actual_{c}':float(yy[:,j].mean()) if len(known) else None for j,c in enumerate(CATS)},**{f'pred_{c}':float(pp[:,j].mean()) if len(known) else None for j,c in enumerate(CATS)}))
 csv('H120_CALIBRATION.csv',qs);pq('H120_OBSERVED_STATES.parquet',hdf)
 dump('RESULT_SUMMARY.json',dict(outcomes=rows,coverage=coverage,tails=tails,H120_quality=qs,candidate_count=1,parameter_scans=0,economic_runs=0,account_runs=0,confidence_intervals=False))
 assert all(sha(p)==h for p,h in hashes.items())
 print(pd.DataFrame(rows).query("month=='ALL' and scope=='STRICT_ORDINARY'").to_string(index=False),flush=True)

if __name__=='__main__':
 {'prepare':prepare,'selftest':lambda:print(json.dumps(clean(selftest()),indent=2)),'fit':fit,'evaluate':evaluate}[sys.argv[1]]()

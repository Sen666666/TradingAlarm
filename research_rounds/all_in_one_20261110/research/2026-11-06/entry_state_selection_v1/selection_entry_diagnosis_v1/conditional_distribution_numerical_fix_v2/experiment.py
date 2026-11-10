from pathlib import Path
import json,sys,hashlib,time
import numpy as np,pandas as pd
from types import SimpleNamespace
def logsumexp(a,axis=1):
 m=np.max(a,axis=axis,keepdims=True)
 return np.squeeze(m,axis=axis)+np.log(np.exp(a-m).sum(axis=axis))
def spearmanr(a,b):
 x=pd.Series(np.asarray(a)).rank(method='average');y=pd.Series(np.asarray(b)).rank(method='average')
 return SimpleNamespace(statistic=float(x.corr(y))if x.nunique()>1 and y.nunique()>1 else np.nan)
class tdist:
 @staticmethod
 def ppf(prob,df):
  assert prob==.975 and df>=1
  tab=[0,12.706205,4.302653,3.182447,2.776446,2.570582,2.446912,2.364625,2.306004,2.262157,2.228139,2.200985,2.178813,2.160369,2.144787,2.131450,2.119906,2.109816,2.100922,2.093025,2.085963,2.079614,2.073874,2.068658,2.063899,2.059539,2.055529,2.051831,2.048407,2.045230,2.042273]
  return tab[min(int(df),30)]
O=Path(__file__).resolve().parent
R=O.parents[1]; B=R/'selection_entry_diagnosis_v1'
DATA=R/'volume_return_kernel_v1/ALL_CANDIDATES_WITH_LABELS.parquet'
CE=B/'cp1_signal_mechanism_v1/cp_timing_quality_v1/candidate_test/CANDIDATE_CE.parquet'
MARKET=B/'MARKET_FIXED1709_WARM.csv'
MAN=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CAL=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
FEATURES=['pvr_relative','risk_scale','CE']
LABELS=['C','F','U']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.item() if isinstance(a,np.generic) else str(a)))
def calendar():
 h=np.load(CAL,allow_pickle=False); d=pd.DatetimeIndex(h['dates'])
 return d[(d>='2022-01-01')&(d<='2026-05-15')]
def months(cal):
 return [(str(g.iloc[0].to_period('M')),int(cal.get_loc(g.iloc[0]))) for _,g in pd.Series(cal,index=cal).groupby(cal.to_period('M')) if g.iloc[0]>=pd.Timestamp('2023-01-01')]
def weights(a):
 # Each date total equal; each sector/date equal.
 ns=a.groupby('day').sector.transform('nunique').to_numpy(float)
 ni=a.groupby(['day','sector']).sid.transform('size').to_numpy(float)
 w=1/(ns*ni)
 return w/w.sum()*len(a)
def train_rows(c,cut):
 return c[c.t.ge(cut-504)&c.t.add(60).lt(cut)&c.feature_known&c.label60_known&c.state.isin(LABELS)].copy()
def prep():
 assert not (O/'PREPARED.parquet').exists()
 start=time.monotonic(); src={str(p):sha(p) for p in [DATA,CE,MARKET,MAN,CAL,Path(__file__),O/'FREEZE.json']}
 dump('INPUT_FREEZE.json',src)
 c=pd.read_parquet(DATA);assert len(c)==53121 and c.account.eq('PVR').all()
 ce=pd.read_parquet(CE,columns=['account','sid','day','CE','floor','CE_known']);ce=ce[ce.account.eq('PVR')]
 c=c.merge(ce[['sid','day','CE','CE_known','floor']].rename(columns={'floor':'CE_floor'}),on=['sid','day'],validate='one_to_one')
 assert np.allclose(pd.to_numeric(c.floor),pd.to_numeric(c.CE_floor),rtol=0,atol=1e-8)
 c['pvr_relative']=c.groupby(['day','sector']).original_PVR.rank(pct=True,method='average')
 market=pd.read_csv(MARKET,index_col=0);c['market']=c.day.map(market.regime);assert c.market.notna().all()
 cal=calendar();manifest={v['symbol']:v for v in json.loads(MAN.read_text())}
 native=np.full(len(c),np.nan);states=np.full(len(c),'UNKNOWN',dtype=object)
 source20=np.zeros(len(c),bool);source60=np.zeros(len(c),bool);floor=pd.to_numeric(c.floor).to_numpy()
 gap=c.open_known.to_numpy()&(c.entry_adjusted_open.to_numpy()<=floor);states[gap]='F'
 patherrors=[];audits=[]
 for sid,g in c.groupby('sid'):
  path=manifest[sid]['refs']['facts']; f=pd.read_parquet(path,columns=['close','segment_id']).reindex(cal)
  hs=sha(path);expected=manifest[sid].get('output_sha256',{}).get(path);assert expected is None or hs==expected
  audits.append(dict(sid=sid,path=path,sha256=hs))
  ix=g.index.to_numpy();tt=g.t.to_numpy(int);close=f.close.to_numpy(float);seg=f.segment_id.to_numpy();native[ix]=close[tt]
  for H,good in [(20,source20),(60,source60)]:
   a=g[g['complete'+str(H)]];ii=a.index.to_numpy();t=a.t.to_numpy(int)
   if not len(a):continue
   jj=t[:,None]+np.arange(1,H+1);pp=close[jj];ss=seg[jj]
   known=(np.isfinite(pp)&(pp>0)).all(axis=1)&(ss==seg[t,None]).all(axis=1)
   good[ii]=known
   e=np.max(np.abs(pp[:,-1]/a.entry_adjusted_open.to_numpy()-1-a['ret'+str(H)].to_numpy()));assert e<1e-8;patherrors.append(e)
   if H==20:
    oo=a.entry_adjusted_open.to_numpy();ff=floor[ii]
    up=pp>=(2*oo-ff)[:,None];dn=pp<=ff[:,None]
    tu=np.where(up.any(1),up.argmax(1),99);td=np.where(dn.any(1),dn.argmax(1),99)
    st=np.where(tu<td,'C',np.where(td<tu,'F','U'))
    st=np.where(oo<=ff,'F',st);states[ii]=np.where(known,st,'UNKNOWN')
 c['native_close']=native;c['state']=states;c['gap_failure']=gap
 c['label20_known']=source20&c.open_known.to_numpy()
 c['label60_known']=source60&c.label20_known.to_numpy()
 c['risk_scale']=np.log(native/floor)/c.scale.to_numpy()
 c['scale_floor_unknown']=c.scale.le(1e-8)
 c['feature_known']=np.isfinite(c[FEATURES]).all(axis=1)&c.CE_known.astype(bool)&(native>floor)&(c.scale>1e-8)
 c['Y']=c.ret60-.004;c['birth_key']=c.sid+'|'+c.epoch.astype(str);c['month']=c.day.str[:7]
 c.to_parquet(O/'PREPARED.parquet',index=False);pd.DataFrame(audits).to_csv(O/'FACT_SOURCE_HASHES.csv',index=False)
 support=[]
 for month,cut in months(cal):
  tr=train_rows(c,cut);nc=tr.state.value_counts();support.append(dict(month=month,cut=cut,cutday=str(cal[cut].date()),n=len(tr),dates=tr.day.nunique(),stocks=tr.sid.nunique(),C=int(nc.get('C',0)),F=int(nc.get('F',0)),U=int(nc.get('U',0)),max_maturity=int((tr.t+60).max())if len(tr)else None))
 pd.DataFrame(support).to_csv(O/'SUPPORT.csv',index=False)
 for p,v in src.items():assert sha(p)==v
 out=dict(rows=len(c),feature_known=int(c.feature_known.sum()),label20_known=int(c.label20_known.sum()),label60_known=int(c.label60_known.sum()),gap_failures=int(gap.sum()),source20_fail=int((c.complete20&~source20).sum()),source60_fail=int((c.complete60&~source60).sum()),max_path_error=max(patherrors),seconds=time.monotonic()-start,monthly_support=support)
 dump('PREP_AUDIT.json',out);print(json.dumps(out),flush=True)
def weighted_bounds(x,w):
 order=np.argsort(x,kind='stable');xx=np.asarray(x)[order];ww=np.asarray(w)[order];cw=np.cumsum(ww)
 return tuple(float(xx[min(np.searchsorted(cw,q*cw[-1],side='left'),len(xx)-1)])for q in [.01,.99])
def pre_fix_audit():
 old=pd.read_parquet(O.parent/'conditional_distribution_v1/PREPARED.parquet')
 c=pd.read_parquet(O/'PREPARED.parquet');cal=calendar()
 shared=[v for v in old.columns if v!='feature_known']
 pd.testing.assert_frame_equal(old[shared],c[shared],check_exact=True)
 changed=old.feature_known.ne(c.feature_known)
 assert changed.sum()==4
 assert (~c.loc[changed,'feature_known']).all()
 assert c.loc[changed,'scale_floor_unknown'].all()
 rows=[]
 for month,cut in months(cal):
  tr=train_rows(c,cut);prior=train_rows(old,cut)
  w=weights(tr);x=tr[FEATURES].to_numpy().copy();lo,hi=weighted_bounds(x[:,1],w);x[:,1]=np.clip(x[:,1],lo,hi)
  mu=np.average(x,axis=0,weights=w);sd=np.sqrt(np.average((x-mu)**2,axis=0,weights=w))
  pw=weights(prior);px=prior[FEATURES].to_numpy();pm=np.average(px,axis=0,weights=pw);ps=np.sqrt(np.average((px-pm)**2,axis=0,weights=pw))
  rows.append(dict(month=month,cut=cut,n_old=len(prior),n_new=len(tr),dropped=len(prior)-len(tr),p01=lo,p99=hi,new_risk_mean=mu[1],new_risk_sd=sd[1],old_risk_mean=pm[1],old_risk_sd=ps[1],clipped_rows=int(((tr.risk_scale<lo)|(tr.risk_scale>hi)).sum()),latest_maturity=int((tr.t+60).max())))
 pd.DataFrame(rows).to_csv(O/'NUMERICAL_FIX_MONTHLY_AUDIT.csv',index=False)
 c.loc[changed,['sid','day','scale','risk_scale','CE','feature_known','scale_floor_unknown']].to_csv(O/'ZERO_SCALE_UNKNOWN_ROWS.csv',index=False)
 audit=dict(status='PREFIT_AUDIT_NO_V2_PREDICTIONS_YET',rows=len(c),old_known=int(old.feature_known.sum()),new_known=int(c.feature_known.sum()),changed_features_known=int(changed.sum()),all_other_prepared_fields_exact=True,zero_scale_unknown=int(c.scale_floor_unknown.sum()),affected_label_training_months=[r['month']for r in rows if r['dropped']],feature_scaler_all_months=41,rule='weighted empirical inverse-CDF1%99% training-only risk clip, then weighted mean/std; zero-scale UNKNOWN at signal time')
 dump('NUMERICAL_FIX_PREFIT_AUDIT.json',audit);print('FIX_PREFLIGHT',json.dumps(audit),flush=True)

def fit_prob(X,y,w):
 n,p=X.shape;pen=np.tile(np.r_[0.,np.repeat(4.,p-1)],2);v=np.zeros(p*2)
 counts=np.array([w[y==j].sum()for j in range(3)])
 v[0]=np.log(counts[1]/counts[0]);v[p]=np.log(counts[2]/counts[0])
 def fg(v,needh=False):
  b=v.reshape(p,2,order='F');logits=np.column_stack([np.zeros(n),X@b]);lse=logsumexp(logits,axis=1);pr=np.exp(logits-lse[:,None])
  loss=float(w@(lse-logits[np.arange(n),y])+.5*np.sum(pen*v*v))
  err=pr.copy();err[np.arange(n),y]-=1
  grad=(X.T@(w[:,None]*err[:,1:])).ravel(order='F')+pen*v
  if not needh:return loss,grad
  H=np.empty((p*2,p*2))
  for j in range(2):
   for k in range(2):
    z=w*pr[:,j+1]*((1. if j==k else 0.)-pr[:,k+1])
    H[j*p:(j+1)*p,k*p:(k+1)*p]=X.T@(z[:,None]*X)
  H+=np.diag(pen)+1e-10*np.eye(p*2)
  return loss,grad,H
 for it in range(200):
  old,g,H=fg(v,True)
  if np.max(np.abs(g))<1e-7:break
  step=np.linalg.solve(H,g);alpha=1.
  while alpha>1e-10:
   nv=v-alpha*step;new,_=fg(nv)
   if new<=old-1e-4*alpha*(g@step):break
   alpha*=.5
  if alpha<=1e-10:
   assert np.max(np.abs(g))<1e-4,('newton stalled',old,g)
   break
  v=nv
  if np.max(np.abs(alpha*step))<1e-11:break
 loss,grad=fg(v);assert np.max(np.abs(grad))<1e-4,('convergence',loss,grad)
 return v.reshape(p,2,order='F'),dict(success=True,nit=it+1,loss=loss,max_gradient=float(np.abs(grad).max()),solver='damped Newton exact objective')
def probs(X,b):
 a=np.column_stack([np.zeros(len(X)),X@b]);return np.exp(a-logsumexp(a,axis=1)[:,None])
def distribution(tr,sector,market):
 # All values belong to the same historical training set. Branch fallback explicit.
 pieces=[];support=[]
 for s in LABELS:
  pool=tr[(tr.state==s)&(tr.market==market)]
  fallback=False
  if not len(pool):pool=tr[tr.state==s];fallback=True
  y=pool.Y.to_numpy();w=weights(pool);w/=w.sum()
  sec=pool.sector.eq(sector).to_numpy();nd=pool.loc[sec,'day'].nunique();lam=nd/(nd+20)
  w*=1-lam
  if sec.any():
   sw=1/pool.loc[sec].groupby('day').sid.transform('size').to_numpy(float);sw/=sw.sum();w[sec]+=lam*sw
  pieces.append((y,w));support.append(dict(state=s,sector_dates=nd,pool_dates=pool.day.nunique(),fallback=fallback))
 ys=np.concatenate([v[0]for v in pieces]);W=np.zeros((len(ys),3));pos=0
 for j,(y,w)in enumerate(pieces):W[pos:pos+len(y),j]=w;pos+=len(y)
 order=np.argsort(ys,kind='stable');ys=ys[order];W=W[order]
 return ys,W,support
def mix_scores(ys,W,P):
 means=W.T@ys
 F=np.cumsum(W,axis=0);A=np.cumsum(W*ys[:,None],axis=0)
 out=[]
 for p in P:
  cum=F@p;k=min(int(np.searchsorted(cum,.1)),len(ys)-1);prev=float(F[k-1]@p)if k else 0.;pay=float(A[k-1]@p)if k else 0.
  tail=(pay+(.1-prev)*ys[k])/.1;es=-tail;mu=float(p@means)
  out.append((mu,es,mu/es if es>0 else np.nan))
 return np.asarray(out)
def history_mean(tr,sector,market):
 a=tr[tr.market==market]
 if not len(a):a=tr
 w=weights(a);glob=np.average(a.Y,weights=w);s=a[a.sector==sector];nd=s.day.nunique();lam=nd/(nd+20)
 return float(lam*s.groupby('day').Y.mean().mean()+(1-lam)*glob)if len(s)else float(glob)
def run():
 assert not (O/'PREDICTIONS.parquet').exists()
 start=time.monotonic();c=pd.read_parquet(O/'PREPARED.parquet');cal=calendar()
 for name in ['pC','pF','pU','mix_mu','mix_ES','MIX_EV_ES','PC','DIRECT_MEAN','HISTORY_MEAN','baseline_pC','baseline_pF','baseline_pU']:c[name]=np.nan
 mods=[];dist_support=[];poison=[]
 for month,cut in months(cal):
  tr=train_rows(c,cut);idx=c.index[c.month.eq(month)&c.feature_known];counts=tr.state.value_counts()
  if len(tr)<300 or tr.day.nunique()<60 or any(counts.get(s,0)<50 for s in LABELS):
   mods.append(dict(month=month,known=False,n=len(tr)));continue
  w=weights(tr);x=tr[FEATURES].to_numpy(float).copy();lo,hi=weighted_bounds(x[:,1],w);x[:,1]=np.clip(x[:,1],lo,hi);mean=np.average(x,axis=0,weights=w);sd=np.sqrt(np.average((x-mean)**2,axis=0,weights=w))
  assert(sd>0).all()
  X=np.column_stack([np.ones(len(tr)),np.clip((x-mean)/sd,-5,5)])
  testx=c.loc[idx,FEATURES].to_numpy().copy();testx[:,1]=np.clip(testx[:,1],lo,hi)
  XT=np.column_stack([np.ones(len(idx)),np.clip((testx-mean)/sd,-5,5)])
  y=np.array([LABELS.index(v)for v in tr.state]);b,diag=fit_prob(X,y,w);P=probs(XT,b)
  base=np.array([w[y==j].sum()/w.sum()for j in range(3)])
  penalty=np.diag([0,4,4,4]);direct=np.linalg.solve(X.T@(w[:,None]*X)+penalty,X.T@(w*tr.Y.to_numpy()))
  c.loc[idx,['pC','pF','pU']]=P;c.loc[idx,'PC']=P[:,0];c.loc[idx,'DIRECT_MEAN']=XT@direct
  c.loc[idx,['baseline_pC','baseline_pF','baseline_pU']]=np.tile(base,(len(idx),1))
  for (sec,reg),g in c.loc[idx].groupby(['sector','market']):
   yy,ww,supp=distribution(tr,sec,reg);vv=mix_scores(yy,ww,g[['pC','pF','pU']].to_numpy())
   c.loc[g.index,['mix_mu','mix_ES','MIX_EV_ES']]=vv;c.loc[g.index,'HISTORY_MEAN']=history_mean(tr,sec,reg)
   dist_support.extend([dict(month=month,sector=sec,market=reg,**s)for s in supp])
  mods.append(dict(month=month,known=True,cut=cut,n=len(tr),dates=tr.day.nunique(),C=int(counts['C']),F=int(counts['F']),U=int(counts['U']),max_maturity=int((tr.t+60).max()),risk_train_p01=float(lo),risk_train_p99=float(hi),risk_train_clipped=int(((tr.risk_scale<lo)|(tr.risk_scale>hi)).sum()),risk_test_clipped=int(((c.loc[idx,'risk_scale']<lo)|(c.loc[idx,'risk_scale']>hi)).sum()),mean=mean.tolist(),sd=sd.tolist(),softmax=b.tolist(),direct=direct.tolist(),baseline=base.tolist(),fit=diag))
  if month in ['2023-01','2024-10','2026-01']:
   mutated=c.copy();future=mutated.t.add(60).ge(cut);mutated.loc[future,'Y']=99999;mutated.loc[future,'state']='C'
   tr2=train_rows(mutated,cut);assert tr.index.equals(tr2.index);pd.testing.assert_frame_equal(tr[FEATURES+['state','Y']],tr2[FEATURES+['state','Y']])
   poison.append(dict(month=month,rows=len(tr),future_mutated=int(future.sum()),identical_training=True))
  print('FIT',month,'n',len(tr),'pred',len(idx),'seconds',round(time.monotonic()-start,2),flush=True)
 c.to_parquet(O/'PREDICTIONS.parquet',index=False);dump('MONTHLY_MODELS.json',mods);dump('POISON.json',poison);pd.DataFrame(dist_support).to_csv(O/'DISTRIBUTION_SUPPORT.csv',index=False)
 # Seal rankings without reading realized evaluation outcomes.
 strategies=['PVR','MIX_EV_ES','PC','DIRECT_MEAN','HISTORY_MEAN'];picks=[];queues=[]
 for day,g in c.groupby('day',sort=True):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));Bidx=list(base.head(K).index);qbase=base.head(K).groupby('sector').size().to_dict()
  for method in strategies:
   selected=[]
   for sec,gs in base.groupby('sector',sort=False):
    k=int(qbase.get(sec,0))
    if not k:continue
    if method=='PVR':order=list(gs.index)
    else:
     known=np.isfinite(gs[method]);ranked=gs[known].sort_values([method,'original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ranked.index)
     order=[next(it)if bool(known.loc[j])else j for j in gs.index]
     assert set(order)==set(gs.index)
     assert all(order[k]==j for k,j in enumerate(gs.index)if not bool(known.loc[j]))
    selected.extend(order[:k])
   assert len(selected)==K;assert c.loc[selected].groupby('sector').size().to_dict()==qbase
   for j in selected:picks.append(dict(row=int(j),day=day,method=method))
   queues.append(dict(day=day,method=method,K=K,changed=len(set(selected)-set(Bidx)),known=int(np.isfinite(base[method]).sum())if method!='PVR'else len(base)))
 sel=pd.DataFrame(picks);sel.to_parquet(O/'SEALED_PICKS.parquet',index=False);pd.DataFrame(queues).to_csv(O/'QUEUE_AUDIT.csv',index=False)
 dump('RANK_SEAL.json',dict(prediction_sha=sha(O/'PREDICTIONS.parquet'),selection_sha=sha(O/'SEALED_PICKS.parquet'),script_sha=sha(Path(__file__)),seconds=time.monotonic()-start))
 print('RANK_SEALED',len(sel),'seconds',time.monotonic()-start,flush=True)
 evaluate(c,sel,strategies)
def auc(y,x):
 y=np.asarray(y,bool);x=np.asarray(x,float)
 if y.all()or not y.any():return np.nan
 ranks=pd.Series(x).rank(method='average').to_numpy();n=y.sum();return float((ranks[y].sum()-n*(n+1)/2)/(n*(len(y)-n)))
def evaluation_metrics(a,H):
 a=a[a['complete'+str(H)]];r=a['ret'+str(H)]
 v=r-.004;u=v[v>0];l=v[v<=0]
 return dict(n=len(a),days=a.day.nunique(),gross_day_mean=float(a.groupby('day')['ret'+str(H)].mean().mean()),gross_event_mean=float(r.mean()),less40bp_day=float(a.groupby('day')['ret'+str(H)].mean().mean()-.004),less100bp_day=float(a.groupby('day')['ret'+str(H)].mean().mean()-.01),positive40bp=float(v.gt(0).mean()),avg_win=float(u.mean()),avg_loss=float(l.mean()),ES10=float(-v[v<=v.quantile(.1)].mean()),tail20pct=int(r.ge(.2).sum()))
def paired_ci(d,tc):
 n=len(d);mu=float(d.mean());grp=tc.loc[d.index].floordiv(60);g=int(grp.nunique())
 sums=(d-mu).groupby(grp).sum();se=float(np.sqrt(g/(g-1)*(sums**2).sum()/n**2))if g>1 else np.nan
 crit=float(tdist.ppf(.975,g-1))if g>1 else np.nan
 return dict(days=n,blocks60=g,delta=mu,se=se,low=mu-crit*se,high=mu+crit*se)
def evaluate(c,sel,strategies):
 s=sel.merge(c,left_on='row',right_index=True,validate='many_to_one',suffixes=('_pick',''))
 periods=[('ALL',c.index[c.year.ge(2023)])]+[(str(y),c.index[c.year.eq(y)])for y in [2022,2023,2024,2025,2026]]+[('2024_924',c.index[c.day.between('2024-09-24','2024-10-31')]),('2026Q1',c.index[c.day.between('2026-01-01','2026-03-31')])]
 annual=[];paired=[];tmap=c.groupby('day').t.first()
 for period,ids in periods:
  a=s[s.row.isin(ids)]
  for H in [5,20,60]:
   for method,g in a.groupby('method'):annual.append(dict(period=period,H=H,method=method,source_picks=len(g),**evaluation_metrics(g,H)))
   ok=a.groupby('day')['complete'+str(H)].all();aa=a[a.day.isin(ok[ok].index)];dm=aa.groupby(['day','method'])['ret'+str(H)].mean().unstack('method').dropna()
   for method in strategies[1:]:
    if len(dm):paired.append(dict(period=period,H=H,method=method,**paired_ci(dm[method]-dm.PVR,tmap)))
 pd.DataFrame(annual).to_csv(O/'ANNUAL_PRICE_RESULTS.csv',index=False);pd.DataFrame(paired).to_csv(O/'PAIRED_BLOCK_RESULTS.csv',index=False)
 # Preserve original root birth; known history did not select roots by future completeness.
 births=c.sort_values('t').drop_duplicates('birth_key');coverage=[];lookup={m:set(zip(a.sid,a.day))for m,a in s.groupby('method')}
 for r in births.itertuples():
  early=c[c.birth_key.eq(r.birth_key)&c.t.le(r.t+5)]
  row=dict(key=r.birth_key,sid=r.sid,birth=r.day,year=r.year,complete60=bool(r.complete60),big60=bool(r.big60_posthoc))
  for m in strategies:row[m]=any((q.sid,q.day)in lookup[m]for q in early.itertuples())
  coverage.append(row)
 cov=pd.DataFrame(coverage);cov.to_csv(O/'ROOT_COVERAGE.csv',index=False);summary=[]
 for period,mask in [('ALL',cov.year.ge(2023))]+[(str(y),cov.year.eq(y))for y in [2022,2023,2024,2025,2026]]+[('2024_924',cov.birth.between('2024-09-24','2024-10-31')),('2026Q1',cov.birth.between('2026-01-01','2026-03-31'))]:
  b=cov[mask&cov.big60]
  for m in strategies:summary.append(dict(period=period,method=m,big_roots=len(b),captured=int(b[m].sum()),base_captured=int(b.PVR.sum()),lost=int((b.PVR&~b[m]).sum()),added=int((~b.PVR&b[m]).sum())))
 pd.DataFrame(summary).to_csv(O/'BIG_ROOT_RESULTS.csv',index=False)
 # Proper scores on valid observed opportunity states, not actual transaction wins.
 proper=[]
 for yr,a in c[c.feature_known&c.label20_known&c.pC.notna()].groupby('year'):
  yy=np.array([LABELS.index(v)for v in a.state]);P=a[['pC','pF','pU']].to_numpy();BB=a[['baseline_pC','baseline_pF','baseline_pU']].to_numpy();one=np.eye(3)[yy]
  for name,prob in [('MODEL',P),('HISTORY',BB)]:
   bs=((prob-one)**2).sum(1);ll=-np.log(prob[np.arange(len(a)),yy]);proper.append(dict(year=yr,model=name,n=len(a),dates=a.day.nunique(),brier=float(bs.mean()),logloss=float(ll.mean()),C_auc=auc(yy==0,prob[:,0]),pred_C=float(prob[:,0].mean()),observed_C=float((yy==0).mean())))
 pd.DataFrame(proper).to_csv(O/'PROPER_SCORES.csv',index=False)
 # Actual original closed first MOBILE rounds remain descriptive source-account associations.
 f=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');f=f[f.account.eq('PVR')&f.first_kind.eq('add')]
 a=f.merge(c[['sid','day','MIX_EV_ES','PC','DIRECT_MEAN','HISTORY_MEAN']],left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='one_to_one');a.to_csv(O/'ORIGINAL_ACTUAL_ASSOCIATION.csv',index=False)
 ar=[]
 for yr,g in a.groupby('year'):
  for m in strategies[1:]:
   q=g[g.closed&np.isfinite(g[m])]
   ar.append(dict(year=yr,method=m,all_births=len(g),scored_closed=len(q),scored_open=int((~g.closed&np.isfinite(g[m])).sum()),source_winrate=float(q.round_pnl.gt(0).mean()),auc=auc(q.round_pnl.gt(0),q[m])if len(q)else None,rho_return=float(spearmanr(q[m],q.round_return_on_cumulative_cost).statistic)if len(q)>2 else None))
 pd.DataFrame(ar).to_csv(O/'ACTUAL_ASSOCIATION_SUMMARY.csv',index=False)
 stable=[]
 for yr,g in c.groupby('year'):
  v=g[g.MIX_EV_ES.notna()];rho=[]
  for _,q in v.groupby(['day','sector']):
   if len(q)>1 and q.MIX_EV_ES.nunique()>1 and q.original_PVR.nunique()>1:rho.append(spearmanr(q.MIX_EV_ES,q.original_PVR).statistic)
  stable.append(dict(year=yr,n=len(g),known=len(v),pct_known=len(v)/len(g),mean_pC=float(v.pC.mean()),mean_mu=float(v.mix_mu.mean()),mean_ES=float(v.mix_ES.mean()),median_sector_rho_vs_PVR=float(np.nanmedian(rho))if rho else None,rho_score_PC=float(spearmanr(v.MIX_EV_ES,v.PC).statistic)if len(v)>2 else None))
 pd.DataFrame(stable).to_csv(O/'STABILITY.csv',index=False)
 src=json.loads((O/'INPUT_FREEZE.json').read_text())
 for p,h in src.items():assert sha(p)==h
 completion=dict(status='ONE_FROZEN_FORWARD_OPPORTUNITY_EXPERIMENT_NOT_ACCOUNT',predictions=int(c.MIX_EV_ES.notna().sum()),rows=len(c),accounts=0,parameter_searches=0,feature_specs=1,all_same_K_sector=True,source_unchanged=True)
 dump('COMPLETION.json',completion)
 print('SUMMARY',json.dumps(completion),flush=True)
 print('PRIMARY60',pd.DataFrame(annual).query('H==60').to_json(orient='records'),flush=True)
 print('PAIRED60',pd.DataFrame(paired).query('H==60').to_json(orient='records'),flush=True)
 print('BIG',pd.DataFrame(summary).to_json(orient='records'),flush=True)
 print('PROPER',json.dumps(proper),flush=True)
 print('STABILITY',json.dumps(stable),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='prepare':
  prep();pre_fix_audit()
 elif sys.argv[1]=='run':run()
 else:raise ValueError(sys.argv[1])

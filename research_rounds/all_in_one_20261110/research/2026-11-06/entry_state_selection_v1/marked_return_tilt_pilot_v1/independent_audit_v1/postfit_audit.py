from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
from scipy.special import logsumexp
O=Path(__file__).resolve().parents[1]; A=Path(__file__).resolve().parent; R=O.parent
PEN=np.array([4.,4.,4.,16.,16.]); EDGES=np.array([0,5,20,60,120,1000000]); BE=np.array([-1,0,1,3,np.inf]); CATS=['Y_le_minus1','Y_minus1_to_0','Y_0_to_1','Y_1_to_3','Y_gt_3','U','M','S']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def conv(x):
 if isinstance(x,dict):return {str(k):conv(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [conv(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.floating):return float(x) if np.isfinite(x) else None
 if isinstance(x,np.bool_):return bool(x)
 return x
seal=json.loads((O/'PREDICTION_SEAL.json').read_text());prep=json.loads((O/'PREPARE_SEAL.json').read_text());inp=json.loads((O/'INPUT_HASHES.json').read_text())
assert sha(O/'PREDICTIONS.parquet')==seal['predictions_sha256']=='82901843818733f8279f6521a835703e752068684b2235c5ec25a3c1ffd5bc02'
assert sha(O/'MONTHLY_MODELS.json')==seal['models_sha256']=='69f4fdc2667e4e168b50e2eeb6e52d04bc55d4eac1395751b6e10c2b1c525c73'
assert all(sha(O/p)==h for p,h in prep.items()) and all(sha(p)==h for p,h in inp.items())
assert sha(O/'run_pilot.py')==seal['code_sha256'] and sha(O/'PROTOCOL.md')==seal['protocol_sha256']
for name in ['OUTCOMES.csv','COVERAGE.csv','H120_CALIBRATION.csv','RESULT_SUMMARY.json']:assert (O/name).stat().st_mtime_ns>(O/'PREDICTION_SEAL.json').stat().st_mtime_ns
p=pd.read_parquet(O/'PREDICTIONS.parquet');obs=pd.read_parquet(O/'ASOF_OBSERVATIONS.parquet');r=pd.read_parquet(O/'ALL_ROWS.parquet');models=json.loads((O/'MONTHLY_MODELS.json').read_text())
assert p.round_id.is_unique and p.model_reason.eq('KNOWN').all()
assert set(p.round_id)==set(r.loc[r.cohort_id.eq('old2024SepDec'),'round_id'])
def scaler(g):
 v=g[['P','D','C']].to_numpy(float);med=np.median(v,axis=0);s=(np.quantile(v,.75,axis=0)-np.quantile(v,.25,axis=0))/1.349
 z=np.clip((v-med)/s,-5,5);v=np.c_[z[:,0]*z[:,1],z[:,0]*z[:,2]];im=np.median(v,axis=0);is_=(np.quantile(v,.75,axis=0)-np.quantile(v,.25,axis=0))/1.349
 return [med,s,im,is_]
def design(g,sc):
 med,s,im,is_=sc;z=np.clip((g[['P','D','C']].to_numpy(float)-med)/s,-5,5);v=np.c_[z[:,0]*z[:,1],z[:,0]*z[:,2]];return np.c_[z,np.clip((v-im)/is_,-5,5)]
def moment(eta,b):
 v=np.r_[0.,b['Y']];w=np.r_[b['q0']+b['qU']+b['qM'],b['q']];logs=np.log(w,where=w>0,out=np.full_like(w,-np.inf));t=eta[:,None]*v+logs;L=logsumexp(t,axis=1);pr=np.exp(t-L[:,None]);mu=pr@v;var=np.sum(pr*(v-mu[:,None])**2,axis=1);return L,mu,var,pr[:,1:]
def forecast(z,beta,bs):
 eta=z@beta;S=np.ones(len(z));P=np.zeros((len(z),8));amt=np.zeros(len(z));cached=[]
 for b in bs:
  L,_,_,q=moment(eta,b);cats=np.searchsorted(BE,b['Y'],side='left');h=np.column_stack([q[:,cats==j].sum(axis=1) for j in range(5)]+[np.exp(np.log(b[k])-L) if b[k]>0 else np.zeros(len(z)) for k in ['qU','qM']]);h0=np.exp(np.log(b['q0'])-L) if b['q0']>0 else np.zeros(len(z));cached.append((h,h0,q@b['Y']))
 for age in range(1,121):
  h,h0,y=cached[np.searchsorted(EDGES[1:],age,side='left')];P[:,:7]+=S[:,None]*h;amt+=S*y;S*=h0
 P[:,7]=S;mass=P[:,:5].sum(axis=1);return P,amt/mass,amt
checks=[]
for model in models:
 cut=pd.Timestamp(model['cut']);tr=obs[obs.cut.eq(cut)&obs.feature_known].copy();mat=tr[tr.event.eq('O')];sc=scaler(mat)
 assert all(np.array_equal(a,np.array(b)) for a,b in zip(sc,model['scaling']))
 z=design(tr,sc);n=tr[[f'n{g}' for g in range(5)]].to_numpy(float);bs=[]
 for g,saved in enumerate(model['baselines']):
  e=tr[tr.event_g.eq(g)&~tr.event.eq('S')];ys,c=np.unique(e.loc[e.event.eq('O'),'Y'].to_numpy(float),return_counts=True);N=n[:,g].sum();b=dict(N=N,Y=ys,q=c/N,q0=1-len(e)/N,qU=e.event.eq('U').sum()/N,qM=e.event.eq('M').sum()/N)
  for k in b:assert np.allclose(b[k],saved[k],rtol=0,atol=1e-15)
  bs.append(b)
 beta=np.array(model['marked_beta']);eta=z@beta;y=tr.Y.fillna(0).to_numpy();objective=.5*np.sum(PEN*beta*beta)-eta@y;grad=PEN*beta-z.T@y;hh=np.diag(PEN);res=-y.copy();information=np.zeros(len(z))
 for g,b in enumerate(bs):
  L,mu,var,_=moment(eta,b);objective+=n[:,g]@L;grad+=z.T@(n[:,g]*mu);hh+=z.T@((n[:,g]*var)[:,None]*z);res+=n[:,g]*mu;information+=n[:,g]*var*np.sum(z*z,axis=1)
 assert max(abs(grad))<1e-6;assert np.isclose(objective,model['marked_QA']['objective'],atol=1e-8,rtol=0);assert np.linalg.eigvalsh(hh).min()>=4-1e-7
 assert np.allclose(np.linalg.eigvalsh(hh),model['marked_QA']['hessian_eigenvalues'],rtol=1e-12,atol=1e-8)
 imax=int(np.nanargmax(tr.Y));gi=res[:,None]*z;delta=np.linalg.solve(hh,gi[imax]);assert np.allclose(delta,model['influence']['maxY_fixed_q_scaler_delete_direction_delta'],rtol=1e-12,atol=1e-12)
 assert tr.iloc[imax].event_g==4
 for col in ['sid','root_cluster','signal_day']:
  gg=pd.DataFrame({'cluster':tr[col].astype(str).to_numpy(),'gradient_norm':np.linalg.norm(gi,axis=1),'information_trace':information}).groupby('cluster').sum();ss=model['influence']['clusters'][col]
  for val in ['gradient_norm','information_trace']:
   for nn in [1,5]:assert np.isclose(gg[val].nlargest(nn).sum()/gg[val].sum(),ss[f'{val}_top{nn}_share'],atol=1e-12,rtol=0)
 pp=p[p.cut.eq(cut)&p.feature_known].copy();Z=design(pp,sc);P,Q,amount=forecast(Z,beta,bs);P0,Q0,_=forecast(np.zeros((1,5)),np.zeros(5),bs)
 assert np.allclose(P,pp[['F_'+c for c in CATS]],rtol=0,atol=1e-12);assert np.allclose(Q,pp.Q,rtol=0,atol=1e-12);assert np.allclose(amount,pp.amount_submoment,rtol=0,atol=1e-12);assert np.allclose(Q0[0],pp.Q0,atol=1e-12,rtol=0)
 assert np.array_equal(Q>=Q0[0],pp.select_marked.to_numpy());assert np.max(abs(P.sum(axis=1)-1))<1e-12
 X=np.c_[np.ones(len(mat)),design(mat,sc)];yy=mat.Y.gt(0).to_numpy(float);binary={}
 for name,inds,pen in [('binary',slice(None),np.array([0.,4,4,4,16,16])),('pvr',slice(0,2),np.array([0.,4]))]:
  b=np.array(model[name+'_beta']);x=X[:,inds];s=1/(1+np.exp(-np.clip(x@b,-35,35)));g=x.T@(s-yy)+pen*b;assert max(abs(g))<1e-6
  V=np.c_[np.ones(len(pp)),Z][:,inds];prob=1/(1+np.exp(-np.clip(V@b,-35,35)));assert np.allclose(prob,pp['p_'+name],atol=1e-14,rtol=0);assert np.array_equal(prob>=yy.mean(),pp['select_'+name]);binary[name]=float(max(abs(g)))
 checks.append(dict(cut=model['cut'],ordinary_n=len(mat),risk_n=len(tr),marked_gradient_max=float(max(abs(grad))),ridge_penalty=float(.5*np.sum(PEN*beta*beta)),marked_objective=float(objective),minimum_hessian_eigenvalue=float(np.linalg.eigvalsh(hh).min()),prediction_max_error=float(np.max(abs(P-pp[['F_'+c for c in CATS]].to_numpy()))),influence_delta_over_beta=float(np.linalg.norm(delta)/np.linalg.norm(beta)),maxY_age=int(tr.iloc[imax].age_end),binary_gradient_max=binary))
 print('VERIFIED_CUT',model['cut'],checks[-1],flush=True)
assert p.loc[~p.feature_known,['select_marked','select_pvr','select_binary']].all().all();assert p.select_original.all() and p.select_beta0.all()
# Original full 0-to-0 cash, using saved actual conditional fills and dated fees.
B=R/'independent_channel_joint_economic_v1/economic_2024';acts=pd.read_csv(B/'joint/ACTIONS.csv',float_precision='round_trip');acts=acts[acts.round_id.isin(p.round_id)].copy();acts['day']=pd.to_datetime(acts.day);acts['cash']=np.where(acts.side.str.startswith('buy'),-acts.q*acts.price-acts.fee,acts.q*acts.price-acts.fee);acts['dq']=np.where(acts.side.str.startswith('buy'),acts.q,-acts.q);cash=acts.groupby('round_id').cash.sum();qty=acts.groupby('round_id').dq.sum()
x=p.merge(r[[c for c in r if c not in p or c=='round_id']],on='round_id',validate='one_to_one');x['month']=x.signal_day.dt.to_period('M').astype(str);strict=x[x.entered&x.ordinary];casherr=float(np.max(abs(strict.round_id.map(cash)-strict.net_pnl)));assert casherr<1e-7 and strict.round_id.map(qty).eq(0).all()
# Independent outcome and tail arithmetic for all scopes and months.
rows=[];tails=[]
for month,g in [('ALL',x)]+list(x.groupby('month')):
 for scope,mask in [('STRICT_ORDINARY',g.ordinary),('NONORDINARY_FINANCIAL_KNOWN_FINAL_ONLY',~g.ordinary&g.eval_financial_known)]:
  base=g[g.entered&mask]
  for arm in ['original','beta0','pvr','binary','marked']:
   s=g[g['select_'+arm]&g.entered&mask];v=s.net_pnl;w=v[v>0];l=v[v<0];z=int(v.eq(0).sum());t3=s[v>9000];t30=s[s.net_return_on_buy_cash>=.3]
   row=dict(month=month,arm=arm,scope=scope,n=len(s),W=len(w),L=len(l),Z=z,winrate=float(v.gt(0).mean()) if len(s) else np.nan,mean_win=w.mean(),mean_loss=l.mean(),payoff=w.mean()/abs(l.mean()) if len(w) and len(l) else np.nan,profit_factor=w.sum()/abs(l.sum()) if len(l) else np.nan,old_static_subset_net_CNY=v.sum(),tail3_n=len(t3),tail3_net_CNY=t3.net_pnl.sum(),tail30_n=len(t30),tail30_net_CNY=t30.net_pnl.sum(),stocks=s.sid.nunique(),roots=s.root_cluster.nunique(),signal_dates=s.signal_day.nunique());rows.append(row)
   b3=base[base.net_pnl>9000];b30=base[base.net_return_on_buy_cash>=.3];tails.append(dict(month=month,arm=arm,scope=scope,tail3_count_retention=len(t3)/len(b3) if len(b3) else np.nan,tail3_amount_retention=t3.net_pnl.sum()/b3.net_pnl.sum() if len(b3) else np.nan,tail30_count_retention=len(t30)/len(b30) if len(b30) else np.nan,tail30_amount_retention=t30.net_pnl.sum()/b30.net_pnl.sum() if len(b30) else np.nan))
for name,vs in [('OUTCOMES.csv',rows),('TAIL_RETENTION.csv',tails)]:
 independent=pd.DataFrame(vs).set_index(['month','arm','scope']).sort_index();saved=pd.read_csv(O/name).set_index(['month','arm','scope']).sort_index();assert independent.index.equals(saved.index);assert np.allclose(independent[saved.columns],saved,rtol=1e-12,atol=1e-7,equal_nan=True)
# Rebuild H120 state from saved action/freeze events and independently verify calibration.
cal=pd.DatetimeIndex(np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)['dates']);buy=acts[acts.side.eq('buy_core')].set_index('round_id').day;sell=acts[acts.side.eq('sell_all')].set_index('round_id').day;fr=pd.DataFrame(json.loads((B/'FROZEN_RESPONSIBILITIES.json').read_text()));fr=fr[fr.round_id.isin(p.round_id)];fr['day']=pd.to_datetime(fr.day);freeze=fr.set_index('round_id').day;hs=[];admin=[]
for _,v in x.iterrows():
 if v.round_id not in buy:continue
 hday=cal[cal.get_loc(buy[v.round_id])+119];end=sell.get(v.round_id,pd.NaT);ud=freeze.get(v.round_id,pd.NaT)
 if pd.notna(ud) and ud<=hday:c='U'
 elif pd.notna(end) and end<=hday:c=CATS[np.searchsorted(BE,v.net_pnl/3000,side='left')] if v.ordinary and v.ordinary_known_at<=hday+pd.Timedelta(hours=15) else 'M'
 elif ((pd.notna(end) and end>=hday) or (pd.notna(ud) and ud>=hday) or pd.to_datetime(v.last_known_mark_day)>=hday):c='S'
 else:admin.append(v.round_id);continue
 hs.append(dict(round_id=v.round_id,observed_H_category=c,H_day=hday,month=v.month))
hs=pd.DataFrame(hs);saved=pd.read_parquet(O/'H120_OBSERVED_STATES.parquet');assert len(admin)==0 and len(hs)==1198;cmp=hs.merge(saved,on='round_id',suffixes=('_ours','_saved'),validate='one_to_one');assert cmp.observed_H_category_ours.eq(cmp.observed_H_category_saved).all() and cmp.H_day_ours.eq(cmp.H_day_saved).all();hh=hs.merge(p,on='round_id',validate='one_to_one');hrows=[]
for month,g in [('ALL',hh)]+list(hh.groupby('month')):
 g=g[g.Q.notna()];observed=np.array([CATS.index(c) for c in g.observed_H_category]);Y=np.eye(8)[observed]
 for arm in ['beta0','marked']:
  if arm=='marked':P=g[['F_'+c for c in CATS]].to_numpy()
  else:P=np.array([next(mm['beta0_forecast']['prob'][0] for mm in models if pd.Timestamp(mm['cut'])==c) for c in g.cut])
  hrows.append(dict(month=month,arm=arm,n=len(g),Brier=np.mean(np.sum((P-Y)**2,axis=1)),logloss_probability_floor_1e12=np.mean(-np.log(np.maximum(P[np.arange(len(P)),observed],1e-12))),zero_predicted_observed_category=int((P[np.arange(len(P)),observed]==0).sum()),**{f'actual_{c}':Y[:,j].mean() for j,c in enumerate(CATS)},**{f'pred_{c}':P[:,j].mean() for j,c in enumerate(CATS)}))
ha=pd.DataFrame(hrows).set_index(['month','arm']).sort_index();hb=pd.read_csv(O/'H120_CALIBRATION.csv').set_index(['month','arm']).sort_index();assert np.allclose(ha[hb.columns],hb,atol=1e-12,rtol=0)
# Held/unknown and original score-unknown membership are preserved; no financial imputation.
coverage=pd.read_csv(O/'COVERAGE.csv');assert len(p)==len(x);assert int(coverage.query("month=='ALL' and arm=='original'").iloc[0].births)==len(x)
for _,row in coverage.iterrows():
 g=x if row.month=='ALL' else x[x.month.eq(row.month)];s=g[g['select_'+row.arm]]
 q=dict(births=len(g),selected_births=len(s),entered=int(g.entered.sum()),selected_entered=int(s.entered.sum()),known_score=int(g.Q.notna().sum()),unknown_score=int(g.Q.isna().sum()),selected_unclosed=int((s.entered&~s.complete).sum()),selected_closed_mark_unavailable=int((s.entered&s.complete&~s.ordinary).sum()),selected_entry_unknown=int((~s.entered&s.status.str.contains('UNKNOWN')).sum()),selected_Q0=int(s.status.eq('PRECHECK_Q0_NO_SUBMIT').sum()),selected_feature_unknown=int((~s.feature_known).sum()))
 assert all(int(row[k])==v for k,v in q.items())
for datecol in ['entry_day','exit_day']:x[datecol]=pd.to_datetime(x[datecol])
x['exit_age']=cal.get_indexer(x.exit_day)-cal.get_indexer(x.entry_day)+1
lost=x[x.ordinary&x.entered&~x.select_marked];late=x[x.ordinary&x.entered&x.exit_age.gt(120)];tail=x[x.ordinary&x.entered&x.net_pnl.gt(9000)]
lateinfo=[]
for scope,g in [('ALL_REJECTED',lost),('LATE_ORDINARY',late),('LATE_REJECTED',late[~late.select_marked]),('LATE_TAIL',tail[tail.exit_age.gt(120)]),('LATE_TAIL_REJECTED',tail[tail.exit_age.gt(120)&~tail.select_marked])]:lateinfo.append(dict(scope=scope,n=len(g),W=int(g.net_pnl.gt(0).sum()),net_CNY=float(g.net_pnl.sum()),tail3_n=int(g.net_pnl.gt(9000).sum()),tail3_net_CNY=float(g.loc[g.net_pnl.gt(9000),'net_pnl'].sum())))
assert all(sha(p)==h for p,h in inp.items()) and all(sha(O/p)==h for p,h in prep.items());assert sha(O/'PREDICTIONS.parquet')==seal['predictions_sha256'] and sha(O/'MONTHLY_MODELS.json')==seal['models_sha256']
summary=dict(status='PASS_REPRODUCIBILITY_AND_CONDITIONAL_SCOPE; NEGATIVE_CANDIDATE_RESULT',checks=checks,source_and_prediction_hashes_unchanged=True,real_data_refits=0,economic_runs=0,source_cash_max_abs_error=casherr,registered=len(x),entered=int(x.entered.sum()),feature_unknown=int((~x.feature_known).sum()),H_observed=len(hs),H_admin=len(admin),H_score_known=int(saved.Q.notna().sum()),late_and_rejected=lateinfo,prediction_seal=seal,limitations=['Exact frozen conditional working model, not identified birth expectation.','Fixed-q/scaler local influence is not full LOO.','Maximum training mark belongs to121+ and is excluded directly from H120 Q.','Historical NON-PIT development revalidation with dependent cohorts; no strategy/account PnL.'])
for name,data in [('POSTFIT_AUDIT.json',summary)]:
 with (A/name).open('x') as f:json.dump(conv(data),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
for name,data in [('INDEPENDENT_OUTCOMES.csv',rows),('INDEPENDENT_TAIL_RETENTION.csv',tails),('INDEPENDENT_H120_CALIBRATION.csv',hrows),('INDEPENDENT_LATE_REJECTED.csv',lateinfo)]:
 assert not (A/name).exists();pd.DataFrame(data).to_csv(A/name,index=False)
print(json.dumps(conv(summary),ensure_ascii=False,indent=2),flush=True)

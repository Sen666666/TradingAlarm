"""One nested interaction test on frozen signal events. No account import or execution."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math,time
O=Path(__file__).resolve().parent;P=O.parent
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
F7=['protected_distance_over_prior_sigma','z5','prior_sigma20','log_amount_relative21','market_breadth20','market_delta5','original_i_buy']
DUM=['d0v1','d1v0','d1v1'];BASE=F7+['environment']+DUM;EXTRA=['environment_x_'+x for x in DUM];FULL=BASE+EXTRA
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False))
start=time.monotonic();freeze=read(O/'FREEZE.json')
assert sha(O/'FREEZE.json')=='81631077414fe98c2fb22d25bb95c61e9a6e1260f99406d54de9ab7ba62d9d21'
assert sha(P/'SIGNAL_EVENTS_WITH_LABELS.parquet')==freeze['parent_event_sha256']
assert sha(P/'FROZEN_SELECTIONS.parquet')==freeze['parent_selection_sha256']
assert sha(P/'FREEZE.json')==freeze['parent_freeze_sha256']
assert sha(HP)==read(P/'SOURCE_HASHES.json')[str(HP)]
assert not (O/'SUMMARY.json').exists(),'No silent rerun'
dump('SOURCE_FREEZE.json',{str(p):sha(p) for p in [Path(__file__),O/'FREEZE.json',P/'SIGNAL_EVENTS_WITH_LABELS.parquet',P/'FROZEN_SELECTIONS.parquet',P/'MARKET_CLOCK.csv',HP,U/'STOCK_MANIFEST.json']})
events=pd.read_parquet(P/'SIGNAL_EVENTS_WITH_LABELS.parquet')
market=pd.read_csv(P/'MARKET_CLOCK.csv',index_col=0,parse_dates=True);days=market.index;n=len(days)
h=np.load(HP,allow_pickle=False);hd=pd.DatetimeIndex(h['dates']);take=hd.get_indexer(days);assert (take>=0).all()
ids=[r['symbol'] for r in read(U/'STOCK_MANIFEST.json')];sym={str(s):i for i,s in enumerate(h['symbols'])};cols=[sym[s] for s in ids]
C=pd.DataFrame(h['close'][take][:,cols],index=days,columns=ids)
S=pd.DataFrame(h['segment'][take][:,cols],index=days,columns=ids)
C=C.where(np.isfinite(C)&C.gt(0))
def relative_returns(c):
 r=np.log(c).diff().where(S.eq(S.shift()))
 m=r.median(axis=1,skipna=True)
 return r.sub(m,axis=0),m
rel,median=relative_returns(C)
events['environment']=events.day.map((2*market.market_breadth20.shift()-1).rename(index=lambda d:str(d.date())))
events['relative_log_return']=np.array([rel.at[pd.Timestamp(r.day),r.sid] for r in events.itertuples()])
knowncat=np.isfinite(events.relative_log_return)&np.isfinite(events.log_amount_relative21)
direction=events.relative_log_return.gt(0).astype(int);volume=events.log_amount_relative21.gt(0).astype(int)
events['category']=['d'+str(d)+'v'+str(v) if k else None for d,v,k in zip(direction,volume,knowncat)]
for cat in DUM:
 events[cat]=np.where(knowncat,events.category.eq(cat).astype(float),np.nan)
 events['environment_x_'+cat]=events.environment*events[cat]
events['common_features_known']=np.isfinite(events[FULL]).all(axis=1)
assert events[['sid','day']].equals(pd.read_parquet(P/'SIGNAL_EVENTS_WITH_LABELS.parquet',columns=['sid','day']))
assert all(days[r.t].strftime('%Y-%m-%d')==r.day for r in events.itertuples())
# Explicit feature-prefix checks; future price poisoning cannot change earlier direction/categories.
feature_checks=[]
for cutoff in ['2022-01-04','2024-10-08','2026-01-05']:
 t=days.get_loc(pd.Timestamp(cutoff));c=C.copy();c.iloc[t+1:]=c.iloc[t+1:]*999
 rr,_=relative_returns(c)
 assert np.allclose(rr.iloc[:t+1],rel.iloc[:t+1],rtol=0,atol=0,equal_nan=True)
 feature_checks.append(dict(cutoff=cutoff,future_prices_poisoned=True,prefix_exact=True))
dump('FEATURE_PREFIX_CHECKS.json',feature_checks)
events.to_parquet(O/'SAME_EVENTS_NEW_FEATURES.parquet',index=False)
def sigmoid(z):return 1/(1+np.exp(-np.clip(z,-35,35)))
def fit(train,features):
 x=train[features].to_numpy(float);y=train.ret5.gt(0).to_numpy(float);mu=x.mean(axis=0);sd=x.std(axis=0);sd=np.where(sd>1e-12,sd,1.)
 X=np.column_stack([np.ones(len(x)),np.clip((x-mu)/sd,-5,5)])
 b=np.zeros(X.shape[1]);b[0]=np.log((y.sum()+.5)/(len(y)-y.sum()+.5))
 pen=np.array([0.]+[16. if c in EXTRA else 4. for c in features])
 def obj(b):
  z=X@b
  return np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(pen*b*b)
 for it in range(100):
  p=sigmoid(X@b);g=X.T@(p-y)+pen*b;H=X.T@((p*(1-p))[:,None]*X)+np.diag(pen)+np.eye(len(b))*1e-10
  step=np.linalg.solve(H,g);scale=1.;old=obj(b)
  while scale>1e-8 and obj(b-scale*step)>old+1e-9:scale*=.5
  b-=scale*step
  if np.max(np.abs(scale*step))<1e-9:break
 grad=np.max(np.abs(X.T@(sigmoid(X@b)-y)+pen*b))
 assert grad<1e-4,(features,grad)
 return dict(mu=mu,sd=sd,b=b,iterations=it+1,rank=int(np.linalg.matrix_rank(X)))
def predict(g,features,m):
 X=np.column_stack([np.ones(len(g)),np.clip((g[features].to_numpy()-m['mu'])/m['sd'],-5,5)])
 return sigmoid(X@m['b'])
events['ADDITIVE']=np.nan;events['INTERACTION']=np.nan;fits=[];poison=[];nested=[]
for month in sorted({str(d.to_period('M')) for d in days if d.year>=2022}):
 first=next(d for d in days if str(d.to_period('M'))==month);cut=days.get_loc(first)
 train=events[events.common_features_known&events.complete5&events.t.ge(cut-252)&events.maturity5.lt(cut)]
 test=events[events.common_features_known&events.day.str.startswith(month)]
 ok=len(train)>=500 and train.ret5.gt(0).sum()>=50 and train.ret5.le(0).sum()>=50 and train.day.nunique()>=60
 assert ok,month
 rec=dict(month=month,cutoff=str(first.date()),train_rows=len(train),train_dates=train.day.nunique(),train_positive=int(train.ret5.gt(0).sum()),last_maturity=str(days[int(train.maturity5.max())].date()),predicted_rows=len(test),categories=train.category.value_counts().to_dict(),models={})
 mm={}
 for name,features in [('ADDITIVE',BASE),('INTERACTION',FULL)]:
  m=fit(train,features);mm[name]=m;events.loc[test.index,name]=predict(test,features,m)
  rec['models'][name]=dict(coefficients=dict(zip(['intercept']+features,m['b'])),means=dict(zip(features,m['mu'])),scales=dict(zip(features,m['sd'])),iterations=m['iterations'],design_rank=m['rank'])
 # Common main-column normalization is identical, so zeroing interactions exactly embeds additive scores.
 assert np.array_equal(mm['ADDITIVE']['mu'],mm['INTERACTION']['mu'][:len(BASE)])
 assert np.array_equal(mm['ADDITIVE']['sd'],mm['INTERACTION']['sd'][:len(BASE)])
 full0=mm['INTERACTION'].copy();full0['b']=np.r_[mm['ADDITIVE']['b'],np.zeros(3)]
 assert np.allclose(predict(test,FULL,full0),predict(test,BASE,mm['ADDITIVE']),atol=1e-14,rtol=0)
 nested.append(dict(month=month,additive_rank=mm['ADDITIVE']['rank'],interaction_rank=mm['INTERACTION']['rank'],rank_gain=mm['INTERACTION']['rank']-mm['ADDITIVE']['rank'],zero_interactions_recover_additive=True))
 if month in ['2022-01','2024-10','2026-01']:
  z=events.copy();z.loc[z.maturity5.ge(cut),'ret5']=999.
  tr=z[z.common_features_known&z.complete5&z.t.ge(cut-252)&z.maturity5.lt(cut)]
  for name,features in [('ADDITIVE',BASE),('INTERACTION',FULL)]:
   m2=fit(tr,features);assert np.array_equal(m2['b'],mm[name]['b'])
   poison.append(dict(month=month,model=name,future_label_poison_exact=True))
 fits.append(rec)
dump('MONTHLY_MODELS.json',fits);dump('NESTED_DESIGN_CHECKS.json',nested);dump('FUTURE_LABEL_POISON_CHECKS.json',poison)
p=events[events.year.ge(2022)].copy();p.to_parquet(O/'FORWARD_PREDICTIONS.parquet',index=False)
selections=[];queues=[]
for day,g in p.groupby('day',sort=True):
 b=g.sort_values(['PVR','H1','sid'],ascending=[False,False,True],na_position='last');slots=list(b.index);K=min(20,len(b));can=b.ADDITIVE.notna()&b.PVR.notna()
 assert np.array_equal(b.ADDITIVE.notna(),b.INTERACTION.notna())
 orders={'PVR':slots}
 for name in ['ADDITIVE','INTERACTION']:
  ranked=b[can].sort_values([name,'PVR','sid'],ascending=[False,False,True]);it=iter(ranked.index)
  orders[name]=[next(it) if can.loc[i] else i for i in slots]
  assert all(i==orders[name][k] for k,i in enumerate(slots) if not can.loc[i])
 for name,order in orders.items():
  z=p.loc[order[:K]].copy();z['strategy']=name;z['selected_rank']=range(1,K+1);selections.append(z)
 queues.append(dict(day=day,year=int(day[:4]),N=len(g),K=K,known=int(can.sum()),interaction_vs_additive_replaced=K-len(set(orders['INTERACTION'][:K])&set(orders['ADDITIVE'][:K]))))
selected=pd.concat(selections,ignore_index=True);queues=pd.DataFrame(queues)
selected.to_parquet(O/'FROZEN_SELECTIONS.parquet',index=False);queues.to_csv(O/'QUEUES.csv',index=False)
oldsel=pd.read_parquet(P/'FROZEN_SELECTIONS.parquet');oldkeys=set(zip(oldsel[oldsel.strategy.eq('PVR')].sid,oldsel[oldsel.strategy.eq('PVR')].day))
assert oldkeys==set(zip(selected[selected.strategy.eq('PVR')].sid,selected[selected.strategy.eq('PVR')].day))
def met(g):
 out=dict(n=len(g),dates=g.day.nunique(),stocks=g.sid.nunique(),next_one_price_up=int(g.next_one_price_up_bar.sum()),unknown=int(g.ADDITIVE.isna().sum()))
 for H in [5,20]:
  z=g[g[f'complete{H}']];r=z[f'ret{H}']
  out.update({f'complete{H}':len(z),f'positive{H}':r.gt(0).mean(),f'mean{H}':r.mean(),f'date_mean{H}':z.groupby('day')[f'ret{H}'].mean().mean(),f'q05_{H}':r.quantile(.05),f'es05_{H}':r[r.le(r.quantile(.05))].mean(),f'mean_mae{H}':z[f'mae{H}'].mean()})
  for cost in [.003,.006]:
   nr=(1+r)/(1+cost)-1;out[f'cost{int(cost*1e4)}_mean{H}']=nr.mean();out[f'cost{int(cost*1e4)}_positive{H}']=nr.gt(0).mean()
 return out
annual=[dict(year=y,strategy=s,**met(g)) for (y,s),g in selected.groupby(['year','strategy'])]
pd.DataFrame(annual).to_csv(O/'ANNUAL_RESULTS.csv',index=False)
paired=[];influence_rows=[]
for scope in ['2022_2025']+[str(y) for y in sorted(selected.year.unique())]:
 allg=selected[selected.year.between(2022,2025)] if scope=='2022_2025' else selected[selected.year.eq(int(scope))]
 for H in [5,20]:
  full=allg.groupby('day')[f'complete{H}'].all();gd=allg[allg.day.isin(full[full].index)].copy();D=gd.day.nunique()
  if not D:continue
  gd['net']=(1+gd[f'ret{H}'])/1.003-1
  piv=gd.groupby(['day','strategy']).net.mean().unstack();pos=gd.assign(positive=gd[f'ret{H}'].gt(0)).groupby(['day','strategy']).positive.mean().unstack()
  tmap=gd.groupby('day').t.first();block=tmap//20
  for baseline in ['ADDITIVE','PVR']:
   diff=piv.INTERACTION-piv[baseline];u=(diff-diff.mean())/D;sums=u.groupby(block).sum();G=len(sums);vb=G/(G-1)*np.square(sums).sum() if G>1 else np.nan
   z=gd[gd.strategy.isin(['INTERACTION',baseline])].copy();means=piv.mean();counts=z.groupby(['day','strategy']).sid.transform('size')
   z['influence']=np.where(z.strategy.eq('INTERACTION'),1.,-1.)*(z.net-z.strategy.map(means))/(counts*D);z['block']=z.t//20
   def cv(keys):
    zz=z.groupby(keys).influence.sum();g=len(zz)
    return g/(g-1)*np.square(zz).sum() if g>1 else np.nan
   vs=cv('sid');vbs=cv(['block','sid']);v2=vb+vs-vbs;se=math.sqrt(max(0.,vb));secons=math.sqrt(max(0.,vb,vs,v2))
   rec=dict(scope=scope,horizon=H,baseline=baseline,matched_dates=D,excluded_dates=allg.day.nunique()-D,matched_signal_slots_per_arm=len(gd)//3,blocks=G,mean_cost30_difference=diff.mean(),positive_difference=(pos.INTERACTION-pos[baseline]).mean(),block20_se=se,stock_se=math.sqrt(max(0.,vs)),two_way_variance=v2,conservative_se=secons,bonferroni95_low=diff.mean()-2.2414*se,bonferroni95_high=diff.mean()+2.2414*se,conservative95_low=diff.mean()-2.2414*secons,conservative95_high=diff.mean()+2.2414*secons)
   paired.append(rec)
pd.DataFrame(paired).to_csv(O/'PAIRED_DATE_BLOCK_RESULTS.csv',index=False)
# Root capture never uses labels in selection.
caps={s:set(zip(g.sid,g.day)) for s,g in selected.groupby('strategy')};roots=[]
for root,g in events.groupby('root',sort=False):
 g=g.sort_values('t');b=g.iloc[0]
 if b.year<2022:continue
 early=g[g.t.le(b.t+5)];r=dict(root=root,sid=b.sid,day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60))
 for strategy,keys in caps.items():r[strategy]=any((x.sid,x.day) in keys for x in early.itertuples())
 roots.append(r)
roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_CAPTURE.csv',index=False);big=[]
for y,g in roots.groupby('year'):
 z=g[g.big60]
 for baseline in ['ADDITIVE','PVR']:
  a=z[baseline];b=z.INTERACTION
  big.append(dict(year=y,baseline=baseline,roots=len(g),complete60=int(g.complete60.sum()),big_roots=len(z),baseline_captured=int(a.sum()),interaction_captured=int(b.sum()),retained=int((a&b).sum()),lost=int((a&~b).sum()),added=int((~a&b).sum())))
pd.DataFrame(big).to_csv(O/'BIG_ROOT_RESULTS.csv',index=False)
def auc(g,col,target):
 z=g[[col,target]].dropna();y=z[target].astype(bool);a=int(y.sum());b=len(y)-a
 return float((z[col].rank()[y].sum()-a*(a+1)/2)/(a*b)) if a and b else np.nan
cal=[]
for y,g in p[p.complete5&p.ADDITIVE.notna()].groupby('year'):
 g=g.copy();g['y']=g.ret5.gt(0)
 for name in ['ADDITIVE','INTERACTION']:
  v=np.clip(g[name],1e-12,1-1e-12);da=[auc(z,name,'y') for _,z in g.groupby('day')];da=[v for v in da if np.isfinite(v)]
  cal.append(dict(year=int(y),model=name,n=len(g),auc=auc(g,name,'y'),within_date_auc=np.mean(da),brier=np.mean((v-g.y)**2),logloss=-np.mean(g.y*np.log(v)+(1-g.y)*np.log(1-v)),mean_prediction=v.mean(),observed=g.y.mean()))
pd.DataFrame(cal).to_csv(O/'PROBABILITY_QUALITY.csv',index=False)
counts=events.groupby(['year','category']).agg(n=('sid','size'),known=('common_features_known','sum'),complete5=('complete5','sum'),dates=('day','nunique')).reset_index()
counts.to_csv(O/'CATEGORY_COVERAGE.csv',index=False)
first=pd.read_csv(P/'ORIGINAL_FIRST_ENTRIES_SCORED.csv');j=first.merge(p[['sid','day','ADDITIVE','INTERACTION']],left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='one_to_one',suffixes=('','_new'));j.to_csv(O/'ORIGINAL_FIRST_ENTRIES_SCORED.csv',index=False)
normal=j[j.year.eq(2022)&j.closed_in_entry_year&~j.signal_day.isin(['2022-01-04','2022-06-17'])].copy();normal['win']=normal.round_pnl.gt(0);rr=[]
for model in ['probability5','ADDITIVE','INTERACTION']:
 z=normal[normal[model].notna()]
 rr.append(dict(scope='NORMAL2022_SCORED',model=model,n=len(z),wins=int(z.win.sum()),winrate=z.win.mean(),auc=auc(z,model,'win'),original_path_net=z.round_pnl.sum()))
 for band,b in z.groupby(pd.cut(z[model],[0,.4,.45,.5,.55,.6,1],include_lowest=True),observed=True):
  rr.append(dict(scope=str(band),model=model,n=len(b),wins=int(b.win.sum()),winrate=b.win.mean(),original_path_net=b.round_pnl.sum()))
pd.DataFrame(rr).to_csv(O/'ORIGINAL_ROUND_DESCRIPTIVE.csv',index=False)
summary=dict(status='COMPLETED_SINGLE_NESTED_SIGNAL_DIAGNOSTIC_NOT_ACCOUNT_NOT_UNTOUCHED_OOS',account_runs=0,model_specifications=2,nested_hypothesis_count=1,parameter_searches=0,events=len(events),events_unchanged=True,PVR_selections_unchanged=True,monthly_fits_per_arm=len(fits),common_prediction_masks=True,all_equalK=bool(selected.groupby(['day','strategy']).size().unstack().nunique(axis=1).eq(1).all()),minimum_design_rank_gain=min(r['rank_gain'] for r in nested),maximum_design_rank_gain=max(r['rank_gain'] for r in nested),nested_zero_interaction_checks=len(nested),future_price_prefix_checks=len(feature_checks),future_label_poison_checks=len(poison),selection_slots_replaced_interaction_vs_additive=int(queues.interaction_vs_additive_replaced.sum()),seconds=time.monotonic()-start,freeze_sha256=sha(O/'FREEZE.json'))
dump('SUMMARY.json',summary);dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('SUMMARY',json.dumps(clean(summary)),flush=True)
print('ANNUAL',pd.DataFrame(annual)[['year','strategy','positive5','mean5','positive20','mean20','q05_20']].to_string(index=False),flush=True)
print('PRIMARY',pd.DataFrame(paired).query("scope=='2022_2025'").to_string(index=False),flush=True)
print('BIG',pd.DataFrame(big).to_string(index=False),flush=True)
print('ROUND',pd.DataFrame(rr).query("scope=='NORMAL2022_SCORED'").to_string(index=False),flush=True)

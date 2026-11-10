"""One frozen, signal-only continuation diagnostic. Never imports or runs an account."""
from pathlib import Path
import json,hashlib,time,collections,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
B=O.parent.parent
PYROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full')
MID=B/'account_comparison_continuous_v1/inputs'
LAST=U.parent/'pvr-slot1-native-readiness-20261101'
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
COLS=['protected_distance_over_prior_sigma','z5','prior_sigma20','log_amount_relative21','market_breadth20','market_delta5','original_i_buy']
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
def checked(p,digest=None):
 v=sha(p)
 if digest is not None:assert v==digest,('source drift',str(p),v,digest)
 sources[str(p)]=v
 return pd.read_parquet(p)
start=time.monotonic();freeze=read(O/'FREEZE.json')
assert sha(O/'FREEZE.json')=='352f29ff515cf4a32017d1911e933d91a91fe0a18aad898186503bdd549847a4'
sources={str(p):sha(p) for p in [O/'FREEZE.json',Path(__file__),U/'STOCK_MANIFEST.json',HP,PYROOT/'SCORES_MANIFEST.json',MID/'H1_MANIFEST.json',LAST/'SCORES_MANIFEST.json']}
assert not (O/'SUMMARY.json').exists(),'Never silently rerun this frozen model'
dump('SOURCE_FREEZE_BEFORE_RESULTS.json',sources)
sm=read(U/'STOCK_MANIFEST.json');ids=[r['symbol'] for r in sm]
rm={r['series_id']:r for r in read(RR/'rs-h1-execution-20261025/inputs-v2/input-manifest.json')['series']}
dmap={r['symbol']:r for r in read(PYROOT/'SCORES_MANIFEST.json')['entries']}
mmap={r['sid']:r for r in read(MID/'H1_MANIFEST.json') if not r['industry']}
lmap={r['symbol']:r for r in read(LAST/'SCORES_MANIFEST.json')['entries']}
h=np.load(HP,allow_pickle=False);hd=pd.DatetimeIndex(h['dates'])
use=(hd>='2020-10-01')&(hd<='2026-05-15');days=hd[use];n=len(days)
H=pd.DataFrame(h['score'][use],index=days,columns=h['symbols'])
C=pd.DataFrame(h['close'][use],index=days,columns=h['symbols'])[ids]
S=pd.DataFrame(h['segment'][use],index=days,columns=h['symbols'])[ids]
valid=np.isfinite(C)&C.gt(0);C=C.where(valid)
ma=C.rolling(20,min_periods=20).mean().where(S.eq(S.shift(19)))
known=ma.notna()&C.notna();above=C.gt(ma);pairs=known&known.shift(5,fill_value=False)
breadth=(above&known).sum(axis=1)/known.sum(axis=1).replace(0,np.nan)
delta=((above.astype(int)-above.shift(5,fill_value=False).astype(int))*pairs).sum(axis=1)/pairs.sum(axis=1).replace(0,np.nan)
market=pd.DataFrame({'market_breadth20':breadth,'market_delta5':delta})
market.to_csv(O/'MARKET_CLOCK.csv')
pieces=[];audit=[];qual=collections.Counter()
for no,r in enumerate(sm):
 sid=r['symbol'];refs=r['refs']
 f0=checked(refs['facts'],r['output_sha256'].get(refs['facts']))
 cp0=checked(refs['CP1'],r['output_sha256'].get(refs['CP1']))
 q0=checked(refs['CP1_input'],r['output_sha256'].get(refs['CP1_input']))
 # Reused original files have different future tails; physically cut all inputs to the frozen endpoint first.
 f0=f0.loc[:'2026-05-15'];cp0=cp0.loc[:'2026-05-15'];q0=q0.loc[:'2026-05-15']
 assert f0.index.equals(cp0.index) and f0.index.equals(q0.index),sid
 f=f0.reindex(days);cp=cp0.reindex(days);q=q0.reindex(days)
 # Empty original exports use object dtype. Numeric conversion preserves NA and rejects malformed values.
 for col in ['close','factor','i_floor','segment_id']:f[col]=pd.to_numeric(f[col],errors='raise')
 cp['candidate']=pd.to_numeric(cp['candidate'],errors='raise')
 q['amount']=pd.to_numeric(q['amount'],errors='raise')
 floor=pd.concat([f.i_floor,cp.candidate],axis=1).max(axis=1,skipna=False)
 eligible=cp.receipt.eq(True)&cp.ready.eq(True)&f.i_target.eq(1)&f.e0_ready.eq(1)&f.g_ready.eq(True)&np.isfinite(f.close)&f.close.gt(0)&np.isfinite(f.factor)&f.factor.gt(0)&floor.gt(0)&floor.lt(f.close)
 eligible &= days>=pd.Timestamp('2021-01-01')
 ix=np.flatnonzero(eligible.to_numpy())
 qual['fixed_ids']+=1;qual['ids_with_events']+=int(len(ix)>0)
 if not len(ix):continue
 raw=checked(rm[sid]['raw']['path'],rm[sid]['raw'].get('sha256'))
 raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();assert raw.index.is_unique
 raw=raw.reindex(days)
 rawvalid=np.isfinite(raw.open)&raw.open.gt(0)&np.isfinite(raw.close)&raw.close.gt(0)
 for field in ['observed_bar','price_eligible']:
  if field in raw:rawvalid &= raw[field].eq(True)
 op=raw.open*f.factor
 C1=f.close;seg=f.segment_id
 lr=np.log(C1).diff().where(seg.eq(seg.shift()))
 sig=lr.shift().rolling(20,min_periods=20).std(ddof=0).where(seg.eq(seg.shift(20)))
 z5=np.log(C1/C1.shift(5))/(sig*np.sqrt(5))
 ar=q.amount/q.amount.shift().rolling(21,min_periods=21).median()
 old=checked(PYROOT/'scores'/f'{sid}.parquet',dmap[sid]['output_sha256']).score
 mid=checked(mmap[sid]['score_path'],mmap[sid]['score_sha256']).score
 last=checked(LAST/'scores'/f'{sid}.parquet',lmap[sid]['output_sha256']).score.loc['2025-07-01':]
 pvr=pd.concat([old,mid,last]);assert pvr.index.is_unique
 pvr=pvr.reindex(days)
 i_on=f0.i_target.eq(1);episode=((i_on&~i_on.shift(fill_value=False))|f0.segment_id.ne(f0.segment_id.shift())).cumsum().reindex(days)
 rows=[]
 for t in ix:
  en=t+1
  rr=dict(sid=sid,day=str(days[t].date()),t=int(t),year=int(days[t].year),root=f'{sid}|{int(seg.iloc[t])}|{int(episode.iloc[t])}',PVR=float(pvr.iloc[t]),H1=float(H.at[days[t],sid]),signal_raw_valid=bool(rawvalid.iloc[t]),original_i_buy=float(bool(f.i_buy.iloc[t])),protected_distance_over_prior_sigma=float(np.log(C1.iloc[t]/floor.iloc[t])/sig.iloc[t]),z5=float(z5.iloc[t]),prior_sigma20=float(sig.iloc[t]),log_amount_relative21=float(np.log(ar.iloc[t])) if ar.iloc[t]>0 else np.nan,market_breadth20=float(breadth.iloc[t]),market_delta5=float(delta.iloc[t]),maturity5=int(t+5),entry_day=str(days[en].date()) if en<n else None)
  rr['next_open_known']=bool(en<n and np.isfinite(op.iloc[en]) and op.iloc[en]>0)
  rr['next_zero_or_missing_volume']=bool(en>=n or not np.isfinite(raw.volume.iloc[en]) or raw.volume.iloc[en]<=0)
  rr['next_one_price_bar']=bool(en<n and np.isfinite(raw.high.iloc[en]) and raw.high.iloc[en]==raw.low.iloc[en])
  rr['next_one_price_up_bar']=bool(rr['next_one_price_bar'] and raw.open.iloc[en]>raw.close.iloc[t])
  for horizon in [5,20,60]:
   end=t+horizon
   ok=bool(end<n and rr['next_open_known'] and rawvalid.iloc[en:end+1].all() and np.isfinite(C1.iloc[en:end+1]).all() and C1.iloc[en:end+1].gt(0).all() and seg.iloc[t:end+1].notna().all() and seg.iloc[t:end+1].nunique()==1)
   rr[f'complete{horizon}']=ok
   rr[f'ret{horizon}']=float(C1.iloc[end]/op.iloc[en]-1) if ok else np.nan
   rr[f'mfe{horizon}']=max(0.,float(C1.iloc[en:end+1].max()/op.iloc[en]-1)) if ok else np.nan
   rr[f'mae{horizon}']=min(0.,float(C1.iloc[en:end+1].min()/op.iloc[en]-1)) if ok else np.nan
  rr['big60']=bool(rr['complete60'] and rr['mfe60']>=.3 and rr['ret60']>=.2)
  rows.append(rr)
 pieces.append(pd.DataFrame(rows))
 same=f.close.notna()&H[sid].notna()
 audit.append(dict(sid=sid,events=len(rows),signal_raw_invalid=sum(not r['signal_raw_valid'] for r in rows),features_known=sum(all(np.isfinite(r[c]) for c in COLS) for r in rows),next_open_missing=sum(not r['next_open_known'] for r in rows)))
 if (no+1)%400==0:print('BUILD',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
frame=pd.concat(pieces,ignore_index=True).sort_values(['t','sid']).reset_index(drop=True)
frame['features_known']=np.isfinite(frame[COLS]).all(axis=1)
frame.to_parquet(O/'SIGNAL_EVENTS_WITH_LABELS.parquet',index=False)
pd.DataFrame(audit).to_csv(O/'SOURCE_COVERAGE.csv',index=False)
dump('SOURCE_HASHES.json',sources)
print('EVENTS',len(frame),'train2021',int(frame.year.eq(2021).sum()),flush=True)
def sigmoid(z):
 z=np.clip(z,-35,35);return 1/(1+np.exp(-z))
def fit(train):
 x=train[COLS].to_numpy(float);y=train.ret5.gt(0).to_numpy(float)
 mu=x.mean(axis=0);sd=x.std(axis=0);sd=np.where(sd>1e-12,sd,1.)
 x=np.column_stack([np.ones(len(x)),np.clip((x-mu)/sd,-5,5)])
 b=np.zeros(x.shape[1]);b[0]=math.log((y.sum()+.5)/(len(y)-y.sum()+.5))
 penalty=np.r_[0.,np.repeat(4.,len(COLS))]
 def objective(beta):
  z=x@beta
  return np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(penalty*beta*beta)
 for it in range(100):
  p=sigmoid(x@b);g=x.T@(p-y)+penalty*b
  h=x.T@((p*(1-p))[:,None]*x)+np.diag(penalty)+np.eye(len(b))*1e-10
  step=np.linalg.solve(h,g);old=objective(b);scale=1.
  while scale>1e-8 and objective(b-scale*step)>old+1e-9:scale*=.5
  b=b-scale*step
  if np.max(np.abs(scale*step))<1e-9:break
 assert np.isfinite(b).all() and np.max(np.abs(x.T@(sigmoid(x@b)-y)+penalty*b))<1e-4
 return mu,sd,b,it+1
def predict(g,model):
 mu,sd,b,_=model
 x=np.column_stack([np.ones(len(g)),np.clip((g[COLS].to_numpy(float)-mu)/sd,-5,5)])
 return sigmoid(x@b)
frame['probability5']=np.nan
months=pd.Series(days[days>=pd.Timestamp('2022-01-01')]).groupby(lambda i:str(days[days>=pd.Timestamp('2022-01-01')][i].to_period('M'))).min()
fits=[]
for month,dt in months.items():
 cut=int(days.get_loc(dt))
 train=frame[frame.features_known&frame.complete5&frame.t.ge(cut-252)&frame.maturity5.lt(cut)].copy()
 test=frame[frame.day.str.startswith(month)&frame.features_known]
 known=len(train)>=500 and train.ret5.gt(0).sum()>=50 and train.ret5.le(0).sum()>=50 and train.day.nunique()>=60
 rec=dict(month=month,cutoff_day=str(dt.date()),train_rows=len(train),train_signal_dates=train.day.nunique(),train_wins=int(train.ret5.gt(0).sum()),maximum_maturity_day=str(days[int(train.maturity5.max())].date()) if len(train) else None,test_rows=len(test),known=known)
 if known:
  model=fit(train);frame.loc[test.index,'probability5']=predict(test,model)
  rec.update(intercept=float(model[2][0]),coefficients=dict(zip(COLS,model[2][1:])),training_means=dict(zip(COLS,model[0])),training_scales=dict(zip(COLS,model[1])),iterations=model[3])
  # Future labels cannot be seen by this fit. Refit independently selected prefix at fixed cutoffs.
  if month in ['2022-01','2024-10','2026-01']:
   poisoned=frame.copy();poisoned.loc[poisoned.maturity5.ge(cut),'ret5']=999.
   tr2=poisoned[poisoned.features_known&poisoned.complete5&poisoned.t.ge(cut-252)&poisoned.maturity5.lt(cut)]
   m2=fit(tr2)
   assert np.array_equal(model[2],m2[2])
   rec['future_label_poison_pass']=True
 fits.append(rec)
print('FITS',len(fits),'seconds',round(time.monotonic()-start,1),flush=True)
dump('MONTHLY_MODELS.json',fits)
pred=frame[frame.year.ge(2022)].copy()
selected=[];queue=[]
for d,g in pred.groupby('day',sort=True):
 base=g.sort_values(['PVR','H1','sid'],ascending=[False,False,True],na_position='last')
 slots=list(base.index);can=base.probability5.notna()&base.PVR.notna()
 ready=base[can].sort_values(['probability5','PVR','sid'],ascending=[False,False,True])
 it=iter(ready.index);alt=[next(it) if can.loc[i] else i for i in slots]
 k=min(20,len(g));assert len(set(alt))==len(slots)
 assert all(slots[j]==alt[j] for j in range(len(slots)) if not can.loc[slots[j]])
 for strategy,idx in [('PVR',slots[:k]),('PROBABILITY',alt[:k])]:
  z=pred.loc[idx].copy();z['strategy']=strategy;z['selected_rank']=np.arange(1,len(z)+1);selected.append(z)
 queue.append(dict(day=d,year=int(d[:4]),N=len(g),K=k,known=int(can.sum()),overlap=len(set(slots[:k])&set(alt[:k]))))
selected=pd.concat(selected,ignore_index=True);queues=pd.DataFrame(queue)
selected.to_parquet(O/'FROZEN_SELECTIONS.parquet',index=False);pred.to_parquet(O/'FORWARD_PREDICTIONS.parquet',index=False);queues.to_csv(O/'QUEUES.csv',index=False)
def metric(g):
 out=dict(n=len(g),dates=g.day.nunique(),stocks=g.sid.nunique(),known=int(g.probability5.notna().sum()),next_open_missing=int((~g.next_open_known).sum()),next_one_price_up=int(g.next_one_price_up_bar.sum()),next_zero_volume=int(g.next_zero_or_missing_volume.sum()))
 for h in [5,20,60]:
  z=g[g[f'complete{h}']];r=z[f'ret{h}']
  out.update({f'complete{h}':len(z),f'mean{h}':r.mean(),f'date_mean{h}':z.groupby('day')[f'ret{h}'].mean().mean(),f'positive{h}':r.gt(0).mean() if len(z) else np.nan,f'median{h}':r.median(),f'q05_{h}':r.quantile(.05),f'es05_{h}':r[r<=r.quantile(.05)].mean(),f'mean_mae{h}':z[f'mae{h}'].mean(),f'loss10_{h}':r.le(-.1).mean() if len(z) else np.nan})
  for cost in [.003,.006]:
   nr=(1+r)/(1+cost)-1
   out[f'cost{int(cost*1e4)}bps_mean{h}']=nr.mean();out[f'cost{int(cost*1e4)}bps_positive{h}']=nr.gt(0).mean() if len(z) else np.nan
 return out
annual=[dict(year=y,strategy=s,**metric(g)) for (y,s),g in selected.groupby(['year','strategy'])]
pd.DataFrame(annual).to_csv(O/'ANNUAL_SIGNAL_RESULTS.csv',index=False)
# Matched fully observed selection dates. These are conditional sensitivity results; missing dates remain separately reported.
paired=[]
for y,gy in selected.groupby('year'):
 for h in [5,20]:
  rows=[]
  for d,g in gy.groupby('day'):
   if not g[f'complete{h}'].all():continue
   a=g[g.strategy.eq('PROBABILITY')][f'ret{h}'];b=g[g.strategy.eq('PVR')][f'ret{h}']
   rows.append(dict(day=d,t=int(g.t.iloc[0]),diff=float(a.mean()-b.mean()),positive_diff=float(a.gt(0).mean()-b.gt(0).mean())))
  z=pd.DataFrame(rows)
  if len(z):
   block=(z.t-z.t.min())//20;u=z['diff']-z['diff'].mean();sums=u.groupby(block).sum();G=len(sums)
   se=math.sqrt(G/(G-1)*np.square(sums).sum()/len(z)**2) if G>1 else np.nan
   paired.append(dict(year=y,horizon=h,matched_dates=len(z),excluded_dates=gy.day.nunique()-len(z),mean_difference=z['diff'].mean(),positive_difference=z.positive_diff.mean(),blocks=G,block20_se=se,approx95_low=z['diff'].mean()-1.96*se,approx95_high=z['diff'].mean()+1.96*se))
pd.DataFrame(paired).to_csv(O/'MATCHED_DATE_BLOCK_RESULTS.csv',index=False)
# Frozen probability calibration; no calibration fit on evaluated labels.
cal=[];bins=np.arange(0,1.0001,.1)
for y,g in pred[pred.complete5&pred.probability5.notna()].groupby('year'):
 p=np.clip(g.probability5.to_numpy(),1e-12,1-1e-12);yy=g.ret5.gt(0).to_numpy(float)
 cal.append(dict(year=y,bin='ALL',n=len(g),predicted=p.mean(),observed=yy.mean(),brier=np.mean((p-yy)**2),logloss=-np.mean(yy*np.log(p)+(1-yy)*np.log(1-p))))
 for label,z in g.groupby(pd.cut(g.probability5,bins,include_lowest=True),observed=True):
  cal.append(dict(year=y,bin=str(label),n=len(z),predicted=z.probability5.mean(),observed=z.ret5.gt(0).mean()))
pd.DataFrame(cal).to_csv(O/'CALIBRATION.csv',index=False)
# First candidate of each native I episode, never hindsight best start.
captures={s:set(zip(g.sid,g.day)) for s,g in selected.groupby('strategy')}
roots=[]
for root,g in frame.groupby('root',sort=False):
 g=g.sort_values('t');b=g.iloc[0]
 if b.year<2022:continue
 early=g[g.t.le(b.t+5)]
 rr=dict(root=root,sid=b.sid,day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60))
 for strategy,keys in captures.items():rr[strategy]=any((r.sid,r.day) in keys for r in early.itertuples())
 roots.append(rr)
roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_CAPTURE.csv',index=False)
big=[]
for y,g in roots.groupby('year'):
 z=g[g.big60];a=z.PVR;b=z.PROBABILITY
 big.append(dict(year=y,roots=len(g),mature_roots=int(g.complete60.sum()),big_roots=len(z),PVR_captured=int(a.sum()),probability_captured=int(b.sum()),retained=int((a&b).sum()),lost=int((a&~b).sum()),added=int((~a&b).sum())))
pd.DataFrame(big).to_csv(O/'BIG_ROOT_RESULTS.csv',index=False)
# Descriptive original-policy round outcomes, never new-policy returns.
first=pd.read_csv(O.parent/'ALL_FIRST_ENTRIES.csv');first=first[first.account.eq('PVR')]
j=first.merge(pred[['sid','day','probability5','PVR']],left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='one_to_one')
j['in_CP_domain']=j.day.notna();j['score_known']=j.probability5.notna()
same=j[j.in_CP_domain&j.PVR_decision.notna()&j.PVR.notna()]
assert len(same)>0 and np.max(np.abs(same.PVR_decision-same.PVR))<1e-7,'original PVR score source mismatch'
j.to_csv(O/'ORIGINAL_FIRST_ENTRIES_SCORED.csv',index=False)
rmetrics=[]
for (y,kind),g in j.groupby(['year','first_kind']):
 for scope,z in [('ALL_ORIGINAL',g),('MATCHED_KNOWN',g[g.score_known])]:
  for clock,zz in [('closed_by_entry_year',z[z.closed_in_entry_year]),('fully_completed_by_source_end',z[z.closed])]:
   for band,bb in [('ALL',zz)]+[(str(label),b) for label,b in zz.groupby(pd.cut(zz.probability5,[0,.4,.45,.5,.55,.6,1],include_lowest=True),observed=True)]:
    rmetrics.append(dict(year=y,kind=kind,scope=scope,completion_clock=clock,probability_band=band,n=len(bb),wins=int(bb.round_pnl.gt(0).sum()),winrate=bb.round_pnl.gt(0).mean() if len(bb) else np.nan,original_path_net=bb.round_pnl.sum(),mean_original_round_return=bb.round_return_on_cumulative_cost.mean(),mean_prediction=bb.probability5.mean()))
pd.DataFrame(rmetrics).to_csv(O/'ORIGINAL_ROUND_DESCRIPTIVE.csv',index=False)
summary=dict(status='SIGNAL_ONLY_FROZEN_FORWARD_DIAGNOSTIC_NOT_ACCOUNT_NOT_INDEPENDENT_OOS',account_runs=0,model_specs=1,parameter_searches=0,seconds=time.monotonic()-start,events=len(frame),training2021=int(frame.year.eq(2021).sum()),training2021_mature_before2022=int((frame.year.eq(2021)&frame.complete5&frame.maturity5.lt(days.get_loc(pd.Timestamp('2022-01-04')))).sum()),event_by_year=frame.groupby('year').size().to_dict(),full_prediction_years=pred.groupby('year').probability5.count().to_dict(),original_first_entries=len(j),matched_CP_domain=int(j.in_CP_domain.sum()),matched_score_known=int(j.score_known.sum()),all_equalK=bool(selected.groupby(['day','strategy']).size().unstack().nunique(axis=1).eq(1).all()),source_freeze_hash=sha(O/'FREEZE.json'),frozen_selections_hash=sha(O/'FROZEN_SELECTIONS.parquet'),limitations=freeze['PIT_limit'],no_calibration_refit=True)
dump('SUMMARY.json',summary)
dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('SUMMARY',json.dumps(clean(summary)),flush=True)
print('ANNUAL',pd.DataFrame(annual)[['year','strategy','n','positive5','mean5','positive20','mean20','q05_20','next_one_price_up']].to_string(index=False),flush=True)
print('PAIRED',pd.DataFrame(paired).to_string(index=False),flush=True)
print('BIG',pd.DataFrame(big).to_string(index=False),flush=True)

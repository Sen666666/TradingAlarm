from pathlib import Path
import json,hashlib,sys,time
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/supported_trajectory_risk_v1')
D=O.parent
M=D/'mobile_candidate_response_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
PY='/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,x): (O/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def score_one(f,dates):
 f=f.reindex(dates)
 p=np.log(f.close.where(f.close>0))
 x=np.arange(21,dtype=float);xc=x-x.mean();xx=(xc*xc).sum()
 beta=p.shift(1).rolling(21,min_periods=21).apply(lambda a:np.dot(xc,a)/xx,raw=True)
 mean=p.shift(1).rolling(21,min_periods=21).mean()
 pred=mean+11*beta
 # No cross-source mixing, including current close. Full 22 common dates required.
 segment=f.segment_id
 continuous=segment.rolling(22,min_periods=22).min().eq(segment.rolling(22,min_periods=22).max())
 return pd.DataFrame({'close':f.close,'beta':beta.where(continuous),'pred_t':pred.where(continuous),'prior_ret20':f.close.shift(1)/f.close.shift(21)-1})
def order(c):
 out=[];queue=[]
 for (a,day),g in c.groupby(['account','day'],sort=True):
  base=g.sort_values(['original_priority_rank','sid'])
  original=list(base.index)
  alt=original.copy()
  for sector,sg in base.groupby('sector',sort=False):
   slots=[j for j,i in enumerate(original) if c.at[i,'sector']==sector and c.at[i,'known']]
   known=sg[sg.known].copy()
   known['q12']=known.Q.round(12);known['pvr12']=known.original_PVR.round(12)
   new=known.sort_values(['q12','pvr12','original_priority_rank','sid'],ascending=[False,False,True,True]).index.tolist()
   assert len(slots)==len(new)
   for pos,idx in zip(slots,new):alt[pos]=idx
  assert set(alt)==set(original)
  assert all(i==alt[j] for j,i in enumerate(original) if not c.at[i,'known'])
  K=min(20,len(g))
  assert base.iloc[:K].sector.value_counts().to_dict()==c.loc[alt[:K]].sector.value_counts().to_dict()
  for strategy,ix in [('PVR',original[:K]),('STR',alt[:K])]:
   for j,i in enumerate(ix):out.append({'row_id':i,'strategy':strategy,'selected_rank':j+1})
  queue.append(dict(account=a,day=day,N=len(g),K=K,known=int(g.known.sum()),overlap=len(set(original[:K])&set(alt[:K]))))
 return pd.DataFrame(out),pd.DataFrame(queue)
def prepare():
 start=time.monotonic()
 freeze=dict(name='SUPPORTED_TRAJECTORY_RISK_STR_v1',status='ONE_FORMULA_FROZEN_BEFORE_NEW_FEATURE_AND_LABEL_RESULTS_NOT_OOS',clock='At signal close t. 21 prior COMMON trading days t-21..t-1, excluding current close from regression, same source segment through t; earliest price anchor next common market open. No future inputs.',formula='p_j=log(native C_j); regress p[t-21:t-1] on x=0..20. beta=sum((x-10)*p)/770; pred_t=mean(p)+11*beta; e=log(C_t)-pred_t; U20=20*beta-e; risk=log(C_t/original pending floor); Q=U20/risk. Require complete same-source 22 closes and 0<floor<C. No truncation, epsilon, gate, sign flip or fit to future labels. U20 is a trajectory extrapolation hypothesis, not expected return or probability.',policy='Original legal empty MOBILE candidate domain; original same-day K=min(20,N). Reorder only known Q and PVR slots WITHIN ORIGINAL SECTOR by Q round12 desc, PVR round12 desc, original priority and sid. Unknown retains exact slot. Preserves baseline daily sector quotas and K. Not actual budgets, eligibility or account replay.',comparison='PVR is primary, E31 separate sensitivity. 2022,2023,2024,2025 and partial2026 separate; all quarters; common complete dates. 20-day date-block uncertainty without random stock selection. Primary horizon20, horizon5/60 secondary. Fixed 30bp cost proxy separate from gross.',right_tail='Reuse original roots account/sid/epoch; earliest legal candidate birth; full60 max close up>=30% and terminal>=20% posthoc only. Capture in first6 common days. Report losses and additions independently, fixed 924 and semiconductor windows, original complete round winners separately diagnostic only.',training='No fitted cross-stock parameters, no training labels, no tuning grid. Windows21 and20 fixed before calculation; seen history remains development, cannot call OOS.',stop='No promotion if 2022-2025 primary common-date difference nonpositive or block95 lower<=0, any complete year primary mean difference<0, or baseline big-root retention<95%. Any failure stops candidate; do not change formula after results.',accounts=0)
 dump('FREEZE.json',freeze)
 source={str(p):sha(p) for p in [U,M/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',O/'FREEZE.json',Path(__file__)]}
 dump('SOURCE_BEFORE_FEATURES.json',source)
 c=pd.read_parquet(M/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
 c.index.name='row_id';c['floor_num']=pd.to_numeric(c.floor)
 h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)
 dates=pd.DatetimeIndex(h['dates']);cal={str(d.date()):i for i,d in enumerate(dates)}
 c['t']=c.day.map(cal);sm={r['symbol']:r for r in json.loads(U.read_text())};features=[];audit=[];tests=[]
 for no,(sid,g) in enumerate(c.groupby('sid',sort=True)):
  p=Path(sm[sid]['refs']['facts']);f=pd.read_parquet(p)
  expected=sm[sid].get('output_sha256',{}).get(str(p))
  actual=sha(p);assert expected is None or actual==expected
  z=score_one(f,dates);ds=pd.DatetimeIndex(g.day);v=z.reindex(ds).copy();v.index=g.index
  features.append(v)
  audit.append(dict(sid=sid,path=str(p),sha256=actual,manifest_hash_known=expected is not None))
  if no%100==0:
   for cutoff in [g.day.min(),g.day.max()]:
    past=score_one(f.loc[:cutoff],dates[dates<=cutoff]);full=z.loc[:cutoff]
    err=(past.beta-full.beta).abs().max()
    assert np.allclose(past.beta,full.beta,atol=1e-13,rtol=0,equal_nan=True)
    assert np.allclose(past.pred_t,full.pred_t,atol=1e-13,rtol=0,equal_nan=True)
    tests.append(dict(sid=sid,cutoff=cutoff,beta_max_error=float(err) if np.isfinite(err) else None,pass_check=True))
  if (no+1)%400==0:print('FEATURE_STOCKS',no+1,round(time.monotonic()-start,1),flush=True)
 c=c.join(pd.concat(features))
 c['extension']=np.log(c.close)-c.pred_t
 c['reward20']=20*c.beta-c.extension
 c['risk']=np.log(c.close/c.floor_num).where((c.floor_num>0)&(c.floor_num<c.close))
 c['Q']=c.reward20/c.risk
 c['known']=np.isfinite(c.Q)&np.isfinite(c.original_PVR)
 selected,queues=order(c)
 c.to_parquet(O/'SEALED_SCORES.parquet');selected.to_parquet(O/'SEALED_SELECTIONS.parquet',index=False)
 queues.to_csv(O/'QUEUE_CHECKS.csv',index=False);pd.DataFrame(audit).to_csv(O/'NATIVE_SOURCE_AUDIT.csv',index=False)
 dump('PREFIX_CHECKS.json',tests)
 dump('SEAL_BEFORE_LABELS.json',dict(scores=sha(O/'SEALED_SCORES.parquet'),selections=sha(O/'SEALED_SELECTIONS.parquet'),features_hashes=source,score_rows=len(c),known_rows=int(c.known.sum()),source_stocks=len(audit),prefix_checks=len(tests),seconds=time.monotonic()-start,account_runs=0))
 print('SCORE_STAGE_DONE',len(c),int(c.known.sum()),'prefix',len(tests),flush=True)
def evaluate():
 seal=json.loads((O/'SEAL_BEFORE_LABELS.json').read_text())
 assert sha(O/'SEALED_SCORES.parquet')==seal['scores'];assert sha(O/'SEALED_SELECTIONS.parquet')==seal['selections']
 c=pd.read_parquet(O/'SEALED_SCORES.parquet').reset_index()
 selections=pd.read_parquet(O/'SEALED_SELECTIONS.parquet')
 l=pd.read_parquet(M/'FIXED_NATIVE_PRICE_LABELS.parquet').drop(columns='t')
 c=c.merge(l,on=['sid','day'],how='left',validate='many_to_one')
 c['quarter']=pd.to_datetime(c.day).dt.to_period('Q').astype(str)
 s=selections.merge(c,on='row_id',validate='many_to_one')
 rows=[];paired=[]
 for (a,y,strategy),g in s.groupby(['account','year','strategy']):
  for H in [5,20,60]:
   z=g[g['complete'+str(H)]]
   rows.append(dict(account=a,year=y,strategy=strategy,horizon=H,selected=len(g),complete=len(z),dates=z.day.nunique(),event_mean=z['ret'+str(H)].mean(),day_mean=z.groupby('day')['ret'+str(H)].mean().mean(),path_positive=z['ret'+str(H)].gt(0).mean(),mae=z['mae'+str(H)].mean(),mfe=z['mfe'+str(H)].mean(),worst5_mean=z['ret'+str(H)].nsmallest(max(1,int(np.ceil(len(z)*.05)))).mean()))
 for (a,d),g in s.groupby(['account','day']):
  for H in [5,20,60]:
   if not g['complete'+str(H)].all():continue
   z=g.groupby('strategy').agg(ret=('ret'+str(H),'mean'),mae=('mae'+str(H),'mean'),mfe=('mfe'+str(H),'mean'))
   p=g.assign(pos=g['ret'+str(H)].gt(0)).groupby('strategy').pos.mean()
   paired.append(dict(account=a,day=d,year=int(d[:4]),quarter=g.quarter.iloc[0],t=int(g.t.iloc[0]),horizon=H,PVR=z.at['PVR','ret'],STR=z.at['STR','ret'],diff=z.at['STR','ret']-z.at['PVR','ret'],mae_diff=z.at['STR','mae']-z.at['PVR','mae'],mfe_diff=z.at['STR','mfe']-z.at['PVR','mfe'],pos_diff=p['STR']-p['PVR']))
 annual=pd.DataFrame(rows);p=pd.DataFrame(paired)
 annual.to_csv(O/'ANNUAL_PATHS.csv',index=False);p.to_csv(O/'COMMON_COMPLETE_DATE_DETAILS.csv',index=False)
 pr=p.groupby(['account','year','horizon']).agg(dates=('day','size'),PVR=('PVR','mean'),STR=('STR','mean'),diff=('diff','mean'),mae_diff=('mae_diff','mean'),mfe_diff=('mfe_diff','mean'),pos_diff=('pos_diff','mean')).reset_index();pr.to_csv(O/'ANNUAL_COMMON_DATES.csv',index=False)
 p.groupby(['account','quarter','horizon']).agg(dates=('day','size'),diff=('diff','mean'),mae_diff=('mae_diff','mean'),pos_diff=('pos_diff','mean')).reset_index().to_csv(O/'QUARTER_COMMON_DATES.csv',index=False)
 # Deterministic date-cluster sandwich, no stock randomization. Fixed blocks of20 common calendar dates.
 blocks=[]
 for (a,H),g in p[p.year<=2025].groupby(['account','horizon']):
  dif=g['diff'].mean();block=(g.t//20);tot=(g['diff']-dif).groupby(block).sum();B=len(tot);N=len(g);se=np.sqrt((B/(B-1))*(tot*tot).sum())/N
  blocks.append(dict(account=a,horizon=H,dates=N,blocks=B,diff=dif,se=se,lo95=dif-1.96*se,hi95=dif+1.96*se))
 pd.DataFrame(blocks).to_csv(O/'DATE_BLOCK_INFERENCE.csv',index=False)
 lookup={strategy:set(zip(g.account,g.day,g.sid,g.epoch))for strategy,g in s.groupby('strategy')}
 roots=[]
 for(a,sid,ep),g in c.groupby(['account','sid','epoch'],dropna=False):
  g=g.sort_values('t');b=g.iloc[0];early=g[g.t<=b.t+5]
  r=dict(account=a,sid=sid,epoch=ep,birth_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc))
  for st,keys in lookup.items():r[st]=any((a,x.day,sid,ep)in keys for x in early.itertuples())
  roots.append(r)
 roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_COVERAGE.csv',index=False);rr=[]
 for(a,y),g in roots.groupby(['account','year']):
  b=g[g.big60];rr.append(dict(account=a,year=y,roots=len(g),big=len(b),PVR=int(b.PVR.sum()),STR=int(b.STR.sum()),lost=int((b.PVR&~b.STR).sum()),added=int((~b.PVR&b.STR).sum()),retained=(b.PVR&b.STR).sum()/b.PVR.sum() if b.PVR.any() else None))
 pd.DataFrame(rr).to_csv(O/'ANNUAL_ROOT_COVERAGE.csv',index=False)
 # Fixed named market windows selected ex ante from task history; no winner-dependent window search.
 ww=[]
 for window,lo,hi in [('924','2024-09-19','2024-10-08'),('semiconductor_period','2025-12-15','2026-01-23')]:
  z=p[(p.day>=lo)&(p.day<=hi)]
  for(a,H),g in z.groupby(['account','horizon']):ww.append(dict(window=window,account=a,horizon=H,dates=len(g),PVR=g.PVR.mean(),STR=g.STR.mean(),diff=g['diff'].mean(),mae_diff=g.mae_diff.mean()))
 pd.DataFrame(ww).to_csv(O/'FIXED_MARKET_WINDOWS.csv',index=False)
 # Old complete round winners are descriptive: losing original membership, not new-strategy rounds.
 f=pd.read_csv(D/'ALL_FIRST_ENTRIES.csv')
 f=f.merge(c[['account','sid','day','row_id']],left_on=['account','sid','signal_day'],right_on=['account','sid','day'],how='left',validate='many_to_one')
 for st in ['PVR','STR']:f['selected_'+st]=f.row_id.isin(set(selections.loc[selections.strategy==st,'row_id']))
 f.to_csv(O/'ORIGINAL_FIRST_ROUND_MEMBERSHIP.csv',index=False)
 s.to_parquet(O/'SELECTED_WITH_LABELS.parquet',index=False)
 print('ANNUAL_COMMON_DATES');print(pr.to_string(index=False));print('BLOCKS');print(pd.DataFrame(blocks).to_string(index=False));print('ROOTS');print(pd.DataFrame(rr).to_string(index=False));print('WINDOWS');print(pd.DataFrame(ww).to_string(index=False))
 dump('SUMMARY.json',dict(status='COMPLETE_ONE_FROZEN_OPPORTUNITY_TEST_NO_ACCOUNT',account_runs=0,parameter_searches=0,original_indicator_runs=0,score_rows=len(c),selected_rows=len(s),before_label_seal_verified=True))
if __name__=='__main__':
 if sys.argv[1]=='score':prepare()
 elif sys.argv[1]=='evaluate':evaluate()

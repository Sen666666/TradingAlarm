
"""Frozen MOBILE-only offline ranking experiment. Does not import an account engine."""
from pathlib import Path
import json,hashlib,time
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/mobile_candidate_response_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
R=O.parents[1]/'account_comparison_continuous_v1'
def read(p):return json.loads(Path(p).read_text())
def dump(n,v):(O/n).write_text(json.dumps(v,indent=2,ensure_ascii=False,default=str))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze=read(O/'FREEZE.json');assert freeze['K']==20
source={str(p):sha(p)for p in [O/'FREEZE.json',O/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',Path(__file__)]}
dump('EXPERIMENT_SOURCE_BEFORE_LABELS.json',source)
started=time.monotonic()
c=pd.read_parquet(O/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)
all_days=pd.DatetimeIndex(h['dates']);use=(all_days>='2022-01-01')&(all_days<='2026-05-15');days=all_days[use];syms=list(h['symbols']);n=len(days)
hclose=pd.DataFrame(h['close'][use],index=days,columns=syms)
cal={str(d.date()):i for i,d in enumerate(days)}
m=pd.read_csv(O.parent/'MARKET_FIXED1709_WARM.csv',index_col=0);c['market_state']=c.day.map(m.regime);c['t']=c.day.map(cal).astype(int)
assert c.market_state.notna().all()
sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
rawm={r['series_id']:r for r in read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json')['series']}
keys=c[['sid','day','t']].drop_duplicates();parts=[];checks=[]
for no,(sid,g)in enumerate(keys.groupby('sid')):
 f=pd.read_parquet(sm[sid]['refs']['facts']).reindex(days)
 raw=pd.read_parquet(rawm[sid]['raw']['path']);raw.index=pd.to_datetime(raw.trade_date);assert raw.index.is_unique
 raw=raw.reindex(days);fac=f.factor.to_numpy(float);op=raw.open.to_numpy(float)*fac
 C=hclose[sid].to_numpy(float);fc=f.close.to_numpy(float);valid=np.isfinite(C)&(C>0)
 same=np.isfinite(C)&np.isfinite(fc);err=np.max(np.abs(C[same]-fc[same]))if same.any()else 0
 assert err<1e-7,(sid,'H1/original-facts-close',err)
 rows=[]
 for r in g.itertuples():
  t=r.t;en=t+1;openknown=bool(en<n and np.isfinite(op[en])and op[en]>0)
  q=dict(sid=sid,day=r.day,t=t,entry_index=en,entry_day=str(days[en].date())if en<n else None,entry_adjusted_open=float(op[en])if openknown else np.nan,entry_raw_open=float(raw.open.iloc[en])if openknown else np.nan,open_known=openknown)
  for H in [1,3,5,10,20,60]:
   end=t+H;ok=bool(openknown and end<n and valid[en:end+1].all())
   q['complete'+str(H)]=ok;q['maturity'+str(H)]=end if end<n else n+H
   q['ret'+str(H)]=float(C[end]/op[en]-1)if ok else np.nan
   q['logret'+str(H)]=float(np.log(C[end]/op[en]))if ok else np.nan
   q['mfe'+str(H)]=max(0,float(C[en:end+1].max()/op[en]-1))if ok else np.nan
   q['mae'+str(H)]=min(0,float(C[en:end+1].min()/op[en]-1))if ok else np.nan
  q['big60_posthoc']=bool(q['complete60']and q['mfe60']>=.3 and q['ret60']>=.2)
  rows.append(q)
 parts.append(pd.DataFrame(rows));checks.append(dict(sid=sid,source_close_max_error=err))
 if(no+1)%400==0:print('LABEL_STOCKS',no+1,'seconds',round(time.monotonic()-started,1),flush=True)
labels=pd.concat(parts,ignore_index=True);labels.to_parquet(O/'FIXED_NATIVE_PRICE_LABELS.parquet',index=False)
pd.DataFrame(checks).to_csv(O/'PRICE_SOURCE_CHECKS.csv',index=False)
c=c.merge(labels,on=['sid','day','t'],validate='many_to_one')
# Validate original actual first MOBILE fills against the raw source open.
first=pd.read_csv(O.parent/'ALL_FIRST_ENTRIES.csv');first=first[first.first_kind=='add']
j=first.merge(labels,left_on=['sid','signal_day'],right_on=['sid','day'],validate='many_to_one')
assert len(j)==len(first)==3601
assert j.entry_raw_open.notna().all()
rawopenerr=float((j.first_raw_open-j.entry_raw_open).abs().max());assert rawopenerr<1e-8
def estimate(frame):
 """Rows are signal-day x sector/state. All rolling values shifted five dates."""
 z=frame[frame.complete5]
 sec=z.groupby(['t','sector','market_state'],observed=True).logret5.mean().unstack(['sector','market_state']).reindex(range(n))
 glob=z.groupby(['t','market_state'],observed=True).logret5.mean().unstack('market_state').reindex(range(n))
 # [t-252,t-5] inclusive = 248 signal dates, all five-session labels mature.
 smean=sec.rolling(248,min_periods=1).mean().shift(5)
 sn=sec.rolling(248,min_periods=1).count().shift(5).fillna(0)
 gmean=glob.rolling(248,min_periods=1).mean().shift(5)
 gn=glob.rolling(248,min_periods=1).count().shift(5).fillna(0)
 out=[]
 for r in frame.itertuples():
  key=(r.sector,r.market_state);mug=gmean.at[r.t,r.market_state]if r.market_state in gmean else np.nan
  ns=float(sn.at[r.t,key])if key in sn else 0
  mus=float(smean.at[r.t,key])if key in smean else np.nan
  mu=(ns*mus+20*mug)/(ns+20)if ns>0 and np.isfinite(mug)else mug
  out.append((mu,ns,gn.at[r.t,r.market_state]if r.market_state in gn else 0,mus,mug))
 return np.array(out,float)
scores=[]
for a,g in c.groupby('account',sort=False):
 g=g.sort_values(['t','original_priority_rank','sid']).copy()
 v=estimate(g)
 for k,col in enumerate(['mu','sector_training_dates','market_training_dates','sector_mean','market_mean']):g[col]=v[:,k]
 scores.append(g)
sc=pd.concat(scores,ignore_index=True)
sc['model_known']=np.isfinite(sc.mu)&np.isfinite(sc.original_PVR)
# One pair of full queue orders; no labels participate in this function.
def orders(g):
 base=g.sort_values(['original_priority_rank','sid'])
 ix=list(base.index);known=base.model_known
 ready=base[known].copy();ready['PVR_round12']=ready.original_PVR.round(12)
 ready=ready.sort_values(['mu','PVR_round12','original_priority_rank','sid'],ascending=[False,False,True,True])
 it=iter(ready.index);alt=[next(it)if bool(base.at[i,'model_known'])else i for i in ix]
 assert set(ix)==set(alt)
 assert all(i==alt[j]for j,i in enumerate(ix)if not bool(base.at[i,'model_known']))
 return ix,alt
sel=[];moves=[];queues=[]
for(a,d),g in sc.groupby(['account','day'],sort=True):
 base,alt=orders(g);K=min(20,len(base))
 for strategy,ix in [('ORIGINAL_PVR',base[:K]),('MOBILE_RESPONSE',alt[:K])]:
  z=sc.loc[ix].copy();z['strategy']=strategy;z['selected_rank']=range(1,len(z)+1);sel.append(z)
 basepos={i:k for k,i in enumerate(base)};altpos={i:k for k,i in enumerate(alt)}
 for i in base:
  if basepos[i]!=altpos[i]:moves.append(dict(account=a,day=d,sid=sc.at[i,'sid'],old_slot=basepos[i],new_slot=altpos[i],mu=sc.at[i,'mu']))
 queues.append(dict(account=a,day=d,N=len(base),K=K,model_known=int(g.model_known.sum()),unknown=int((~g.model_known).sum()),top_overlap=len(set(base[:K])&set(alt[:K])),added=len(set(alt[:K])-set(base[:K])),mean_sector_training_dates=g.sector_training_dates.mean()))
selected=pd.concat(sel,ignore_index=True);selected.to_parquet(O/'SEALED_SAME_K_SELECTIONS.parquet',index=False)
sc.to_parquet(O/'CANDIDATE_SCORES.parquet',index=False)
pd.DataFrame(queues).to_csv(O/'QUEUE_COUNTS.csv',index=False)
pd.DataFrame(moves).to_parquet(O/'RANK_MOVES.parquet',index=False)
dump('RANK_SEAL.json',dict(source=source,selections_sha256=sha(O/'SEALED_SAME_K_SELECTIONS.parquet'),score_sha256=sha(O/'CANDIDATE_SCORES.parquet'),rank_label_columns=['mu','original_PVR','original_priority_rank','sid'],maturity_condition='tau+5<=t and tau>=t-252',actual_first_mobile_open_checks=len(j),max_actual_raw_open_error=rawopenerr))
# Physical future label mutation, testing all candidates on each fixed cutoff.
tests=[]
for a in ['PVR','E31']:
 orig=sc[sc.account==a].sort_values(['t','original_priority_rank','sid']).copy()
 for cutoff in ['2022-03-31','2024-09-24','2026-01-15']:
  t=cal[cutoff];q=orig.copy();q.loc[q.maturity5>t,'logret5']=99999
  v=estimate(q);old=orig.loc[orig.t<=t,'mu'].to_numpy();new=v[q.t<=t,0]
  assert np.allclose(old,new,rtol=0,atol=1e-12,equal_nan=True)
  tests.append(dict(account=a,cutoff=cutoff,prefix_candidates=int((orig.t<=t).sum()),future_mutated=int((q.maturity5>t).sum()),max_prefix_error=float(np.nanmax(np.abs(old-new)))if np.isfinite(old).any()else 0,passed=True))
dump('FUTURE_LABEL_POISON_TESTS.json',tests)
def met(g):
 r=dict(selected=len(g),signal_days=g.day.nunique(),stocks=g.sid.nunique(),big60_events=int(g.big60_posthoc.sum()),complete60=int(g.complete60.sum()))
 for H in [1,3,5,10,20,60]:
  z=g[g['complete'+str(H)]]
  r.update({f'complete{H}':len(z),f'event_mean_ret{H}':z['ret'+str(H)].mean(),f'day_mean_ret{H}':z.groupby('day')['ret'+str(H)].mean().mean(),f'positive_ret{H}':z['ret'+str(H)].gt(0).mean(),f'mean_mfe{H}':z['mfe'+str(H)].mean(),f'mean_mae{H}':z['mae'+str(H)].mean()})
 return r
annual=[dict(account=a,year=y,strategy=s,**met(g))for(a,y,s),g in selected.groupby(['account','year','strategy'])]
pd.DataFrame(annual).to_csv(O/'ANNUAL_SAME_K_OUTCOMES.csv',index=False)
selected['quarter']=pd.to_datetime(selected.day).dt.to_period('Q').astype(str)
quarter=[dict(account=a,quarter=q,strategy=s,**met(g))for(a,q,s),g in selected.groupby(['account','quarter','strategy'])]
pd.DataFrame(quarter).to_csv(O/'QUARTER_SAME_K_OUTCOMES.csv',index=False)
state=[dict(account=a,year=y,market_state=m,strategy=s,**met(g))for(a,y,m,s),g in selected.groupby(['account','year','market_state','strategy'])]
pd.DataFrame(state).to_csv(O/'MARKET_STATE_OUTCOMES.csv',index=False)
# Earliest legal MOBILE candidate of each original root, not best hindsight starting date.
lookup={s:set(zip(g.account,g.day,g.sid,g.epoch))for s,g in selected.groupby('strategy')}
episodes=[]
for(a,sid,ep),g in sc.groupby(['account','sid','epoch']):
 g=g.sort_values('t');b=g.iloc[0];early=g[g.t<=int(b.t)+5]
 row=dict(account=a,sid=sid,epoch=ep,birth_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc),candidate_events=len(g),early_candidate_events=len(early))
 for strategy,ss in lookup.items():row[strategy+'_early_capture']=any((a,r.day,sid,ep)in ss for r in early.itertuples())
 episodes.append(row)
episodes=pd.DataFrame(episodes);episodes.to_csv(O/'ROOT_EPISODE_COVERAGE.csv',index=False)
ec=[]
for(a,y),g in episodes.groupby(['account','year']):
 b=g[g.big60];base=b.ORIGINAL_PVR_early_capture;alt=b.MOBILE_RESPONSE_early_capture
 ec.append(dict(account=a,year=y,roots=len(g),complete60_roots=int(g.complete60.sum()),big_roots=len(b),base_captured=int(base.sum()),response_captured=int(alt.sum()),lost=int((base&~alt).sum()),added=int((~base&alt).sum()),retained_baseline_fraction=float((base&alt).sum()/base.sum())if base.any()else None))
pd.DataFrame(ec).to_csv(O/'ANNUAL_ROOT_BIG_COVERAGE.csv',index=False)
# Event membership selection-only loss and addition, independent of any NAV.
diffs=[]
for(a,y),g in selected.groupby(['account','year']):
 b=g[g.strategy=='ORIGINAL_PVR'];v=g[g.strategy=='MOBILE_RESPONSE']
 bk=set(zip(b.day,b.sid));vk=set(zip(v.day,v.sid))
 for side,z in [('removed',b[[(d,s)not in vk for d,s in zip(b.day,b.sid)]]),('added',v[[(d,s)not in bk for d,s in zip(v.day,v.sid)]])]:
  diffs.append(dict(account=a,year=y,side=side,**met(z)))
pd.DataFrame(diffs).to_csv(O/'ADDED_REMOVED_PATHS.csv',index=False)
for p,v in source.items():assert sha(p)==v
summary=dict(status='COMPLETED_FROZEN_OFFLINE_MOBILE_RANK_TEST_NOT_ACCOUNT_NOT_OOS',seconds=time.monotonic()-started,candidate_rows=len(sc),selected_rows=len(selected),price_series=len(checks),first_mobile_open_checks=len(j),future_poison_checks=len(tests),sources_unchanged=True,account_runs=0,original_indicator_runs=0,all_equal_K=True,full_domain_rows_by_account=sc.groupby('account').size().to_dict(),known_rows_by_account=sc.groupby('account').model_known.sum().to_dict())
dump('SUMMARY.json',summary)
print(json.dumps(summary));print('ANNUAL');print(pd.DataFrame(annual)[['account','year','strategy','selected','day_mean_ret5','day_mean_ret20','mean_mae20','big60_events']].to_string(index=False));print('BIG_ROOTS');print(pd.DataFrame(ec).to_string(index=False))

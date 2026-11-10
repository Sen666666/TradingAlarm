"""One frozen Q on original eligible MOBILE queues. Never runs original models/accounts."""
from pathlib import Path
import sys,json,math,hashlib,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
B=O.parents[2]/'mobile_candidate_response_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
L=20/21;A=1/21
CUTS=['2022-03-31','2024-09-24','2026-01-15']
KEY=['account','day','sid']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def qarray(r,m,s):
 out=np.full((len(r),4),np.nan);U=D=0.;run=0;prev=None
 for i,(ri,mi,si) in enumerate(zip(r,m,s)):
  if prev is None or si!=prev:U=D=0.;run=0;prev=si
  if not (math.isfinite(ri) and math.isfinite(mi) and mi>0):
   U=D=0.;run=0;out[i]=[0.,0.,math.nan,0.];continue
  U=L*U+A*mi*max(ri,0);D=L*D+A*mi*max(-ri,0);run+=1
  out[i]=[U,D,100*(U/(U+D)) if U+D>0 else 50.,run]
 return out

def score():
 start=time.monotonic()
 freeze=dict(name='沿原CP m的21期连续加权涨跌比',formula='lambda=20/21, alpha=1/21; U=lambda*Uprev+alpha*m*max(r,0); D=lambda*Dprev+alpha*m*max(-r,0); Q=100*U/(U+D), zero denominator=50',reset='Only segment change or unavailable r/m; UNKNOWN current row, next valid starts from zero. E0/I/native-down/lower-anchor/receipt never reset.',clock='Original daily source observations; close and amount available at t; ranking after t close, evaluation from original next common open. No calendar-day decay or synthetic suspended observations. Entire original cache prefix warm-up. All 2022-26 are consumed research history, NOT OOS.',domain='103766 original legal account-specific EMPTY MOBILE candidates, PVR/E31 separated. Never filter accepted or i_buy. Unknown Q retains exact original slot. Finite score with <21 valid observations retained, separately reported.',ranking='Baseline original_priority_rank ascending, sid ascending. K=min(20,N). Slots with finite Q and original PVR only are replaceable; original PVR missing also stays fixed without being counted as Q UNKNOWN. Replaceable slots reranked by Q rounded12 desc, original_PVR rounded12 desc, original_priority_rank asc, sid asc. No admission threshold; no old strict wait; no other signal/size/exit modification.',labels='Read existing FIXED_NATIVE_PRICE_LABELS only after sealing new selections. No price labels recomputed. Original raw.open * facts.factor coordinate.',evaluation='Year/account event-sum and event-mean paths plus equal-day means; 5/20 return and close MAE; both-strategies all-selected-complete common-date paired differences. Quarterly date-block descriptions only. Not money, NAV, fills, or an account replay.',root='Earliest legal candidate of original account/sid/epoch is birth; birth complete60 & mfe60>=.30 & ret60>=.20. Capture any same-root selection within common-calendar birth.t..birth.t+5. Future label evaluation-only.',prefix_cutoffs=CUTS,parameter_scans=0)
 dump('FREEZE.json',freeze)
 c=pd.read_parquet(B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');assert len(c)==103766
 assert not c.duplicated(KEY).any()
 manifest={x['symbol']:x for x in json.loads(M.read_text())}
 source={str(p):sha(p) for p in [M,B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',Path(__file__)]};dump('SOURCE_BEFORE_SCORES.json',source)
 parts=[];tests=[];hashes=[]
 for no,(sid,g) in enumerate(c[['sid','day']].drop_duplicates().groupby('sid',sort=True)):
  ref=manifest[sid]['refs'];cp_path=Path(ref['CP1']);f_path=Path(ref['facts'])
  before={str(p):sha(p) for p in [cp_path,f_path]}
  cp=pd.read_parquet(cp_path,columns=['r','m']);f=pd.read_parquet(f_path,columns=['segment_id','i_buy'])
  assert cp.index.equals(f.index) and cp.index.is_monotonic_increasing and cp.index.is_unique
  r=cp.r.to_numpy();m=cp.m.to_numpy();s=f.segment_id.to_numpy();q=qarray(r,m,s)
  for cutoff in CUTS:
   stop=int(cp.index.searchsorted(pd.Timestamp(cutoff),side='right'))
   if stop:
    small=qarray(r[:stop],m[:stop],s[:stop]);assert np.array_equal(q[:stop],small,equal_nan=True)
   tests.append(dict(sid=sid,cutoff=cutoff,full_observations=len(cp),prefix_observations=stop,passed=True))
  query=pd.DatetimeIndex(g.day);loc=cp.index.get_indexer(query);known=loc>=0
  zz=np.full((len(g),4),np.nan);zz[known]=q[loc[known]]
  z=g.copy();z[['U','D','Q','continuous_valid_observations']]=zz
  z['source_i_buy']=False;z.loc[known,'source_i_buy']=f.i_buy.to_numpy()[loc[known]]
  z['Q_known']=np.isfinite(z.Q);z['short_warm_history']=z.Q_known & z.continuous_valid_observations.lt(21)
  assert z.Q.dropna().between(0,100).all()
  parts.append(z)
  for p,b in before.items():
   after=sha(p);assert after==b;expected=manifest[sid].get('output_sha256',{}).get(p)
   if expected is not None:assert b==expected
   hashes.append(dict(sid=sid,path=p,sha256=b,manifest_expected=expected,source_unchanged=True))
  if (no+1)%300==0:print('SCORE_STOCKS',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
 scores=pd.concat(parts,ignore_index=True)
 sc=c.merge(scores,on=['sid','day'],validate='many_to_one')
 sc['slot_replaceable']=sc.Q_known & np.isfinite(sc.original_PVR)
 assert len(sc)==len(c)
 # Existing seven-case arithmetic is an exact implementation cross-check, not a score choice.
 cases=pd.read_csv(O.parent/'SIGNAL_SUMMARY.csv');checked=0
 for rr in cases.itertuples():
  z=sc[(sc.sid==rr.sid)&(sc.day==rr.signal_day)]
  if len(z):assert np.max(np.abs(z.Q-rr.signal_score))<1e-12;checked+=1
 sc.to_parquet(O/'CANDIDATE_Q.parquet',index=False)
 pd.DataFrame(tests).to_csv(O/'PREFIX_TESTS.csv',index=False)
 pd.DataFrame(hashes).to_csv(O/'CACHE_SOURCE_AUDIT.csv',index=False)
 coverage=sc.groupby(['account','year']).agg(candidates=('sid','size'),known=('Q_known','sum'),short_warm=('short_warm_history','sum'),i_buy_false=('source_i_buy',lambda x:int((~x).sum()))).reset_index()
 coverage['unknown']=coverage.candidates-coverage.known;coverage['short_warm_fraction']=coverage.short_warm/coverage.candidates
 coverage.to_csv(O/'SCORE_COVERAGE_BY_YEAR.csv',index=False)
 out=dict(candidate_rows=len(sc),unique_stock_days=len(scores),stocks=sc.sid.nunique(),known=int(sc.Q_known.sum()),unknown=int((~sc.Q_known).sum()),original_PVR_unknown=int((~np.isfinite(sc.original_PVR)).sum()),replaceable=int(sc.slot_replaceable.sum()),finite_short_warm=int(sc.short_warm_history.sum()),false_i_buy_preserved=int((~sc.source_i_buy).sum()),prefix_checks=len(tests),case_value_crosschecks=checked,seconds=time.monotonic()-start,by_account=sc.groupby('account').size().to_dict(),full_formula_fixed_before_case_calculation=True,labels_not_read=True)
 for p,h in source.items():assert sha(p)==h
 dump('SCORE_COVERAGE.json',out);print(json.dumps(out));print(coverage.to_string(index=False))

def orders(g):
 base=g.sort_values(['original_priority_rank','sid']);indices=list(base.index)
 known=base[base.slot_replaceable].copy();known['qr']=known.Q.round(12);known['pvr']=known.original_PVR.round(12)
 known=known.sort_values(['qr','pvr','original_priority_rank','sid'],ascending=[False,False,True,True])
 it=iter(known.index);alt=[next(it) if base.at[i,'slot_replaceable'] else i for i in indices]
 assert set(indices)==set(alt)
 assert all(i==alt[j] for j,i in enumerate(indices) if not base.at[i,'slot_replaceable'])
 return indices,alt

def metrics(g):
 out=dict(selected=len(g),signal_days=g.day.nunique(),stocks=g.sid.nunique(),i_buy_false=int((~g.source_i_buy).sum()),short_warm=int(g.short_warm_history.sum()),Q_unknown=int((~g.Q_known).sum()))
 for H in [5,20,60]:
  z=g[g[f'complete{H}']]
  out.update({f'complete{H}':len(z),f'unknown{H}':len(g)-len(z),f'event_sum_ret{H}':z[f'ret{H}'].sum(min_count=1),f'event_mean_ret{H}':z[f'ret{H}'].mean(),f'day_equal_ret{H}':z.groupby('day')[f'ret{H}'].mean().mean(),f'positive_ret{H}':z[f'ret{H}'].gt(0).mean(),f'event_mean_mae{H}':z[f'mae{H}'].mean(),f'day_equal_mae{H}':z.groupby('day')[f'mae{H}'].mean().mean()})
 return out

def evaluate():
 start=time.monotonic()
 sc=pd.read_parquet(O/'CANDIDATE_Q.parquet')
 assert len(sc)==103766
 # The queue function has no labels in its inputs.
 selections=[];queues=[];moves=[];members=[]
 for (a,day),g in sc.groupby(['account','day'],sort=True):
  base,alt=orders(g);k=min(20,len(base));bp={i:j+1 for j,i in enumerate(base)};ap={i:j+1 for j,i in enumerate(alt)}
  for strategy,ix in [('ORIGINAL_PVR',base[:k]),('CONTINUOUS_Q',alt[:k])]:
   z=sc.loc[ix].copy();z['strategy']=strategy;z['selected_rank']=range(1,len(z)+1);selections.append(z)
  for i in base:
   row=dict(account=a,day=day,sid=sc.at[i,'sid'],year=sc.at[i,'year'],epoch=sc.at[i,'epoch'],CP1_id=sc.at[i,'CP1_id'],original_rank=bp[i],Q_rank=ap[i],K=k,Q=sc.at[i,'Q'],original_PVR=sc.at[i,'original_PVR'],Q_known=sc.at[i,'Q_known'],original_selected=bp[i]<=k,Q_selected=ap[i]<=k)
   moves.append(row)
   if (bp[i]<=k)!=(ap[i]<=k):members.append(dict(**row,side='added' if ap[i]<=k else 'removed'))
  queues.append(dict(account=a,day=day,year=g.year.iloc[0],N=len(base),K=k,known=int(g.Q_known.sum()),unknown=int((~g.Q_known).sum()),top_overlap=len(set(base[:k])&set(alt[:k])),added=len(set(alt[:k])-set(base[:k]))))
 selected=pd.concat(selections,ignore_index=True);mov=pd.DataFrame(moves);queue=pd.DataFrame(queues)
 assert selected.groupby(['account','day','strategy']).size().unstack().nunique(axis=1).eq(1).all()
 selected.to_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet',index=False)
 mov.to_parquet(O/'FULL_QUEUE_ORDERS.parquet',index=False);queue.to_csv(O/'QUEUE_COUNTS.csv',index=False)
 dump('RANK_SEAL.json',dict(selections_sha256=sha(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet'),score_sha256=sha(O/'CANDIDATE_Q.parquet'),rank_input_columns=['Q','Q_known','original_PVR','original_priority_rank','sid'],future_labels_read=False,all_equal_K=True))
 # Confirm the old exact baseline, including tie order, before evaluation.
 old=pd.read_parquet(B/'SEALED_SAME_K_SELECTIONS.parquet');old=old[old.strategy=='ORIGINAL_PVR']
 cols=['account','day','selected_rank','sid','CP1_id']
 a=selected[selected.strategy=='ORIGINAL_PVR'][cols].sort_values(cols[:3]).reset_index(drop=True)
 b=old[cols].sort_values(cols[:3]).reset_index(drop=True)
 pd.testing.assert_frame_equal(a,b,check_dtype=False)
 print('BASELINE_IDENTICAL',len(a),'rows. RANK_SEALED. Now reading fixed labels.',flush=True)
 labels=pd.read_parquet(B/'FIXED_NATIVE_PRICE_LABELS.parquet')
 source={str(p):sha(p) for p in [B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',B/'FIXED_NATIVE_PRICE_LABELS.parquet',B/'SEALED_SAME_K_SELECTIONS.parquet',B/'ROOT_EPISODE_COVERAGE.csv',O/'CANDIDATE_Q.parquet',Path(__file__)]}
 assert len(labels)==54852 and not labels.duplicated(['sid','day']).any()
 selected=selected.merge(labels,on=['sid','day'],validate='many_to_one');sc=sc.merge(labels,on=['sid','day'],validate='many_to_one')
 assert selected.t.notna().all() and sc.t.notna().all()
 selected['quarter']=pd.to_datetime(selected.day).dt.to_period('Q').astype(str)
 selected.to_parquet(O/'SELECTED_WITH_FIXED_LABELS.parquet',index=False)
 replacement=pd.DataFrame(members).merge(labels,on=['sid','day'],validate='many_to_one')
 replacement.to_csv(O/'REPLACEMENTS.csv',index=False)
 annual=pd.DataFrame([dict(account=a,year=int(y),strategy=s,**metrics(g)) for (a,y,s),g in selected.groupby(['account','year','strategy'])]);annual.to_csv(O/'ANNUAL_OUTCOMES.csv',index=False)
 quarterly=pd.DataFrame([dict(account=a,quarter=q,strategy=s,**metrics(g)) for (a,q,s),g in selected.groupby(['account','quarter','strategy'])]);quarterly.to_csv(O/'QUARTER_OUTCOMES.csv',index=False)
 # Analysis-only maturity restriction: every selected item in both strategies complete on a paired day.
 paired=[]
 for (account,year),g in selected.groupby(['account','year']):
  for H in [5,20]:
   z=g.groupby(['day','strategy']).agg(k=('sid','size'),complete=(f'complete{H}','sum'),mean_ret=(f'ret{H}','mean'),sum_ret=(f'ret{H}','sum'),mean_mae=(f'mae{H}','mean'),sum_mae=(f'mae{H}','sum'))
   complete=z.k.eq(z.complete).unstack('strategy').fillna(False).all(axis=1)
   for day in complete.index:
    b=z.loc[(day,'ORIGINAL_PVR')];q=z.loc[(day,'CONTINUOUS_Q')]
    paired.append(dict(account=account,year=int(year),day=day,quarter=str(pd.Timestamp(day).to_period('Q')),horizon=H,K=int(b.k),both_all_complete=bool(complete.loc[day]),base_complete=int(b.complete),Q_complete=int(q.complete),base_ret=b.mean_ret,Q_ret=q.mean_ret,diff_ret=q.mean_ret-b.mean_ret,base_sum_ret=b.sum_ret,Q_sum_ret=q.sum_ret,diff_sum_ret=q.sum_ret-b.sum_ret,base_mae=b.mean_mae,Q_mae=q.mean_mae,diff_mae=q.mean_mae-b.mean_mae,changed=int(queue[(queue.account==account)&(queue.day==day)].added.iloc[0])>0))
 pair=pd.DataFrame(paired);pair.to_csv(O/'PAIRED_DATE_DETAILS.csv',index=False)
 def pairmet(g):
  z=g[g.both_all_complete];ch=z[z.changed]
  return dict(all_dates=len(g),common_complete_dates=len(z),complete_event_count=int(z.K.sum()),changed_complete_dates=len(ch),base_day_equal_ret=z.base_ret.mean(),Q_day_equal_ret=z.Q_ret.mean(),day_paired_diff=z.diff_ret.mean(),event_paired_diff=z.diff_sum_ret.sum()/z.K.sum() if z.K.sum()>0 else np.nan,event_sum_diff=z.diff_sum_ret.sum(min_count=1),base_day_equal_mae=z.base_mae.mean(),Q_day_equal_mae=z.Q_mae.mean(),mae_day_paired_diff=z.diff_mae.mean(),positive_diff_dates=int(z.diff_ret.gt(0).sum()),negative_diff_dates=int(z.diff_ret.lt(0).sum()),equal_diff_dates=int(z.diff_ret.eq(0).sum()),changed_day_paired_diff=ch.diff_ret.mean())
 pm=pd.DataFrame([dict(account=a,year=int(y),horizon=H,**pairmet(g)) for (a,y,H),g in pair.groupby(['account','year','horizon'])]);pm.to_csv(O/'MATCHED_COMPLETE_DATE_RESULTS.csv',index=False)
 pq=pd.DataFrame([dict(account=a,quarter=q,horizon=H,**pairmet(g)) for (a,q,H),g in pair.groupby(['account','quarter','horizon'])]);pq.to_csv(O/'QUARTER_PAIRED_RESULTS.csv',index=False)
 # Preserve the original root birth and evaluation-only big-event definition.
 lookup={strategy:set(zip(g.account,g.day,g.sid,g.epoch)) for strategy,g in selected.groupby('strategy')}
 episodes=[]
 for (a,sid,ep),g in sc.groupby(['account','sid','epoch'],sort=True):
  g=g.sort_values('t');b=g.iloc[0];early=g[g.t<=int(b.t)+5]
  row=dict(account=a,sid=sid,epoch=ep,birth_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc),candidate_events=len(g),early_candidate_events=len(early))
  for strategy,ss in lookup.items():row[strategy+'_early_capture']=any((a,r.day,sid,ep) in ss for r in early.itertuples())
  row['lost']=row['ORIGINAL_PVR_early_capture'] and not row['CONTINUOUS_Q_early_capture'];row['added']=not row['ORIGINAL_PVR_early_capture'] and row['CONTINUOUS_Q_early_capture'];episodes.append(row)
 ep=pd.DataFrame(episodes)
 oldep=pd.read_csv(B/'ROOT_EPISODE_COVERAGE.csv')
 ek=['account','sid','epoch'];cols=ek+['birth_day','year','complete60','big60','candidate_events','early_candidate_events','ORIGINAL_PVR_early_capture']
 pd.testing.assert_frame_equal(ep[cols].sort_values(ek).reset_index(drop=True),oldep[cols].sort_values(ek).reset_index(drop=True),check_dtype=False)
 ep.to_csv(O/'ROOT_EPISODES.csv',index=False);ep[ep.big60&(ep.lost|ep.added)].to_csv(O/'BIG_ROOT_LOST_ADDED.csv',index=False)
 coverage=[]
 for (a,y),g in ep.groupby(['account','year']):
  b=g[g.big60]
  coverage.append(dict(account=a,year=int(y),roots=len(g),complete60_roots=int(g.complete60.sum()),unknown60_roots=int((~g.complete60).sum()),big_roots=len(b),base_captured=int(b.ORIGINAL_PVR_early_capture.sum()),Q_captured=int(b.CONTINUOUS_Q_early_capture.sum()),lost=int(b.lost.sum()),added=int(b.added.sum()),net_added=int(b.added.sum()-b.lost.sum())))
 cov=pd.DataFrame(coverage);cov.to_csv(O/'ANNUAL_BIG_ROOT_COVERAGE.csv',index=False)
 changes=queue.groupby(['account','year']).agg(days=('day','size'),changed_days=('added',lambda x:int(x.gt(0).sum())),selected_per_strategy=('K','sum'),added=('added','sum'),unknown=('unknown','sum')).reset_index();changes['replacement_fraction']=changes.added/changes.selected_per_strategy;changes.to_csv(O/'ANNUAL_REPLACEMENTS.csv',index=False)
 cases=pd.read_csv(O.parent/'SIGNAL_SUMMARY.csv').rename(columns={'signal_day':'day'})
 mov.merge(cases[['sid','day','case_kind','original_round_pnl']],on=['sid','day'],how='inner').to_csv(O/'FIXED_CASE_QUEUE_EFFECTS.csv',index=False)
 # Label mutation cannot alter membership because ranks were sealed without any label columns.
 poison=sc.copy()
 for col in labels.columns:
  if col not in ['sid','day']:poison[col]=-999999 if pd.api.types.is_numeric_dtype(poison[col]) else 'POISON'
 for (a,day),g in poison.groupby(['account','day'],sort=True):
  b,q=orders(g)
  expected=mov[(mov.account==a)&(mov.day==day)].sort_values('Q_rank').sid.tolist()
  assert g.loc[q,'sid'].tolist()==expected
 for p,h in source.items():assert sha(p)==h
 summary=dict(status='COMPLETED_FROZEN_Q_OFFLINE_CANDIDATE_TEST_NOT_ACCOUNT_NOT_OOS',candidate_rows=len(sc),selected_per_strategy=len(selected)//2,baseline_exact_match=True,roots_exact_original_match=True,future_label_mutation_all_queues_unchanged=True,all_equal_K=True,account_runs=0,original_indicator_runs=0,parameter_scans=0,seconds=time.monotonic()-start,source_unchanged=True)
 dump('EVALUATION_SOURCE_HASHES.json',source);dump('SUMMARY.json',summary)
 print(json.dumps(summary));print('PAIRED_COMPLETE');print(pm[['account','year','horizon','common_complete_dates','day_paired_diff','event_paired_diff','mae_day_paired_diff']].to_string(index=False));print('BIG_ROOTS');print(cov.to_string(index=False));print('REPLACEMENTS');print(changes.to_string(index=False))
if __name__=='__main__':
 {'score':score,'evaluate':evaluate}[sys.argv[1]]()

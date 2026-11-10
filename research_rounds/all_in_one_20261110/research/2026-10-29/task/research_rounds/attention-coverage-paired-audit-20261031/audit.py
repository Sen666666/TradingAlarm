from pathlib import Path
import sys,importlib.util,time,json,collections,signal
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;PREV=O.parent/'attention-turnover-source-audit-20261031'
s=importlib.util.spec_from_file_location('coverage_prior_audit',PREV/'audit.py');A=importlib.util.module_from_spec(s);sys.modules[s.name]=A;s.loader.exec_module(A)
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(A.norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if isinstance(x,list) and x:pd.DataFrame(A.norm(x)).to_csv(O/(n+'.csv'),index=False)
def main():
 start=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('30s paired coverage audit')));signal.setitimer(signal.ITIMER_REAL,30)
 old=A.read(PREV/'EXIT_EVENTS.json');events=[r for r in old if r['primary']=='coverage_changed'];assert len(events)==75;gids_events={r['group_id'] for r in events};groups=[r for r in A.read(PREV/'GROUP_MEMBERSHIP_IDENTITIES.json') if r['group_id'] in gids_events];freeze=A.read(PREV/'FREEZE.json');assert all(A.sha(p)==h for p,h in freeze['sha256'].items());save('FREEZE',dict(no_future_labels=True,old_identities_unchanged=True,sha256={str(p):A.sha(p) for p in [O/'PROTOCOL.txt',O/'audit.py',PREV/'EXIT_EVENTS.json',A.SRC/'AMOUNT_INPUT.npz',A.SRC/'FEATURE_MATRIX_90.parquet']}))
 meta=A.read(A.ROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');z=np.load(A.SRC/'AMOUNT_INPUT.npz');dates=pd.DatetimeIndex(z['dates']);sids=[str(s) for s in z['symbols']];amount=z['amount'];gids=sorted({meta[s]['sector_id'] for s in sids});gi={s:i for i,s in enumerate(gids)};sg=np.array([gi[meta[s]['sector_id']] for s in sids]);names={meta[s]['sector_id']:meta[s]['industry'] for s in sids};mat=pd.read_parquet(A.SRC/'FEATURE_MATRIX_90.parquet').set_index(['day','sector']);facts={p.stem:pd.read_parquet(p,columns=['e0_ready','e0_target']) for p in (A.W/'mainline-absolute-Q4-20261031/industry-facts').glob('*.parquet')};targets={r['day']:r['targets'] for r in A.read(A.W/'mainline-attention-top3-Q4-20261031/TARGETS.json')+A.read(A.W/'mainline-forward-Q1-20261031/analysis/TARGETS.json')};result=[];factor=[];groupstats=[];observations={};rawneeded=collections.defaultdict(set)
 def rank(q,s):return sorted([i for i in range(len(gids)) if q[i] and np.isfinite(s[i])],key=lambda i:(-s[i],gids[i]))
 def ND(a,G):
  N=np.full(len(sids),np.nan);D=N.copy();valid=np.isfinite(a).all(axis=0)&(a>=0).all(axis=0);den=a[:,G].sum(axis=1);share=a[:,valid]/den[:,None];N[valid]=np.median(share[21:],axis=0);D[valid]=np.median(share[:21],axis=0);return N,D
 def score(n,d,m):return np.array([np.median(n[m&(sg==j)]/d[m&(sg==j)]) if (m&(sg==j)).any() else np.nan for j in range(len(gids))])
 for group in groups:
  day=[group['previous_day'],group['day']];ix=[dates.get_loc(pd.Timestamp(d)) for d in day];aa=[amount[j-25:j+1] for j in ix];V=[np.isfinite(a).all(axis=0)&(a>=0).all(axis=0) for a in aa];G=V[0]&V[1];nd=[ND(a,v) for a,v in zip(aa,V)];M=[v&(d>0)&np.isfinite(n) for v,(n,d) in zip(V,nd)];MM=M[0]&M[1];q=[np.array([bool(facts[g].loc[d,'e0_ready']) and bool(facts[g].loc[d,'e0_target']) and np.isfinite(mat.loc[d,g].H1_original) for g in gids]) for d in day];nf=[ND(a,G) for a in aa];scores={};ranks={};complete={}
  for f in ['00','10','01','11']:
   scores[f]=[];ranks[f]=[];complete[f]=True
   for t in [0,1]:
    n,d=nf[t] if f[0]=='1' else nd[t];m=MM if f[1]=='1' else M[t];sc=score(n,d,m);scores[f].append(sc);complete[f]&=bool(np.isfinite(sc[q[t]]).all());ranks[f].append(rank(q[t],sc))
  for t,d in enumerate(day):
   np.testing.assert_allclose(scores['00'][t],mat.loc[d].loc[gids].attention_ratio.to_numpy(),rtol=1e-12,atol=1e-12,equal_nan=True);assert [gids[j] for j in ranks['00'][t][:3]]==targets[d]
  for j in np.flatnonzero(V[0]^V[1]):
   for t,a in enumerate(aa):
    for k in np.flatnonzero(~np.isfinite(a[:,j])):rawneeded[sids[j]].add(dates[ix[t]-25+k])
  groupstats.append(dict(group_id=group['group_id'],day=day[1],union_dates=len(set(dates[ix[0]-25:ix[0]+1])|set(dates[ix[1]-25:ix[1]+1])),complete_pool0=int(V[0].sum()),complete_pool1=int(V[1].sum()),common_pool=int(G.sum()),removed_from_prior_pool=int((V[0]&~G).sum()),removed_from_current_pool=int((V[1]&~G).sum()),ratio_sample0=int(M[0].sum()),ratio_sample1=int(M[1].sum()),fixed_ratio_sample=int(MM.sum()),zero_baseline_excluded_from_common=int((G&~MM).sum()),all_qualified_competitors_common_scored=complete['11'],minimum_fixed_industry_members=min(int((MM&(sg==j)).sum()) for j in range(len(gids))),zero_amount_cells_in_union=int((amount[min(ix)-25:max(ix)+1]==0).sum()),missing_amount_cache_cells_in_union=int(np.isnan(amount[min(ix)-25:max(ix)+1]).sum())))
  for oldrow in [r for r in events if r['group_id']==group['group_id']]:
   sec=oldrow['sector'];i=gi[sec];ys={};states={}
   for f in scores:
    isin=[i in rs[:3] for rs in ranks[f]]
    if not complete[f]:state='unknown';y=None
    elif isin[0] and not isin[1]:state='remains';y=1
    else:state='disappears';y=0
    ys[f]=y;states[f]=state
   assert ys['00']==1
   ownlogs={f:float(np.log(v[1][i]/v[0][i])) if min(v[0][i],v[1][i])>0 else None for f,v in scores.items()};numeric=all(v is not None for v in ownlogs.values());ld=ownlogs['10']-ownlogs['00'] if numeric else None;lm=ownlogs['01']-ownlogs['00'] if numeric else None;interaction=ownlogs['11']-ownlogs['10']-ownlogs['01']+ownlogs['00'] if numeric else None
   if numeric:np.testing.assert_allclose(ld+lm+interaction,ownlogs['11']-ownlogs['00'],rtol=1e-12,atol=1e-12)
   yknown=all(y is not None for y in ys.values());rankint=ys['11']-ys['10']-ys['01']+1 if yknown else None
   result.append(dict(group_id=group['group_id'],previous_day=day[0],day=day[1],sector=sec,industry=names[sec],main=states['11'],common_prev_in_top3=i in ranks['11'][0][:3] if complete['11'] else None,common_current_in_top3=i in ranks['11'][1][:3] if complete['11'] else None,common_prev_rank=ranks['11'][0].index(i)+1 if i in ranks['11'][0] else None,common_current_rank=ranks['11'][1].index(i)+1 if i in ranks['11'][1] else None,original_industry_sample0=int((M[0]&(sg==i)).sum()),original_industry_sample1=int((M[1]&(sg==i)).sum()),common_industry_sample=int((MM&(sg==i)).sum()),original_score0=scores['00'][0][i],original_score1=scores['00'][1][i],common_score0=scores['11'][0][i],common_score1=scores['11'][1][i],factor_states=states,indicator_effect_fixed_global=ys['10']-1 if yknown else None,indicator_effect_fixed_members=ys['01']-1 if yknown else None,indicator_interaction=rankint,score_change_log_direct_global=ld,score_change_log_direct_members=lm,score_change_log_interaction=interaction))
   for f in scores:factor.append(dict(group_id=group['group_id'],sector=sec,day=day[1],factor=f,state=states[f],complete_competitor_ranking=complete[f],score0=scores[f][0][i],score1=scores[f][1][i],top3_prior=[gids[j] for j in ranks[f][0][:3]],top3_current=[gids[j] for j in ranks[f][1][:3]],minimum_qualified_members0=min([int(((MM if f[1]=='1' else M[0])&(sg==j)).sum()) for j in np.flatnonzero(q[0])],default=0),minimum_qualified_members1=min([int(((MM if f[1]=='1' else M[1])&(sg==j)).sum()) for j in np.flatnonzero(q[1])],default=0)))
 # Read only local rows behind changed completeness, not a new 1709-bar scan.
 prepared=A.ROOT/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared';records={r['series_id']:r for r in A.read(prepared/'manifest.json')['series']};quality=[]
 for sid,needed in rawneeded.items():
  f=pd.read_parquet(records[sid]['raw']['path']);f=f.set_index('trade_date');f.index=pd.to_datetime(f.index)
  for d in sorted(needed):
   r=f.loc[d] if d in f.index else None
   if r is None:kind='before_first_local_bar' if d<f.index.min() else 'no_local_bar';zero=False
   else:
    v=r.amount;zero=bool(np.isfinite(v) and v==0);flags=bool(r.observed_bar and r.price_eligible and not r.synthetic_event_bar)
    kind='raw_amount_missing_or_invalid' if not np.isfinite(v) or v<0 else 'zero_amount_but_source_ineligible' if zero and not flags else 'source_observation_flags_excluded' if not flags else 'eligible_actual_zero' if zero else 'eligible_positive'
   quality.append(dict(sid=sid,day=str(d.date()),cache_missing_reason=kind,raw_zero=zero,explicit_listing_or_suspension_reason='not available in fields used; do not infer from missing bar'))
 assert len(result)==75
 counts=dict(collections.Counter(r['main'] for r in result));summary=dict(events=75,groups=len(groups),joint_common_scorable=sum(r['main']!='unknown' for r in result),counts=counts,disappeared_prior_already_out=sum(r['main']=='disappears' and not r['common_prev_in_top3'] for r in result),disappeared_current_still_in=sum(r['main']=='disappears' and r['common_current_in_top3'] for r in result),common_pool_min=min(r['common_pool'] for r in groupstats),common_pool_max=max(r['common_pool'] for r in groupstats),pool_loss_from_prior_max=max(r['removed_from_prior_pool'] for r in groupstats),pool_loss_from_current_max=max(r['removed_from_current_pool'] for r in groupstats),pool_loss_from_prior_median=float(np.median([r['removed_from_prior_pool'] for r in groupstats])),pool_loss_from_current_median=float(np.median([r['removed_from_current_pool'] for r in groupstats])),own_members_loss_events=sum(r['common_industry_sample']<max(r['original_industry_sample0'],r['original_industry_sample1']) for r in result),common_industry_min=min(r['common_industry_sample'] for r in result),common_industry_max=max(r['common_industry_sample'] for r in result),global_only_counts=dict(collections.Counter(r['factor_states']['10'] for r in result)),members_only_counts=dict(collections.Counter(r['factor_states']['01'] for r in result)),indicator_interaction_counts=dict(collections.Counter(str(r['indicator_interaction']) for r in result)),changed_stocks_raw_read=len(rawneeded),quality_counts_stockdates=dict(collections.Counter(r['cache_missing_reason'] for r in quality)),no_future_labels_read=True,no_economic_paths=True,seconds_before_output=time.monotonic()-start)
 for n,x in [('EVENTS',result),('FACTOR_RANKINGS',factor),('GROUP_COVERAGE',groupstats),('SOURCE_EXCLUSIONS',quality)]:save(n,x)
 summary['seconds_with_output']=time.monotonic()-start;save('SUMMARY',summary);signal.setitimer(signal.ITIMER_REAL,0);print(json.dumps(A.norm(summary),ensure_ascii=False),flush=True);print('DISAPPEARED',json.dumps(A.norm([r for r in result if r['main']!='remains']),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR',dict(error=repr(e),traceback=traceback.format_exc()));raise

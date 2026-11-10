from pathlib import Path
import json,time,hashlib,signal,traceback,collections,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;SRC=W/'market-mainline-measurement-20261031';ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
def read(p):return json.loads(Path(p).read_text())
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [norm(v) for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(name,x):
 (O/(name+'.json')).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if isinstance(x,list) and x:pd.DataFrame(norm(x)).to_csv(O/(name+'.csv'),index=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 start=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('30s frozen cache audit budget')));signal.setitimer(signal.ITIMER_REAL,30)
 paths=[O/'PROTOCOL.txt',O/'audit.py',SRC/'AMOUNT_INPUT.npz',SRC/'FEATURE_MATRIX_90.parquet',W/'mainline-attention-top3-Q4-20261031/TARGETS.json',W/'mainline-forward-Q1-20261031/analysis/TARGETS.json'];save('FREEZE',dict(no_future_labels=True,sha256={str(p):sha(p) for p in paths}))
 meta=read(ROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');z=np.load(SRC/'AMOUNT_INPUT.npz');dates=pd.DatetimeIndex(z['dates']);sids=[str(s) for s in z['symbols']];amount=z['amount'];gids=sorted({meta[s]['sector_id'] for s in sids});gn={s:i for i,s in enumerate(gids)};groups=np.array([gn[meta[s]['sector_id']] for s in sids]);names={meta[s]['sector_id']:meta[s]['industry'] for s in sids};matrix=pd.read_parquet(SRC/'FEATURE_MATRIX_90.parquet');days={d:g.set_index('sector').loc[gids] for d,g in matrix.groupby('day',sort=False)};tt=read(paths[-2])+read(paths[-1]);tt=sorted(tt,key=lambda x:x['day']);obs=[r['day'] for r in tt];assert len(obs)==116 and len(set(obs))==116;index={d:dates.get_loc(pd.Timestamp(d)) for d in obs};facts={g:pd.read_parquet(W/'mainline-absolute-Q4-20261031/industry-facts'/f'{g}.parquet',columns=['e0_ready','e0_target']) for g in gids};qual={};parts={};counter=collections.Counter()
 def calc(a,valid=None):
  valid=np.isfinite(a).all(axis=0)&(a>=0).all(axis=0) if valid is None else valid
  ids=np.flatnonzero(valid);den=a[:,valid].sum(axis=1);N=np.full(len(sids),np.nan);D=np.full(len(sids),np.nan)
  if len(ids) and (den>0).all():q=a[:,valid]/den[:,None];D[ids]=np.median(q[:21],axis=0);N[ids]=np.median(q[21:],axis=0)
  good=np.isfinite(D)&(D>0)&np.isfinite(N);rat=np.full(len(sids),np.nan);rat[good]=N[good]/D[good];scores=np.array([np.median(rat[(groups==i)&good]) if ((groups==i)&good).any() else np.nan for i in range(len(gids))]);return dict(valid=valid,good=good,N=N,D=D,score=scores,den=den)
 def ranking(q,scores):return sorted([i for i in range(len(gids)) if q[i] and np.isfinite(scores[i])],key=lambda i:(-scores[i],gids[i]))
 for r in tt:
  d=r['day'];j=index[d];a=amount[j-25:j+1];p=calc(a);g=days[d];np.testing.assert_allclose(p['score'],g.attention_ratio.to_numpy(),rtol=1e-12,atol=1e-12,equal_nan=True);assert int(p['valid'].sum())==int(g.denominator_complete_window_members.iloc[0]);np.testing.assert_array_equal([int(((groups==i)&p['good']).sum()) for i in range(len(gids))],g.attention_members.to_numpy());q=np.array([pd.Timestamp(d) in facts[sec].index and bool(facts[sec].loc[d,'e0_ready']) and bool(facts[sec].loc[d,'e0_target']) and np.isfinite(g.loc[sec,'H1_original']) for sec in gids]);assert [gids[i] for i in ranking(q,p['score'])[:3]]==r['targets'],('target reconstruction',d);qual[d]=q;parts[d]=p
 events=[];entries=[];stockrows=[];groups_out=[]
 for k in range(1,len(tt)):
  prev,now=tt[k-1],tt[k];d0,d1=prev['day'],now['day'];removed=sorted(set(prev['targets'])-set(now['targets']));entered=sorted(set(now['targets'])-set(prev['targets']))
  if not removed:continue
  group_id=f'G{len(groups_out)+1:03d}';quarter=str(pd.Period(d1,'Q'));boundary=str(pd.Period(d0,'Q'))!=quarter;g0,g1=days[d0],days[d1];a0,a1=(amount[index[d]-25:index[d]+1] for d in [d0,d1]);p0,p1=parts[d0],parts[d1];q0,q1=qual[d0],qual[d1];V=p0['valid']&p1['valid'];f0,f1=calc(a0,V),calc(a1,V);fixedgood=f0['good']&f1['good'];global_change=not np.array_equal(p0['valid'],p1['valid']);ratio_change=not np.array_equal(p0['good'],p1['good']);coverage=global_change or ratio_change
  def agg(a):
   shares=a[:,V]/a[:,V].sum(axis=1)[:,None];return np.array([shares[:,groups[V]==i].sum(axis=1) for i in range(len(gids))])
  agg0,agg1=agg(a0),agg(a1);groups_out.append(dict(group_id=group_id,previous_day=d0,day=d1,quarter=quarter,cross_quarter_boundary=boundary,removed=removed,entered=entered,complete_denominator_changed=global_change,ratio_members_changed=ratio_change))
  def levels(i):
   ids=(groups==i)&fixedgood;return dict(fixed_members=int(ids.sum()),N0=float(np.median(f0['N'][ids])) if ids.any() else np.nan,N1=float(np.median(f1['N'][ids])) if ids.any() else np.nan,D0=float(np.median(f0['D'][ids])) if ids.any() else np.nan,D1=float(np.median(f1['D'][ids])) if ids.any() else np.nan,aggregate_recent_share0=float(np.median(agg0[i,-5:])),aggregate_recent_share1=float(np.median(agg1[i,-5:])),aggregate_prior_share0=float(np.median(agg0[i,:21])),aggregate_prior_share1=float(np.median(agg1[i,:21])))
  for sec in entered:
   i=gn[sec];entries.append(dict(group_id=group_id,day=d1,sector=sec,industry=names[sec],old_qualified=bool(q0[i]),new_qualified=bool(q1[i]),score0=p0['score'][i],score1=p1['score'][i],R21_0=g0.loc[sec,'R21'],R21_1=g1.loc[sec,'R21'],snapshot_total_share0=g0.loc[sec,'snapshot_amount_share'],snapshot_total_share1=g1.loc[sec,'snapshot_amount_share'],**levels(i)))
  for sec in removed:
   i=gn[sec];ids=(groups==i)&fixedgood;lv=levels(i);S00=np.median(f0['N'][ids]/f0['D'][ids]) if ids.any() else np.nan;S10=np.median(f1['N'][ids]/f0['D'][ids]) if ids.any() else np.nan;S01=np.median(f0['N'][ids]/f1['D'][ids]) if ids.any() else np.nan;S11=np.median(f1['N'][ids]/f1['D'][ids]) if ids.any() else np.nan;corners=np.array([S00,S10,S01,S11]);num=den=np.nan
   if np.isfinite(corners).all() and (corners>0).all():num=.5*(np.log(S10/S00)+np.log(S11/S01));den=.5*(np.log(S01/S00)+np.log(S11/S10));np.testing.assert_allclose(num+den,np.log(S11/S00),rtol=1e-12,atol=1e-12)
   outcomes={};minimal=[];single=[];primary='coverage_changed' if coverage else 'unknown'
   if not coverage:
    same=(groups==i)&p0['good'];assert np.array_equal(same,(groups==i)&p1['good']);N=[p0['N'][same],p1['N'][same]];DD=[p0['D'][same],p1['D'][same]]
    for mask in range(16):
     qq=q1 if mask&1 else q0;sc=(p1['score'] if mask&8 else p0['score']).copy();sc[i]=np.median(N[bool(mask&2)]/DD[bool(mask&4)]);outcomes[mask]=i not in ranking(qq,sc)[:3]
    assert not outcomes[0] and outcomes[15]
    minimal=[m for m in range(1,16) if outcomes[m] and not any(outcomes[s] for s in range(1,16) if s!=m and s&m==s)];single=[m for m in [1,2,4,8] if outcomes[m]];primary=({1:'qualification_single_sufficient',2:'numerator_single_sufficient',4:'denominator_single_sufficient',8:'opponent_single_sufficient'}[single[0]] if len(single)==1 else 'multiple_singletons_sufficient' if len(single)>1 else 'joint_required' if minimal else 'unknown')
   oldscore,newscore=p0['score'][i],p1['score'][i];ranked=ranking(q1,p1['score']);current_rank=ranked.index(i)+1 if i in ranked else None;threshold=p1['score'][ranked[2]] if len(ranked)>=3 else np.nan
   strong=bool(not coverage and outcomes.get(4) and not outcomes.get(11) and lv['N1']>=lv['N0'] and lv['aggregate_recent_share1']>=lv['aggregate_recent_share0'] and g0.loc[sec,'R21']>0 and g1.loc[sec,'R21']>0)
   row=dict(group_id=group_id,previous_day=d0,day=d1,quarter=quarter,cross_quarter_boundary=boundary,sector=sec,industry=names[sec],entered=entered,primary=primary,global_denominator_members_changed=global_change,original_ratio_members_changed=ratio_change,own_ratio_members_changed=not np.array_equal(p0['good']&(groups==i),p1['good']&(groups==i)),own_qualification_lost=bool(q0[i] and not q1[i]),any_qualification_changed=bool((q0!=q1).any()),opponent_qualification_changes=int(((q0!=q1)&(np.arange(len(gids))!=i)).sum()),own_score0=oldscore,own_score1=newscore,score_change=newscore-oldscore,score_log_change=np.log(newscore/oldscore) if oldscore>0 and newscore>0 else np.nan,current_rank=current_rank,current_third_score=threshold,rank_margin=newscore-threshold,self_score_not_weaker=bool(newscore>=oldscore),fixed_S00=S00,fixed_S10=S10,fixed_S01=S01,fixed_S11=S11,fixed_numerator_log_component=num,fixed_denominator_log_component=den,coverage_log_difference=np.log(newscore/oldscore)-np.log(S11/S00) if min(oldscore,newscore,S00,S11)>0 else np.nan,minimal_sufficient_masks=minimal,singleton_sufficient_masks=single,all16_outcomes=outcomes,strong_denominator_catchup_fact=strong,R21_0=g0.loc[sec,'R21'],R21_1=g1.loc[sec,'R21'],snapshot_total_share0=g0.loc[sec,'snapshot_amount_share'],snapshot_total_share1=g1.loc[sec,'snapshot_amount_share'],**lv);events.append(row)
   for j in np.flatnonzero(groups==i):stockrows.append(dict(group_id=group_id,sector=sec,sid=sids[j],day=d1,original_member0=bool(p0['good'][j]),original_member1=bool(p1['good'][j]),original_N0=p0['N'][j],original_N1=p1['N'][j],original_D0=p0['D'][j],original_D1=p1['D'][j],fixed_comparable=bool(ids[j]),fixed_N0=f0['N'][j],fixed_N1=f1['N'][j],fixed_D0=f0['D'][j],fixed_D1=f1['D'][j]))
 summary=dict(groups=len(groups_out),quarter_internal_groups=dict(collections.Counter(g['quarter'] for g in groups_out if not g['cross_quarter_boundary'])),cross_quarter_groups=sum(g['cross_quarter_boundary'] for g in groups_out),industry_exit_events=len(events),primary_counts=dict(collections.Counter(r['primary'] for r in events)),coexisting_own_qualification_lost=sum(r['own_qualification_lost'] for r in events),coexisting_global_denominator_change=sum(r['global_denominator_members_changed'] for r in events),coexisting_own_ratio_member_change=sum(r['own_ratio_members_changed'] for r in events),self_score_not_weaker_events=sum(r['self_score_not_weaker'] for r in events),strong_denominator_catchup_events=sum(r['strong_denominator_catchup_fact'] for r in events),numerator_log_negative=sum(r['fixed_numerator_log_component']<0 for r in events),denominator_log_negative=sum(r['fixed_denominator_log_component']<0 for r in events),events_original_E0_RS_still_qualified=sum(not r['own_qualification_lost'] for r in events),no_future_labels_read=True,top3_exact_days=len(tt),reconstructed_score_exact_with_float64_tolerance=True,seconds=time.monotonic()-start)
 for name,data in [('GROUPS',groups_out),('EXIT_EVENTS',events),('ENTRY_EVENTS',entries),('STOCK_NUMERATOR_DENOMINATOR',stockrows)]:save(name,data)
 cases=[]
 for predicate in [lambda r:r['strong_denominator_catchup_fact'],lambda r:r['self_score_not_weaker'] and not r['own_qualification_lost'],lambda r:r['primary']=='numerator_single_sufficient',lambda r:r['primary']=='joint_required',lambda r:r['primary']=='coverage_changed']:
  rs=[r for r in events if predicate(r) and r['sector'] not in {x['sector'] for x in cases}]
  if rs:cases.append(rs[0])
  if len(cases)==3:break
 save('CASES',cases);summary['seconds_with_output']=time.monotonic()-start;save('SUMMARY',summary);signal.setitimer(signal.ITIMER_REAL,0);print(json.dumps(norm(summary),ensure_ascii=False),flush=True);print('CASES',json.dumps(norm(cases),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR',dict(error=repr(e),traceback=traceback.format_exc()));raise

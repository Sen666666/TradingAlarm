"""Join separately frozen static industry channels to saved old-state/old-account records.
No opportunity rule, score, account, amount series or forward label is recalculated.
"""
from pathlib import Path
import pandas as pd,numpy as np,json,collections,hashlib
O=Path(__file__).resolve().parent;OLD=O.parent/'original_candidates';NEW=O.parent/'industry_selection/channels_v2/SNAPSHOTS_3D.parquet'
A=pd.read_parquet(O/'THREE_DATES_ORIGINAL_INDUSTRY_BASE.parquet');B=pd.read_parquet(NEW);F=pd.read_parquet(OLD/'ALL_STATIC_STOCKS_FACTS_H1_PVR.parquet')
for d in [A,B,F]:d['date']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d')
assert len(B)==270 and not B.duplicated(['date','sector_id_static']).any()
B=B.rename(columns={c:'new_'+c for c in B if c not in ['date','sector_id_static']});T=A.merge(B,on=['date','sector_id_static'],validate='one_to_one',indicator=True);assert T._merge.eq('both').all();T=T.drop(columns='_merge')
def tv(x):return None if pd.isna(x) else bool(x)
def label(r):
 c,s,u=tv(r.new_CONT),tv(r.new_START),tv(r.new_UNION)
 if u is None:return 'UNKNOWN'
 if not u:return 'NONE'
 if c and s:return 'BOTH'
 if c and s is False:return 'CONT_ONLY'
 if s and c is False:return 'START_ONLY'
 return 'UNION_TRUE_WITH_OTHER_CHANNEL_UNKNOWN'
T['new_static_opportunity_class']=T.apply(label,axis=1);T['new_union_status']=T.new_UNION.map(lambda x:'UNKNOWN' if pd.isna(x) else 'TRUE' if x else 'FALSE')
# This describes evidence actually present in the last old owner event, not a synthetic full budget snapshot.
pos=T.old_actual_financial_last_event_result.isin(['probe','confirmed','expanded'])&T.old_actual_financial_event_episode_matches_current_market&T.old_market_E0_valid.eq(True)
T['old_actual_positive_financial_grant_event_in_current_episode']=pos
T['old_actual_positive_financial_grant_event_bucket']=np.where(pos,T.old_actual_financial_last_event_level.map({0:'probe_event',1:'confirmed_event',2:'expanded_event'}),'NO_CURRENT_POSITIVE_SAVED_EVENT')
diag=[]
for d,g in F[F.date.isin(T.date.unique())].groupby(['date','sector_static']):
 allp=pd.to_numeric(g.PVR_cache_score,errors='coerce');sp=pd.to_numeric(g.loc[g.source_Q_core_or_CP_mobile,'PVR_cache_score'],errors='coerce')
 diag.append({'date':d[0],'sector_id_static':d[1],'old_PVR_median_all_static_known':allp.median(),'old_PVR_median_source_Q_known':sp.median(),'old_PVR_known_source_Q_stocks':int(np.isfinite(sp).sum())})
T=T.merge(pd.DataFrame(diag),on=['date','sector_id_static'],validate='one_to_one');T.to_csv(O/'THREE_DATES_NEW_CHANNELS_VS_ORIGINAL.csv',index=False);T.to_parquet(O/'THREE_DATES_NEW_CHANNELS_VS_ORIGINAL.parquet',index=False)
rows=[]
def total_counter(g,col):
 c=collections.Counter()
 for x in g[col]:c.update(json.loads(x))
 return dict(c)
for d,g in T.groupby('date',sort=True):
 for axis,col in [('UNION_STATUS','new_union_status'),('CHANNEL_CLASS','new_static_opportunity_class')]:
  for value,s in g.groupby(col,dropna=False,sort=True):
   rows.append({'date':d,'axis':axis,'group':value,'industries':len(s),'old_H1_rank0_min':s.old_H1_rank0_of90.min(),'old_H1_rank0_max':s.old_H1_rank0_of90.max(),'old_market_E0_true':int(s.old_market_E0_valid.eq(True).sum()),'old_market_authorization_usable':int(s.old_market_authorization_usable.eq(True).sum()),'old_market_stage_counts_json':json.dumps(s.old_market_stage.value_counts().to_dict(),ensure_ascii=False),'old_actual_current_episode_positive_grant_event_buckets_json':json.dumps(s.old_actual_positive_financial_grant_event_bucket.value_counts().to_dict(),ensure_ascii=False),'old_actual_last_financial_event_missing':int((~s.old_actual_financial_last_event_saved).sum()),'old_static_stocks':int(s.old_static_pool_stocks.sum()),'old_source_Q_stocks':int(s.old_source_Q_union_stocks.sum()),'old_pre_size_stocks':int(s.old_account_pre_size_roles_no_barriers_stocks.sum()),'old_pending_stocks':int(s.old_actual_pending_unique_stocks.sum()),'old_pending_core_intents':int(s.old_actual_pending_core_intents.sum()),'old_pending_mobile_intents':int(s.old_actual_pending_mobile_intents.sum()),'old_CLOSE_size_results_json':json.dumps(total_counter(s,'old_CLOSE_size_result_counts_json'),ensure_ascii=False),'old_nextOPEN_funding_results_json':json.dumps(total_counter(s,'old_nextOPEN_result_counts_json'),ensure_ascii=False),'old_nextOPEN_reserved_unique_stocks':int(s.old_nextOPEN_reserved_unique_stocks.sum()),'old_nextOPEN_reserved_pools_json':json.dumps(total_counter(s,'old_nextOPEN_reserved_pool_counts_json'),ensure_ascii=False),'new_flags_are_identification_not_permission_or_counterfactual_funding':True})
S=pd.DataFrame(rows);S.to_csv(O/'THREE_DATES_CHANNEL_PERMISSION_FUNNEL.csv',index=False)
foc=[('2024-09-24','URFI881129'),('2024-09-24','URFI881272'),('2026-01-15','URFI881121'),('2022-01-24','URFI881153')]
Z=T[[tuple(v) in foc for v in T[['date','sector_id_static']].to_numpy()]];Z.to_csv(O/'FOCAL_INDUSTRIES_NEW_CHANNELS_VS_OLD.csv',index=False)
checks={'industry_rows':len(T),'dates':sorted(T.date.unique()),'join_complete':True,'counts_by_date':[{ 'date':d,'CONT':int(g.new_CONT.eq(True).sum()),'START':int(g.new_START.eq(True).sum()),'UNION':int(g.new_UNION.eq(True).sum()),'UNKNOWN_UNION':int(g.new_UNION.isna().sum())}for d,g in T.groupby('date')],'new_rule_calculations_in_this_script':0,'new_scores_calculated':0,'new_accounts_or_orders':0,'forward_labels_read':False,'formal_PIT_verified':False,'source_SHA256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in [NEW,O/'THREE_DATES_ORIGINAL_INDUSTRY_BASE.parquet',OLD/'ALL_STATIC_STOCKS_FACTS_H1_PVR.parquet',Path(__file__)]}}
(O/'JOIN_AUDIT.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print('NEW_COUNTS',json.dumps(checks['counts_by_date'],ensure_ascii=False));print('FUNNEL',S[S.axis=='UNION_STATUS'][['date','group','industries','old_market_E0_true','old_market_authorization_usable','old_source_Q_stocks','old_pending_stocks','old_nextOPEN_reserved_unique_stocks']].to_string(index=False));print('FOCALS',Z[['date','industry_static','old_H1_score','old_H1_rank0_of90','new_CONT','new_START','new_UNION','new_rs_ind20','new_p_rs5','new_B_now','new_B_lag5_pairedU','new_dB5_paired','old_market_stage','old_market_authorization_usable','old_actual_positive_financial_grant_event_bucket','old_source_Q_union_stocks','old_actual_pending_unique_stocks','old_nextOPEN_reserved_unique_stocks','old_nextOPEN_result_counts_json']].to_string(index=False))

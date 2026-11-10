"""Read-only re-slice of verified original all-candidate inventory. No engine import or phase."""
from pathlib import Path
import json,hashlib,time,resource,csv
import pandas as pd
import pyarrow.dataset as ds
from datetime import datetime
B=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent;I=B/'daily_gap_inventory_v1'
P=B/'annual_2022_compound_tax_v1';A=P/'economic_run_2022_compound_once';C=B/'priority_halt_batch_sources_v1'
T=time.monotonic();seen={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def verify(p,h):
 p=Path(p);actual=seen.setdefault(str(p),sha(p));assert actual==h,str(p)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def write(n,df):
 with (O/n).open('x') as f:df.to_csv(f,index=False)
for folder,seal,key in [(I,'FINAL_INVENTORY_SEAL.json',None),(C,'FINAL_SEAL.json','files'),(B/'priority_halt_evidence_batch12_v1','FINAL_SEAL.json','files')]:
 s=read(folder/seal);mapping=s if key is None else s[key]
 for n,h in mapping.items():verify(folder/n,h)
for p,h in read(I/'SOURCE_HASHES.json').items():verify(p,h)
for rel,h in read(P/'AUTHOR_COMPLETION_SEAL.json')['file_sha256'].items():verify(P/rel,h)
u=pd.read_csv(I/'STOCK_UNIVERSE_V2.csv');events=pd.read_csv(I/'CANDIDATE_EVENT_STATIC_CHECKS.csv')
assert len(u)==1458 and len(events)==12917 and set(u.sid)==set(events.sid)
start='2022-06-29';end='2022-12-30'
panel=B.parent/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
cal=sorted(pd.read_parquet(panel,columns=['day']).day.dt.strftime('%Y-%m-%d').unique())
cal=[d for d in cal if start<=d<=end]
u['remaining_common_sessions']=[sum(d>=first for d in cal) for first in u.first_broad_next_open]
layers=read(A/'LAYERS.json');hold=[x for x in layers if x['qty']>0]
held={}
for x in hold:
 d=held.setdefault(x['sid'],{'round_ids':set(),'core':0,'add':0})
 d['round_ids'].add(x['round_id']);d[x['kind']]+=x['qty']
for v in held.values():v['round_ids']=sorted(v['round_ids'])
u['has_actual_positive_layer_at_2022_06_29_OPEN']=u.sid.isin(held)
u['membership_rule']='ALL_ORIGINAL_2022_AB_BIRTHS_FROM_FIRST_NEXT_COMMON_OPEN; NO_FUTURE_OUTCOME_FILTER'
write('ALL_1458_CANDIDATE_SCOPE.csv',u)
issue=pd.read_csv(I/'DAILY_ISSUES_V2.csv')
issue=issue[issue.day.between(start,end)].copy()
# Old shared path overlays stop months earlier, so drop those instead of relabeling them as current.
oldcols=[c for c in issue if c.startswith('actual_') or c.startswith('old_noshared_')]
issue=issue.drop(columns=oldcols)
issue['positive_layer_snapshot_now']=issue.sid.isin(held)
issue['future_ownership_not_predicted']=True
write('REMAINING_DAILY_ISSUES.csv',issue)
bad=issue[issue.issue.isin(['MISSING_ROW','INVALID_OPEN'])][['sid','day']].drop_duplicates().sort_values(['sid','day'])
sse=read(C/'SSE_HISTORY_ROWS.json');sz=read(C/'SZ_MONTHLY_ROWS.json')
dfmt=lambda x:x[:4]+'-'+x[4:6]+'-'+x[6:8]
prior=pd.read_csv(B/'priority_halt_evidence_batch12_v1/FINAL_CLASSIFICATION.csv').fillna('')
oldmatches=pd.read_csv(C/'TARGET_SESSION_MATCHES.csv').fillna('')
matches=[]
for z in bad.to_dict('records'):
 sid=z['sid'];day=z['day'];bounds=[];points=[]
 if sid.endswith('.SH'):
  for r in sse:
   if r['productCode']!=sid[:6] or r['controlType']!='TR' or not r['endStopDate'] or r['endStopDate'].startswith('9999'):continue
   if dfmt(r['startStopDate'])<=day<=dfmt(r['endStopDate']) and (r['type']=='LXTP' or r['type']=='LSTP' and r['stopTime']=='WH'):bounds.append(r['row_id'])
 else:
  for r in sz:
   if r['sid']!=sid:continue
   if r['resume'] is not None and r['start']<=day+' 09:30' and r['resume']>=day+' 15:00':bounds.append(r['row_id'])
   elif r['start']==day+' 09:30':points.append(r['row_id'])
 pp=prior[(prior.sid==sid)&(prior.episode_start<=day)&(prior.episode_end>=day)]
 oo=oldmatches[(oldmatches.sid==sid)&(oldmatches.day==day)]
 status='RETROSPECTIVE_BOUNDED_OFFICIAL_ROW_NO_PUBLIC_CLOCK' if bounds else 'START_POINT_ONLY_NO_COMPLETE_INTERVAL' if points else 'NO_BOUNDED_SUPPORT_IN_CACHED_LISTS'
 matches.append(dict(sid=sid,day=day,read_only_cached_class=status,row_ids=';'.join(bounds or points),
  was_in_old55_target_sessions=not oo.empty,
  prior_case_grades=';'.join(sorted(set(pp.grade))),
  prior_case_review_candidate=any(day in str(v).split(';') for v in pp.review_candidate_sessions),
  prior_case_clock_bounds=';'.join(sorted(set(pp.known_at_upper_bound)-{''})),
  positive_layer_snapshot_now=sid in held,new_permission_granted=False,current_known_at_certified=False,
  future_ownership_not_predicted=True))
matches=pd.DataFrame(matches);write('ALL_CACHED_HALT_MATCHES.csv',matches)
gaps=pd.read_csv(I/'MISSING_ROW_RUNS_V2.csv')
gaps=gaps[(gaps.gap_start<=end)&(gaps.gap_end>=start)].copy()
gaps=gaps.drop(columns=[c for c in gaps if c.startswith('actual_') or c.startswith('old_noshared_')])
gaps['remaining_missing_sessions']=[int(((issue.sid==r.sid)&issue.day.between(max(start,r.gap_start),min(end,r.gap_end))&(issue.issue=='MISSING_ROW')).sum()) for r in gaps.itertuples()]
gaps['positive_layer_snapshot_now']=gaps.sid.isin(held)
gaps['future_ownership_not_predicted']=True
write('REMAINING_MISSING_RUNS.csv',gaps)
episodes=pd.read_csv(I/'UNUSABLE_QUOTE_EPISODES.csv')
episodes=episodes[(episodes.episode_start<=end)&(episodes.episode_end>=start)].copy()
write('REMAINING_UNUSABLE_EPISODES_REFERENCE.csv',episodes)
trans=pd.read_csv(I/'FACTOR_LINEAGE_TRANSITIONS_V2.csv')
trans=trans[trans.day.between(start,end)].copy()
trans=trans.drop(columns=[c for c in trans if c.startswith('actual_') or c.startswith('old_noshared_')])
facts=read(P/'FACTS_DERIVED_CANDIDATES.json');extra={(x['sid'],x['ex_date']):x['economic_event_id'] for x in facts['new_pure_cash']+facts['new_compound']}
trans['additional_current_442_event']=[extra.get((r.sid,r.day),'') for r in trans.itertuples()]
trans['current_442_coordinate_candidate_covered']=trans.kind.str.contains('FACTOR_TRANSITION_ADMITTED_COORDINATE')|trans.additional_current_442_event.ne('')
trans['positive_layer_snapshot_now']=trans.sid.isin(held)
trans['future_ownership_not_predicted']=True
write('REMAINING_FACTOR_AND_SOURCE_TRANSITIONS.csv',trans)
write('CURRENT_POSITIVE_LAYER_FUTURE_GAPS.csv',gaps[gaps.sid.isin(held)])
write('CURRENT_POSITIVE_LAYER_FUTURE_TRANSITIONS.csv',trans[trans.sid.isin(held)])
raw_path='/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet'
table=ds.dataset(raw_path,format='parquet').to_table(filter=(ds.field('symbol')=='002703.SZ')&(ds.field('trade_date')>=datetime(2022,6,24))&(ds.field('trade_date')<=datetime(2022,7,15)),columns=['symbol','trade_date','open','close','volume','source'])
write('002703_RAW_NEIGHBOR_ROWS.csv',table.to_pandas())
row=u[u.sid.eq('002703.SZ')].iloc[0];verify(row.signal_path,row.signal_sha256)
sig=pd.read_parquet(row.signal_path)
if 'day' in sig: sig=sig.set_index('day')
near=sig.loc[(sig.index>=pd.Timestamp('2022-06-24'))&(sig.index<=pd.Timestamp('2022-07-15'))]
cols=[c for c in ['raw_open','raw_close','adjustment_factor','source_kind','source_path','observed_bar','price_eligible','source_invalid','synthetic_event_bar'] if c in near]
write('002703_FROZEN_SIGNAL_NEIGHBOR_ROWS.csv',near[cols].reset_index())
missing=['2022-06-29','2022-06-30','2022-07-01','2022-07-04','2022-07-05']
assert not set(missing)&set(table.to_pandas().trade_date.dt.strftime('%Y-%m-%d'))
save('CURRENT_ACTUAL_RESPONSIBILITY.json',{'asof':'2022-06-29 COMPLETE OPEN','positive_layer_security_count':len(held),'positive_layer_count':len(hold),'holdings':held,'future_holding_not_assumed':True})
summary={'status':'READ_ONLY_REMAINING_DOMAIN_INVENTORY_NO_PERMISSION_OR_ECONOMIC_RUN','range':[start,end],
 'all_original_2022_birth_events':len(events),'all_birth_candidate_sids':len(u),'original_source_fixed_universe_count':1709,'common_sessions':len(cal),'broad_stock_sessions':int(u.remaining_common_sessions.sum()),
 'domain_not_pruned_by_fixed_budget_or_realized_future_results':True,
 'raw_and_indicator_issue_counts':issue.issue.value_counts().to_dict(),'unique_unusable_stock_sessions':len(bad),'unusable_sids':bad.sid.nunique(),'overlapping_missing_run_count':len(gaps),'overlapping_unusable_episode_count':len(episodes),
 'boundary_counts_clipped_to_remaining_range':True,
 'all_cached_rows_rematch_counts':matches.read_only_cached_class.value_counts().to_dict(),
 'cached_original55_target_days':int(matches.was_in_old55_target_sessions.sum()),'newly_matched_bounded_days_beyond_old55':int(((matches.read_only_cached_class=='RETROSPECTIVE_BOUNDED_OFFICIAL_ROW_NO_PUBLIC_CLOCK')&~matches.was_in_old55_target_sessions).sum()),
 'all_retrospective_matches_need_public_clock_and_equity_scope_review':True,'new_registered_sessions':0,
 'transitions_total':len(trans),'transition_kinds':trans.kind.value_counts().to_dict(),'additional_four_cash_coordinate_candidates':int(trans.additional_current_442_event.ne('').sum()),
 'factor_transitions_without_current442_event':int((trans.kind.str.contains('FACTOR_TRANSITION')&~trans.current_442_coordinate_candidate_covered).sum()),
 'source_lineage_rows':trans[trans.kind.str.contains('SOURCE_LINEAGE')].to_dict('records'),
 'current_positive_layer_snapshot_sids':len(held),'current_positive_layer_future_gap_runs':len(gaps[gaps.sid.isin(held)]),'current_positive_layer_future_gap_sids':sorted(set(gaps[gaps.sid.isin(held)].sid)),
 'all_current_positive_layer_future_factor_rows_covered_in442':bool(trans[trans.sid.isin(held)&trans.kind.str.contains('FACTOR_TRANSITION')].current_442_coordinate_candidate_covered.all()),
 'current_stop_missing_not_invalid_quote':{'sid':'002703.SZ','missing_sessions':missing,'previous_real':'2022-06-28 OPEN14.52 CLOSE15.56','next_observed_real':'2022-07-06 OPEN14 CLOSE14','next_bar_not_by_itself_official_resume_proof':True},
 'verified_prior_hash_count':len(seen),'engine_imports':0,'economic_phases':0,'external_source_rescan':False,'reused_immutable_original_inventory_after_hash_verification':True,
 'research_limits':['All1458 original A/B names retained, from their first next common OPEN. Not all-A-share or PIT-certified universe.',
  'Current positive layers are a snapshot, not future holdings; none of51 gaps is automatically a future account blocker.',
  'Source factor and lineage transitions are workload candidates, not automatically bad data or trade responsibility.',
  'Existing historical halt rows alone lack publication clock; no new carry, fill, registration or risk release granted.',
  'One synthetic nonquote600345 Aug5 remains unusable; do not convert it to observed quote.',
  'Many possible later equity events still lack an admitted consumer; no promised full-year completion.'],
 'elapsed_seconds':time.monotonic()-T,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
save('INVENTORY_RESULT.json',summary)
save('INVENTORY_SOURCE_HASHES.json',seen)
save('INVENTORY_SEAL.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name not in ('REQUEST_LEDGER.jsonl','SEARCH_BUDGET.json')})
print(json.dumps(summary,ensure_ascii=False,indent=2))

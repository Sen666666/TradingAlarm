"""Freeze user-specified case windows from saved PRIMARY/book evidence only."""
from pathlib import Path
from collections import Counter
import gzip,json,hashlib

OUT=Path(__file__).resolve().parent
EQ=OUT.parents[1]
PRIMARY=EQ/'pvr_information_v1/universe_audit/PRIMARY_CANDIDATES.jsonl'
BOOKS=EQ/'trend_exit_controls_v1/runs/BASELINE'
SCOPES=[dict(sid='000620.SZ',window='2022_2024',periods=[['2022-01-01','2022-01-31']]),
 dict(sid='300666.SZ',window='strong',periods=[['2025-07-01','2026-06-30']]),
 dict(sid='300085.SZ',window='2022_2024',periods=[['2024-09-12','2024-10-31']]),
 dict(sid='002583.SZ',window='2022_2024',periods=[['2024-01-01','2024-01-31'],['2024-09-01','2024-11-30']])]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def include(window,day,sid):
 return any(s['sid']==sid and s['window']==window and any(a<=day<=b for a,b in s['periods'])for s in SCOPES)
sources={};candidates=[];day_counts=Counter();n=0
save('FIXED_CASE_SCOPE_BEFORE_NEW_FEATURES.json',dict(status='FIXED_USER_SPECIFIED_WINDOWS_NO_OUTCOME_SELECTION',scopes=SCOPES,
 new_features_read=False,new_scores_or_rankings_computed=False,new_future_labels=False,new_account_runs=0))
sources[str(PRIMARY.resolve())]=sha(PRIMARY)
with PRIMARY.open()as f:
 for line in f:
  r=json.loads(line);n+=1;day_counts[(r['window'],r['day'])]+=1
  if include(r['window'],r['day'],r['sid']):
   r=dict(r,original_PVR_candidate_ordinal_1based=r['original_PVR_slot']+1,
    original_H1_candidate_ordinal_1based=r['original_H1_slot']+1,
    new_score_status='NOT_READ_WAIT_SHARED_FEATURE_EXPORT',new_rank_status='NOT_READ_WAIT_PARENT_RANKING')
   candidates.append(r)
assert n==133713
for r in candidates:r['same_day_original_pending_stocks']=day_counts[(r['window'],r['day'])]
bykey={(r['window'],r['day'],r['sid']):r for r in candidates};assert len(bykey)==len(candidates)
opportunities=[];trades=[];target_intents=[];expected=[]
for window in ['2022_2024','strong']:
 for filename in ['daily.jsonl.gz','opportunities.jsonl.gz']:
  path=BOOKS/window/'pair'/filename;sources[str(path.resolve())]=sha(path)
  with gzip.open(path,'rt')as f:
   for line in f:
    r=json.loads(line)
    if filename=='daily.jsonl.gz':
     day=r['at'][:10]
     for spec in SCOPES:
      if include(window,day,spec['sid']):expected.append((window,day,spec['sid']))
    elif include(window,r['day'],r['sid']):opportunities.append(dict(window=window,**r))
 path=BOOKS/window/'pair/B.json.gz';sources[str(path.resolve())]=sha(path)
 with gzip.open(path,'rt')as f:book=json.load(f)
 for r in book['trades']:
  day=r.get('signal_at','')[:10]
  if r['side']=='buy'and include(window,day,r['security_id']):
   k=(window,day,r['security_id']);assert k in bykey
   trades.append(dict(window=window,**r,original_candidate=bykey[k]))
 for d in book['decisions']:
  day=d['at'][:10]
  for r in d['intents']:
   if include(window,day,r['sid']):target_intents.append(dict(window=window,day=day,decision_at=d['at'],**r))
ops={(r['window'],r['day'],r['sid']):r for r in opportunities};assert len(ops)==len(opportunities)
assert set(expected)==set(ops),'Original target opportunity/calendar mother differs'
coverage=[]
for k in expected:
 op=ops[k];candidate=bykey.get(k)
 if candidate:status='ORIGINAL_PRIMARY_CANDIDATE'
 elif op['barriers']:status='NOT_CANDIDATE_ORIGINAL_BARRIERS'
 elif not op['roles']:status='NOT_CANDIDATE_NO_ORIGINAL_ROLES'
 else:status='NOT_CANDIDATE_NO_POSITIVE_PENDING_SIZE_OR_QUOTE_NOT_RESOLVED'
 coverage.append(dict(window=k[0],day=k[1],sid=k[2],original_status=status,
  original_opportunity=op,original_primary=candidate,
  comparison_status='ORIGINAL_PVR_READY_NEW_SCORE_UNCHECKED'if candidate and candidate['original_PVR_ready']else'NO_ORIGINAL_LEGAL_CANDIDATE_COMPARISON'if candidate is None else'ORIGINAL_PVR_UNKNOWN_NEW_SCORE_UNCHECKED'))
save('ALL_FIXED_ORIGINAL_PRIMARY_CANDIDATES.json',candidates)
save('ALL_FIXED_ORIGINAL_OPPORTUNITIES.json',opportunities)
save('ALL_FIXED_ACTUAL_BUYS_ORIGINAL_BOOK.json',trades)
save('ALL_FIXED_ORIGINAL_INTENTS.json',target_intents)
save('ALL_FIXED_MARKET_DAY_COVERAGE.json',coverage)
summary=[]
for spec in SCOPES:
 sid=spec['sid'];cr=[r for r in candidates if r['sid']==sid];tr=[r for r in trades if r['security_id']==sid]
 cov=[r for r in coverage if r['sid']==sid]
 summary.append(dict(**spec,market_decision_days=len(cov),candidate_days=len(cr),original_PVR_ready=sum(r['original_PVR_ready']for r in cr),
  candidate_dates=[r['day']for r in cr],actual_buy_fills=len(tr),
  actual_signal_dates=sorted(set(r['signal_at'][:10]for r in tr)),actual_layers=[r['layer']for r in tr],
  missing_status_counts=dict(Counter(r['original_status']for r in cov if r['original_status']!='ORIGINAL_PRIMARY_CANDIDATE'))))
assert all(sha(p)==h for p,h in sources.items())
receipt=dict(status='FIXED_ORIGINAL_FOUR_CASE_WINDOWS_COMPLETE',original_primary_mother=n,case_scopes=summary,
 selected_candidates=len(candidates),all_original_candidate_ready=sum(r['original_PVR_ready']for r in candidates),
 target_market_stock_days=len(coverage),new_features_read=False,new_scores=0,new_future_labels=0,new_rankings=0,new_account_runs=0,
 source_sha256=sources,rank_definition='final_slot+1 is original same-day full pending candidate ordinal; numeric priority key is not global PVR rank',
 comparison_limit='Absent original legal candidate has no comparable new rank. New fast/slow availability/rank remains unchecked until shared export.',
 signal_clock='Original decision CLOSE; saved actual fills are later original facts, never date-selection input.')
save('ORIGINAL_CASE_AUDIT_RECEIPT.json',receipt)
print(json.dumps({k:v for k,v in receipt.items()if k!='source_sha256'},ensure_ascii=False))

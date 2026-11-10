"""Correct same-open context filter only. No scores, matching, labels or accounts."""
from pathlib import Path
from datetime import datetime,timezone
import json,gzip,hashlib,collections,shutil
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;OLD=W/'opportunity-quality-ranking-20261031'
ROOTS={'2022':W/'2022-normal-reference-20261031/runs/B_diag/pair','2025_26':W/'q2-normal-continuation-20261031/runs/B_diag/pair'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');t.replace(p)
meta=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
archive=O/'capital-time-filter-errata-v1';archive.mkdir(exist_ok=False)
for name in ['CAPITAL_CHAIN_READINESS.json','2022/POTENTIAL_COMPETITION.json','2025_26/POTENTIAL_COMPETITION.json']:
 p=archive/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(O/name,p)
shutil.copy2(O/'prepare_only.py',archive/'prepare_only.py')
before=sha(O/'PAIR_ID_FREEZE.json');cap={}
for win,root in ROOTS.items():
 rs=list(rows(OLD/win/'CANDIDATES.jsonl.gz'));ks={(r['sid'],r['day'],r['receipt']) for r in rs};op={}
 for r in rows(root/'opportunities.jsonl.gz'):
  k=r['sid'],r['day'],r['CP1_id']
  if k in ks:op[k]=r
 daily={r['at'][:10]:r['on'] for r in rows(root/'daily.jsonl.gz')};cal=list(daily);nextday=dict(zip(cal,cal[1:]));fund=list(rows(root/'funding.jsonl.gz'))
 fm=collections.defaultdict(list);prefix={};prior=collections.defaultdict(list)
 for i,r in enumerate(fund):
  fm[r['sid'],r['at'][:10]].append((i,r))
  if '09:30:00' in r['at']:
   prefix[i]=list(prior[r['at'][:10]])
   if r['result']=='reserved':prior[r['at'][:10]].append(dict(sid=r['sid'],sector=meta[r['sid']]['sector_id'],role=r['role'],pool=r.get('pool'),shares=r.get('shares')))
 count=collections.Counter();detail=[]
 for r in rs:
  k=r['sid'],r['day'],r['receipt'];s=op[k];nd=nextday.get(r['day']);oo=[(i,x) for i,x in fm[r['sid'],nd] if '09:30:00' in x['at']] if nd else []
  close=[x for i,x in fm[r['sid'],r['day']] if '15:10:00' in x['at'] and x['role']=='mobile']
  mm=[(i,x) for i,x in oo if x['role']=='mobile'];assert len(mm)<=1,(win,k,mm)
  count['ACT_paused' if not daily[r['day']] else 'ACT_on']+=1;count['already_held' if s['held'] else 'not_held']+=1;count['core_role_same_stock' if 'core' in s['roles'] else 'no_core_role_same_stock']+=1
  core=any(x['role']=='core' and x['result']=='reserved' for i,x in oo)
  if core and not mm:count['core_reserved_no_mobile_open_record']+=1
  for x in close:count['authorization_close_mobile_result:'+x['result']]+=1
  for reason in s['barriers']:count['asof_barrier:'+reason]+=1
  if not nd:count['next_open_outside_saved_window']+=1
  for i,x in mm:
   count['mobile_open_result:'+x['result']]+=1
   if any(z in x['result'] for z in ['pool_capital','probe_risk','sector_risk','sector_capital','cash','confirmed_unfunded']):
    earlier=prefix[i];cross=[z for z in earlier if z['sector']!=r['sector']];same=[z for z in earlier if z['sector']==r['sector']]
    count['resource_rejection_receipts']+=1;count['resource_rejection_with_earlier_NEW_order']+=int(bool(earlier));count['resource_rejection_with_cross_industry_NEW_order']+=int(bool(cross));count['resource_rejection_with_same_industry_NEW_order']+=int(bool(same))
    detail.append(dict(sid=r['sid'],day=r['day'],receipt=r['receipt'],opening=nd,raw_reason=x['result'],earlier_actual_NEW_reservations=earlier,only_potential_competition_not_substitution_proof=True))
 cap[win]=dict(events=len(rs),flags_and_raw_reasons=dict(count),classification_nonexclusive=True,validated_fixed_state_one_order_substitutions=0)
 save(win+'/POTENTIAL_COMPETITION.json',detail)
# Inventory already-audited resource projections; do not construct a new state.
points=[]
for opening,sid in [('2025-09-01','601869.SH'),('2025-12-19','601869.SH'),('2026-04-22','301511.SZ')]:
 p=W/'migration-singlepass-causal-review-20261101/points'/f'{opening}_{sid}_SC.json';r=json.loads(p.read_text());day=r['previous'];f=pd.read_parquet(O/'2025_26/FEATURES.parquet');z=f[(f.symbol==sid)&f.date.eq(pd.Timestamp(day))];pairs=pd.read_parquet(O/'2025_26/PAIRS_PRE_OUTCOMES.parquet');hit=pairs[pairs.date.eq(day)&(pairs.h1_symbol.eq(sid)|pairs.other_symbol.eq(sid))]
 points.append(dict(path=str(p),sha256=sha(p),sid=sid,authorization=day,opening=opening,resource_projection_not_full_Account=True,mother_events=len(z),feature_ready=bool(z.iloc[0].feature_ready) if len(z) else None,matched_pairs=len(hit),earlier_NEW_orders=len(r['earlier_open_reservations']),fixed_state_substitution_verified=False))
cap['exact_state_inventory']=dict(2022_contexts=0,strong_target_contexts=3,strong_contexts_with_earlier_NEW_order=sum(x['earlier_NEW_orders']>0 for x in points),contexts_in_matched_pairs=sum(x['matched_pairs']>0 for x in points),validated_one_order_substitutions=0,points=points,unknown='all other receipts lack independently validated fixed-prefix resources/fee/cash/pending/ownership projections; daily+funding context cannot prove local replacement')
save('CAPITAL_CHAIN_READINESS.json',cap);assert sha(O/'PAIR_ID_FREEZE.json')==before
save('CAPITAL_TIME_FILTER_CORRECTION.json',dict(corrected_at=datetime.now(timezone.utc).isoformat(),reason='initial context lookup included next-day close sizing records; corrected strictly next-session09:30; no matching/score/label/account changes',preserved='capital-time-filter-errata-v1',pair_ID_freeze_unchanged=True,new_accounts=0))
print(json.dumps({win:cap[win]['flags_and_raw_reasons'] for win in ROOTS},ensure_ascii=False));print('EXACT_CONTEXTS',json.dumps({k:v for k,v in cap['exact_state_inventory'].items() if k!='points'},ensure_ascii=False))

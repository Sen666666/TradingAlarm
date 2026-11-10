from pathlib import Path
from collections import Counter
from statistics import median,mean
import json,gzip,hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/reentry_v1');P=O/'funding_agent/private_projection';read=lambda p:json.loads(p.read_text())
labels_path=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031/2025_26/PRICE_LABELS.jsonl.gz')
source=read(O/'ADDED_LABEL_SOURCE_SHA256.json');assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in source.items())
comparisons=read(P/'ON_ALL4172_CANDIDATE_COMPARISONS.json');out=read(O/'ADDED_AND_CUT_EXISTING_LABELS.json');summary=read(O/'ADDED_EXISTING_LABEL_SUMMARY.json')
assert len(comparisons)==4172 and len({r['key'] for r in comparisons})==4172
ls={};duplicates=0
with gzip.open(labels_path,'rt') as f:
 for r in map(json.loads,f):
  k=r['sid'],r['day'],r['receipt']
  if k in ls:assert ls[k]==r['labels'];duplicates+=1
  ls[k]=r['labels']
expected=[r for r in comparisons if r['status'] in ['added_intent','shrunk_original_intent','lost_original_intent']]
assert len(expected)==len(out)==149
for a,b in zip(expected,out):
 assert all(b[k]==v for k,v in a.items())
 order=a['ON_order'] or a['OFF_order'];day=order['key'].split('|')[1][:10]
 assert b['signal_day']==day and b['existing_price_labels']==ls.get((a['sid'],day,a['CP1_id']))
# Independently rederive all comparison statuses from frozen original/alternative orders.
for f in P.glob('OFF_2026*.json'):
 day=f.stem[4:];off={r['key']:r for r in read(f)['orders']};on={r['key']:r for r in read(P/f'ON_{day}.json')['orders']}
 for r in [x for x in comparisons if x['opening']==day]:
  a=off.get(r['key']);b=on.get(r['key'])
  assert a==r['OFF_order'] and b==r['ON_order']
  if not a and b:assert r['status']=='added_intent'
  if a and not b:assert r['status']=='lost_original_intent'
  if a and b and b['quantity']<a['quantity']:assert r['status']=='shrunk_original_intent'
groups={'added_all':[x for x in out if x['status']=='added_intent'],'added_semiconductor':[x for x in out if x['status']=='added_intent' and x['industry']=='半导体'],'added_original_flat_reentry':[x for x in out if x['status']=='added_intent' and x['entry_kind']=='flat_actual_original_reentry'],'shrunk_original':[x for x in out if x['OFF_order'] and x['ON_order'] and x['quantity_delta']<0]}
ind={}
for name,rs in groups.items():
 assert len(rs)==summary[name]['events'] and len({r['sid'] for r in rs})==summary[name]['unique_stocks']
 ind[name]={'events':len(rs),'unique_stocks':len({r['sid'] for r in rs}),'horizons':{}}
 for h in ['21','63']:
  valid=[r['existing_price_labels'][h] for r in rs if r['existing_price_labels'] and r['existing_price_labels'][h]['valid']]
  v={'known':len(valid),'unknown_or_original_invalid':len(rs)-len(valid),'endpoint_median_pct':median(x['return_pct'] for x in valid) if valid else None,'negative_endpoints':sum(x['return_pct']<0 for x in valid),'MFE30':sum(x['right_tail_MFE30'] for x in valid)}
  for k,x in v.items():assert x==summary[name]['horizons'][h][k]
  ind[name]['horizons'][h]=v
result={'status':'PASS_KEEP_COMPONENT_ECONOMICS_UNVERIFIED','old_label_keys':len(ls),'duplicate_old_keys_with_identical_labels':duplicates,'complete_added_and_cut_rows':len(out),'full_candidate_comparisons':4172,'independent_summary':ind,'interpretation':'Local-high gate remains stopped. Confirmed-min-first is not established as the main repair, but1/15 focus rescue cannot negate the other added opportunities. Preserve demonstrated accessible-opportunity component. Overall economic value remains unverified. This audit neither authorizes a new account nor selects a rule using these outcomes.','scope':'Only join and complete denominator checks against already saved labels; no new price labels or financial replay. Horizon labels start at original signal CLOSE and follow original stock valid-price-observation clock, not actual fill/holding/account return. MFE30 is a price excursion, not realized profit; missing/core rows remain unknown.','new_accounts':0,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'ADDED_OPPORTUNITY_LABEL_PROTOCOL.txt',O/'join_added_labels.py',O/'ADDED_EXISTING_LABEL_SUMMARY.json',O/'ADDED_AND_CUT_EXISTING_LABELS.json',O/'ADDED_LABEL_SOURCE_SHA256.json']}}
(O/'review/ADDED_EXISTING_LABEL_JOIN_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['source_sha256','independent_summary']},ensure_ascii=False,indent=2))

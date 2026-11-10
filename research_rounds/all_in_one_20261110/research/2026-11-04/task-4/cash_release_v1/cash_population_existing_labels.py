"""Read-only coverage join of existing labels; never fill unknown outcomes."""
from pathlib import Path
from collections import defaultdict
import gzip,hashlib,json,statistics,time
O=Path(__file__).resolve().parent;T=O.parent.parent/'task'
Q=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031')
S={}
def bind(p):
 p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def gz(p,lines=False):
 with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h)) if lines else json.load(h)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
start=time.monotonic();bind(__file__)
labels={}
for sub in ['2022','2025_26']:
 for r in gz(Q/sub/'PRICE_LABELS.jsonl.gz',True):
  k=(r['sid'],r['day'],r['receipt']);assert k not in labels;labels[k]=r['labels']
roots={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair','strong':T/'pvr_pool_feasibility/runs/2025_26/pair'}
keys={}
for w,root in roots.items():
 b=gz(root/'B.json.gz')
 keys[w]={(d['at'][:10],i['sid'],i['role']):i.get('CP1_id') for d in b['decisions'] for i in d['intents']}
group=defaultdict(list)
for r in gz(O/'ALL_ORIGINAL_CASH_REJECTS.jsonl.gz',True):
 cp=keys[r['window']][r['signal_day'],r['sid'],r['role']]
 lab=labels.get((r['sid'],r['signal_day'],cp))
 for role in ['all',r['role']]:
  group[r['window'],r['OPEN'][:4],role,'all_cash_reject_events'].append(lab)
  if r['original_permission_eligible']:group[r['window'],r['OPEN'][:4],role,'mature_release_criterion'].append(lab)
summary=[]
for k,xs in sorted(group.items()):
 z=dict(window=k[0],year=k[1],role=k[2],stratum=k[3],role_events=len(xs),horizons={})
 for h in ['21','63']:
  a=[l[h] for l in xs if l and l[h]['valid']]
  z['horizons'][h]=dict(known=len(a),unknown_or_original_invalid=len(xs)-len(a),
    endpoint_median_pct=statistics.median(l['return_pct'] for l in a) if a else None,
    negative_endpoints=sum(l['return_pct']<0 for l in a),MFE30=sum(l['right_tail_MFE30'] for l in a))
 summary.append(z)
save('ALL_CASH_POPULATION_EXISTING_LABEL_COVERAGE.json',summary)
save('POPULATION_LABEL_SCOPE.json',dict(
 label_source='Existing 2022 and 2025_26 fixed21/63 stock-valid-price-observation labels, no new prices; no dedicated 2023/2024 label sets; any exact cross-year keys retained and all other cases unknown',
 key='original frozen intent signal_day,sid,CP1_id; role repeated events explicitly not independent stocks',
 unknown='No imputation and no claim known subset represents full mother',
 evaluation='Stock price from signal CLOSE, not release orders, fills, held returns or account profit',
 accounts=0,new_labels=0,seconds=time.monotonic()-start))
save('POPULATION_LABEL_SOURCE_SHA256.json',S)
print(json.dumps([r for r in summary if r['role']=='mobile' and r['stratum']=='mature_release_criterion'],ensure_ascii=False,indent=2))

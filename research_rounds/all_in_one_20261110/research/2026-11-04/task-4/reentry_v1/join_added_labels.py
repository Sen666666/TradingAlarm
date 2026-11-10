from pathlib import Path
import json,gzip,statistics,hashlib
O=Path(__file__).resolve().parent;P=O/'funding_agent/private_projection'
labels=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031/2025_26/PRICE_LABELS.jsonl.gz')
rows=json.loads((P/'ON_ALL4172_CANDIDATE_COMPARISONS.json').read_text())
with gzip.open(labels,'rt') as f:ls={(x['sid'],x['day'],x['receipt']):x['labels'] for x in map(json.loads,f)}
out=[]
for r in rows:
 if r['status'] not in ['added_intent','shrunk_original_intent','lost_original_intent']:continue
 order=r['ON_order'] or r['OFF_order'];day=order['key'].split('|')[1][:10]
 out.append(dict(r,signal_day=day,existing_price_labels=ls.get((r['sid'],day,r['CP1_id']))))
groups={'added_all':[x for x in out if x['status']=='added_intent'],
        'added_semiconductor':[x for x in out if x['status']=='added_intent' and x['industry']=='半导体'],
        'added_original_flat_reentry':[x for x in out if x['status']=='added_intent' and x['entry_kind']=='flat_actual_original_reentry'],
        'shrunk_original':[x for x in out if x['OFF_order'] and x['ON_order'] and x['quantity_delta']<0]}
summary={}
for name,xs in groups.items():
 summary[name]={'events':len(xs),'unique_stocks':len({x['sid'] for x in xs}),'horizons':{}}
 for h in ['21','63']:
  zz=[x['existing_price_labels'][h] for x in xs if x['existing_price_labels'] and x['existing_price_labels'][h]['valid']]
  summary[name]['horizons'][h]=dict(known=len(zz),unknown_or_original_invalid=len(xs)-len(zz),endpoint_mean_pct=statistics.mean(z['return_pct'] for z in zz) if zz else None,endpoint_median_pct=statistics.median(z['return_pct'] for z in zz) if zz else None,negative_endpoints=sum(z['return_pct']<0 for z in zz),MFE30=sum(z['right_tail_MFE30'] for z in zz),MAE_mean_pct=statistics.mean(z['MAE_pct'] for z in zz) if zz else None)
for name,x in [('ADDED_AND_CUT_EXISTING_LABELS.json',out),('ADDED_EXISTING_LABEL_SUMMARY.json',summary)]: (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
sources=[labels,P/'ON_ALL4172_CANDIDATE_COMPARISONS.json',O/'ADDED_OPPORTUNITY_LABEL_PROTOCOL.txt',Path(__file__)]
(O/'ADDED_LABEL_SOURCE_SHA256.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2));print('STATUSES',sorted({x['status'] for x in rows}))

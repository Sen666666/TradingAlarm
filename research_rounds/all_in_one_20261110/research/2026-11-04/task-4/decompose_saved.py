"""Existing exported stocks/layers only; arithmetic, not a counterfactual."""
from pathlib import Path
from collections import Counter
import json, hashlib
from decimal import Decimal as D
O=Path(__file__).resolve().parent
T=O.parent/'task'
src={}
def read(p):
 p=Path(p);src[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
a=read(O/'SEMICONDUCTOR_ALL126_COMPARISON.json')
f={pol:{x['sid']:x for x in a if x['policy']==pol} for pol in ['PVR_BASELINE','PVR_NO60']}
old={s for s,x in f['PVR_BASELINE'].items() if x['actual_layers']};new={s for s,x in f['PVR_NO60'].items() if x['actual_layers']}
res={}
for name,ids in [('both',old&new),('baseline_only',old-new),('No60_only',new-old)]:
 res[name]={'stocks':len(ids),'members':[{'sid':s,'name':f['PVR_BASELINE'][s]['name'],'old_net':f['PVR_BASELINE'][s]['actual_net'],'new_net':f['PVR_NO60'][s]['actual_net'],'old_cost':f['PVR_BASELINE'][s]['actual_buy_cost'],'new_cost':f['PVR_NO60'][s]['actual_buy_cost']} for s in sorted(ids)]}
 for pol in f:res[name][pol]={'cost':sum(f[pol][s]['actual_buy_cost'] for s in ids),'net':sum(f[pol][s]['actual_net'] for s in ids)}
save('SEMICONDUCTOR_STOCK_DELTA_DECOMPOSITION.json',res)
weekly=read(O/'SEMICONDUCTOR_WEEKLY_CHAIN.json')
market=read(T/'participation/PVR_SEMICONDUCTOR_CHAIN/DAILY_CLOSE_RESOURCE_ALL116.json')
# Market stage is identical for the two books, funding/holdings are not.
cap=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/semiconductor-2026H1-readonly/DAILY_ALIGNED_CAPITAL.json')
cap={r['day']:r for r in cap if r['industry']=='半导体'}
funnel={p:read(T/f'loss_correction/no60_behavior_v1/{p}-SEMICONDUCTOR_FUNNEL.json')['all_market_receipts'] for p in f}
life=read(T/'loss_correction/no60_behavior_v1/SEMICONDUCTOR_HOLD_EXIT_REENTRY_SUMMARY.json')
for r in weekly:
 pol=r['policy'];xs=[x for x in cap.values() if r['first_day']<=x['day']<=r['last_day']]
 rr=[x for x in funnel[pol] if r['first_day']<=x['signal_day']<=r['last_day']]
 fills=[x for x in life[pol]['all_actual_layers'] if r['first_day']<=x['opened']<=r['last_day']]
 ranks=sorted(x['frozen_intent']['priority_rank'] for x in rr if x['frozen_intent'])
 r.update(original_PVR_stage_daily=[{'day':x['day'],'stage':x['industry_stage'],'action':x['industry_action'],'CP1':x['industry_CP1']} for x in xs],
   planned_priority_min=min(ranks) if ranks else None,
   planned_priority_median=(ranks[len(ranks)//2]+ranks[(len(ranks)-1)//2])/2 if ranks else None,
   actual_new_layers=[{k:x[k] for k in ['sid','name','signal','opened','closed','role','action','buy_cost','net']} for x in fills],
   actual_entry_actions=dict(Counter(x['action'] for x in fills)))
save('SEMICONDUCTOR_WEEKLY_ENRICHED.json',weekly)
save('DECOMPOSITION_SOURCE_SHA256.json',dict(src,reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
print(json.dumps({k:{q:v for q,v in x.items() if q!='members'} for k,x in res.items()},ensure_ascii=False,indent=2))

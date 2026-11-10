"""Post-planning evaluation only: old fixed labels and whole original paths.
No fitted thresholds, new price labels, scaling of old PnL, or portfolio PnL.
Usage: python3 ... input_comparisons.json OUTPUT_PREFIX
"""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,statistics,sys

O=Path(__file__).resolve().parent
P=O.parent/'reentry_v1/funding_agent/private_projection'
L=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031/2025_26/PRICE_LABELS.jsonl.gz')
sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def stats(a):return dict(n=len(a),minimum=min(a) if a else None,mean=statistics.mean(a) if a else None,median=statistics.median(a) if a else None,maximum=max(a) if a else None)
def labstats(xs):
 out={}
 for h in ['21','63']:
  known=[r['existing_signal_CLOSE_price_labels'][h] for r in xs if r['existing_signal_CLOSE_price_labels'] and r['existing_signal_CLOSE_price_labels'][h]['valid']]
  out[h]=dict(known=len(known),unknown_or_original_invalid=len(xs)-len(known),
   endpoint_pct=stats([v['return_pct'] for v in known]),MAE_pct=stats([v['MAE_pct'] for v in known]),
   negative_endpoints=sum(v['return_pct']<0 for v in known),MFE30=sum(v['right_tail_MFE30'] for v in known))
 return out
def summary(xs):
 return dict(events=len(xs),unique_stocks=len({r['sid'] for r in xs}),
  by_role=dict(Counter(r['role'] for r in xs)),by_entry_kind=dict(Counter(r['entry_kind'] for r in xs)),
  by_frozen_release_eligible=dict(Counter(str(r['cash_release_eligible']) for r in xs)),
  rank=stats([r['rank'] for r in xs]),existing_price_labels=labstats(xs))

if __name__=='__main__':
 bind(__file__);inp=Path(sys.argv[1]);prefix=sys.argv[2];rows=read(inp)
 assert len(rows)==4172 and len({(r['opening'],r['key']) for r in rows})==4172
 old={(r['opening'],r['key']):r for r in read(P/'ON_ALL4172_CANDIDATE_COMPARISONS.json')}
 actual={r['comparison']['key']:r['original_path_reference'] for r in read(P/'ON_ORIGINAL50_ORDER_OPPORTUNITY_REFERENCES.json')}
 labels={}
 with gzip.open(bind(L),'rt')as h:
  for r in map(json.loads,h):
   k=(r['sid'],r['day'],r['receipt']);assert k not in labels;labels[k]=r['labels']
 out=[]
 for r in rows:
  z=old[r['opening'],r['key']];assert all(r[k]==z[k] for k in ['sid','role','rank','CP1_id'])
  a=r['old_order'];b=r['new_order'];qty=lambda q: int(q['quantity']) if q else 0
  change='added' if b and not a else 'lost' if a and not b else 'shrunk' if qty(b)<qty(a) else 'increased' if qty(b)>qty(a) else 'unchanged_reserved' if a else 'not_reserved_both'
  sd=r['signal_day'];assert sd==r['key'].split('|')[1][:10]
  out.append(dict(r,change=change,pool_changed=bool(a and b and a['pool']!=b['pool']),name=z['name'],industry=z['industry'],entry_kind=z['entry_kind'],
   original_held_qty=z['original_held_qty'],existing_signal_CLOSE_price_labels=labels.get((r['sid'],sd,r['CP1_id'])),
   whole_original_order_path_reference=actual.get(r['key']),
   no_new_PnL=True,no_proportional_PnL=True))
 groups={k:[r for r in out if r['change']==k] for k in ['added','lost','shrunk','increased','unchanged_reserved','not_reserved_both']}
 for c in ['added','lost','shrunk','increased']:
  groups[c+'_semiconductor']=[r for r in groups[c] if r['industry']=='半导体']
  groups[c+'_original_flat_reentry']=[r for r in groups[c] if r['entry_kind']=='flat_actual_original_reentry']
 groups['all_common_pool_changed']=[r for r in out if r['pool_changed']]
 groups['common_same_qty_pool_changed']=[r for r in out if r['pool_changed'] and r['quantity_delta']==0]
 changed=[r for r in out if r['change'] in ['added','lost','shrunk','increased']]
 save(prefix+'_EXISTING_EVIDENCE.json',changed)
 save(prefix+'_EXISTING_LABEL_SUMMARY.json',{k:summary(v) for k,v in groups.items()})
 refs=[dict(opening=r['opening'],key=r['key'],name=r['name'],industry=r['industry'],change=r['change'],
  old_quantity=int(r['old_order']['quantity'])if r['old_order']else 0,new_quantity=int(r['new_order']['quantity'])if r['new_order']else 0,
  original_path=r['whole_original_order_path_reference']) for r in changed if r['whole_original_order_path_reference']]
 save(prefix+'_CHANGED_ORIGINAL_ORDER_PATH_REFERENCES.json',refs)
 save(prefix+'_EXISTING_EVIDENCE_SOURCE_SHA256.json',sources)
 save(prefix+'_EVALUATION_SCOPE.json',dict(input_events=4172,changed_events=len(changed),
  price_label_clock='Fixed original21/63 stock-valid-price observations from signal CLOSE; not common-market/fill/holding return',
  paths='Whole original order paths referenced unchanged, not new policy profit or scaled opportunity cost; open-path cash is not loss',
  allocation='13 independent original S0 resource projections do not carry new holdings into future states',
  selection='Evidence evaluated only after frozen planning, no thresholds, ranks, dates or rule changes selected from future labels',
  accounts=0,new_labels=0,new_PnL=0))
 print(json.dumps({k:summary(v) for k,v in groups.items() if k not in ['unchanged_reserved','not_reserved_both']},ensure_ascii=False,indent=2))

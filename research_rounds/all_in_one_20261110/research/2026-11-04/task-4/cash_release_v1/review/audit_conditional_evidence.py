"""Existing labels/path associations only; no pricing or portfolio simulation."""
from pathlib import Path
from collections import Counter
import json,gzip,statistics,hashlib
O=Path(__file__).resolve().parent;C=O.parent;PR=O.parents[1]/'reentry_v1/funding_agent/private_projection'
def read(p):return json.loads(Path(p).read_text())
def stats(a):return dict(n=len(a),minimum=min(a)if a else None,mean=statistics.mean(a)if a else None,median=statistics.median(a)if a else None,maximum=max(a)if a else None)
def summary(xs):
 out=dict(events=len(xs),unique_stocks=len({x['sid']for x in xs}),by_role=dict(Counter(x['role']for x in xs)),by_entry_kind=dict(Counter(x['entry_kind']for x in xs)),by_frozen_release_eligible=dict(Counter(str(x['cash_release_eligible'])for x in xs)),rank=stats([x['rank']for x in xs]),existing_price_labels={})
 for h in ['21','63']:
  a=[x['lab'][h]for x in xs if x['lab']and x['lab'][h]['valid']]
  out['existing_price_labels'][h]=dict(known=len(a),unknown_or_original_invalid=len(xs)-len(a),endpoint_pct=stats([v['return_pct']for v in a]),MAE_pct=stats([v['MAE_pct']for v in a]),negative_endpoints=sum(v['return_pct']<0 for v in a),MFE30=sum(v['right_tail_MFE30']for v in a))
 return out
def main():
 lp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031/2025_26/PRICE_LABELS.jsonl.gz')
 with gzip.open(lp,'rt')as f:ls=list(map(json.loads,f))
 labels={(r['sid'],r['day'],r['receipt']):r['labels']for r in ls};assert len(labels)==len(ls)==19358
 old={(r['opening'],r['key']):r for r in read(PR/'ON_ALL4172_CANDIDATE_COMPARISONS.json')};assert len(old)==4172
 paths={r['comparison']['key']:r['original_path_reference']for r in read(PR/'ON_ORIGINAL50_ORDER_OPPORTUNITY_REFERENCES.json')}
 outcomes={}
 for prefix in ['A_NATIVE','B_MINFIRST']:
  rs=read(C/'funding'/(prefix+'_ALL4172_COMPARISONS.json'));assert len(rs)==4172;full=[]
  for r in rs:
   a=r['old_order'];b=r['new_order'];qty=lambda x:x['quantity']if x else 0
   change='added'if b and not a else'lost'if a and not b else'shrunk'if qty(b)<qty(a)else'increased'if qty(b)>qty(a)else'unchanged_reserved'if a else'not_reserved_both'
   z=old[r['opening'],r['key']];assert all(r[k]==z[k]for k in['sid','role','rank','CP1_id'])
   x=dict(r,change=change,name=z['name'],industry=z['industry'],entry_kind=z['entry_kind'],original_held_qty=z['original_held_qty'],lab=labels.get((r['sid'],r['signal_day'],r['CP1_id'])),path=paths.get(r['key']));full.append(x)
  groups={k:[x for x in full if x['change']==k]for k in ['added','lost','shrunk','increased','unchanged_reserved','not_reserved_both']}
  for c in['added','lost','shrunk','increased']:
   groups[c+'_semiconductor']=[r for r in groups[c]if r['industry']=='半导体'];groups[c+'_original_flat_reentry']=[r for r in groups[c]if r['entry_kind']=='flat_actual_original_reentry']
  groups['all_common_pool_changed']=[r for r in full if r['old_order']and r['new_order']and r['old_order']['pool']!=r['new_order']['pool']]
  groups['common_same_qty_pool_changed']=[r for r in groups['all_common_pool_changed']if r['old_order']['quantity']==r['new_order']['quantity']]
  saved=read(C/(prefix+'_EXISTING_LABEL_SUMMARY.json'));assert set(groups)==set(saved)
  for k,xs in groups.items():assert summary(xs)==saved[k],(prefix,k)
  changed=[r for r in full if r['change']in['added','lost','shrunk','increased']];savedchanged=read(C/(prefix+'_EXISTING_EVIDENCE.json'));assert len(changed)==len(savedchanged)
  for r,z in zip(changed,savedchanged):
   assert r['key']==z['key']and r['lab']==z['existing_signal_CLOSE_price_labels']and r['path']==z['whole_original_order_path_reference']and r['entry_kind']==z['entry_kind']
  refs=read(C/(prefix+'_CHANGED_ORIGINAL_ORDER_PATH_REFERENCES.json'));expected=[x for x in changed if x['path']];assert len(refs)==len(expected)
  for r,z in zip(expected,refs):assert r['key']==z['key']and r['path']==z['original_path']
  outcomes[prefix]=dict(complete_rows=len(rs),changed_rows=len(changed),all_summary_groups=len(groups),added=summary(groups['added']),added_semiconductor=summary(groups['added_semiconductor']),added_original_flat_reentry=summary(groups['added_original_flat_reentry']),pool_changed=len(groups['all_common_pool_changed']),same_qty_pool_changed=len(groups['common_same_qty_pool_changed']),changed_original_path_refs=len(refs))
 result=dict(status='PASS_CONDITIONAL_EXISTING_LABELS_AND_PATH_JOINS',label_keys_unique=len(labels),comparisons=outcomes,no_new_labels=True,no_new_policy_profit=True,scope='All groups and added/lost/shrunk/increased paths, unknowns and pool changes retained. Signal CLOSE stock-observation labels do not identify actual held returns or profitability of the cash release policy.')
 (O/'CONDITIONAL_EXISTING_EVIDENCE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:dict(complete_rows=v['complete_rows'],changed_rows=v['changed_rows'],pool_changed=v['pool_changed'],same_qty_pool_changed=v['same_qty_pool_changed'])for k,v in outcomes.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

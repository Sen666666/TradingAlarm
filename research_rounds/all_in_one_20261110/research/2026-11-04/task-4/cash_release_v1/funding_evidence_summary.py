"""Join existing fixed price labels and original paths; no new trading PnL."""
from pathlib import Path
from collections import Counter
import csv, gzip, hashlib, json, statistics

O=Path(__file__).resolve().parent
L=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031/2025_26/PRICE_LABELS.jsonl.gz')
P=O/'funding/ALL14_FUNDING_DECOMPOSITION.json'
rows=json.loads(P.read_text())
with gzip.open(L,'rt') as h:
    labels={(r['sid'],r['day'],r['receipt']):r['labels'] for r in map(json.loads,h)}

def write(n,x): (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def stat(a): return dict(n=len(a),minimum=min(a) if a else None,median=statistics.median(a) if a else None,maximum=max(a) if a else None)
def labelstats(a):
    out={}
    for h in ['21','63']:
        b=[r['existing_signal_CLOSE_price_labels'][h] for r in a if r['existing_signal_CLOSE_price_labels'] and r['existing_signal_CLOSE_price_labels'][h]['valid']]
        out[h]=dict(events=len(a),known=len(b),unknown_or_original_invalid=len(a)-len(b),
                    endpoint_pct=stat([v['return_pct'] for v in b]),negative_endpoints=sum(v['return_pct']<0 for v in b),
                    MFE30=sum(v['right_tail_MFE30'] for v in b))
    return out

targets=[]; earlier={}; table=[]
for r in rows:
    t=r['target']; a=r['OFF_native']; f=a['frame']
    targets.append(dict(sid=r['sid'],name=r['name'],signal_day=r['signal_day'],OPEN=r['opening'],rank=t['rank'],H1_rank=t['H1_rank'],
                        H1_score=t['H1_score'],PVR_score=t['PVR_score'],CP1=t['CP1_id'],
                        existing_signal_CLOSE_price_labels=labels.get((r['sid'],r['signal_day'],t['CP1_id'])),
                        original_candidate_not_filled=True))
    table.append(dict(OPEN=r['opening'],name=r['name'],original_rank=t['rank'],original_submitted_front_orders=len(a['prior_orders']),
                      original_submitted_front_reserve=f['reserved_cash_including_Fq'],marked_original_stock_inventory=f['marked_stock_inventory'],
                      real_available_after_submitted_orders=f['available_after_submitted_or_planned_orders'],extra_cash10=f['original_cash10_buffer'],
                      spendable_after_extra_cash10=f['discretionary_space_with_cash10'],minimum_cash=a['minimum_cash_including_buy_fee'],
                      cash10_shortfall=a['cash10_minimum_shortfall'],individual_optimistic_cash_only_reachable=a['individual_optimistic_cash_only_reachable']))
    for q in a['prior_orders']:
        k=q['budget_order']; sd=k.split('|')[1][:10]
        z=dict(q,signal_day=sd,existing_signal_CLOSE_price_labels=labels.get((q['sid'],sd,q['CP1_id'])))
        if k in earlier: assert earlier[k]==z
        earlier[k]=z

front=list(earlier.values())
fullyclosed=[r for r in front if r['same_key_original_actual_path'] and r['same_key_original_actual_path']['all_original_layers_closed']]
filled=[r for r in front if r['same_key_original_actual_path'] and r['same_key_original_actual_path']['actual_original_fill_occurred']]
nets=[float(r['same_key_original_actual_path']['whole_original_closed_layers_net_reference_cny']) for r in fullyclosed]
summary=dict(
    blocked_targets=14,original_front_unique_orders=len(front),original_front_actual_filled=len(filled),
    original_front_fully_closed_orders=len(fullyclosed),original_front_closed_positive=sum(n>0 for n in nets),original_front_closed_negative=sum(n<0 for n in nets),
    original_closed_path_net_reference=sum(nets),original_closed_path_net_scope='Original whole order paths, each unique key once; NOT released-policy PnL or opportunity cost',
    target_original_rank=stat([r['rank'] for r in targets]),front_original_rank=stat([r['rank'] for r in front]),
    target_existing_price_labels=labelstats(targets),front_existing_price_labels=labelstats(front),
    cash10_shortfall=stat([float(r['cash10_shortfall']) for r in table]),
    stock_inventory=stat([float(r['marked_original_stock_inventory']) for r in table]),
    real_available_net_of_submitted_orders=stat([float(r['real_available_after_submitted_orders']) for r in table]),
    labels_scope='Original pre-existing fixed 21/63 stock-valid-price observations from signal CLOSE, not actual buy/fill clock or trading returns; preserved unknowns; no sizing or policy chosen from labels',
    no_new_pricing_labels=True,no_new_accounts=True,no_proportional_PnL=True)
write('FOCUS14_AND_REAL_FRONT_EXISTING_OUTCOMES.json',dict(targets=targets,front_orders=front))
write('FOCUS14_AND_REAL_FRONT_SUMMARY.json',summary)
with (O/'FOCUS14_CASH_RESPONSIBILITY_TABLE.csv').open('w') as h:
    w=csv.DictWriter(h,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
write('FUNDING_EVIDENCE_SUMMARY_SOURCE_SHA256.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [L,P,Path(__file__)]})
print(json.dumps(summary,ensure_ascii=False,indent=2))

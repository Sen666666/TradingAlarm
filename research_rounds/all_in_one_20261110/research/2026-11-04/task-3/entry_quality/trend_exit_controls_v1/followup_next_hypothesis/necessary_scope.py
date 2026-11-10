"""Frozen-condition scope only. No indicator, execution or account imports."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D, getcontext
import datetime
import hashlib
import json
import math

getcontext().prec = 70
OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
EPS = 4*2**-53/(1-4*2**-53)

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ge(a,b): return a >= b or abs(a-b) <= EPS*max(abs(a),abs(b),1e-300)
def write(n,x): (OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

sources = [OUT/'PROTOCOL.json']
summary = {}
hits = []
for window in ['2022_2024','strong']:
    jp = BASE/'entry_exit_scale/mechanism_review'/f'{window}_ACTUAL_ENTRY_SCALE_JOIN.json'
    fp = BASE/'entry_exit_scale/decision_features'/f'{window}_ROWS.json'
    sources.extend([jp,fp])
    fields = {r['layer']:r for r in read(fp)}
    rows = []
    for r in read(jp):
        if r['role'] != 'mobile': continue
        q = fields[r['layer']]
        cp = r['CP1_cached']
        anchor = cp.get('anchor')
        unknown = []
        if not cp.get('receipt') or r['receipt'] is None: unknown.append('not_actual_receipt')
        if q['signal_source_segment'] != q['fill_source_segment']: unknown.append('noncomparable_source')
        if anchor is None or not math.isfinite(float(anchor)): unknown.append('unknown_anchor')
        # Proof uses un-slipped raw opening price. Fill price is audit-only.
        op = D(q['actual_raw_open'])*D(q['fill_factor'])
        floor = D(r['original_frozen_intent_floor_causal'])
        erased = None if unknown else ge(float(anchor),math.log(float(op)))
        row = dict(window=window,layer=r['layer'],sid=r['sid'],name=r['name'],
                   decision=r['decision_at'],fill=r['actual_fill_at'],action=r['action'],
                   receipt=r['receipt'],source_segment=q['signal_source_segment'],
                   actual_raw_OPEN=q['actual_raw_open'],same_clock_factor=q['fill_factor'],
                   causal_raw_OPEN=str(op),anchor_log=anchor,open_log=math.log(float(op)),
                   actual_execution_price_audit_only=q['actual_execution_price'],
                   original_floor_causal=str(floor),original_raw_floor_at_fill=str(floor/D(q['fill_factor'])),
                   native_floor_already_break=op<=floor,erased=erased,unknown=unknown,
                   original_net=r['original_net'],original_cost=r['original_cost'])
        rows.append(row)
        if erased: hits.append(row)
    groups = {'all_mobile':rows}
    if window == '2022_2024':
        groups['opened2022_2023'] = [r for r in rows if r['fill'][:4] in ['2022','2023']]
        groups['post303_mobile'] = [r for r in rows if r['fill'][:10] > '2024-10-08']
    for group,selected in groups.items():
        erased_rows = [r for r in selected if r['erased'] is True]
        additional = [r for r in erased_rows if not r['native_floor_already_break']]
        neg = sum((D(r['original_net']) for r in selected if D(r['original_net'])<0),D(0))
        hitneg = sum((D(r['original_net']) for r in additional if D(r['original_net'])<0),D(0))
        hitpos = sum((D(r['original_net']) for r in additional if D(r['original_net'])>0),D(0))
        summary[window+'|'+group] = dict(mobile_layers=len(selected),unknown=sum(bool(r['unknown']) for r in selected),
            erased_raw=len(erased_rows),already_broken_original_floor=sum(r['native_floor_already_break'] for r in erased_rows),
            erased_additional=len(additional),all_hits_strictly_above_original_floor=all(not r['native_floor_already_break'] for r in erased_rows),
            actions=dict(Counter(r['action'] for r in additional)),total_original_negative=str(neg),
            hit_original_negative=str(hitneg),hit_original_positive=str(hitpos),hit_original_net=str(hitneg+hitpos),
            negative_coverage_percent=str(100*hitneg/neg) if neg else None,scope_only_not_policy_profit=True)
    write(f'{window}_NECESSARY_SCOPE_ROWS.json',rows)

assert len(hits)==29 and all(not r['native_floor_already_break'] for r in hits)
write('ALL_29_HIT_ORIGINAL_LAYERS.json',hits)
write('NECESSARY_SCOPE_SUMMARY.json',summary)
comparisons = BASE/'trend_exit_controls_v1/execution_review/account_comparison/results_v2'
sources.extend([comparisons/'READOUT.txt',BASE/'trend_exit_controls_v1/NAV_SUMMARY.json',
                BASE/'trend_exit_controls_v1/native_adapter/event_diagnostic/READOUT.txt'])
write('SOURCE_MANIFEST.json',dict(status='STOP_NO_ECONOMIC_SCOPE',
    at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    sources={str(p):sha(p) for p in sources},
    deliverables={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='SOURCE_MANIFEST.json'},
    new_accounts=0,new_models=0,unknown=0,actual_candidate_389_421_condition_measured=False,
    checks=['un_slipped_raw_OPEN_used','all29_hit_above_original_frozen_floor','immutable_used_anchor_not_next_anchor']))
print(json.dumps(summary,ensure_ascii=False))

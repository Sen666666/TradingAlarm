"""Read-only five-point source/recurrence audit; no strategy/helper import."""
from pathlib import Path
import hashlib, json, math
from collections import Counter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
def load(p): return json.loads((ROOT / p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a, b):
    if a is None or pd.isna(a): return b is None or pd.isna(b)
    if b is None or pd.isna(b): return False
    return a == b

sc = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
manifest = {r['symbol']: r['refs'] for r in json.loads(sc.read_text())}
source_expected = load('yingxin_hyn/FROZEN_RUN_SOURCE_MANIFEST.json')['source_sha256']
source_expected.update(load('yinzhijie/PREPARATION_RECEIPT.json')['source_sha256'])
source_expected.update(load('semiconductor/SIGNAL_RUN_RECEIPT.json')['source_sha256'])
y = load('yingxin_hyn/FROZEN_BALANCE_WINDOW_DAILY.json')
z = load('yinzhijie/fixed_balance_run/ALL_58_DAILY.json')
semi = load('semiconductor/FIXED25_SIGNAL_BALANCES.json')
points = [
    next(r for r in y if r['sid']=='000620.SZ' and r['day']=='2022-01-20'),
    next(r for r in y if r['sid']=='002583.SZ' and r['day']=='2024-09-20'),
    next(r for r in z if r['day']=='2024-10-09'),
    next(r for r in z if r['day']=='2024-10-14'),
    next(r for r in semi if r['layer']==737),
]
checks=[]; source_hashes={}; loaded={}
for item in points:
    sid=item['sid']; day=item.get('day',item.get('decision_at','')[:10])
    if sid not in loaded:
        cp_path=Path(manifest[sid]['CP1']); q_path=Path(manifest[sid]['CP1_input'])
        for p in [cp_path,q_path]:
            actual=sha(p); assert actual==source_expected[str(p)],str(p)
            source_hashes[str(p)]=actual
        end={'000620.SZ':'2022-01-31','002583.SZ':'2024-11-30','300085.SZ':'2024-11-30','300623.SZ':'2026-06-30'}[sid]
        cp=pd.read_parquet(cp_path).loc[:end]; q=pd.read_parquet(q_path).loc[cp.index]
        assert cp.index.equals(q.index)
        loaded[sid]=(cp,q)
    cp,q=loaded[sid]; t=pd.Timestamp(day); original=cp.loc[t]; inp=q.loc[t]
    old=item.get('original_CP',item.get('old_CP'))
    if old is None:
        old={k:item['original_'+k] for k in ['r','m','delta_frontier']}
        old.update(scale=item['original_used_scale'],receipt=item['original_CP_receipt'],
                   reset_reason=item['original_reset_reason'])
    matched=[]
    for key,value in old.items():
        assert eq(value,original[key]),(sid,day,key,value,original[key]); matched.append(key)
    if 'original_CP_input' in item:
        for key,value in item['original_CP_input'].items():
            assert eq(value,inp[key]),(sid,day,key)
    b=item.get('fixed_balance',item)
    previous_day=cp.index[cp.index.get_loc(t)-1]
    if sid in ['000620.SZ','002583.SZ']:
        prior=next(r for r in y if r['sid']==sid and r['day']==str(previous_day.date()))['fixed_balance']['balance_after']
    elif sid=='300085.SZ':
        prior=next(r for r in z if r['day']==str(previous_day.date()))['fixed_balance']['balance_after']
    else:
        saved=pd.read_parquet(ROOT/'semiconductor'/f'{sid.replace(".","_")}_BALANCE_2026H1.parquet')
        prior=float(saved.loc[previous_day,'balance_after'])
    assert prior==b['balance_before']
    loss=max(-float(original.r),0.0)
    innovation=float(original.delta_frontier)*float(original.m)
    pre=(20.0/21.0)*prior+innovation-loss
    reason=None if pd.isna(original.reset_reason) else str(original.reset_reason)
    if reason in {'start','E0_down_reset','lower_anchor','E0_invalid'}: pre=min(pre,0.0)
    h=math.sqrt(5.0)*float(original.scale)
    eps=4*2**-53/(1-4*2**-53)
    allowed=bool(original.receipt) and (pre>=h or abs(pre-h)<=eps*max(abs(pre),abs(h),1e-300))
    expected={'loss':loss,'innovation':innovation,'pre_balance':pre,'threshold':h,
              'effective_advance':allowed,'balance_after':0.0 if allowed else pre}
    for key,value in expected.items(): assert value==b[key],(sid,day,key,value,b[key])
    checks.append(dict(sid=sid,day=day,source_fields_checked=matched,previous_observation=str(previous_day.date()),
                       original_used_scale=float(original.scale),original_next_scale=float(original.next_scale),
                       balance_before=prior,**expected))

# Count only already-saved event tables; do not run the candidate on a new path.
windows=[]
for sid,start,end in [('000620.SZ','2022-01-01','2022-01-31'),('002583.SZ','2024-01-01','2024-01-31'),('002583.SZ','2024-09-01','2024-11-30')]:
    rows=[r for r in y if r['sid']==sid and start<=r['day']<=end]
    raw=[r for r in rows if r['original_CP']['receipt']]
    windows.append(dict(sid=sid,start=start,end=end,rows=len(rows),raw=len(raw),
                        effective=sum(r['fixed_balance']['effective_advance'] for r in raw),
                        rejected_days=[r['day'] for r in raw if not r['fixed_balance']['effective_advance']]))
raw=[r for r in z if r['old_CP']['receipt']]
windows.append(dict(sid='300085.SZ',start='2024-09-01',end='2024-11-30',rows=len(z),raw=len(raw),
                    effective=sum(r['fixed_balance']['effective_advance'] for r in raw),
                    rejected_days=[r['day'] for r in raw if not r['fixed_balance']['effective_advance']]))
raw=load('semiconductor/ALL238_RAW_CP_EVENTS.json')
assert len(raw)==238 and sum(r['effective_advance'] for r in raw)==119
cohort={r['layer']:r for r in load('semiconductor/FIXED25_COHORT.json')['layers']}
mobile=[r for r in semi if r['role']=='mobile']
assert len(mobile)==24
rejected=[r['layer'] for r in mobile if not r['effective_advance']]
assert rejected==[737] and cohort[737]['actual_entry_action']=='first'
groups={}
for action in ['first','add','reentry']:
    rs=[r for r in mobile if cohort[r['layer']]['actual_entry_action']==action]
    groups[action]=dict(original_rows=len(rs),effective=sum(r['effective_advance'] for r in rs),
                        rejected=[r['layer'] for r in rs if not r['effective_advance']])
assert groups['add']==dict(original_rows=6,effective=6,rejected=[])
assert groups['reentry']==dict(original_rows=4,effective=4,rejected=[])
assert next(r for r in semi if r['layer']==743)['effective_advance']
fills=[(r['sid'],r['day'],a['layer'],r['fixed_balance']['effective_advance']) for r in y for a in r['original_actual_fills_annotations_only'] if a['role']=='mobile']
assert len(fills)==7 and all(r[3] for r in fills)
assert next(r for r in z if 1963 in r['original_actual_layer_ids'])['fixed_balance']['effective_advance']

bindings={}
for name in ['FREEZE.md','balance.py','TWO_PATH_INFORMATION_WITNESS.json',
             'yingxin_hyn/FROZEN_SUMMARY.json','yingxin_hyn/FROZEN_RUN_SOURCE_MANIFEST.json',
             'yingxin_hyn/FROZEN_BALANCE_WINDOW_DAILY.json','yingxin_hyn/run_frozen_balance.py',
             'yinzhijie/fixed_balance_run/SUMMARY.json','yinzhijie/fixed_balance_run/RUN_RECEIPT.json',
             'yinzhijie/fixed_balance_run/PREFIX_CHECK.json','yinzhijie/fixed_balance_run/ALL_58_DAILY.json',
             'yinzhijie/run_fixed_balance.py','semiconductor/SIGNAL_RUN_RECEIPT.json',
             'semiconductor/PREFIX_CHECK.json','semiconductor/FIXED25_SIGNAL_BALANCES.json',
             'semiconductor/FIXED25_COHORT.json','semiconductor/ALL238_RAW_CP_EVENTS.json','semiconductor/run_frozen.py']:
    bindings[str(ROOT/name)]=sha(ROOT/name)
model=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
bindings[str(model)]=sha(model)
result=dict(status='PASS_LIMITED_SOURCE_FORMULA_AND_FIXED_TABLE_AUDIT_NO_ECONOMIC_APPROVAL',
    review_scope='Static helper and three producers; five local recurrence steps from independently read original CP/input, eight source files hash-verified; saved event counts and original static signal annotations. Producer prefix receipts read, not rerun. No whole-prefix independent recurrence, CP/E0 recalculation, V5 state/funding proof, or account.',
    five_points=checks,windows=windows,
    semiconductor=dict(raw=238,effective=119,rejected=119,mobile=24,action_groups=groups,
        only_rejected_original_mobile=737,only_rejected_action='first',applicability='Not a blocked MATURE_ADD; first-UP probe retained. Original action labels do not establish V5 mature state.',
        layer743_effective=True),
    actual_original_mobile_annotations_yingxin_hai=fills,
    original_silver_layer1963_signal_passes=True,
    source_hashes_verified=source_hashes,bindings=bindings,
    formula_checks={'used_scale_not_next_scale':True,'charge_then_clip':True,'raw_rejection_keeps_original_CP_reanchor':True,
        'effective_only_balance_zero':True,'source_unprepared_clear':True,'current_source_boolean_inputs_required_by_original_kernel':True},
    recommendation='Do not adopt this fixed candidate or launch an account on this evidence. Mathematical extra memory is established; targeted economic separation is not.',
    new_accounts=0,new_CP_or_E0_runs=0,parameter_searches=0,new_candidate_path_runs=0)
(OUT/'FIXED_SCOPE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':result['status'],'five_points':[{k:r[k] for k in ['sid','day','pre_balance','threshold','effective_advance']} for r in checks],'action_groups':groups,'windows':windows},ensure_ascii=False))

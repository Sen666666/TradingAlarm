"""Read original CP tables and original holdings; no model/indicator/account calls."""
import csv
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
CASE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json')
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CODE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code')
J=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')
SID='000620.SZ';START='2022-01-04';END='2022-02-08'
def clean(v):
    if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return[clean(x)for x in v]
    if v is pd.NA or v is pd.NaT:return None
    if hasattr(v,'item'):return clean(v.item())
    if isinstance(v,float)and not math.isfinite(v):return None
    return v
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvsave(n,rows):
    with(OUT/n).open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))
case=json.loads(CASE.read_text());manifest=json.loads(MANIFEST.read_text())
rec=next(r for r in manifest if r['symbol']==SID)
input_path=Path(rec['refs']['CP1_input']);cp_path=Path(rec['refs']['CP1'])
for p in [input_path,cp_path]:assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['output_sha256'][str(p)]
inputs=pd.read_parquet(input_path);cp=pd.read_parquet(cp_path)
days=case['days'];assert len(days)==21 and days[0]['day']==START and days[-1]['day']==END
rows=[];layer_rows=[];original=[]
for r in days:
    day=r['day'];dt=pd.Timestamp(day);i=clean(inputs.loc[dt].to_dict());q=clean(cp.loc[dt].to_dict())
    assert q==r['original_CP_cache']
    f=r['original_stock_facts'];bar=r['original_bar'];factor=f['factor']
    assert i['close']==f['close']==bar['close'] and i['amount']==bar['amount']
    assert bool(i['i_target'])==bool(f['i_target'])==bool(i['e0_valid'])
    row=dict(day=day,original_CLOSE_clock=r['original_CLOSE_clock'],sid=SID,
             close_a=i['close'],close_raw=f['raw_close'],factor=factor,
             amount_CNY=i['amount'],raw_volume_shares=bar['raw_volume'],
             segment_id=i['segment_id'],original_fact_e0_target=f['e0_target'],
             CP_e0_valid_is_I_target=i['e0_valid'],original_I_target=i['i_target'],
             original_I_floor_a=i['i_floor'],CP_e0_down_original_input=i['e0_down'],
             CP_ready=q['ready'],phase=q['phase'],reset_reason=q['reset_reason'],
             r_log_return=q['r'],daily_s_63_lag_abs_return_median_scale=q['s'],
             daily_z_after_log1p_001_floor=q['z'],B_prior21_amount_median_CNY=q['B'],
             u=q['u'],v=q['v'],m=q['m'],
             active_frozen_scale=q['scale'],anchor_log_price=q['anchor'],frontier_log_price=q['frontier'],
             credit=q['credit'],delta_frontier=q['delta_frontier'],displacement=q['displacement'],
             original_receipt=q['receipt'],candidate_a=q['candidate'],
             candidate_raw_display=q['candidate']/factor if q['candidate'] is not None else None,
             next_anchor_log_price=q['next_anchor'],next_frozen_scale=q['next_scale'],
             next_credit=q['next_credit'],next_phase=q['next_phase'],
             original_stock_qty_at_CLOSE=sum(l['qty']for l in r['original_live_layers']),
             original_CORE_qty_at_CLOSE=sum(l['qty']for l in r['original_live_layers']if l['role']=='core'),
             original_MOBILE_qty_at_CLOSE=sum(l['qty']for l in r['original_live_layers']if l['role']=='mobile'),
             original_CLOSE_exit_reasons=';'.join(dict.fromkeys(x['reason']for x in r['original_CLOSE_specific_exit_requests'])),
             original_OPEN_bought_shares=sum(x['shares']for x in r['original_OPEN_buys']),
             original_OPEN_sold_shares=sum(x['shares']for x in r['original_OPEN_sells']))
    rows.append(row)
    for l in r['original_live_layers']:
        layer_rows.append(dict(day=day,original_CLOSE_clock=r['original_CLOSE_clock'],layer=l['layer'],role=l['role'],qty=l['qty'],
                               close_a=i['close'],close_raw=f['raw_close'],factor=factor,
                               guard_before_CLOSE_check_a=l['guard_before_CLOSE_check_adjusted'],
                               guard_before_CLOSE_check_raw=l['guard_before_CLOSE_check_raw'],
                               guard_after_original_CLOSE_a=l['guard_after_original_CLOSE_adjusted'],
                               guard_after_original_CLOSE_raw=l['guard_after_original_CLOSE_raw'],
                               original_guard_true_numeric_advance=l['guard_true_numeric_advance'],
                               original_exit_latched=l['original_layer_exit_latched_at_CLOSE'],
                               original_latched_requests=json.dumps(l['latched_requests'],ensure_ascii=False),
                               original_mark_to_guard_before=l['native_mark_to_guard_before_check'],
                               original_mark_to_guard_after=l['native_mark_to_guard_after_checks']))
    original.append(dict(day=day,original_CP1_input=i,original_CP1_output=q,
                         original_price_amount_record=bar,original_stock_facts=f,
                         original_canonical_receipt=r['original_CP_canonical_receipt'],
                         original_native_event=r['original_native_event'],original_live_layers=r['original_live_layers'],
                         historical_original_OPEN_buys=r['original_OPEN_buys'],historical_original_OPEN_sells=r['original_OPEN_sells'],
                         historical_original_CLOSE_exit_requests=r['original_CLOSE_specific_exit_requests']))
csvsave('ORIGINAL_CP_21_DAILY_INPUTS_AND_STATES.csv',rows)
csvsave('ORIGINAL_HELD_LAYER_PROTECTION_BY_CLOSE.csv',layer_rows)
save('ORIGINAL_21_DAILY_RAW_RECORDS.json',original)
sources=[CASE,MANIFEST,input_path,cp_path,CODE/'model.py',CODE/'common.py',CODE/'study.py',J]
out=[]
for p,ranges in [(CODE/'model.py',[(1,58)]),(CODE/'common.py',[(17,24)]),(J,[(225,240),(302,307)])]:
    lines=p.read_text().splitlines();out.extend([str(p),'SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest()])
    for a,z in ranges:out.extend(f'{n}: {lines[n-1]}'for n in range(a,z+1))
    out.append('')
(OUT/'ORIGINAL_FORMULA_AND_EFFECTIVE_PROTECTION_SOURCE.txt').write_text('\n'.join(out))
save('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in sources])
save('FIELD_AVAILABILITY_AND_SCOPE.json',dict(
    status='ORIGINAL_SAVED_FIELD_EXTRACTION_ONLY',sid=SID,window=[START,END],daily_rows=21,
    exact_source_parquet_vs_prior_original_JSON_rows=21,all_21_CP_feature_ready=True,
    source_inputs_full_history_rows=len(inputs),source_inputs_first_date=str(inputs.index[0].date()),
    original_receipt_days=[r['day']for r in rows if r['original_receipt']],
    source_e0_down_days=[r['day']for r in rows if r['CP_e0_down_original_input']],
    inactive_days=[r['day']for r in rows if r['active_frozen_scale']is None],
    complete_numeric_fields=['close_a/raw/factor','amount','r/s/z/B/u/v/m','active anchor/frontier/credit/scale','receipt/candidate','next state','original layer before/after guards and exit requests'],
    legitimate_undefined='Inactive CP state has null anchor/scale; no-receipt days have null candidate. These are not imputed missing data.',
    not_stored=['vendor received_at/known_at for price/amount','explicit numeric-state anchor observation date on every nonreceipt day','historical per-attempt exchange order/queue snapshots'],
    only_window_not_enough_for_independent_warmup='21 days alone cannot recompute prior63 returns and prior21 amount median; original complete prefix is already saved at source_inputs path. No features function called here.',
    candidate_raw='Display-only original candidate_a/factor scalar conversion; not an executable order',
    sigma_warning='daily s/z and active frozen scale are separate. Source scale is robust median absolute log-return scale, not RMS.',
    CP_e0_naming='common.py:22–23 binds e0_valid=facts.i_target and e0_floor=I_floor. e0_down is original saved down-event Boolean, not I exit.',
    new_formula_signals=0,new_EMA=0,new_feature_model_calls=0,new_accounts=0,new_orders=0,new_backtests=0,
    original_holdings='Saved original realized history included only as historical protection/exit context; not replayed or replaced'))
print(json.dumps(dict(rows=len(rows),protection_rows=len(layer_rows),receipts=[r['day']for r in rows if r['original_receipt']],input_matches=True,CP_cache_matches=True),ensure_ascii=False))

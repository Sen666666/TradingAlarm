"""Pure log-path arithmetic following saved original CP anchors and reset flags.

Does not call CP calculate/features, invent receipts or instantiate any trading object.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
SAVED=ROOT/'cp_formula_redesign_v1/yingxin/ORIGINAL_21_DAILY_RAW_RECORDS.json'
START='2022-01-04';END='2022-02-08';SID='000620.SZ'
def clean(x):
    if isinstance(x,dict):return{k:clean(v)for k,v in x.items()}
    if isinstance(x,list):return[clean(v)for v in x]
    if hasattr(x,'item'):return clean(x.item())
    if isinstance(x,float)and not math.isfinite(x):return None
    return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def finite(x):return x is not None and math.isfinite(float(x))
manifest=json.loads(MANIFEST.read_text());rec=next(r for r in manifest if r['symbol']==SID)
ip=Path(rec['refs']['CP1_input']);zp=Path(rec['refs']['CP1'])
for p in [ip,zp]:assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['output_sha256'][str(p)]
f=pd.read_parquet(ip).loc[:END];z=pd.read_parquet(zp).reindex(f.index)
context={r['day']:r for r in json.loads(SAVED.read_text())}

def metrics(anchor,L,high,p):
    A=p-anchor
    return dict(A=A,L=L,ER=A/L if L else None,DD=high-p)

state=None;previous_p=None;previous_segment=None;rows=[];max_r_difference=0.;max_frontier_difference=0.
for dt,r in f.iterrows():
    day=str(dt.date());q=z.loc[dt];p=math.log(float(r.close));segment=r.segment_id
    dp=p-previous_p if previous_p is not None and segment==previous_segment else None
    if dp is not None and finite(q.r):max_r_difference=max(max_r_difference,abs(dp-float(q.r)))
    # The old path is evaluated on every observation BEFORE any original reanchor.
    old_state=state if segment==previous_segment else None
    pre=None
    if old_state is not None and dp is not None:
        preL=math.fsum((old_state['L'],abs(dp)));prehigh=max(old_state['high'],p)
        pre=metrics(old_state['anchor'],preL,prehigh,p)
    reason=None if pd.isna(q.reset_reason)else str(q.reset_reason)
    active=finite(q.anchor)
    reanchor=reason in ['start','E0_down_reset','lower_anchor']
    main=None;anchor_day=None;observations=None
    if not active:
        state=None
    elif reanchor:
        assert abs(float(q.anchor)-p)<1e-14
        state=dict(anchor=float(q.anchor),anchor_day=day,L=0.,high=p,observations=0)
        main=metrics(state['anchor'],0.,p,p);anchor_day=day;observations=0
    else:
        assert old_state is not None and dp is not None,(day,reason)
        assert abs(float(q.anchor)-old_state['anchor'])<1e-14,(day,'saved anchor changed without original reset')
        state=dict(anchor=old_state['anchor'],anchor_day=old_state['anchor_day'],L=pre['L'],
                   high=max(old_state['high'],p),observations=old_state['observations']+1)
        main=metrics(state['anchor'],state['L'],state['high'],p)
        anchor_day=state['anchor_day'];observations=state['observations']
    if main is not None:
        max_frontier_difference=max(max_frontier_difference,abs(state['high']-float(q.frontier)))
    # Receipt metrics above belong to the original pre-consumption anchor.
    pre_consumption=dict(state) if state is not None else None
    if bool(q.receipt):
        assert main is not None
        state=dict(anchor=float(q.next_anchor),anchor_day=day,L=0.,high=p,observations=0)
    if state is not None:
        assert abs(state['anchor']-float(q.next_anchor))<1e-14
    if START<=day<=END:
        c=context[day];oldfacts=c['original_stock_facts']
        row=dict(day=day,sid=SID,original_CLOSE_clock=day+' 15:10:00+08:00',
                 close_a=float(r.close),close_raw=oldfacts['raw_close'],factor=oldfacts['factor'],
                 original_r_cached=float(q.r)if finite(q.r)else None,
                 r_from_original_input_math_log_difference=dp,
                 original_receipt=bool(q.receipt),original_reset_reason=reason,
                 original_e0_down=bool(r.e0_down),original_CP_e0_valid_is_I_target=bool(r.e0_valid),
                 original_phase=None if pd.isna(q.phase)else str(q.phase),
                 original_saved_anchor_log=float(q.anchor)if active else None,
                 original_saved_frontier_log=float(q.frontier)if finite(q.frontier)else None,
                 original_anchor_day_pre_receipt=anchor_day,observations_after_original_anchor=observations,
                 A_pre_receipt_under_original_current_anchor=main['A']if main else None,
                 L_pre_receipt_including_every_observation=main['L']if main else None,
                 ER_pre_receipt_L0_is_null=main['ER']if main else None,
                 DD_pre_receipt_from_known_max_close=main['DD']if main else None,
                 previous_anchor_day_before_any_today_original_reset=old_state['anchor_day']if old_state else None,
                 pre_original_reanchor_or_clear_A=pre['A']if pre else None,
                 pre_original_reanchor_or_clear_L=pre['L']if pre else None,
                 pre_original_reanchor_or_clear_ER=pre['ER']if pre else None,
                 pre_original_reanchor_or_clear_DD=pre['DD']if pre else None,
                 original_reanchor_before_receipt_check=reanchor,
                 next_anchor_day_after_original_reset_or_receipt=state['anchor_day']if state else None,
                 next_L_after_original_reset_or_receipt=state['L']if state else None,
                 next_high_log_after_original_reset_or_receipt=state['high']if state else None,
                 original_delta_frontier=float(q.delta_frontier),
                 original_open_buy_shares=sum(t['shares']for t in c['historical_original_OPEN_buys']),
                 original_open_sell_shares=sum(t['shares']for t in c['historical_original_OPEN_sells']),
                 original_close_exit_reasons=';'.join(dict.fromkeys(t['reason']for t in c['historical_original_CLOSE_exit_requests'])),
                 original_CORE_qty=sum(l['qty']for l in c['original_live_layers']if l['role']=='core'),
                 original_MOBILE_qty=sum(l['qty']for l in c['original_live_layers']if l['role']=='mobile'))
        rows.append(row)
    previous_p=p;previous_segment=segment
assert len(rows)==21
save('ALL21_ORIGINAL_ANCHOR_ER_PATH.json',rows)
with(OUT/'ALL21_ORIGINAL_ANCHOR_ER_PATH.csv').open('w',newline='')as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))
save('ORIGINAL_LAYER_EVENTS_REUSED_NOT_REPLAYED.json',[
    dict(day=d,original_live_layers=c['original_live_layers'],
         original_OPEN_buys=c['historical_original_OPEN_buys'],original_OPEN_sells=c['historical_original_OPEN_sells'],
         original_CLOSE_exit_requests=c['historical_original_CLOSE_exit_requests'])for d,c in context.items()])
summary=dict(window=[START,END],rows=21,original_receipts=sum(r['original_receipt']for r in rows),
             all_original_receipt_metrics=[{k:r[k]for k in ['day','original_anchor_day_pre_receipt','observations_after_original_anchor','A_pre_receipt_under_original_current_anchor','L_pre_receipt_including_every_observation','ER_pre_receipt_L0_is_null','DD_pre_receipt_from_known_max_close']}for r in rows if r['original_receipt']],
             max_abs_math_log_return_vs_saved_np_log_return_difference=max_r_difference,
             max_abs_known_path_max_vs_original_frontier_difference=max_frontier_difference,
             original_reanchor_reasons_used=['start','E0_down_reset','lower_anchor','receipt_consumed'],
             semantics='L sums abs(log C_t - log C_prev) at EVERY original price observation after active original anchor. DD includes anchor and all known closes. Signed A/ER un-clipped; L0 null.',
             old_path_before_down_or_lower_reset='Separate pre_original_reanchor_or_clear columns retain that day old-path fall. Current original-anchor columns then follow saved new anchor with A=L=DD=0 and ER null.',
             full_saved_prefix_used_until_END=True,source_future_after_END_used=False,
             new_CP_calculate_or_features_calls=0,new_signal_rule=0,new_account=0,new_order=0,new_backtest=0)
save('SCOPE_AND_KEY_NUMBERS.json',summary)
save('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in [MANIFEST,ip,zp,SAVED,Path(__file__)]])
print(json.dumps(clean(summary),ensure_ascii=False))
print('KEY_NONRECEIPTS',json.dumps(clean([r for r in rows if r['day']in['2022-01-14','2022-01-17','2022-01-18','2022-01-19','2022-01-26','2022-01-27','2022-01-28','2022-02-07']]),ensure_ascii=False))

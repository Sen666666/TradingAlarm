"""Four actual consecutive stock CLOSEs and their saved next OPENs only."""
from pathlib import Path
import csv
import hashlib
import json
import time

O=Path(__file__).resolve().parent;ROOT=O.parents[1]
P=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json')
SOURCES={};NS='NOT_SAVED';NONE='NONE';DAYS=['2022-01-20','2022-01-21','2022-01-24','2022-01-25']
def read(p):
    p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cell(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))if v else NONE
def slimlayer(l):
    n=l['saved_native_layer']
    return dict(layer=l['layer'],role=l['role'],qty=l['qty'],stored_floor_a=n['floor'],
        saved_last_core_line_a=n.get('last_core_line',NS),
        saved_guard_before_CLOSE_a=l['guard_before_CLOSE_check_adjusted'],
        saved_guard_after_CLOSE_a=l['guard_after_original_CLOSE_adjusted'],
        exit_latched=l['original_layer_exit_latched_at_CLOSE'],latched_requests=l['latched_requests'])

start=time.monotonic();SOURCES[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
d=read(P);allrows=d['days'];by={r['day']:r for r in allrows};ordered=sorted(by)
canon={r['original_CP_canonical_receipt']['receipt_id']:r for r in allrows if r['original_CP_canonical_receipt']}
buys={t['layer']:t for r in allrows for t in r['original_OPEN_buys']}
failed=by['2022-01-19'];sale=by['2022-01-20']['original_OPEN_sells'][0]
failed_ids=sorted({lid for e in failed['original_CLOSE_specific_exit_requests']for lid in e['layers']})
assert failed_ids==[69,75,78]
sources=[]
for lid in failed_ids:
    t=buys[lid];signal=by[t['signal_at'][:10]]
    layer=next(l for l in failed['original_live_layers']if l['layer']==lid)
    sources.append(dict(layer=lid,actual_qty_at_failure=layer['qty'],
        original_actual_buy=t,source_signal_at=t['signal_at'],
        source_signal_close_a=signal['original_stock_facts']['close'],source_signal_raw_close=signal['original_stock_facts']['raw_close'],
        source_canonical_receipt=signal['original_CP_canonical_receipt'],
        known_failed_at_CLOSE='2022-01-19 15:10:00+08:00',failure_C_a=failed['original_stock_facts']['close'],
        old_actual_CP_floor_a=layer['guard_before_CLOSE_check_adjusted'],
        actual_sale_at=sale['at'],actual_sale_raw_open=sale['raw_open'],actual_sale_fill_price_raw=sale['price'],
        source_anchor_type='Actual failed Mobile source signal and its then-canonical confirmation, never a retrospectively selected price peak.',
        known_status_at_each_requested_CLOSE='Both CP failure and actual liquidation already known by Jan20CLOSE.'))
save('FIRST_MOBILE_FAILURE_KNOWN_SOURCES.json',dict(failure_CLOSE_original_row={k:failed[k]for k in ['day','original_CLOSE_clock','original_stock_facts','original_CP_cache','original_CLOSE_specific_exit_requests']},
    failed_source_layers=sources,actual_sale=sale,original_Core_remained=100,
    exit_clock='Jan19CLOSE request -> Jan20 next actualOPEN sale. No missing earlier intraday fill is invented.',
    reference_warning='Latest failed SOURCE confirmation is Jan13. It is not called a peak/highest future price. All3 failed source confirmations remain listed.'))

flat=[];details=[]
for day in DAYS:
    r=by[day];j=ordered.index(day);prev=by[ordered[j-1]];nxt=by[ordered[j+1]]
    f=r['original_stock_facts'];cp=r['original_CP_cache'];receipt=r['original_CP_canonical_receipt'];prior=canon.get(receipt.get('previous_market_receipt_id'))if receipt else None
    if prior is not None:assert prior['day']<day
    priorc=prior['original_stock_facts']if prior else {}
    matched=[t for t in nxt['original_OPEN_buys']if t['signal_at'][:10]==day]
    next_reserves=[a for a in nxt['original_audit_today']if a.get('kind')=='reserve']
    if matched:
        window='PROXY_WINDOW_EXISTS_CONFIRMED_BY_ORIGINAL_ACTUAL_FILL'
        execution_class='ACTUAL_NATIVE_PROXY_FILL'
    elif nxt['original_funding']and not next_reserves:
        window='NOT_SAVED_WINDOW_LOOKUP; POTENTIAL_EXECUTION_UNKNOWN'
        execution_class='FUNDING_OR_QUALIFICATION_DENIED_BEFORE_RESERVATION; NOT_A_PROVEN_WINDOW_REJECTION'
    else:
        window='NOT_SAVED_WINDOW_LOOKUP; POTENTIAL_EXECUTION_UNKNOWN'
        execution_class='NO_FILL_WITHOUT_PROVEN_WINDOW_REJECTION'
    currentcp_before=[{'layer':l['layer'],'qty':l['qty'],'old_CP_a':l['guard_before_CLOSE_check_adjusted']}for l in r['original_live_layers']if l['role']=='mobile']
    currentcp_after=[{'layer':l['layer'],'qty':l['qty'],'current_CP_a':l['guard_after_original_CLOSE_adjusted']}for l in r['original_live_layers']if l['role']=='mobile']
    row=dict(day=day,actual_CLOSE_at=r['original_CLOSE_clock'],raw_close=f['raw_close'],C_a=f['close'],factor=f['factor'],
        previous_canonical_strictly_before_today_day=prior['day']if prior else NS,
        previous_canonical_confirmation_close_a=priorc.get('close',NS),previous_canonical_confirmation_raw_close=priorc.get('raw_close',NS),
        previous_canonical_receipt_id=receipt.get('previous_market_receipt_id',NS)if receipt else NS,
        today_canonical_confirmation_day=receipt['confirmed_day']if receipt else NONE,
        today_canonical_confirmation_close_a=f['close']if receipt else NONE,
        CP_previous_observation_day=prev['day'],CP_previous_observation_frontier=prev['original_CP_cache']['frontier'],
        CP_previous_next_anchor=prev['original_CP_cache']['next_anchor'],CP_previous_next_scale=prev['original_CP_cache']['next_scale'],
        CP_previous_next_credit=prev['original_CP_cache']['next_credit'],CP_previous_next_phase=prev['original_CP_cache']['next_phase'],
        CP_row_anchor=cp['anchor'],CP_row_frontier=cp['frontier'],CP_row_credit=cp['credit'],CP_row_scale=cp['scale'],
        CP_receipt=cp['receipt'],CP_candidate_a=cp['candidate'],CP_next_anchor=cp['next_anchor'],CP_next_scale=cp['next_scale'],
        CP_next_credit=cp['next_credit'],CP_next_phase=cp['next_phase'],CP_reset_reason=cp['reset_reason'],
        E0_target=f['e0_target'],E0_floor_a=f['e0_floor'],I_target=f['i_target'],I_floor_a=f['i_floor'],I_buy=f['i_buy'],
        G1_grade=f['g_grade'],G1_fresh_up=f['g_fresh_up'],G1_up_reasons=r['original_G1']['up_reasons'],
        old_CP_layers_a=cell(currentcp_before),after_CLOSE_CP_layers_a=cell(currentcp_after),
        actual_live_layers=cell([slimlayer(l)for l in r['original_live_layers']]),
        original_CLOSE_exit_proposals=cell(r['original_CLOSE_specific_exit_requests']),original_CLOSE_intents=cell(r['original_intents']),
        next_actual_OPEN_day=nxt['day'],next_raw_OPEN=nxt['original_bar']['raw_open'],
        next_OPEN_window_saved_status=window,next_OPEN_execution_class=execution_class,
        next_OPEN_actual_buys_from_this_signal=cell(matched),
        next_OPEN_original_funding=cell(nxt['original_funding']),
        known_at_signal_CLOSE='Current original facts/G1/CP and previous canonical/source failures are then-known; nextOPEN fields are later realized evaluation only.',
        latest_failed_SOURCE_confirmation_day='2022-01-13',latest_failed_SOURCE_confirmation_close_a=by['2022-01-13']['original_stock_facts']['close'],
        latest_failed_SOURCE_confirmation_raw_close=by['2022-01-13']['original_stock_facts']['raw_close'],
        failed_source_reference_role='DISPLAY_ONLY: original algorithm has no saved last_failed_breakout field; not a new eligibility gate')
    flat.append(row)
    details.append(dict(day=day,original_actualfacts=f,original_G1=r['original_G1'],original_aux_E0_event=r['original_native_event'],
        original_CP_row=cp,previous_stock_observation_CP_row=prev['original_CP_cache'],
        today_canonical_receipt=receipt,previous_canonical_receipt=prior['original_CP_canonical_receipt']if prior else NS,
        previous_canonical_confirmation_close_a=priorc.get('close',NS),
        actual_live_layers=[slimlayer(l)for l in r['original_live_layers']],original_CLOSE_intents=r['original_intents'],
        original_CLOSE_opportunities=r['original_opportunities'],original_CLOSE_exit_proposals=r['original_CLOSE_specific_exit_requests'],
        original_OPEN_today_buys=r['original_OPEN_buys'],original_OPEN_today_sells=r['original_OPEN_sells'],
        next_OPEN=dict(day=nxt['day'],raw_OPEN=nxt['original_bar']['raw_open'],actual_buys_from_this_signal=matched,
            original_funding=nxt['original_funding'],original_audit=nxt['original_audit_today'],original_journal=nxt['original_journal_today'],
            window_lookup_direct_record=NS,execution_class=execution_class,
            actual_fill_proves_proxy_window=bool(matched),known_at='Later nextOPEN realization, not currentCLOSE signal input.'),
        source_known_at='Original native consuming CLOSE; cache publication timestamp NOT_SAVED.'))
save('CONTINUOUS_FOUR_CLOSE_AND_NEXT_OPEN.json',details)
save('FOUR_CLOSE_TIMELINE_ROWS.json',flat)
with(O/'FOUR_CLOSE_TIMELINE.csv').open('w',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)

reference_files=[ROOT/'native_algorithm_read_v1/daily_hytera/HYTERA_DAILY_NATIVE.csv',ROOT/'native_algorithm_read_v1/daily_hytera/ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json']
save('HYTERA_REFERENCE_ONLY.json',dict(existing_files=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in reference_files],
    read_these_existing_rows=['2024-10-14','2024-10-15','2024-10-18','2024-10-21','2024-10-22'],
    chain='Existing Core1994 actual100 shares, then first Mobile2017 signalOct18/fillOct21 1100, then2039 signalOct21/fillOct22 1000. No Hytera frames regenerated or source market reread.',
    comparison_scope='YingXin is Mobile-sleeve reentry while Core100 stayed; Hytera is first Mobile layering after Core100, not an identically timed prior-Mobile-failure reentry.'))
save('SOURCE_SHA256.json',SOURCES)
save('COST_AND_SCOPE.json',dict(observations=4,next_OPENs=['2022-01-21','2022-01-24','2022-01-25','2022-01-26'],
    weekend_not_observation=['2022-01-22','2022-01-23'],only_existing_saved_JSON=True,
    no_new_quotes_parquet_or_Hytera_extraction=True,new_models=0,new_accounts=0,new_backtests=0,new_indicators=0,
    source_price_anchors='All3 actual failed source signal closes, with latest chronological prior sourceJan13 labeled confirmation, not future peak.',
    previous_CP_definition='Follow current canonical previous_market_receipt_id to its actual confirmation row and copy original close. No exp(log anchor), no reset-anchor substitution.',
    failed_source_fixed_reference='Keep Jan13 prior failed source confirmation separate as display-only reference while immediate previousCP updatesJan13->Jan20->Jan21->Jan24. No original last_failed_breakout state/eligibility is claimed.',
    seconds=time.monotonic()-start))
print(json.dumps(dict(observations=4,next_OPEN_links=4,failed_layers=failed_ids,seconds=time.monotonic()-start,new_models=0)))

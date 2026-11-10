"""Eight fixed saved snapshots. No parquet/model/indicator/price conversion."""
from pathlib import Path
import csv
import hashlib
import json
import time

O=Path(__file__).resolve().parent;ROOT=O.parents[1]
PEER=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality')
SOURCES={};NS='NOT_SAVED'
def read(p):
    p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cell(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))if v else 'NONE'
def val(r,k):return r.get(k,NS)
def layer(l):
    return {k:l.get(k,NS)for k in ['id','kind','qty','floor','last_core_line','reason','opened','signal_at']}

start=time.monotonic()
SOURCES[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
hai=read(ROOT/'native_algorithm_read_v1/daily_hytera/ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json')
hai_clock={r['date']:r['original_CLOSE_at']for r in read(ROOT/'native_algorithm_read_v1/daily_hytera/HYTERA_DAILY_NATIVE_ROWS.json')}
ying=read(PEER/'structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json')['days']
boundary=read(PEER/'structure_risk_position_contract_v3/cases/ORIGINAL_EXIT_LOCK_BOUNDARY.json')['days']
yb={r['day']:r for r in ying};yb.update({r['day']:r for r in boundary})
rows=[];snapshots=[]

def add(sid,name,day,x,hstyle=False):
    f=x['facts']if hstyle else x['original_stock_facts']
    g=x['legacy_IX_provenance_frame_not_actual_native_I']if hstyle else x['original_G1']
    ev=x['E0_events']if hstyle else x['original_native_event']
    es=x['E0_states']if hstyle else None
    cp=x['CP1']if hstyle else x['original_CP_cache']
    if hstyle:
        live=x['current_CLOSE_stock_layers'];old=x['previous_CLOSE_stock_layers']
        buys=[t for t in x['trades']if t['side']=='buy'];sells=[t for t in x['trades']if t['side']=='sell']
        exits=[r for r in x['audit']if r.get('kind')=='pilot_layer_exit']
        oldcp=[dict(layer=l['id'],qty=l['qty'],CP_old_floor_a=l['floor'],scope='Previous actual CLOSE boundary; same line as current breach onNov4, sold before currentCLOSE onNov5')for l in old if l['kind']=='add']
    else:
        layers=x['original_live_layers'];live=[l['saved_native_layer']for l in layers]
        buys=x['original_OPEN_buys'];sells=x['original_OPEN_sells'];exits=x['original_CLOSE_specific_exit_requests']
        oldcp=[dict(layer=l['layer'],qty=l['qty'],CP_old_floor_a=l['guard_before_CLOSE_check_adjusted'],scope='Saved original source trace guard-before-CLOSE for this actual Mobile layer')for l in layers if l['role']=='mobile']
        if not live and day=='2022-02-08':
            oldcp=[dict(layer=l['layer'],qty=l['qty'],CP_old_floor_a=l['guard_after_original_CLOSE_adjusted'],scope='PriorFeb7actualCLOSE line; layer actually soldFeb8OPEN, not a liveFeb8CLOSE contract')for l in yb['2022-02-07']['original_live_layers']if l['role']=='mobile']
    components={k:val(g,k)for k in ['S21','S63','s21','s63','S21_state','S63_state','pace21','pace63','mu5','mu21','s','sigma','z5','z21','qeff','acute','acute_up','acute_down','phase','proposal','score','strength_ready','fresh_up','up_reasons']}
    # Names are copied only. z21 is not relabeled as S21 state/pace; CP.s is
    # not copied into G1.s. Missing mathematical components remain NOT_SAVED.
    bar=x['source_signal']if hstyle else x['original_bar']
    row=dict(stock=sid,name=name,day=day,actual_native_CLOSE_at=hai_clock.get(day,NS)if hstyle else x.get('original_CLOSE_clock',NS),
        C_a=f['close'],raw_close=f['raw_close'],raw_open=val(bar,'raw_open'),raw_high=val(bar,'raw_high'),raw_low=val(bar,'raw_low'),factor=f['factor'],
        E0_target_actualfacts=f['e0_target'],E0_floor_a_actualfacts=f['e0_floor'],E0_ready_actualfacts=f['e0_ready'],
        E0_native_event=val(ev,'event'),E0_native_event_target=val(ev,'target'),E0_native_event_entered_aux=val(ev,'entered'),E0_native_event_exited_aux=val(ev,'exited'),
        E0_native_states_entered_aux=val(es,'entered')if es else NS,E0_native_states_price_event_aux=val(es,'price_event')if es else NS,
        I_target_actualfacts=f['i_target'],I_floor_a_actualfacts=f['i_floor'],I_buy_actualfacts=f['i_buy'],
        G1_grade_actualfacts=f['g_grade'],G1_ready_actualfacts=f['g_ready'],G1_fresh_up_actualfacts=f['g_fresh_up'],G1_acute_down_actualfacts=f['g_acute_down'],
        G1_S21_state=components['S21_state'],G1_S63_state=components['S63_state'],G1_pace21=components['pace21'],G1_pace63=components['pace63'],
        G1_mu5=components['mu5'],G1_mu21=components['mu21'],G1_s=components['s'],G1_z5=components['z5'],G1_z21=components['z21'],G1_qeff=components['qeff'],
        G1_phase_saved=components['phase'],G1_proposal_saved=components['proposal'],G1_acute_up_saved=components['acute_up'],G1_up_reasons_saved=components['up_reasons'],
        CP_ready=val(cp,'ready'),CP_phase=val(cp,'phase'),CP_receipt=val(cp,'receipt'),CP_candidate_a=val(cp,'candidate'),
        CP_old_floor_a_by_actual_layer=cell(oldcp),actual_live_layer_snapshot=cell([layer(l)for l in live]),
        CORE_stored_entry_floor_a_by_layer=cell([{'layer':l['id'],'floor':l['floor']}for l in live if l['kind']=='core']),
        CORE_saved_last_core_line_a_by_layer=cell([{'layer':l['id'],'last_core_line':l.get('last_core_line',NS)}for l in live if l['kind']=='core']),
        original_OPEN_buys=cell(buys),original_OPEN_sells=cell(sells),original_CLOSE_exit_proposals=cell(exits),
        source_publication_timestamp=NS)
    rows.append(row)
    snapshots.append(dict(stock=sid,name=name,day=day,original_actualfacts=f,
        original_aux_E0_event=ev,original_aux_E0_states=es if es is not None else NS,
        saved_G1_source_frame_not_actual_I=g,requested_G1_components_exact_names=components,
        original_CP_frame=cp,CP_old_actual_layer_floors=oldcp,
        original_live_layers=[layer(l)for l in live],original_OPEN_buys=buys,original_OPEN_sells=sells,original_CLOSE_exit_proposals=exits,
        source_container_note='Only saved original evidence selected from peer paper container; its candidate paper decisions/quantities are excluded.',
        scope='All continuous C/line fields copied verbatim. Raw separate, no factor conversion or I/IX replacement.'))

hb={r['day']:r for r in hai}
for day in ['2024-11-04','2024-11-05','2024-11-26']:add('002583.SZ','海能达',day,hb[day],True)
for day in ['2022-01-21','2022-01-24','2022-01-27','2022-02-07','2022-02-08']:add('000620.SZ','盈新发展',day,yb[day])
save('PAIRED_SAME_A_COORDINATE_ROWS.json',rows)
save('ORIGINAL_SNAPSHOT_RAWDICTS.json',snapshots)
with (O/'PAIRED_SAME_A_COORDINATE.csv').open('w',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save('SOURCE_SHA256.json',SOURCES)
save('COST_AND_SCOPE.json',dict(stock_dates=8,source='Own saved43-day Hytera extraction and peer saved original YingXin case/exit traces only; no original parquet needed.',
    all_C_and_lines_in_original_a_coordinate=True,raw_prices_and_factor_separate=True,price_conversion_performed=False,
    missing_G1_components='S21/S63 state/pace, mu5/mu21/s/qeff not present in saved source IX G1 frame: NOT_SAVED. Saved z5/z21/phase/proposal/acute kept without relabeling.',
    actual_I_only_actualfacts=True,IX_target_not_copied=True,E0_auxiliary_event_and_state_labeled=True,
    new_models=0,new_accounts=0,new_backtests=0,new_features=0,new_parquet_reads=0,seconds=time.monotonic()-start))
print(json.dumps(dict(rows=len(rows),seconds=time.monotonic()-start,new_models=0)))

"""One bounded saved-anchor diagnostic; no Account, orders, sizing, or fitting."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import argparse
import json
import hashlib
import math
import sys
import time
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SHARED = BASE.parent / 'channel_atr_fsm_v1'
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(BASE))
import engine
import runner
import run_observation as trace_provider
import cusum_v2 as core_v2
import stratify
import match

PAIR_RUNS = [SHARED/'shard_a/run_v1', SHARED/'shard_b/run_v1', SHARED/'semiconductor_full/run_v1']
SEMICO = SHARED/'semiconductor_full/SYMBOLS126.json'
CORE_SHA = 'dc51546262739da5db9e7ae50c26c42e10162a2b108608d34e119f100a37583c'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(engine.clean(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def window_tags(sid, day, semiconductor):
    tags = []
    if '2022-01-01' <= day <= '2023-12-31':
        tags.append('2022_2023')
    if '2024-09-01' <= day <= '2024-12-31':
        tags.append('2024_Sep_Dec')
        if day >= '2024-09-24':
            tags.append('2024_post924_APPENDIX_OVERLAPS')
    if sid in semiconductor and '2026-01-01' <= day <= '2026-06-30':
        tags.append('2026H1_FIXED_SEMICONDUCTOR_APPENDIX_OVERLAPS')
    if sid in semiconductor and '2025-01-01' <= day <= '2026-06-30':
        tags.append('2025_2026Jun_FIXED_SEMICONDUCTOR')
    return tags


def forward_labels(price, f, daily):
    """Fixed next20 closes, cross later I freely; never skip unknown or source."""
    C = price.close.to_numpy(float)
    valid = f.close_valid.to_numpy(bool)
    source = f.source_key.to_numpy()
    n = len(price)
    end = np.arange(n)
    for j in range(n-2, -1, -1):
        if valid[j] and valid[j+1] and source[j] == source[j+1]:
            end[j] = end[j+1]
    scales = daily.s63.to_numpy()
    out = []
    for j in range(n):
        if not valid[j]:
            out.append(dict(label_status='CURRENT_CLOSE_UNKNOWN', forward20_n_observations=0, MFE20=None, MAE20=None,
                            first_hit20_label='CURRENT_INPUT_UNKNOWN',first_hit20_day=None,rebound_after_down=None))
            continue
        count = min(20, int(end[j])-j)
        future = C[j+1:j+1+count]
        if count == 20:
            result = dict(label_status='COMPLETE_20', forward20_n_observations=20,
                          MFE20=max(0., float(future.max()/C[j]-1)), MAE20=max(0., float(1-future.min()/C[j])))
        else:
            next_bad = int(end[j])+1
            status = 'SOURCE_END_RIGHT_CENSORED' if next_bad >= n else 'SOURCE_INCOMPARABLE' if source[next_bad] != source[j] else 'UNKNOWN_FUTURE_CLOSE'
            result = dict(label_status=status, forward20_n_observations=count, MFE20=None, MAE20=None)
        first, hit_step = None, None
        if engine.positive(scales[j]) and daily.scale_status.iloc[j]=='READY':
            upper, lower = C[j]*math.exp(float(scales[j])), C[j]*math.exp(-float(scales[j]))
            for k, value in enumerate(future,1):
                if engine.ge(float(value),upper):first,hit_step='UP_FIRST',k;break
                if engine.ge(lower,float(value)):first,hit_step='DOWN_FIRST',k;break
            if first is None:
                first = 'UNDECIDED_FULL20' if count==20 else 'UNKNOWN_CENSORED' if result['label_status']=='UNKNOWN_FUTURE_CLOSE' else 'SOURCE_CENSORED'
            rebound = None
            rebound_status = 'NOT_DOWN_FIRST'
            if first=='DOWN_FIRST':
                returned = any(engine.ge(float(value),float(C[j])) for value in future[hit_step:])
                rebound = True if returned else False if count==20 else None
                rebound_status = 'KNOWN_REBOUND_AFTER_DOWN' if returned else 'NO_REBOUND_COMPLETE20' if count==20 else 'REBOUND_UNRESOLVED_CENSORED'
            result.update(first_hit20_label=first,first_hit20_step=hit_step,
                          first_hit20_day=None if hit_step is None else str(price.index[j+hit_step].date()),
                          first_hit_known_before_later_censor=hit_step is not None and count<20,
                          rebound_after_down=rebound,rebound_after_down_status=rebound_status)
        else:
            result.update(first_hit20_label='CURRENT_SCALE_UNKNOWN',first_hit20_day=None,rebound_after_down=None)
        out.append(result)
    return out


def worker(task):
    slot, sids, core_path, output = task
    output = Path(output)
    assert Path(core_v2.__file__).resolve()==Path(core_path).resolve()
    core = core_v2  # legacy run_observation main/cusum.calculate is never called.
    metas = {x['symbol']: x for x in json.loads(runner.MANIFEST.read_text())}
    semiconductor = set(json.loads(SEMICO.read_text()))
    panel, reports, errors = [], [], []
    started = time.monotonic()
    for number, sid in enumerate(sids):
        try:
            pairs, pair_sources = [], {}
            for root in PAIR_RUNS:
                path = root/sid.replace('.', '_')/'CP_ANCHOR_PAIRS.json'
                if path.exists():
                    pair_sources[str(path)] = sha(path)
                    pairs.extend(json.loads(path.read_text()))
            ids = [(x['sid'], x['anchor_day']) for x in pairs]
            assert len(ids) == len(set(ids)), (sid, 'duplicate original anchor')
            if not pairs:
                reports.append(dict(sid=sid,status='NO_SAVED_RAW_CP_ANCHOR',raw_anchors=0))
                continue
            data, source_hashes = runner.read_symbol(metas[sid])
            p, native = data['price'], data['facts']
            f = engine.features(p)
            daily = core.calculate(sid, p, f, native)
            original_events = data['events'].reindex(p.index).event.to_numpy()
            native_exact=native.reindex(p.index)
            labels = forward_labels(p, f, daily)
            dates = [str(t.date()) for t in p.index]
            positions = {d:j for j,d in enumerate(dates)}
            sources = f.source_key.to_numpy()
            cv = f.close_valid.to_numpy(bool)
            day_records = engine.clean(daily.to_dict('records'))
            cycle_starts = {}
            for j, row in enumerate(day_records):
                if row['cycle_id'] and row['cycle_start_day']:
                    cycle_starts[row['cycle_id']] = positions.get(row['cycle_start_day'])
                row['I_cycle_age'] = None if not row['cycle_id'] or cycle_starts.get(row['cycle_id']) is None else j-cycle_starts[row['cycle_id']]+1
                row['one_day'] = max(0., -row['r']/row['s63']-.25) if engine.finite(row['r']) and engine.positive(row['s63']) else None
                row['memory_required_on_cross'] = bool(row['threshold_cross'] and row['one_day'] is not None and row['one_day'] < 3.)
                event = original_events[j]
                row['E0_down_same_close'] = None if not engine.finite(event) else float(event) == -1.
                row['original_native_e0_ready']=engine.bit(native_exact.e0_ready.iloc[j])
                row['original_native_e0_target']=engine.bit(native_exact.e0_target.iloc[j])
                prior = range(j-5,j)
                row['E0_down_in_prior5_complete_observations'] = None if j<5 or any(not cv[k] or sources[k]!=sources[j] or not engine.finite(original_events[k]) for k in prior) else any(float(original_events[k]) == -1. for k in prior)
                next_down=None;future_status='NO_EVENT_WITHIN_COMPLETE20';available=0
                for k in range(j+1,min(len(day_records),j+21)):
                    if sources[k]!=sources[j]:future_status='SOURCE_CENSORED';break
                    if not cv[k] or not engine.finite(original_events[k]):future_status='UNKNOWN_CENSORED';break
                    available+=1
                    if float(original_events[k])==-1.:next_down=k;future_status='KNOWN_FUTURE_DOWN_WITHIN20';break
                if next_down is None and future_status=='NO_EVENT_WITHIN_COMPLETE20' and available<20:future_status='SOURCE_END_CENSORED'
                row['next_E0_down_within20_status_LABEL_ONLY']=future_status
                row['next_E0_down_within20_day_LABEL_ONLY']=None if next_down is None else dates[next_down]
                row['next_E0_down_within20_lead_LABEL_ONLY']=None if next_down is None else next_down-j
            # Backward future-event diagnostics are labels only, never used to
            # choose the reference, warning status, controls, or a match.
            next_down_by_cycle = {}
            for j in range(len(day_records)-1,-1,-1):
                row=day_records[j];cid=row['cycle_id']
                upcoming=next_down_by_cycle.get(cid)
                row['future_E0_unknown_barrier_LABEL_ONLY']=upcoming=='UNKNOWN'
                row['next_E0_down_same_I_cycle_day_LABEL_ONLY']=None if upcoming is None or upcoming=='UNKNOWN' else dates[upcoming]
                row['next_E0_down_same_I_cycle_lead_LABEL_ONLY']=None if upcoming is None or upcoming=='UNKNOWN' else upcoming-j
                if cid:
                    if not row['close_valid'] or row['native_i_target'] is None or row['E0_down_same_close'] is None:next_down_by_cycle[cid]='UNKNOWN'
                    elif row['E0_down_same_close'] is True:next_down_by_cycle[cid]=j
            cycle_terminal={}
            for row in day_records:
                if row['cycle_id']:
                    cycle_terminal[row['cycle_id']]=row
            for row in day_records:
                terminal=cycle_terminal.get(row['cycle_id'])
                row['next_E0_down_status_LABEL_ONLY']='KNOWN_FUTURE_DOWN' if row['next_E0_down_same_I_cycle_day_LABEL_ONLY'] else 'UNKNOWN_CENSORED_I_CYCLE' if row['future_E0_unknown_barrier_LABEL_ONLY'] else 'NO_LATER_DOWN_IN_COMPLETED_I_CYCLE' if terminal and terminal['cycle_end_reason']=='NATIVE_I_ONE_TO_ZERO' and terminal['D_status']!='UNKNOWN' else 'UNKNOWN_CENSORED_I_CYCLE' if terminal and terminal['D_status']=='UNKNOWN' else 'SOURCE_CENSORED_I_CYCLE'
            selected = {}
            status_counts = Counter(x['status'] for x in pairs)
            trace_rows = 0
            unknown_endpoints = 0
            preentry_trace_rows_ignored=0
            for pair in pairs:
                if pair['status'] != 'PAIRED_SHADOWS':
                    continue  # all omitted reference statuses remain explicit in reports.
                trace = trace_provider.original_CP_line(pair, p, f, native, data['CP1'])
                trace_rows += len(trace)
                entry = pair['entry_reference']['next_observation_day']
                entryj = positions[entry]
                entryD = day_records[entryj]
                before_entry=None if entryj==0 else day_records[entryj-1]
                inherited=None
                if before_entry is not None and before_entry['close_valid'] and before_entry['source_key']==entryD['source_key']:
                    if before_entry['native_i_target']==0:inherited=False
                    elif before_entry['native_i_target']==1 and before_entry['D_status']=='KNOWN' and engine.finite(before_entry['D']):inherited=before_entry['D']>=3
                inherited_status='UNKNOWN_BEFORE_ENTRY' if inherited is None else 'KNOWN_WARNING_BEFORE_ENTRY' if inherited else 'KNOWN_NO_ACTIVE_WARNING_BEFORE_ENTRY'
                peak = None
                rank = (entry, pair['anchor_day'], pair['anchor_id'])
                entered_trace=[line for line in trace if line['day']>=entry]
                preentry_trace_rows_ignored+=len(trace)-len(entered_trace)
                for age, line in enumerate(entered_trace, 1):
                    day = line['day']
                    C = float(line['C'])
                    peak = C if peak is None else max(peak, C)
                    if not window_tags(sid, day, semiconductor):
                        continue
                    row = dict(day_records[positions[day]], anchor_id=pair['anchor_id'], anchor_day=pair['anchor_day'],
                        entry_day=entry, holding_age=age, known_close_peak=peak, P_old=line['P_old'],
                        original_CP_proposal=line['proposal_after_old_line_check'],
                        current_CP_I_exit=line['exit_reason'] is not None, current_CP_exit_reason=line['exit_reason'],
                        reference_status='ENTERED_ORIGINAL_CP_REFERENCE', warning_inherited_at_entry=inherited,
                        warning_inherited_at_entry_status=inherited_status,
                        prior_entry_completed_close_day=None if before_entry is None else before_entry['day'],
                        saved_CP_exit_day_LABEL_ONLY=pair['CP']['exit_day'],
                        saved_CP_exit_status_LABEL_ONLY='KNOWN_EXIT' if pair['CP']['exit_day'] is not None else pair['CP']['outcome']+'_WITHOUT_EXIT',
                        lead_to_CP_exit_observations_LABEL_ONLY=None if pair['CP']['exit_day'] is None else len(entered_trace)-age,
                        **labels[positions[day]])
                    row['extra_event_only_cross_bridge']=bool(row['active_cross_warning'] and not row['current_CP_I_exit'] and row['E0_down_same_close'] is False and row['E0_down_in_prior5_complete_observations'] is False)
                    row['extra_incremental_active_cross_candidate']=bool(row['extra_event_only_cross_bridge'] and row['original_native_e0_ready']==1 and row['original_native_e0_target']==1)
                    # Select before current exit/label classification; do not replace
                    # today's exiting oldest anchor with a younger survivor.
                    if day not in selected or rank < selected[day][0]:
                        selected[day] = (rank, row)
                if pair['CP']['outcome'] == 'UNKNOWN':
                    unknown_endpoints += 1
                    last_known=positions[trace[-1]['day']] if trace else positions[pair['anchor_day']]
                    day = dates[min(last_known+1,len(dates)-1)]
                    if day>=entry and day in positions and window_tags(sid, day, semiconductor):
                        row = dict(day_records[positions[day]], anchor_id=pair['anchor_id'], anchor_day=pair['anchor_day'],
                            entry_day=entry, holding_age=None, known_close_peak=peak, P_old=None,
                            current_CP_I_exit=None, current_CP_exit_reason=None,
                            reference_status='UNKNOWN_ORIGINAL_CP_REFERENCE_ENDPOINT',
                            warning_inherited_at_entry=inherited,extra_incremental_active_cross_candidate=False,
                            warning_inherited_at_entry_status=inherited_status,extra_event_only_cross_bridge=False,
                            **labels[positions[day]])
                        if day not in selected or rank < selected[day][0]:
                            selected[day] = (rank,row)
            for day, (_, row) in sorted(selected.items()):
                for tag in window_tags(sid, day, semiconductor):
                    panel.append(dict(row,analysis_window=tag))
            reports.append(dict(sid=sid,status='COMPLETE',raw_anchors=len(pairs),saved_anchor_status_counts=dict(status_counts),
                CP_trace_rows=trace_rows,original_CP_unknown_reference_endpoints=unknown_endpoints,
                preentry_trace_rows_ignored=preentry_trace_rows_ignored,
                selected_stock_days_before_overlapping_scope_tags=len(selected),
                source_sha256=source_hashes,pair_source_sha256=pair_sources,
                no_unstored_preperiod_carry_added=True))
        except Exception as error:
            errors.append(dict(sid=sid,error=repr(error)))
        if (number+1)%50==0:
            print(json.dumps(dict(worker=slot,completed=number+1,total=len(sids),errors=len(errors),elapsed=time.monotonic()-started)),flush=True)
    pd.DataFrame(engine.clean(panel)).to_parquet(output/f'PANEL_{slot}.parquet')
    save(output/f'WORKER_{slot}_REPORTS.json',reports)
    save(output/f'WORKER_{slot}_ERRORS.json',errors)
    return dict(worker=slot,symbols=len(sids),rows=len(panel),errors=len(errors),raw_anchors=sum(x['raw_anchors'] for x in reports),seconds=time.monotonic()-started)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--processes',type=int,default=3)
    args = parser.parse_args()
    assert args.processes == 3 and sha(args.core) == CORE_SHA
    assert args.core.resolve()==(BASE/'cusum_v2.py').resolve()
    output = args.out
    output.mkdir(exist_ok=False)
    frozen_files = [args.core,BASE/'FREEZE.md',BASE/'run_observation.py',SHARED/'engine.py',SHARED/'runner.py',runner.MANIFEST,
                    SEMICO,Path(__file__),HERE/'match.py',HERE/'stratify.py']
    sources = {str(p):sha(p) for p in frozen_files}
    all_sids = sorted(x['symbol'] for x in json.loads(runner.MANIFEST.read_text()))
    tasks = [(i,all_sids[i::3],str(args.core.resolve()),str(output.resolve())) for i in range(3)]
    started = time.monotonic()
    save(output/'RUN_START.json',dict(source_sha256=sources,processes=3,symbols=len(all_sids),raw_anchor_mother=51026))
    with ProcessPoolExecutor(max_workers=3) as pool:
        statuses = list(pool.map(worker,tasks))
    assert sum(x['raw_anchors'] for x in statuses) == 51026 or any(x['errors'] for x in statuses)
    if any(x['errors'] for x in statuses):
        save(output/'RUN_RECEIPT.json',dict(status='PARTIAL_ERROR_NO_RETRY',workers=statuses,source_sha256=sources))
        raise SystemExit('Preserved per-worker errors; no automatic rerun')
    panel = pd.concat([pd.read_parquet(output/f'PANEL_{i}.parquet') for i in range(3)],ignore_index=True)
    records = engine.clean(panel.to_dict('records'))
    coarse = stratify.aggregate(records)
    matched, match_rows = match.run(records)
    save(output/'COARSE_STRATA_DESCRIPTIVE.json',coarse)
    save(output/'SAME_DAY_CALIPER_MATCH_SUMMARY.json',matched)
    matched_records=[dict(analysis_window=x['analysis_window'],day=x['day'],warning_sid=x['warning_sid'],control_sid=x['control_sid'],
                      warning_anchor_id=x['warning_anchor_id'],control_anchor_id=x['control_anchor_id'],score=x['score'],
                      label_pair_status=x['label_pair_status'],**{'warning_'+k:x['warning'].get(k) for k in ['D','MFE20','MAE20','oldP_logdist_s','known_close_drawdown_s','holding_age','s63','first_hit20_label','rebound_after_down','active_cross_warning','extra_incremental_active_cross_candidate','original_native_e0_ready','original_native_e0_target']},
                      **{'control_'+k:x['control'].get(k) for k in ['D','MFE20','MAE20','oldP_logdist_s','known_close_drawdown_s','holding_age','s63','first_hit20_label','rebound_after_down','active_cross_warning','extra_incremental_active_cross_candidate','original_native_e0_ready','original_native_e0_target']})
                  for x in match_rows]
    pd.DataFrame(matched_records if matched_records else {'analysis_window':pd.Series(dtype=str)}).to_parquet(output/'CALIPER_MATCHED_PAIRS.parquet')
    cross_summary = {}
    for tag, frame in panel.groupby('analysis_window',sort=True):
        cross = frame.loc[frame.threshold_cross.eq(True)]
        active = cross.loc[cross.native_i_target.eq(1)]
        cross_summary[tag] = dict(selected_rows=len(frame),threshold_cross_rows=len(cross),active_cross_rows=len(active),
            memory_required_on_cross=int(cross.memory_required_on_cross.eq(True).sum()),
            active_memory_required_on_cross=int(active.memory_required_on_cross.eq(True).sum()),
            cross_current_CP_I_exit=int(cross.current_CP_I_exit.eq(True).sum()),
            warning_inherited_at_entry_rows=int(frame.warning_inherited_at_entry.eq(True).sum()))
        cross_summary[tag]['warning_inherited_at_entry_unknown_rows']=int(frame.warning_inherited_at_entry.isna().sum())
        cross_summary[tag]['inherited_at_entry_status_counts']=dict(Counter(frame.warning_inherited_at_entry_status))
        cross_summary[tag]['wide_event_only_cross_bridge_rows']=int(frame.extra_event_only_cross_bridge.eq(True).sum())
        cross_summary[tag]['cross_current_E0_ready_target_counts']=dict(Counter(str((engine.bit(x),engine.bit(y))) for x,y in zip(cross.original_native_e0_ready,cross.original_native_e0_target)))
        extra=frame.loc[frame.extra_incremental_active_cross_candidate.eq(True)]
        cross_summary[tag]['extra_incremental_active_cross_candidate_rows']=len(extra)
        cross_summary[tag]['all_active_cross_unique_stocks']=int(active.sid.nunique())
        cross_summary[tag]['all_active_cross_unique_I_cycles']=int(active.cycle_id.nunique())
        cross_summary[tag]['extra_cross_unique_stocks']=int(extra.sid.nunique())
        cross_summary[tag]['extra_cross_unique_I_cycles']=int(extra.cycle_id.nunique())
        cross_summary[tag]['extra_cross_future_CP_status_counts']=dict(Counter(extra.get('saved_CP_exit_status_LABEL_ONLY',pd.Series(dtype=object))))
        cross_summary[tag]['extra_cross_future_E0_status_counts']=dict(Counter(extra.next_E0_down_status_LABEL_ONLY))
        cross_summary[tag]['extra_cross_future_E0_within20_status_counts']=dict(Counter(extra.next_E0_down_within20_status_LABEL_ONLY))
        cross_summary[tag]['extra_cross_known_first_hit20_counts']=dict(Counter(extra.first_hit20_label))
    save(output/'CROSS_AND_MEMORY_DECOMPOSITION.json',cross_summary)
    assert all(sha(path)==value for path,value in sources.items()),'source changed; preserve outputs'
    save(output/'RUN_RECEIPT.json',dict(status='COMPLETE_LIMITED_SAVED_ANCHOR_PRICE_DIAGNOSTIC',workers=statuses,
        source_sha256=sources,raw_anchor_mother=51026,panel_rows_with_overlapping_scope_tags=len(panel),
        windows=list(coarse),matched_pairs_with_overlapping_scope_tags=sum(x['matched_pairs'] for x in matched.values()),
        elapsed_seconds=time.monotonic()-started,new_accounts=0,new_orders=0,new_quantities=0,new_returns=0,
        no_future_labels_used_to_choose_anchor_or_match=True,no_parameter_search=True))
    print(json.dumps(dict(status='COMPLETE',rows=len(panel),seconds=time.monotonic()-started,match_summary=matched),allow_nan=False),flush=True)


if __name__=='__main__':
    main()

"""Validate the already exported baseline after correcting nested audit dates.
No bootstrap, restore, event replay, account mutation or checkpoint rewrite.
"""
from pathlib import Path
import json, time, re
import resume_baseline as B


def main():
    started = time.monotonic()
    out = B.HERE/'run'
    assert not (out/'DONE.json').exists(), 'Do not overwrite a completed result'
    original = B.S.read(out/'PREDECLARED.json')
    failure = B.S.read(out/'FAILURE.json')
    assert 'undated record' in failure['error']
    assert failure['last_complete_event'] == '2023-04-28 15:10:00+08:00'
    assert B.sha(B.HERE/'resume_baseline_execution_v1.py') == original['driver_sha256']
    B.verify_frozen_sources(original['source_freeze'])
    assert B.sha(B.CHECKPOINT) == B.CHECKPOINT_SHA256
    checkpoint = out/'latest_checkpoint/checkpoint.pkl'
    meta = B.S.read(checkpoint.with_suffix('.json'))
    provenance = B.S.read(checkpoint.with_suffix('.provenance.json'))
    assert B.sha(checkpoint) == meta['sha256'] == provenance['checkpoint_sha256']
    assert meta['at'] == provenance['last_completed_event'] == '2023-04-28 15:10:00+08:00'
    assert meta['source_freeze'] == original['source_freeze']
    assert provenance['engine_identity'] == B.S.read(B.CHECKPOINT.with_suffix('.provenance.json'))['engine_identity']
    clock = list(B.jsonl(out/'EVENT_CLOCK.jsonl.gz'))
    opens = [x for x in clock if x['phase']=='OPEN']
    closes = [x for x in clock if x['phase']=='CLOSE']
    assert len(opens) == len(closes) == 78
    assert opens[0]['at'] == '2023-01-03 09:30:00+08:00'
    assert closes[-1]['at'] == '2023-04-28 15:10:00+08:00'
    print('COMPARE_ORIGINAL_PREFIX', flush=True)
    result = B.validate_exports(out)
    B.S.save(out/'BASELINE_VALIDATION.json', result)
    assert result['passed'], result['first_difference']
    last_daily = list(B.jsonl(out/'pair/daily.jsonl.gz'))[-1]
    log = (B.HERE/'run.log').read_text()
    run_seconds = float(re.search(r'MONTH 2023-04-28 elapsed ([0-9.]+)', log)[1])
    input_seconds = float(re.search(r'INPUTS_READY ([0-9.]+)', log)[1])
    done = dict(completed=True, validation_passed=True, last_event=closes[-1]['at'],
                sessions=78, events=len(clock), action_events=sum(x['phase']=='ACTION' for x in clock),
                run_seconds=run_seconds, input_load_seconds=input_seconds,
                logged_runtime_precision_seconds=0.001,
                validation_recovery_seconds=time.monotonic()-started,
                holdings_count=len(last_daily['positions']), pending_count=last_daily['pending_intents'],
                ending_cash=last_daily['available'], ending_nav=last_daily['nav'],
                original_sources_unchanged=True, original_checkpoint_unchanged=True,
                original_engine_guards_preserved=True, real_orders=False,
                continuation_rerun=False, checkpoints_rewritten=False,
                original_post_run_comparison_failure_retained='FAILURE.json',
                correction='Only validation timestamp extraction: fill.receipt.at and dividend_accrual.receivable.ex_at. All original financial execution and outputs retained.',
                executed_driver_sha256=original['driver_sha256'], current_driver_sha256=B.sha(B.HERE/'resume_baseline.py'))
    B.S.save(out/'DONE.json', done)
    B.S.save(out/'OUTPUT_HASHES.json', {str(p.relative_to(out)): B.sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'OUTPUT_HASHES.json'})
    print('DONE', json.dumps(done), flush=True)


if __name__ == '__main__':
    main()

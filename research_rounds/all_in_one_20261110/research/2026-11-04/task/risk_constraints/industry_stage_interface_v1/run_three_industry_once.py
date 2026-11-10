"""One root-authorized pure Stage gate. Never imports an account or runner."""
from pathlib import Path
import importlib.util
import json
import signal
import sys
import time
import traceback

import pandas as pd

HERE = Path(__file__).resolve().parent
START = time.monotonic()
CURRENT = 'preflight'


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def timeout(*_):
    raise TimeoutError('fixed 30 second total Stage gate budget exhausted')


def main():
    global CURRENT
    freeze = read(HERE / 'SOURCE_FREEZE.json')
    assert freeze['authorized_series'] == ['URFI881155', 'URFI881278', 'URFI881118']
    assert not (HERE / 'COMPLETED.json').exists() and not (HERE / 'FAILED.json').exists(), 'one execution only'
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, 30 - (time.monotonic() - START)))
    bridge = load('volume_neutral_original_pure_stage_bridge', HERE / 'pure_stage_wrapper.py')
    for path, expected in freeze['all_input_sha256'].items():
        assert bridge.sha(path) == expected, ('frozen_input_changed', path)
    cp1 = load('volume_neutral_original_CP1_for_Stage_ge', bridge.MODEL_PATH)
    norm = None
    true_gates = []
    prefixes = []
    all_results = {}
    for sid in freeze['authorized_series']:
        refs = freeze['series'][sid]
        for arm in ('real', 'neutral'):
            CURRENT = arm + '_' + sid
            features = {k: pd.read_parquet(path) for k, path in refs[arm].items()}
            result = bridge.run_industry(sid, features, cp1, arm=arm,
                                        method_identity=freeze['neutral_method_identity'])
            if norm is None:
                norm = bridge._interfaces(cp1, 'real', 'unused', '2026-06-30')[0]['norm']
            folder = HERE / (sid + '_' + arm.upper())
            folder.mkdir(exist_ok=False)
            pd.DataFrame(result['rows']).to_parquet(folder / 'Stage.parquet', index=False)
            save(folder / 'TRACE_RECEIPTS.json', norm(result['receipts']))
            save(folder / 'IDENTITY.json', {k: result[k] for k in ('arm', 'canonical_series', 'scale_id', 'episode_source', 'financial_state_owned')})
            if arm == 'real':
                gate = bridge.assert_real_saved_reference(result, refs['old_state'], refs['old_receipts'])
                true_gates.append(dict(sid=sid, **gate))
            else:
                pd.DataFrame(dict(observed_m=result['observed_amount_multiplier'], effective_m=1.0)).to_parquet(folder / 'AMOUNT_MULTIPLIER.parquet')
            all_results[(sid, arm)] = result
    # Only the three neutral industry prefixes explicitly granted by root.
    for sid in freeze['authorized_series']:
        CURRENT = 'neutral_physical_prefix_' + sid
        cut = freeze['physical_prefix_cut']
        short = {k: pd.read_parquet(path).loc[:cut].copy() for k, path in freeze['series'][sid]['neutral'].items()}
        result = bridge.run_industry(sid, short, cp1, arm='neutral', method_identity=freeze['neutral_method_identity'], end=cut)
        full = all_results[(sid, 'neutral')]
        expected_rows = [r for r in full['rows'] if r['day'] <= cut]
        expected_receipts = [r for r in full['receipts'] if r['confirmed_day'] <= cut]
        known_receipts = {r['receipt_id'] for r in expected_receipts}
        expected_increments = [r for r in full['increments'] if r['receipt_id'] in known_receipts]
        assert norm(result['rows']) == norm(expected_rows), 'neutral physical Stage prefix mismatch'
        assert norm(result['receipts']) == norm(expected_receipts), 'neutral physical trace prefix mismatch'
        assert norm(result['increments']) == norm(expected_increments), 'neutral physical trace evidence prefix mismatch'
        prefixes.append(dict(sid=sid, cutoff=cut, Stage_rows_exact=len(result['rows']), trace_receipts_all_fields_exact=len(result['receipts']), original_trace_increments_exact=len(result['increments'])))
    for path, expected in freeze['all_input_sha256'].items():
        assert bridge.sha(path) == expected, ('frozen_input_changed_after', path)
    assert not any('Runner' in name or 'controller' in name.lower() or name.startswith('trace_original_cp1_common') for name in sys.modules)
    imports = {k: str(getattr(v, '__file__', '')) for k, v in sys.modules.items() if k.startswith('volume_neutral_')}
    save(HERE / 'IMPORT_IDENTITIES.json', imports)
    save(HERE / 'REAL_REFERENCE_GATES.json', true_gates)
    save(HERE / 'NEUTRAL_PHYSICAL_PREFIXES.json', prefixes)
    save(HERE / 'COMPLETED.json', dict(passed=True, seconds=time.monotonic() - START, source_freeze_sha256=bridge.sha(HERE / 'SOURCE_FREEZE.json'),
                                      original_algorithm_unchanged=True, original_three_fixture_outputs_unchanged=True,
                                      industries=3, neutral_physical_prefixes=3, neutral_E0_episode_rebuilt=True,
                                      account_events=0, economic_outputs=0, ninety_industry_batch=False,
                                      receipt_scope='Fullwarm old Stage rows include receipt identities; separate compact receipt JSON is only existing saved audit dates.'))
    signal.setitimer(signal.ITIMER_REAL, 0)
    print('THREE_INDUSTRY_PURE_STAGE_COMPLETED', time.monotonic() - START, flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        save(HERE / 'FAILED.json', dict(stage=CURRENT, error=repr(exc), traceback=traceback.format_exc(), seconds=time.monotonic() - START,
                                       account_events=0, no_automatic_retry=True))
        print('THREE_INDUSTRY_PURE_STAGE_STOPPED', CURRENT, repr(exc), flush=True)
        raise

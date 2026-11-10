"""Verify only this prototype and fixed read-only input hashes."""
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

from signal_core import VERSION
from test_signal_core import series, trace

OUT = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def main():
    suite = unittest.defaultTestLoader.loadTestsFromName('test_signal_core.PermissionTests')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (OUT/'TEST_LOG.txt').write_text(stream.getvalue())
    source_before = json.loads((OUT/'INPUT_SHA256.json').read_text())
    current = {p: sha(p) for p in source_before}
    unchanged = {p: current[p] == h for p, h in source_before.items()}
    controls = json.loads((OUT/'HISTORICAL_INPUT_READINESS.json').read_text())['source_control_checks']
    controls_unchanged = {p: sha(p) == r['expected'] for p, r in controls.items()}
    definitions = [
        ('fast_start', [110], None),
        ('single_jump_flat', [110, 120, 120, 120, 120], None),
        ('gradual_rise', [110, 111, 112, 113, 114, 115, 116, 117, 118], None),
        ('repair_below_old_high', [110, 125, 114, 112, 116], None),
        ('ADVERSE_false_repair_lagging_breadth', [110, 125, 114, 118, 100, 90], [.8, .8, .8, .8, .8, .4]),
        ('double_failure_no_bounce_restart', [110, 125, 114, 118, 100, 90, 95, 100, 110], [.8, .8, .8, .8, .8, .4, .9, .9, .9]),
        ('unknown_price_then_observed_failure', [110, None, 90], [.8, .8, .8]),
    ]
    cases = []
    for name, prices, breadths in definitions:
        seq = series(prices, breadths)
        states, decisions = trace(seq)
        cases.append(dict(name=name, input=[asdict(o) for o in seq[-len(prices):]],
                          states=[asdict(s) for s in states[-len(prices):]],
                          decisions=[asdict(d) for d in decisions[-len(prices):]]))
    save('SYNTHETIC_CASES.json', dict(warmup='64 alternating 100,100*exp(.01) closes, breadth=.5; synthetic only', cases=cases))
    status = dict(
        version=VERSION, implemented_contract_tests_passed=result.wasSuccessful(),
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        physical_prefix_fresh_process_cuts=[0, 1, 63, 64, 65, 68, 74, 88],
        checkpoint_split_points=76,
        input_files_unchanged=unchanged, existing_source_controls_unchanged=controls_unchanged,
        all_checked_original_inputs_unchanged=all(unchanged.values()) and all(controls_unchanged.values()),
        final_contract_frozen=False,
        semantic_blocker='ACTIVE observed price breach with unknown breadth: ENDED vs pending-failure branch awaits answer',
        branch_behavior='raises structured SemanticDecisionRequired; retains serializable observed-failure receipt; stream must stop',
        historical_shadow_sequences=0, historical_indicator_recomputations=0,
        account_runs=0, data_downloads=0, orders=0,
        source_tree_mutations=0, existing_result_mutations=0, service_actions=0,
        independent_review='not performed; explicitly required before historical admission',
    )
    save('VERIFICATION.json', status)
    save('SOURCE_SHA256.json', {p.name: sha(p) for p in sorted(OUT.glob('*.py'))})
    save('ARTIFACT_SHA256.json', {p.name: sha(p) for p in sorted(OUT.iterdir())
                                  if p.is_file() and p.name != 'ARTIFACT_SHA256.json'})
    print(json.dumps(dict(tests=result.testsRun, passed=result.wasSuccessful(),
                          original_inputs_unchanged=status['all_checked_original_inputs_unchanged'],
                          final_contract_frozen=False, historical_shadow_sequences=0)))
    if not result.wasSuccessful() or not status['all_checked_original_inputs_unchanged']:
        sys.exit(1)


if __name__ == '__main__':
    main()

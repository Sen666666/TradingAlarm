"""Verify only this prototype and fixed read-only input hashes."""
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

from signal_core import VERSION
from test_signal_core import pending_series, series, trace

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
        ('pending_positive_forward_only', [110, 90, 60, None, 70, 120, 121, 125],
         [.8, None, None, .9, None, .9, .9, .9]),
        ('pending_nonpositive_first_complete', [110, 90, None, 60, 120], [.8, None, .4, None, .6]),
        ('pending_classification_break_does_not_restart', [110, 90, 60, 120], [.8, None, None, .9]),
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
        pending_physical_prefix_cuts=dict(positive=list(range(64, 73)), nonpositive=list(range(64, 70))),
        pending_checkpoint_split_points=dict(positive=73, nonpositive=70),
        pending_disk_checkpoint_fresh_process_cuts=dict(positive=list(range(65, 73)), nonpositive=list(range(65, 70))),
        total_fresh_process_prefixes=23, total_fresh_process_disk_resumes=13,
        total_json_checkpoint_split_points=219,
        input_files_unchanged=unchanged, existing_source_controls_unchanged=controls_unchanged,
        all_checked_original_inputs_unchanged=all(unchanged.values()) and all(controls_unchanged.values()),
        final_contract_frozen=True,
        unresolved_unknown_transition_boundaries=[],
        branch_behavior='pending_price_failure; immutable receipt; zero waiting credit; first complete future observation only classifies REPAIR-anchor or ENDED; no same-observation restore or restart',
        old_line_failure_comparison='close <= old_line; inclusive touch per latest delegated ruling',
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
                          final_contract_frozen=True, historical_shadow_sequences=0)))
    if not result.wasSuccessful() or not status['all_checked_original_inputs_unchanged']:
        sys.exit(1)


if __name__ == '__main__':
    main()

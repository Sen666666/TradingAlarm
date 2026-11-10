"""Transport-free tests of queue stop/resume and persisted result checks."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

import history_batch as hb
import history_queue as q


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.plan = {'schema_version': 1, 'max_requests': 2, 'items': [dict(symbol='USHA600000', node='9602',
                     end='20261022', earliest='20261001', mode='tail', rights=True)]}
        self.path = self.base / 'plan.json'; self.path.write_bytes(hb.encoded(self.plan))
        self.batch = dict(name='plan', plan=str(self.path), sha256=hb.digest(self.path.read_bytes()), nodes=['9602'], items=1, max_requests=2)
        self.out = self.base / 'out'

    def child(self, directory, status='complete', nodes=None, rights='received'):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'protocol.json').write_bytes(self.path.read_bytes())
        hb.atomic(directory / 'code-manifest.json', {})
        hb.atomic(directory / 'run-summary.json', dict(protocol_sha256=self.batch['sha256'], stopped_nodes_this_run=nodes or [], requests_reserved_total=2))
        hb.atomic(directory / 'checkpoints/USHA600000.json', dict(protocol_sha256=self.batch['sha256'], symbol='USHA600000', node='9602',
                  history_status=status, rights_status=rights))

    def protocol(self):
        return dict(schema_version=1, batches=[self.batch], collector_code={})

    def test_finished_complete(self):
        self.child(self.out)
        self.assertTrue(q.inspect_batch(self.batch, self.out, {})['data_complete'])

    def test_node_error_stops(self):
        self.child(self.out, nodes=['9602'])
        self.assertEqual(q.inspect_batch(self.batch, self.out, {})['reason'], 'node_error')

    def test_quarantine_explicit_terminal(self):
        self.child(self.out, status='quarantined')
        result = q.inspect_batch(self.batch, self.out, {})
        self.assertEqual(result['status'], 'finished'); self.assertFalse(result['data_complete'])

    def test_pending_rights_stops(self):
        self.child(self.out, rights='pending')
        self.assertEqual(q.inspect_batch(self.batch, self.out, {})['status'], 'halted')

    def test_process_failure_no_automatic_retry(self):
        with patch.object(q.subprocess, 'run') as run:
            run.return_value.returncode = 7
            self.assertEqual(q.execute(self.protocol(), self.out, self.base), 2)
            self.assertEqual(run.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'queue halted'):
                q.execute(self.protocol(), self.out, self.base)
            self.assertEqual(run.call_count, 1)

    def test_completed_resume_skips_process(self):
        def process(*args, **kwargs):
            self.child(self.out / 'batches/plan')
            return type('Result', (), {'returncode': 0})()
        with patch.object(q.subprocess, 'run', side_effect=process) as run:
            self.assertEqual(q.execute(self.protocol(), self.out, self.base), 0)
            self.assertEqual(q.execute(self.protocol(), self.out, self.base), 0)
            self.assertEqual(run.call_count, 1)

    def test_plan_mutation_rejected_before_process(self):
        self.path.write_text('{}')
        with patch.object(q.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'plan changed'):
                q.execute(self.protocol(), self.out, self.base)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

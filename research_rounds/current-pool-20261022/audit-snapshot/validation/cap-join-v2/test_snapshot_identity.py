"""Offline integration tests: small synthetic quotes, no economic accounts."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else Path(__file__).parents[2] / 'join_current_cap.py'
SNAPSHOT = '2026-10-22'
ACTUAL_OBSERVED = '2026-10-23T00:10:00+08:00'


class SnapshotIdentityIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.master = self.root / 'master.csv'
        fields = ['symbol', 'ths_symbol', 'exchange', 'currency', 'name',
                  'industry_index_symbol', 'southbound_sse_eligible']
        # Two A/H listings of one issuer; the unrelated issuer has the SAME name.
        rows = [
            ['600001.SH', 'USHAA600001', 'SH', 'CNY', 'SAME NAME', 'URFI881155', ''],
            ['00001.HK', 'UHKMHK0001', 'HK', 'HKD', 'SAME NAME', 'UFIH871116', 'True'],
            ['00002.HK', 'UHKMHK0002', 'HK', 'HKD', 'SAME NAME', 'UFIH871116', 'True'],
        ]
        with self.master.open('w', newline='') as f:
            w = csv.writer(f); w.writerow(fields); w.writerows(rows)
        self.links = self.root / 'links.csv'
        self.links.write_text('a_symbol,h_symbol,current_pair_status\n600001.SH,00001.HK,both_current\n')
        self.fx = self.root / 'fx.json'
        self.fx.write_text(json.dumps({'snapshot_date': SNAPSHOT, 'rates': [{
            'currency': 'HKD', 'rate_to_cny': .8, 'effective_date': SNAPSHOT,
            'observed_at': ACTUAL_OBSERVED, 'source': 'synthetic fixture only',
            'source_sha256': '0' * 64}]}))
        self.quote_file = self.root / 'quotes.json'
        self.output = self.root / 'output'
        self.quotes = {'as_of_date_label': SNAPSHOT, 'rows': [
            self.row('USHAA600001', 12_000_000_000),
            self.row('UHKMHK0001', 99_000_000_000),
            self.row('UHKMHK0002', 14_000_000_000),
        ]}

    def row(self, symbol, cap):
        return {'symbol': symbol, 'as_of_date_label': SNAPSHOT,
                'raw_fields': {'3541450': cap}, 'observations': {'202': {
                    'returned_symbol_matched': True, 'observed_at': ACTUAL_OBSERVED,
                    'response_sha256': '1' * 64}}}

    def execute(self):
        self.quote_file.write_text(json.dumps(self.quotes))
        return subprocess.run([sys.executable, str(SCRIPT), '--master', str(self.master),
                               '--ah-links', str(self.links), '--quotes', str(self.quote_file),
                               '--fx', str(self.fx), '--output', str(self.output)],
                              capture_output=True, text=True)

    def read_output(self):
        with (self.output / 'current-snapshot-selection.csv').open() as f:
            return {r['symbol']: r for r in csv.DictReader(f)}

    def assert_rejected_without_output(self):
        result = self.execute()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('snapshot date', result.stderr.lower())
        self.assertFalse(self.output.exists(), 'Rejected input must not create selected-pool artifacts')

    def test_next_day_observation_does_not_change_frozen_identity_or_company(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.read_output()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows['600001.SH']['issuer_id'], rows['00001.HK']['issuer_id'])
        self.assertNotEqual(rows['00001.HK']['issuer_id'], rows['00002.HK']['issuer_id'])
        for symbol in ('600001.SH', '00001.HK'):
            r = rows[symbol]
            self.assertEqual(float(r['company_market_cap_cny']), 12_000_000_000)
            self.assertEqual(r['company_cap_observed_at'], ACTUAL_OBSERVED)
            self.assertEqual(r['company_cap_as_of_date_label'], SNAPSHOT)
            self.assertEqual(r['company_cap_snapshot_date_status'], 'matched')
        self.assertEqual(float(rows['00002.HK']['company_market_cap_cny']), 11_200_000_000)

    def test_wrong_row_date_cannot_be_hidden_by_correct_batch_label(self):
        self.quotes['rows'][1]['as_of_date_label'] = '2026-10-23'
        self.assert_rejected_without_output()

    def test_missing_row_label_is_not_inferred_from_batch_or_observation(self):
        del self.quotes['rows'][1]['as_of_date_label']
        self.assert_rejected_without_output()

    def test_wrong_batch_date_is_rejected_even_when_rows_match(self):
        self.quotes['as_of_date_label'] = '2026-10-21'
        self.assert_rejected_without_output()

    def test_missing_label_on_no_data_row_also_rejected(self):
        self.quotes['rows'][1]['raw_fields'] = {}
        del self.quotes['rows'][1]['as_of_date_label']
        self.assert_rejected_without_output()

    def test_unlabelled_legacy_probe_keeps_raw_evidence_but_cannot_select(self):
        self.quotes = {'observed_at': ACTUAL_OBSERVED,
                       'records': [{'5': 'USHAA600001', '3541450': 12_000_000_000}]}
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        r = self.read_output()['600001.SH']
        self.assertEqual(float(r['company_cap_raw']), 12_000_000_000)
        self.assertEqual(r['company_market_cap_status'], 'unknown_snapshot_date')
        self.assertEqual(r['size_filter_status'], 'unknown')
        self.assertEqual(r['company_market_cap_cny'], '')
        self.assertEqual(r['company_cap_observed_at'], ACTUAL_OBSERVED)

    def test_explicit_wrong_probe_date_cannot_be_ignored(self):
        self.quotes = {'observed_at': ACTUAL_OBSERVED, 'as_of_date_label': '2026-10-23',
                       'records': [{'5': 'USHAA600001', '3541450': 12_000_000_000}]}
        self.assert_rejected_without_output()


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""No-network current-snapshot validation and raw recovery tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import struct
import unittest
import urllib.parse

import snapshot_batch as s
import history_batch as hb
from test_history_batch_offline import fake_ths, NetworkFailure


class FakeSnapshot:
    def __init__(self, fail=None):
        self.instance = 1; self.calls = 0; self.fail = fail
    def _send(self, payload):
        self.calls += 1
        self.query = {k: v[0] for k, v in urllib.parse.parse_qs(payload.decode()).items()}
    def _receive_matching(self, match):
        if self.calls == self.fail: raise NetworkFailure()
        kind, instance = int(self.query['id']), int(self.query['instance'])
        records = []
        for code in self.query['codelist'].split(','):
            row = {'5': self.query['market'] + code}
            row.update({field: 'Name' if field == '55' else 100 for field in self.query['datatype'].split(',')})
            records.append(row)
        data = struct.pack('<HII', 17, instance, kind) + json.dumps(records).encode()
        assert match(data)
        return data
    def close(self): pass


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.master = self.out / 'master.csv'
        self.master.write_text('ths_symbol,ths_market,code,ths_code\nUHKMHK0001,UHKM,00001,HK0001\n')
        self.item = dict(symbol='UHKMHK0001', market='UHKM', code='HK0001', node='9603')
        self.plan = dict(schema_version=1, as_of_date='2026-10-22', items=[self.item], max_requests=2,
                         source_master=dict(path=str(self.master), sha256=hb.digest(self.master.read_bytes())))

    def test_hk_native_code_not_display_code(self):
        s.validate_plan(self.plan)
        self.item['code'] = '00001'
        with self.assertRaisesRegex(ValueError, 'symbol/market/code'):
            s.validate_plan(self.plan)

    def test_master_hash_required(self):
        self.master.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'master hash'):
            s.validate_plan(self.plan)

    def test_fifty_codes_and_market_separation(self):
        a = [dict(symbol='USHA'+str(i), market='USHA', code=str(i), node='9602') for i in range(101)]
        groups = s.groups_for(dict(items=a+[self.item]))
        self.assertEqual([len(g['items']) for g in groups], [50, 50, 1, 1])

    def test_response_position_not_used(self):
        rows, audit = s.match_records([{'5': 'b'}, {'5': 'a'}, {'5': 'z'}], ['a','b','c'])
        self.assertEqual(set(rows), {'a','b'})
        self.assertEqual(audit['missing_symbols'], ['c']); self.assertEqual(audit['unexpected_symbols'], ['z'])

    def test_duplicate_symbol_quarantined(self):
        rows, audit = s.match_records([{'5':'a','10':1},{'5':'a','10':2}], ['a'])
        self.assertFalse(rows); self.assertEqual(audit['duplicate_symbols'], ['a'])

    def test_complete_resume_zero_requests(self):
        first = FakeSnapshot()
        with patch.object(hb.Collector, 'connection', return_value=first):
            self.assertEqual(s.run(self.plan, self.out, fake_ths(), None, 'hash'), 0)
        self.assertEqual(first.calls, 2)
        second = FakeSnapshot()
        with patch.object(hb.Collector, 'connection', return_value=second):
            self.assertEqual(s.run(self.plan, self.out, fake_ths(), None, 'hash'), 0)
        self.assertEqual(second.calls, 0)
        row = hb.read_json(self.out/'snapshot.json')['rows'][0]
        self.assertEqual(row['status'], 'received'); self.assertIsNone(row['derived_market_cap'])
        self.assertIsNotNone(row['observations']['202']['observed_at'])

    def test_node_error_stops_and_partial_is_explicit(self):
        conn = FakeSnapshot(fail=2)
        with patch.object(hb.Collector, 'connection', return_value=conn):
            self.assertEqual(s.run(self.plan, self.out, fake_ths(), None, 'hash'), 2)
        self.assertEqual(conn.calls, 2)
        self.assertEqual(hb.read_json(self.out/'snapshot.json')['rows'][0]['status'], 'partial')
        self.assertEqual(hb.read_json(self.out/'run-summary.json')['stopped_nodes_this_run'], ['9603'])

    def test_nonpositive_cap_not_ready(self):
        self.assertEqual(s.field_state(0,'3541450'), 'nonpositive')
        self.assertEqual(s.field_state(float('nan'),'3541450'), 'invalid_numeric')
        self.assertEqual(s.field_state(None,'3541450'), 'missing')


if __name__ == '__main__':
    unittest.main()

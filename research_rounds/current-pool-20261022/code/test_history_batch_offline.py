"""No-network collector tests: raw page clocks, recovery, identity and failures."""
import importlib.util
from pathlib import Path
from datetime import date, timedelta
from types import SimpleNamespace
import json
import struct
import tempfile
import unittest
import urllib.parse

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('history_batch_under_test', HERE / 'history_batch.py')
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)


class NetworkFailure(Exception): pass
class BudgetExhausted(Exception): pass
class HandshakeRejected(Exception): pass
class SessionUnavailable(Exception): pass


def records(n=1000):
    start = date(2026, 10, 22) - timedelta(days=n-1)
    return [{'1': int((start + timedelta(days=i)).strftime('%Y%m%d')), '7': 10, '8': 11, '9': 9, '11': 10, '13': 100, '19': 1000, '74': 1} for i in range(n)]


class FakeConnection:
    def __init__(self, wire_rows, failure_call=None, bad_rights=False):
        self.instance = 1; self.endpoint = h.ENDPOINTS['9603']; self.calls = 0
        self.rows = wire_rows; self.failure_call = failure_call; self.bad_rights = bad_rights
    def _send(self, payload):
        self.calls += 1; self.query = {k:v[0] for k,v in urllib.parse.parse_qs(payload.decode()).items()}
    def _receive_matching(self, match):
        if self.calls == self.failure_call: raise NetworkFailure()
        kind, inst = int(self.query['id']), int(self.query['instance'])
        if kind == 211:
            rs = [] if self.bad_rights else [{'1': 20260515, '471': 'raw rights'}]
        else:
            rs = [x for x in self.rows if str(x['1']) <= self.query['end']][-750:]
        body = struct.pack('<HII',17,inst,kind) + json.dumps(rs).encode()
        assert match(body)
        return body
    def close(self): pass


def fake_ths(bad_rights=False):
    def decode(body, allowed_kinds):
        _, inst, kind = struct.unpack_from('<HII',body)
        if bad_rights and kind == 211: raise ValueError('unsupported rights')
        return kind, inst, json.loads(body[10:])
    def bars(rs):
        return [dict(date=str(r['1']),open=r['7'],high=r['8'],low=r['9'],close=r['11'],volume=r['13'],amount=r['19']) for r in rs if r.get('11') is not None]
    return SimpleNamespace(decode=decode,daily_bars=bars,NetworkFailure=NetworkFailure,BudgetExhausted=BudgetExhausted,
                           HandshakeRejected=HandshakeRejected,SessionUnavailable=SessionUnavailable)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        self.item = {'symbol':'UHKMHK0700','node':'9603','end':'20261022','earliest':'1900-01-01','mode':'full','max_pages':10,'rights':False}
        self.plan = {'schema_version':1,'items':[self.item],'max_requests':20}
    def tearDown(self): self.tmp.cleanup()
    def collector(self, conn, bad_rights=False):
        c = h.Collector(self.plan,self.out,fake_ths(bad_rights),None,'frozen')
        c.connection = lambda node: conn
        return c
    def test_validation_rejects_unbounded_timeout_and_pool(self):
        for value in [None,0,-1,True,float('inf'),'20']:
            with self.assertRaises(ValueError): h.validate_plan(dict(self.plan,read_timeout_seconds=value))
        with self.assertRaises(ValueError): h.validate_plan(dict(self.plan,items=[self.item]*101))
        h.validate_plan(self.plan)
    def test_raw_not_cleaned_short_page(self):
        rs=records(750); rs[0]['11']=None
        outcome=h.classify_page(rs,{},'20261022','19000101')
        self.assertIsNone(outcome['stop'])
        self.assertEqual(len(fake_ths().daily_bars(rs)),749)
    def test_raw_auxiliary_overlap_conflict(self):
        rs=records(1); old={str(rs[0]['1']):dict(rs[0],**{'74':2})}
        self.assertEqual(h.classify_page(rs,old,'20261022','19000101')['stop'],'raw_overlap_conflict')
    def test_no_new_dates_is_not_complete(self):
        rs=records(1); old={str(rs[0]['1']):rs[0]}
        x=h.classify_page(rs,old,'20261022','19000101')
        self.assertEqual(x['stop'],'no_new_raw_dates');self.assertFalse(x['complete'])
    def test_interrupted_page_resume_reuses_first_page(self):
        first=FakeConnection(records(),failure_call=2)
        c=self.collector(first); cp=c.collect_one(self.item)
        self.assertEqual(len(cp['pages']),1);self.assertEqual(first.calls,2)
        raw_before=(self.out/cp['pages'][0]['attempt']/'response.bin').read_bytes()
        second=FakeConnection(records()); cp=self.collector(second).collect_one(self.item)
        self.assertEqual(cp['history_status'],'complete');self.assertEqual(second.calls,1)
        self.assertEqual(len(cp['pages']),2)
        self.assertEqual((self.out/cp['pages'][0]['attempt']/'response.bin').read_bytes(),raw_before)
        data=json.loads((self.out/'history/UHKMHK0700.json').read_text())
        self.assertEqual(data['raw_unique_dates'],1000)
        self.assertEqual(json.loads((self.out/'batch-state.json').read_text())['requests_reserved'],3)
    def test_completed_resume_performs_zero_requests(self):
        self.collector(FakeConnection(records(50))).collect_one(self.item)
        second=FakeConnection(records(50));self.collector(second).collect_one(self.item)
        self.assertEqual(second.calls,0)
    def test_rights_decode_error_does_not_pollute_history_or_repeat(self):
        self.item['rights']=True
        c=self.collector(FakeConnection(records(50)),True);cp=c.collect_one(self.item)
        self.assertEqual(cp['history_status'],'complete');self.assertEqual(cp['rights_status'],'decode_or_integrity_error')
        second=FakeConnection(records(50));self.collector(second,True).collect_one(self.item)
        self.assertEqual(second.calls,0)
        self.assertTrue((self.out/'rights/UHKMHK0700/attempt-001/response.bin').exists())
    def test_orphan_wrong_symbol_rejected(self):
        c=self.collector(FakeConnection(records(10)))
        base=self.out/'pages/UHKMHK0700/page-001'
        params=dict(market='UHKM',code='HK0005',start=-749,end='20261022',datatype=h.FIELDS,period=16384)
        c.fetch_evidence('9603',base,210,params)
        params['code']='HK0700'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):c.fetch_evidence('9603',base,210,params)
    def test_pending_half_file_not_recovered_as_complete(self):
        base=self.out/'pages/UHKMHK0700/page-001/attempt-001';base.mkdir(parents=True)
        (base/'response.bin.pending-dead').write_bytes(b'partial')
        conn=FakeConnection(records(10));cp=self.collector(conn).collect_one(self.item)
        self.assertEqual(conn.calls,1);self.assertEqual(cp['history_status'],'complete')
        self.assertTrue((base/'response.bin.pending-dead').exists())
    def test_protocol_mismatch_fails_before_network(self):
        h.atomic(self.out/'batch-state.json',{'protocol_sha256':'different','requests_reserved':0})
        with self.assertRaisesRegex(ValueError,'protocol mismatch'):self.collector(FakeConnection(records(1)))
    def test_request_budget_persists_and_stops(self):
        self.plan['max_requests']=1
        conn=FakeConnection(records());cp=self.collector(conn).collect_one(self.item)
        self.assertEqual(conn.calls,1);self.assertEqual(cp['last_error']['type'],'request_budget_exhausted')
        again=FakeConnection(records());self.collector(again).collect_one(self.item)
        self.assertEqual(again.calls,0)


if __name__=='__main__': unittest.main(verbosity=2)

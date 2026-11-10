"""Synthetic integrity/closure tests; these are not market or account results."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from finalize_a import boundary_status,verify_history,safe_child


def encoded(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()


def fixture(root):
    native='USHA600000';attempt=root/'pages'/native/'page-001'/'attempt-001';attempt.mkdir(parents=True)
    item=dict(symbol=native,node='9602',end='20261022',earliest='2026-10-20',mode='tail',rights=False,max_pages=1)
    protocol=encoded(dict(schema_version=1,items=[item],max_requests=1));(root/'protocol.json').write_bytes(protocol)
    query=dict(id=210,instance=1,zipversion=3,market='USHA',code='600000',start=-749,end='20261022',datatype='1,7,8,9,11,13,19,74',period=16384)
    records=[{'1':20261022,'7':10.,'8':11.,'9':9.,'11':10.5,'13':12300.,'19':123000.}]
    raw=b'synthetic parser fixture, never a real source response';decoded=encoded(records)
    (attempt/'request.json').write_bytes(encoded(dict(query=query,node='9602',endpoint='119.3.43.91:9602')))
    (attempt/'response.bin').write_bytes(raw);(attempt/'decoded.json').write_bytes(decoded)
    (attempt/'receipt.json').write_bytes(encoded(dict(sha256=sha(raw),bytes=len(raw),received_at='2026-10-22T23:00:00+08:00')))
    page=dict(attempt=str(attempt.relative_to(root)),query=query,raw_sha256=sha(raw),decoded_sha256=sha(decoded))
    cp=dict(symbol=native,node='9602',protocol_sha256=sha(protocol),history_status='complete',pages=[page],stop_reason='short_raw_page_source_boundary')
    (root/'checkpoints').mkdir();(root/'checkpoints'/(native+'.json')).write_bytes(encoded(cp))
    h=dict(symbol=native,node='9602',protocol_sha256=sha(protocol),requested_end='20261022',requested_earliest='20261020',history_status='complete',
           pages=[page],raw_unique_dates=1,rows_dropped_by_parser=0,bars=[dict(date='2026-10-22',open=10.,high=11.,low=9.,close=10.5,volume=12300.,amount=123000.)])
    (root/'history').mkdir();path=root/'history'/(native+'.json');path.write_bytes(encoded(h));return path,attempt


class IntegrityTest(unittest.TestCase):
    def test_matching_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            path,_=fixture(Path(d));x,cp,item,seen=verify_history(path)
            self.assertEqual(x['bars'][0]['volume'],12300.)
            self.assertTrue(seen.endswith('+08:00'))

    def test_raw_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path,attempt=fixture(Path(d));(attempt/'response.bin').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'Raw response hash'):verify_history(path)

    def test_export_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path,_=fixture(Path(d));x=json.loads(path.read_text());x['bars'][0]['volume']/=100;path.write_bytes(encoded(x))
            with self.assertRaisesRegex(ValueError,'differs from verified raw'):verify_history(path)

    def test_master_end_and_protocol_identity(self):
        with tempfile.TemporaryDirectory() as d:
            path,_=fixture(Path(d));x=json.loads(path.read_text());x['requested_end']='20261023';path.write_bytes(encoded(x))
            with self.assertRaisesRegex(ValueError,'date request mismatch'):verify_history(path)

    def test_wrong_endpoint_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path,attempt=fixture(Path(d));x=json.loads((attempt/'request.json').read_text());x['endpoint']='wrong:9602';(attempt/'request.json').write_bytes(encoded(x))
            with self.assertRaisesRegex(ValueError,'endpoint mismatch'):verify_history(path)

    def test_boundary_is_not_listing_date_or_suspension_fact(self):
        evidence=[dict(accepted=True,history_status='complete',stop_reason='short_raw_page_source_boundary',first='2020-01-03',requested_end='20261022')]
        start,tail=boundary_status('2020-01-03','2026-09-01','2013-01-04','2013-01-01','2026-10-22',evidence)
        self.assertEqual(start,'available_source_start_verified')
        self.assertEqual(tail,'latest_source_bar_before_end_suspension_or_source_limit')

    def test_tail_success_does_not_prove_start_boundary(self):
        evidence=[dict(accepted=True,history_status='complete',stop_reason='requested_earliest_reached',first='2023-01-03',requested_end='20261022')]
        start,tail=boundary_status('2020-01-03','2026-10-22','2013-01-04','2013-01-01','2026-10-22',evidence)
        self.assertEqual(start,'later_first_bar_unconfirmed');self.assertEqual(tail,'end_reached')

    def test_failed_source_never_certifies_boundary(self):
        evidence=[dict(accepted=False,history_status='complete',stop_reason='short_raw_page_source_boundary',first='2020-01-03',requested_end='20261022')]
        self.assertEqual(boundary_status('2020-01-03','2026-09-01','2013-01-04','2013-01-01','2026-10-22',evidence),('later_first_bar_unconfirmed','tail_unresolved'))

    def test_evidence_path_cannot_escape_batch(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'outside batch'):safe_child(Path(d),'../unrelated')


if __name__=='__main__':unittest.main(verbosity=2)

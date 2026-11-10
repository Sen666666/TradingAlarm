"""Synthetic integrity/closure tests; these are not market or account results."""
import hashlib,json,tempfile,unittest
from pathlib import Path
import pandas as pd
import numpy as np
from finalize_a import boundary_status,verify_history,safe_child,verified_raw_frame,annotate_observations,merge_observations


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


def observation(day='2026-10-20',volume=100.,amount=1000.,close=10.):
    return dict(trade_date=day,open=10.,high=11.,low=9.,close=close,volume=volume,amount=amount)


class RowPreservationTest(unittest.TestCase):
    def test_missing_volume_preserves_valid_price(self):
        x=annotate_observations(pd.DataFrame([observation(volume=None)]),'000001.SZ','fixture')
        self.assertTrue(x.price_eligible.iloc[0]);self.assertFalse(x.volume_eligible.iloc[0]);self.assertTrue(np.isnan(x.volume.iloc[0]))

    def test_missing_amount_preserves_volume_and_price(self):
        x=annotate_observations(pd.DataFrame([observation(amount=None)]),'000001.SZ','fixture')
        self.assertTrue(x.price_eligible.iloc[0]);self.assertTrue(x.volume_eligible.iloc[0]);self.assertTrue(np.isnan(x.amount.iloc[0]))

    def test_bad_geometry_stays_raw_but_not_price_eligible(self):
        x=annotate_observations(pd.DataFrame([observation(close=8.)]),'000001.SZ','fixture')
        self.assertEqual(len(x),1);self.assertFalse(x.price_eligible.iloc[0]);self.assertTrue(x.source_invalid.iloc[0])

    def test_one_incomplete_overlap_does_not_erase_good_tail(self):
        old=annotate_observations(pd.DataFrame([observation()]),'000001.SZ','old')
        new=annotate_observations(pd.DataFrame([observation(volume=None),observation('2026-10-22')]),'000001.SZ','new')
        merged,conflicts,status=merge_observations(old,new,'000001.SZ')
        self.assertTrue(status['accepted']);self.assertEqual(len(merged),2);self.assertFalse(conflicts);self.assertEqual(merged.volume.iloc[0],100.)

    def test_invalid_unique_date_not_dropped(self):
        old=annotate_observations(pd.DataFrame([observation()]),'000001.SZ','old')
        new=annotate_observations(pd.DataFrame([observation(),observation('2026-10-21',close=8.),observation('2026-10-22')]),'000001.SZ','new')
        merged,_,status=merge_observations(old,new,'000001.SZ');self.assertTrue(status['accepted']);self.assertEqual(len(merged),3);self.assertEqual(merged.price_eligible.tolist(),[True,False,True])

    def test_actual_valid_price_conflict_stays_quarantined(self):
        old=annotate_observations(pd.DataFrame([observation()]),'000001.SZ','old')
        new=annotate_observations(pd.DataFrame([observation(close=10.5),observation('2026-10-22')]),'000001.SZ','new')
        merged,conflicts,status=merge_observations(old,new,'000001.SZ');self.assertFalse(status['accepted']);self.assertEqual(len(merged),1);self.assertTrue(conflicts)

    def test_parser_missing_ohlc_date_recovers_without_inventing_price(self):
        with tempfile.TemporaryDirectory() as d:
            path,attempt=fixture(Path(d));records=json.loads((attempt/'decoded.json').read_text());records[0].pop('8')
            data=encoded(records);(attempt/'decoded.json').write_bytes(data)
            cp_path=path.parent.parent/'checkpoints'/path.name;cp=json.loads(cp_path.read_text());cp['pages'][0]['decoded_sha256']=sha(data);cp_path.write_bytes(encoded(cp))
            x=json.loads(path.read_text());x['pages']=cp['pages'];x['bars']=[];x['rows_dropped_by_parser']=1;path.write_bytes(encoded(x))
            raw,*_=verified_raw_frame(path);out=annotate_observations(raw,'000001.SZ','fixture')
            self.assertEqual(len(out),1);self.assertTrue(np.isnan(out.high.iloc[0]));self.assertFalse(out.price_eligible.iloc[0]);self.assertEqual(out.close.iloc[0],10.5)


if __name__=='__main__':unittest.main(verbosity=2)

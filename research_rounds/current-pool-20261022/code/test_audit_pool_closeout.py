"""Synthetic inventory tests; fixtures are never certified market observations."""
import tempfile,unittest
from pathlib import Path
from audit_pool_closeout import audit_rows,artifact,sha


def fixture():
    m=dict(symbol='600000.SH',name='fixture',ths_symbol='USHA600000',snapshot_date='2026-10-22',industry_index_symbol='sector')
    f=dict(symbol=m['symbol'],rows=5,price_eligible_rows=4,invalid_price_rows=1,missing_volume_rows=2,
        accepted_new_sources=1,rejected_new_sources=0,unresolved_source_failures=0,resolved_source_failures=0,
        start_status='available_source_start_verified',tail_status='latest_source_bar_before_end_suspension_or_source_limit',
        rights_status='received_current',rights_records=0,volume_unit='source_wire_units_unscaled')
    s=dict(symbol='sector',rows=5,price_eligible_rows=5,positive_volume_rows=0,price_rows_missing_or_nonpositive_volume=5,end_reached=True)
    c=dict(m,strategy_snapshot_filter_status='pass',size_filter_status='pass')
    return [m],[f],[s],[c]


class CloseoutTest(unittest.TestCase):
    def run_audit(self,args):return audit_rows(*args,check_artifact=lambda *_:'verified')
    def test_absent_manifest_and_cap_do_not_shrink_master(self):
        m,f,s,c=fixture();m.append(dict(m[0],symbol='00700.HK'))
        rows,audit=self.run_audit((m,f,s,c));self.assertEqual([x['symbol'] for x in rows],['600000.SH','00700.HK'])
        self.assertEqual(rows[1]['raw_collection'],'manifest_missing');self.assertEqual(rows[1]['snapshot'],'snapshot_row_missing')
        self.assertEqual(audit['manifest_missing_master_symbols'],['00700.HK'])
    def test_duplicate_identity_fails_instead_of_last_row_wins(self):
        args=fixture();args[1].append(args[1][0].copy())
        with self.assertRaisesRegex(ValueError,'duplicate symbol'):self.run_audit(args)
    def test_unknown_inputs_recorded_separately(self):
        args=fixture();args[1].append(dict(args[1][0],symbol='000001.SZ'))
        rows,audit=self.run_audit(args);self.assertEqual(len(rows),1);self.assertEqual(audit['manifest_symbols_outside_master'],['000001.SZ'])
    def test_missing_volume_keeps_valid_price_clock(self):
        row=self.run_audit(fixture())[0][0]
        self.assertEqual(row['price'],'valid_prices_with_quarantined_rows');self.assertEqual(row['volume'],'missing_volume_prices_preserved')
        self.assertFalse(row['economic_input_ready'])
    def test_raw_rights_empty_received_never_certifies_ledger(self):
        row=self.run_audit(fixture())[0][0]
        self.assertEqual(row['actions'],'raw_received_ledger_not_certified');self.assertEqual(row['rights_records'],0)
        self.assertFalse(row['action_ledger_certified'])
    def test_source_boundary_not_converted_to_listing_or_suspension_fact(self):
        row=self.run_audit(fixture())[0][0]
        self.assertEqual(row['source_boundary'],'documented_available_source_bounds')
        self.assertIn('tail_reason_not_established',row['issues']);self.assertNotIn('listing_date',row)
    def test_zero_missing_volume_does_not_certify_positive_or_units(self):
        args=fixture();args[1][0]['missing_volume_rows']=0
        row=self.run_audit(args)[0][0]
        self.assertEqual(row['volume'],'no_missing_volume_reported_positive_count_unknown')
        self.assertEqual(row['volume_unit'],'source_wire_units_unscaled')
    def test_industry_zero_volume_remains_visible(self):
        row=self.run_audit(fixture())[0][0]
        self.assertEqual(row['industry'],'mapped_sector_price_observations_present')
        self.assertEqual(row['sector_positive_volume_rows'],0);self.assertEqual(row['sector_price_rows_without_positive_volume'],5)
    def test_cap_failure_is_selection_fact_not_raw_failure(self):
        args=fixture();args[3][0]['strategy_snapshot_filter_status']='excluded'
        row=self.run_audit(args)[0][0]
        self.assertEqual(row['snapshot'],'excluded');self.assertEqual(row['raw_collection'],'current_raw_observations_verified')
    def test_corrupt_count_and_changed_artifact_cannot_get_price_status(self):
        args=fixture();args[1][0]['price_eligible_rows']=99
        row=self.run_audit(args)[0][0];self.assertEqual(row['price'],'price_counts_invalid')
        row=audit_rows(*fixture(),check_artifact=lambda *_:'hash_mismatch')[0][0]
        self.assertEqual(row['price'],'price_artifact_unverified');self.assertEqual(row['actions'],'raw_actions_unverified')
    def test_hash_verification_observes_actual_file_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'artifact';p.write_bytes(b'fixture');h=sha(p)
            self.assertEqual(artifact(p,h),'verified');p.write_bytes(b'changed')
            self.assertEqual(artifact(p,h),'hash_mismatch');self.assertEqual(artifact(p,''),'missing_expected_hash')
    def test_wrong_snapshot_date_and_industry_are_not_hidden(self):
        args=fixture();args[3][0].update(snapshot_date='2026-10-23',industry_index_symbol='changed')
        row=self.run_audit(args)[0][0]
        self.assertIn('cap_snapshot_date_mismatch',row['issues']);self.assertIn('master_snapshot_industry_disagreement',row['issues'])
        self.assertFalse(row['historical_currency_certified'])


if __name__=='__main__':unittest.main(verbosity=2)

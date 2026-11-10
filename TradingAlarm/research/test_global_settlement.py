"""Regression checks against saved, hashed issuer snapshots."""
import hashlib
import json
import unittest
from build_stock_features import ROOT
from reconcile_global_distributions import parse_ishares,parse_ssga


class SettlementSnapshotTests(unittest.TestCase):
    def test_issuer_snapshot_hashes(self):
        folder=ROOT/'data/global-transfer'
        for name,extension in [('IEF-issuer-download','xls'),('EFA-issuer-download','xls'),('SSGA-distributions','xlsx')]:
            record=json.loads((folder/f'{name}-source.json').read_text())
            self.assertEqual(hashlib.sha256((folder/f'{name}.{extension}').read_bytes()).hexdigest(),record['sha256'])

    def test_spy_invalid_payment_is_not_accepted(self):
        data=json.loads((ROOT/'data/global-transfer/SPY-issuer-distributions.json').read_text())
        bydate={r['ex_date']:r for r in data}
        self.assertFalse(bydate['2006-06-16']['settlement_verified'])
        self.assertTrue(all(r['settlement_verified'] for r in data if r['ex_date']>='2007-01-01'))
        self.assertEqual(bydate['2025-12-19']['pay_date'],'2026-01-30')
        self.assertAlmostEqual(bydate['2021-12-17']['amount'],1.636431)

    def test_issuer_cash_chronology_ishares(self):
        for symbol in ('IEF','EFA'):
            rows=parse_ishares(ROOT/f'data/global-transfer/{symbol}-issuer-download.xls')
            self.assertTrue(all(r['pay_date']>=r['record_date']>=r['ex_date'] for r in rows))


if __name__=='__main__':unittest.main()

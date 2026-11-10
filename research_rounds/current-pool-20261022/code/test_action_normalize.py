"""Small exact-terms tests; no network and no account engine."""
import unittest
import action_normalize as a


def row(text, day=20240517):
    return {'1': day, '471': text}


class TermsTests(unittest.TestCase):
    def test_hk_per_share_not_a_per_ten(self):
        hk = a.normalize_hk_record('UHKMHK0700', row('2024-05-17$每股3.4港元,'))
        ashare = a.normalize_a_record('USHA600000', row('2024-05-17(每十股 红利3.4元)$'))
        self.assertEqual(hk['event']['cash_per_old_share'], '3.4')
        self.assertEqual(ashare['event']['cash_per_old_share'], '0.34')

    def test_cash_components_cents_and_angles(self):
        for text, value in [('每股0.25港元,每股0.1港元','0.35'), ('每股53港仙,','0.53'),
                            ('每股港币8角7仙,','0.87'), ('每股港币2元3角,','2.3')]:
            self.assertEqual(a.normalize_hk_record('UHKMHK0001', row('2024-05-17$'+text))['event']['cash_per_old_share'], value)

    def test_ambiguous_suffix_not_silently_trimmed(self):
        x = a.normalize_hk_record('UHKMHK0001', row('2024-05-17$每股港币6角1仙4,'))
        self.assertIsNone(x['event']); self.assertTrue(x['unresolved'])

    def test_foreign_currency_retained_not_converted(self):
        x = a.normalize_hk_record('UHKMHK0770', row('2024-05-17$每股普通股0.10美元'))
        self.assertEqual(x['cash_by_currency'], {'USD':'0.1'}); self.assertIsNone(x['event'])
        y = a.normalize_hk_record('UHKMHK0770', row('2024-05-17$每股普通股0.10美元'), 'USD')
        self.assertEqual(y['event']['cash_per_old_share'], '0.1')

    def test_split_and_consolidation(self):
        split = a.normalize_hk_record('UHKMHK0700', row('2024-05-17$每1股拆分为5股'))
        merge = a.normalize_hk_record('UHKGHK8003', row('2024-05-17$每10股每股面值0.01港元之已发行及未发行现有股份将合并成1股'))
        self.assertEqual(split['event']['split_ratio'], '5'); self.assertEqual(merge['event']['split_ratio'], '0.1')

    def test_in_kind_subscription_and_cash_choice_not_cash(self):
        for text in ['每21股股份获发1股京东集团A类普通股,', '每持有1,256股可认购1股China Literature Ltd.预留股份',
                     '每3900股分派1股腾讯音乐美国预托股份,可选择收取现金']:
            x = a.normalize_hk_record('UHKMHK0700', row('2024-05-17$'+text))
            self.assertIsNone(x['event']); self.assertTrue(x['unresolved']); self.assertFalse(x['ledger_ready'])

    def test_preorigin_unknown_kept_but_not_active(self):
        x = a.normalize_actions('UHKMHK0700', [row('2024-05-17$未知条款')], 'HKD', '2024-05-18', '2026-10-22', 'saved-source')
        self.assertFalse(x['unresolved']); self.assertEqual(len(x['ignored_outside_window']), 1)
        self.assertEqual(x['status'], 'needs_review')

    def test_date_disagreement_and_same_date_records_block(self):
        x = a.normalize_hk_record('UHKMHK0700', row('2024-05-18$每股3.4港元,'))
        self.assertTrue(x['unresolved'])
        record = row('2024-05-17$每股3.4港元,')
        y = a.normalize_actions('UHKMHK0700', [record, record], 'HKD', '2013-01-01', '2026-10-22', 'saved-source')
        self.assertFalse(y['events']); self.assertEqual(len(y['unresolved']), 2)

    def test_stable_id_and_source_symbol_separated(self):
        record = row('2024-05-17$每股3.4港元,')
        x = a.normalize_actions('HK00700', [record], 'HKD', '2013-01-01', '2026-10-22', 'saved-source', market='HK', source_symbol='UHKMHK0700')
        self.assertEqual(x['series_id'], 'HK00700'); self.assertEqual(x['source_symbol'], 'UHKMHK0700')
        self.assertEqual(x['events'][0]['cash_per_old_share'], '3.4')

    def test_origin_day_requires_explicit_policy(self):
        record = row('2024-05-17$每股3.4港元,')
        x = a.normalize_actions('00700.HK', [record], 'HKD', '2024-05-17', '2026-10-22', 'saved-source')
        self.assertFalse(x['events']); self.assertFalse(x['ignored_outside_window'])
        self.assertIn('origin_date_action_requires_explicit_prior_or_origin_policy', x['unresolved'][0]['reasons'])

    def test_unsupported_preorigin_a_terms_keep_valid_date(self):
        record = row('1993-05-17(未知条款)$', day=19930517)
        x = a.normalize_actions('600000.SH', [record], 'CNY', '2013-01-01', '2026-10-22', 'saved-source')
        self.assertFalse(x['unresolved']); self.assertEqual(x['ignored_outside_window'][0]['source_effective_date'], '1993-05-17')

    def test_empty_rights_not_assumed_event_free(self):
        x = a.normalize_actions('UHKMHK0700', [], 'HKD', '2013-01-01', '2026-10-22', 'saved-source')
        self.assertTrue(x['unresolved'])


if __name__ == '__main__': unittest.main()
